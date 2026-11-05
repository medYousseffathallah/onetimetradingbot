# External verification register

Checked during preparation on 2026-11-05. These references justify tooling conventions,
not strategy performance or competition eligibility. No source content is bundled wholesale.

| ID | Primary source | Used for | Verification limits |
|---|---|---|---|
| S01 | https://developers.openai.com/codex/guides/agents-md | Codex AGENTS.md project guidance | Documentation inspection; not an editor integration test |
| S02 | https://developers.openai.com/codex/skills | .agents/skills and SKILL.md conventions | Documentation inspection |
| S03 | https://code.claude.com/docs/en/skills | Claude project .claude/skills | Local-code workflow only; cloud discovery differs |
| S04 | https://cursor.com/docs/skills | Cursor .agents/skills support | Documentation inspection |
| S05 | https://cursor.com/docs/rules | .cursor/rules/*.mdc | Documentation inspection |
| S06 | https://docs.astral.sh/uv/guides/projects/ | pyproject, lockfile and reproducible sync | Actual environment checks recorded separately |
| S07 | https://www.backtrader.com/docu/filler/ | Default ignores volume; filler hook | No BVMT adapter or execution test claimed |
| S08 | https://github.com/openai/skills | Curated catalog and skill installer | Optional external code not bundled/installed |
| S09 | https://raw.githubusercontent.com/openai/skills/main/skills/.curated/gh-fix-ci/SKILL.md | CI skill purpose | Read entrypoint only |
| S10 | https://raw.githubusercontent.com/openai/skills/main/skills/.curated/security-best-practices/SKILL.md | Security skill purpose | Read entrypoint only |
| S11 | https://raw.githubusercontent.com/openai/skills/main/skills/.curated/playwright/SKILL.md | Browser skill purpose | Read entrypoint only |
| S12 | https://developers.openai.com/learn/docs-mcp | Optional read-only documentation MCP | Not configured |
| S13 | https://lightgbm.readthedocs.io/en/stable/ | Tree-based ML candidate | No fitted model or performance evidence |
| S14 | https://www.tunisbourse-challenge.com/displayp.aspx | Intended competition source | HTTP 403 during preparation; HTTP 302 to `login.aspx` on 2026-11-05 (unauthenticated) |
| S15 | https://www.tunisbourse-challenge.com/reglement.aspx | Public regulation page (14th edition) | HTTP 200 on 2026-11-05T16:04:08Z (SHA256 `767725a9e60aac3efd8da30c107c0e8a95f7a85c73501e1775001278bdd21891`); awaiting human review before marking `configs/competition.json` verified |
| S16 | https://www.tunisbourse-challenge.com/help.aspx | Competition FAQ (`Questions fréquentes`) | Participant-supplied text captured on 2026-11-05 (not independently fetched; unauthenticated HTTP GET redirects to `login.aspx`). Documents order types, 09:00–14:15 execution window, pending/partial execution, 1-week order expiry, 10% single-stock cap, 0.50% buy/sell fee, and 11:00–15:00 hourly leaderboard recalculation |

The 43% prior fourth-place return is user-provided, not independently verified. No current
market statistics, starting balance, dates, simulator fees or position caps are asserted here.
