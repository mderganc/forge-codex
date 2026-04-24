"""Shared orchestrator base for all forge-codex skill scripts.

Provides common patterns for state management, step progression,
review loop enforcement, agent dispatch tracking, beads state,
session resume, and handoff file generation.

All skill orchestrators inherit from SkillOrchestrator.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT_PARTS = (".codex", "forge-codex")
LEGACY_RUNTIME_DIRNAME = ".forge"
EVALUATE_STATE_FILENAME = ".evaluate-state.json"


def _blocked_runtime_anchor(base_dir: Path) -> bool:
    """True when the canonical `.codex` anchor exists but is not a directory."""
    anchor = base_dir / RUNTIME_ROOT_PARTS[0]
    return anchor.exists() and not anchor.is_dir()


def runtime_root(search_dir: Path | None = None) -> Path:
    """Return the runtime root for forge-codex artifacts.

    Prefer the canonical `.codex/forge-codex` layout, but fall back to the
    legacy `.forge` runtime when `.codex` is blocked by a file or symlink-like
    non-directory entry in the repo root.
    """
    base_dir = search_dir or REPO_ROOT
    if _blocked_runtime_anchor(base_dir):
        return base_dir / LEGACY_RUNTIME_DIRNAME
    return base_dir.joinpath(*RUNTIME_ROOT_PARTS)


def legacy_runtime_root(search_dir: Path | None = None) -> Path:
    """Return the legacy runtime root used by the original copied workflow."""
    base_dir = search_dir or REPO_ROOT
    return base_dir / LEGACY_RUNTIME_DIRNAME


def runtime_memory_dir(search_dir: Path | None = None) -> Path:
    """Return the canonical memory directory."""
    return runtime_root(search_dir) / "memory"


def legacy_memory_dir(search_dir: Path | None = None) -> Path:
    """Return the legacy memory directory."""
    return legacy_runtime_root(search_dir) / "memory"


def runtime_state_dir(search_dir: Path | None = None) -> Path:
    """Return the canonical state directory."""
    return runtime_root(search_dir) / "state"


def legacy_state_dir(search_dir: Path | None = None) -> Path:
    """Return the legacy state directory."""
    return legacy_runtime_root(search_dir)


def runtime_adr_dir(search_dir: Path | None = None) -> Path:
    """Return the canonical ADR directory."""
    return runtime_root(search_dir) / "adr"


def runtime_backlog_path(search_dir: Path | None = None) -> Path:
    """Return the canonical backlog path."""
    return runtime_root(search_dir) / "backlog.md"


def ensure_runtime_dirs(search_dir: Path | None = None) -> None:
    """Create the canonical runtime directory structure if missing."""
    runtime_state_dir(search_dir).mkdir(parents=True, exist_ok=True)
    runtime_memory_dir(search_dir).mkdir(parents=True, exist_ok=True)
    runtime_adr_dir(search_dir).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReviewLoopState:
    """Tracks review loop progress for a single stage gate."""
    round: int = 0
    self_review: str = "pending"       # pending / pass / fail
    cross_review: str = "pending"
    critic_review: str = "pending"
    pm_validation: str = "pending"
    findings: list[dict] = field(default_factory=list)

    def is_clean(self) -> bool:
        """True if all four checks passed in the current round."""
        return all(
            getattr(self, attr) == "pass"
            for attr in ("self_review", "cross_review", "critic_review", "pm_validation")
        )

    def reset_round(self) -> None:
        """Start a new review round."""
        self.round += 1
        self.self_review = "pending"
        self.cross_review = "pending"
        self.critic_review = "pending"
        self.pm_validation = "pending"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ReviewLoopState:
        return cls(**data)


@dataclass
class AgentDispatch:
    """Tracks dispatch and completion of a single agent in a step."""
    agent: str
    step: int
    dispatched: bool = False
    completed: bool = False
    review_passed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AgentDispatch:
        return cls(**data)


@dataclass
class SkillState:
    """Base state for all skill orchestrators."""
    skill_name: str
    current_step: int = 0
    last_completed_step: int = 0
    max_step: int = 6
    quick_mode: bool = False
    autonomy_level: int = 1

    # Beads tracking
    beads_available: bool = False
    epic_id: str | None = None
    issue_ids: dict[str, str] = field(default_factory=dict)

    # Review loop state (per-step, keyed by step number)
    review_loops: dict[str, ReviewLoopState] = field(default_factory=dict)

    # Agent dispatch tracking
    dispatches: list[AgentDispatch] = field(default_factory=list)

    # Findings
    findings: list[dict] = field(default_factory=list)

    # Phase todos (per-step, keyed by step number)
    phase_todos: dict[str, list[dict]] = field(default_factory=dict)

    # Timestamps
    started_at: str | None = None
    completed_at: str | None = None

    # Custom state for specific skills
    custom: dict[str, Any] = field(default_factory=dict)

    def get_review_loop(self, step: int) -> ReviewLoopState:
        """Get or create review loop state for a step."""
        key = str(step)
        if key not in self.review_loops:
            self.review_loops[key] = ReviewLoopState()
        loop = self.review_loops[key]
        if isinstance(loop, dict):
            loop = ReviewLoopState.from_dict(loop)
            self.review_loops[key] = loop
        return loop

    def record_dispatch(self, agent: str, step: int) -> AgentDispatch:
        """Record that an agent was dispatched for a step."""
        dispatch = AgentDispatch(agent=agent, step=step, dispatched=True)
        self.dispatches.append(dispatch)
        return dispatch

    def add_finding(self, phase: str, severity: str, title: str, detail: str) -> dict:
        """Add a finding."""
        fid = f"F{len(self.findings) + 1}"
        finding = {
            "id": fid,
            "phase": phase,
            "severity": severity,
            "title": title,
            "detail": detail,
            "status": "open",
        }
        self.findings.append(finding)
        return finding

    def open_findings(self) -> list[dict]:
        return [f for f in self.findings if f.get("status") != "dismissed"]

    def to_dict(self) -> dict:
        data = {
            "skill_name": self.skill_name,
            "current_step": self.current_step,
            "last_completed_step": self.last_completed_step,
            "max_step": self.max_step,
            "quick_mode": self.quick_mode,
            "autonomy_level": self.autonomy_level,
            "beads_available": self.beads_available,
            "epic_id": self.epic_id,
            "issue_ids": self.issue_ids,
            "review_loops": {
                k: v.to_dict() if isinstance(v, ReviewLoopState) else v
                for k, v in self.review_loops.items()
            },
            "dispatches": [
                d.to_dict() if isinstance(d, AgentDispatch) else d
                for d in self.dispatches
            ],
            "findings": self.findings,
            "phase_todos": self.phase_todos,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "custom": self.custom,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> SkillState:
        state = cls(skill_name=data["skill_name"])
        state.current_step = data.get("current_step", 0)
        state.last_completed_step = data.get("last_completed_step", 0)
        state.max_step = data.get("max_step", 6)
        state.quick_mode = data.get("quick_mode", False)
        state.autonomy_level = data.get("autonomy_level", 1)
        state.beads_available = data.get("beads_available", False)
        state.epic_id = data.get("epic_id")
        state.issue_ids = data.get("issue_ids", {})
        state.review_loops = {
            k: ReviewLoopState.from_dict(v) if isinstance(v, dict) else v
            for k, v in data.get("review_loops", {}).items()
        }
        state.dispatches = [
            AgentDispatch.from_dict(d) if isinstance(d, dict) else d
            for d in data.get("dispatches", [])
        ]
        state.findings = data.get("findings", [])
        state.phase_todos = data.get("phase_todos", {})
        state.started_at = data.get("started_at")
        state.completed_at = data.get("completed_at")
        state.custom = data.get("custom", {})
        return state


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def state_filename(skill_name: str) -> str:
    """Return the state filename for a skill."""
    return f"{skill_name}.json"


def legacy_state_filename(skill_name: str) -> str:
    """Return the legacy pre-refactor state filename for a skill."""
    return f".forge-{skill_name}-state.json"


def runtime_state_path(skill_name: str, search_dir: Path | None = None) -> Path:
    """Return the canonical state path for a skill."""
    return runtime_state_dir(search_dir) / state_filename(skill_name)


def save_state(state: SkillState, path: Path) -> None:
    """Write state to JSON file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(state.to_dict(), indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.close(fd)
        Path(tmp).write_text(content)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_state(path: Path) -> SkillState:
    """Load state from JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"No state file at {path}")
    data = json.loads(path.read_text())
    if "skill_name" not in data:
        raise KeyError("State file missing required field: skill_name")
    return SkillState.from_dict(data)


def clear_state_file(path: Path) -> None:
    """Remove a state file if it exists."""
    path.unlink(missing_ok=True)


def find_state_file(skill_name: str, search_dir: Path | None = None) -> Path | None:
    """Search for a skill's state file."""
    cwd = search_dir or Path.cwd()
    candidates = [
        runtime_state_path(skill_name, cwd),
        cwd / state_filename(skill_name),
        legacy_state_dir(cwd) / legacy_state_filename(skill_name),
        cwd / legacy_state_filename(skill_name),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


# ---------------------------------------------------------------------------
# Cross-session detection & pipeline flow
# ---------------------------------------------------------------------------

# Known skills that produce state files (used by detect_active_sessions)
KNOWN_SKILLS = [
    "develop",
    "plan",
    "implement",
    "code-review",
    "test",
    "diagnose",
    "evaluate",
]

PIPELINE_SKILLS = {
    "develop",
    "plan",
    "implement",
    "code-review",
    "test",
    "diagnose",
}

# Pipeline flow: which skill comes next after each skill completes
PIPELINE_FLOW = {
    "develop": "plan",
    "plan": "implement",
    "implement": "code-review",
    "code-review": "test",
    "test": "diagnose",
    "diagnose": None,  # end of pipeline
    "evaluate": None,  # standalone skill
}


def _scan_evaluate_sessions(cwd: Path) -> list[dict]:
    """Find active evaluate sessions.

    Evaluate is special: it uses `.evaluate-state.json` and places state files
    alongside the plan being evaluated instead of the runtime state directory.
    """
    import json

    sessions: list[dict] = []

    # Candidate locations: cwd, runtime roots, and anywhere under docs/
    candidates: list[Path] = []
    for fname in (EVALUATE_STATE_FILENAME,):
        direct = cwd / fname
        if direct.exists():
            candidates.append(direct)
        for extra_dir in (runtime_root(cwd), legacy_runtime_root(cwd)):
            candidate = extra_dir / fname
            if candidate.exists():
                candidates.append(candidate)

    docs_dir = cwd / "docs"
    if docs_dir.is_dir():
        candidates.extend(docs_dir.rglob(".evaluate-state.json"))

    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)

        try:
            data = json.loads(path.read_text())
        except Exception:
            continue

        # Evaluate state has no completed_at field (it's ephemeral - deleted on
        # completion). If the file exists, it's active.
        mode = data.get("mode") or "pre"
        if mode == "review":
            max_step = 5
        elif mode == "post":
            max_step = 8
        else:
            max_step = 7
        sessions.append({
            "skill": "evaluate",
            "path": path,
            "current_step": data.get("current_step", 1),
            "last_completed_step": data.get("last_completed_step", 0),
            "max_step": max_step,
            "started_at": None,
            "completed_at": None,
            "is_complete": False,
        })
    return sessions


def detect_active_sessions(search_dir: Path | None = None) -> list[dict]:
    """Scan for all active skill state files.

    Returns a list of dicts, one per active session:
        {
            "skill": str,
            "path": Path,
            "current_step": int,
            "last_completed_step": int,
            "max_step": int,
            "started_at": str | None,
            "completed_at": str | None,
            "is_complete": bool,
        }

    Only returns sessions that are NOT completed (completed_at is None).
    """
    cwd = search_dir or REPO_ROOT
    sessions: list[dict] = []
    candidate_dirs = [
        runtime_state_dir(cwd),
        legacy_state_dir(cwd),
        cwd,
    ]

    seen_paths: set[Path] = set()
    for skill in KNOWN_SKILLS:
        # Evaluate uses a different state system - handle separately below
        if skill == "evaluate":
            continue

        fnames = (state_filename(skill), legacy_state_filename(skill))
        for dir_path in candidate_dirs:
            for fname in fnames:
                candidate = dir_path / fname
                if not candidate.exists() or candidate in seen_paths:
                    continue
                seen_paths.add(candidate)

                try:
                    state = load_state(candidate)
                except Exception:
                    continue

                if state.completed_at:
                    continue

                sessions.append({
                    "skill": state.skill_name,
                    "path": candidate,
                    "current_step": state.current_step,
                    "last_completed_step": state.last_completed_step,
                    "max_step": state.max_step,
                    "started_at": state.started_at,
                    "completed_at": state.completed_at,
                    "is_complete": False,
                })

    # Handle evaluate separately (different state format + location)
    sessions.extend(_scan_evaluate_sessions(cwd))

    return sessions


def get_conflicting_sessions(
    starting_skill: str,
    sessions: list[dict] | None = None,
    search_dir: Path | None = None,
) -> list[dict]:
    """Return only sessions that should block a fresh step-1 start."""
    active = sessions if sessions is not None else detect_active_sessions(search_dir)

    if starting_skill == "evaluate":
        return []

    if starting_skill in PIPELINE_SKILLS:
        return [
            session
            for session in active
            if session["skill"] != starting_skill and session["skill"] in PIPELINE_SKILLS
        ]

    return [
        session
        for session in active
        if session["skill"] != starting_skill
    ]


def next_skill_command(current_skill: str) -> str | None:
    """Return the next skill name in the pipeline, or None."""
    return PIPELINE_FLOW.get(current_skill)


def format_active_session_warning(sessions: list[dict], starting_skill: str) -> str:
    """Render a Codex-friendly cross-session conflict prompt.

    Used when a skill's step 1 detects other active sessions.
    """
    if not sessions:
        return ""

    lines = [
        "",
        "━" * 60,
        "ACTIVE SESSION DETECTED",
        "━" * 60,
        "",
        f"You are starting `{starting_skill}` but other active sessions exist:",
        "",
    ]
    for s in sessions:
        lines.append(
            f"  • {s['skill']} — step {s['current_step']}/{s['max_step']} "
            f"(last completed: {s['last_completed_step']}) — {s['path']}"
        )
    lines.extend([
        "",
        "**PAUSE.** Ask the user a concise question before proceeding:",
        f'- Resume `{sessions[0]["skill"]}` and continue the in-progress session',
        f'- Start `{starting_skill}` fresh and leave the existing session alone',
        "- Cancel and let the user decide manually",
        "",
        "━" * 60,
        "",
    ])
    return "\n".join(lines)


def validate_state_path(state_file: str, skill_name: str) -> Path | None:
    """Validate and resolve a --state CLI argument.

    Returns the resolved Path if valid, or None if the argument should be
    ignored (doesn't exist, outside project).
    """
    sp = Path(state_file).resolve()
    repo_root = REPO_ROOT.resolve()

    # Reject paths outside the repository directory
    try:
        sp.relative_to(repo_root)
    except ValueError:
        print(f"WARNING: --state path is outside the repository, ignoring: {state_file}",
              file=sys.stderr)
        return None

    # Reject paths that don't look like state files
    expected_names = {
        state_filename(skill_name),
        legacy_state_filename(skill_name),
        EVALUATE_STATE_FILENAME,
    }
    if sp.name not in expected_names:
        print(f"WARNING: --state path doesn't look like a state file, ignoring: {state_file}",
              file=sys.stderr)
        return None

    if not sp.exists():
        return None

    return sp


def read_handoff(name: str) -> str:
    """Read a handoff file from the runtime memory directory if it exists.

    Args:
        name: The skill name (e.g. "develop", "implement", "code-review").

    Returns:
        File content as string, or empty string if not found.
    """
    for handoff in (
        runtime_memory_dir() / f"handoff-{name}.md",
        legacy_memory_dir() / f"handoff-{name}.md",
    ):
        if handoff.exists():
            return handoff.read_text(encoding="utf-8")
    return ""


def read_memory_file(name: str) -> str:
    """Read a file from the runtime memory directory if it exists.

    Args:
        name: The filename (e.g. "project.md").

    Returns:
        File content as string, or empty string if not found.
    """
    for path in (
        runtime_memory_dir() / name,
        legacy_memory_dir() / name,
    ):
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_phase_todos(phase_todos: list[dict]) -> str:
    """Render a Codex plan-tracking block for the current phase.

    Uses json.dumps() for proper escaping of quotes, backslashes, newlines,
    and other special characters in todo content.
    """
    if not phase_todos:
        return ""

    # Build a list of safe todo dicts (only the three expected keys)
    safe_todos = [
        {
            "content": todo.get("content", ""),
            "activeForm": todo.get("activeForm", ""),
            "status": todo.get("status", "pending"),
        }
        for todo in phase_todos
    ]

    # json.dumps handles all escaping correctly
    todos_json = json.dumps(safe_todos, indent=2)

    return "\n".join([
        "## Create Phase Todos",
        "",
        "**IMMEDIATELY mirror these todos in Codex progress tracking before any other work.**",
        "Prefer `update_plan` by translating each item into a plan step with the same status.",
        "When work changes, keep the plan updated and add new steps for important sub-tasks.",
        "",
        "```json",
        todos_json,
        "```",
        "",
    ])


def build_skill_todos(
    phase_names: dict[int, str],
    phase_todos: dict[int, list[dict]],
    current_step: int,
    last_completed_step: int = 0,
) -> list[dict]:
    """Build a complete skill-level todo list covering all phases.

    Completed phases are marked 'completed', the current phase is
    'in_progress', and future phases are 'pending'.  Sub-tasks for the
    current phase are appended as 'pending' items.
    """
    todos: list[dict] = []
    for step_num in sorted(phase_names.keys()):
        name = phase_names[step_num]
        if step_num <= last_completed_step:
            status = "completed"
        elif step_num == current_step:
            status = "in_progress"
        else:
            status = "pending"

        todos.append({
            "content": name,
            "activeForm": f"Running {name}",
            "status": status,
        })

        # Add sub-tasks for the current phase only
        if step_num == current_step:
            for sub_todo in phase_todos.get(step_num, []):
                todos.append({
                    "content": f"  {sub_todo['content']}",
                    "activeForm": sub_todo["activeForm"],
                    "status": "pending",
                })

    return todos


def format_continuation_block(next_cmd: str) -> str:
    """Render the strong continuation directive replacing the old NEXT STEP block."""
    bar = "━" * 60
    return (
        f"\n\n{bar}\n"
        f"CONTINUATION — IMMEDIATE ACTION REQUIRED\n"
        f"{bar}\n"
        f"This phase is complete. To continue the workflow:\n"
        f"\n"
        f"  1. Mark the current phase todo as `completed` in your Codex plan tracking.\n"
        f"  2. Execute the next command:\n"
        f"\n"
        f"     {next_cmd}\n"
        f"\n"
        f"DO NOT STOP. DO NOT SUMMARIZE. Execute the next command now\n"
        f"to advance to the next phase. If the user has asked you to\n"
        f"pause, confirm with them and report the state file location."
    )


def format_workflow_transition(cross_skill_next: str) -> str:
    """Render a Codex-friendly cross-skill transition prompt.

    `cross_skill_next` is a skill name like "plan". If the user chooses to
    proceed, invoke that skill so its orchestrator can start at step 1.
    """
    bar = "═" * 60
    return (
        f"\n\n{bar}\n"
        f"WORKFLOW TRANSITION — SKILL BOUNDARY\n"
        f"{bar}\n"
        f"This skill is complete. The next skill in the pipeline is:\n"
        f"\n"
        f"    {cross_skill_next}\n"
        f"\n"
        f"**PAUSE HERE.** Do not automatically advance to the next skill.\n"
        f"Ask the user directly whether to proceed to `{cross_skill_next}`, pause here, or run a different skill.\n"
        f"\n"
        f'If the user chooses to proceed, invoke the `{cross_skill_next}` skill so its orchestrator starts at step 1.\n'
    )


def format_step_output(
    skill_name: str,
    step: int,
    max_step: int,
    phase_name: str,
    body: str,
    next_cmd: str | None = None,
    phase_todos: list[dict] | None = None,
    cross_skill_next: str | None = None,
    all_phase_names: dict[int, str] | None = None,
    all_phase_todos: dict[int, list[dict]] | None = None,
) -> str:
    """Format step output with title, todos, body, and continuation directive.

    Args:
        skill_name: Name of the skill (e.g. "develop").
        step: Current step number.
        max_step: Maximum step number for this skill.
        phase_name: Human-readable phase name.
        body: The rendered prompt body.
        next_cmd: Command to run for the next step (None if final step).
        phase_todos: Optional list of todo dicts for current phase only (legacy).
        cross_skill_next: Optional next-skill command when at skill boundary.
        all_phase_names: Full dict of {step: phase_name} for the skill.
            When provided, a skill-level todo list is generated showing
            all phases with their completion status.
        all_phase_todos: Full dict of {step: [todo_dicts]} for the skill.
            Used alongside all_phase_names for sub-task detail.
    """
    title = f"{skill_name.upper()} — {phase_name} (Step {step} of {max_step})"
    header = f"{title}\n{'=' * len(title)}\n\n"

    # Todos come first so Codex creates them before doing phase work.
    # Prefer full skill-level todos when available; fall back to per-phase.
    if all_phase_names:
        # If caller provided a per-step phase_todos override (e.g. implement's
        # wave-scoped todos), use it for the current step's sub-tasks instead
        # of the generic all_phase_todos entry.
        effective_phase_todos = dict(all_phase_todos or {})
        if phase_todos is not None:
            effective_phase_todos[step] = phase_todos
        skill_todos = build_skill_todos(
            all_phase_names,
            effective_phase_todos,
            current_step=step,
            last_completed_step=step - 1,
        )
        todos_section = format_phase_todos(skill_todos)
    elif phase_todos:
        todos_section = format_phase_todos(phase_todos)
    else:
        todos_section = ""
    output = header + todos_section + body

    if next_cmd:
        output += format_continuation_block(next_cmd)
    elif cross_skill_next:
        output += "\n\nWORKFLOW COMPLETE — this skill has finished."
        output += format_workflow_transition(cross_skill_next)
    else:
        output += "\n\nWORKFLOW COMPLETE — return results to the user."

    return output


def build_next_command(script_path: Path, step: int, max_step: int, **extra_args: str) -> str:
    """Build the command string for the next step."""
    if step >= max_step:
        return ""
    cmd = f"python3 {shlex.quote(str(script_path))} --step {step + 1}"
    for key, val in extra_args.items():
        cmd += f" --{key} {shlex.quote(val)}"
    return cmd


# ---------------------------------------------------------------------------
# Handoff file generation
# ---------------------------------------------------------------------------

def write_handoff(
    skill_name: str,
    state: SkillState,
    context: dict[str, str],
    suggested_next: str,
    memory_dir: Path | None = None,
) -> Path:
    """Write a handoff file to the runtime memory directory.

    Args:
        skill_name: Name of the completing skill.
        state: Current skill state.
        context: Key-value pairs of context for the next skill.
        suggested_next: Suggested next command string.
        memory_dir: Override memory directory path.

    Returns:
        Path to the written handoff file.
    """
    if memory_dir is None:
        memory_dir = runtime_memory_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)

    handoff_path = memory_dir / f"handoff-{skill_name}.md"
    now = datetime.now(timezone.utc).isoformat()

    lines = [
        f"# Handoff: {skill_name} → {suggested_next.split()[0] if suggested_next else 'next'}",
        "",
        "## Completed",
        f"- **Skill:** {skill_name}",
        f"- **Timestamp:** {now}",
        f"- **Status:** complete",
        f"- **Quick mode:** {state.quick_mode}",
        "",
        "## Context for Next Skill",
    ]

    for key, val in context.items():
        lines.append(f"- **{key}:** {val}")

    lines.extend([
        "",
        "## Beads State",
        f"- **Epic:** {state.epic_id or 'N/A'}",
        f"- **Open issues:** {', '.join(k for k, v in state.issue_ids.items()) or 'none'}",
        "",
        "## Suggested Next",
        f"`{suggested_next}`" if suggested_next else "(end of flow)",
        "",
    ])

    handoff_path.write_text("\n".join(lines), encoding="utf-8")
    return handoff_path


# ---------------------------------------------------------------------------
# Dashboard rendering
# ---------------------------------------------------------------------------

def render_dashboard(state: SkillState) -> str:
    """Render a skill completion dashboard."""
    open_count = len(state.open_findings())
    resolved_count = len(state.findings) - open_count
    agents = set()
    for d in state.dispatches:
        name = d.agent if isinstance(d, AgentDispatch) else d.get("agent", "unknown")
        agents.add(name)

    lines = [
        "## forge-codex — Skill Summary",
        f"**Skill:** {state.skill_name}",
        f"**Status:** {'COMPLETE' if state.completed_at else 'IN_PROGRESS'}",
        f"**Started:** {state.started_at or 'N/A'}",
        f"**Completed:** {state.completed_at or 'N/A'}",
        f"**Agents dispatched:** {', '.join(sorted(agents)) or 'none'}",
        f"**Findings:** {open_count} open, {resolved_count} resolved",
        f"**Beads:** {state.epic_id or 'N/A'}",
        f"**Quick mode:** {state.quick_mode}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def build_base_parser(skill_name: str, max_step: int) -> argparse.ArgumentParser:
    """Build the base argument parser for a skill orchestrator."""
    parser = argparse.ArgumentParser(
        description=f"forge-codex {skill_name} skill orchestrator"
    )
    parser.add_argument(
        "--step", type=int, required=True,
        help=f"Phase number (1-{max_step})"
    )
    parser.add_argument(
        "--state", type=str, default=None,
        help="Path to state file (auto-detected if omitted)"
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: minimal review loops, lead agents only"
    )
    return parser


def validate_step(step: int, max_step: int) -> None:
    """Validate step number is in range."""
    if step < 1 or step > max_step:
        sys.exit(f"ERROR: --step must be 1-{max_step}")


def now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()
