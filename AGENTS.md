# Forge Codex Project Instructions

## Forge Skill Delegation Contract

Invoking a Forge workflow skill is itself permission to dispatch the Forge agent team required by that workflow.

- `forge:develop`, `forge:plan`, `forge:implement`, `forge:code-review`, `forge:test`, and `forge:diagnose` imply automatic delegation to the relevant Forge agents.
- `forge:evaluate` implies automatic delegation when team/review mode is active.
- The user should not have to separately say "use sub-agents", "delegate", or "parallelize" after invoking a Forge skill.
- If the active Codex session policy still blocks `spawn_agent`, surface that as an environment-policy limitation rather than silently falling back to single-agent execution.

## Documentation

When editing this repo's user-facing documentation, keep the role names aligned with the current agent set. Use `doc-writer`, not the legacy `tech-writer`.
