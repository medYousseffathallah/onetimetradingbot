# Milestone 14 integration report

Historical checkpoint: superseded by [M14 joint integration review](M14_JOINT_INTEGRATION_REVIEW.md).
Gemini's later delivered audit has now been reproduced and reviewed; the waiting
status below describes the earlier session, not the latest state.

## Outcome

Codex-owned orchestration, safe status access, reliability checks, performance
investigation and review-only UX artifacts are implemented. Gemini's quantitative
audit/proposal, v2 experiments and promotion remain BLOCKED / WAITING_FOR_AGENT.
There is no production Decision Engine v2 and no claim of improved predictive skill.

## 1. Codex session provenance and starting state

Actual CLI command reported `codex-cli 0.167.1`. Active model ID was not exposed
by the checked metadata; no unsupported model identity is claimed. Root:
`C:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit`. Branch main, HEAD
`6f0b64dcdf36071b136bd729f89bae5778088516`. Existing P0 changes were uncommitted.
Re-ran the full offline gate: **439 passed**, 1 warning, 143.36s; all static checks
passed. These are dirty-tree results, not results for HEAD alone.

Other worktrees: codex/data-research at
`4a57b441c3322b33ac3c4fbd5cdd3d1fb5066a16` clean;
gemini/dashboard at `fdfae2a228c919793f1c125bbe2b61a3a74f60f9` with the existing
dirty playwright_worker.py and portfolio_service.py. No other worktree was edited.
No new commits, merges, pushes, deployments or dependency installations occurred.

## 2. Gemini provenance and blocker

`gemini --version` failed (CommandNotFoundException); executable lookup found no
Gemini command. Antigravity IDE is installed/running, public version 1.107.0.
That does not establish a Gemini provider/model/session or callable agent API.
No authentication secrets were inspected and no paid agent/API was invoked.

The complete assignment is in `handoffs/GEMINI_M14_QUANT_TASK.md`, including the
exact existing worktree and user startup instructions. All five requested Gemini
research deliverables are absent and explicitly BLOCKED. No substitute agent is
presented as Gemini. See M14_AGENT_HANDOFF.md for return-package requirements.

## 3. Executed tasks and acceptance register

| TASK | OWNER | STATUS | DEPENDENCIES | EVIDENCE | COMMIT |
|---|---|---|---|---|---|
| Provenance/preservation and baseline P0 gate | Codex lead | PASS | existing working tree | 439 tests; starting-hashes.json | base 6f0b64d; uncommitted |
| Genuine Gemini invocation | Codex lead/Gemini | BLOCKED | callable genuine agent | command unavailable; IDE presence only | none |
| Complete research assignment/handoff | Codex lead | PASS | launch investigation | handoffs/GEMINI_M14_QUANT_TASK.md | uncommitted |
| G1-G7 quantitative audit, ICF and source research | Gemini | BLOCKED | WAITING_FOR_AGENT | no session or outputs | none |
| Local status offline default | Codex lead | PASS | reproduced regression | 2 new tests fail before/pass after | uncommitted |
| Authenticated browser sync acceptance | Operator + Codex | NOT TESTED | operator login and review | M14_BROWSER_SYNC_ACCEPTANCE.md | no account mutation |
| API performance and cache investigation | Codex /root/m14_perf | PASS | baseline completed; isolated inputs | performance.json; M14_PERFORMANCE_AUDIT.md | uncommitted |
| Prior <180ms warm range reproduced | Codex lead | FAIL | same audit scope caveats | three routes exceed 180ms; no claimed speedup | uncommitted |
| UX blueprint, eight wireframes and two prototypes | Codex /root/m14_ux | PASS | existing P0 contracts | M14_UX_BLUEPRINT.md; prototypes/m14 | uncommitted |
| Independent local Chrome verification | Codex lead | PASS | isolated build and synthetic fixtures | browser-results.json and screenshots | uncommitted |
| Human review of UX/contracts | User + Codex | NOT TESTED | completed blueprint | full production redesign withheld | none |
| New v2 architecture acceptance/comparison/promotion | Gemini + Codex | BLOCKED | accepted audit and frozen experiments | no v2 implemented or promoted | none |
| Final combined offline gate | Codex lead | PASS | all code/harness changes | 441 tests; 78 formatted; Ruff/mypy/skills pass | uncommitted |

## 4. Reliability implementation and account safety

The specialist found `/api/market-data/status` called `gateway.get_status()` whose
remote probing default is true. Two offline regressions reproduced the omission.
The API now takes `check_remote=False` and explicitly passes
`probe_remote=check_remote`; normal status visits perform local inspection.
Explicit opt-in remains supported. Tests never call a real provider and verify
that the disposable ledger is unchanged. No recommendation/model code changed.

All P0 guards remain: unverified rules/identity/account/quote evidence suppress
real-account quantities; price observations remain separate from user limits.
The sync checklist stops before Confirm & Apply. Live acceptance remains
NOT TESTED, not implied by automated fixture success. Pending snapshots and
history/order verification still need operator review. Rules-check independently
returns exit 2 with **72 evidence blockers** and execution_authorized false.
Synthetic demo exits 0 with execution disabled. No trading or account API POST
was used against an actual account.

## 5. Recommendation weaknesses and ICF findings

Full quantitative audit is BLOCKED. Codex recorded review seeds, not a completed
substitute audit: hardcoded 2026-11-06 cutoff/session defaults and turnover fallback
in multi_horizon.py; mixed potential ratio/percent entry paths; static macro event
catalog; fixed horizon narrative in holding_period.py. Exact audit requests are
in M14_AGENT_HANDOFF.md and the G1-G7 handoff. No scoring fixes were assumed valid
without reproducible research evidence.

ICF M14 reproduction is **NOT TESTED**. The previous local autopsy reports a B
reservation-status quarantine, negative pre-November momentum, thin turnover and
execution/fill difficulties, distinguishing data failure from prediction failure.
The previous sparse comparison reports FPR **0.6058 > 0.45** and rejected promotion.
Those are inherited report claims requiring source/hash/cutoff reproduction,
not new M14 results. No pre-rally catalyst, available financial statement or
prospective edge has been established in this milestone. No ICF-specific tuning.

## 6. Proposed architecture and quantitative comparisons

The UX blueprint proposes separate A-G evidence panels and separate opportunity,
coverage, uncertainty, eligibility and portfolio-suitability dimensions. It does
not select feature weights, invent confidence, or define an accepted v2 score.
Gemini's versioned model proposal and frozen experiment specification are absent.
Model G, sparse_research_v1 and historical baseline results remain unchanged.

No new experimental returns, precision, false positives, drawdowns, capital
utilization or stability measurements were generated. Comparative validation is
BLOCKED until an accepted design specifies purged folds, training-only fitting,
cohort/label rules, transaction costs, T+1 execution/capacity, trial registry and
held-out/independent forward evidence. Retrospective improvement alone cannot
promote a model.

## 7. Performance and cold-load findings

Fresh measurement used 17,110 EOD bars through 2026-11-10 and disposable account
copies. 21/21 in-process routes returned 200; warm p95 was below 500ms, maximum
**304.575ms** (holdings), n=8 per route, nearest-rank p95. The previous <180ms range
was not reproduced for holdings, rankings and paper trading. Four cache probes
passed; 61 source/input hashes unchanged; external network attempts zero.

Cold state load is **5717.487ms**; application-cache-cold routes can take **6578.437ms**.
Profile shows 85,550 validate_bar calls for 17,110 bars, roughly five passes.
No validation was removed or cache optimization silently applied. The next bounded
experiment is an immutable validated-artifact reuse contract with tests for content,
config, cutoff and parser changes. Timing scopes/load differ from the older report;
no before/after speedup or production latency SLO is claimed.

Current-source Next production build passed in an isolated copy using existing
node_modules. Original frontend build/runtime was not replaced. Chrome tested
nine current pages with synthetic intercepted API responses; this checks rendering
and local navigation, not end-to-end real-account/API latency. Final Chrome 157.0.8103.39 results: nine pages and 115 API responses all 200;
zero page runtime errors, external requests or write requests. Three warm reloads
per route give nearest-rank p95 1043.91-2033.21ms; Home is the 2033.21ms outlier.
Six sidebar navigation samples were 637.51-856.30ms with an explicit 550ms delay
for scheduled effects plus network-idle settling. A sub-two-second reload across
all pages was not achieved. These are fixture browser smoke measurements, not a
production SLO; use the exact samples in browser-results.json. Live-sync browser
acceptance is absent.

## 8. UX blueprint and independent review

Eight destinations are covered: Investment Overview, Portfolio Manager,
Opportunity Screener, Individual Stock Research, Investment Decision Workspace,
Trade Planner, Performance/Strategy Evaluation and Data Health. Artifacts:
`M14_UX_BLUEPRINT.md`, eight annotated SVG wireframes in
`prototypes/m14/wireframes.html`, and two interactive high-fidelity prototypes
`overview.html` / `research.html` sharing local CSS/JS.

All companies, values and charts are synthetic fixtures with persistent labeling.
The artifacts separate account truth, research hypotheses and planning constraints;
show missing/stale/pending/blocked states; never offer trade submission or account
confirmation. Browser checks cover 1440px/390px layouts and interactions; lead
visually reviewed desktop/mobile screenshots and required an allocation-legend
correction. No full production redesign is implemented. Human review of contracts
and blueprint remains NOT TESTED.

## 9. Test evidence and limitations

- Initial current-tree gate: 439 tests pass; all static checks pass.
- New local-status regressions: 2 pass after failing before the fix.
- Isolated current-source Next build: PASS (existing dependencies, no installs).
- Prototype JS syntax and local references: PASS; browser interaction/layout
  checks PASS; final browser artifact records exact Chrome version and status.
- Final `uv run python scripts/check.py`: exit0; **441 passed**, 1 Starlette
  deprecation warning,139.87s;78 files formatted, Ruff clean, mypy35 files
  clean,10 skills valid. Final frontend `npm.cmd run typecheck`: exit0.
- All16 account JSONs present at M14 start unchanged; no account JSON added.
  Original data.py/test_gateway.py bytes unchanged; official configs unchanged.
  Final source and evidence hashes are in artifacts/m14/final-manifest.json.

First browser fixture setup omitted the relative demo CSV fallback and returned
503s; corrected the disposable fixture setup, not product assertions. A subsequent
browser pass returned all pages/API responses 200. No failed fixture-run timings
are used to claim production performance. Windows subprocess restrictions required
approved test/build/browser execution; no permissions or safety gates were bypassed.

## 10. Remaining blockers and next steps

1. User launches the genuine Gemini task in Antigravity using the full handoff;
   record actual model/provider/session and return G1-G7 outputs. Codex reviews
   reproducible evidence before any experimental implementation is approved.
2. Operator verifies the authenticated Browser Companion capture and movement/
   pending-order history using the acceptance checklist. This is not permission
   for this coding session to confirm pending state or place orders.
3. Official-rule evidence review remains blocked; all 72 gaps remain visible.
4. Review UX contracts and prototypes before authorizing the full redesign.
5. A bounded cold-state reuse experiment may be planned separately; preserve
   all validation and invalidation semantics. No production change is approved
   merely because a profile shows repeated calls.

All changes remain reviewable and uncommitted on main. No branch push, paid API,
autonomous trade, account overwrite or experimental-model promotion occurred.
