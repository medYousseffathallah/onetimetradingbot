# M14 Gemini integration contract

Later checkpoint: [joint integration review](M14_JOINT_INTEGRATION_REVIEW.md).
The requested evidence has now been delivered and reproduced. This earlier
contract remains the review protocol; v2 implementation/promotion stays blocked.

Status: **DONE** as a review contract. Quantitative acceptance and Decision Engine
v2 implementation/promotion remain **BLOCKED** until the gates below pass.
Owner: Codex lead/integrator. Gemini is the research specialist; this document
was prepared by a Codex documentation specialist, not Gemini.

## Launch and source provenance

The user reports that Gemini G1-G7 is being launched separately in Google
Antigravity. Codex did not invoke Gemini CLI. A user-managed launch is not yet
independent evidence of a specific model, session or completed audit. Record the
visible provider/model, session ID if exposed, UTC start/end times, worktree and
actual output paths when Gemini returns. Never inspect authentication secrets.
Use the full assignment in [GEMINI_M14_QUANT_TASK.md](handoffs/GEMINI_M14_QUANT_TASK.md).

The intended isolated research worktree is
`C:/Users/Thinkcenter/Desktop/BVMT/bvmt-gemini-dashboard`, branch
`gemini/dashboard`. Its last verified HEAD was
`fdfae2a228c919793f1c125bbe2b61a3a74f60f9`; recheck it on receipt. Existing dirty
`src/bvmt/playwright_worker.py` and `src/bvmt/portfolio_service.py` belong to prior
work and must be preserved and distinguished from this assignment. A branch or
worktree name does not prove Gemini ran.

The integration tree is `C:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit`.
Its last recorded base was `6f0b64dcdf36071b136bd729f89bae5778088516` plus
uncommitted P0/M14 work; the lead may create reviewed local commits separately.
Gemini must identify the actual source it audited by commit AND source-file
SHA-256 values. Auditing its older worktree alone is insufficient for claims
about newer integration code. Reconcile differences explicitly, read-only.

## Expected return package

Initial scope is audit/design documentation only. These five files are required
in the Gemini worktree; they must not be fabricated or filled with unsupported
completion claims when evidence is absent.

| Expected file | Minimum review content | Acceptance owner |
|---|---|---|
| `docs/M14_SCORING_AUDIT.md` | Signal-to-selection trace; equations/units; missingness/cutoff/default audit; all-42 challenge coverage; exact code paths, minimal reproductions and affected instruments | Codex |
| `docs/M14_ICF_CASE_STUDY.md` | Pre-move data availability; separate ingestion, prediction and execution findings; costs/capacity; counterfactual assumptions; no hindsight tuning | Codex |
| `docs/M14_FUNDAMENTAL_DATA_GAPS.md` | Actually available documents versus source suggestions; source/access/parser feasibility; publication/first-available/retrieval limitations; explicit gaps | Codex |
| `docs/M14_DECISION_ENGINE_V2_PROPOSAL.md` | Independent A-G evidence layers; opportunity/coverage/uncertainty/eligibility/suitability separation; nullable inputs; deterministic gates; failure modes and tradeoffs | Codex |
| `docs/M14_EXPERIMENT_PLAN.md` | Frozen hypotheses/config/trial protocol; baselines/cohorts/labels; purging/embargo; costs/fills/capacity; metrics/denominators; rejection/promotion rules | Codex |

Every reported result needs a reproducibility manifest, which may be a sanitized
section of the document or an ignored local audit artifact. It must include:

- Actual agent provenance, audited commit, dirty-source state, worktree and
  changed-file list. Separate this task from pre-existing worktree edits.
- SHA-256 of each audited source file, canonical/raw input used, instrument master,
  exchange calendar, model/research config and baseline/experiment artifact.
  Record parser/model/config version and source permission/provenance identifiers.
- Input date coverage, universe version/membership convention, decision cutoff
  with timezone, label/execution horizons and missing/publication-time policy.
- Exact working directory, environment/tool versions, command, arguments, exit
  code, output artifact location/hash, sample count and assertions/checks run.
- Implemented, reproduced, proposed and not tested results stated separately.
  A command copied into prose is not evidence that it ran. Include failures.

Do not put raw account snapshots, credentials, tokens, session diagnostics or
licensed datasets into the return documents or Git. Describe protected input
requirements with sanitized counts/hashes and local paths instead. A hash proves
identity, not source correctness, licensing, publication availability or truth.

## Changed-file ownership and permitted work

| Scope | Initial permission | Later permission |
|---|---|---|
| The five research documents above | Gemini may write in its isolated worktree | Codex reviews each diff before integration |
| Sanitized manifests and audit outputs | Local ignored artifacts, preserving source/baseline files | No private or licensed payloads in Git |
| Audit reproducer scripts/tests | Propose exact paths and ownership first; not blanket production permission | Codex may approve a bounded, independently testable research-only patch |
| Experimental v2 modules/configs/results | **BLOCKED** in this initial audit | Separate Codex approval after accepted audit and frozen experiment plan; isolated namespace, versioned config and default-disabled integration |
| Production frontend/API/sizing/decision paths | Read-only for Gemini | Codex-owned integration after independent validation; no direct rewrite |
| Official competition config, confirmed ledger, account snapshots, secrets and baseline results | Forbidden mutation | This contract grants no permission to change them |

Do not change `features.py`, `recommendations.py`, `research_coverage.py`,
`sparse_research.py`, `sparse_generalization.py`, `multi_horizon.py`,
`strategies.py`, `holding_period.py` or `macro_events.py` during initial audit.
Inspect them read-only and report proposed corrections. Do not auto-merge,
reset/stash existing work, submit orders, confirm snapshots/trades, request broker
credentials, install code, call paid APIs, deploy or push Git branches.

Decision Engine v2 remains absent/disabled and unpromoted. This is a release
condition, not a claim that a particular feature flag already exists. No new flag
name, model weights or API behavior is invented by this document. Model G,
`sparse_research_v1` and recorded baseline outcomes remain authoritative frozen
comparison inputs. Research findings cannot override deterministic trade gates.

## Research acceptance gates

Codex records the result and evidence for every gate. A missing required input
blocks that claim or comparison; it must not be converted to a favorable score.

1. **Provenance and source agreement.** Inspect actual five deliverables and
   changed-file diff. Resolve stale source/worktree mismatches. Verify all input
   hashes and commands. Agent narrative alone is insufficient.
2. **Mathematical contracts.** State ratio versus percentage units at every
   interface; verify horizon/session indexing, ranking direction, denominators,
   rounding and missingness. Zero-volume, missing and suspended sessions stay
   distinct. A missing return or financial ratio is null with a reason, not zero.
3. **Identity and universe.** Account for all 42 observed challenge securities,
   including missing/restricted entries and exclusions. Verify dated IDs/ISINs
   and mapping conflicts. Do not use current membership as historical membership
   without disclosing the point-in-time limitation.
4. **Point-in-time evidence.** No feature may use publication/first availability
   after the decision cutoff. Keep source publication, effective, retrieval,
   market/session and account-capture clocks separate. Retrieval does not prove
   prior publication. Date-only releases need an explicit conservative convention;
   restatements are separate versions. Unknown availability blocks predictive
   claims that depend on it.
5. **ICF reconstruction.** Separate H1 and November episodes where supported.
   Reproduce the previous quarantine/coverage assessment and pre-event inputs.
   Keep official reservation/reference values distinct from executed prices.
   Counterfactual data repair is a separate labeled scenario. Do not select
   features, thresholds or cohorts because ICF later rose. Missing disclosures
   mean insufficient evidence, not proof that no catalyst existed.
6. **Failure analysis and economic feasibility.** Classify DATA, FEATURE, MODEL,
   EXECUTION, LIQUIDITY, UNIVERSE, IMPLEMENTATION or INSUFFICIENT EVIDENCE. Assess
   STA over its intended holding horizon, not only its first day. Review SOTETEL
   dependence, rebalance offsets, capital utilization and sparse false positives.
   Enforce later-session execution, no zero-volume fills, shared participation,
   pending/partial fills, fees, cash and concentration limits. EOD is not an
   executable intraday quote; attractive evidence is not a BUY authorization.
7. **Experimental specification before implementation.** Freeze versioned
   hypotheses/configs, labels, top-k, cohorts, turnover/cost/fill assumptions,
   training/validation/test windows, purging and embargo before running new
   comparisons. Fit preprocessing and choose thresholds using training/validation
   only. Purge overlapping label horizons across the entire market by date.
8. **Comparative evidence.** Compare existing Model G, `sparse_research_v1`,
   proposed v2 and simple cash/equal-weight/liquidity-aware momentum baselines
   on identical declared dates and feasible execution assumptions. Include
   winners, losers, flat, sparse, thin and subsequently declining trend cohorts.
   Report survivorship/universe limits, not only successful examples.
9. **Metrics and false positives.** Report top-k precision, false-positive and
   missed-opportunity rates, forward net returns, drawdown, liquidity feasibility,
   turnover/fees, outlier dependence, capital utilization and stability. Define
   every denominator, label and unfillable-trade treatment; undefined metrics
   remain null. Preserve adverse cohorts and all attempted variations. Previous
   reported FPR 0.6058 above 0.45 is evidence to reproduce, not a threshold to
   retune after seeing new outcomes.
10. **Trial discipline and forward evidence.** Register all trials and failed
    variants; do not quietly select favorable rebalance calendars or horizons.
    Keep an untouched final period. Independently timestamped forward signals
    must precede their outcomes; retrospectively acquired history is not forward
    evidence. Report uncertainty and sample limits. Lack of independent forward
    data is explicit and prevents unsupported live-skill claims.
11. **Safety/regression equivalence.** Unknown rules/account/quote/identity still
    suppress actionable quantities. No missing values become fabricated prices,
    liquidity or fundamentals. Required targeted tests and the full offline gate
    must pass on proposed code. No changed expected results merely to make CI green.
12. **Independent acceptance.** Codex reruns key reproductions and reviews diff,
    tests and artifacts. An accepted audit only permits the next bounded research
    task; it does not approve production integration. A positive retrospective
    result never automatically promotes v2 or authorizes a manual trade.

## Receipt, review and integration sequence

1. Receive provenance, the five files, sanitized manifest, changed-file list and
   exact commit SHAs if any. Record WORKING for review, not DONE for research
   acceptance. User-reported external launch stays unverified until evidence arrives.
2. Inspect the actual files in the research worktree and compare with the agreed
   allowlist. Separate old dirty files and unrelated commits. Do not merge first
   to discover what changed. Reject or hold mixed-scope returns.
3. Review source/data/config identity and every required research gate. Reproduce
   representative findings independently on disposable data where appropriate.
   Document accepted, rejected and unresolved claims with exact evidence.
4. For doc-only delivery, integrate only reviewed documents via an explicit file
   allowlist or a focused commit. For later approved code, inspect every changed
   file and choose a focused cherry-pick only if its complete scope is acceptable.
   Resolve shared contracts on main and rerun targeted/full gates.
5. A full branch merge is considered only after inspecting its complete commit
   range/diff, ownership, private-file exclusions and checks. The name
   `gemini/dashboard` does not make its historical changes safe to merge.
6. Record integration commit(s), source/output hashes, executed commands and
   outcomes. Never push, mutate accounts or promote models as a side effect.

## Current register

| Task | Owner | Status | Dependency / completion evidence |
|---|---|---|---|
| Complete integration contract | Codex | DONE | This document; technical review by lead remains available |
| External Gemini launch/audit | User / Gemini | WORKING | User-managed launch reported; actual session and outputs not independently verified |
| G1-G7 research acceptance | Codex | BLOCKED | Actual five-file return package and reproducible evidence |
| v2 experimental implementation | Gemini + Codex | BLOCKED | Accepted audit and separately approved frozen experiment scope |
| v2 production integration/promotion | Codex | BLOCKED | Independent comparative validation and explicit promotion review |
| Authenticated account reconciliation | User + Codex | NEEDS USER REVIEW | Separate protected action; never authorized by research approval |

Prepared from existing repository documents and prototype contracts only. No
Gemini outputs, quantitative results, account contents or new external sources
were inspected or fabricated while preparing this contract.
