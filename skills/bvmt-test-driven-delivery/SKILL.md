---
name: bvmt-test-driven-delivery
description: "Implement, debug, or review a bounded change in the BVMT codebase using reproducible tests and honest handoffs. Trigger for Python modules, CLI features, regressions, refactors, or failing quality checks. Inputs are a task and repository state; outputs are a minimal patch, executed test evidence, and updated state."
---

# BVMT Test-Driven Delivery

Work from the BVMT repository root. If the repository is unavailable, request its
path or files; do not invent project state or claim commands were executed.


1. Read the task and existing implementation; identify a reproducible failure or missing behavior.
2. Write a focused test before changing behavior. Keep assertions tied to the contract.
3. Implement the smallest typed, pure core with I/O at boundaries. Avoid unrelated refactors.
4. Run targeted tests, then scripts/check.py; inspect failures rather than weakening checks.
5. Add negative cases for malformed inputs, future dates, empty data and failure recovery.
6. Request a read-only review for financial/permission boundary changes.
7. Update docs/STATE.md with exact commands, outcomes, limitations and next action.
Never fabricate green checks or delete difficult tests to finish a task.
