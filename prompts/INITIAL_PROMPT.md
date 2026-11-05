You are joining the BVMT Trading Intelligence repository as its lead coding agent.

Read AGENTS.md, rules.md, goal.md, task.md, docs/STATE.md, and docs/FILE_MAP.md.
Then read skills/bvmt-project-bootstrap/SKILL.md. Inspect the existing code before editing.
This is a tested starter foundation, not an empty repository and not a finished bot.

FIRST SESSION: establish the environment and complete T01 only.
1. Inspect repository status and preserve unrelated work. Report the available Python,
   package manager, terminal, and network capabilities without requesting secrets.
2. Run `python scripts/bootstrap.py`. The delivery environment could not reach package
   registries, so uv.lock is intentionally absent. With network access, the script resolves
   a real lockfile and synchronizes development dependencies. Review and commit that file.
   If a lockfile already exists, preserve it and use locked sync; do not silently upgrade.
   If setup fails, report the blocker and run `python scripts/smoke_check.py`.
3. Run `uv run python scripts/check.py`, `uv run bvmt demo --output artifacts/demo-report.json`,
   and `uv run bvmt rules-check --config configs/competition.json`.
   The rules check should exit 2 while official rules are unknown; do not weaken it.
4. Inspect configs/competition.json and docs/COMPETITION_RULES_CHECKLIST.md. Attempt only
   permitted read-only access to official rules. Record edition, source, exact wording,
   retrieval time, and uncertainties. Do not treat previous chat claims as verified facts.
5. Update docs/STATE.md and task.md with the actual results and blockers. Propose the
   smallest T02 local-CSV ingestion improvement with acceptance tests and files to change.

Do not train an ML model, build a dashboard, connect a broker, place orders, create cloud
resources, fork an entire trading bot, or start autonomous browser actions during this task.
Do not ask for clarification when a safe engineering default is already documented.
If market access is blocked, continue with synthetic fixtures and leave the rule gate closed.

Return: environment summary; exact commands/outcomes; files changed; remaining unknowns;
and the next narrowly scoped implementation task. Never report synthetic rankings as
investment recommendations or as evidence of strategy profitability.
