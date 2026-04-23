# forge-codex

A Codex-native agent toolkit for structured software delivery: investigation, planning, implementation, review, testing, diagnostics, and workflow continuity across sessions.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/your-org/forge-codex.git /path/to/forge-codex

# Enter the project
cd /path/to/forge-codex
```

Then use the repo as the home for Codex-oriented workflow assets, skills, prompts, and orchestrators.

## Goals

- Turn a structured multi-skill workflow model into a Codex-first environment
- Support multi-step, resumable engineering workflows instead of one-shot prompts
- Separate skill orchestration from reusable methodology templates
- Preserve handoff context between phases and between sessions
- Make review, verification, and diagnostics first-class parts of the workflow

## Planned Skills

| Skill | Purpose | Typical Invocation |
|-------|---------|--------------------|
| **develop** | Investigate a problem space and shape solution options | `develop <problem or feature>` |
| **plan** | Convert an approved direction into an implementation plan | `plan` |
| **evaluate** | Review a plan before or after implementation | `evaluate <plan>` |
| **implement** | Execute a plan in ordered or parallel waves | `implement` |
| **code-review** | Run structured review modes against code changes | `code-review <target>` |
| **test** | Execute tests, analyze failures, and identify coverage gaps | `test` |
| **diagnose** | Perform root-cause analysis on bugs and regressions | `diagnose <issue>` |
| **status** | Show workflow position, open findings, and next action | `status` |
| **resume** | Continue the active workflow from persisted state | `resume` |

## Workflow Model

```text
develop -> plan -> evaluate (pre) -> implement -> code-review -> test -> diagnose (if needed)

At any point:
- evaluate can run as a standalone critique workflow
- diagnose can run as an ad-hoc incident workflow
- status and resume can inspect or continue the current state
```

The intended model is composable rather than monolithic:

- Each skill can run on its own
- Skills can hand off context to the next skill in the chain
- State files make interrupted workflows resumable
- Review loops enforce quality gates before moving downstream

## Agents

The Codex version is expected to use a small set of specialized roles rather than a single undifferentiated agent.

| Agent | Role |
|-------|------|
| **architect** | Investigation lead, solution design, architecture review |
| **planner** | Implementation planning, sequencing, dependency mapping |
| **backend-dev** | Backend implementation with tests |
| **frontend-dev** | Frontend implementation with tests |
| **critic** | Challenges assumptions, stresses weak logic, finds hidden risks |
| **qa-reviewer** | Validates behavior, testing quality, and verification depth |
| **security-reviewer** | Reviews security-sensitive changes and operational risk |
| **tech-writer** | Produces user-facing and developer-facing documentation |

## Methodology Coverage

`forge-codex` is intended to bundle practical engineering methods instead of vague “best practices”.

**Investigation and diagnostics**

- 5 Whys
- Kepner-Tregoe IS/IS-NOT
- Fishbone / Ishikawa
- FMEA
- MECE decomposition
- Bayesian evidence updates
- hypothesis-driven debugging
- change analysis
- counterfactual reasoning
- barrier analysis

**Solution design**

- divergent and convergent option generation
- trade-off scoring
- pre-mortem analysis
- reversibility checks
- constraint analysis

**Planning**

- phased execution
- dependency mapping
- parallelization opportunities
- rollback planning
- explicit verification steps
- documentation-in-the-loop

**Review and testing**

- structured finding severity
- behavior verification
- edge-case analysis
- regression coverage review
- failure triage
- operational readiness checks

## Architecture

The repo is expected to follow a script-driven orchestration model.

- **Skill orchestrators** drive state progression for each workflow
- **Prompt templates** provide repeatable phase instructions
- **Shared templates** hold reusable review and planning patterns
- **State files** persist current step, completed step, findings, and handoffs
- **Memory files** carry context between adjacent skills
- **Reports** provide durable outputs from evaluate, review, and diagnose flows

## State and Continuity

Cross-session continuity is a core design goal.

- Each active skill should persist its own state file
- Resume logic should distinguish between a true conflict and an unrelated active session
- Standalone skills should not pause just because another non-conflicting workflow exists
- Handoff files should summarize completed work and recommend the next step
- Status tooling should surface active sessions, findings, and next actions without requiring manual inspection

## Design Principles

- **Codex-first**: optimize for Codex workflows, not a direct port of another assistant’s toolkit model
- **Actionable outputs**: produce plans, findings, commands, and reports that can be used immediately
- **Resumable by default**: interrupted work should be recoverable
- **Verification over narration**: claims should be tied to code, tests, or runtime evidence
- **Composable workflows**: users should be able to run a single skill or the full chain
- **Minimal hidden state**: the workflow should be inspectable from files in the repo

## Current Project Structure

```text
forge-codex/
├── README.md
├── agents/
├── prompts/
│   ├── develop/
│   ├── plan/
│   ├── evaluate/
│   ├── implement/
│   ├── code-review/
│   ├── test/
│   └── diagnose/
├── templates/
│   ├── review/
│   ├── planning/
│   ├── reporting/
│   └── handoff/
├── scripts/
│   ├── shared/
│   ├── develop/
│   ├── plan/
│   ├── evaluate/
│   ├── implement/
│   ├── code-review/
│   ├── test/
│   └── diagnose/
├── skills/
│   ├── develop/
│   ├── plan/
│   ├── evaluate/
│   ├── implement/
│   ├── code-review/
│   ├── test/
│   ├── diagnose/
│   ├── status/
│   └── resume/
└── templates/
```

## Initial Roadmap

### Phase 1: Skeleton

- define repository layout
- add shared orchestration primitives
- add `status` and `resume` foundations
- document the state model

### Phase 2: Core Skills

- implement `evaluate`
- implement `diagnose`
- implement `develop`
- add report generation and state cleanup rules

### Phase 3: Delivery Flow

- implement `plan`
- implement `implement`
- implement `code-review`
- implement `test`

### Phase 4: Hardening

- add regression tests for state handling
- verify conflict detection logic
- tighten workflow transitions
- document extension points for future agents and skills

## Current Status

This repository now contains the copied Codex workflow assets, reorganized into a Codex-first layout. Assistant-specific packaging has been removed, and the top-level structure has been normalized around `agents/`, `skills/`, `scripts/`, `prompts/`, and `templates/`.

## License

MIT
