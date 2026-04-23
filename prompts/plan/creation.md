Dispatch the **Planner** to create the detailed implementation plan.

## Architecture
{{ARCHITECTURE_NOTES}}

## Instructions for Planner

Follow `templates/writing-plans.md` to create:
1. Task breakdown with exact file paths, assigned agents, TDD steps
2. Validate each task against INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
3. Parallelization map and branch strategy
4. Risk register with mitigations
5. Pre-mortem session per `templates/pre-mortem.md`: imagine implementation failed — surface hidden risks in task ordering, dependencies, and assumptions
6. Rollback strategy (specific, not "revert commits")
7. Acceptance criteria per task

Write the plan to `{{PLAN_FILE}}`.

## Agents to Dispatch
- **Planner** (lead): Plan creation
- **Architect** (available): Architecture clarification
