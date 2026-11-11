# Milestone 14 — Full Scoring System Audit (`Task G1`)

- **Author**: Gemini Quantitative Research Mission (executed directly in Google Antigravity IDE; not invoked by Codex CLI)
- **Runtime Provenance**: `ANTIGRAVITY_AGENT=1`, `ANTIGRAVITY_AUTH_SUCCESS_APP=antigravity-ide`, `ANTIGRAVITY_LS_VERSION=cli-2.31.0`, Conversation ID `f52abe73-b91c-4cc5-ad93-809e6f7ae9fe`, Trajectory ID `c3e644a9-aa02-4cdf-b1ef-1bb6749781a3` (underlying vendor model ID not exposed in environment metadata).
- **Integration Baseline Audited (Read-Only)**: `C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`, branch `main` @ `6f0b64dcdf36071b136bd729f89bae5778088516` (`[ahead 13]` vs `origin/main`) + pre-existing Codex P0/M14 working-tree edits.
- **Research Worktree (Deliverables & Reproducers)**: `C:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`, branch `gemini/dashboard` @ `fdfae2a228c919793f1c125bbe2b61a3a74f60f9` (preserving pre-existing uncommitted diffs in `src/bvmt/playwright_worker.py` and `src/bvmt/portfolio_service.py`).
- **Real Portfolio Ledger Integrity**: `data/portfolio/real_competition_ledger.json` SHA-256 = `0A1B86CB281187A0E9AB88A4CDE6D4DE173A5DF162111266CE1988DCBF91D395` (verified unchanged before and after every audit run).

---

## 1. Audited Baseline File Manifest (SHA-256)

Every finding below was audited directly against the following file states in `bvmt-starter-kit` (`6f0b64d` + local working-tree state):

| File | Tree vs `6f0b64d` | SHA-256 |
| :--- | :--- | :--- |
| `src/bvmt/features.py` | SAME | `66654E5CCDDB5F57124F9EA16FF3FF890C3EEDE86E105E9F0D709F24240ED3FC` |
| `src/bvmt/recommendations.py` | SAME | `70591DA4019697904081076465C757E688E7096FEFAF2210CC750497727803CB` |
| `src/bvmt/research_coverage.py` | SAME | `84196FBCA0915E6056D4725AD48FAB8ACD6D36756951C040111D261E14927690` |
| `src/bvmt/sparse_research.py` | DIFF | `2FB3B7F867610F6569394F2766DCBAF62AC481C0FC180291D2B4CEE6A41EA658` |
| `src/bvmt/sparse_generalization.py` | DIFF | `B11C00F47BAF72132E2164A96BCF460EB802C4230AEC589662647A65AFE1356F` |
| `src/bvmt/multi_horizon.py` | DIFF | `BE14FA7149373373EF4903585612D054AF68E5AB8A2A77761756791AD8C8D4D5` |
| `src/bvmt/strategies.py` | SAME | `73EE1EEDC41D275FCF6466EA70733E00617F930D42D484BFCCC99AB6504B8DD1` |
| `src/bvmt/holding_period.py` | DIFF | `9CB44CC5804AF4821575243B11C24C8FC155658BDC7416BFD3AD598D0A7DFF5F` |
| `src/bvmt/macro_events.py` | SAME | `9B03A39537C5B310981306F56CA9493D59FEBDC3AAC7BF8A605E8162F9D1692E8` |
| `src/bvmt/execution.py` | SAME | `F7F5527CFC9FDA6DF755D8C081306F10E7FCD5115952880C8BA22D5BB9DC8063` |
| `src/bvmt/position_sizing.py` | DIFF | `EB6133B10DE28B7E443B770A0F60E91583E0D93875FC4C532520ABFADC3E9ABC` |
| `src/bvmt/challenge_universe.py` | DIFF | `BF6902BC86BC9DD3996642428F1F903C8D6087B51C78BB9E830FF01A374E349A` |
| `src/bvmt/trade_planner.py` | DIFF | `4A2700ED81105B585FAC75015D502F39A6D254B3D898F028FC35FCAEA96B9BE9` |
| `src/bvmt/data.py` | DIFF | `CEF1631801B6466E9371BFBAB4449B9CFD302D52B1799270BE55C53BCC6C4D93` |
| `src/bvmt/calendar.py` | DIFF | `3774FDC1B26094E45F25A8BDF463628A703757B47318353A0512746C0B3D7C62` |
| `src/bvmt/api.py` | DIFF | `2DC25727C429870D6A5853C6DCA159F1338EA6B21892FDB4085DED487D757747` |
| `src/bvmt/gateway.py` | DIFF | `5E19E107CDBC32C6AD9813E619C79B700B1C3361C9A3563B1C5B01118D8BA245` |
| `src/bvmt/dashboard.py` | DIFF | `F218E26ADE82DB5CD775D687540DBEA204D89BD9967425683616296D69B9C197` |
| `src/bvmt/llm.py` | SAME | `3CFC42FFCB9A553CA6B36EEE027583BDDE29962BCA6A8F759C742024F505618F` |
| `configs/competition.json` | DIFF | `0B71F5AAE60ED4CACE88288BC63884EF85F8C12BAE739AAFCB4328921393D451` |
| `configs/research.json` | DIFF | `46CAD32000F6C0F6F771223BDDA7862C9C0FEF4831185AA21EB8B3106F101091` |
| `configs/sparse_research_v1.json` | DIFF | `F0BF9E10577CD04A540C35C2494DCA9A060A25FA39A2226FAF6AAFA04663DE22` |
| `data/portfolio/real_competition_ledger.json` | DIFF | `0A1B86CB281187A0E9AB88A4CDE6D4DE173A5DF162111266CE1988DCBF91D395` |

---

## 2. Executive Defect Matrix (`G1` Findings)

| ID | Severity | Module & Line Ref | Defect Class | Reproducible Evidence & Quantitative Impact |
| :--- | :--- | :--- | :--- | :--- |
| **G1-01** | **CRITICAL** | `src/bvmt/holding_period.py:139-143` | Challenge Universe Filter Bug (`symbol` vs `canonical_id`) | Compares `m.instrument_id in get_challenge_symbol_set()`. Only **15 of 42** Challenge stocks match (`missed_count = 27`, dropping `AB`, `AMV`, `BH`, `CC`, `CITY`, `DH`, `ECYCL`, `LNDOR`, `MGR`, `NAKL`, `NBL`, `OTH`, `PGH`, `SAM`, `SMART`, `SOTET`, `SOTUV`, `SPDIT`, `STPAP`, `STPIL`, `TJARI`, `TJL`, `TLNET`, `TLS`, `TRE`, `UMED`, `WIFAK`). Distorts Challenge holding-period returns (`20s: +5.86%`, `BNA = 63.8%` of PnL vs `19s: +11.25%`). |
| **G1-02** | **CRITICAL** | `src/bvmt/holding_period.py:120-127, 205-212` | Hardcoded Stale Narrative & Midnight Close Fallback | Falls back to `datetime.min` when `closes_at is None`; hardcodes `"194 trading sessions"`, `"42 equities"`, `"+18.8% vs +8.5%"` on any dataset including the **196-session** Nov 10 data (`test_g1_holding_period_symbol_set_drops_27_of_42_and_hardcodes_194` passes). |
| **G1-03** | **CRITICAL** | `src/bvmt/multi_horizon.py:143-145` | Hardcoded Macro Cutoff (Lookahead + Drop-Off) | Hardcodes `cutoff_dt = datetime(2026, 11, 6, 23, 59, 59, tzinfo=UTC)`. On `2026-10-09`, leaks **6 future macro events** published through Nov 05 (`BCT_RATE_STABLE_800`, `INS_CPI_INFLATION_OCT2026`, `DH_Q3_2026_REVENUE_EXPANSION`, `STA_AUTOMOTIVE_VOLUME_RESILIENCE`, `LOI_FINANCES_2026_ENERGY_TRANSITION`, `SOTETEL_TELECOM_INFRASTRUCTURE_CONTRACTS`). On `2026-11-10`, drops events after Nov 06. |
| **G1-04** | **CRITICAL** | `src/bvmt/multi_horizon.py:278-289, 300, 354` | Falsy `0.0`, Ratio-vs-% Mismatch, Synthetic `10000` Liquidity, Hardcoded Fields | Uses Python `or` (`0.0` falls back to `momentum_20s` and treats decimal ratio `0.15` vs percentage threshold `1.50` inconsistently); missing/None `median_turnover_tnd` silently defaults to `Decimal("10000.000")`; `rank <= 5` triggers swing candidates even on negative momentum; hardcodes `quantity_limit=100` and review date `2026-11-27`. |
| **G1-05** | **CRITICAL** | `src/bvmt/recommendations.py:144-176, 237-250, 556-632` | Missing Challenge Gate & Budget Consumption | Without API `_guard_plan`, emits `"BUY CANDIDATE"` + simulated cash allocation for non-challenge stocks (`MONOPRIX` rank 2, `302` shares; `ESSOUKNA` rank 3, `119` shares on Nov 10), consuming scarce simulated cash ahead of Challenge securities. Also nulls excluded metrics and falls back to `average_cost_tnd` (`L237-250`). |
| **G1-06** | **HIGH** | `src/bvmt/features.py:165-172, 248-257, 328-339, 359, 369` | Blank `published_at` Crash, Binary `60s` Cliff & `1e-6` Vol Blowup | (a) Raw `daily_bars.canonical.csv` has **`17,110 / 17,110`** blank `published_at` -> raw `rank_session_baseline` throws `ValueError: No completed open exchange sessions on or before cutoff`; (b) single missing open session in 60s (`L248-257`) disqualifies Challenge stocks for ~3 months (`ATB`, `BH_BANK`, `ICF`, `SOTUMAG`, `TJL`, `TUNIS_RE`); (c) `vol_20` floored at `1e-6` (`L328-339, L369`) amplifies `FLAT_SPIKE` (`mom20=0, mom60=0.25`) to **`composite_score=125000.0`** vs normal **`16.762861`** (`7,457x` ratio); (d) `recs[0].listed_from/to` ignores split IDs (`L185-186`); survivor-only equal-weight benchmark (`L359`). |
| **G1-07** | **HIGH** | `src/bvmt/sparse_research.py:1044, 1097-1106, 1651-1677, 1772-1786, 2283, 2748` | Non-Challenge Top-K Slot Eviction & Blind Awakening Trigger | (a) Top-8 cap (`L1772-1774, L2283`) includes **3 non-challenge stocks** (`MONOPRIX=24.0979`, `ESSOUKNA=19.7327`, `CIL=15.2646` on Nov 10), evicting Challenge stock `ICF` (`357.83x` awakening, `quant_score=10.0201`); (b) awakening triggers even with `latest_day_return_pct == 0.0` (`BNA`, `quant_score=-12.9996`) or `latest_day_return_pct is None` after >15s gap regardless of drop direction (`ENNAKL_AUTOMOBILES`, `quant_score=-11.1404`), and bypasses trend filter using marginal `1000` vs `5000` TND threshold (`L1777-1786`); (c) mixes calendar/traded proxies and hardcoded `+6 / +2.5 / -3` constants (`L1651-1677`); (d) daily compounding across overlapping horizons in promotion gate (`L2748`). |
| **G1-08** | **HIGH** | `src/bvmt/data.py` & `src/bvmt/calendar.py` & `src/bvmt/challenge_universe.py` | Split `POULINA` Canonical ID (`TN0005700018`) | Verified Challenge ISIN `TN0005700018` is split between `POULINA_GROUP_HOLDING` (`2026-01-02..2026-04-08`, `68` bars / `67` traded, close `24.120`) and `POULINA_GP_HOLDING` (`2026-04-10..2026-11-10`, `128` bars / `128` traded, close `26.490`) with zero date overlap and BOTH having `valid_to=None` in `instrument_master.csv`. Severs 60-session history cleanly across April–June and creates duplicate portfolio/price identities. Also `NB_TRANSACTION` is stripped during ingestion into `daily_bars.canonical.csv`. |
| **G1-09** | **HIGH** | `src/bvmt/sparse_generalization.py:273-278, 295-311, 503` | Selection Bias in Mean Returns, Stale Mark-to-Mark, Asymmetric Baseline | (a) Defines `TRUE_OPPORTUNITY` using unexecutable mark-to-market (`L273-278`) from stale `last_verified_close`; (b) omits unfillable picks from `mean_forward_net_return_pct` while counting them in `false_positive_rate` (`L295-311`); (c) evaluates baseline at `1000` TND liquidity threshold (`L503`) rather than production `5000` TND default. |
| **G1-10** | **MEDIUM** | `src/bvmt/research_coverage.py:483-506` | Incomparable Scale Concatenation & Ad-Hoc Weights | Writes `composite * liq` (`[-13.03, +8.82]` for `ELIGIBLE`) and `obs_ret_pct * liq * 0.1` (`[-0.28, +0.27]` for `EXCLUDED`) into the same `continuous_research_score` field; ad-hoc `(0.4, 0.3, 0.3)` weights; computes `hypothetical_shares` ignoring challenge eligibility and stale quote age. |
| **G1-11** | **MEDIUM** | `src/bvmt/macro_events.py:59-169, 220` | Static In-Code Catalog & Alias Bypass | Hardcodes 6 Python events instead of a PIT file store; `get_verified_macro_intelligence(..., instrument_id="CARTHAGE_CEMENT", include_aliases=False)` returns **0 events** vs **1** with `include_aliases=True` because the event targets `"CC"`. |
| **G1-12** | **MEDIUM** | `src/bvmt/strategies.py:257-263, 303, 397, 494, 567` | Fail-Open PIT, Full-Day Volume Lookahead, Cadence Instability | Fail-open when `published_at is None`; `1e-6` vol floor (`L303`); Model C initial-day top-10 turnover survivor basket (`L494`); purchase-only 10% weight cap permitting drift >14% (`L567`); full-day volume participation lookahead (`L397`); extreme rebalance-phase sensitivity across 196 sessions (`D_MOMENTUM_20S` at `k=19`: `-1.12%..+23.77%`; `k=20`: `+0.30%..+22.81%`; `G` at `k=40`: `-1.24%..+20.81%`), with `+12,097.785 TND` out of `+19.26%` headline return (`+7.86%` ex-top-winner) driven by a single stock (`SOTETEL`). |

---

## 3. Model-by-Model Evaluation Separately Across Cutoffs & Universes

### 3.1 Baseline Strategy Suite (Models A–I)

| Model | `<= 2026-11-06` (`194`s Full BVMT) Net / Liq / MaxDD | `<= 2026-11-10` (`196`s Full BVMT) Net / Liq / MaxDD | `<= 2026-11-10` (`196`s Challenge-42 Only) Net / Liq / MaxDD | Top Winner PnL (196s Full / Ex-Top Return) |
| :--- | :--- | :--- | :--- | :--- |
| `A_CASH_ONLY` | `0.00%` / `0.00%` / `0.00%` | `0.00%` / `0.00%` / `0.00%` | `0.00%` / `0.00%` / `0.00%` | `None` |
| `B_EQUAL_WEIGHT_ELIGIBLE` | `14.05%` / `13.50%` / `17.20%` | `14.75%` / `14.19%` / `17.20%` | `14.75%` / `14.19%` / `17.20%` | `AMEN_BANK` (`5,010.85` / `11.64%`) |
| `C_BUY_AND_HOLD_BENCHMARK` | `14.03%` / `13.61%` / `12.61%` | `14.65%` / `14.23%` / `12.61%` | `14.65%` / `14.23%` / `12.61%` | `AMEN_BANK` (`5,301.40` / `11.05%`) |
| `D_MOMENTUM_20S` | `17.05%` / `16.90%` / `5.35%` | `17.61%` / `17.51%` / `5.35%` | `17.36%` / `17.26%` / `6.52%` | `SOTETEL` (`12,018.12` / `4.66%`) |
| `E_MOMENTUM_60S` | `14.36%` / `14.26%` / `8.12%` | `14.44%` / `14.42%` / `8.12%` | `13.70%` / `13.65%` / `8.31%` | `SOTETEL` (`12,277.11` / `2.98%`) |
| `F_RELATIVE_STRENGTH_20S` | `17.05%` / `16.90%` / `5.35%` | `17.61%` / `17.51%` / `5.35%` | `17.36%` / `17.26%` / `6.52%` | Identical to `D` |
| `G_LIQUIDITY_FILTERED_MOMENTUM` | `18.81%` / `18.73%` / `4.98%` | `19.26%` / `19.17%` / `4.98%` | `19.42%` / `19.39%` / `6.09%` | `SOTETEL` (`12,097.79` / `7.86%`) |
| `H_DOWNSIDE_RISK_TREND_MULTIFACTOR` | `15.14%` / `15.06%` / `6.10%` | `15.58%` / `15.50%` / `6.10%` | `14.93%` / `14.90%` / `6.35%` | `SOTETEL` (`12,093.22` / `4.15%`) |
| `I_REGIME_FILTERED_QUALITY_MOMENTUM` | `15.74%` / `15.71%` / `5.47%` | `15.73%` / `15.71%` / `5.47%` | `15.83%` / `15.81%` / `5.46%` | `SOTETEL` (`12,261.27` / `4.60%`) |

* **Cash-Utilization Caveat (`avg_utilization_pct`)**: Active strategies `D–I` sit ~**70–75% in cash** (`avg_util_pct`: `24.33%–31.46%` vs `B`'s `93.88%`).
* **Rebalance-Phase Dispersion (`196`s Full BVMT across every start phase)**:
  * `D_MOMENTUM_20S`: `k=5` `[5.76%, 13.73%]` (med `11.22%`); `k=10` `[1.69%, 19.74%]` (med `9.97%`); `k=19` `[-1.12%, +23.77%]` (med `11.83%`); `k=20` `[+0.30%, +22.81%]` (med `11.71%`); `k=40` `[-2.89%, +20.65%]` (med `8.36%`).
  * `E_MOMENTUM_60S`: `k=19` `[2.68%, 19.52%]` (med `13.23%`); `k=20` `[2.88%, 23.64%]` (med `11.63%`); `k=40` `[-2.66%, +21.51%]` (med `7.27%`).
  * `G_LIQUIDITY_FILTERED_MOMENTUM`: `k=19` `[0.98%, 24.10%]` (med `13.52%`); `k=20` `[2.73%, 25.26%]` (med `11.62%`); `k=40` `[-1.24%, +20.81%]` (med `10.86%`).
* **Verdict on Model G**: Unpromoted & fragile (~`63%` of net profit from one single-stock trajectory, ~`70%` cash idle, wide phase variance). Keep **research-only**.

### 3.2 `sparse_research_v1` Walk-Forward Promotion Gate (vs Production Baseline)

* `196`s, `H=10` (`13` non-overlapping folds `2026-03-30..2026-10-20`):
  * **Baseline**: `cov=50.81%`, `missed_opp=89.26%`, `prec=39.22%`, `mean_fwd_net=+3.59%`, `liq_feas=50.98%`, `cum_ret=+16.29%`, `max_dd=3.47%`.
  * **`sparse_research_v1` (raw & H/B recovered identical headline)**: `cov=81.88%`, `missed_opp=87.60%`, `prec=39.42%`, `mean_fwd_net=+4.30%`, `liq_feas=47.12%`, `cum_ret=+18.65%`, `max_dd=1.47%`.
  * **`SPARSE_LATER_FELL` cohort (`10` selected / `173` obs)**: `precision=0.0%`, `false_positive_rate=100.0%`, `mean_fwd_net=-5.11%` (examples: `BTE_ADP -17.16%`, `ASSU_MAGHREBIA_VIE -7.57%`, `SOTETEL -7.23%`, `SOTUVER -6.87%`, `ICF -6.51%` & `-5.45%`).
* `196`s, `H=20` (`6` folds `2026-03-30..2026-09-21`):
  * **Baseline**: `prec=43.75%`, `mean_fwd_net=+7.49%`, `liq_feas=52.08%`, `cum_ret=+16.77%`.
  * **`sparse_research_v1`**: `prec=43.75%`, `mean_fwd_net=+7.01%`, `liq_feas=43.75%`, `cum_ret=+12.98%` — **underperforms baseline**.
* **Verdict on `sparse_research_v1`**: Failed promotion criteria (`DO NOT PROMOTE`). Keep **research-only**.

---

## 4. Complete 42-Security Tunis Bourse Challenge Universe Accounting (`<= 2026-11-10`)

Every row reflects the exact 42 Challenge definitions from `challenge_universe.py`, verified against `bvmt_official_2026` (`194`s Nov 06 vs `196`s Nov 10) after PIT `published_at` replay:

| Sym | Canonical ID | ISIN | Mode | Bars `06`/`10` (`Traded`) | Age `06`/`10` | Miss `60`s | Last Close (TND) | Med Turn `20`s | Freq `20`s | Baseline `11-06` | Baseline `11-10` | Sparse `11-06` Status | Sparse `11-10` Quant | Sel `11-10` | H/B Events |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AB` | `AMEN_BANK` | `TN0003400058` | Continu | 194/196 (196) | 0/0 | 0 | 92.490 | 478,955.94 | 1.00 | `RANK_6` | `RANK_5` | `FULL` | `17.3984` | **YES** | — |
| `ATB` | `ATB` | `TN0003600350` | Continu | 192/194 (192) | 0/0 | 1 | 3.680 | 30,320.79 | 0.95 | `missing_observation` | `missing_observation` | `PARTIAL` | `9.2299` | No | `10-19:B` |
| `ATL` | `ATL` | `TN0004700100` | Continu | 194/196 (196) | 0/0 | 0 | 14.800 | 60,461.74 | 1.00 | `RANK_20` | `RANK_19` | `FULL` | `-8.5744` | No | — |
| `ARTES` | `ARTES` | `TN0007300015` | Continu | 193/195 (193) | 0/0 | 0 | 9.810 | 18,340.14 | 1.00 | `RANK_22` | `untraded_lookback_anchor` | `FULL`/`PARTIAL` | `-3.7985` | No | — |
| `TJARI` | `ATTIJARI_BANK` | `TN0001600154` | Continu | 194/196 (196) | 0/0 | 0 | 78.000 | 172,790.29 | 1.00 | `RANK_29` | `RANK_25` | `FULL` | `-20.8828` | No | — |
| `TJL` | `ATTIJARI_LEASING` | `TN0006610018` | Continu | 192/194 (161) | 1/0 | 2 | 40.190 | 0.00 | 0.45 | `missing_observation` | `missing_observation` | `PARTIAL` | `-7.4747` | No | `08-20:H`, `08-28:B` |
| `BT` | `BT` | `TN0002200053` | Continu | 194/196 (196) | 0/0 | 0 | 8.580 | 136,496.56 | 1.00 | `RANK_21` | `RANK_17` | `FULL` | `-7.9685` | No | — |
| `BNA` | `BNA` | `TN0003100609` | Continu | 194/196 (196) | 0/0 | 0 | 19.900 | 358,397.85 | 1.00 | `RANK_35` | `RANK_24` | `FULL` | `-12.9996` | No | — |
| `BH` | `BH_BANK` | `TN0001900604` | Continu | 192/194 (185) | 0/0 | 1 | 12.770 | 3,238.30 | 0.95 | `missing_observation` | `missing_observation` | `PARTIAL` | `-17.1825` | No | `07-15:H`, `09-23:B` |
| `BIAT` | `BIAT` | `TN0001800457` | Continu | 194/196 (196) | 0/0 | 0 | 166.380 | 335,204.33 | 1.00 | `RANK_13` | `RANK_9` | `FULL` | `5.7053` | No | — |
| `CC` | `CARTHAGE_CEMENT` | `TN0007400013` | Continu | 194/196 (196) | 0/0 | 0 | 1.780 | 117,216.52 | 1.00 | `RANK_33` | `RANK_32` | `FULL` | `-38.3992` | No | — |
| `CITY` | `CITY_CARS` | `TN0007550015` | Continu | 193/195 (194) | 0/0 | 0 | 20.850 | 26,004.39 | 1.00 | `RANK_16` | `RANK_10` | `FULL` | `4.3329` | No | — |
| `DH` | `DELICE_HOLDING` | `TN0007670011` | Continu | 194/196 (196) | 0/0 | 0 | 18.930 | 153,216.54 | 1.00 | `RANK_7` | `RANK_13` | `FULL` | `-3.5135` | No | — |
| `NAKL` | `ENNAKL_AUTOMOBILES` | `TN0007410012` | Continu | 194/196 (194) | 0/0 | 0 | 17.490 | 4,299.43 | 0.95 | `RANK_25` | `insufficient_liquidity` | `FULL` | `-11.1404` | No | — |
| `ECYCL` | `EURO-CYCLES` | `TN0007570013` | Continu | 194/196 (195) | 0/0 | 0 | 9.750 | 21,145.23 | 1.00 | `RANK_27` | `RANK_30` | `FULL` | `-32.9902` | No | — |
| `ICF` | `ICF` | `TN0003200755` | Continu | 193/195 (183) | 0/0 | 1 | 143.500 | 1,364.09 | 0.70 | `missing_observation` | `missing_observation` | `PARTIAL` | `10.0201` | No | `09-22:B` |
| `LNDOR` | `LAND_OR` | `TN0007510019` | Continu | 194/196 (193) | 0/0 | 0 | 14.400 | 24,181.48 | 1.00 | `RANK_10` | `RANK_18` | `FULL` | `-9.0063` | No | — |
| `AMV` | `ASSU_MAGHREBIA_VIE` | `TNDKJ8O68X14` | Continu | 194/196 (195) | 0/0 | 0 | 12.660 | 10,127.47 | 0.95 | `RANK_12` | `RANK_14` | `FULL` | `-6.1788` | No | — |
| `SAM` | `ATELIER_MEUBLE_INT` | `TN0007740012` | Continu | 194/196 (194) | 0/0 | 0 | 5.930 | 7,631.36 | 0.95 | `RANK_19` | `RANK_16` | `FULL` | `-6.1002` | No | — |
| `MPBS` | `MPBS` | `TN0007620016` | Continu | 193/195 (190) | 0/0 | 0 | 10.680 | 8,944.82 | 1.00 | `RANK_8` | `RANK_8` | `FULL` | `7.8502` | No | — |
| `NBL` | `NEW_BODY_LINE` | `TN0007540016` | Continu | 194/196 (179) | 0/0 | 0 | 2.400 | 2,361.54 | 0.95 | `insufficient_liquidity` | `untraded_lookback_anchor` | `FULL`/`PARTIAL` | `-6.5810` | No | — |
| `OTH` | `ONE_TECH_HOLDING` | `TN0007530017` | Continu | 194/196 (196) | 0/0 | 0 | 10.820 | 195,660.06 | 1.00 | `RANK_15` | `RANK_15` | `FULL` | `-5.1445` | No | — |
| `PGH` | `POULINA_GP_HOLDING` *(split `POULINA_GROUP_HOLDING`)* | `TN0005700018` | Continu | 126/128 (128) *(+68 prev ID)* | 0/0 | 0 | 26.490 | 162,008.02 | 1.00 | `RANK_11` | `RANK_12` | `FULL` | `-0.1347` | No | — |
| `SAH` | `SAH` | `TN0007610017` | Continu | 193/195 (195) | 0/0 | 0 | 12.290 | 113,057.73 | 1.00 | `RANK_18` | `RANK_20` | `FULL` | `-12.4946` | No | — |
| `SFBT` | `SFBT` | `TN0001100254` | Continu | 194/196 (196) | 0/0 | 0 | 13.600 | 352,231.79 | 1.00 | `RANK_31` | `RANK_28` | `FULL` | `-27.4099` | No | — |
| `SIAME` | `SIAME` | `TN0006590012` | Continu | 193/195 (190) | 0/0 | 0 | 3.350 | 8,493.54 | 1.00 | `RANK_36` | `RANK_34` | `FULL` | `-50.0000` | No | — |
| `SMART` | `SMART_TUNISIE` | `TNQPQXRODTH8` | Continu | 194/196 (195) | 0/0 | 0 | 32.000 | 19,955.66 | 1.00 | `RANK_4` | `RANK_4` | `FULL` | `17.7090` | **YES** | — |
| `SOTET` | `SOTETEL` | `TN0006530018` | Continu | 194/196 (193) | 0/0 | 0 | 22.120 | 165,379.52 | 1.00 | `RANK_26` | `RANK_26` | `FULL` | `-22.3769` | No | — |
| `STPAP` | `SOTIPAPIER` | `TN0007630015` | Continu | 193/195 (186) | 0/0 | 0 | 2.600 | 1,277.68 | 0.85 | `insufficient_liquidity` | `insufficient_liquidity` | `FULL` | `14.9325` | **YES** | — |
| `STPIL` | `SOTRAPIL` | `TN0006660013` | Continu | 194/196 (193) | 0/0 | 0 | 25.400 | 6,675.47 | 0.90 | `RANK_37` | `RANK_35` | `FULL` | `-50.0000` | No | — |
| `MGR` | `SOTUMAG` | `TN0006580013` | Continu | 193/195 (185) | 0/0 | 1 | 21.000 | 38,893.51 | 0.95 | `missing_observation` | `missing_observation` | `PARTIAL` | `73.0690` | **YES** | `08-04:H` |
| `SOTUV` | `SOTUVER` | `TN0006560015` | Continu | 194/196 (186) | 0/0 | 0 | 23.220 | 86,604.36 | 1.00 | `RANK_32` | `RANK_29` | `FULL` | `-28.1747` | No | — |
| `SPDIT` | `SPDIT_-_SICAF` | `TN0001400704` | Continu | 194/196 (189) | 0/0 | 0 | 16.200 | 2,076.65 | 0.95 | `insufficient_liquidity` | `insufficient_liquidity` | `FULL` | `7.5421` | No | — |
| `STA` | `STA` | `TNNGTFLC2986` | Continu | 193/195 (190) | 0/0 | 0 | 114.500 | 30,780.73 | 0.95 | `RANK_1` | `RANK_1` | `FULL` | `39.9688` | **YES** | — |
| `STB` | `STB` | `TN0002600955` | Continu | 194/196 (195) | 0/0 | 0 | 5.100 | 59,464.38 | 1.00 | `RANK_24` | `RANK_21` | `FULL` | `-10.9806` | No | — |
| `TLNET` | `TELNET_HOLDING` | `TN0007440019` | Continu | 194/196 (195) | 0/0 | 0 | 11.900 | 77,982.67 | 1.00 | `RANK_9` | `RANK_11` | `FULL` | `1.4133` | No | — |
| `TPR` | `TPR` | `TN0007270010` | Continu | 194/196 (196) | 0/0 | 0 | 12.240 | 95,803.29 | 1.00 | `RANK_28` | `RANK_23` | `FULL` | `-18.4093` | No | — |
| `TRE` | `TUNIS_RE` | `TN0007380017` | Fixing | 185/187 (178) | 0/0 | 3 | 8.860 | 4,122.50 | 0.75 | `missing_observation` | `missing_observation` | `PARTIAL` | `-29.1611` | No | `07-20:H`, `09-21:B`, `09-22:B`, `11-02:H` |
| `TLS` | `TUNISIE_LEASING_F` | `TN0002100907` | Continu | 193/195 (189) | 0/0 | 0 | 36.320 | 31,803.34 | 0.90 | `RANK_17` | `RANK_22` | `FULL` | `-17.1635` | No | — |
| `UIB` | `UIB` | `TN0003900107` | Continu | 194/196 (190) | 0/0 | 0 | 36.000 | 10,847.68 | 0.95 | `RANK_5` | `RANK_6` | `FULL` | `13.7946` | No | — |
| `UMED` | `UNIMED` | `TN0007720014` | Continu | 194/196 (195) | 0/0 | 0 | 8.430 | 62,378.12 | 1.00 | `RANK_34` | `RANK_31` | `FULL` | `-34.8325` | No | — |
| `WIFAK` | `WIFACK_INT_BANK` | `TN0007200017` | Fixing | 193/195 (159) | 0/0 | 0 | 6.750 | 8,009.15 | 1.00 | `untraded_lookback_anchor` | `RANK_33` | `PARTIAL`/`FULL` | `-46.5050` | No | — |
