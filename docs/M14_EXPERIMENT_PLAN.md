# Milestone 14 — Pre-Registered Validation & Experiment Plan (`Task G5`)

- **Author**: Gemini Quantitative Research Mission (executed directly in Google Antigravity IDE; not invoked by Codex CLI)
- **Baseline Audited (Read-Only)**: `C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit` (`main` @ `6f0b64dcdf36071b136bd729f89bae5778088516` + Codex P0/M14 working-tree edits)
- **Evidence Artifacts**:
  - [`scripts/m14_quant_audit.py`](../scripts/m14_quant_audit.py) -> `artifacts/m14/m14_audit_results.json` & `artifacts/m14/challenge_42_accounting.json`
  - [`scripts/m14_g5_folds_and_peers.py`](../scripts/m14_g5_folds_and_peers.py) -> `artifacts/m14/m14_g5_folds_and_peers.json`
- **Current Promotion Posture**:
  - **`G_LIQUIDITY_FILTERED_MOMENTUM`**: **DO NOT PROMOTE — KEEP RESEARCH-ONLY**
  - **`sparse_research_v1`**: **DO NOT PROMOTE — KEEP RESEARCH-ONLY**

---

## 1. Empirical Premise & Statistical Power Constraints

Before running any experiment, the M14 audit (`G1–G3`) established five non-negotiable empirical constraints on `bvmt_official_2026`:

1. **Short Sample (`196` open sessions, `2026-01-02..2026-11-10`)**: After a `60`-session feature warmup (`2026-01-02..2026-03-27`), only **`136` post-warmup sessions** remain (`~6.5` calendar months). That is sufficient for falsifying structural bugs and evaluating low-dimensional (`<= 3` frozen parameters) robust rules across `7` purged dev folds + `1` untouched holdout, **NOT** for training LightGBM or multi-factor weights without multi-year history.
2. **Single-Stock Return Dominance (`SOTETEL`)**: Across the `196`-session Full BVMT backtest, `D_MOMENTUM_20S` (`+17.61%`), `E_MOMENTUM_60S` (`+14.44%`), `F_RELATIVE_STRENGTH_20S` (`+17.61%`, exact duplicate of `D`), `G_LIQUIDITY_FILTERED_MOMENTUM` (`+19.26%`), `H_DOWNSIDE_RISK_TREND_MULTIFACTOR` (`+15.58%`), and `I_REGIME_FILTERED_QUALITY_MOMENTUM` (`+15.73%`) all earn **`12,018`–`12,277 TND`** of net PnL from a single equity (`SOTETEL`). Removing `SOTETEL` collapses all six active strategies below Buy-and-Hold `C` (`+14.65%`): `D=+4.66%`, `E=+2.98%`, `F=+4.66%`, `G=+7.86%`, `H=+4.15%`, `I=+4.60%`.
3. **Cash-Drag Comparison Distortion**: Active models `D–I` maintain only `24.33%–31.46%` average capital utilization vs `B_EQUAL_WEIGHT_ELIGIBLE`'s `93.88%`. Comparing raw returns without a cash-utilization-matched benchmark (`cash_matched_b_pct`) hides cash timing vs true stock-selection alpha.
4. **Severe Rebalance-Phase Lottery**: Evaluating `196`s Full BVMT across every starting day offset reveals massive phase dispersion:
   - `D_MOMENTUM_20S`: `k=19` `[-1.12%, +23.77%]` (med `+11.83%`); `k=20` `[+0.30%, +22.81%]` (med `+11.71%`); `k=40` `[-2.89%, +20.65%]` (med `+8.36%`)
   - `E_MOMENTUM_60S`: `k=19` `[+2.68%, +19.52%]` (med `+13.23%`); `k=20` `[+2.88%, +23.64%]` (med `+11.63%`); `k=40` `[-2.66%, +21.51%]` (med `+7.27%`)
   - `G_LIQUIDITY_FILTERED_MOMENTUM`: `k=19` `[+0.98%, +24.10%]` (med `+13.52%`); `k=20` `[+2.73%, +25.26%]` (med `+11.62%`); `k=40` `[-1.24%, +20.81%]` (med `+10.86%`)
5. **Non-Challenge Displacement & Weak Awakening Edge**: On `2026-11-10`, **3 non-challenge equities** (`MONOPRIX` `#2`, `ESSOUKNA` `#3`, `CIL` `#7`) occupy the baseline top-15 AND top-8 sparse slots. Meanwhile, the `82` sparse awakening flags (`75` traded entries across `13` WF dates) yielded `+3.27%` mean (`57.33%` hit) overall, with `quant < 0` (`n=9`) actually higher (`+4.43%`, `66.67%` hit) than `quant >= 0` (`n=66`, `+3.12%`, `56.06%` hit), while the `SPARSE_LATER_FELL` cohort (`10` selected / `173` obs) posted `100%` FPR (`-5.11%` mean) and `sparse_research_v1` at `H=20` underperformed baseline (`+12.98%` vs `+16.77%`, `43.75%` liquidity feasibility).

---

## 2. Purged + Embargoed Time-Split Protocol (Zero Holdout Leakage)

All Milestone 14 development experiments (`H1–H5`) run **exclusively** on `196`-session `bvmt_official_2026` (`2026-01-02..2026-11-10`) using expanding purged + embargoed walk-forward splits with **zero parameter tuning permitted after Dev Fold 7 (`2026-10-06`)**:

- **Global Warmup Window**: Sessions `0..59` (`2026-01-02..2026-03-27`, `60` open sessions).
- **Forward Evaluation Horizon (`H`)**: `10` open exchange sessions (decision at close `t`, hypothetical entry at open `t+1`, exit/eval at close `t+10`).
- **Purge Gap**: `10` open sessions (`label_end_idx <= oos_decision_idx - 1 - embargo`). Every training observation whose `[entry, exit]` label window touches or post-dates the OOS boundary is purged.
- **Embargo Buffer**: `2` open sessions strictly between `max_train_label_bar_date` and `oos_decision_date`.
- **Fold Step**: `15` open sessions across OOS indices `71..161`.

### 2.1 Seven Strictly Pre-Holdout Development Folds

Generated deterministically by `scripts/m14_g5_folds_and_peers.py` (`artifacts/m14/m14_g5_folds_and_peers.json`):

| Fold | Train Feature Window | Max Train Decision Date | Max Train Label Bar Date | Purge / Embargo | OOS Decision Date (`idx`) | OOS Fill Open Date | OOS Eval End Date | Before Holdout |
| :---: | :--- | :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| **1** | `2026-01-02..2026-03-27` | `2026-03-27` | `2026-04-13` | `10` / `2` | `2026-04-15` (`71`) | `2026-04-16` | `2026-04-29` | YES |
| **2** | `2026-01-02..2026-04-20` | `2026-04-20` | `2026-05-05` | `10` / `2` | `2026-05-07` (`86`) | `2026-05-08` | `2026-05-21` | YES |
| **3** | `2026-01-02..2026-05-12` | `2026-05-12` | `2026-05-26` | `10` / `2` | `2026-06-01` (`101`) | `2026-06-02` | `2026-06-15` | YES |
| **4** | `2026-01-02..2026-06-04` | `2026-06-04` | `2026-06-19` | `10` / `2` | `2026-06-23` (`116`) | `2026-06-24` | `2026-07-16` | YES |
| **5** | `2026-01-02..2026-07-07` | `2026-07-07` | `2026-07-21` | `10` / `2` | `2026-07-27` (`131`) | `2026-07-28` | `2026-08-10` | YES |
| **6** | `2026-01-02..2026-07-30` | `2026-07-30` | `2026-08-14` | `10` / `2` | `2026-08-18` (`146`) | `2026-08-19` | `2026-09-15` | YES |
| **7** | `2026-01-02..2026-08-21` | `2026-08-21` | `2026-09-18` | `10` / `2` | `2026-09-22` (`161`) | `2026-09-23` | `2026-10-06` | YES |

### 2.2 Locked Final Confirmatory Holdout (`idx 176..195`)

- **Holdout Window**: **`2026-10-13` .. `2026-11-10`** (`20` open exchange sessions; indices `176..195`).
- **Two Non-Overlapping Holdout Evaluation Blocks**:
  - **Block 1**: Decision date `2026-10-12` (`>= 4` sessions after Fold 7 `eval_end = 2026-10-06`) -> Eval window **`2026-10-13..2026-10-27`**.
  - **Block 2**: Decision date `2026-10-27` -> Eval window **`2026-10-28..2026-11-10`** (includes Nov 06 `idx 193`, Nov 09 `idx 194`, Nov 10 `idx 195`).
- **Holdout Firewall Rule**:
  1. **Zero inspection, fitting, threshold search, or universe curation on `idx 176..195` during `H1–H5` development.**
  2. Candidate configuration + thresholds must be checksum-locked prior to running the single confirmatory pass on `idx 176..195`.
  3. Any candidate modification after viewing holdout results invalidates the holdout and resets promotion status to `UNVERIFIED / BLOCKED`.

---

## 3. Pre-Registered Hypotheses (`H1–H6`)

Each experiment changes **one bounded mechanism at a time** relative to the verified M14 baseline (`bvmt-starter-kit` `6f0b64d`), tracking exact trial count (`N_trials = 5` executable offline hypotheses; `H6` external-data blocked).

| Hypothesis ID | Target Defect(s) & Owned Modules (Codex-Approved Implementation) | Exact Experimental Change | Primary Evaluation Metrics | Explicit Falsification / Rejection Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **`H1`**: Universe Scope Isolation, ISIN Continuity & Holding-Period Repair | **G1-01, G1-05, G1-07, G1-08** (`data.py`, `calendar.py`, `holding_period.py`, `recommendations.py`, `sparse_research.py`) | 1. Fix `holding_period.py` Challenge filter (`get_challenge_symbol_set()` -> canonical ISIN/ID matching -> `42/42` equities).<br>2. Unify `POULINA` (`TN0005700018`) split series (`68 + 128` bars) under `POULINA_GP_HOLDING`.<br>3. Isolate `CHALLENGE_42` from non-challenge stocks (`MONOPRIX`, `ESSOUKNA`, `CIL`) in top-K, `recommendations.py`, and simulated cash budgets. | - `challenge_covered_count` (must equal `42`)<br>- Non-challenge top-K slot count (`3` -> `0`)<br>- `POULINA` April–June continuity (`60s` eligible sessions restored)<br>- Clean split of `CHALLENGE_42` vs `FULL_BVMT` tables | **FAIL** if any non-challenge equity appears in `CHALLENGE` top-K / holding-period / simulated cash ledger, if `holding_period` drops any of the 42 Challenge IDs, or if `TN0005700018` loses/duplicates any session bar. |
| **`H2`**: Soft Coverage Completeness + Bounded Volatility Floor (`0.25%`) | **G1-06, G1-12** (`features.py`, `strategies.py`, `sparse_research.py`) | 1. Replace `obs_60 == 60` cliff with `coverage_ratio_60s >= 0.90` and explicit H/B rejection audit provenance (`quote_age <= 5s`), leaving missing metrics `None`.<br>2. Replace `vol_20` floor `1e-6` with `0.0025` (`0.25%` daily vol floor) + cross-sectional winsorization `[p5, p95]`. | - Score explosion ratio on flat/single-jump stocks (`125000.0` vs `16.76` normal)<br>- Challenge coverage stability for `ICF`, `ATB`, `BH_BANK`, `SOTUMAG`, `TJL`, `TUNIS_RE`<br>- Dev Folds `1–7` OOS precision, mean net return, and max drawdown | **FAIL** if relaxing `60s` binary check degrades Dev Fold `1–7` Challenge OOS precision below baseline, widens `SPARSE_LATER_FELL` losses, or fails to eliminate the `7,457x` `FLAT_SPIKE` distortion. |
| **`H3`**: Directional Awakening Filter & `NB_TRANSACTION` Microstructure Gate | **G1-07, G1-12** (`data.py` header preservation + `sparse_research.py`) | 1. Retain raw BVMT `NB_TRANSACTION`, `QUANTITE_BLOC`, `CAPITAUX_BLOC` during canonical import.<br>2. Require `latest_day_return_pct is not None and latest_day_return_pct >= +1.5%` AND `median_trade_count_20s >= 3` before raising `awakening` alerts (blocking `BNA` `0.0%` / negative gap `ENNAKL` / 1-print bloc crosses). | - Dev Folds `1–7` OOS precision (`fwd10 > 0` after fees)<br>- `SPARSE_LATER_FELL` cohort false-positive rate (baseline `100%`)<br>- Liquidity feasibility across **all** selected triggers (not post-filtered) | **FAIL** if Dev Fold `1–7` OOS hit rate `< 55%` OR Dev Fold `1–7` mean net return fails to outperform matched Challenge equal-weight benchmark after realistic fees/slippage (never evaluate on Nov 09–10 anecdotes alone!). |
| **`H4`**: De-Duplicated Factors + Phase-Averaged Tranche Rebalancing | **G1-12** + duplicate `D/F` (`strategies.py`, `research_coverage.py`) | 1. Remove duplicate `F_RELATIVE_STRENGTH_20S` (`== D_MOMENTUM_20S`).<br>2. Evaluate active strategies across **all `k` starting offset phases** (`k in {5, 10, 20}` overlapping equal tranches), reporting phase median, IQR, min/max, `excess_vs_matched_b_pct`, and `ex_top_winner_pct`. | - Phase-averaged Dev Fold median net return & phase IQR (`k=5, 10, 20`)<br>- `ex_top_winner_excess_vs_matched_b_pct`<br>- Number of Dev Folds (`>= 5/7`) beating `cash_matched_b_pct` | **FAIL** if any candidate fails to clear positive phase-minimum return across dev folds, loses to cash-matched Challenge `B` on `ex_top_winner` basis, or exhibits phase IQR `> 6.0` percentage points. |
| **`H5`**: PIT Timestamp Enforcement, Unit Discipline & Symmetric Metrics | **G1-02, G1-03, G1-04, G1-06a, G1-09, G1-10, G1-11** (`features.py`, `multi_horizon.py`, `macro_events.py`, `holding_period.py`, `sparse_generalization.py`, `research_coverage.py`) | 1. Enforce `cutoff_dt` strictly inside `multi_horizon.py` (delete hardcoded `2026-11-06` and `2026-11-27`) and fix `published_at` replay vs fail-closed raw behavior.<br>2. Fix Python `or` falsy `0.0` bugs, align decimal vs `%` units, remove `Decimal("10000.000")` synthetic liquidity.<br>3. Enable macro aliases unconditionally; decouple `research_coverage.py` heterogeneous score formulas; fix `sparse_generalization.py` mean return denominator & `1000` vs `5000` TND asymmetry. | - Automated PIT leakage regression (`cutoff=2026-10-09` yields `0` post-cutoff events)<br>- Zero fallback defaults on `0.0` / `None` inputs<br>- Exact equivalence of `FPR` and `mean_fwd_net` evaluation sample sizes | **FAIL** if any future-dated event, silent `10000 TND` default, unit mismatch, or mismatched sample-denominator divergence persists in isolated pytest assertions. |
| **`H6` (`BLOCKED`)**: PIT Fundamental Filings, Corporate Actions & Verified Challenge Rules | Cross-module + `configs/competition.json` + `events_pit` | Integrate `2022–2025` historical BVMT OHLCV, corporate-action split/dividend adjustment ledger, CMF PIT earnings/balance-sheet tables (`mapping_emetteur.json`), and verified Tunis Bourse Challenge `15` rule fields. | - Multi-year regime generalization (`2022–2026`)<br>- Dividend/split-adjusted total return accuracy<br>- `bvmt rules-check` exit code `0` | **CURRENTLY BLOCKED** — cannot execute or claim completion until external datasets and official rule document exist locally (Section 5). |

---

## 4. Mandatory Reporting & Promotion Gate (Single Source of Truth)

Every evaluation run MUST emit separate tables for:
- `<= 2026-11-06` (`194`s) **vs** `<= 2026-11-10` (`196`s)
- `CHALLENGE_42` **vs** `FULL_BVMT`
- **Dev Folds `1–7` (`2026-04-15..2026-10-06`)** **vs** **Locked Holdout (`2026-10-13..2026-11-10`)**

A research model may leave `RESEARCH-ONLY` for `PAPER-TRADE CANDIDATE` (**and only `MANUAL TRADE PLAN` once competition rules verify to exit `0`**) **ONLY IF ALL SIX GATES PASS**:

| Gate | Requirement | Current M13 `Model G` | Current M13 `sparse_research_v1` |
| :---: | :--- | :--- | :--- |
| **G-1** | **Dev OOS Beat Rate**: Beat cash-utilization-matched Challenge benchmark on **`>= 5 / 7`** purged dev folds | Fails stability across folds (`4/7` pos ex-SOTETEL, `wf_mean=+0.44%`) | **FAILS** (`H=20` `+12.98%` vs Baseline `+16.77%`) |
| **G-2** | **Single-Stock Concentration**: `ex_top_winner` excess vs cash-matched `B` `> 0%` AND single winner PnL share `< 35%` | **FAILS** (`SOTETEL` = `~63%` of PnL; `+7.86%` ex-top vs `+14.65%` C) | **FAILS** (`SPARSE_LATER_FELL` `100%` FPR; `BNA`/`ENNAKL` negative-quant leaks) |
| **G-3** | **Phase Robustness**: All-phase median excess `> 0%`, phase IQR `<= 6.0` pp, phase min `> 0%` | **FAILS** (`k=19`: `[0.98%, 24.10%]`; `k=40`: `[-1.24%, +20.81%]`) | Not phase-invariant; sensitive to non-challenge eviction |
| **G-4** | **Drawdown & Liquidity**: Dev `max_drawdown_pct <= 10.0%` AND `>= 80%` picks executable `<= 10%` trailing median volume (`trade_count >= 3`) | `4.98%`–`6.09%` DD, ~`70.4%` idle cash (`29.56%` util) | **FAILS** (`47.12%` at `H=10`, `43.75%` at `H=20` liquidity feasibility) |
| **G-5** | **Locked Holdout Confirmatory Pass**: Single frozen pass on `idx 176..195` passes with `N_trials <= 5` disclosed | Not unlocked — held back pending `H1–H5` fixes | **FAILS** (`DO NOT PROMOTE`) |
| **G-6** | **Competition & Integrity Gate**: Zero `G1` safety violations + non-challenge isolation + (for `MANUAL TRADE PLAN` only) `rules-check` exit `0` | **FAILS** (Challenge isolation/rules pending) | **FAILS** (`MONOPRIX`/`ESSOUKNA`/`CIL` top-8 leakage) |

---

## 5. Explicitly `BLOCKED` Multi-Year, Fundamental & Rule Experiments

Per [M14_FUNDAMENTAL_DATA_GAPS.md](./M14_FUNDAMENTAL_DATA_GAPS.md), the following investigations are formally registered as **`BLOCKED`** — they MUST NOT be improvised using LLM memory, guessed corporate actions, or scraped unverified blogs:

| Blocked Experiment | Exact Missing Prerequisite | Impact of Proceeding Without It |
| :--- | :--- | :--- |
| **Multi-year walk-forward & LightGBM / ML ranking** | Pre-2026 BVMT official OHLCV + transaction counts (`2022–2025` daily bars) | High-dimensional models overfit a `196`-session bull/regime slice (`SOTETEL` concentration) |
| **Total-return (dividend & split-adjusted) backtests** | Verified `corporate_actions` ledger (ex-dividend dates, stock splits, capital increases) | Splits or large cash dividends create artificial price drops / false breakouts |
| **Valuation / earnings / solvency alpha factors (`PE`, `ROE`, `Revenue YoY`)** | CMF / BVMT PIT issuer financial statements (`balance_sheet`, `income_statement`, `dividend_history`) | Financial quality cannot be scored cleanly; only zero local coverage (`None`) can be reported |
| **Accurate Challenge score & fee / concentration enforcement** | Verified official Tunis Bourse Challenge rules PDF mapped into `configs/competition.json` (`15` unverified fields; `rules-check` exit `2`) | Simulation assumptions (`100,000 TND`, `10%` cap, `0.30%` fee, `T+2`) remain unverified approximations |
| **Microstructure depth & block-cross exclusion (`Layer B`)** | Re-ingesting raw BVMT CSV/NDJSON fields (`NB_TRANSACTION`, `CAPITAUX_BLOC`, `QUANTITE_BLOC`, `OUV`, `VWAP`, `IND_RES`) currently stripped in `bvmt_official_2026` import | Large single-print bloc trades are indistinguishable from organic continuous-book buying |
| **Dynamic Exchange Session Reconciliation (`2026-04-09`, `2026-07-06`, etc.)** | Authoritative BVMT exchange holiday / closure calendar confirmation | H/B rejections vs official session holidays conflate missing data with non-trading sessions |
