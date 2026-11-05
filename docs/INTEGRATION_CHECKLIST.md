# Multi-Agent Integration & Merge Checklist (`main`)

Use this checklist before merging work from `gemini/dashboard` or `codex/data-research` into the `main` integration branch at `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`.

---

## 1. Pre-Merge Worktree Verification (In Agent Worktree)

Before proposing a merge from `gemini/dashboard` or `codex/data-research`:

- [ ] **1. Ownership Scope Check**: Run `git diff --name-only main...HEAD` and confirm all modified files belong to the agent's assigned ownership scope in `docs/AGENT_WORKSTREAMS.md`.
- [ ] **2. Secret & Private Data Check**: Run `git status` and `git diff --cached` to verify that no `.env` files, `DASHSCOPE_API_KEY` values, private `data/portfolio/ledger.json` files, or raw licensed datasets (`data/raw/`, `data/processed/`, `data/staging/`) are staged.
- [ ] **3. Offline Default Check**: Confirm `configs/llm_budget.example.json` still has `"network_enabled": false` and `configs/competition.json` still has `"execution_enabled": false`.
- [ ] **4. Full Quality Gate**: Run from the worktree root:
  ```powershell
  uv run python scripts/check.py
  ```
  Verify `ruff format --check`, `ruff check`, `mypy src/bvmt`, `scripts/validate_skills.py`, and `pytest -q` all exit `0`.

---

## 2. Integration Merge Procedure (On `main` in `bvmt-starter-kit`)

Run from `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`:

```powershell
# 1. Ensure main working tree is clean and up to date
cd c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit
git checkout main
git status

# 2. Merge the verified agent branch (no fast-forward so merge boundaries are auditable)
git merge --no-ff gemini/dashboard -m "Merge gemini/dashboard: <concise summary>"
# OR
git merge --no-ff codex/data-research -m "Merge codex/data-research: <concise summary>"

# 3. Run the complete integration quality gate on main
.\.venv\Scripts\python.exe scripts/check.py

# 4. Push verified main to GitHub and rebase/merge main back into active worktrees
git push origin main
```

---

## 3. Keeping Agent Worktrees Synchronized with `main`

After `main` advances:

```powershell
# Update Gemini worktree
cd c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard
git merge main

# Update Codex worktree
cd c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research
git merge main
```
