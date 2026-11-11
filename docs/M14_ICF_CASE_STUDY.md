# Milestone 14 — `ICF` Forensic Case Study & Anti-Hindsight Peer Analysis (`Task G2`)

- **Author**: Gemini Quantitative Research Mission (Google Antigravity IDE; reproducible read-only audit against `bvmt-starter-kit` @ `6f0b64d`)
- **Security Audited**: `ICF` (`SOCIETE DES INDUSTRIES CHIMIQUES DU FLUOR`, ISIN `TN0003200755`, Challenge Symbol `ICF`, `Continu`, `CHIMIE`)
- **Prior Baseline Reference Reviewed**: `docs/ICF_MISSED_OPPORTUNITY_AUTOPSY.md` (independently reproduced and extended here across both `<= 2026-11-06` `194`-session and `<= 2026-11-10` `196`-session snapshots).

---

## 1. Executive Verdict: Why `ICF` Was Missed — Without Hindsight Bias

Our independent audit **confirms** that `ICF`'s `2026-09-22` status `"B"` data quarantine (`rejections.json#688`) caused a 60-session `missing_observation` cliff in production baseline rankings from `2026-09-22` onward — **including Nov 06 and Nov 10**.

However, rigorous counterfactual testing refutes the naive hypothesis that restoring the `2026-09-22` bar alone would have surfaced `ICF` before its `2026-11-09..11-10` bounce (`134.200 -> 143.500 TND`, **`+6.93%`**):

1. **Counterfactual `2026-09-22` Recovery Still Fails Production & Sparse Models on `2026-11-06`**: Even if `2026-09-22` (`open=high=143.600`, `close=135.070`, `vol=2445`, `turnover=336304.930` recovered — or actual raw `vol=31`, `turnover=4451.6`) is injected cleanly under **both** `CF_A` (`143.600`) and `CF_B` (`135.070`), `ICF` on `2026-11-06` is **still excluded** by baseline (`insufficient_liquidity`, trailing 20s median turnover **`1,364.090 TND < 5,000 TND`**) and **still unselected** by `sparse_research_v1` (`quantitative_score = -50.0`, `mom5 = -0.59%`, `mom20 = -2.68%`, `mom60 = -10.53%`, `awakening = 0.15x`).
2. **Post-Rally Awakening Was Real — and Blocked by Non-Challenge Top-8 Leakage**: On **`2026-11-09`** (`close=135.900`, `vol=3,192`, `turnover=420,885.550 TND`), `awakening_ratio` jumped to **`308.55x`** (`quant_score = -42.2234`). On **`2026-11-10`** (`open=135.890`, `high=143.500`, `close=143.500`, `vol=3,473`, `turnover=488,106.220 TND`), `quant_score` flipped positive (`+10.0201`, `awakening = 357.83x`), yet `sparse_research_v1` STILL rejected `ICF` with `"Below candidate_top_k=8 cap"` while reserving **3 of its 8 slots for non-challenge stocks (`MONOPRIX`, `ESSOUKNA`, `CIL`)**.
3. **Not Predictably Undervalued in Available Local Data**: Prior to Nov 09, local price-only indicators showed declining 20s/60s momentum (`155.000` on `2026-07-08` down to `130.510` intraday low on `2026-11-05` and `2`-share print on `2026-11-06`) and dried-up order flow (`1,364.090 TND` median 20s turnover), with **zero** local CMF H1/Q3 financial disclosures or catalyst text chunks to verify fundamental value ex-ante.

---

## 2. Independent Reproduction of Historical Trajectory & `2026-09-22` Quarantine

### 2.1 Bar Completeness & Price Range (`2026-01-02 .. 2026-11-10`)
- **Total open BVMT sessions**: `196` (`2026-01-02 .. 2026-11-10`).
- **`ICF` canonical bars present**: `195` (`183` traded sessions, `12` zero-volume canonical sessions).
- **Single missing open session**: **`2026-09-22`** (confirmed missing in `daily_bars.canonical.csv`).
- **Price extremes (canonical closes)**:
  - **2026 H1 minimum close**: **`77.000 TND`** on `2026-02-06`.
  - **2026 H1 maximum close**: **`151.900 TND`** on `2026-06-23` (**`+97.27%`** trough-to-peak H1 move).
  - **Full-sample peak close**: **`155.000 TND`** on `2026-07-08` (**`+101.30%`** vs `77.000` H1 low).

### 2.2 Forensics of `2026-09-22` Status `"B"` Record & Raw Rejections (`bvmt_official_2026/rejections.json`)
- Raw rejections for `ICF` fall into two categories:
  1. **Ingestion deduplication (`10` duplicate keys)** on `2026-07-10`, `07-24`, `08-03`, `08-05` (`3x`), `08-06`, `08-17`, `09-01`, `10-07`.
  2. **OHLC bounds quarantine (`rejections.json#688`) on `2026-09-22`**:
     - Raw JSON payload: `dateSeance="2026-09-22"`, `indicateur="B"` (*Baisse* / downward reservation band), `coursReference=143.690`, `coursOuvert=143.600`, `plusHaut=143.600`, `plusBas=143.600`, `cloture=135.070` (`varJour="-6.00"`), `echanges=1`, `quantites=31`, `capitaux=4451.600`, `vwap=143.600`.
     - Because raw `plusBas=143.6 > cloture=135.07`, canonical ingestion rejected the row (`OHLC bounds are inconsistent`), leaving a 1-session hole after `2026-09-21` (`close=143.690, vol=102, turnover=14461.180`).
     - In production `features.py:248-257`, `len(bars_60s) < 60` (`59 < 60`) immediately imposed a binary **`missing_observation`** exclusion for the next ~3 months!
     - `hb_recovery_meta_for_icf` confirms `sparse_research.extract_limit_reserved_bars_from_rejections` recovers `low=135.07, high=143.6, volume=31, turnover=4451.6` with provenance `"rejections.json#688"`.

---

## 3. Exact `ICF` Timeline Across Models (`2026-03-30 .. 2026-11-10`)

Observed directly via `scripts/m14_quant_audit.py` (`g2_icf_forensic.timeline`):

| Session | Last Close (TND) | Med Turn 20s (TND) | `mom5` / `mom20` / `mom60` (%) | Baseline Rank / Exclusion | Sparse v1 Status | Sparse Quant Score | Awakening Ratio | Sparse v1 Selected? & Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`2026-03-30`** | `93.000` | `97,114.48` | `+6.96` / `+15.53` / `+8.78` | Eligible **Rank 17** (`comp=5.3687`) | `FULL` | `+25.04` | `4.10x` (`False`) | No (`Below candidate_top_k=8 cap`) |
| **`2026-06-15`** | `117.500` | `592,309.93` | `+12.98` / `+33.60` / `+48.73` | Eligible **Rank 7** (`comp=14.4691`) | `FULL` | `+65.14` | `2.76x` (`False`) | **YES** (`risk_adjusted_trend`) |
| **`2026-09-21`** | `143.690` | `33,174.72` | `-4.13` / `-4.84` / `+56.18` | Eligible **Rank 1** (`comp=18.3867`) | `FULL` | `+72.66` | `0.39x` (`False`) | **YES** (`risk_adjusted_trend`) |
| **`2026-09-22`** | `143.690` | `34,981.64` | `None` / `None` / `None` | **EXCLUDED** (`missing_observation`) | `PARTIAL` | `-4.65` | `None` (`False`) | No |
| **`2026-10-09`** | `137.890` | `18,637.50` | `+0.14` / `-6.51` / `+1.01` | **EXCLUDED** (`missing_observation`) | `PARTIAL` | `-5.27` | `0.44x` (`False`) | No |
| **`2026-11-06`** | `134.200` | `1,364.09` | `-0.59` / `-2.68` / `-10.53` | **EXCLUDED** (`missing_observation`) | `PARTIAL` | `-50.00` | `0.15x` (`False`) | No |
| **`2026-11-09`** | `135.900` | `1,364.09` | `None` / `-1.44` / `-10.59` | **EXCLUDED** (`missing_observation`) | `PARTIAL` | `-42.22` | **`308.55x` (`True`)** | No (`Below candidate_top_k=8 cap`) |
| **`2026-11-10`** | `143.500` | `1,364.09` | `+6.71` / `+4.82` / `-3.67` | **EXCLUDED** (`missing_observation`) | `PARTIAL` | `+10.02` | **`357.83x` (`True`)** | No (`Below candidate_top_k=8 cap` — non-challenge top-8 evicted `ICF`) |

### Late-October / Early-November Order-Book Sequence (Observed Canonical Bars)
- `2026-10-28`: untraded (`vol=0`, close `135.970`)
- `2026-10-29`: traded (`open=133.970, close=135.870, vol=1,433, turnover=192,113.780`)
- `2026-10-30`: traded (`open=131.900, close=134.990, vol=1,320, turnover=174,154.170`)
- `2026-11-02`: untraded (`vol=0`, close `134.990`)
- `2026-11-03`: traded (`open=131.930, close=134.480, vol=142, turnover=18,775.730`)
- `2026-11-04`: untraded (`vol=0`, close `134.480`)
- `2026-11-05`: traded (`open=130.580, close=134.480, vol=137, turnover=18,314.520`)
- `2026-11-06`: traded **`2` shares** (`open=134.250, low=134.200, close=134.200, turnover=268.450`) -> explains `0.15x` awakening on Nov 06!
- `2026-11-09`: breakout bar (`open=133.900, high=135.900, low=131.000, close=135.900, vol=3,192, turnover=420,885.550`)
- `2026-11-10`: expansion bar (`open=135.890, high=143.500, low=135.890, close=143.500, vol=3,473, turnover=488,106.220`)

---

## 4. Counterfactual (`2026-09-22`) & Execution Feasibility Simulations

### 4.1 Counterfactual Fix Test on `2026-11-06`
Injecting `2026-09-22` under both `CF_A` (`close=143.600`) and `CF_B` (`close=135.070`, `vol=2445`, `turnover=336304.930`):
- **Production Baseline (`5,000 TND` threshold)**: `baseline_eligible = False`, `baseline_exclusions = ["insufficient_liquidity"]` under BOTH counterfactuals.
- **`sparse_research_v1`**: `sparse_status = PARTIAL_RESEARCH_AVAILABLE`, `sparse_quant_score = -50.0`, `sparse_selected = False` under BOTH counterfactuals.
- **Finding**: Removing the 1-day `missing_observation` cliff fixes **eligibility attribution**, NOT `ICF`'s Nov 06 ranking — because before `2026-11-09`, `ICF`'s recent trailing trend and 20s median turnover (`1,364.090 TND`) were genuinely weak.

### 4.2 Feasible Next-Open Fill & Participation Capacity (`4,250 TND` = `8.5%` Portfolio Budget, `10%` Vol Cap, `+20 bps` Slippage, `50 bps` Fee)

| Fill Date | Bar OHLC (`O / H / L / C`) | Session Volume (`Turnover TND`) | 10% Vol Cap (Shares) | Target Shares (`4,250 TND`) | Simulated Filled Shares | Simulated Fill Price (`+20 bps`) | Simulated Fee (`50 bps`) | Execution Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `2026-03-31` | `94.70 / 94.70 / 89.51 / 91.27` | `1,694` (`153,136.93`) | `169` | `44` | `0` *(limit/price band rejection check)* | `None` | `0.000` | `assumed_price_outside_observed_bar` *(+20bps above open `94.70 = 94.889 > high 94.70`)* |
| `2026-07-06` | `156.00 / 156.00 / 149.98 / 154.99` | `2,632` (`401,672.75`) | `263` | `27` | `0` | `None` | `0.000` | `assumed_price_outside_observed_bar` *(open == high ceiling `156.00`)* |
| `2026-10-12` | `136.90 / 136.90 / 136.90 / 136.90` | `16` (`2,190.40`) | `1` | `31` | `0` | `None` | `0.000` | Illiquid (`1`-share 10% cap, flat bar) |
| **`2026-11-09`** | `133.90 / 135.90 / 131.00 / 135.90` | `3,192` (`420,885.55`) | `319` | `31` | **`31`** | **`134.167800`** | **`20.796`** | Executable if triggered intraday/pre-open on breakout |
| **`2026-11-10`** | `135.89 / 143.50 / 135.89 / 143.50` | `3,473` (`488,106.22`) | `347` | `31` | **`31`** | **`136.161780`** | **`21.105`** | Executable at Nov 10 open (post Nov-09 awakening) |

---

## 5. Anti-Hindsight Peer Cohort Analysis

### 5.1 All 10 Challenge Securities Excluded by Baseline on `2026-11-06` (`194`s -> `196`s Outcomes)
Had a hypothetical naive rule blindly bought **every** Challenge stock excluded by baseline on `2026-11-06`, what happened from Nov 06 close to Nov 10 close?

| Sym | Exclusion Reason (`Nov 06`) | Close `11-06` | Close `11-10` | `11-06 -> 11-10` Ret | `10-20 -> 11-06` Ret | Sparse Quant `11-06` | Awakening `11-06` | Med Turn `20`s (`TND`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`ATB`** | `missing_observation` | `3.400` | `3.680` | **`+8.24%`** | `0.00%` | `-10.50` | `6.22x` | `23,342.81` |
| **`ICF`** | `missing_observation` | `134.200` | `143.500` | **`+6.93%`** | `-1.83%` | `-50.00` | `0.15x` | `1,364.09` |
| **`STPAP`** | `insufficient_liquidity` | `2.520` | `2.600` | **`+3.17%`** | `+2.86%` | `+5.64` | `22.67x` | `1,860.70` |
| **`SPDIT`** | `insufficient_liquidity` | `16.000` | `16.200` | `+1.25%` | `-3.03%` | `-2.49` | `12.67x` | `1,344.03` |
| **`TJL`** | `missing_observation` | `40.000` | `40.190` | `+0.48%` | `-4.76%` | `-8.50` | `None` | `0.00` |
| **`MGR`** | `missing_observation` | `21.000` | `21.000` | `0.00%` | `+0.05%` | `+70.44` | `0.87x` | `41,815.96` |
| **`TRE`** | `missing_observation` | `8.900` | `8.860` | `-0.45%` | `-2.20%` | `-6.93` | `0.52x` | `2,866.50` |
| **`WIFAK`** | `untraded_lookback_anchor` | `6.810` | `6.750` | `-0.88%` | `-14.88%` | `-4.25` | `0.01x` | `8,009.15` |
| **`NBL`** | `insufficient_liquidity` | `2.450` | `2.400` | `-2.04%` | `-12.50%` | `-50.00` | `1.26x` | `2,361.54` |
| **`BH`** | `missing_observation` | `13.090` | `12.770` | **`-2.44%`** | `-2.75%` | `-11.21` | `14.82x` | `4,909.88` |

### 5.2 Out-of-Sample Volume Awakening Cohort (`13` Walk-Forward Dates, `196`s)
Across all `82` `volume_awakening` flags (`75` traded next-open entries) in the full BVMT universe (`49` inside the 42-stock Challenge universe):
- **All 75 traded awakenings (`H=10` next-open -> close)**: `mean = +3.27%`, `median = +1.11%`, `positive rate = 57.33%`.
- **Challenge 49 traded awakenings (`H=10`)**: `29 / 49` positive (**`59.18%` hit rate**), `mean = +3.42%`, with `20 / 49` negative/flat (`40.82%`), including severe reversals (`SIAME -12.36%`, `CITY_CARS -8.14%`, `NEW_BODY_LINE -7.80%`, `LAND_OR -7.39%`, `ATELIER_MEUBLE_INT -6.25%`, `SOTUMAG -5.72%`, **`ICF` on `2026-08-24` `-5.45%`**).
- **Walk-forward `ICF` cohort inside `sparse_generalization.py` (`H=10`, 13 folds)**: **`selected = 5 / 13`, `precision = 20.0%` (`false_positive_rate = 80.0%`), `liquidity_feasibility_rate = 40.0%`**.

**Scientific Conclusion**: `ICF` is a genuine **operational visibility & universe-isolation victim** (`missing_observation` cliff + non-challenge top-8 slot displacement on Nov 10), **not** evidence that every dormant or volume-awakened stock is an automatic winning trade. Treating `volume_awakening` or `missing_observation` alone as a buy signal produces an ~`41%–60%` false-positive rate and negative drawdowns (`-5.45%` to `-12.36%`) in OOS folds.
