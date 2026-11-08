# BVMT Quantitative Model & Strategy Catalog

**Document Status**: Verified Milestone 4 Model Inventory  
**Code Implementation**: [`src/bvmt/features.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/features.py), [`src/bvmt/strategies.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/strategies.py), [`src/bvmt/execution.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/execution.py)  
**Shared Execution Rules**: T+1 Next-Open Fills, `0.50%` Buy / `0.50%` Sell Fee, `10.0%` Max Single-Stock Concentration Cap, `10.0%` Max Daily Volume Participation Cap, `0` Fills on Zero-Volume Bars.

---

## 1. Summary Inventory of Models & Baselines

| Model ID | Code Identifier | Name | Category | Status | Role in System |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Demo v0.1** | `demo-momentum-v0.1` | Synthetic 3-Bar Demo Momentum | Synthetic Fixture | **Implemented** | Offline CLI smoke test (`bvmt demo`); never used on real data |
| **Baseline A** | `baseline_a_cash` | Cash-Only Baseline (`0%` Exposure) | Naïve Benchmark | **Implemented** | Capital preservation floor (`50,000.000 TND` constant) |
| **Baseline B** | `baseline_b_equal_weight` | Equal-Weight Eligible Universe | Market Benchmark | **Implemented** | Broad BVMT Principal Market (`11`/`12`) beta benchmark |
| **Baseline C** | `baseline_c_buy_and_hold` | Buy-and-Hold Initial Top Basket | Passive Benchmark | **Implemented** | Tests passive buy-and-hold of initial liquid leaders after warmup |
| **Baseline D** | `baseline_d_momentum_20` | Simple 20-Session Momentum ($M_{20}$) | Single-Factor | **Implemented** | Pure short-term (1-month) price continuation baseline |
| **Baseline E** | `baseline_e_momentum_60` | Simple 60-Session Momentum ($M_{60}$) | Single-Factor | **Implemented** | Pure medium-term (3-month) trend continuation baseline |
| **Baseline F** | `baseline_f_relative_strength` | Cross-Sectional Relative-Strength Rank | Rank Composite | **Implemented** | Percentile rank blend of 20d and 60d returns |
| **Baseline G** | `baseline_g_liquidity_momentum` | T04 Liquidity-Filtered Vol-Adjusted Momentum | Production Baseline | **Implemented (Active)** | Current default engine for live dashboard recommendations |
| **Model H** | `model_h_multifactor_quality` | Downside-Vol, Drawdown, Consistency & Liquidity Multi-Factor | Enhanced Multi-Factor | **Implemented (Candidate)** | Penalizes downside tail risk, 60d drawdowns, and erratic price jumps |
| **Model I** | `model_i_regime_event_momentum` | Market-Regime-Filtered Quality Momentum + PIT Event Overlay | Regime + Event | **Implemented (Candidate)** | Scales gross exposure by market breadth & integrates verified disclosures |
| **ML Ranker** | `lgbm_walk_forward_v0` | Walk-Forward LightGBM Cross-Sectional Ranker | Machine Learning | **Gated / Blocked** | Blocked by pre-registered promotion gate (`194 < 250` sessions) |

---

## 2. Shared Eligibility Gate Pipeline

Every real-market model (`B` through `I`) applies a deterministic point-in-time eligibility filter before scoring or allocating capital on session $t$:

1. **Instrument Listing Gate (`unlisted_or_delisted`)**: Instrument must exist in the verified instrument master (`active == True`).
2. **Market Group Gate (`ineligible_market_segment`)**: Only Principal Market quotation groups (`11` and `12`) are eligible by default (`64` of `76` instruments). Fixing/secondary groups (`21`, `51`, `99`) are excluded.
3. **Minimum Session History Gate (`insufficient_session_history`)**: Requires at least $L_{\max} + 1 = 61$ historical exchange sessions up to $t$ (except Model D when evaluated stand-alone, though all comparative evaluations share the 60-session warm-up start for identical evaluation windows).
4. **Active Trading Gate (`suspended` / `missing_observation`)**: Instrument must have a valid bar on session $t$ with `status == "traded"`, `close > 0`, and `volume > 0`.
5. **Lookback Anchor Gate (`stale_quote` / `untraded_lookback_anchor`)**: Anchor bars at $t - 20$ and $t - 60$ must have valid positive closing prices.
6. **Minimum Liquidity Gate (`insufficient_liquidity`)**: 20-session Average Daily Traded Value ($\text{ADV}_{i,20}^{\text{TND}}$) must meet the configured minimum threshold (`5,000 TND` in `configs/research.json`).

---

## 3. Detailed Model Specifications

### 3.1 Baseline A: Cash-Only Baseline (`baseline_a_cash`)
- **Purpose**: Zero-risk capital preservation benchmark.
- **Mathematical Formula**:
  $$w_{i}(t) = 0 \quad \forall i, t \implies \text{Equity}(t) = \text{Cash}_0 = 50,000.000\text{ TND}$$
- **Inputs / Outputs**: Initial cash (`50,000 TND`); outputs zero orders, `0.00%` return, `0.00%` drawdown, `0` TND fees.
- **Failure Mode**: Loses purchasing power and competition rank during bull markets (`+7.47%` equal-weight market advance in 2026).

---

### 3.2 Baseline B: Equal-Weight Eligible Universe (`baseline_b_equal_weight`)
- **Purpose**: Measures the return of holding an equal-weighted basket of liquid Principal Market (`11`/`12`) stocks subject to competition concentration caps.
- **Mathematical Formula**:
  Let $\mathcal{E}(t)$ be the set of eligible liquid instruments on session $t$, ordered deterministically by highest $\text{ADV}_{i,20}^{\text{TND}}$ (top $K_{\max} = 11$ stocks so each weight satisfies $w_i \le 8.5\% < 10.0\%$, or equal weight across the eligible basket capped at $8.5\%$ per stock).
- **Rebalancing**: Rebalanced on the shared evaluation schedule (`every 10 sessions`) using T+1 next-open execution.
- **Failure Mode**: Allocates equally to deteriorating laggards and strong leaders; incurs turnover fees across many small positions.

---

### 3.3 Baseline C: Buy-and-Hold Initial Top Basket (`baseline_c_buy_and_hold`)
- **Purpose**: Passive benchmark testing whether buying the top liquid stocks once at the end of the 60-session warm-up (`session 61`) and holding to maturity beats active rotation after fees.
- **Mathematical Formula**:
  On first active rebalance session $t_0$: select top $K$ eligible stocks by liquidity/baseline rank with target weight $w_i(t_0) = 8.5\%$, execute at $t_0 + 1$ open, and set:
  $$\text{Orders}(t) = \emptyset \quad \forall t > t_0$$
- **Failure Mode**: Cannot exit stocks that suffer fundamental deterioration or prolonged drawdowns mid-year; subject to uninvested cash drag if initial T+1 open volume caps partially restrict initial fills.

---

### 3.4 Baseline D: Simple 20-Session Momentum (`baseline_d_momentum_20`)
- **Purpose**: Pure short-horizon price momentum without volatility normalization or multi-horizon confirmation.
- **Mathematical Formula**:
  $$S_i^{(D)}(t) = M_{i,20}(t) = \frac{P_i(t)}{P_i(t-20)} - 1$$
- **Selection Rule**: Select up to $K = 3$ eligible stocks with $S_i^{(D)}(t) > 0$, ranked descending by $S_i^{(D)}(t)$.
- **Failure Mode**: Chases short-term illiquid price spikes that mean-revert over the next 10–20 sessions, generating high turnover and fee drag.

---

### 3.5 Baseline E: Simple 60-Session Momentum (`baseline_e_momentum_60`)
- **Purpose**: Pure medium-horizon (quarterly) trend continuation without volatility scaling.
- **Mathematical Formula**:
  $$S_i^{(E)}(t) = M_{i,60}(t) = \frac{P_i(t)}{P_i(t-60)} - 1$$
- **Selection Rule**: Select up to $K = 3$ eligible stocks with $S_i^{(E)}(t) > 0$, ranked descending by $S_i^{(E)}(t)$.
- **Failure Mode**: Slow to react to sudden trend reversals; unscaled raw returns favor high-beta/high-volatility names.

---

### 3.6 Baseline F: Cross-Sectional Relative-Strength Ranking (`baseline_f_relative_strength`)
- **Purpose**: Non-parametric cross-sectional percentile rank combining 20-session and 60-session momentum, robust to extreme return outliers.
- **Mathematical Formula**:
  For $i \in \mathcal{E}(t)$:
  $$S_i^{(F)}(t) = 0.50 \cdot \text{PercentileRank}\big(M_{i,20}(t)\big) + 0.50 \cdot \text{PercentileRank}\big(M_{i,60}(t)\big)$$
  requiring $M_{i,20}(t) > 0$ or $M_{i,60}(t) > 0$.
- **Failure Mode**: Ignores return volatility and path smoothness—a stock that gained $+15\%$ via one gap-up bar and 19 flat bars ranks the same as a stock with steady daily institutional buying.

---

### 3.7 Baseline G: T04 Liquidity-Filtered Volatility-Adjusted Momentum (`baseline_g_liquidity_momentum`)
- **Purpose**: **Current Production Baseline** (`rank_session_baseline` in [`src/bvmt/features.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/src/bvmt/features.py)). Combines short- and medium-term momentum normalized by 20-session realized volatility.
- **Mathematical Formula**:
  $$M_{i,20}(t) = \frac{P_i(t)}{P_i(t-20)} - 1, \qquad M_{i,60}(t) = \frac{P_i(t)}{P_i(t-60)} - 1$$
  $$\sigma_{i,20}(t) = \sqrt{\frac{1}{19} \sum_{\tau=t-19}^{t} (r_{i,\tau} - \bar{r}_{i,20})^2}, \qquad \sigma^*_{i,20}(t) = \max\big(\sigma_{i,20}(t), 0.005\big)$$
  $$S_i^{(G)}(t) = 0.50 \cdot \frac{M_{i,20}(t)}{\sigma^*_{i,20}(t)} + 0.50 \cdot \frac{M_{i,60}(t)}{\sigma^*_{i,20}(t)}$$
- **Selection Rule**: Requires $S_i^{(G)}(t) > 0$, selects top $K = 3$ eligible stocks at `8.5%` target weight each (`25.5%` gross exposure under conservative 3-stock concentration, or configurable top-$K$).
- **Limitations Identified in Audit**:
  1. Uses total standard deviation $\sigma_{i,20}$, which penalizes upside breakout days equally with downside crash days.
  2. Does not explicitly penalize deep rolling 60-day drawdowns ($DD_{i,60}$) or reward liquidity depth beyond the hard `5,000 TND` gate.

---

### 3.8 Model H: Multi-Factor Downside-Risk, Drawdown, Consistency & Liquidity Model (`model_h_multifactor_quality`)
- **Purpose**: Addresses the specific weaknesses of Baseline G by replacing symmetric volatility with **downside semi-deviation**, rewarding **trend consistency**, penalizing **rolling 60-session drawdowns**, and tilting toward **deeper order-book liquidity**.
- **Mathematical Formula**:
  1. **Downside Semi-Deviation** over 20 sessions:
     $$\sigma^-_{i,20}(t) = \max\left(\sqrt{\frac{1}{20}\sum_{\tau=t-19}^{t} \min(0, r_{i,\tau})^2},\; 0.004\right)$$
  2. **Sortino-Adjusted Dual Momentum**:
     $$Z^{\text{mom}}_i(t) = \frac{0.45 \cdot M_{i,20}(t) + 0.55 \cdot M_{i,60}(t)}{\sigma^-_{i,20}(t)}$$
  3. **Trend Consistency Ratio** (fraction of non-negative return sessions in last 20 bars):
     $$C_{i,20}(t) = \frac{1}{20} \sum_{\tau=t-19}^{t} \mathbb{I}(r_{i,\tau} > 0)$$
  4. **Rolling 60-Session Max Drawdown Penalty**:
     $$DD_{i,60}(t) = \max_{t-60 \le u \le v \le t} \left(1 - \frac{P_i(v)}{P_i(u)}\right)$$
  5. **Cross-Sectional Liquidity Bonus**:
     $$L_{i,20}(t) = \text{PercentileRank}_{j \in \mathcal{E}(t)}\big(\ln(1 + \text{ADV}_{j,20}^{\text{TND}})\big)$$
  6. **Composite Score**:
     $$S_i^{(H)}(t) = Z^{\text{mom}}_i(t) \cdot \big(0.75 + 0.50 \cdot C_{i,20}(t)\big) \cdot \big(1 - 1.50 \cdot DD_{i,60}(t)\big) + 0.35 \cdot L_{i,20}(t)$$
     subject to strict trend confirmation: $M_{i,60}(t) > 0$, $M_{i,20}(t) > -0.01$, and $DD_{i,60}(t) \le 0.15$.
- **Turnover Hysteresis**: Retains an existing holding if it remains eligible and within the top $K_{\text{hold}} = 5$ ranks, preventing unnecessary round-trip fees on minor rank swaps.

---

### 3.9 Model I: Market-Regime-Filtered Quality Momentum + Point-in-Time Event Overlay (`model_i_regime_event_momentum`)
- **Purpose**: Extends Model H with a **cross-sectional market breadth regime filter** and a **point-in-time verified corporate disclosure overlay**.
- **Mathematical Formula**:
  1. **Market Breadth & Regime Indicator** $B_{\text{mkt}}(t)$:
     Let $B_{\text{mkt}}(t)$ be the fraction of eligible Group `11`/`12` instruments with positive 20-session momentum ($M_{j,20}(t) > 0$) and let $\tilde{M}_{\text{mkt},20}(t)$ be the cross-sectional median 20-session return:
     $$\text{Regime}(t) = \begin{cases} \text{BULL} & \text{if } B_{\text{mkt}}(t) \ge 0.50 \text{ and } \tilde{M}_{\text{mkt},20}(t) > 0 \\ \text{NEUTRAL} & \text{if } 0.35 \le B_{\text{mkt}}(t) < 0.50 \\ \text{DEFENSIVE} & \text{if } B_{\text{mkt}}(t) < 0.35 \end{cases}$$
  2. **Point-in-Time Disclosure Overlay** $\Delta^{\text{event}}_i(t)$:
     Reads verified point-in-time disclosures where `published_at <= decision_cutoff(t)`:
     - Verified positive dividend / earnings growth disclosure: $\Delta^{\text{event}}_i(t) = +0.25$
     - Verified regulatory warning / suspension / adverse tax shock: $\Delta^{\text{event}}_i(t) = -\infty$ (hard exclusion)
     - No verified event in window: $\Delta^{\text{event}}_i(t) = 0.0$
  3. **Composite Score**:
     $$S_i^{(I)}(t) = S_i^{(H)}(t) + \Delta^{\text{event}}_i(t)$$
  4. **Regime-Adaptive Target Slot Count**:
     Scales maximum active positions $K(t)$ dynamically: $K_{\text{BULL}} = 5$, $K_{\text{NEUTRAL}} = 3$, $K_{\text{DEFENSIVE}} = 1$ (preserving cash during broad BVMT pullbacks).

---

### 3.10 Gated ML Ranker: Walk-Forward LightGBM (`lgbm_walk_forward_v0`)
- **Status**: **Blocked by Pre-Registered Governance Gate (`session_count = 194 < 250`)**.
- **Governance Rule**: [`configs/research.json`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/configs/research.json) mandates `minimum_sessions_for_ml_promotion = 250`. Because the verified 2026 daily dataset contains `194` sessions, the engine explicitly blocks ML promotion and records the gate status in `artifacts/strategy_experiments_2026.json` and on the Strategy Lab UI.

