# Independent strategy audit — Milestone 5, Phase 0

Audit completed before strategy logic changes on 2026-11-08. Profile: research-conservative; offline local evidence, not verified competition rules. Line references below identify the Milestone 4 source (strategies.py SHA-256 `4875cdac53e65af8e723c0c84d4c8993fe7f2e7a3a4f397589925ee3b483f503`); later additive changes move lines. Original registry preserved byte-for-byte as `artifacts/strategy_experiments_2026_v1_archive.json`.

| Severity | Question | Evidence and finding |
|---|---|---|
| CRITICAL | 7: volume participation | `strategies.py:392–395, 407, 417–424` computes capacity from execution-day full-day volume, but executes at that day's open. `execution.py:60–78` has the same assumption. Full-day volume is unavailable at the open: intraday volume lookahead. Ten percent of daily volume may exceed the entire opening auction. Daily OHLCV cannot validate auction capacity. All new robustness simulations inherit this hypothetical fill model; none repairs this missing intraday evidence. |
| HIGH | 2: model selection | `strategies.py:36–56, 739–745` registers nine A–I hypotheses after observing one 194-session 2026 sample (`trial_count=9`). Structural selection, not just parameter fitting, induces specification-selection bias. No promotion of G is justified without untouched forward evidence. |
| HIGH | 4: cash and outlier attribution | G is 20.574965% invested overall and 29.787636% over 134 active marks. Its 4.983999% drawdown is strongly confounded by cash. SOTETEL is material, but the requested claim that it generated >100% of all D–I profits is contradicted by the saved registry; details below. |
| HIGH | 5: concentration | `strategies.py:405–414` caps purchases only; `460–463, 527–529` measures subsequent drift. Rebalance is every 19 sessions (`476–497`). G reaches 14.251688% with 22 breach sessions; C reaches 14.697064% with 133. Compliance is explicitly false. Next-open trims cannot guarantee a continuous hard cap under gaps, zero volume or capacity constraints. |
| HIGH | 9: actions | `strategies.py:59–62, 299–300`; `features.py:325–326` use raw closes, with no dividend/split/rights table. An ex-dividend price drop can mechanically lower bank/insurer momentum and understate buy-and-hold total return. Magnitude cannot be quantified without action evidence. |
| HIGH | 10: folds | `strategies.py:595–615, 641–645` uses 61 training/19 test sessions, seven chronological folds, resetting cash and fitting no parameters. G/H/I structures and thresholds were selected using the entire period. These are chronological stability checks, not untouched model-selection-independent OOS tests. |
| MEDIUM | 1: benchmarks | `strategies.py:592, 720–723` compares marked strategy return with marked C only. Liquidated excess and B comparison were absent. Cash exposure differs enormously; unadjusted excess does not isolate ranking skill. Earlier audit benchmark conventions differ; see below. |
| MEDIUM | 6: opening data | 14,480 canonical bars, 11,920 traded: 3,922 open=close (32.90%), 2,993 flat OHLC (25.11%), 2,547 volume<500 (21.37%). Presence of an open field does not establish executable auction liquidity; out-of-range slippage is blocked by `execution.py:78–79`. |
| MEDIUM | 8: costs and exit | `execution.py:94–95` defaults to 50 bps commission, 10 bps adverse slippage; `80–82` rounds fees half-up to .001 TND. `strategies.py:85–86, 425` rounds notional too. `500–508` subtracts terminal 50 bps fee only, without exit slippage or multi-day capacity simulation. Liquidated returns are estimates. |
| LOW | 3: duplicate hypotheses | `strategies.py:320–330`: rs_i(t)=mom_i(t)-mean_j(mom_j(t)). Subtracting the same scalar strictly preserves ordering, including ties. If five eligible names exceed the mean, D and F select identical ordered top five. This holds on all seven dates below; duplication reduces strategy diversity. |

## Reproduction and empirical measurements

Local inputs: `data/processed/bvmt_official_2026/daily_bars.canonical.csv` (canonical SHA-256 `cdec16511f5d5ecd937a89656f9cd65746eb6655091447bc0078f7a30b159116`), dated master and exchange calendar in the same directory. Read using `read_bars_csv`, `read_instrument_master`, `read_exchange_calendar`. 194 sessions span 2026-01-02–2026-11-06. Index 60 is 2026-03-30; `curve[60:]` includes that initial flat decision mark and has 134 marks. Active utilization is the arithmetic mean of holdings/equity over those marks. Warmup is not counted as invested capital.

| Model | Marked return % | Liquidated return % | Active utilization % | Maximum drawdown % | Maximum weight % | Breach sessions |
|---|---:|---:|---:|---:|---:|---:|
| B | 14.047960 | 13.495489 | 93.813194 | 17.199911 | 12.808956 | 133 |
| C | 14.026112 | 13.607358 | 72.441246 | 12.605515 | 14.697064 | 133 |
| D | 17.050596 | 16.902679 | 26.805481 | 5.353297 | 14.352114 | 23 |
| E | 14.356077 | 14.261320 | 31.473681 | 8.117902 | 13.943277 | 24 |
| F | 17.050596 | 16.902679 | 26.805481 | 5.353297 | 14.352114 | 23 |
| G | 18.811715 | 18.728904 | 29.787636 | 4.983999 | 14.251688 | 22 |
| H | 15.144953 | 15.063097 | 27.397489 | 6.095076 | 14.340509 | 23 |
| I | 15.735354 | 15.714658 | 24.644349 | 5.466234 | 14.340509 | 23 |

Five 8.5% targets impose 42.5% maximum intended gross exposure before market drift. One-shot next-open partial fills (`carry_pending_orders=False`) lower actual exposure. G holds 70.212364% cash actively and 79.425035% across all marks. Exposure-scaled drawdown is 4.983999/0.29787636 = approximately 16.73%, versus B's 17.199911/0.93813194 = 18.33%. This ratio is a descriptive normalization, not the drawdown of a dynamically leveraged portfolio. Cash-matched and equal-budget reruns are needed; higher utilization may worsen execution and losses.

D/F rebalance dates and counts above the cross-sectional mean: 2026-03-30:18; 2026-04-27:13; 2026-05-25:14; 2026-06-24:16; 2026-08-03:16; 2026-09-01:18; 2026-10-09:18. Ordered targets match on every date. Both have +17.050596%, 40 fills, 1,192.787 TND fees.

## Outlier claim: measured correction

Registry `assumptions.execution.initial_cash_tnd` is **100000.000**, unlike the earlier backtest audit's **50000.000**. G's closed SOTETEL round trip costs approximately 8,465.81 TND including entry fee and yields approximately 20,563.60 TND after exit fee: net **12,097.7841 TND**, or **12.097784%** of registry initial equity, approximately **64.31%** of G net profit. It is 24.195568% of a hypothetical 50,000 denominator, but that denominator is not this registry's initial capital. Do not mix the two experiments.

Independent exclusion rerun (remove SOTETEL from bars before feature computation, recomputing cross-sectional means, targets, sizing and fills with unchanged config): D +4.129819%, E +2.932361%, F +4.129819%, G +7.431954%, H +3.738236%, I +4.604604%. These are positive after modeled costs. Exclusion reruns are counterfactual portfolios and differ from subtracting the original trade contribution. Even direct subtraction leaves these registry portfolios profitable. The assertion of >100% dependency and slightly negative ex-SOTETEL outcomes is unsupported for this artifact. Dependency remains substantial and does not justify promotion.

## Benchmark convention reconciliation

The request describes `artifacts/backtest_audit_2026.json` as frictionless, but the **locally saved artifact contradicts that premise**: its limitations explicitly say the first-open static equal-sleeve benchmark pays entry costs and respects share caps. Independently rerunning reviewed `run_historical_backtest` with no strategy orders, the 64 principal instruments, the saved calendar, 50,000 TND capital, 50 bps fees, 10 bps slippage and 10% participation reproduces the saved benchmark **19.94452800%** exactly. Its first mark is **49,969.104 TND**, final mark **59,972.264 TND**, also exact matches. `execution.py:342–369` implements these entry costs and caps. No earlier frictionless artifact version is locally established; do not attribute that convention to this saved file. The saved post-warmup benchmark is **12.4410600%**. Differences from B/C still include inception dates, universe, starting cash, and order persistence. Milestone 4 C starts after warmup with next-open execution, fees, slippage and one-shot participation limits; B periodically rebalances its initial sleeves. C marked return is 14.026112%, liquidated 13.607358%. Existing excess subtracts only marked C. Compare both conventions explicitly and retain old fields as historical contracts.

## Historical acquisition evidence and blockers

Inspected `data/staging/market_resume_full.ndjson`, processed directory and its provenance/manifest, and `data/raw/` (only `.gitkeep`). Processed v1/v2/previous-partial directories are alternate 2026 imports, not independently acquired 2020–2025 daily archives. The NDJSON historical coverage audit reports older monthly summaries without usable daily quantities/OHLCV. No verified corporate-action adjustment table is present. The saved manifest reports older ZIP requests returned zero bytes; this is an attributed user report, not a new HTTP test. An authorized official daily-history delivery and dated dividend/split/rights records are required. No older bars/actions were synthesized, no source endpoints invented and no network acquisition attempted.

## Required interpretation of Milestone 5

Additional exact accounting checks: the registry simulator rounds each fill notional to .001 TND before cash posting. Consequently G's ledger-consistent SOTETEL P&L is **12,097.785 TND**; 12,097.7841 above is the unrounded price-times-quantity cash-flow calculation, differing by less than .001 TND. Reconstructing holdings from saved fills and marking every close identifies G's 14.251688% peak as **SOTETEL on 2026-05-19**, and C's 14.697064% peak as **BNA on 2026-07-17**. Archive file SHA-256 is `719895467f1c706c687571ee345e93146ff4a206208d9aff0ef3cfe2cc2c637a`.

G remains `exploratory_unvalidated_high_outlier_dependency`, promotion ineligible. Risk ratios and deterministic moving-block bootstrap intervals describe this selected, short sample; they do not correct selection bias, unavailable auction volume, missing actions or membership/availability gaps. Continuous trims are delayed capacity-limited interventions, not hard-cap compliance. The forward journal must begin at its actual recording time, never populate simulated historical fills as forward evidence, and remain separate from the competition account.
