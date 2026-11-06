# May MCP

A Model Context Protocol server for [May](https://github.com/dannymcc/may), a
self-hosted vehicle manager.

## Project status

Vehicle, fuel, expense, trip and charging read and optionally enabled CRUD tools
and the stdio MCP server are implemented. Authenticated Streamable HTTP uses an
external OAuth provider; see [remote authentication](docs/authentication.md).
[Client compatibility](docs/compatibility.md) records verified Codex CLI stdio
operations and the remaining ChatGPT, Claude Code and remote-client checks.
The [container deployment guide](docs/deployment.md) covers the pinned non-root
image, runtime configuration, health checks, HTTPS proxy and external auth storage.
The [spending summary](docs/summary.md) uses May's Home Assistant Bearer API for
verified account currency and reports exact recorded totals with explicit coverage
and exclusions. Owner-only currency metadata is unavailable for shared-only access.

Follow [the delivery tracker](https://github.com/ivanceba/may-mcp/issues/1) for
the implementation issues and acceptance criteria.
The [capability inventory](docs/capabilities.md) records implemented operations,
supported upstream surfaces and unresolved maintenance/reminder/document gaps.

Validated settings and the guarded asynchronous May HTTP client are implemented.
See [the HTTP boundary guide](docs/development/client.md) for configuration,
write protection and safe error handling. Run `uv run --frozen may-mcp` from a
local MCP client using the [stdio setup guide](docs/stdio.md). Fuel fields and
pagination behavior are documented in the [fuel guide](docs/fuel.md); see the
[expense guide](docs/expenses.md) for amounts, categories and permissions.
Trip fields and purpose discovery are covered in the [trip guide](docs/trips.md).
Energy units, charger lookup and optional fields are in the [charging guide](docs/charging.md).

## Development setup

Install [uv](https://docs.astral.sh/uv/) version **0.11.8**, then run:

```sh
uv python install
uv sync --locked
```

The project uses Python 3.12.13. The committed lockfile fixes dependency versions.

Run the quality checks:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Apply formatting locally with `uv run ruff format .` and inspect the resulting
diff. CI checks formatting without changing files.

Run the offline harness with `uv run --frozen pytest tests/unit tests/contract tests/protocol -q`.
For the disposable real-May tests, Docker requirements and cleanup, see the
[testing guide](docs/development/testing.md). The suite covers vehicle MCP calls
and real synthetic May persistence; see the compatibility record for named clients.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the issue, TDD, and PR workflow.
For Codex development, follow the [agent setup guide](docs/development/agent-setup.md)
and [repository instructions](AGENTS.md).

## Delivery scope

- Typed tools for vehicles, fuel logs, expenses, trips, and charging sessions.
- Read-only mode by default; environment-controlled write access.
- stdio and authenticated Streamable HTTP transports.
- Client setup: [ChatGPT](docs/clients/chatgpt.md), [Codex](docs/clients/codex.md),
  and [Claude Code](docs/clients/claude.md). Unverified paths are marked explicitly.

The capability inventory and delivery tracker distinguish delivered functionality
from remaining API gaps and client/deployment verification.
