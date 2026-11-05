# Working on May MCP

This Python 3.12 package contains validated settings and a guarded asynchronous
HTTP client for May, vehicle/fuel/expense/trip/charging tools, and a stdio MCP server. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the issue, PR, and TDD workflow.

## Layout and checks

- `src/may_mcp/`: package source.
- `src/may_mcp/tools/`: explicit typed MCP tools.
- `.github/workflows/ci.yml`: Windows and Ubuntu quality checks.
- `.agents/skills/ponytail/`: pinned, instruction-only Ponytail skill.
- [Agent setup](docs/development/agent-setup.md): prerequisites and discovery checks.

Use uv 0.11.8 and the committed Python version:

```sh
uv python install
uv sync --locked
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src
uv build
```

See [README.md](README.md) for available test layers and their commands.
Do not report quality checks as functional or deployed integration coverage.

## Development workflow

Use Superpowers as the primary development method. Apply Ponytail as a
complementary discipline: the smallest change that meets the full acceptance
criteria. It never reduces required tests, validation, or security checks.
Before implementation, verify the skills are available using the setup guide.

Work on an issue branch and open a linked PR with `Closes #N`. Use TDD for
behavior changes: observe the intended failure, implement, verify, refactor.
Auto-merge requires green required checks and resolved blocking review findings.
Never bypass branch rules or push implementation directly to `main`.
After each issue's PR merges, update delivery tracker #1 with its status and PR.

Keep public documentation and tool descriptions in English. Use synthetic data
and disposable May instances for tests. Never use production writes as tests.
Keep credentials and personal records out of commits, logs, and fixtures.
Local plans and execution evidence live under ignored `docs/superpowers/`;
public documentation must work without that directory.
