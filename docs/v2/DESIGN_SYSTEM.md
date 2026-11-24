# BVMT Trading Intelligence V2 — Institutional Design System

**Status**: Gate 1 UX Specification (`V2-UX1`)  
**Aesthetic Direction**: Calm, Light-First Institutional Research Terminal  
**Strict Prohibitions**: Zero neon/cyberpunk gradients, zero glowing box shadows, zero fake `LIVE` badges, zero raw LLM model IDs in default views.

---

## 1. Color Palette & Surface Tokens

```css
:root {
  /* Surfaces */
  --bg-canvas: #F8F9FA;         /* Warm-neutral institutional canvas */
  --bg-surface: #FFFFFF;        /* Primary card & table surface */
  --bg-subtle: #F1F5F9;         /* Secondary panels, table headers, muted wells */
  --bg-hover: #F8FAFC;          /* Subtle row hover */

  /* Hairline Borders */
  --border-hairline: #E2E8F0;   /* Standard 1px card/table separator */
  --border-strong: #CBD5E1;     /* Focused inputs, active segmented controls */

  /* Typography */
  --text-primary: #0F172A;      /* Primary headings & key figures */
  --text-secondary: #334155;    /* Body prose & table labels */
  --text-muted: #64748B;        /* Eyebrows, timestamps, units, captions */
  --text-unavailable: #94A3B8;  /* Missing/null values */

  /* Brand & Interactive Accent */
  --accent-primary: #0F766E;    /* Forest Teal — primary CTA & active nav */
  --accent-hover: #115E59;      /* Forest Teal dark hover */
  --accent-tint: #F0FDFA;       /* Soft teal background tint */
  --accent-border: #99F6E4;     /* Soft teal border */

  /* Semantic Status Colors (Restrained Institutional Tones) */
  --pos-text: #065F46;   --pos-bg: #ECFDF5;   --pos-border: #A7F3D0;
  --warn-text: #92400E;  --warn-bg: #FFFBEB;  --warn-border: #FDE68A;
  --neg-text: #991B1B;   --neg-bg: #FEF2F2;   --neg-border: #FECACA;
  --info-text: #1E40AF;  --info-bg: #EFF6FF;  --info-border: #BFDBFE;
  --sim-text: #5B21B6;   --sim-bg: #F5F3FF;   --sim-border: #DDD6FE;
  --neut-text: #475569;  --neut-bg: #F1F5F9;  --neut-border: #CBD5E1;
}
```

---

## 2. Typography & Numeric Precision

- **Sans-Serif UI Font**: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Monospace / Financial Font**: `'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace`
- **Mandatory `tabular-nums`**: All financial values, quantities, percentages, dates, and rank counters MUST declare:
  ```css
  font-variant-numeric: tabular-nums;
  ```
- **Precision Standards**:
  - Tunisian Dinars (`TND`): Always 3 decimal places (`10.160 TND`, `50,093.190 TND`, `+235.680 TND`).
  - Percentages (`PCT`): Always 2 decimal places (`+3.69%`, `10.29%`, `-16.65%`) with explicit `+` / `-` sign on deltas.
  - Share counts (`SHARES`): Integer with thousand separator (`510`, `14,258`).
- **Type Scale**:
  - Page Title (`h1`): `22px` / `600` weight / `-0.02em` tracking (`#0F172A`)
  - Section Title (`h2`): `15px` / `600` weight (`#0F172A`)
  - Eyebrow / Table Header: `11px` / `600` weight / uppercase / `0.05em` tracking (`#64748B`)
  - Body / Table Cell: `13.5px–14px` / `400–500` weight (`#334155`)
  - KPI Hero Metric: `24px–26px` / `600` weight / `tabular-nums` (`#0F172A`)
  - Footnote / Provenance Meta: `12px` / `400` weight (`#64748B`)

---

## 3. Mandatory 5-State Provenance Badge Semantics (`ADR-002`)

Every numeric figure or panel must carry an explicit `ValueStatus` pill (`11px`, uppercase, `600` weight, `4px` radius, `1px` border):

| `ValueStatus` | Visual Style | Exact Meaning | Mandatory UI Rule |
|---|---|---|---|
| `OBSERVED` | `--pos-bg` `#ECFDF5` / `--pos-text` `#065F46` / `--pos-border` `#A7F3D0` | Directly recorded in canonical CSV or confirmed DOM snapshot | Must accompany `session_date` or `captured_at` timestamp |
| `CALCULATED` | `--info-bg` `#EFF6FF` / `--info-text` `#1E40AF` / `--info-border` `#BFDBFE` | Deterministic arithmetic over observed inputs (e.g., EOD mark-to-market, 20s return, weight %) | Hover/caption states formula inputs |
| `SIMULATED` | `--sim-bg` `#F5F3FF` / `--sim-text` `#5B21B6` / `--sim-border` `#DDD6FE` | Walk-forward backtest, forward paper journal, or dry-run trade scenario | **NEVER** styled like realized account profit; separated into distinct lanes |
| `UNVERIFIED` | `--warn-bg` `#FFFBEB` / `--warn-text` `#92400E` / `--warn-border` `#FDE68A` | User screenshot, conflicting/newer unconfirmed capture, unverified rules, or unimported orders | Must include warning note explaining what verification is missing |
| `UNAVAILABLE` | `--neut-bg` `#F1F5F9` / `--neut-text` `#475569` / `--neut-border` `#CBD5E1` | Missing data (`current_executable_quote_tnd`, `fundamentals`, `published_at`) | Value renders as `Unavailable` / `—` with `missing_reason`; **never zero** |

---

## 4. Decision & Execution Status Badge Semantics (`ADR-004`)

### 4.1 Position Monitoring States (`PositionDecision.monitoring_state`)
- `HOLD`: `--pos-bg` / `--pos-text` / `--pos-border` — Existing position within concentration/liquidity limits with no deterioration trigger.
- `REVIEW`: `--warn-bg` / `--warn-text` / `--warn-border` — Requires human inspection (e.g., snapshot conflict, weight near/over 10% cap, mixed technical horizon).
- `CONSIDER_TRIM`: `--warn-bg` / `--warn-text` / `--warn-border` (with amber left accent) — Weight breaches 10% cap or partial de-risking is indicated by risk rules.
- `CONSIDER_EXIT`: `--neg-bg` / `--neg-text` / `--neg-border` — Exit conditions or sustained trend/event invalidation triggered.
- `INSUFFICIENT_DATA`: `--neut-bg` / `--neut-text` / `--neut-border` — Coverage or reconciliation gaps prevent monitoring verdict.

### 4.2 Execution Gate States (`PositionDecision.execution_state`) — ALWAYS SEPARATE PILL
- `EXECUTION_BLOCKED`: `--neg-bg` `#FEF2F2` / `--neg-text` `#991B1B` / `--neg-border` `#FECACA` — Deterministic blockers prevent manual planning clearance (`rules_unverified`, `quote_unavailable`, `snapshot_conflict`).
- `ELIGIBLE_MANUAL_ONLY`: `--accent-tint` `#F0FDFA` / `--accent-primary` `#0F766E` / `--accent-border` `#99F6E4` — All deterministic gates passed; human may copy parameters into the external competition portal manually. **Still zero auto-execution.**

### 4.3 Stock Assessment States (`StockAssessment.state`)
- `RESEARCH_CANDIDATE`: `--accent-tint` / `--accent-primary`
- `WATCH`: `--info-bg` / `--info-text`
- `NO_CURRENT_EDGE`: `--neut-bg` / `--neut-text`
- `INSUFFICIENT_EVIDENCE`: `--neut-bg` / `--neut-text`
- `RESTRICTED`: `--neg-bg` / `--neg-text` (e.g., non-Challenge security viewed in Challenge scope)
- `HELD_POSITION_REVIEW`: `--warn-bg` / `--warn-text`

---

## 5. Component Patterns & Responsive Layout Grid

- **Desktop Shell (`1440px`)**:
  - Fixed left sidebar (`240px`) on `#FFFFFF` with `#E2E8F0` right hairline.
  - Main workspace (`flex: 1`, `max-width: 1200px` inner container, `24px–28px` padding).
  - Top Global Context Bar (`56px` height) with Mode badge, Dataset Cutoff (`2026-11-18 EOD`), Account Truth indicator, and Mobile Nav toggle.
- **Mobile Shell (`390px`)**:
  - Left sidebar collapses into a toggleable top-bar drawer (`<details>` or lightweight JS drawer); zero horizontal overflow (`overflow-x: hidden` never hides data—content actually wraps/stacks!).
  - Multi-column KPI grids collapse to `1 column` (or `2 columns` for compact 2-up pairs with >= 140px card width).
  - Dense data tables transform below `768px` into **stacked border-separated mobile record cards** (`data-label` key-value rows) OR stay cleanly wrapped within `390px` so `document.documentElement.scrollWidth <= window.innerWidth` is strictly satisfied on every page.
- **Spacing & Radius**:
  - Card radius: `8px`; Pill/badge radius: `4px`; Input/button radius: `6px`.
  - Card padding: `16px` (`mobile`) / `20px` (`desktop`).
  - Minimum touch target height on interactive controls: `40px–44px` on mobile.
