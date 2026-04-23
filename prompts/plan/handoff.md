Write the handoff file and render the dashboard.

## Handoff Content
Write `.codex/forge-codex/memory/handoff-plan.md` with:
- Plan location (`{{PLAN_FILE}}`)
- Task count and assignments
- Dependencies summary
- Beads state

## Dashboard
Render the skill completion dashboard per `templates/dashboard.md`.

## Suggested Next
- `evaluate --mode pre` (optional: review plan before implementing)
- `implement` (proceed directly to implementation)

## Git Checkpoint
```
git add .codex/forge-codex/ && git commit -m "workflow: plan complete"
```
