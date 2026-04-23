# Findings Aggregation

Collect findings from all reviewers and aggregate.

## Previous Findings
{{PREVIOUS_FINDINGS}}

## Instructions

1. Read all reviewer memory files (qa-reviewer.md, security-reviewer.md, critic.md, investigator.md)
2. Collect all non-PASS findings
3. Deduplicate (same issue found by multiple reviewers)
4. Create the Open Findings Tracker in project.md:

| ID | Source | Severity | Status | Description | Owner | Reviewer | Beads ID |
|----|--------|----------|--------|-------------|-------|----------|----------|

5. Create beads issues for each finding (if beads available)
6. Present aggregated findings to user by severity (FAIL first, then WARN)
