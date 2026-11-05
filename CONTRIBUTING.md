# Contributing

## Issue and pull request workflow

Start from an open issue with acceptance criteria. Work on a branch such as
`feat/5-may-client` and open a PR targeting `main`. Include `Closes #N` and the
actual verification results in the PR description.
After an issue's PR merges, update the [delivery tracker](https://github.com/ivanceba/may-mcp/issues/1)
with the completed task, PR and relevant verification or remaining limitations.

Auto-merge is authorized once required checks pass and blocking review findings
are resolved. Do not bypass branch rules, weaken checks, or push implementation
changes directly to `main`.

## Test-driven development

For each behavior, write a focused test first, observe it failing for the intended
reason, implement the minimum required change, observe it passing, and refactor.
Run affected regression tests and the quality checks before submitting a PR.
Missing dependencies and syntax errors do not demonstrate a behavior's red phase.

Environment configuration is verified with installation and tool checks rather
than artificial tests that copy the configuration. The test harness provides
offline guards, HTTP contract fixtures, MCP client helpers, and an isolated
real-May smoke test. See [the testing guide](docs/development/testing.md). Do not
report missing or skipped integration checks as passing.

## Quality checks

Use uv 0.11.8 and the committed Python version and lockfile:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Run the offline suite with `uv run --frozen pytest tests/unit tests/contract tests/protocol -q`.
Real-May integration requires Docker and explicit opt-in; run
`uv run --frozen pytest --may-integration -q` for the full suite, following the
testing guide. Selected integration tests fail when provisioning is not enabled.

Ruff handles both lint and formatting. Use `uv run ruff format .` to apply
formatting. Type checks use mypy in strict mode. Do not automatically rewrite
unrelated code or disable rules merely to make CI pass.

`uv sync --locked` rejects a lockfile that no longer matches `pyproject.toml`.
When intentionally changing dependencies, run `uv lock`, inspect both files,
and commit them together. Build-backend versions are constrained in the project
configuration as well.

## Documentation and data

Write public documentation, tool descriptions, agent instructions, issues, and PR
descriptions in English. Public documentation must work from a fresh clone.

`docs/superpowers/` is ignored and contains local designs, plans, and execution
evidence. Do not link to it from public documentation or force-add it to Git.

Use synthetic records and a disposable May instance for integration tests. Do
not commit API keys, `.env` files, private documents, personal vehicle data, or
production databases. Never use production writes to test behavior.
