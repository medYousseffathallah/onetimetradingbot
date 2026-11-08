# BVMT Quantitative Experiment Registry (`2026` Comparative Suite)

**Registry Schema Version**: `1.0.0`  
**Machine-Readable Artifact**: `artifacts/strategy_experiments_2026.json`  
**Code Generator**: [`generate_experiment_registry()`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/strategies.py#L762) in [`src/bvmt/strategies.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/strategies.py)  
**Statistical Classification**: `exploratory` (`is_statistically_conclusive: false`, `194 < 250` sessions)  
**Promotion Policy**: `research_only_requires_human_approval` (Zero automatic promotion into live trading)

---

## 1. Cryptographic Provenance & Reproducibility Hashes

Every metric reported in this registry and rendered in the Strategy Lab UI (`/strategy`) is bound to deterministic SHA-256 hashes of the canonical dataset, strategy code, and simulation configuration:

| Provenance Field | Verified Value |
| :--- | :--- |
| **Canonical Bars SHA-256 (`canonical_sha256`)** | `cdec16511f5d5ecd937a89656f9cd65746eb6655091447bc0078f7a30b159116` |
| **Raw NDJSON Archive SHA-256 (`archive_sha256`)** | `486761f55253480a0e19e9b7e8300512522316f93f67081c6fa010d86df45c55` |
| **Parsed Dataset Hash (`data_hash`)** | `bde44a60246fdaf4540f33dba5579d91b397c5ac061b81100919652b61e000d3` |
| **Strategy Engine SHA-256 (`code_sha256`)** | `4875cdac53e65af8e723c0c84d4c8993fe7f2e7a3a4f397589925ee3b483f503` |
| **Contract & Config Hash (`config_hash`)** | `87e57368642da1b01a0cefd7f720e4e200f1d38e2f900374b6699c63285f5927` |
| **Evaluation Horizon** | `2026-01-02` to `2026-11-06` (`194` verified open sessions; `61`-session warmup; `133` active sessions) |
| **Initial Capital** | `50,000.000 TND` |
| **Execution Profile** | T+1 `next_open`, `0.50%` (`50 bps`) buy/sell fee, `10 bps` slippage, `8.5%` target / `10.0%` purchase cap, `10.0%` volume participation cap, rebalance every `19` sessions |

---

## 2. Full-Period Comparative Strategy Results (`A` through `I`)

All 9 registered strategies (`7` baselines + `2` multi-factor enhancements) were evaluated over the identical 194-session 2026 BVMT dataset under identical execution and fee rules:

| Strategy ID | Family | Experiment ID (Prefix) | Marked Net Return (%) | Liquidated Net Return (%) | Excess vs. Benchmark C (%) | Max Drawdown (%) | Turnover Ratio (x) | Total Fees (TND) | Fills / Orders | Hit Rate (%) | Avg Cash Util (%) | Max Weight w/ Drift (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`A_CASH_ONLY`** | Baseline | `d249531fab98e972` | `0.0000%` | `0.0000%` | `-14.0261%` | `0.0000%` | `0.0000x` | `0.000` | `0 / 0` | `0.00%` | `0.00%` | `0.00%` |
| **`B_EQUAL_WEIGHT_ELIGIBLE`** | Baseline | `a115d18cda3a4084` | `+14.0480%` | `+13.4955%` | `+0.0218%` | `17.1999%` | `1.2719x` | `635.963` | `46 / 52` | `84.62%` | `64.80%` | `12.81%` |
| **`C_BUY_AND_HOLD_BENCHMARK`** | Baseline | `679d0708eca625ca` | `+14.0261%` | `+13.6074%` | `0.0000%` | `12.6055%` | `0.6938x` | `346.890` | `7 / 10` | `85.71%` | `50.04%` | `14.70%` |
| **`D_MOMENTUM_20S`** | Baseline | `468ba4e77e328636` | `+17.0506%` | `+16.9027%` | `+3.0245%` | `5.3533%` | `2.3856x` | `1,192.787` | `40 / 41` | `65.52%` | `18.52%` | `14.35%` |
| **`E_MOMENTUM_60S`** | Baseline | `8863822254050da4` | `+14.3561%` | `+14.2613%` | `+0.3300%` | `8.1179%` | `1.8329x` | `916.464` | `37 / 39` | `66.67%` | `21.74%` | `13.94%` |
| **`F_RELATIVE_STRENGTH_20S`** | Baseline | `5a45434a2f649a2c` | `+17.0506%` | `+16.9027%` | `+3.0245%` | `5.3533%` | `2.3856x` | `1,192.787` | `40 / 41` | `65.52%` | `18.52%` | `14.35%` |
| **`G_LIQUIDITY_FILTERED_MOMENTUM`** | **Baseline (Prod)** | `a613a8b406de75d6` | **`+18.8117%`** | **`+18.7289%`** | **`+4.7856%`** | **`4.9840%`** | `2.3937x` | `1,196.867` | `43 / 44` | `67.86%` | `20.57%` | `14.25%` |
| **`H_DOWNSIDE_RISK_TREND_MULTIFACTOR`** | Enhanced | `c29253260faae591` | `+15.1450%` | `+15.0631%` | `+1.1188%` | `6.0951%` | `2.3470x` | `1,173.480` | `43 / 44` | `64.29%` | `18.92%` | `14.34%` |
| **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** | Enhanced | `d680a10db78c3795` | `+15.7354%` | `+15.7147%` | `+1.7092%` | `5.4662%` | `2.1791x` | `1,089.535` | `41 / 42` | **`69.23%`** | `17.02%` | `14.34%` |

---

## 3. Position Win/Loss Distribution & Tail-Risk Analysis

| Strategy ID | Winning Slices | Losing Slices | Best Position Return (%) | Worst Position Return (%) | Economic Interpretation |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`A_CASH_ONLY`** | `0` | `0` | `—` | `—` | Zero market risk; trails inflation and market beta. |
| **`B_EQUAL_WEIGHT_ELIGIBLE`** | `22` | `4` | `+64.5630%` | `-10.3463%` | Broad market rise lifts most sleeves, but `17.20%` portfolio drawdown during spring correction. |
| **`C_BUY_AND_HOLD_BENCHMARK`** | `6` | `1` | `+52.1505%` | `-2.0284%` | Low fee drag (`346.890 TND`), but `12.61%` drawdown and no rotation into mid-year breakouts. |
| **`D_MOMENTUM_20S`** | `19` | `10` | `+195.5024%` | `-16.1612%` | Captures strong short-term winners, but vulnerable to `-16.16%` reversals on unscreened names. |
| **`E_MOMENTUM_60S`** | `16` | `8` | `+202.2769%` | `-22.1756%` | Suffers the deepest single-position loss (`-22.18%`) due to delayed exit on 60-session lookback. |
| **`F_RELATIVE_STRENGTH_20S`** | `19` | `10` | `+195.5024%` | `-16.1612%` | Identical top-5 selection to `D` when top momentum leaders all exceed cross-sectional mean. |
| **`G_LIQUIDITY_FILTERED_MOMENTUM`** | `19` | `9` | **`+202.2909%`** | **`-9.1815%`** | **Best overall risk-return profile**: liquidity (`>= 5,000 TND`), trade-frequency (`>= 60%`), and `1.5%` fee-hurdle filters cut worst-position loss nearly in half (`-9.18%` vs `-16.16%`) while achieving highest net return (`+18.81%`) and lowest max drawdown (`4.98%`). |
| **`H_DOWNSIDE_RISK_TREND_MULTIFACTOR`** | `18` | `10` | `+202.2909%` | `-16.1612%` | Downside-risk and drawdown penalties reduce turnover slightly (`1,173.48 TND`) but underperform `G` in strong momentum breakouts. |
| **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** | `18` | `8` | `+202.2909%` | `-16.1612%` | **Highest active hit rate (`69.23%`) and lowest active fee drag (`1,089.54 TND`)**: regime filter halves target exposure when `bench_20 < 0`, avoiding late-autumn whipsaws. |

---

## 4. 7-Fold Chronological Walk-Forward Results (`Train = 61`, `Test = 19`, `Step = 19`)

Each fold resets capital to `50,000.000 TND`, uses the trailing `61` sessions strictly for point-in-time feature warmup, and evaluates fresh T+1 execution over the next `19` open sessions:

| Fold # | Test Window (`19` Sessions) | `B` Equal Weight (%) | `C` Buy & Hold (%) | `D` Mom 20S (%) | `E` Mom 60S (%) | `G` Liq-Mom T04 (%) | `H` Multi-Factor (%) | `I` Regime-Filtered (%) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Fold 1** | `2026-03-31` -> `2026-04-27` | `+2.7056%` | `+2.7056%` | `+0.1389%` | `+0.5510%` | `+0.3898%` | `+0.3898%` | `+0.3898%` |
| **Fold 2** | `2026-04-28` -> `2026-05-25` | `+8.8999%` | `+8.8999%` | `+8.3967%` | **`+8.9888%`** | `+8.6881%` | `+8.3967%` | `+8.3967%` |
| **Fold 3** | `2026-05-26` -> `2026-06-24` | **`+10.1620%`** | **`+10.1620%`** | `+5.8178%` | `+5.2935%` | `+5.1022%` | `+5.1022%` | `+5.1022%` |
| **Fold 4** | `2026-07-06` -> `2026-08-03` | `-0.3996%` | `-0.3996%` | `+0.0442%` | `+0.0462%` | **`+0.4965%`** | `+0.0462%` | `+0.0462%` |
| **Fold 5** | `2026-08-04` -> `2026-09-01` | `-0.7907%` | `-0.7907%` | `-0.5550%` | `-0.7072%` | **`-0.2878%`** | `-0.7200%` | `-0.7200%` |
| **Fold 6** | `2026-09-15` -> `2026-10-09` | `-1.0453%` | `-1.0453%` | `-1.1660%` | **`-0.3495%`** | `-0.7164%` | `-0.7164%` | `-0.4798%` |
| **Fold 7** | `2026-10-12` -> `2026-11-06` | `+0.0922%` | `+0.0922%` | `-0.0752%` | `-0.0673%` | `-0.1241%` | `-0.1241%` | **`0.0000%`** |
| **Mean** | **All 7 Folds (`4/7` Pos)** | `+2.8035%` | `+2.8035%` | `+1.8002%` | `+1.9651%` | `+1.9355%` | `+1.7678%` | `+1.8193%` |

### Key Walk-Forward Findings
1. **Regime Dichotomy (Folds 1–3 vs. Folds 4–7)**:
   - During the broad spring rally (**Folds 1–3**: April–June 2026), higher-beta broad baskets (`B` and `C`, ~50–65% invested) outperformed selective 5-slot momentum sleeves (~20% average cash utilization due to `8.5%` target sizing and volume participation caps).
   - During the summer/autumn consolidation (**Folds 4–6**: July–October 2026), when the benchmark lost `-0.40%`, `-0.79%`, and `-1.05%`, **`G_LIQUIDITY_FILTERED_MOMENTUM`** generated positive excess return in all three folds (`+0.8961%`, `+0.5029%`, and `+0.3289%` excess return), and **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** went completely flat (`0` fills, `0.00%` loss) in **Fold 7** when momentum signals turned choppy.

---

## 5. Fee & Liquidity Sensitivity Grid (`3 x 3` Full Re-Simulation)

Every strategy was re-simulated from scratch across `3` commission levels (`30 bps`, `50 bps`, `70 bps`) $\times$ `3` volume participation caps (`5%`, `10%`, `20%` of daily share volume):

| Strategy ID | Min Net Return Across Grid (%) | Baseline (`50 bps`, `10%` Vol Cap) (%) | Max Net Return Across Grid (%) | Sensitivity Spread (Max - Min) |
| :--- | :---: | :---: | :---: | :---: |
| **`A_CASH_ONLY`** | `0.0000%` | `0.0000%` | `0.0000%` | `0.0000%` |
| **`B_EQUAL_WEIGHT_ELIGIBLE`** | `+13.6039%` | `+14.0480%` | `+14.2952%` | `0.6913%` |
| **`C_BUY_AND_HOLD_BENCHMARK`** | `+13.4030%` | `+14.0261%` | `+14.1691%` | `0.7660%` |
| **`D_MOMENTUM_20S`** | `+15.5925%` | `+17.0506%` | `+17.8539%` | `2.2614%` |
| **`E_MOMENTUM_60S`** | `+12.8770%` | `+14.3561%` | `+16.2279%` | `3.3510%` |
| **`F_RELATIVE_STRENGTH_20S`** | `+15.5925%` | `+17.0506%` | `+17.8539%` | `2.2614%` |
| **`G_LIQUIDITY_FILTERED_MOMENTUM`** | **`+17.4734%`** | **`+18.8117%`** | **`+19.9143%`** | `2.4408%` |
| **`H_DOWNSIDE_RISK_TREND_MULTIFACTOR`** | `+13.7360%` | `+15.1450%` | `+16.2025%` | `2.4664%` |
| **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** | `+14.1921%` | `+15.7354%` | `+17.0651%` | `2.8730%` |

Even under the most punitive friction scenario (`70 bps` commission per side + `5%` volume participation cap), **`G_LIQUIDITY_FILTERED_MOMENTUM`** delivers **`+17.4734%`**, outperforming the baseline return of every other strategy in the suite.

---

## 6. Governance Conclusion & Active Recommendation Engine Selection

1. **Retained Production Baseline**: **`G_LIQUIDITY_FILTERED_MOMENTUM`** (the T04 Liquidity-Filtered Volatility-Adjusted Momentum model) remains the highest-performing and lowest-drawdown strategy on the verified 2026 BVMT dataset (`+18.8117%` net return, `4.9840%` max drawdown, `-9.1815%` worst slice).
2. **Complementary Regime Diagnostic**: **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** is retained in the Strategy Lab comparison suite as a defensive regime indicator (`69.23%` hit rate, lowest active fee drag).
3. **Purchase Concentration vs. Post-Entry Market Drift**: All orders strictly enforce the `8.5%` target weight and `10.0%` purchase concentration cap at order entry (`room = 0.10 * equity - owned * price`). When a winning stock appreciates strongly between 19-session rebalance dates (up to `+202.29%` on the top winner), its mark-to-market weight drifts up to `14.25%–14.70%` before being trimmed at the next scheduled rebalance. In live daily trading, [`src/bvmt/recommendations.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/recommendations.py) monitors this daily and emits an immediate `REDUCE` recommendation whenever any holding reaches `9.5%` (`REDUCE_TRIGGER_WEIGHT_RATIO = 0.095`).
4. **Machine Learning Promotion Gate**: Blocked (`session_count = 194 < 250`).
