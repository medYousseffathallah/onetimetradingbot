# BVMT Market Microstructure Research (2026 Empirical Audit)

**Provenance Notice**: All empirical figures below are computed directly by [r2_microstructure_audit.py](../../research/experiments-v2/r2_microstructure_audit.py) and stored in [r2_microstructure_results.json](../../research/experiments-v2/r2_microstructure_results.json) over `data/v2_market/daily_bars.equity_only.csv` (`15,080` rows, `202` sessions `2026-01-02..2026-11-18`) and `bvmt-starter-kit/data/processed/bvmt_official_2026/daily_bars.canonical.csv` (read-only).

---

## 1. Universe Structure: Token IDs vs. Economic ISINs

- **Equity-Only Canonical File (`daily_bars.equity_only.csv`)**: `15,080` rows across **`76` `instrument_id` tokens**, representing **`75` distinct economic ISINs** (`42` Tunis Bourse Challenge-eligible ISINs, `33` non-Challenge BVMT ISINs).
- **Split-Identity Anomaly (`TN0005700018`)**: `POULINA_GROUP_HOLDING` (`68` rows, `2026-01-02..2026-04-08`) and `POULINA_GP_HOLDING` (`134` rows, `2026-04-10..2026-11-18`) represent the same Challenge security. Failure to join on `verified_isin` inflates Challenge token count to `43` (`33` non-Challenge = `76`) and artificially creates a `0%` trailing 20s/60s row for the retired token. All ISIN-grouped metrics below join `POULINA` cleanly (`42` Challenge vs `33` Non-Challenge = `75` ISINs).

---

## 2. Empirical Liquidity & Activity Across Horizons (`2026`, `60s`, `20s`)

### 2.1 Cross-Sectional Summary (ISIN-Joined: Challenge 42 vs. Non-Challenge 33)

| Horizon | Cohort (`n`) | Median Traded-Session Ratio | P25 / P75 Traded Ratio | Median Zero-Vol Day % | Mean Zero-Vol Day % | Median Daily Share Vol (Median / P25 / P75) | Median Daily Turnover TND (Median / P25 / P75) | Mean Daily Turnover TND (Median / Mean) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Full 2026** (`202`s: `01-02..11-18`) | **All Equities (`75`)** | `0.9604` | `0.8168` / `0.9950` | `3.48%` | `17.76%` | `2,268.5` / `209.0` / `8,014.0` | `17,519.63` / `2,480.63` / `86,631.40` | `49,737.59` / `142,569.80` |
| **Full 2026** | **Challenge (`42`)** | **`0.9901`** | `0.9653` / `0.9988` | **`0.99%`** | `2.53%` | **`3,734.5`** / `1,300.75` / `14,693.5` | **`61,982.18`** / `24,136.55` / `228,438.97` | `119,841.13` / `233,611.28` |
| **Full 2026** | **Non-Challenge (`33`)** | `0.7475` | `0.3317` / `0.8960` | **`24.88%`** | `37.13%` | `195.0` / `0.0` / `2,350.0` | **`915.00`** / `0.00` / `12,238.17` | `4,524.79` / `26,698.82` |
| **Trailing 60s** (`08-11..11-18`) | **All Equities (`75`)** | `0.9500` | `0.7167` / `1.0000` | `5.00%` | `20.16%` | `953.5` / `63.75` / `4,461.75` | `12,190.83` / `962.77` / `44,318.68` | `32,932.79` / `99,680.08` |
| **Trailing 60s** | **Challenge (`42`)** | `0.9833` | `0.9500` / `1.0000` | `0.84%` | `3.54%` | `2,001.0` / `934.88` / `7,400.0` | **`32,707.05`** / `12,281.74` / `139,357.62` | `74,941.11` / `165,340.51` |
| **Trailing 60s** | **Non-Challenge (`33`)** | `0.7000` | `0.2000` / `0.8833` | `30.00%` | `41.31%` | `52.5` / `0.0` / `945.5` | `330.79` / `0.00` / `2,580.50` | `2,772.39` / `16,112.26` |
| **Trailing 20s** (`10-22..11-18`) | **All Equities (`75`)** | `0.9500` | `0.7500` / `1.0000` | `5.00%` | `20.46%` | `1,067.5` / `52.75` / `4,407.25` | `8,874.00` / `1,108.88` / `54,295.38` | `24,933.96` / `117,011.67` |
| **Trailing 20s** | **Challenge (`42`)** | **`1.0000`** | `0.9500` / `1.0000` | **`0.00%`** | `3.58%` | **`2,264.25`** / `1,009.5` / `9,148.63` | **`29,726.06`** / `10,080.67` / `129,705.02` | `79,539.58` / `198,108.48` |
| **Trailing 20s** | **Non-Challenge (`33`)** | `0.7500` | `0.1500` / `0.9000` | `25.00%` | `41.95%` | `20.0` / `0.0` / `817.5` | **`458.10`** / `0.00` / `3,514.40` | `2,622.52` / `13,797.55` |

### 2.2 Three Structural Microstructure Regimes
1. **Two-Tier Market Split**: The Challenge 42 universe (*Continu* + 2 *Fixing* stocks `TUNIS_RE`, `WIFACK_INT_BANK`) has a full-year median turnover of **`61,982.18 TND/day`** — **`67.7x`** higher than the Non-Challenge 33 universe (`915.00 TND/day`, where over `25%` of stocks have zero median daily volume).
2. **Autumn Liquidity Contraction**: Even inside Challenge 42, median daily turnover fell by **more than half** from full 2026 (`61,982.18 TND`) to trailing 60s (`32,707.05 TND`) and trailing 20s (`29,726.06 TND`). Backtests calibrated on H1 2026 average volume overstate October–November execution capacity.
3. **Heavy Skew Between Mean & Median Turnover**: Challenge 42 trailing 20s **mean** turnover (`198,108 TND`) is **`6.66x`** its **median** (`29,726 TND`), driven by sporadic block/cross prints (e.g., `DELICE_HOLDING` Nov 13 `372,109` shares, `SFBT` 20s mean `1.87M` vs median `451k`). Using mean ADV for position sizing creates false capacity confidence.

---

## 3. 5,000 TND Position Capacity Audit (10% Weight on 50,000 TND, 10% ADV Budget)

Under a strict **10% ADV participation budget**, a **5,000 TND** target sleeve requires:
- **1-Session Fill (`0.10 × ADV >= 5,000 TND`)**: `ADV >= 50,000.00 TND`
- **3-Session Staged Fill (`3 × 0.10 × ADV >= 5,000 TND`)**: `ADV >= 16,666.67 TND`

| Window | Cohort (`n`) | 1-Session Pass (Median ADV) | 1-Session Pass (Mean ADV) | 3-Session Pass (Median ADV) | 3-Session Pass (Mean ADV) |
|---|---|---:|---:|---:|---:|
| **Full 2026** | Challenge (`42`) | **23 / 42** (`54.8%`) | 32 / 42 (`76.2%`) | **33 / 42** (`78.6%`) | 39 / 42 (`92.9%`) |
| **Trailing 60s** | Challenge (`42`) | **18 / 42** (`42.9%`) | 27 / 42 (`64.3%`) | **29 / 42** (`69.0%`) | 36 / 42 (`85.7%`) |
| **Trailing 20s** | Challenge (`42`) | **20 / 42** (`47.6%`) | 26 / 42 (`61.9%`) | **27 / 42** (`64.3%`) | 36 / 42 (`85.7%`) |
| **Trailing 20s** | Non-Challenge (`33`) | **1 / 33** (`3.0%`) | 3 / 33 (`9.1%`) | **4 / 33** (`12.1%`) | 7 / 33 (`21.2%`) |
| **Trailing 20s** | All BVMT (`75`) | **21 / 75** (`28.0%`) | 29 / 75 (`38.7%`) | **31 / 75** (`41.3%`) | 43 / 75 (`57.3%`) |

### Representative Challenge Bottlenecks (Trailing 20s Median Turnover)
- **Liquid Core (`>= 50,000 TND`, 20 stocks)**: `AMEN_BANK` (`584,008`), `BNA` (`462,688`), `SFBT` (`450,958`), `BIAT` (`407,051`), `ONE_TECH_HOLDING` (`264,354`), `SOTETEL` (`234,781`), `POULINA_GP_HOLDING` (`201,015`), `ATTIJARI_BANK` (`184,703`), `DELICE_HOLDING` (`182,711`), `BT` (`141,617`), ..., `UIB` (`50,985`).
- **3-Session Staged Tier (`16,667–49,999 TND`, 7 stocks)**: `STA` (`30,781`), `ATB` (`28,671`), `LAND_OR` (`25,674`), `SOTUMAG` (`24,639`), `EURO-CYCLES` (`21,552`), `SMART_TUNISIE` (`21,525`), `CITY_CARS` (`19,381`). *(Note: `EURO-CYCLES` 510 sh = 4,997 TND in the real portfolio actually exceeded 1-day 10% median ADV `2,155 TND` and took ~2.3x daily 10% budget.)*
- **Capacity-Blocked at 5,000 TND (`< 16,667 TND`, 15 stocks — `35.7%` of Challenge)**: `SPDIT_-_SICAF` (`15,437`), `ARTES` (`14,324`), `ASSU_MAGHREBIA_VIE` (`11,159`), `ICF` (`11,051`, zero-vol `30%`), `SIAME` (`9,757`), `TUNIS_RE` (`8,874`, Fixing), `SOTRAPIL` (`8,579`), `MPBS` (`8,102`), `WIFACK_INT_BANK` (`7,666`, Fixing), `ATELIER_MEUBLE_INT` (`7,631`), `ENNAKL_AUTOMOBILES` (`6,773`), `SOTIPAPIER` (`6,561`), `BH_BANK` (`5,278`), `NEW_BODY_LINE` (`2,678`), `ATTIJARI_LEASING` (`1,353`, zero-vol `40%`).

**Portfolio Design Implication**: A `10%` (`5,000 TND`) equal-weight sleeve size cannot be filled in 1 session across more than half of Challenge stocks (`22/42` fail 1s median ADV; `15/42` fail 3s median ADV). V2 must separate **signal score** from **liquidity-capped target slice** (`min(5,000 TND, 10% × 20s median ADV × staging_days)`).

---

## 4. Non-Equity Bond & Rights Contamination (`daily_bars.canonical.csv`)

Auditing `bvmt-starter-kit/data/processed/bvmt_official_2026/daily_bars.canonical.csv` against `data/v2_market/daily_bars.equity_only.csv`:
- **Total Legacy Canonical Rows**: `17,560` across `572` unique `instrument_id` tokens.
- **Equity Rows Kept in V2 (`ADR-001`)**: `15,080` (`76` token IDs / `75` ISINs).
- **Excluded Non-Equity Rows**: **`2,480` rows** across **`496` non-equity IDs** (`228` subscription/attribution rights matching `*_DA*` / `*_DS*`, `268` bond/debt instruments such as `AB0528_7.0_AP20`, `ABCB0627_11_5_P7-2`).
- **Injection Pattern**: All `496` non-equity IDs appeared exclusively across **5 consecutive sessions** (`2026-11-04`, `2026-11-05`, `2026-11-06`, `2026-11-09`, `2026-11-10`; `496` rows/day = `2,480` rows), with **`2,427 / 2,480` (`97.86%`) untraded / zero-volume** (`53` traded).
- **`rejected_rows.csv` Count**: `2` rows (`reason = unknown`).
