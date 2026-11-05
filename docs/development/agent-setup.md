# Agent setup

## Supported arrangement

Use the official **Superpowers** plugin as the primary method and the repository
**ponytail** skill as a complementary minimal-change discipline. Required TDD,
acceptance criteria, security checks, and the issue/PR workflow remain in force.

This repository does not install global configuration or lifecycle hooks. The
Ponytail skill is a complete, instruction-only upstream file with its license;
its source revision is recorded in [.agents/README.md](../../.agents/README.md).
It does not provide the plugin's persistent mode flag, status line, or automatic
per-turn/subagent hook injection. Request a level explicitly when needed.

## Fresh clone prerequisites

1. Open the repository root as your Codex workspace.
2. Check the current session's skill catalogue before installing anything.
   If Superpowers is already present, keep that installation. Do not also copy
   its skills into `.agents/skills/` or a user skill directory.
3. If it is absent, use the official plugin marketplace: in the Codex app open
   **Plugins**, find **Superpowers** in Coding, and select **+**. In Codex CLI,
   open `/plugins`, search for Superpowers, and select **Install Plugin**.
   These are manual prerequisites, not commands run by this repository.
4. Start a fresh session from the repository root after setup. The project
   `ponytail` skill lives in `.agents/skills/ponytail/SKILL.md` and requires no
   separate plugin installation. If another Ponytail installation already
   exists, resolve the duplicate before relying on automatic selection.

Superpowers 7.0.1 was present in the development session. This is the observed
baseline, not a claim that a marketplace install pins that version. Record the
actual version used when reproducing verification; no Superpowers code is
vendored by this repository.

## Verify discovery and invocation

In the fresh session, send these requests separately:

```text
List the available Superpowers and Ponytail skills and their exact names.
Read the repository AGENTS.md and report the verified quality commands.
Invoke superpowers:using-superpowers and report which skill file was loaded.
Invoke ponytail full and report which skill file was loaded.
```

Names may be namespaced by the host; use the exact names from its catalogue if
they differ. Check that Ponytail resolves to this repository's copy and that
Superpowers appears once. A model saying it knows the method, or finding a file
on disk, does not prove automatic discovery. Record the catalogue, actual loaded
skills, version, and outcome in the PR. A manual file read is useful fallback
instruction loading, but must be reported separately from native discovery.

For a non-mutating behavior check, ask the agent to explain how it would handle
a small implementation task. It should preserve Superpowers' TDD workflow and
Ponytail's smallest complete change; it must not drop required acceptance checks.

Repeat the documented [quality checks](../../CONTRIBUTING.md#quality-checks).
Confirm all relative links in [AGENTS.md](../../AGENTS.md) exist in the checkout,
and that neither the guide nor agent entry points require personal cache paths,
credentials, or ignored planning documents.

## Verification recorded for this change

On 2026-11-05, the existing session catalogue exposed
`superpowers:using-superpowers`, `superpowers:executing-plans`, and
`superpowers:test-driven-development`; their instructions were loaded. Ponytail
was not in that session's initial catalogue. Its self-contained project skill
was added and loaded directly as instructions.

**Fresh-session native discovery and explicit invocation of the added Ponytail
skill remain pending.** Do not treat this record as that verification. Reopening
the workspace/session and recording the check above is the remaining runtime
setup check; file presence alone is insufficient.

## Sources and installation choice

- [Official skills documentation](https://learn.chatgpt.com/docs/build-skills).
- [Official AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
- [Superpowers installation](https://github.com/obra/superpowers#installation).
- [Ponytail installation at the incorporated revision](https://github.com/DietrichGebert/ponytail/blob/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846/INSTALL.md).
- [Ponytail portability at that revision](https://github.com/DietrichGebert/ponytail/blob/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846/docs/agent-portability.md).

Ponytail supports both a full plugin and direct skill loading. The direct skill
option fits project scope and avoids duplicating Superpowers. Full plugin
installation would add lifecycle hooks and user-level state. No hooks are
incorporated or activated here; any later plugin migration must inspect its
hook map and referenced scripts before activation and resolve duplicate skills.
