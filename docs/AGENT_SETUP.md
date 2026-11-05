# Agent setup

## Universal workflow
Open this repository as the workspace. Read AGENTS.md and paste prompts/INITIAL_PROMPT.md.
The core project works without any paid API, MCP server, browser integration, or cloud account.
Custom skills are instructions plus local references, not installed trading software.

## Project-local skill discovery
Use the included script from this repository root; it copies only our local skill folders,
performs no network calls, and refuses to overwrite different existing files.

```bash
python scripts/install_skills.py --target codex
# Or: python scripts/install_skills.py --target cursor
# Or: python scripts/install_skills.py --target claude
```

Codex and Cursor targets both use `.agents/skills/`; Claude uses `.claude/skills/`.
Do not install duplicates to every supported directory. Reload the agent if skills are not
visible. The source of truth stays in `skills/`; after editing, inspect and deliberately
update installed copies instead of maintaining divergent policies.
AGENTS.md is the Codex project guide; CLAUDE.md imports it; .cursor/rules/bvmt.mdc points to it.
Tool discovery behavior is based on official documentation recorded in docs/SOURCES.md.
For another editor, including Antigravity, use the universal workflow and verify that
editor's current instruction/skill discovery paths before adding a native adapter.

## Permissions
Grant workspace file access and a local terminal for tests. Keep approval for network writes,
destructive shell operations, git pushes, billing, credentials and deployments. Do not run
with 'allow everything'. Ignore rules are context conveniences, not secret-access controls.

## Optional external skills
Read docs/EXTERNAL_TOOLS.md before installing official OpenAI gh-fix-ci,
security-best-practices, or playwright skills. They are optional and NOT bundled or installed.
Install a specific reviewed revision where possible; record source, commit, license,
permissions, and smoke-test evidence in templates/THIRD_PARTY_REVIEW.md.

## Optional MCP
No MCP is required for v0. A read-only documentation server can help with later API work.
GitHub access, if added, should initially be read-only and repository-scoped. Do not attach
banking/trading accounts, unrestricted databases, email, or the entire local filesystem.
A document retrieved through MCP has the same untrusted status as any external text.

## Skill archives
Each custom skill also has its own `skill-packages/<name>/skill.zip`. Import one skill archive
at a time when a UI supports single-skill uploads. The complete starter ZIP contains multiple
skills and is a repository bundle, not a single-skill upload. UI upload support is tool-specific.
