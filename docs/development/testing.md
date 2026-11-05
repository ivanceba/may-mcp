# Testing May MCP

The offline suite uses synthetic records, HTTPX MockTransport, and the official
MCP SDK client. Integration tests provision an independent May 0.44.2 container
pinned by image digest in [compose.test.yml](../../compose.test.yml). They never
use production databases, credentials, volumes, or a caller-supplied server URL.

## Offline checks

Install the locked environment using [the development instructions](../../README.md),
then run:

```sh
uv run --frozen pytest tests/unit tests/contract tests/protocol -q
```

An autouse fixture blocks Python IP sockets and DNS during offline test setup
and execution. Unix sockets are allowed for asyncio internals; the pinned
pytest-asyncio function runner initializes first so Windows can create its
internal loopback self-pipe. Both synchronous and async tests prove a network
socket is rejected. A deliberate incorrect fixture assertion was observed
failing during setup verification, restored to passing, then removed.

This is a Python-process guard, not an operating-system sandbox: subprocesses
do not inherit monkeypatches. Keep child-process tests synthetic and explicitly
scoped. The fixture removes inherited `MAY_BASE_URL`, `MAY_API_KEY`, and
`MAY_MCP_ALLOW_WRITES` and all `MAY_MCP_OAUTH_*` variables from the test process
environment. Tests construct their own synthetic configuration.

Shared fixtures:

- `synthetic_vehicle`: a full fictitious May 0.44.2 vehicle response.
- `settings_factory(**overrides)`: build validated Settings from synthetic
  environment inputs; overrides use the environment variable names.
- `mock_may_http(handler=None)`: HTTPX MockTransport; unexpected requests fail
  when no handler is provided.
- `mcp_client_factory(server)`: the SDK Client forced into framed JSON-RPC mode
  for in-memory protocol tests, rather than SDK 2's direct in-process dispatch.
- `may_test_instance`: integration-only disposable lifecycle and credentials;
  its representation hides both generated keys.

Protocol tests verify vehicle discovery, typed mutations, partial updates, safe
errors, and rejection of direct write calls in read-only mode. Real-May CRUD
tests verify persistence, null/zero/false updates, shared read access versus
owner-only modification, private-vehicle read denial, and cascading fuel-log
deletion. Other documented cascade relationships are inspected from pinned May
models; the integration test exercises a fuel-log dependent record.
Fuel tests additionally cover full-history page metadata, malformed upstream
pages, bounds/order, strict dates/numbers, real fuel CRUD with tax totals,
unknown versus confirmed-zero readings and May's zero-to-null normalization.
Expense tests cover live category lookup, amount/date/optional-field persistence,
instruction-like notes retained as data, full-history pagination, shared mutations
and safe inaccessible-record errors using the two synthetic accounts.
Trip tests cover purpose lookup, start/end readings including confirmed zero,
optional fuel-level null/zero/100 semantics, preserved upstream distance/fuel-used
fields, paginated CRUD, shared-user mutations and private-record denial.
Charging tests use a synthetic EV for persisted energy, prices, costs, SoC and
time formats, plus optional null/zero updates, paging, charger validation,
shared mutations and private-record denial. Vehicle deletion warnings also name
parts, whose additional ORM cascade is inspected in the pinned upstream models.
Summary tests cover exact Decimal sums, included tax, separate currencies,
inclusive dates, exclusions, corrupted/repeated/changing pages and page budgets.
Real May tests traverse multiple pages, obtain account currency from the Home
Assistant Bearer endpoint and verify exact known totals. Shared-only access
retains honest unknown-currency exclusions when owner-only metadata is absent.
A separate integration test starts the real stdio subprocess, reads synthetic
May records and verifies the connection survives a tool error. This does not
establish interoperability with ChatGPT, Codex or a particular Claude client.

## Real-May checks

Docker Engine and Docker Compose v2 must be available on PATH in the same
environment as pytest. On Windows with Docker in WSL only, run these commands
inside WSL with Linux Python/uv; do not reuse a Windows `.venv` in Linux. If
sharing one checkout, set `UV_PROJECT_ENVIRONMENT` to a separate ignored Linux
environment directory and keep the committed lockfile unchanged.

```sh
uv sync --locked
uv run --frozen pytest -m integration tests/integration --may-integration -q
```

`--may-integration` explicitly permits fixture provisioning. Without it, selected
integration tests **fail**, rather than silently skip. To run the complete suite:

```sh
uv run --frozen pytest --may-integration -q
```

The fixture starts only Compose project `may-mcp-test`, waits for health, and runs
[the provisioner](../../scripts/provision_test_may.py) inside that container as
the May user. The provisioner checks the test-only flag, database location and
May version before creating two synthetic accounts, one shared vehicle owned by
the primary account, and a private vehicle owned by the second account. It refuses
to seed the same account twice. CRUD tests clean up additional synthetic vehicles
in `finally`. Credentials remain in the container's temporary storage
and fixture memory; command output is captured and never echoed on failure.

May listens on host `127.0.0.1:15050`; ensure the port is free. A project-specific
Docker bridge provides local connectivity. An `internal` Docker network is not
used because it suppresses the published port with the verified Docker runtime.
This bridge does not enforce container egress restrictions. Test code restricts
socket connections to loopback and all requests target the fixed disposable URL.
The synthetic app has no configured real notification targets or personal data.

The smoke test verifies unauthenticated requests are rejected and the generated
API key lists exactly the synthetic vehicle. This tests a real May HTTP service
and persistence, independently of mocked HTTP tests.

The fixture removes its Compose project in `finally`. Its data is a fresh tmpfs
mount, not a named production volume. CI also runs cleanup on failure. If a test
run is interrupted, remove only these explicitly named resources from the repo:

```sh
docker compose --project-name may-mcp-test -f compose.test.yml down --volumes --remove-orphans
```

Do not run two integration suites concurrently against this fixed project/port.
The fixture refuses to reuse an existing project container before starting its
cleanup-protected lifecycle; inspect leftovers before explicitly removing them.
Do not substitute a production Compose file or pass production environment data.

## OAuth checks

The same opt-in integration command also runs
[the OAuth suite](../../tests/integration/test_oauth_flow.py). It provisions only
Compose project `may-mcp-oauth-test` from the pinned official Keycloak 26.8.2 image
in [the disposable profile](../../compose.oauth-test.yml). HTTPS binds to
`127.0.0.1:15060`; a fresh certificate and key are generated in a temporary
directory, mounted read-only and removed after container teardown.
The directory is owner-only (`0700`) and the private key is owner-only (`0600`).
Run these tests as a non-root Linux/WSL user; the fixture runs Keycloak with that
same UID, retaining the official image's group 0 for its writable data directory.
It does not make the TLS key group/world-readable to handle CI UID differences.
Test HTTP
clients trust only that generated certificate in their additional isolated trust
context; TLS verification and secure cookies remain enabled.

The fixture imports a fictitious realm/user and public PKCE clients with exact
loopback callbacks. The separately named H2 volume exists only for this test and
allows a provider restart to exercise persistent sessions, signing keys and
refresh state. It is removed in `finally`; no existing state is reused.
The fixture refuses pre-existing project containers or labeled volumes.

```sh
uv run --frozen pytest tests/protocol/test_http_auth.py -q
uv run --frozen pytest tests/integration/test_oauth_flow.py --may-integration -q
```

The suite covers the real code/PKCE flow, incorrect proof, code replay, callback
and resource mismatch, renewal/rotation/revocation, expiry and provider restart.
The official SDK HTTP client then discovers tools and performs real synthetic
May CRUD through the ASGI resource app, followed by a new read-only app instance
that hides and rejects writes. This verifies protocol/provider/API wiring, not
ChatGPT, Codex or Claude application interoperability or public deployment.
Offline tests cover invalid signatures/claims, required scope, secret separation,
metadata/challenges, Host validation, key-cache refresh/failures and client cleanup.

If interrupted, inspect leftovers and remove only this explicitly named project:

```sh
docker compose --project-name may-mcp-oauth-test -f compose.oauth-test.yml down --volumes --remove-orphans
```

Never use this development IdP or its published synthetic credentials in
production. See [authentication](../authentication.md) for provider limitations,
shared May identity, JWT revocation delay and production persistence boundaries.

## CI and diagnostics

[CI](../../.github/workflows/ci.yml) has separate quality, offline-test, and
real-May integration jobs. Quality and offline suites run on Windows and Ubuntu;
the real-May container job runs on Ubuntu. Missing Docker, provisioning errors,
unexpected data and authentication failures fail integration visibly.

If provisioning fails, inspect only the disposable project's status. Avoid
printing its generated key file, raw captured command output or request headers.
Recreate the project to reset its data. Local and CI results must be reported
separately from deployment or ChatGPT/Codex/Claude interoperability checks.
