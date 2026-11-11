# Milestone 14 — Gemini Quantitative Research Handoff to Codex (`Task G7`)

- **From**: Gemini Quantitative Research Mission (executed directly by user in Google Antigravity IDE; **not invoked by Codex CLI**)
- **To**: Codex CLI Lead Orchestrator, Critical Reviewer & Integration Authority
- **Runtime Provenance**: `ANTIGRAVITY_AGENT=1`, `ANTIGRAVITY_AUTH_SUCCESS_APP=antigravity-ide`, `ANTIGRAVITY_LS_VERSION=cli-2.31.0`, Conversation `f52abe73-b91c-4cc5-ad93-809e6f7ae9fe`, Trajectory `c3e644a9-aa02-4cdf-b1ef-1bb6749781a3` (underlying vendor model ID not exposed in environment metadata).
- **Date**: `2026-11-11`

---

## 1. Safety & Integrity Confirmation

| Verification Check | Status & Evidence |
| :--- | :--- |
| **Integration Tree (`C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`)** | **UNMODIFIED by Gemini** (`main` @ `6f0b64dcdf36071b136bd729f89bae5778088516` + pre-existing Codex P0/M14 local edits preserved intact; zero files written, staged, or deleted). |
| **Confirmed Competition Ledger (`data/portfolio/real_competition_ledger.json`)** | **UNTOUCHED** — SHA-256 `0A1B86CB281187A0E9AB88A4CDE6D4DE173A5DF162111266CE1988DCBF91D395` verified before and after all audits. |
| **Research Worktree (`C:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`)** | Branch `gemini/dashboard` @ `fdfae2a228c919793f1c125bbe2b61a3a74f60f9`. Pre-existing uncommitted hunks in `src/bvmt/playwright_worker.py` and `src/bvmt/portfolio_service.py` **preserved untouched**. |
| **Production Trading Posture** | **Zero production recommendation changes made.** Both `G_LIQUIDITY_FILTERED_MOMENTUM` and `sparse_research_v1` remain **`DO NOT PROMOTE / RESEARCH-ONLY`**. Live LLM calls disabled (`BVMT_ALLOW_LIVE_LLM=0`). |

---

## 2. Executive Summary of M14 Findings

BVMT Trading Intelligence missed or downgraded valid Challenge securities (`ICF`, `ATB`, `BH_BANK`, `SOTUMAG`, `TJL`, `TUNIS_RE`) AND surfaced fragile research candidates due to **measurable software/modeling defects**, not hidden Alpha:

1. **Structural Bugs & Identity Corruption (`G1`)**:
   - `holding_period.py:139-143` uses `get_challenge_symbol_set()`, silently dropping **`27 of 42` Challenge equities** (`15/42` retained) and hardcoding stale `"194 trading sessions"` narrative (`L205-212`).
   - Verified Challenge ISIN **`TN0005700018` (`POULINA`)** is split across **`POULINA_GROUP_HOLDING`** (`2026-01-02..2026-04-08`, `68` bars) and **`POULINA_GP_HOLDING`** (`2026-04-10..2026-11-10`, `128` bars), both with `valid_to=None`, severing its 60-session window.
   - `multi_horizon.py:143-145, 278-289, 300, 354` hardcodes `cutoff_dt = 2026-11-06` (leaking 6 future macro events onto `2026-10-09`), misuses Python `or` on `0.0` (confusing decimal ratios vs `%`), fabricates `Decimal("10000.000")` liquidity defaults, and hardcodes `2026-11-27` / `quantity_limit=100`.
   - `features.py` & `strategies.py` floor `vol_20` at `1e-6`, inflating zero-volatility breakouts (`FLAT_SPIKE`) to **`composite_score=125000.0`** vs `16.76` normal (`7,457x`), while raw `daily_bars.canonical.csv` has **`17,110/17,110` blank `published_at`** values.
   - `D_MOMENTUM_20S` and `F_RELATIVE_STRENGTH_20S` produce **numerically identical results** (`+17.6130%` full, `+4.6574%` ex-SOTETEL).
   - `recommendations.py` and `sparse_research.py` allocate Challenge top-K / top-8 slots and simulated cash to **3 non-challenge equities (`MONOPRIX`, `ESSOUKNA`, `CIL`)**, evicting Challenge stocks (`ICF`).
2. **`ICF` Case Study (`G2`)**:
   - `ICF`'s Nov 9–10 appreciation (`134.20 -> 143.50 TND`, `+6.93%`) was driven on-book by **`2026-09-22` status `B` row**, Nov 09 (`410` shares, `+4.99%`) & Nov 10 (`1,472` shares, `+1.85%`), **NOT** reliably predictable from missing `60s` history; across Challenge peers with identical gaps, outcomes mixed sharply (`ATB +8.24%`, `STPAP +3.17%`, `BH_BANK -2.44%`, `WIFAK -0.88%`, `NBL -2.04%`). Furthermore, `ICF` fails conservative execution depth on Nov 06 (`20s` median `1,364.09 TND`; `10%` volume cap `= 1 share / 134.20 TND`).
3. **Why Current Models Fail Promotion (`G3`)**:
   - **`Model G`**: `+19.26%` (`196`s) depends on **`+12,097.79 TND` from `SOTETEL` alone** (`+7.86%` ex-SOTETEL vs Buy-and-Hold `C=+14.65%`), leaves `~70%` cash idle (`avg_util=29.56%`), and swings wildly by start phase (`k=19`: `+0.98%..+24.10%`; `k=40`: `-1.24%..+20.81%`).
   - **`sparse_research_v1`**: Fails at `H=20` (`+12.98%` vs Baseline `+16.77%`, `43.75%` liquidity feasibility), leaks `SPARSE_LATER_FELL` (`100%` FPR, `-5.11%` mean), and fires blind awakening alerts on zero/negative returns (`BNA 0.0%` `quant=-12.9996`, `ENNAKL` `quant=-11.1404`).
4. **Fundamental & Microstructure Data Gaps (`G6`)**:
   - Zero pre-2026 BVMT OHLCV, zero CMF financial statements/earnings, zero corporate-action adjustments, raw BVMT `NB_TRANSACTION`/`CAPITAUX_BLOC`/`QUANTITE_BLOC`/`OUV` stripped on ingest, and `configs/competition.json` retains `15` unverified rule fields (`rules-check` exit `2`).

---

## 3. Ranked Top-10 Integration Backlog & Proposed Ownership

| Priority | ID / Bug Ref | Problem Summary | Target Module(s) | Proposed Owner (`AGENTS.md` Alignment) |
| :---: | :--- | :--- | :--- | :--- |
| **1 (`P0`)** | **G1-08** | Merge `POULINA` split ISIN `TN0005700018` (`POULINA_GROUP_HOLDING` -> `POULINA_GP_HOLDING`); retain raw `NB_TRANSACTION`, `QUANTITE_BLOC`, `CAPITAUX_BLOC` on import. | `src/bvmt/data.py`, `src/bvmt/calendar.py`, `src/bvmt/challenge_universe.py`, `tests/test_data_import.py` | **Codex** (`codex/data-research`) |
| **2 (`P0`)** | **G1-01, G1-02** | Fix `holding_period.py:139-143` `get_challenge_symbol_set()` dropping **27/42** Challenge stocks; remove hardcoded `"194 trading sessions"` and `datetime.min` fallback. | `src/bvmt/holding_period.py` | **Gemini** (upon Codex task assignment) |
| **3 (`P0`)** | **G1-05, G1-07a** | Enforce `CHALLENGE_42` isolation in `recommendations.py` and `sparse_research.py` so `MONOPRIX`/`ESSOUKNA`/`CIL` never enter Challenge top-K or cash allocation. | `src/bvmt/recommendations.py`, `src/bvmt/sparse_research.py` | **Gemini** (with **Codex** `api.py` review) |
| **4 (`P0`)** | **G1-03, G1-04** | Remove hardcoded `2026-11-06` cutoff (PIT leak) and `2026-11-27` in `multi_horizon.py`; fix Python `or` on `0.0`, ratio-vs-% mismatch, and synthetic `10000` TND default. | `src/bvmt/multi_horizon.py` | **Gemini** (upon Codex assignment) |
| **5 (`P1`)** | **G1-06** | Handle blank `published_at` safely (fail-closed raw / strict replay); replace binary `60s` cliff with `coverage_ratio_60s >= 0.90`; clamp `vol_20` at `0.0025` instead of `1e-6`. | `src/bvmt/features.py` | **Codex** (`codex/data-research`) |
| **6 (`P1`)** | **G1-07b,c,d** | Fix `sparse_research.py` blind awakening (`latest_day_return_pct >= +1.5%` + trade count), remove `1000`/`5000` threshold asymmetry, fix overlapping-horizon compounding. | `src/bvmt/sparse_research.py` | **Gemini** |
| **7 (`P1`)** | **G1-12 + `D=F`** | Remove duplicate `F_RELATIVE_STRENGTH_20S`, enforce phase-averaged tranche backtest reporting (`k=5,10,20`) + `ex_top_winner`, fix `1e-6` floor and fail-open `published_at`. | `src/bvmt/strategies.py` | **Codex / Gemini joint** (under G5 gate) |
| **8 (`P1`)** | **G1-09** | Fix `sparse_generalization.py` unexecutable mark-to-market, align `mean_fwd_net` and `FPR` sample denominators, evaluate baseline at `5,000` TND. | `src/bvmt/sparse_generalization.py` | **Gemini** |
| **9 (`P2`)** | **G1-10, G1-11** | Separate heterogeneous scoring scales in `research_coverage.py`; load verified PIT events with unconditional alias expansion in `macro_events.py`. | `src/bvmt/research_coverage.py`, `src/bvmt/macro_events.py` | **Gemini** (`research_coverage`) / **Codex** (`macro_events`) |
| **10 (`P2`)** | **G4 & G6** | Implement 7-layer Decision Engine v2 (`Layer A–G`, vetoes `O1–O6`) validated strictly on Dev Folds `1–7` prior to single untouched holdout (`idx 176..195`); collect blocked external inputs (`H6`). | `docs/M14_DECISION_ENGINE_V2_PROPOSAL.md`, `configs/` | **Codex Architecture & Gate** |

---

## 4. Deliverables Index & Exact Reproducer Commands

### 4.1 M14 Deliverables Created in `bvmt-gemini-dashboard`
1. [M14_SCORING_AUDIT.md](./M14_SCORING_AUDIT.md) (`Task G1` + complete `42/42` Challenge table + `<= 2026-11-06` vs `<= 2026-11-10` vs `CHALLENGE_42` strategy comparisons)
2. [M14_ICF_CASE_STUDY.md](./M14_ICF_CASE_STUDY.md) (`Task G2` forensic audit of `ICF`, `2026-09-22` status `B` anomaly, Nov 09–10 liquidity constraints, and 10 excluded Challenge peers)
3. [M14_FUNDAMENTAL_DATA_GAPS.md](./M14_FUNDAMENTAL_DATA_GAPS.md) (`Task G6` audit of missing BVMT microstructure fields, corporate actions, CMF financials, `2022–2025` history, and unverified rules)
4. [M14_DECISION_ENGINE_V2_PROPOSAL.md](./M14_DECISION_ENGINE_V2_PROPOSAL.md) (`Task G4` 7-layer separation `Layer A–G`, 8 research states, 6 deterministic overrides `O1–O6`, design only)
5. [M14_EXPERIMENT_PLAN.md](./M14_EXPERIMENT_PLAN.md) (`Task G5` pre-registered `H1–H6`, 7 purged+embargoed dev folds `2026-04-15..2026-10-06`, locked untouched holdout `2026-10-13..2026-11-10`, blocked experiments)
6. [M14_GEMINI_TO_CODEX_HANDOFF.md](./M14_GEMINI_TO_CODEX_HANDOFF.md) (`Task G7` — this document)
7. [`scripts/m14_quant_audit.py`](../scripts/m14_quant_audit.py) -> emits gitignored `artifacts/m14/m14_audit_results.json` & `artifacts/m14/challenge_42_accounting.json`
8. [`scripts/m14_g5_folds_and_peers.py`](../scripts/m14_g5_folds_and_peers.py) -> emits gitignored `artifacts/m14/m14_g5_folds_and_peers.json`
9. [`tests/test_m14_quant_audit.py`](../tests/test_m14_quant_audit.py) -> 10 deterministic characterization/reproducer tests pinning M14 defects without loosening assertions.

### 4.2 Cherry-Pick & Reproducer Commands for Codex Integration

> **Note for Codex**: `gemini/dashboard` (`fdfae2a`) predates M13/P0 modules merged onto `main` (`6f0b64d`), and contains pre-existing dirty formatting diffs in `src/bvmt/playwright_worker.py` and `src/bvmt/portfolio_service.py`. Cherry-pick ONLY the M14 `docs/`, `scripts/m14_*.py`, and `tests/test_m14_quant_audit.py` artifacts — OR resolve cleanly from a fresh research branch off verified `main`.

Run reproducibly from `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard` against read-only `bvmt-starter-kit`:
```powershell
$env:PYTHONPATH = "c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit\src"
& "c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit\.venv\Scripts\python.exe" scripts\m14_quant_audit.py --repo-root "c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit"
& "c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit\.venv\Scripts\python.exe" scripts\m14_g5_folds_and_peers.py --repo-root "c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit"
& "c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit\.venv\Scripts\python.exe" -m pytest -q tests/test_m14_quant_audit.py
```
