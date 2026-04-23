# Phase 3: Wave Dispatch

Dispatch agents for Wave {{CURRENT_WAVE}} of {{TOTAL_WAVES}}.

## Tasks in This Wave

{{WAVE_TASKS}}

## Instructions

For each task in the wave, dispatch the assigned agent with:

1. Task details from the plan file (path from handoff or `.codex/forge-codex/memory/plans/`)
2. Branch name for their sub-branch
3. TDD instructions per `templates/tdd-protocol.md`:
   - Write failing test first
   - Verify it fails with expected error
   - Implement minimal code to pass
   - Verify all tests pass (new + existing)
4. Cross-reference beads if available

Follow `templates/parallel-dispatch.md` for dispatch protocol.

## Sub-Branch Creation

For each task in this wave:
```
git checkout forge/[feature-name]
git checkout -b forge/[feature-name]/[task-name]
```

## Agents to Dispatch

{{AGENT_LIST}}

## Blocker Protocol

If any agent reports a blocker during implementation:
1. Classify: missing dependency, unclear requirement, technical obstacle, external
2. Route to appropriate agent for resolution
3. Update plan if wave structure changes
4. Other agents in the wave continue unblocked
