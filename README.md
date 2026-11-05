# May MCP

A Model Context Protocol server for [May](https://github.com/dannymcc/may), a
self-hosted vehicle manager.

## Project status

The development environment is being prepared. Vehicle tools, the MCP server,
remote authentication, and client integrations are not implemented yet.

Follow [the delivery tracker](https://github.com/ivanceba/may-mcp/issues/1) for
the implementation issues and acceptance criteria.

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

There are no behavioral tests yet. The isolated test harness is tracked in
[issue #4](https://github.com/ivanceba/may-mcp/issues/4). Passing environment
checks does not demonstrate a working MCP integration.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the issue, TDD, and PR workflow.

## Planned integration

- Typed tools for vehicles, fuel logs, expenses, trips, and charging sessions.
- Read-only mode by default; environment-controlled write access.
- stdio and authenticated Streamable HTTP transports.
- Connection examples and verification for ChatGPT, Codex, and Claude.

These are planned capabilities, not currently available features.
