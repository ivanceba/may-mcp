# Project agent resources

The repository entry point is [AGENTS.md](../AGENTS.md). Follow the
[setup and verification guide](../docs/development/agent-setup.md).

Superpowers is supplied by the official plugin; do not copy its skills here as
well. Ponytail is provided by [this project skill](skills/ponytail/SKILL.md),
including its [MIT license](skills/ponytail/LICENSE). Do not install a second
Ponytail plugin alongside it for this project.

The copied Ponytail skill is unmodified from
[DietrichGebert/ponytail at revision 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846](https://github.com/DietrichGebert/ponytail/tree/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846).
Only `skills/ponytail/SKILL.md` and `LICENSE` are incorporated. The skill is
self-contained and references no other resources. No hooks, executables, mode
state, status line, or other Ponytail skills are included.

For an update, inspect the upstream skill and any newly referenced resources,
preserve the license, record the new revision here, and repeat the setup checks
in a PR. Do not run an upstream installer or activate hooks as part of an update.
