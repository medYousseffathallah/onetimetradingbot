# M14 UX review package

Status: **NEEDS USER REVIEW**. The package and review artifacts are **DONE**;
production redesign remains **BLOCKED** until the information architecture and
versioned data contracts are reviewed. Owner: Codex lead/product integrator.
This is a structural investment-management review, not another theme-only change.

## Review scope and entry points

Read the [UX blueprint](M14_UX_BLUEPRINT.md) for information architecture,
nullable evidence contracts and decision/operational state matrices. Two local,
interactive high-fidelity prototypes cover eight destinations:

- [Investment and portfolio workspace](prototypes/m14/overview.html#overview)
- [Research and decision workspace](prototypes/m14/research.html#screener)
- [Eight annotated structural wireframes](prototypes/m14/wireframes.html)

All companies, charts and values are synthetic fixtures, visibly labeled DESIGN
SANDBOX. They have no actual account or source connection. Notes persist only in
page memory; reload clears them. No order submission or account confirmation is
available. EOD observations remain research references, never executable quotes.

Open the files locally. If browser file handling limits review, this existing
Python command serves only the prototype folder on loopback; it installs nothing:

```powershell
python -m http.server 8766 --bind 127.0.0.1 --directory docs/prototypes/m14
```

Visit `http://127.0.0.1:8766/overview.html`, `research.html` or `wireframes.html`.
Do not expose the server publicly or use a logged-in competition page for UX tests.

## Eight-destination review map

| Destination | Wireframe | High-fidelity view | Review question |
|---|---|---|---|
| Investment Overview | [1](prototypes/m14/wireframes.html#page-1) | [Overview](prototypes/m14/overview.html#overview) | Can the user distinguish confirmed value, available cash, actual performance and review priorities immediately? |
| Portfolio Manager | [2](prototypes/m14/wireframes.html#page-2) | [Portfolio](prototypes/m14/overview.html#portfolio) | Are confirmed positions separate from staged observations and unverified commitments? |
| Opportunity Screener | [3](prototypes/m14/wireframes.html#page-3) | [Screener](prototypes/m14/research.html#screener) | Does the table surface research questions without equating opportunity strength with trading permission? |
| Individual Stock Research | [4](prototypes/m14/wireframes.html#page-4) | [Stock](prototypes/m14/research.html#stock) | Can sources, gaps, thesis, counter-thesis and quote limitations be understood for one verified identity? |
| Investment Decision Workspace | [5](prototypes/m14/wireframes.html#page-5) | [Decision](prototypes/m14/research.html#decision) | Can the user explain a decision, uncertainty and review trigger before seeing a quantity? |
| Trade Planner | [6](prototypes/m14/wireframes.html#page-6) | [Planner](prototypes/m14/research.html#planner) | Are observed reference, user limit, constraints and zero-share blockers unmistakably separate? |
| Performance and Strategy Evaluation | [7](prototypes/m14/wireframes.html#page-7) | [Performance](prototypes/m14/overview.html#performance) | Are actual account attribution, forward paper observations and retrospective simulations kept apart? |
| Data Health | [8](prototypes/m14/wireframes.html#page-8) | [Health](prototypes/m14/overview.html#health) | Can a user see the exact missing evidence, source age and authorized recovery step without assuming a technical success means trading readiness? |

The navigation is consistent across files. On mobile it becomes horizontally
scrollable; tables retain their fields in local horizontal scrolling containers.
Review whether those scroll affordances are discoverable before production work.

## Guided review journeys

### 1. Establish portfolio truth

Start at Overview. Identify synthetic portfolio/cash/exposure and the unavailable
session P&L. Inspect the pending-capture dialog and then Portfolio. Check that
there is no confirmation or trade button and that the current confirmed holdings
are not replaced by a staged capture. Open observation history. A review modal is
not a completed account synchronization.

Decision to record: whether the information hierarchy and labels make confirmed,
staged and locally recalculated values clear before any research action.

### 2. Find a research question

Go to Screener, filter by coverage and search for a synthetic issuer. Try an
unmatched search to review the empty state, then clear it. Open Stock Research.
Compare opportunity strength, evidence coverage, uncertainty, eligibility and
portfolio suitability. Inspect sources/documents and risks/invalidation tabs.

Decision to record: whether the table supports investment research while leaving
thin, restricted or incomplete cases visible with honest explanations.

### 3. Exercise evidence failure states

On Stock Research switch among partial, stale and no-source scenarios. With no
source, the price becomes Unavailable and the line disappears; no interpolation
or zero-valued price is substituted. With stale evidence, retain historical
context but make its inability to establish an executable quote clear.

Decision to record: whether missing, stale and conflicting evidence need stronger
visual or verbal distinctions. Do not approve default scores for absent inputs.

### 4. Explain a decision before planning

Open Decision Workspace. Inspect thesis/counter-thesis, A-G evidence and review
triggers. Save a research-note draft, reload, and verify it clears. Open Planner,
enter a hypothetical user limit and review the illustration. The user limit is
not a market observation. Quantity/notional/fees stay zero while required evidence
is missing, and cash cannot be portrayed as spent.

Decision to record: whether the progression from research question to reviewable
decision and separately gated worksheet matches the intended workflow. This
prototype does not implement a persistent decision journal or v2 scoring method.

### 5. Evaluate and recover

Inspect Performance and Data Health. Keep historical simulations, forward paper
journal and actual account outcomes in different lanes. Do not judge a multi-week
holding decision from its first day's movement. Identify account, rule, quote,
identity and fundamental gaps; review the separate
[browser-sync acceptance checklist](M14_BROWSER_SYNC_ACCEPTANCE.md).

Decision to record: whether limitations and recovery instructions are actionable
without implying that the system can resolve authenticated or protected actions
on its own. Stop before any real account confirmation.

## Required data/decision contract review

| Contract question | Acceptance criterion | Owner / unresolved dependency |
|---|---|---|
| Which entity identifies a security across screens? | Stable instrument ID plus dated ISIN mapping; conflicting/free-text identifiers cannot promote eligibility | Codex; Gemini audits mappings/coverage |
| Which clocks are shown? | EOD session, source publication/first availability/retrieval, account capture and human confirmation remain distinct; unknown times stay null | Codex |
| What supports opportunity strength? | Supported evidence or Not established; no production aggregate weights invented by the UI | Gemini proposal then independent Codex validation |
| How are coverage and uncertainty represented? | Layer-level missingness/reasons, not an invented probability of profit or neutral zero | Gemini + Codex |
| Who determines trading eligibility and quantities? | Backend deterministic rules/account/identity/quote/portfolio checks; UI never overrides blockers | Codex |
| Does account state include pending commitments? | Unverified history/orders remain explicitly unverified; no assumed zero reservations | User verification + Codex |
| What defines HOLD or REVIEW POSITION? | Reviewable position context and horizon, with missing-price/coverage limits visible; not automated investment advice | Gemini evidence design + Codex |
| How is a MANUAL TRADE PLAN allowed? | Verified deterministic inputs plus human review; never a submission mechanism or positive-thesis shortcut | Codex; current rule/account blockers remain |
| What persists? | Prototype drafts are transient; production journal/versioning/access contract must be separately designed and tested | Codex; not implemented here |
| Which outcomes may be compared? | Actual account attribution, simulations and forward paper results stay separate and traceable to their inputs/cutoffs | Codex |

Supported decision vocabulary is WATCH, RESEARCH FURTHER, PAPER-TRADE CANDIDATE,
HOLD, REVIEW POSITION, MANUAL TRADE PLAN, NOT ELIGIBLE and INSUFFICIENT EVIDENCE.
Displaying a vocabulary does not validate a transition algorithm. Evidence and
operational dimensions remain separate; source positivity cannot bypass a gate.
Decision Engine v2 remains disabled/unpromoted pending independent validation.

## Technical evidence already recorded

These results are inherited from the existing M14 integrator report, not rerun
by the documentation specialist. Use the linked artifacts and command versions
when reproducing; do not treat the figures as a production SLO.

- [Blueprint verification](M14_UX_BLUEPRINT.md): JavaScript syntax/local references
  checked; eight prototype views at 1440px/390px and 14 interaction checks passed
  in Chrome 157.0.8103.39, with no document-level overflow or page runtime errors.
- [Integration report](M14_INTEGRATION_REPORT.md): isolated production Next build,
  nine pages and 115 synthetic API responses all 200; no runtime errors, external
  requests or writes. Warm reload p95 was 1.04-2.03 seconds; six sidebar samples
  0.64-0.86 seconds with explicit settling delay. Home exceeded two seconds.
- Local ignored evidence: `artifacts/m14/browser-results.json` and
  `artifacts/m14/screenshots/`. Desktop/mobile screenshots were visually inspected
  by the lead; an allocation legend was corrected to exclusive 75% cash, 9% other
  holdings and 16% industrials, with 25% total invested.
- Full earlier gate was 441 tests plus formatting/lint/typing/skill validation;
  new cold-load work must report its own final regression result separately.

These checks establish technical behavior of local fixtures. They do not prove
user approval, a correct financial model, live account synchronization, accessible
fundamental sources, current executable quotes or quantitative predictive skill.
Dense prototype captions remain an accessibility concern: production body text
should meet the blueprint's 14px/12px readability targets. Keyboard flow, screen
reader labeling, contrast and mobile table/navigation affordances need explicit
review before production acceptance; automated layout checks are insufficient.

## User review decision record

Status: **NEEDS USER REVIEW**. Record accept / revise / defer and a short reason
for each item; no answer is inferred from elapsed time or technical tests.

- [ ] Eight-destination information architecture and navigation sequence.
- [ ] Portfolio-first hierarchy and confirmed/staged/local valuation labels.
- [ ] Research vocabulary, limitation language and evidence-versus-execution split.
- [ ] Evidence failure states: missing, stale, partial, conflicting and unavailable.
- [ ] Thesis/counter-thesis and review-trigger workflow before planning.
- [ ] Separate observed reference versus user limit and blocked zero-share worksheet.
- [ ] Separation of actual account, forward paper and retrospective performance.
- [ ] Desktop/mobile readability, chart labels, scroll affordances and keyboard flow.
- [ ] Nullable source/time/identity contracts and proposed decision-record persistence.
- [ ] First bounded production workflow to implement after contract acceptance.

Design approval does not authorize a model promotion, new data source access,
paid API, account confirmation, trade, deployment or Git push. Any later production
slice needs explicit ownership, tests for empty/stale/partial/failed/synthetic
states, source/cutoff fidelity and independent verification of P0 protections.
No production redesign or theme change was made for this package.

## Current register

| Task | Owner | Status | Evidence / next dependency |
|---|---|---|---|
| Eight wireframes and two high-fidelity artifacts | Codex | DONE | Existing local HTML/SVG/CSS/JS artifacts |
| Structured UX review package | Codex | DONE | This package and anchor verification |
| Information architecture and contract decision | User + Codex | NEEDS USER REVIEW | Checklist above |
| Quantitative evidence/transition design | Gemini + Codex | RESEARCH ONLY | G1-G7 reproduced; joint review/corrected results supersede earlier waiting status; no v2 approval |
| Full production redesign | Codex | BLOCKED | UX/contract review and accepted evidence design |
| Authenticated account synchronization | User + Codex | NEEDS USER REVIEW | Separate protected live acceptance; no confirmation authorized |

Joint-integration verification: Chrome prototype and production-fixture suites
passed. Refreshed local screenshots:
[overview desktop](../artifacts/m14-joint/screenshots/overview-desktop.png),
[overview mobile](../artifacts/m14-joint/screenshots/overview-mobile.png),
[research desktop](../artifacts/m14-joint/screenshots/research-desktop.png),
[research mobile](../artifacts/m14-joint/screenshots/research-mobile.png).
These ignored local artifacts contain synthetic design fixtures, not a deployment.
