# BVMT Quantitative Experiment Registry (`2026` Comparative & Risk-Normalized Suite)

**Registry Schema Version**: `1.1.0` (Milestone 5 Risk-Normalized & Audited Suite; Milestone 4 preserved in `artifacts/strategy_experiments_2026_v1_archive.json`)  
**Machine-Readable Artifact**: `artifacts/strategy_experiments_2026.json`  
**Code Generator**: [`generate_experiment_registry()`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/strategies.py) in [`src/bvmt/strategies.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/strategies.py)  
**Independent Audit Report**: [`docs/INDEPENDENT_STRATEGY_AUDIT.md`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/docs/INDEPENDENT_STRATEGY_AUDIT.md)  
**Statistical Classification**: `exploratory` (`is_statistically_conclusive: false`, `194 < 250` sessions)  
**Model G Audit Status**: `exploratory_unvalidated_high_outlier_dependency` (`model_g_promotion_eligible: false`)

---

## 1. Cryptographic Provenance & Reproducibility Hashes

| Provenance Field | Verified Value |
| :--- | :--- |
| **Canonical Bars SHA-256 (`canonical_sha256`)** | `cdec16511f5d5ecd937a89656f9cd65746eb6655091447bc0078f7a30b159116` |
| **Raw NDJSON Archive SHA-256 (`archive_sha256`)** | `486761f55253480a0e19e9b7e8300512522316f93f67081c6fa010d86df45c55` |
| **Parsed Dataset Hash (`data_hash`)** | `bde44a60246fdaf4540f33dba5579d91b397c5ac061b81100919652b61e000d3` |
| **Evaluation Horizon** | `2026-01-02` to `2026-11-06` (`194` verified open sessions; `61`-session warmup; `134` active decision/mark sessions) |
| **Initial Capital** | `50,000.000 TND` |
| **Baseline Execution Profile** | T+1 `next_open`, `0.50%` (`50 bps`) buy/sell fee, `10 bps` slippage, `8.5%` target / `10.0%` purchase cap (`top_k = 5`), `10.0%` volume participation cap, rebalance every `19` sessions |

---

## 2. Standard 5-Slot (`8.5%` Target) Comparative Results (`A` through `I`)

| Strategy ID | Marked Net Return | Liquidated Return | Excess vs. C (Marked) | Excess vs. C (Liq) | Excess vs. B (Marked) | Max Drawdown | Turnover | Total Fees (TND) | Fills / Orders | Hit Rate | All-Session Util | Active Post-Warmup Util |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`A_CASH_ONLY`** | `0.0000%` | `0.0000%` | `-14.0261%` | `-13.6074%` | `-14.0480%` | `0.0000%` | `0.00x` | `0.000` | `0 / 0` | `0.00%` | `0.00%` | `0.00%` |
| **`B_EQUAL_WEIGHT_ELIGIBLE`** | `+14.0480%` | `+13.4955%` | `+0.0218%` | `-0.1119%` | `0.0000%` | `17.1999%` | `1.27x` | `635.963` | `46 / 52` | `84.62%` | `64.80%` | **`93.81%`** |
| **`C_BUY_AND_HOLD_BENCHMARK`** | `+14.0261%` | `+13.6074%` | `0.0000%` | `0.0000%` | `-0.0218%` | `12.6055%` | `0.69x` | `346.890` | `7 / 10` | `85.71%` | `50.04%` | **`72.44%`** |
| **`D_MOMENTUM_20S`** | `+17.0506%` | `+16.9027%` | `+3.0245%` | `+3.2953%` | `+3.0026%` | `5.3533%` | `2.39x` | `1,192.787` | `40 / 41` | `65.52%` | `18.52%` | `26.81%` |
| **`E_MOMENTUM_60S`** | `+14.3561%` | `+14.2613%` | `+0.3300%` | `+0.6540%` | `+0.3081%` | `8.1179%` | `1.83x` | `916.464` | `37 / 39` | `66.67%` | `21.74%` | `31.47%` |
| **`F_RELATIVE_STRENGTH_20S`** | `+17.0506%` | `+16.9027%` | `+3.0245%` | `+3.2953%` | `+3.0026%` | `5.3533%` | `2.39x` | `1,192.787` | `40 / 41` | `65.52%` | `18.52%` | `26.81%` |
| **`G_LIQUIDITY_FILTERED_MOMENTUM`** | **`+18.8117%`** | **`+18.7289%`** | **`+4.7856%`** | **`+5.1215%`** | **`+4.7638%`** | **`4.9840%`** | `2.39x` | `1,196.867` | `43 / 44` | `67.86%` | `20.57%` | `29.79%` |
| **`H_DOWNSIDE_RISK_TREND_MULTIFACTOR`** | `+15.1450%` | `+15.0631%` | `+1.1188%` | `+1.4557%` | `+1.0970%` | `6.0951%` | `2.35x` | `1,173.480` | `43 / 44` | `64.29%` | `18.92%` | `27.40%` |
| **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** | `+15.7354%` | `+15.7147%` | `+1.7092%` | `+2.1073%` | `+1.6874%` | `5.4662%` | `2.18x` | `1,089.535` | `41 / 42` | **`69.23%`** | `17.02%` | `24.64%` |

---

## 3. Milestone 5 Risk-Normalized, Equal-Budget & Outlier-Adjusted Comparison

When we normalize for **active post-warmup capital utilization (`active_cash_utilization_pct`)**, re-simulate at an **equalized 10-slot (`9.5%` target) capital budget**, and test **excluding the single largest outlier (`SOTETEL`, `+202.29%`)**, the true economic structure of Models `A`–`I` emerges:

| Strategy ID | Active Util (%) | Exposure-Normalized Return (%) | Exposure-Normalized Max DD (%) | Realized Ann. Vol (%) | Return / Vol Ratio | Cash-Matched Bench B (%) | Excess vs. Cash-Matched B (%) | Equal-Budget 10-Slot Net Return (%) | Equal-Budget 10-Slot Max DD (%) | Ex-`SOTETEL` Net Return (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`A_CASH_ONLY`** | `0.00%` | `0.00%` | `0.00%` | `0.00%` | `0.00` | `0.00%` | `0.00%` | `0.0000%` | `0.00%` | `0.0000%` |
| **`B_EQUAL_WEIGHT_ELIGIBLE`** | `93.81%` | `+14.97%` | `18.33%` | `15.11%` | `0.93` | `+14.05%` | `0.00%` | `+14.0480%` | `17.20%` | `+14.0480%` |
| **`C_BUY_AND_HOLD_BENCHMARK`** | `72.44%` | `+19.36%` | `17.40%` | `11.89%` | `1.18` | `+10.85%` | `+3.18%` | `+14.0261%` | `12.61%` | `+14.0261%` |
| **`D_MOMENTUM_20S`** | `26.81%` | `+63.61%` | `19.97%` | `8.89%` | `1.92` | `+4.01%` | `+13.04%` | `+26.9350%` | `12.39%` | `+4.1298%` |
| **`E_MOMENTUM_60S`** | `31.47%` | `+45.61%` | `25.79%` | `9.92%` | `1.45` | `+4.71%` | `+9.64%` | `+21.1587%` | `14.00%` | `+2.9324%` |
| **`F_RELATIVE_STRENGTH_20S`** | `26.81%` | `+63.61%` | `19.97%` | `8.89%` | `1.92` | `+4.01%` | `+13.04%` | `+26.9350%` | `12.39%` | `+4.1298%` |
| **`G_LIQUIDITY_FILTERED_MOMENTUM`** | `29.79%` | `+63.15%` | **`16.73%`** | `8.99%` | **`2.09`** | `+4.46%` | **`+14.35%`** | `+25.3667%` | `10.92%` | **`+7.4320%`** |
| **`H_DOWNSIDE_RISK_TREND_MULTIFACTOR`** | `27.40%` | `+55.28%` | `22.25%` | `8.85%` | `1.71` | `+4.10%` | `+11.04%` | `+27.7614%` | `11.13%` | `+3.7382%` |
| **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** | `24.64%` | **`+63.85%`** | `22.18%` | **`8.67%`** | `1.81` | `+3.69%` | `+12.05%` | **`+28.8225%`** | **`10.30%`** | `+4.6046%` |

### Key Conclusions from Risk-Normalized & Outlier-Adjusted Testing
1. **Why Model G Had the Lowest Raw Drawdown (`4.98%`)**: Model G only deployed `29.79%` of capital during active post-warmup sessions. Its exposure-normalized sleeve drawdown (`16.73%`) is only marginally lower than Buy-and-Hold `C` (`17.40%`) and Equal-Weight `B` (`18.33%`).
2. **Equal-Budget (`10-Slot`) Winner is Model I (`+28.82%`), Not Model G (`+25.37%`)**: When active strategies are scaled to `10` slots (`9.5%` target weight) to match Benchmark B/C exposure, **`I_REGIME_FILTERED_QUALITY_MOMENTUM`** achieves the highest return (`+28.8225%`) and lowest max drawdown (`10.30%`), followed by **`H_DOWNSIDE_RISK_TREND_MULTIFACTOR`** (`+27.7614%`).
3. **Single-Stock Outlier Sensitivity (`ex-SOTETEL`)**: Removing `SOTETEL` reduces Model G's 5-slot return from `+18.8117%` to `+7.4320%` (which still beats cash-matched Benchmark B's `+4.46%` by `+2.97%`, whereas `D`, `E`, `F`, and `H` fall close to or below their cash-matched benchmark). This proves that **liquidity and fee-hurdle filtering in Model G adds real downside protection on secondary trades (`+7.43%` vs `+4.13%` for unfiltered `D`), but ~60% of its headline `+18.81%` return came from a single stock (`SOTETEL`)**.
