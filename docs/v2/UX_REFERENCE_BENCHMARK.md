# BVMT Trading Intelligence V2 — Conceptual UX Reference Benchmark

**Status**: Gate 1 UX Specification (`V2-UX1`)  
**Policy**: Strictly conceptual workflow and information-ergonomics analysis. **Zero proprietary CSS, icons, typography assets, color palettes, or branding are copied from any external product.**

---

## 1. Benchmark Rationale

V1 dashboards failed investors in two ways: they either presented raw developer tables with mixed truth states, or buried critical blockers (unverified competition rules, missing fundamentals, stale EOD closes) inside dense prose. To build a **calm, high-trust institutional decision terminal**, BVMT V2 benchmarks four complementary workflow archetypes conceptually:

| Benchmark Archetype | Core Strength Benchmarked | Specific BVMT V2 Problem Solved |
|---|---|---|
| **Koyfin** | High-density scannable financial tables, aligned `tabular-nums`, explicit unit headers, clean multi-period comparison | Solves misaligned numbers, ambiguous `%` vs `TND` units, and noisy KPI cards in Portfolio & Attribution |
| **TIKR** | Structured single-issuer multi-panel research (persistent security header + tabbed evidence layers + side-by-side diagnostics) | Solves Stock Research fragmentation; maps cleanly to V2's 10-layer `StockAssessment` (`L1–L10`) without modal fatigue |
| **TradingView** | Price/volume chart legibility, clean session-axis hierarchy, uncluttered workspace rail, effortless horizon switching | Solves EOD bar inspection (gap/untraded session visibility) and fast `1_2..20_60` horizon switching |
| **Linear** | Restrained typography, `1px` hairline structural clarity, keyboard-calm hierarchy, crisp semantic pills, progressive disclosure | Solves visual overload, fake urgency/neon clutter, and distinguishes monitoring states from execution blockers |

---

## 2. Conceptual Pattern Breakdown

### 2.1 Koyfin — Financial Density & Numeric Precision
- **What works conceptually**:
  - Numbers are right-aligned in `tabular-nums` monospace or tabular sans so decimal points stack vertically down a column.
  - Units (`TND`, `%`, `SHARES`, `SESSIONS`, `BPS`) live in column headers or subtle muted suffixes—not repeated inside every cell in bold.
  - Summary KPI strips separate **headline metric**, **period delta**, and **reference basis** onto three quiet typographic levels.
- **How BVMT V2 adapts it**:
  - Every `TND` column uses exact 3-decimal alignment (`10.160`, `5,181.600`, `+184.240`) from backend `Decimal` strings (`ADR-002`).
  - Provenance pills (`OBSERVED`, `CALCULATED`, `SIMULATED`, `UNVERIFIED`, `UNAVAILABLE`) attach cleanly to KPI headers and table column groups so dense numbers never lose their epistemological footing.
  - Attribution tables place **Realized**, **Unrealized**, **Fees**, and **Unexplained Residual (`+235.680 TND`)** in balanced columns with zero visual hand-waving.

### 2.2 TIKR — Institutional Stock Research Structure
- **What works conceptually**:
  - Selecting an equity opens a **persistent issuer identity band** (Company Name, Ticker/ID, ISIN, Market Mode, Benchmark Scope) above modular research tabs/panels.
  - Missing financial statement sections are shown as explicit empty/unavailable slots rather than omitted silently, preserving analyst muscle memory.
- **How BVMT V2 adapts it**:
  - Destination 4 (`Stock Research Workspace`) anchors a persistent `Instrument` identity header (`EURO-CYCLES · TN0007570013 · Challenge Continu`) above the **L1–L9 Evidence Panels** (`Technical`, `Liquidity`, `Fundamental [UNAVAILABLE]`, `Events`, `Regime`, `Contradictions`, `Provenance Register`).
  - Rather than hiding missing Tunisian corporate filings, `L3 Fundamentals` stays visibly present in the grid with an explicit `UNAVAILABLE · ABSENT_NO_FILINGS` state, ensuring the user never assumes "no red flags" means "fundamentals verified."

### 2.3 TradingView — Price/Volume Clarity & Workspace Navigation
- **What works conceptually**:
  - A quiet left rail + compact top context bar maximizes horizontal canvas for charts and tables.
  - Price and volume sit in a unified vertical stack with shared session dates, clear gridlines, and crisp high/low/close callouts.
  - Timeframe/horizon selectors use clean segmented pills (`1-2s`, `3-5s`, `5-10s`, `10-20s`, `20-60s`) with instant state feedback.
- **How BVMT V2 adapts it**:
  - EOD candlestick/line-and-volume SVG charts plot **observed sessions only**, visibly breaking lines or marking `untraded` zero-volume bars (e.g., `STA` on `2026-11-13` and `2026-11-16`) so sparse BVMT liquidity is immediately legible.
  - Every chart carries an explicit `EOD SESSION CLOSE — NOT AN EXECUTABLE QUOTE` caption, eliminating V1's false real-time impression.

### 2.4 Linear — Typographic Calm, Hairlines & Progressive Disclosure
- **What works conceptually**:
  - Light canvas (`#F8F9FA`) paired with pure white cards (`#FFFFFF`) and `1px solid #E2E8F0` hairlines eliminates heavy drop shadows and visual fatigue.
  - Status pills use muted, high-contrast pastel surfaces (`#ECFDF5` / `#065F46`, `#FFFBEB` / `#92400E`, `#FEF2F2` / `#991B1B`) instead of saturated neon fills.
  - Complex diagnostics sit behind calm progressive disclosure (`Summary` -> `Evidence Drawer` -> `Raw Provenance Register`) so first-glance scanning stays effortless.
- **How BVMT V2 adapts it**:
  - Monitoring status (`HOLD`, `REVIEW`, `CONSIDER_TRIM`, `CONSIDER_EXIT`, `INSUFFICIENT_DATA`) and execution gate (`EXECUTION_BLOCKED`, `ELIGIBLE_MANUAL_ONLY`) are rendered as **adjacent, non-overlapping pills** separated by a subtle hairline divider.
  - Desktop (`1440px`) uses a crisp `240px` left rail + `1200px` structured workspace; mobile (`390px`) collapses cleanly into a single-column stack with responsive cards and zero horizontal scrolling.

---

## 3. Anti-Patterns Explicitly Rejected in V2

1. **No Retail Gamification**: No confetti, rocket icons, leaderboard hype, or "43% target" banners.
2. **No Cyberpunk/Dark-Neon Terminal Aesthetics**: No glowing cyan/magenta gradients, scanlines, or fake pulsing `LIVE` indicators.
3. **No Conflated Truth Cards**: Never mix confirmed ledger equity (`49,993.430 TND`), newer unapplied DOM snapshot (`50,093.190 TND`), and EOD mark estimates (`50,355.830 TND`) into one unattributed hero number.
4. **No Silent Imputation**: Never render `0.000 TND` or `0%` when a field is `UNAVAILABLE` or `UNVERIFIED`.
5. **No Composite Magic Scores**: Never collapse `L1–L10` evidence into a single opaque `87/100` score that hides liquidity traps or missing fundamentals.
