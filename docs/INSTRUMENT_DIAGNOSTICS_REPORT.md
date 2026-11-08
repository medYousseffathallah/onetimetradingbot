# BVMT Market Instruments Diagnostic Report (P0 Research Coverage Recovery)

**As-of Cutoff:** 2026-11-06T17:00:00+00:00 | **Total Exchange Sessions:** 194 | **Total Instruments Audited:** 76

## 1. Executive Summary & Root Cause Breakdown

- **Strategy Eligible (Candidates):** 40 instruments (52.6%)
- **Strategy Excluded:** 36 instruments (47.4%)
- **Instruments with Valid Historical Trades:** 76 / 76 (98.7%)
- **Instruments Showing 0.000 TND / 0.00% Placeholder in Legacy UI:** 36 instruments

### Root Cause Taxonomy for Strategy-Excluded Instruments

| Primary Root Cause | Count | Impacted Examples | Description |
| :--- | :--- | :--- | :--- |
| **OHLC Validation / Exchange Limit Reservation** | 12 | `BH_BANK`, `ATB`, `TUNIS_RE`, `CIL`, `SOTUMAG` | Official BVMT feed closes at ceiling/floor reservation (`indicateur: 'H'/'B'`) outside executed trade band, causing strict parser quarantine on 1–2 sessions. |
| **Restricted Market Segment** | 12 | `AETECH`, `ELECTROSTAR`, `MIP`, `SOPAT` | Listed in `surveillance` or `alternatif` segments. Legally restricted or excluded from competition main list, yet possess valid quotes. |
| **Lookback Anchor Untraded** | 7 | `TAWASOL_GP_HOLDING`, `SANIMED`, `SIMPAR` | Stock trades occasionally, but session exactly 20 or 60 open sessions ago had 0 volume, failing textbook anchor price check. |
| **Prolonged Untraded Staleness** | 4 | `BH_ASSURANCE`, `BH_LEASING`, `STE_TUNISIENNE_D_ENTREPRISES_DE_TELECOMMUNICATION` | 3+ consecutive `no_trade` sessions at decision cutoff. Latest trade was weeks or months prior. |
| **Strategy Liquidity Gate** | 1 | `ASTREE` | Trade frequency $< 60\%$ or 20-session median turnover $< 1,000$ TND despite recent trading. |

---

## 2. Targeted Regression Verification (User-Specified Examples)

| Symbol | Instrument ID | Market Segment | Latest Traded Price | Traded Sessions | Trade Freq (20s) | Strat Status | Primary Exclusion Reason | Safe Research Indicators |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AETECH** | `AETECH` | `surveillance` | 0.420 TND (2026-01-23) | 8/194 | 0.0% | **EXCLUDED** | `ineligible_market_segment` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |
| **ASTREE** | `ASTREE` | `principal_fixing` | 79.000 TND (2026-11-06) | 108/194 | 55.0% | **EXCLUDED** | `insufficient_liquidity` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |
| **ATB** | `ATB` | `principal_continu` | 3.400 TND (2026-11-06) | 190/194 | 100.0% | **EXCLUDED** | `missing_observation` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |
| **BH ASSURANCE** | `BH_ASSURANCE` | `principal_fixing` | 75.980 TND (2026-09-28) | 22/194 | 0.0% | **EXCLUDED** | `stale_quote` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |
| **BH BANK** | `BH_BANK` | `principal_continu` | 13.090 TND (2026-11-06) | 183/194 | 100.0% | **EXCLUDED** | `missing_observation` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |
| **NEW BODY LINE** | `NEW_BODY_LINE` | `principal_continu` | 2.450 TND (2026-11-06) | 177/194 | 95.0% | **ELIGIBLE** | `None` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |
| **POULINA GP HOLDING** | `POULINA_GP_HOLDING` | `principal_continu` | 26.600 TND (2026-11-06) | 126/194 | 105.0% | **ELIGIBLE** | `None` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |
| **POULINA GROUP HOLDING** | `POULINA_GROUP_HOLDING` | `principal_continu` | 24.120 TND (2026-04-08) | 67/194 | 0.0% | **EXCLUDED** | `missing_observation` | last_verified_traded_price, last_traded_session_date, quote_age_sessions, observed_trade_return_pct |

---

## 3. Comprehensive 76-Instrument Audit Matrix

| Symbol | ISIN | Segment | Traded / Total | Latest Trade | Quote Age | Obs Return | 20s Trade Freq | Strategy Status | Exclusion Diagnostic | Research Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| AETECH | `TN0007500010` | `surveillance` | 8 / 194 | 0.420 TND | 178s | -2.33% | 0% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `SPARSE_DATA` |
| AIR LIQUIDE TSIE | `TN0002300358` | `surveillance` | 159 / 194 | 225.000 TND | 0s | +1.81% | 60% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| ALKIMIA | `TN0003800703` | `surveillance` | 32 / 194 | 13.400 TND | 28s | -0.67% | 0% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| AMEN BANK | `TN0003400058` | `principal_continu` | 194 / 194 | 92.300 TND | 0s | -0.05% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ARTES | `TN0007300015` | `principal_continu` | 191 / 194 | 9.990 TND | 0s | -0.10% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ASSAD | `TN0007140015` | `surveillance` | 162 / 194 | 2.570 TND | 0s | +3.21% | 90% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| ASSUR MAGHREBIA | `TN0007830011` | `principal_continu` | 175 / 194 | 79.990 TND | 0s | -0.01% | 95% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ASSU MAGHREBIA VIE | `TNDKJ8O68X14` | `principal_continu` | 194 / 194 | 12.670 TND | 0s | -0.08% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ASTREE | `TN0003000452` | `principal_fixing` | 108 / 194 | 79.000 TND | 0s | -1.25% | 55% | **EXCLUDED** | `STRATEGY_LIQUIDITY_GATE` | `SPARSE_DATA` |
| ATB | `TN0003600350` | `principal_continu` | 190 / 194 | 3.400 TND | 0s | +1.49% | 100% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| ATELIER MEUBLE INT | `TN0007740012` | `principal_continu` | 192 / 194 | 5.940 TND | 0s | -0.17% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ATL | `TN0004700100` | `principal_continu` | 194 / 194 | 14.520 TND | 0s | -1.16% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ATTIJARI BANK | `TN0001600154` | `principal_continu` | 194 / 194 | 77.030 TND | 0s | -0.61% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ATTIJARI LEASING | `TN0006610018` | `principal_continu` | 159 / 194 | 40.000 TND | 1s | -2.42% | 40% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| BEST LEASE | `TN0007580012` | `principal_fixing` | 149 / 194 | 2.460 TND | 0s | -0.40% | 100% | **EXCLUDED** | `LOOKBACK_ANCHOR_UNTRADED` | `SPARSE_DATA` |
| BH ASSURANCE | `TN0006550016` | `principal_fixing` | 22 / 194 | 75.980 TND | 28s | -4.49% | 0% | **EXCLUDED** | `PROLONGED_UNTRADED_STALENESS` | `SPARSE_DATA` |
| BH BANK | `TN0001900604` | `principal_continu` | 183 / 194 | 13.090 TND | 0s | -3.04% | 100% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| BH LEASING | `TN0006720049` | `principal_fixing` | 135 / 194 | 4.650 TND | 3s | +1.31% | 60% | **EXCLUDED** | `PROLONGED_UNTRADED_STALENESS` | `SPARSE_DATA` |
| BIAT | `TN0001800457` | `principal_continu` | 194 / 194 | 164.510 TND | 0s | +0.13% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| BNA | `TN0003100609` | `principal_continu` | 194 / 194 | 19.270 TND | 0s | +0.42% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| BNA ASSURANCES | `TN0007680010` | `principal_continu` | 194 / 194 | 3.990 TND | 0s | +1.01% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| BT | `TN0002200053` | `principal_continu` | 194 / 194 | 8.600 TND | 0s | -0.35% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| BTE (ADP) | `TN0001300557` | `principal_fixing` | 161 / 194 | 5.600 TND | 0s | +5.66% | 95% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| CARTHAGE CEMENT | `TN0007400013` | `principal_continu` | 194 / 194 | 1.780 TND | 0s | +0.00% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| CELLCOM | `TN0007590011` | `principal_continu` | 182 / 194 | 1.430 TND | 0s | +0.00% | 85% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| CIL | `TN0004200853` | `principal_continu` | 193 / 194 | 39.200 TND | 0s | +0.51% | 105% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| CIMENTS DE BIZERTE | `TN0007350010` | `principal_fixing` | 129 / 194 | 0.760 TND | 7s | -3.80% | 30% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| CITY CARS | `TN0007550015` | `principal_continu` | 192 / 194 | 20.240 TND | 0s | +5.97% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| DELICE HOLDING | `TN0007670011` | `principal_continu` | 194 / 194 | 19.100 TND | 0s | +1.17% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ENNAKL AUTOMOBILES | `TN0007410012` | `principal_continu` | 193 / 194 | 17.480 TND | 0s | +1.33% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| ESSOUKNA | `TN0007210016` | `principal_continu` | 189 / 194 | 4.640 TND | 0s | -0.22% | 95% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| EURO-CYCLES | `TN0007570013` | `principal_continu` | 193 / 194 | 10.180 TND | 0s | +0.79% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| HANNIBAL LEASE | `TN0007310139` | `principal_fixing` | 143 / 194 | 10.450 TND | 0s | +0.10% | 50% | **EXCLUDED** | `LOOKBACK_ANCHOR_UNTRADED` | `SPARSE_DATA` |
| ICF | `TN0003200755` | `principal_continu` | 181 / 194 | 134.200 TND | 0s | -0.21% | 75% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| LAND OR | `TN0007510019` | `principal_continu` | 191 / 194 | 14.950 TND | 0s | +0.34% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| MAGASIN GENERAL | `TN0006440010` | `principal_fixing` | 112 / 194 | 12.360 TND | 1s | +0.00% | 55% | **EXCLUDED** | `LOOKBACK_ANCHOR_UNTRADED` | `SPARSE_DATA` |
| MONOPRIX | `TN0001000108` | `principal_fixing` | 176 / 194 | 12.290 TND | 0s | -1.68% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| MPBS | `TN0007620016` | `principal_continu` | 188 / 194 | 10.650 TND | 0s | +0.57% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| NEW BODY LINE | `TN0007540016` | `principal_continu` | 177 / 194 | 2.450 TND | 0s | +0.00% | 95% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| OFFICEPLAST | `TN0007700016` | `principal_continu` | 192 / 194 | 1.220 TND | 0s | +0.00% | 105% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| ONE TECH HOLDING | `TN0007530017` | `principal_continu` | 194 / 194 | 10.730 TND | 0s | +0.37% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| PLAC. TSIE-SICAF | `TN0002500650` | `principal_fixing` | 11 / 194 | 38.820 TND | 25s | +0.28% | 0% | **EXCLUDED** | `PROLONGED_UNTRADED_STALENESS` | `SPARSE_DATA` |
| POULINA GP HOLDING | `TN0005700018` | `principal_continu` | 126 / 194 | 26.600 TND | 0s | +3.30% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| POULINA GROUP HOLDING | `TN0005700018` | `principal_continu` | 67 / 194 | 24.120 TND | 126s | +4.64% | 0% | **EXCLUDED** | `TICKER_RENAMED_SPLIT` | `PARTIAL_HISTORY` |
| SAH | `TN0007610017` | `principal_continu` | 193 / 194 | 12.380 TND | 0s | -0.48% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SANIMED | `TN0007730013` | `surveillance` | 107 / 194 | 0.370 TND | 3s | +0.00% | 65% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| SFBT | `TN0001100254` | `principal_continu` | 194 / 194 | 13.630 TND | 0s | +0.22% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SIAME | `TN0006590012` | `principal_continu` | 188 / 194 | 3.340 TND | 0s | +0.30% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SIMPAR | `TN0004000055` | `principal_fixing` | 22 / 194 | 35.500 TND | 10s | +0.00% | 5% | **EXCLUDED** | `PROLONGED_UNTRADED_STALENESS` | `SPARSE_DATA` |
| SIPHAT | `TN0006670012` | `surveillance` | 65 / 194 | 3.400 TND | 1s | -4.23% | 10% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| SITS | `TN0007180011` | `principal_fixing` | 39 / 194 | 3.600 TND | 0s | -4.26% | 30% | **EXCLUDED** | `LOOKBACK_ANCHOR_UNTRADED` | `SPARSE_DATA` |
| SMART TUNISIE | `TNQPQXRODTH8` | `principal_continu` | 193 / 194 | 31.990 TND | 0s | -0.03% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SOMOCER | `TN0006780019` | `surveillance` | 163 / 194 | 0.680 TND | 0s | +0.00% | 90% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| SOTEMAIL | `TN0007600018` | `surveillance` | 5 / 194 | 1.440 TND | 30s | -30.77% | 0% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `SPARSE_DATA` |
| SOTETEL | `TN0006530018` | `principal_continu` | 191 / 194 | 22.120 TND | 0s | -2.56% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SOTIPAPIER | `TN0007630015` | `principal_continu` | 184 / 194 | 2.520 TND | 0s | +0.80% | 90% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SOTRAPIL | `TN0006660013` | `principal_continu` | 192 / 194 | 25.700 TND | 0s | -0.39% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SOTUMAG | `TN0006580013` | `principal_continu` | 183 / 194 | 21.000 TND | 0s | +0.00% | 100% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| SOTUVER | `TN0006560015` | `principal_continu` | 184 / 194 | 23.240 TND | 0s | -1.32% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| SPDIT - SICAF | `TN0001400704` | `principal_continu` | 187 / 194 | 16.000 TND | 0s | -0.62% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| STA | `TNNGTFLC2986` | `principal_continu` | 188 / 194 | 115.900 TND | 0s | +0.00% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| STAR | `TN0006060016` | `principal_continu` | 191 / 194 | 89.000 TND | 0s | -0.78% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| STB | `TN0002600955` | `principal_continu` | 193 / 194 | 4.900 TND | 0s | +3.59% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| STIP | `TN0005030010` | `surveillance` | 81 / 194 | 7.950 TND | 6s | +0.00% | 35% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| TAWASOL GP HOLDING | `TN0007650013` | `surveillance` | 169 / 194 | 0.750 TND | 0s | -1.32% | 85% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| TELNET HOLDING | `TN0007440019` | `principal_continu` | 193 / 194 | 12.200 TND | 0s | +0.58% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| TPR | `TN0007270010` | `principal_continu` | 194 / 194 | 12.140 TND | 0s | -0.90% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| TUNINVEST-SICAR | `TN0004100202` | `principal_fixing` | 172 / 194 | 43.890 TND | 0s | +4.50% | 75% | **EXCLUDED** | `LOOKBACK_ANCHOR_UNTRADED` | `SPARSE_DATA` |
| TUNISAIR | `TN0001200401` | `surveillance` | 173 / 194 | 0.310 TND | 0s | -3.12% | 85% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| TUNISIE LEASING F | `TN0002100907` | `principal_continu` | 187 / 194 | 36.400 TND | 0s | +0.33% | 95% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| TUNIS RE | `TN0007380017` | `principal_fixing` | 176 / 194 | 8.900 TND | 0s | -3.16% | 80% | **EXCLUDED** | `OHLC_VALIDATION_OR_DATA_GAP` | `PARTIAL_HISTORY` |
| UADH | `TN0007690019` | `surveillance` | 40 / 194 | 0.420 TND | 138s | +0.00% | 0% | **EXCLUDED** | `MARKET_SEGMENT_RESTRICTION` | `FULL_COVERAGE` |
| UBCI | `TN0002400505` | `principal_fixing` | 140 / 194 | 39.000 TND | 1s | +0.00% | 85% | **EXCLUDED** | `LOOKBACK_ANCHOR_UNTRADED` | `SPARSE_DATA` |
| UIB | `TN0003900107` | `principal_continu` | 188 / 194 | 36.390 TND | 0s | +0.55% | 100% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| UNIMED | `TN0007720014` | `principal_continu` | 193 / 194 | 8.500 TND | 0s | -0.93% | 105% | **ELIGIBLE** | `NONE_ELIGIBLE` | `FULL_COVERAGE` |
| WIFACK INT BANK | `TN0007200017` | `principal_fixing` | 157 / 194 | 6.810 TND | 0s | +0.15% | 100% | **EXCLUDED** | `LOOKBACK_ANCHOR_UNTRADED` | `SPARSE_DATA` |