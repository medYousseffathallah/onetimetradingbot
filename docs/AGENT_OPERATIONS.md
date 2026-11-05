# Coding-agent operating protocol

## One task, one evidence-backed handoff
Task header: objective, scope, files owned, acceptance checks, dependencies, and forbidden
operations. State a short plan; do not generate speculative architecture for unrelated stages.
Use targeted file reads and symbol search. Keep the root instruction file small and stable.
On compaction/new sessions, reload STATE and the task rather than replaying all history.

## Roles
Lead/integrator owns schemas, configuration, shared public interfaces and final acceptance.
Implementer owns one bounded module. Reviewer reads the diff and runs checks without editing.
Use at most two concurrent implementers with distinct file ownership and worktrees. Resolve
shared interfaces before parallelizing. Do not count two agents agreeing as independent proof.

## Model usage
Use the strongest reasoning model available for architecture, financial correctness and
review; a cheaper model may do bounded extraction or documentation after schema validation.
Do not hard-code a model brand/version or assume access to a particular plan. Confirm current
provider capabilities and pricing only when an API becomes necessary. No LLM calls in v0.

## Efficient session contract
Read AGENTS + STATE + current task + one skill. Inspect existing code, propose tests, implement,
run targeted tests, then full gate. Stop after the current acceptance criteria are met.
Document verified facts and actual commands, not verbose reasoning or speculative confidence.

## Failure handling
After two identical failed attempts, change the hypothesis and inspect the error; do not
reinstall everything. For blocked source access, retain evidence and use fixtures. For unknown
financial semantics, add an explicit BLOCKED state and preserve the invariant. Do not lower
safety controls, loosen tests, or install another agent framework to hide the issue.

## Prompt templates
Use prompts/NEXT_TASK.md for implementation, REVIEW_PROMPT.md for independent review,
and templates/HANDOFF.md for state transfer. SYSTEM_PROMPT.md is optional application-level
guidance, not a mechanism that overrides your agent's built-in system/security instructions.
