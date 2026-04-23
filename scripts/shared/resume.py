#!/usr/bin/env python3
"""Resume meta-orchestrator for the forge-codex toolkit.

Detects all active skill sessions and outputs the appropriate resume command.
Handles three cases:
  0 active sessions: Check for handoff files and suggest the next skill in the pipeline
  1 active session:  Output the exact command to resume it
  2+ active sessions: Output a menu and tell Codex to ask the user directly

Usage:
    python3 resume.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Auto-detect repo root so this works from any working directory
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent  # scripts/shared/ -> scripts/ -> repo root

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.orchestrator import (
    KNOWN_SKILLS,
    PIPELINE_FLOW,
    detect_active_sessions,
    legacy_memory_dir,
    runtime_memory_dir,
)


# Map skill name to script path for generating resume commands
def _script_for(skill: str) -> str:
    """Return the Python script path for a given skill name."""
    script_map = {
        "develop": "scripts/develop/develop.py",
        "plan": "scripts/plan/plan.py",
        "implement": "scripts/implement/implement.py",
        "code-review": "scripts/code-review/code_review.py",
        "test": "scripts/test/test.py",
        "diagnose": "scripts/diagnose/orchestrate.py",
        "evaluate": "scripts/evaluate/evaluate.py",
    }
    rel = script_map.get(skill)
    if rel:
        return str(REPO_ROOT / rel)
    return f"scripts/{skill}/{skill}.py"


def _resume_step(session: dict) -> int:
    """Determine which step to resume.

    Rules:
    - If current_step is 0 or unset, start at step 1.
    - If last_completed_step matches current_step AND there's a next step,
      advance to current_step + 1.
    - Otherwise re-execute the current step (idempotent retry).
    - Cap last_completed_step at current_step to defend against inconsistent
      state (e.g. wave loops that decrement current_step but leave last high).
    """
    current = session.get("current_step", 1)
    last_completed = session.get("last_completed_step", 0)
    max_step = session.get("max_step", 6)

    # Defensive: clamp last_completed to never exceed current_step
    last_completed = min(last_completed, current)

    # Fresh/uninitialized state
    if current <= 0:
        return 1

    # Workflow complete - nothing to advance to
    if current >= max_step and last_completed >= max_step:
        return max_step  # caller can detect "complete" via separate flag

    # Step completed - advance
    if last_completed == current and current < max_step:
        return current + 1

    # Retry current step
    return max(current, 1)


def _session_is_complete(session: dict) -> bool:
    """True if the session's workflow has finished."""
    current = session.get("current_step", 1)
    last_completed = session.get("last_completed_step", 0)
    max_step = session.get("max_step", 6)
    return current >= max_step and last_completed >= max_step


def _resume_command(session: dict) -> str:
    """Build the command to resume a session."""
    skill = session["skill"]
    script = _script_for(skill)
    step = _resume_step(session)
    state_path = session["path"]
    return f"python3 {script} --step {step} --state '{state_path}'"


def _pipeline_successor_skill(completed_skills: set[str]) -> str | None:
    """Given the set of skills with handoff files, return the next skill to run."""
    # Walk the pipeline in order; return the first skill whose predecessor
    # has a handoff but which itself has no handoff.
    pipeline = ["develop", "plan", "implement", "code-review", "test", "diagnose"]
    for i, skill in enumerate(pipeline):
        if i == 0:
            continue
        predecessor = pipeline[i - 1]
        if predecessor in completed_skills and skill not in completed_skills:
            return skill
    return None


def _check_handoffs() -> list[str]:
    """List skill names that have written handoff files in runtime memory."""
    memory_dirs = [runtime_memory_dir(), legacy_memory_dir()]
    completed = []
    for skill in KNOWN_SKILLS:
        for memory_dir in memory_dirs:
            handoff = memory_dir / f"handoff-{skill}.md"
            if handoff.exists():
                completed.append(skill)
                break
    return completed


def render_no_sessions() -> str:
    """Output when no active sessions exist."""
    completed = _check_handoffs()

    lines = [
        "FORGE-CODEX RESUME",
        "=" * 60,
        "",
        "**No active sessions found.**",
        "",
    ]

    if not completed:
        lines.extend([
            "No handoff files exist either — no workflow is currently in progress.",
            "",
            "To start a new workflow, run one of these skills:",
            "  develop   - investigate and brainstorm solutions",
            "  plan      - create an implementation plan",
            "  diagnose  - deep root-cause analysis",
            "  evaluate  - critique an existing plan",
        ])
        return "\n".join(lines)

    lines.extend([
        f"**Handoff files found for:** {', '.join(completed)}",
        "",
    ])

    successor = _pipeline_successor_skill(set(completed))
    if successor:
        lines.extend([
            f"**Next skill in pipeline:** `{successor}`",
            "",
            "Ask the user directly whether to continue to that skill, run a different skill, or stay idle.",
        ])
    else:
        lines.extend([
            "**Workflow appears complete** — all pipeline skills have handoff files.",
            "",
            "Start a new workflow or view status with the `status` skill.",
        ])

    return "\n".join(lines)


def render_single_session(session: dict) -> str:
    """Output when exactly one active session exists."""
    skill = session["skill"]
    current = session.get("current_step", 1)
    last = session.get("last_completed_step", 0)
    max_step = session.get("max_step", 6)

    # If workflow is actually complete, don't produce a resume command
    if _session_is_complete(session):
        lines = [
            "FORGE-CODEX RESUME",
            "=" * 60,
            "",
            f"**Session `{skill}` is complete** ({current}/{max_step}).",
            f"**State file:** `{session['path']}`",
            "",
            "The final step has been executed. No resume command is needed.",
            "",
            "You may:",
            "  - Delete the state file to start fresh next time",
            "  - Run `resume` again to advance to the next pipeline skill",
            "  - Run `status` to see the overall workflow state",
        ]
        return "\n".join(lines)

    next_step = _resume_step(session)
    cmd = _resume_command(session)

    # Determine if resuming completed step vs retrying current
    if last == current and current < max_step:
        status = f"Step {current} completed, advancing to step {next_step}"
    else:
        status = f"Step {current} in progress, re-executing phase prompt"

    lines = [
        "FORGE-CODEX RESUME",
        "=" * 60,
        "",
        f"**Active session:** `{skill}` ({current}/{max_step})",
        f"**Status:** {status}",
        f"**State file:** `{session['path']}`",
        "",
        "━" * 60,
        "CONTINUATION — IMMEDIATE ACTION REQUIRED",
        "━" * 60,
        "Execute this command to resume:",
        "",
        f"    {cmd}",
        "",
        "DO NOT STOP. Execute the command now to continue the workflow.",
    ]
    return "\n".join(lines)


def render_multiple_sessions(sessions: list[dict]) -> str:
    """Output when 2+ active sessions exist - emit a menu."""
    options_lines = []
    for i, s in enumerate(sessions):
        skill = s["skill"]
        current = s.get("current_step", 1)
        max_step = s.get("max_step", 6)
        started = s.get("started_at", "unknown")
        comma = "," if i < len(sessions) - 1 or True else ""  # always comma, "None" follows
        options_lines.append(
            f'      {{"label": "{skill} ({current}/{max_step})", '
            f'"description": "Started {started}, resume from step {_resume_step(s)}"}}'
        )

    lines = [
        "FORGE-CODEX RESUME",
        "=" * 60,
        "",
        f"**{len(sessions)} active sessions found.**",
        "",
        "Ask the user directly which session to resume:",
    ]

    for i, opt_line in enumerate(options_lines):
        lines.append(opt_line.replace('      {"label": "', "- `").replace('", "description": "', "` — ").replace('"}', ""))
    lines.append("- `None` — do nothing and let the user decide")
    lines.extend(["", "After the user chooses, execute the corresponding resume command:"])
    lines.append("")
    for s in sessions:
        cmd = _resume_command(s)
        lines.append(f"  {s['skill']}: `{cmd}`")

    return "\n".join(lines)


def main() -> None:
    sessions = detect_active_sessions()

    if not sessions:
        print(render_no_sessions())
    elif len(sessions) == 1:
        print(render_single_session(sessions[0]))
    else:
        # Sort by most recent first
        sessions_sorted = sorted(
            sessions,
            key=lambda s: s.get("started_at") or "",
            reverse=True,
        )
        print(render_multiple_sessions(sessions_sorted))


if __name__ == "__main__":
    main()
