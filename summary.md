# BVMT recent work summary

Latest update: [M14 joint integration review](docs/M14_JOINT_INTEGRATION_REVIEW.md)
supersedes the earlier in-progress status below. Gemini evidence was reproduced,
correctness defects repaired, corrected studies recorded, and the final working-tree
gate passed516 tests. See the linked report for local commits, preservation,
performance limits and remaining research/operational blockers. No predictive
improvement or production strategy promotion is claimed.

Prepared on **2026-11-11** from the local repository, Git history, task register,
state records, implementation files and saved audit artifacts.

## Scope and status

This summary focuses on the latest tasks: Milestone 13 integration, P0 operational
recovery, Milestone 14 orchestration/performance/UX work, and the subsequent
validation-reuse work. Earlier milestones are included for context.

The application is a local, human-supervised research and decision-support system.
It has data ingestion, research ranking, historical simulation, a portfolio ledger,
account synchronization, FastAPI endpoints and a Next.js interface. These capabilities
do not establish profitable predictions or readiness for autonomous trading.

At inspection, `main` remained at **6f0b64d**, the Milestone 13 integration commit.
P0/M14 changes and the newer validation-reuse work were **uncommitted**. A safe local
commit was listed as WORKING, not completed. Existing unrelated edits were present.
Historical test counts below belong to their recorded checkpoints; they are not a
fresh certification of every change currently in the working tree.

## 1. Foundation already delivered

The earlier task records describe the following completed capabilities:

| Area | Delivered capability |
|---|---|
| Reproducibility | Locked environment, offline demo, quality gate, local skills and evidence-backed handoffs |
| Market data | Canonical CSV and source-specific BVMT adapters, immutable raw snapshots, hashes, provenance and rejection reports |
| Instruments and sessions | Dated identifiers, instrument master, exchange sessions, suspensions and coverage diagnostics |
| Baseline research | Session-aware momentum, liquidity filters, lagged features and research shortlists |
| Simulation | Later-session fills, shared participation limits, partial fills, order expiry, Decimal cash/fee accounting and benchmark comparisons |
| Portfolio workflow | Manual ledger, order lifecycle, valuation history, reconciliation and local notifications |
| Research evaluation | Frozen strategy hypotheses, chronological walk-forward evaluation, sensitivity analysis and promotion gates |
| Forward validation | Immutable forward paper-trading journal and robustness comparisons |
| Interfaces | Streamlit dashboard, later FastAPI/Next.js interface, glossary and metric explanations |
| LLM infrastructure | Budget-gated provider adapter, offline/mocked tests, document chunking and retrieval fallbacks; live calls remain opt-in |

Evidence: [task backlog](task.md), [working state](docs/STATE.md),
[workstream history](docs/AGENT_WORKSTREAMS.md).

## 2. Recent operational and interface work before Milestone 13

### Challenge alignment and planning

Milestones 8 and 9 introduced challenge-universe filtering, safer trade planning,
human-centered navigation, and multi-horizon research views. Research coverage and
competition tradability became separate concerns. Later audits identified fixed
cutoffs, static macro catalogs and horizon narratives requiring further verification;
their presence is not proof of current, timestamp-verified fundamental evidence.

### Account synchronization

Milestone 10 introduced a canonical synchronization service with three acquisition
paths: Chrome Browser Companion, manual paste/CSV, and asynchronous Playwright
fallback. It added normalized observation schemas, Decimal balance checks, content
deduplication, local pairing tokens, background job status/cancellation and a
confirmation-based portfolio review workflow.

Missing values remain unknown rather than silently becoming zero. Capturing or
staging an account observation is distinct from confirming it into the ledger.

### Daily accounting and planner recovery

Milestone 12 added session accounting and `/api/session/summary`, separating
acquisition-to-date unrealized P&L, session realized P&L, holdings movement and total
return. The November 9 reconciliation report reconstructed an account-equity change
with a zero arithmetic gap, while retaining incomplete attribution pending exact
transaction-history evidence. This is account reconstruction, not model-return proof.

The November 10 hotfix resolved a planner crash caused by `day_trading_notice`
contract differences (`reasons` versus `primary_reasons`) and added defensive
frontend fallbacks. That checkpoint recorded **388 Python tests** and a production
build passing. Historical service-status observations do not establish that those
services are running now.

## 3. Milestone 13 — integrated on main

Integration commit: **6f0b64d**. The recorded integration combined the dashboard
and research branches and resolved shared portfolio-service changes.

### Synchronization reliability

The synchronization audit documented 24 reproduced failures across the extension,
parsers, API, job lifecycle, staging and ledger. Fixes included:

- Extension background upload relay, stricter table-column mapping and French
  numeric parsing, plus transaction/pending-order extraction.
- Explicit validation failures instead of silent default balances or stale-success
  responses; persisted pairing/job state and extension CORS support.
- Snapshot rejection, transaction import and expected-snapshot conflict protection.
- Content-based deduplication, collision-resistant filenames, corrupt-file
  resilience and browser/profile-lock fallback handling.
- Atomic ledger persistence, incremental partial-fill merging, fee/realized-P&L
  tracking and preservation of account-history verification flags.
- Cache invalidation after account rejection, transaction imports and partial
  browser salvage; isolation of job managers by persistence path.

Source: [synchronization audit](docs/SYNC_RELIABILITY_AUDIT.md).

### Performance and explainability

Content-fingerprinted bounded caches, lighter endpoint options, lazy chart loading
and plain-language decision explanations were integrated. Sparse explanations were
wired into rankings, research and both planning paths without replacing Models A–I.

The original performance report recorded 19 warm routes below 180 ms p95. A later
M14 audit did **not** reproduce that bound for all routes; see section 5.

### Sparse-data research and ICF investigation

`sparse_research_v1` introduced a seven-layer research architecture separating
research availability from trading eligibility. Sparse or excluded instruments can
receive evidence-linked research without becoming actionable competition trades.

The ICF autopsy separated ingestion quarantine, negative pre-move momentum, thin
liquidity and execution constraints. It did not establish a prospective winning
signal. The recorded sparse comparison used 988 observations and 13 purged folds;
promotion was rejected because the reported overall false-positive rate was
**0.6058**, above its **0.45** threshold.

These are inherited M13 findings, not independently reproduced M14 experiments.
Sources: [ICF autopsy](docs/ICF_MISSED_OPPORTUNITY_AUTOPSY.md),
[sparse research](docs/SPARSE_DATA_RESEARCH.md),
[strategy comparison](docs/STRATEGY_COMPARISON.md).

### Recorded acceptance

The integrated checkpoint recorded **424 tests passed**, Ruff/format checks clean,
mypy clean across 35 source files, and 10 local skills validated. Account-ledger
preservation was checked. Authenticated Browser Companion acceptance remained open.

## 4. P0 operational recovery — implemented, uncommitted

The recovery task addressed cases where real-account API responses could suggest
actionable quantities despite incomplete evidence.

### Financial and operational guards

Rankings, overview actionable counts, both planner routes and multi-horizon
decisions now suppress actionable quantities for unknown rules, nonmembership,
conflicting identifiers, missing/future/stale quotes, pending synchronization or
unverified account history. Blocked plans keep notional, fees, cash and exposure
arithmetic consistent.

### Identifier and quote honesty

Browser/universe resolution rejects contradictory symbols and ISINs. Static
membership no longer implies a fresh quote. Mapping documentation was reconciled
against the saved registry; this was not independent official-source verification.

The planner stopped fabricating a 16:00 quote timestamp. User-entered limits and
observed prices are distinct, and absent quote timestamps/ages remain null.
Frontend types and explanations were updated accordingly.

### Recorded validation and remaining scope

- 14 focused recovery tests passed.
- Frontend typecheck passed; synthetic demo completed with execution disabled.
- Rules check returned the expected exit 2 with **72 evidence blockers**.
- Full gate recorded **439 tests passed**, one Starlette deprecation warning,
  clean static checks and 10 valid local skills.
- Preservation checks covered pre-existing user edits and account artifacts.

Legacy Streamlit presentation parity was handed off as **G-P0** and was not
implemented by this API recovery slice. Pending account captures, transaction
history and pending orders still require review.

Source: [P0 recovery report](docs/P0_OPERATIONAL_RECOVERY.md).

## 5. Milestone 14 — audits, orchestration and review artifacts

### Ownership and research handoff

Project instructions now identify Codex as lead/integrator for frontend, API,
performance, safety and tests, with Gemini assigned quantitative/data-quality/
fundamental-source research. A complete G1–G7 assignment and integration contract
define provenance, source hashes, point-in-time evidence and acceptance requirements.

Earlier reports marked Gemini WAITING_FOR_AGENT because no callable CLI session
was established. The newer task register records a **user-reported Antigravity
launch as WORKING**. No completed five-file return package or quantitative acceptance
was available in the reviewed records. This status is newer than the waiting label,
but does not establish completion.

### Offline status safety

`GET /api/market-data/status` now defaults to `check_remote=False` and explicitly
propagates remote-probe opt-in. Two regression tests were recorded failing before
the fix and passing afterward. Ordinary status inspection therefore avoids the
previous implicit remote probe.

### Independent performance audit

The saved audit used disposable account copies and 17,110 EOD bars through
November 10. It measured 21 in-process API routes with eight warm samples each.

| Measurement | Recorded result |
|---|---|
| Route responses | 21/21 routes returned HTTP 200 |
| Worst warm p95 | 304.575 ms, holdings |
| Cold state build | 5,717.487 ms |
| Largest measured cold route | 6,578.437 ms |
| Controlled cache checks | 4/4 passed |
| Source/input preservation | 61 hashes unchanged |
| External connection attempts | 0 |

Holdings, rankings and paper trading exceeded the older 180 ms claim. The profiler
found 85,550 bar-validation calls for 17,110 bars, motivating the later reuse work.
These measurements are local in-process smoke evidence, not production latency SLOs.

Source: [M14 performance audit](docs/M14_PERFORMANCE_AUDIT.md).

### UX deliverables and browser checks

Delivered an eight-destination UX blueprint, eight annotated wireframes and two
interactive prototypes: [overview](docs/prototypes/m14/overview.html) and
[research](docs/prototypes/m14/research.html). Fixtures are explicitly synthetic.
They separate account truth, research evidence, uncertainty and planning constraints.
This is a review package; a full production redesign has not been delivered.

Recorded Chrome checks covered desktop/mobile prototype views and 14 interactions.
An isolated production build with synthetic intercepted responses exercised nine
pages and 115 API responses, all 200, with no runtime errors, external requests or
write requests. Warm reload p95 ranged from 1.04 to 2.03 seconds; a universal
sub-two-second reload target was not achieved. These were fixture-rendering checks,
not authenticated account synchronization or real-account/API latency tests.

Sources: [UX blueprint](docs/M14_UX_BLUEPRINT.md),
[review package](docs/M14_UX_REVIEW_PACKAGE.md),
[integration report](docs/M14_INTEGRATION_REPORT.md).

### Recorded M14 checkpoint

The integration report records **441 tests passed**, clean Ruff/format/mypy checks,
10 valid local skills, frontend typecheck success and an isolated production build.
That checkpoint precedes newer working-tree changes described next.

## 6. Latest follow-up — validation reuse and review fixes in progress

The newer task register marks immutable validation reuse, final review and a safe
local commit as **WORKING**. Files and local benchmark artifacts exist beyond the
441-test checkpoint:

- `data.py` contains immutable validated-bar artifacts and a versioned reuse path.
- `test_validated_bar_artifacts.py` covers defensive lists, changed/invalid rows,
  duplicate handling, generation/version invalidation, parser/file changes,
  cutoff/liquidity recomputation, representation preservation, mutable subclasses,
  state equivalence and immutable record storage.
- `test_m14_review_fixes.py` adds identifier-conflict and custom-calendar source
  provenance regression coverage. Browser/calendar/data changes are present.
- `m14_validation_benchmark.py` isolates validation CPU work on already parsed rows.

The saved `artifacts/m14/cold-reuse/paired-final.json` records seven alternating
reference/reuse pairs over 17,110 rows. Median validation time was **518.010 ms**
versus **300.658 ms**, a **41.96% reduction**. Three validation boundaries required
51,330 reference calls versus 17,110 reused-path calls; the input hash was unchanged.

This is a narrow CPU benchmark under uncontrolled background load, not a whole-API
speedup. It was read from an existing artifact, not rerun for this summary. Earlier
audit statements that no optimization existed describe their earlier checkpoint.
Final full-gate acceptance and commit completion for this newer slice are not
established by the reviewed task register. Do not apply the 441-test result to it
without rerunning the gate.

## 7. What remains open

| Item | Current evidence-backed status | Next action |
|---|---|---|
| New reuse/review slice | WORKING, uncommitted | Finish independent review, run complete gate and reconcile task/state evidence |
| Local commit | WORKING, not observed in Git history | Complete staged allowlist/privacy review before committing |
| Gemini G1–G7 | User-reported launch; return package not received in reviewed records | Obtain five reports with actual provenance and reproducible source/input hashes |
| Decision Engine v2 | Absent; implementation/promotion blocked | Accept audit and frozen experiment design before implementation |
| Model promotion | Blocked | Meet predefined validation and independent forward-evidence requirements |
| Official competition rules | 72 unresolved evidence items at recorded check | Resolve against actual official documents and review configuration |
| Authenticated Browser Companion | Acceptance not tested in M14 | Follow operator-assisted capture/history/order acceptance checklist |
| Account synchronization | Pending/unverified state remains | Review the specific capture and reconcile history/orders manually |
| Streamlit recovery parity | Separate G-P0 handoff, not completed here | Implement and test owned presentation changes |
| UX redesign | Prototypes delivered; needs human review | Review workflows and nullable contracts before production redesign |
| Market freshness | EOD evidence only; publication timestamps absent in recorded dataset | Establish actual availability and executable quote evidence |

No new profitable strategy, production v2 score, authenticated sync acceptance or
live intraday quotation feed should be inferred from the delivered infrastructure.

## 8. Validation chronology and documentation limits

| Checkpoint | Recorded Python test result | Meaning |
|---|---:|---|
| November 10 planner recovery | 388 passed | Historical checkpoint |
| M13 integrated main | 424 passed | Integrated M13 tree |
| P0 recovery | 439 passed | Uncommitted recovery tree |
| M14 audit/status checkpoint | 441 passed | Uncommitted M14 checkpoint before newer reuse work |
| New reuse/review slice | Final acceptance not established here | Working-tree code/tests/artifacts exist |

This summary was prepared through read-only repository/history/artifact inspection
and documentation edits. Application tests, demo, build and benchmarks were not
rerun for this documentation task. Older state sections contain historical counts
and planned next actions; the newer task register takes precedence for current
work-in-progress labels. No account files, strategy configuration or runtime code
were changed while preparing this summary.

## 9. Source and handoff index

- [Current state and historical checkpoints](docs/STATE.md)
- [Task backlog](task.md)
- [M14 active task register](docs/M14_TASK_REGISTER.md)
- [M14 orchestration plan](docs/M14_ORCHESTRATION_PLAN.md)
- [M14 integration report](docs/M14_INTEGRATION_REPORT.md)
- [P0 operational recovery](docs/P0_OPERATIONAL_RECOVERY.md)
- [Gemini research assignment](docs/handoffs/GEMINI_M14_QUANT_TASK.md)
- [Gemini integration contract](docs/M14_GEMINI_INTEGRATION_CONTRACT.md)
- [Authenticated browser acceptance checklist](docs/M14_BROWSER_SYNC_ACCEPTANCE.md)
- [M14 performance audit](docs/M14_PERFORMANCE_AUDIT.md)
- [M14 UX review package](docs/M14_UX_REVIEW_PACKAGE.md)
- [M13 synchronization audit](docs/SYNC_RELIABILITY_AUDIT.md)
- [M13 performance audit](docs/PERFORMANCE_AUDIT.md)
- [Sparse-data research design](docs/SPARSE_DATA_RESEARCH.md)
- [Strategy comparison and rejected promotion](docs/STRATEGY_COMPARISON.md)
