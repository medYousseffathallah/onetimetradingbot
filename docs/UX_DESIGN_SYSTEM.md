# BVMT Trading Intelligence — UX Design System & Human-Centered Specification

**Milestone**: 9 — Human-Centered Product Redesign  
**Audience**: Frontend Engineers, Designers, Traders  
**Guiding Philosophy**: Calm, Minimal, Professional Fintech SaaS. Replace dense technical dashboards with intuitive answers to human investment questions.

---

## 1. Core Human Questions & Information Architecture

Every screen in the application is designed to answer a specific, natural investor question:

| Navigation Item | Route | Human Question Answered | Primary Focus |
|---|---|---|---|
| **Home** | `/` | *How much money do I have? What deserves attention today?* | Clear capital KPIs, holdings pulse, actionable opportunities, account freshness |
| **My Portfolio** | `/portfolio` | *What investments do I own and how are they doing?* | Positions table, weights, P&L, review status, simple 1-click sync |
| **Discover Stocks** | `/market` | *What stocks are worth researching and why?* | 42 Challenge stocks, plain-language summaries, search, progressive detail drawer |
| **Trade Planner** | `/planner` | *How much could I buy and when should I review or exit?* | Simple trade plans (What, Why, Price, Shares, Cost, Risk, Horizon, Exit) |
| **My Trades** | `/transactions` | *What orders and transactions have taken place?* | Historical trade executions, pending orders, cash movements |
| **Research Lab** | `/strategy` | *How do the underlying strategies perform over time?* | Multi-horizon models (Swing, Position, Day), forward paper trading, backtests |
| **Settings & Data Health** | `/health` | *Is my market data and system connection fresh and healthy?* | EOD gateway status, BCT calendars, rule checkers, local security |

---

## 2. Visual Palette & Theming

### A. Color Palette
- **Canvas / Background**: Warm off-white (`bg-slate-50/70` in light mode; `bg-slate-950` in dark mode).
- **Text & Contrast**:
  - Primary Headings: Dark charcoal (`text-slate-900` / `text-slate-100`).
  - Secondary Body: Readable slate (`text-slate-600` / `text-slate-400`).
  - Muted Captions: Slate 500 (`text-slate-500` / `text-slate-500`).
- **Brand & Action**: Muted Teal (`teal-600` / `teal-700` hover; dark `teal-500`).
- **Restrained Status Indicators**:
  - Positive / Verified: Soft Emerald (`emerald-600` / `emerald-700`, `bg-emerald-50`).
  - Warning / Informational: Warm Amber (`amber-600` / `amber-700`, `bg-amber-50`).
  - Danger / Blocked: Subdued Rose (`rose-600` / `rose-700`, `bg-rose-50`).
  - Neutral / Research: Slate Gray (`slate-600`, `bg-slate-100`).

### B. Typography & Sizing Rules
1. **Body Text**: Comfortable `16px` (`text-base`) for narrative and instructional paragraphs.
2. **Table Data**: Minimum `14px` (`text-sm`) for all table rows and ticker symbols. No unreadable micro-fonts.
3. **Financial Numbers**: Monospace numbers (`font-mono`) with consistent 3-decimal precision for Tunisian Dinars (`0.000 TND`).
4. **Whitespace & Padding**: Generous padding (`p-6` on cards, `py-3.5` on table rows) to eliminate visual crowding.

---

## 3. Component Guidelines & Progressive Disclosure

### A. Progressive Disclosure
- **Level 1 (Card / Summary)**: Clean high-level metrics: Symbol, Company Name, Latest Price, 20-Day Trend, Recommendation Badge.
- **Level 2 (Drawer / Modal)**: Deep dive on demand: Sizing constraints, break-even math, supporting vs contradicting factors, macro context.
- **Level 3 (Advanced Toggle)**: Raw statistical diagnostics (volatility, turnover ratio, 60s momentum) reserved for users who enable "Advanced Metrics".

### B. Accessible Explainability (Tooltips & Popovers)
Every technical term (e.g. `10% Volume Cap`, `ATR Volatility`, `Quotation Group`, `Break-Even Price`) must provide a clickable/hoverable explanation answering:
1. **What it means**: Plain-language definition.
2. **Why it matters**: Direct impact on trading safety or returns.
3. **Calculation formula**: Exact mathematical expression used in Python backend.
4. **Limitations**: Inherent risks or sample boundaries.

---

## 4. Responsive Viewports Tested

- **1366 × 768**: Typical laptop display. Compact sidebar, 2-column card layouts, horizontally scrollable data tables.
- **1920 × 1080**: Standard desktop display. Generous whitespace, 4-column KPI grids, side-by-side calculator and candidate lists.
- **Tablet / Mobile (768px & below)**: Stacked column cards, full-width touch targets (min 44px height), collapsible navigation drawer.

