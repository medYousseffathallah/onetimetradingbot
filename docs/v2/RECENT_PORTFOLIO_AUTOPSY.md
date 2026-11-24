# Recent Portfolio Autopsy (2026-11-06 through 2026-11-18)

**Provenance Notice**: All numeric figures below come directly from [r1_portfolio_autopsy.py](../../research/experiments-v2/r1_portfolio_autopsy.py) and its immutable JSON output [r1_autopsy_results.json](../../research/experiments-v2/r1_autopsy_results.json), executed over read-only competition snapshots, `real_competition_ledger.json`, and V2 equity-only canonical bars (`15,080` rows, `76` token IDs / `75` unique ISINs, `202` sessions `2026-01-02..2026-11-18`).  
**Status Tags**: `OBSERVED` (confirmed DOM capture / official BVMT EOD bar), `CALCULATED` (deterministic arithmetic from observed data), `SIMULATED` (counterfactual benchmark), `UNVERIFIED_CANDIDATE` (inferred pending `display_histo.aspx`), `UNVERIFIED_USER_SCREENSHOT` (user-supplied screenshot not backed by DOM JSON), `UNAVAILABLE` (absent from local archive).

---

## 1. Chronological Snapshot Reconstruction (11 Captures + Opening State)

| # | Source / File | Capture UTC | Status | Equity (TND) | Available Cash (TND) | Holdings MV (TND) | Cash Drag % | Holdings | Rank / Participants |
|---:|---|---|---|---|---|---|---|---|---|
| 0 | `SNAP-TBC-USER-001` (`real_account_snapshot.json`) | `null` (pre-Nov 7) | `OBSERVED` (screenshot init) | 49,998.050 | 49,608.050 | 390.000 | **99.22%** | 1 (`BH_BANK` 30) | 4,813 / 14,530 |
| 1 | `sync_20261107_122006.json` | `2026-11-07T12:20:06Z` | `OBSERVED` | 50,000.75 | 49,608.05 | 392.700 | **99.21%** | 1 (`BH_BANK` 30) | 118 / 14,530 |
| 2 | `sync_20261109_091300.json` | `2026-11-09T09:13:00Z` | `OBSERVED` | 49,979.07 | 44,586.07 | 5,393.000 | **89.21%** | 2 (`+DELICE_HOLDING` 263) | 133 / 14,547 |
| 3 | `sync_20261109_120109.json` | `2026-11-09T12:01:09Z` | `CORRUPTED_DOM` | 50,000.000 | 36,939.520 | 13,060.480 | **73.88%** | 5 (shifted as `VENDRE`) | 14,450 / 14,572 |
| 4 | `sync_20261109_120310.json` | `2026-11-09T12:03:10Z` | `CORRUPTED_DOM` | 50,000.000 | 36,939.520 | 13,060.480 | **73.88%** | 5 (shifted as `VENDRE`) | 98 / 14,573 |
| 5 | `sync_20261109_120411.json` | `2026-11-09T12:04:11Z` | `CORRUPTED_DOM` | 50,000.000 | 36,939.520 | 13,060.480 | **73.88%** | 5 (shifted as `VENDRE`) | 98 / 14,573 |
| 6 | `sync_20261109_144000.json` | `2026-11-09T14:40:00Z` | `OBSERVED` | 50,061.960 | 41,622.790 | 8,439.170 | **83.14%** | 4 (`BH`, `DH`, `NBL`, `STA`) | 112 / 14,573 |
| 7 | `sync_20261110_092042.json` | `2026-11-10T09:20:42Z` | `OBSERVED` | 50,006.570 | 39,628.870 | 10,377.700 | **79.25%** | 5 (`+SMART_TUNISIE` 62) | 118 / 14,429 |
| 8 | `sync_20261110_092129.json` | `2026-11-10T09:21:29Z` | `OBSERVED` | 50,006.570 | 39,628.870 | 10,377.700 | **79.25%** | 5 | 118 / 14,429 |
| 9 | `sync_20261110_110400.json` | `2026-11-10T11:04:00Z` | `OBSERVED` | 49,993.430 | 38,752.350 | 11,241.080 | **77.51%** | 6 (`+UIB` 24) | 14,258 / 14,430 |
| 10 | `sync_20261110_110702.json` | `2026-11-10T11:07:02Z` | `OBSERVED` | 49,993.430 | 38,752.350 | 11,241.080 | **77.51%** | 6 | 14,258 / 14,430 |
| 11 | `sync_20261112_093526.json` (`ext_1794476128406`) | `2026-11-12T09:35:26Z` | `OBSERVED` | 50,093.190 | 29,574.190 | 20,519.000 | **59.04%** | 8 (`+ECYCL` 510, `+MPBS` 400) | 81 / 14,450 |
| — | `UNVERIFIED_USER_SCREENSHOT` | Post-Nov 12 (date unverified) | `UNVERIFIED_USER_SCREENSHOT` | 50,647.64 | Unreported | Unreported | Unreported | 9 (`+AMEN_BANK` 45 sh) | 111 / 14,541 |

> [!CAUTION]
> **Active Ledger Discrepancy (`real_competition_ledger.json`)**: Even though `real_competition_ledger.json` recorded `ext_1794476128406` (`2026-11-12T09:35:26.734Z`, 8 holdings, cash `29,574.190` TND, total `50,093.190` TND) at `snapshot_history[10]` / `EVT-00020..21`, a stale Nov 10 capture (`browser_sync_20261110_110702`, 6 holdings, cash `38,752.350` TND, total `49,993.430` TND) was subsequently re-applied at `snapshot_history[11]` / `EVT-00022..23`. Because V1 lacked a monotonic `capture_timestamp` ingestion guard, the active ledger reverted to Nov 10 (`updated_at = 2026-11-10T11:07:02.522000+00:00`), erasing `EURO-CYCLES` (510 sh) and `MPBS` (400 sh) and distorting available cash by **+9,178.160 TND**.

---

## 2. DOM Column-Shift Corruption (`sync_20261109_120109..120411`)

In all three midday captures on `2026-11-09` (`12:01:09`, `12:03:10`, `12:04:11` UTC), the Chrome extension DOM scraper shifted `displayp.aspx` table columns right/left around the action button (`VENDRE`):
- `symbol` / `displayed_identifier` captured `"VENDRE"`.
- `quantity` captured the portal's internal integer ID (`223375`, `223493`, `223529`, `223514`, `223516`).
- `acquisition_price_tnd` captured the true share count (`30`, `263`, `35`, `200`, `22`).
- `latest_price_tnd` captured the true average acquisition price (`13.065`, `19.095`, `131.756`, `2.462`, `115.575`).
- `market_value_tnd` captured the true acquisition cost (`391.950`, `5,021.990`, `4,611.440`, `492.450`, `2,542.650`).
- `acquisition_amount_tnd` became `portal_id × actual_qty` (e.g. `223,375 × 30 = 6,701,250.000`), inflating aggregate unrealized loss to **`-122,910,515.520 TND`** (`EVT-00011` / `EVT-00013` in `real_competition_ledger.json`).

---

## 3. Nov 9 Intraday Round-Trip Audit (`Portal ID 223529`)

Decoding row 3 of the midday Nov 9 DOM capture (`portal_id = 223529`) and reconciling cash balances (`09:13 -> 12:04 -> 14:40` UTC):
- **Midday Entry**: `35` shares acquired at `131.756` TND displayed average cost (`4,611.440` TND DOM shifted amount; `4,611.450` TND cash-reconciled outlay: `44,586.070 - 36,939.520 - 492.450 - 2,542.650 = 4,611.450` TND). Implied gross purchase price (assuming 0.50% fee): **`131.100 TND`**.
- **Afternoon Liquidation (before `14:40:00Z`)**: Net cash proceeds = `41,622.790 - 36,939.520` = **`4,683.270 TND`** (`implied gross sell price = 134.480 TND`).
- **Realized Net Profit**: **`+71.820 TND`** (cash-reconciled; `+71.830` vs DOM shifted amount).
- **Candidate Identification (`UNVERIFIED_CANDIDATE`)**: Scanning all 76 equities in `daily_bars.equity_only.csv` across `2026-11-06` and `2026-11-09` for prices in `[130, 136]` TND yields **only one matching security: `ICF`** (`2026-11-06`: `O=134.250, L=134.200, C=134.200, V=2`; `2026-11-09`: `O=133.900, L=131.000, H=135.900, C=135.900, V=3,192`). Both implied gross prices (`131.100` and `134.480`) lie strictly inside `ICF`'s Nov 9 intraday range (`131.000..135.900`). However, per V2 governance, `ICF` remains strictly **`UNVERIFIED_CANDIDATE`** until `display_histo.aspx` is imported.
- **Ex-Post Opportunity Cost (if `223529 == ICF`)**: Closing `ICF` at `134.480` on Nov 9 locked in `+71.820` TND (`+1.56%`), whereas `ICF` subsequently closed at `143.500` (Nov 10), `146.990` (Nov 11), `144.790` (Nov 12), and `145.800` (Nov 18), where 35 shares net of 0.50% exit fee would have netted `5,077.485 TND` (**`+466.035 TND`** net, an opportunity cost of `~394.22 TND`).

---

## 4. Cash Drag & EOD Mark-to-Market Trajectories (`2026-11-12` to `2026-11-18`)

### 4.1 Cash Drag Progression
Account capital sat overwhelmingly idle across every verified snapshot: **99.21%** cash on Nov 7 -> **89.21%** (Nov 9 `09:13`) -> **73.88%** (Nov 9 `12:04`) -> **83.14%** (Nov 9 `14:40`) -> **79.25%** (Nov 10 `09:21`) -> **77.51%** (Nov 10 `11:07`) -> **59.04%** (Nov 12 `09:35`). Even at peak confirmed deployment (`40.96%` invested on Nov 12), nearly 60% of the bankroll earned 0%, capping portfolio beta during the Nov 12–18 market rebound. Moreover, three positions were micro-sized (`BH_BANK` `0.77%`, `NEW_BODY_LINE` `0.95%`, `UIB` `1.76%`), contributing negligible dollar alpha while incurring fixed decision attention.

### 4.2 Confirmed 8 Holdings (`ext_1794476128406`) EOD MTM Through `2026-11-18`

| Instrument | Qty | Cost Basis (TND) | Nov 12 Snap | Nov 12 EOD Close | Nov 12 EOD PnL | Nov 18 EOD Close | Nov 18 EOD MV | Nov 18 EOD PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `BH_BANK` | 30 | 391.950 | 12.910 | 12.650 | -12.450 | 12.480 | 374.400 | -17.550 (-4.48%) |
| `DELICE_HOLDING` | 263 | 5,021.990 | 19.000 | 18.800 | -77.590 | 19.480 | 5,123.240 | +101.250 (+2.02%) |
| `EURO-CYCLES` | 510 | 4,997.360 | 9.850 | 9.990 | +97.540 | 10.160 | 5,181.600 | +184.240 (+3.69%) |
| `MPBS` | 400 | 4,180.800 | 10.600 | 10.670 | +87.200 | 10.690 | 4,276.000 | +95.200 (+2.28%) |
| `NEW_BODY_LINE` | 200 | 492.450 | 2.370 | 2.360 | -20.450 | 2.390 | 478.000 | -14.450 (-2.93%) |
| `SMART_TUNISIE` | 62 | 1,993.920 | 32.000 | 31.990 | -10.540 | 31.700 | 1,965.400 | -28.520 (-1.43%) |
| `STA` | 22 | 2,542.650 | 115.000 | 115.000 | -12.650 | 114.500 | 2,519.000 | -23.650 (-0.93%) |
| `UIB` | 24 | 876.520 | 36.800 | 36.100 | -10.120 | 36.000 | 864.000 | -12.520 (-1.43%) |
| **8 Holdings Sum** | — | **20,497.640** | — | — | **+40.940** | — | **20,781.640** | **+284.000** |

Holding those 8 positions statically with `29,574.190` TND cash produces:
- **2026-11-12 EOD**: `50,112.770 TND` (`+0.2255%` MTM / `+0.0202%` liquidated net of 0.50% sell fee)
- **2026-11-13 EOD**: `50,328.120 TND` (`+0.6562%` MTM / `+0.4487%` liquidated)
- **2026-11-16 EOD**: `50,308.040 TND` (`+0.6161%` MTM / `+0.4087%` liquidated)
- **2026-11-17 EOD**: `50,351.820 TND` (`+0.7036%` MTM / `+0.4959%` liquidated)
- **2026-11-18 EOD**: `50,355.830 TND` (`+0.7117%` MTM / `+0.5038%` liquidated)

In contrast, the corrupted/stale active ledger (`browser_sync_20261110_110702`, 6 holdings + `38,752.350` cash) tracks statically to only **`50,076.390 TND` (`+0.1528%`)** on Nov 18 EOD — understating confirmed static equity by **279.440 TND** because it omits `EURO-CYCLES` (`+184.240`) and `MPBS` (`+95.200`).

### 4.3 `UNVERIFIED_USER_SCREENSHOT` Reconciliation Gap
The user-supplied screenshot (`UNVERIFIED_USER_SCREENSHOT`) reports **`50,647.64 TND`** (**`+1.30%`** displayed / `+1.2953%` calculated, rank **`111 / 14,541`**, `9` holdings including **`AMEN_BANK` 45 sh**; note `AMEN_BANK` closed at `92.750` on Nov 12 and `93.000` on Nov 13–18 -> `4,173.75–4,185.00 TND`).
- Reported Total Account Gain (`50,647.64 - 50,000.00`): **`+647.64 TND`**
- Reported Sum of Open Unrealized Gains: **`+411.96 TND`**
- **Unexplained Realized / Fee / Valuation Gap**: `647.64 - 411.96` = **`+235.68 TND`**. Of this, **`+71.82 TND`** is already accounted for by the Nov 9 intraday round-trip (`portal ID 223529`), leaving **`+163.86 TND`** unexplained without `display_histo.aspx` (likely uncaptured realized gains/losses, partial trims, or portal mark-to-market differences between Nov 12 and the screenshot date).

---

## 5. Counterfactual Benchmark Comparison (Identical Windows)

> **TUNINDEX**: **`UNAVAILABLE`** (no point-in-time TUNINDEX daily series CSV exists in the local archive).

| Portfolio / Benchmark | Window `Nov 7 – Nov 12` (vs 50k) | Window `Nov 7 – Nov 18` (vs 50k) | Notes & Cost Basis |
|---|---:|---:|---|
| **Cash Baseline** | `0.0000%` | `0.0000%` | Zero market exposure |
| **Actual Confirmed Account** (`ext_1794476128406` / Static EOD MTM) | **`+0.1864%`** (Nov 12 morning snap)<br>**`+0.2255%`** (Nov 12 EOD MTM)<br>(`+0.0202%` liquidated) | **`+0.7117%`** (Nov 18 EOD MTM)<br>(`+0.5038%` liquidated) | Confirmed 8 holdings through Nov 18; no trades assumed after Nov 12 |
| **`UNVERIFIED_USER_SCREENSHOT`** | — | **`+1.2953%`** (`+1.30%` displayed) | `50,647.64` TND, rank `111 / 14,541`, 9 holdings incl. `AMEN_BANK` 45 sh |
| **Equal-Weight Challenge (42 equities, Nov 6 EOD gross)** | `+0.1260%` (median `-0.1164%`) | **`+1.1185%`** (median `+0.0885%`) | Clean ISIN-deduplicated; zero friction |
| **Equal-Weight Challenge (42 equities, Nov 9 Open net)** | `-0.9939%` (median `-1.1162%`) | **`-0.0130%`** (median `-0.7667%`) | `0.50%` buy + `0.50%` sell fees (1.00% round-trip drag) |
| **Equal-Weight Full BVMT (75 ISINs, Nov 6 EOD gross)** | `-0.1287%` (median `0.0000%`) | `+0.8831%` (median `0.0000%`) | Clean ISIN-deduplicated; zero friction |
| **Equal-Weight Full BVMT (75 ISINs, Nov 9 Open net)** | `-1.0853%` (median `-0.9950%`) | `-0.0791%` (median `-0.9950%`) | `0.50%` buy + `0.50%` sell fees |
| **Simple 20s Momentum (Challenge Top-5, `>=5k` TND liq, Nov 9 Open)** | `-0.1651%` MTM / `-0.3542%` liq | `+0.4612%` MTM / `+0.2690%` liq | Picks: `CITY_CARS`, `TELNET_HOLDING`, `MPBS`, `STA`, `ONE_TECH_HOLDING` (`31,009.65` cash left due to 10% vol cap on `MPBS` & `STA`) |
| **Simple 20s Momentum (Full Top-5, `>=5k` TND liq, Nov 9 Open)** | `+0.2059%` MTM / `+0.0561%` liq | `+0.7500%` MTM / `+0.5974%` liq | Picks include non-Challenge `MONOPRIX` & `ESSOUKNA` (ineligible in Challenge) |
| **Buy & Hold Nov 7 Initial** (`BH_BANK` 30 + cash) | `-0.0249%` (`49,987.55` TND) | `-0.0351%` (`49,982.45` TND) | `99.2%` cash drag + `BH_BANK` decline (`13.09 -> 12.48`) |
| **Buy & Hold Nov 9 14:40** (4 holdings + cash) | `-0.1026%` (`49,948.69` TND) | `+0.2349%` (`50,117.43` TND) | `83.1%` cash drag; misses Nov 10–12 adds (`ECYCL`, `MPBS`) |

### Key Conclusions from the Window Audit
1. **Outperformance vs. Net Equal-Weight, Underperformance vs. Gross Equal-Weight**: Over the 8-session `Nov 7–Nov 18` window, the confirmed static portfolio (`+0.7117%` MTM / `+0.5038%` liquidated) beat **Equal-Weight Challenge Net** (`-0.0130%`), **Simple Challenge 20s Momentum** (`+0.4612%` MTM / `+0.2690%` liq), and **Cash** (`0.00%`), because avoiding indiscriminate turnover across 42 stocks saved `~1.00%` in round-trip friction and adding `EURO-CYCLES` (`+3.69%`) & `MPBS` (`+2.28%`) captured positive momentum.
2. **However, Cash Drag & Micro-Sizing Capped Upside**: Holding `59.04%`–`99.21%` cash meant even the confirmed portfolio captured less than two-thirds of gross Challenge EW (`+1.1185%`), while `BH_BANK` (`30 sh`, `-4.48%`) and `NEW_BODY_LINE` (`200 sh`, `-2.93%`) were noise-sized drags.
3. **Legacy M14 Context (Longer 2026 Horizon)**: In `M14_CORRECTED_STRATEGY_RESULTS.md` (`196` sessions through `2026-11-10`), legacy **Model G** returned **`18.5995%`** (corrected Challenge, vs `19.4244%` original), but sat **`74.83%`** idle in cash (`25.17%` utilization), had a **7.29 pp** cadence-20 phase IQR (`2.42%` to `17.39%`), and dropped to **`8.0331%`** (Challenge) / **`6.3468%`** (Full BVMT) when excluding a single outlier (`SOTETEL`). Meanwhile `STRATEGY_COMPARISON.md` showed `sparse_research_v1` achieved `18.645%` vs `Baseline` `16.2927%` at `H=10` (driven by sparse risers) while **underperforming** Baseline at `H=20` (`12.98%` vs `16.77%`), with `60.58%` false-positive rate. Neither legacy model earned promotion.
