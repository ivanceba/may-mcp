# May MCP

A Model Context Protocol server for [May](https://github.com/dannymcc/may), a
self-hosted vehicle manager.

## Project status

Vehicle, fuel, expense, trip and charging read and optionally enabled CRUD tools
and the stdio MCP server are implemented. Remote HTTP authentication and
application-specific client integrations are not implemented yet.

Follow [the delivery tracker](https://github.com/ivanceba/may-mcp/issues/1) for
the implementation issues and acceptance criteria.

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
and real synthetic May persistence; named consumer-client verification is pending.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the issue, TDD, and PR workflow.
For Codex development, follow the [agent setup guide](docs/development/agent-setup.md)
and [repository instructions](AGENTS.md).

## Planned integration

- Typed tools for vehicles, fuel logs, expenses, trips, and charging sessions.
- Read-only mode by default; environment-controlled write access.
- stdio and authenticated Streamable HTTP transports.
- Connection examples and verification for ChatGPT, Codex, and Claude.

These are planned capabilities, not currently available features.
