# Read the smallest relevant context

| Question | File or directory |
|---|---|
| What are the mandatory rules? | AGENTS.md, rules.md |
| What are we building? | goal.md, architecture.md |
| What is next and what already works? | task.md, docs/STATE.md, docs/VALIDATION_REPORT.md |
| What should I paste into a coding agent? | prompts/INITIAL_PROMPT.md |
| How do I install the project and skills? | README.md, docs/AGENT_SETUP.md |
| Which skills are included? | skills/INDEX.md |
| How do I interpret records and timestamps? | docs/DATA_CONTRACTS.md, schemas/ |
| How must fills and tests work? | docs/BACKTEST_SPEC.md, tests/ |
| Where are unverified assumptions? | configs/competition.json, configs/research.json |
| Which external repos/skills are allowed? | docs/THIRD_PARTY_AUDIT.md, docs/EXTERNAL_TOOLS.md |
| How do I manage agent context and handoffs? | docs/AGENT_OPERATIONS.md |
| What did we verify externally? | docs/SOURCES.md |

Do not indiscriminately load all files or the dependency lockfile into agent context.
