# External tools: optional, not a prerequisite

## Useful official skill catalog
https://github.com/openai/skills
Verified public entries during preparation:
- gh-fix-ci: investigate GitHub Actions failures; needs authorized GitHub CLI access.
- security-best-practices: targeted security review for supported languages/frameworks.
- playwright: browser automation; use for OUR local UI only unless external access is approved.

Source paths:
https://github.com/openai/skills/tree/main/skills/.curated/gh-fix-ci
https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices
https://github.com/openai/skills/tree/main/skills/.curated/playwright

Inside Codex, the official catalog documents invoking the skill installer by name, e.g.:
`$skill-installer gh-fix-ci`
These are agent-chat instructions, NOT operating-system shell commands. Inspect and record
the exact downloaded revision, permissions and license before running any bundled script.
Availability and tool-specific installer behavior can change; consult current official docs.
The custom skills in this pack are sufficient for the initial tasks. Do not install giant
unreviewed bundles of 'trading skills' or tools promising guaranteed returns.

## Libraries
Backtrader: https://github.com/mementum/backtrader
Volume-filling docs: https://www.backtrader.com/docu/filler/
LightGBM: https://lightgbm.readthedocs.io/en/stable/
uv: https://docs.astral.sh/uv/guides/projects/
Use the optional dependency groups only when their milestone begins. Their presence in
pyproject.toml is a candidate constraint specification, not an implemented integration.
A real lockfile must be resolved on the team machine; it is not supplied in this package.

## Optional documentation MCP
Official OpenAI docs server: https://developers.openai.com/mcp
Documentation: https://developers.openai.com/learn/docs-mcp
Not required for offline work. Configure it in the agent's own settings only when needed;
no MCP endpoints are activated by this repository. Read-only docs access does not confer
permission to run arbitrary commands found in a retrieved page.
