---
description: |
  Execute tests, analyze coverage, investigate failures, and identify coverage
  gaps. Uses QA Reviewer as lead with Investigator support for failure analysis.
  Supports --quick mode.
---

# forge-codex Test — Execution, Coverage & Failure Analysis

When this skill activates, invoke the orchestrator script.

Read `templates/codex-runtime.md` before executing the workflow if you need a
tooling reminder.

The test script is located relative to this repo root
(the nearest ancestor containing `README.md`).

## CRITICAL: Progress Tracking

**The orchestrator outputs a phase-todo JSON block at the start of every phase.**
Mirror it in Codex immediately, ideally with `update_plan`, before doing any
other work. As you work:
- Mark items `in_progress` when starting them
- Mark items `completed` when done
- Add new items as sub-tasks emerge

**If you skip progress tracking, the user has no visibility into what you are doing.**

## Invocation

Find the repo root directory, then run:

<invoke cmd="python3 [repo-root]/scripts/test/test.py --step 1" />

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--step` | Yes | Current phase (1-6) |
| `--target` | No | Test command, path, or pattern (auto-detected from handoff if omitted) |
| `--quick` | No | Quick mode: minimal review loops, lead agents only |

After step 1, state is persisted to `.codex/forge-codex/state/test.json` and
subsequent steps auto-detect it.

## Subsequent steps

<invoke cmd="python3 [repo-root]/scripts/test/test.py --step N" />

Replace N with the step number printed at the end of each phase.

Do NOT analyze or explore first. Run the script and follow its output.
