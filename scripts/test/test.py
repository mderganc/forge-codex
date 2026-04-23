#!/usr/bin/env python3
"""Test skill orchestrator.

Script-driven workflow that outputs formatted prompts for Codex to follow.
Each --step invocation loads state, selects the appropriate prompt template,
substitutes variables, and prints the prompt for Codex to execute.

Steps:
  1. Context Detection — read handoff files, identify test targets, initialize state
  2. Test Discovery — QA Reviewer identifies test suites and coverage targets
  3. Test Execution — run test suites, collect results, follow verification-protocol.md
  4. Failure Analysis — for each failure, Investigator performs root-cause
  5. Coverage Gap Analysis — QA Reviewer + Critic identify untested paths
  6. Report — write test report, handoff, dashboard
"""

from __future__ import annotations

import sys
from pathlib import Path

# Auto-detect repo root so this works from any working directory
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent  # scripts/test/ -> scripts/ -> repo root

# Add repo root to sys.path so imports resolve without PYTHONPATH
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.orchestrator import (
    SkillState,
    build_base_parser,
    build_next_command,
    clear_state_file,
    detect_active_sessions,
    find_state_file,
    format_active_session_warning,
    get_conflicting_sessions,
    format_step_output,
    load_state,
    next_skill_command,
    now_iso,
    read_handoff,
    read_memory_file,
    render_dashboard,
    runtime_state_path,
    save_state,
    validate_state_path,
    validate_step,
    write_handoff,
)
from scripts.evaluate.template_engine import load_template, render_template

PROMPTS_DIR = REPO_ROOT / "prompts"
SKILL_NAME = "test"
MAX_STEP = 6

PHASE_NAMES = {
    1: "Context Detection",
    2: "Test Discovery",
    3: "Test Execution",
    4: "Failure Analysis",
    5: "Coverage Gap Analysis",
    6: "Report",
}

PHASE_TODOS = {
    1: [
        {"content": "Read handoff-code-review.md and handoff-implement.md",
         "activeForm": "Reading handoffs"},
        {"content": "Initialize test state",
         "activeForm": "Initializing state"},
    ],
    2: [
        {"content": "Dispatch QA Reviewer to discover test suites",
         "activeForm": "Discovering test suites"},
        {"content": "Identify coverage targets",
         "activeForm": "Identifying coverage targets"},
    ],
    3: [
        {"content": "Run test suites via verification ladder",
         "activeForm": "Running test suites"},
        {"content": "Collect results and coverage data",
         "activeForm": "Collecting results"},
    ],
    4: [
        {"content": "Dispatch Investigator for failure root-cause analysis",
         "activeForm": "Investigating failures"},
    ],
    5: [
        {"content": "Dispatch QA + Critic for coverage gap analysis",
         "activeForm": "Analyzing coverage gaps"},
        {"content": "Run mutation audit on critical paths",
         "activeForm": "Running mutation audit"},
    ],
    6: [
        {"content": "Write test report",
         "activeForm": "Writing test report"},
        {"content": "Write handoff and render dashboard",
         "activeForm": "Writing handoff"},
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_path() -> Path:
    """Return the default state file path."""
    return runtime_state_path(SKILL_NAME)




def _build_variables(state: SkillState) -> dict[str, str]:
    """Build template variable dict from state."""
    target = state.custom.get("target", "")
    handoff_cr = state.custom.get("handoff_code_review", "")
    handoff_impl = state.custom.get("handoff_implement", "")

    # Build handoff section
    handoff_parts = []
    if handoff_cr:
        handoff_parts.append(
            "## Handoff from Code Review\n\n"
            "<handoff>\n"
            f"{handoff_cr}\n"
            "</handoff>"
        )
    if handoff_impl:
        handoff_parts.append(
            "## Handoff from Implement\n\n"
            "<handoff>\n"
            f"{handoff_impl}\n"
            "</handoff>"
        )
    if not handoff_parts:
        handoff_parts.append(
            "## No Handoff Found\n\n"
            "No handoff files found. Discovering test targets from the project."
        )
    handoff_section = "\n\n".join(handoff_parts)

    # Build test results summary
    test_results = state.custom.get("test_results", {})
    passed = test_results.get("passed", 0)
    failed = test_results.get("failed", 0)
    skipped = test_results.get("skipped", 0)
    total = test_results.get("total", 0)
    coverage = test_results.get("coverage_pct", "N/A")

    if total > 0:
        results_section = (
            f"**Total:** {total} | **Passed:** {passed} | "
            f"**Failed:** {failed} | **Skipped:** {skipped}\n"
            f"**Coverage:** {coverage}%"
        )
    else:
        results_section = "(Tests not yet executed)"

    # Build findings summary
    findings_text = ""
    if state.findings:
        for f in state.findings:
            status = f" [{f['status']}]" if f.get("status") != "open" else ""
            findings_text += (
                f"- **{f['id']}** ({f['severity']}): {f['title']}{status}\n"
                f"  {f['detail']}\n\n"
            )
    else:
        findings_text = "(No findings yet)"

    # Team assignments based on quick mode
    if state.quick_mode:
        team_section = (
            "**Quick mode active** -- abbreviated team:\n\n"
            "| Agent | Focus |\n"
            "|-------|-------|\n"
            "| QA Reviewer | Test execution and coverage analysis |\n"
            "| Investigator | Failure root-cause (if needed) |\n"
        )
    else:
        team_section = (
            "| Agent | Focus |\n"
            "|-------|-------|\n"
            "| QA Reviewer (lead) | Test discovery, execution, coverage analysis |\n"
            "| Investigator | Failure root-cause analysis |\n"
            "| Critic | Coverage gap identification, untested assumptions |\n"
            "| Doc-writer | Test report documentation |\n"
        )

    # Discovered test suites
    test_suites = state.custom.get("test_suites", [])
    if test_suites:
        suites_text = "\n".join(f"- {s}" for s in test_suites)
    else:
        suites_text = "(Not yet discovered)"

    return {
        "TARGET": target or "(auto-detected from handoff or project)",
        "HANDOFF_CONTENT": handoff_section,
        "TEST_RESULTS": results_section,
        "TEST_SUITES": suites_text,
        "FINDINGS": findings_text.strip(),
        "TEAM_ASSIGNMENTS": team_section,
        "QUICK_MODE": "yes" if state.quick_mode else "no",
        "SKILL_NAME": SKILL_NAME,
        "PASSED": str(passed),
        "FAILED": str(failed),
        "SKIPPED": str(skipped),
        "TOTAL": str(total),
        "COVERAGE": str(coverage),
    }


def _next_command(step: int, state_path: str = "") -> str:
    """Build the command for the next step."""
    extra = {}
    if state_path:
        extra["state"] = state_path
    return build_next_command(SCRIPT_DIR / "test.py", step, MAX_STEP, **extra)


# ---------------------------------------------------------------------------
# Step handlers
# ---------------------------------------------------------------------------

def handle_step_1(args) -> None:
    """Step 1: Context Detection -- read handoffs, identify targets, init state."""
    # Cross-session detection: only warn on fresh starts, not resumes
    existing_self = find_state_file(SKILL_NAME)
    if existing_self is None:
        conflicting_sessions = get_conflicting_sessions(
            SKILL_NAME,
            sessions=detect_active_sessions(),
        )
        if conflicting_sessions:
            print(format_active_session_warning(conflicting_sessions, SKILL_NAME), file=sys.stderr)

    # Read handoffs
    handoff_cr = read_handoff("code-review")
    handoff_impl = read_handoff("implement")
    project_md = read_memory_file("project.md")

    # Determine target
    target = getattr(args, "target", None) or ""

    state = SkillState(skill_name=SKILL_NAME, max_step=MAX_STEP)
    state.current_step = 1
    state.quick_mode = args.quick
    state.started_at = now_iso()
    state.custom["target"] = target
    state.custom["handoff_code_review"] = handoff_cr
    state.custom["handoff_implement"] = handoff_impl
    state.custom["project_context"] = project_md
    state.custom["test_results"] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0,
        "coverage_pct": "N/A",
    }
    state.custom["test_suites"] = []

    sp = _state_path()
    save_state(state, sp)

    # Print state path so Codex knows where it is
    print(f"STATE FILE: {sp}\n", file=sys.stderr)

    template = load_template("test/context", PROMPTS_DIR)
    variables = _build_variables(state)
    body = render_template(template, variables)

    state.last_completed_step = 1
    save_state(state, sp)

    phase_name = PHASE_NAMES[1]
    next_cmd = _next_command(1, state_path=str(sp))
    print(format_step_output(
        SKILL_NAME, 1, MAX_STEP, phase_name, body,
        next_cmd=next_cmd,
        phase_todos=PHASE_TODOS.get(1, []),
        all_phase_names=PHASE_NAMES,
        all_phase_todos=PHASE_TODOS,
    ))


def handle_step_n(step: int, state_file: str | None = None) -> None:
    """Steps 2-6: Load state, render template, output prompt."""
    sp = validate_state_path(state_file, SKILL_NAME) if state_file else None
    if sp is None:
        sp = find_state_file(SKILL_NAME)
        if sp is None:
            sp = _state_path()

    if not sp.exists():
        print("ERROR: No test session in progress. Run step 1 first.")
        print(f"Expected state file at: {_state_path()}")
        sys.exit(1)

    try:
        state = load_state(sp)
    except Exception as e:
        print(f"ERROR: Failed to load state: {e}")
        print("Delete the state file and re-run step 1.")
        sys.exit(1)

    state.current_step = step
    save_state(state, sp)

    # Map steps to template names
    template_map = {
        2: "test/discovery",
        3: "test/execution",
        4: "test/failure_analysis",
        5: "test/coverage_gaps",
        6: "test/report",
    }

    template_name = template_map.get(step)
    if not template_name:
        print(f"ERROR: Invalid step {step}")
        sys.exit(1)

    template = load_template(template_name, PROMPTS_DIR)
    variables = _build_variables(state)
    body = render_template(template, variables)

    # Step 6: mark completion and write handoff
    cross_skill_next = None
    if step == MAX_STEP:
        state.last_completed_step = step
        state.completed_at = now_iso()
        save_state(state, sp)

        test_results = state.custom.get("test_results", {})
        passed = test_results.get("passed", 0)
        failed = test_results.get("failed", 0)
        total = test_results.get("total", 0)
        coverage = test_results.get("coverage_pct", "N/A")

        # Suggest diagnose if there are failures, otherwise end of flow
        suggested_next = "diagnose" if failed > 0 else "(end of flow)"

        handoff_path = write_handoff(
            skill_name=SKILL_NAME,
            state=state,
            context={
                "Test results": f"{passed}/{total} passed, {failed} failed",
                "Coverage": f"{coverage}%",
                "Failures": str(failed),
                "Open findings": str(len(state.open_findings())),
                "Suggested action": "diagnose failures" if failed > 0 else "all tests passing",
            },
            suggested_next=suggested_next,
        )

        dashboard = render_dashboard(state)
        body += f"\n\n---\n\n{dashboard}"
        body += f"\n\nHandoff written to: {handoff_path}"
        cross_skill_next = "diagnose" if failed > 0 else None
        clear_state_file(sp)

    if step != MAX_STEP:
        state.last_completed_step = step
        save_state(state, sp)

    phase_name = PHASE_NAMES.get(step, f"Step {step}")
    next_cmd = _next_command(step, state_path=str(sp)) if step < MAX_STEP else None
    print(format_step_output(
        SKILL_NAME, step, MAX_STEP, phase_name, body,
        next_cmd=next_cmd,
        phase_todos=PHASE_TODOS.get(step, []),
        cross_skill_next=cross_skill_next,
        all_phase_names=PHASE_NAMES,
        all_phase_todos=PHASE_TODOS,
    ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_base_parser(SKILL_NAME, MAX_STEP)
    parser.add_argument(
        "--target", type=str, default=None,
        help="Test command, path, or pattern to run"
    )
    args = parser.parse_args()

    validate_step(args.step, MAX_STEP)

    if args.step == 1:
        handle_step_1(args)
    else:
        handle_step_n(args.step, state_file=args.state)


if __name__ == "__main__":
    main()
