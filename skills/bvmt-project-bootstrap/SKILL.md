---
name: bvmt-project-bootstrap
description: "Bootstrap or resume the BVMT virtual-competition research repository. Use when setting up the coding agent, running the first task, reading project state, choosing the next milestone, or preparing a handoff. Inputs are a repository path and task; outputs are verified environment evidence, a bounded plan, and updated project state. No external connector is required."
---

# BVMT Project Bootstrap

Work from the BVMT repository root. If the repository is unavailable, request its
path or files; do not invent project state or claim commands were executed.


1. Locate the project root; read AGENTS.md, rules.md, goal.md, task.md, and docs/STATE.md.
2. Inspect current files and working-tree changes; do not rebuild existing modules.
3. Select one unblocked task. Define file ownership, acceptance tests, and excluded work.
4. Run the documented environment checks and offline demo. Record commands and exit codes.
5. Check competition/source status. Leave unverified facts null and permission gates closed.
6. Implement only the selected scope, or report the concrete environment blocker.
7. Update state using templates/HANDOFF.md and report implemented/tested/planned separately.
Read references/acceptance.md for the first-session checklist. Do not add autonomous trading.
