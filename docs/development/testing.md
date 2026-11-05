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
`MAY_MCP_ALLOW_WRITES` from the test process environment.

Shared fixtures:

- `synthetic_vehicle`: a full fictitious May 0.44.2 vehicle response.
- `settings_factory(**overrides)`: synthetic environment inputs; the validated
  Settings class belongs to issue #5 and will extend this fixture.
- `mock_may_http(handler=None)`: HTTPX MockTransport; unexpected requests fail
  when no handler is provided.
- `mcp_client_factory(server)`: the SDK Client for in-memory protocol tests.
- `may_test_instance`: integration-only disposable lifecycle and credentials;
  its representation hides the generated key.

The protocol fixture is ready for issue #6. No production MCP server or vehicle
tools exist yet; this harness does not demonstrate their functionality.

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
May version before creating a synthetic account and vehicle. It refuses to seed
the same account twice. Credentials remain in the container's temporary storage
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

## CI and diagnostics

[CI](../../.github/workflows/ci.yml) has separate quality, offline-test, and
real-May integration jobs. Quality and offline suites run on Windows and Ubuntu;
the real-May container job runs on Ubuntu. Missing Docker, provisioning errors,
unexpected data and authentication failures fail integration visibly.

If provisioning fails, inspect only the disposable project's status. Avoid
printing its generated key file, raw captured command output or request headers.
Recreate the project to reset its data. Local and CI results must be reported
separately from deployment or ChatGPT/Codex/Claude interoperability checks.
