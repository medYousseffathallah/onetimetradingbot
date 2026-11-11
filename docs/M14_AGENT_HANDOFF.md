# M14 agent handoff and integration contract

Historical handoff: later Gemini delivery, reproduction and corrections are in
[the joint integration review](M14_JOINT_INTEGRATION_REVIEW.md). Waiting/absent-output
statuses below describe the earlier checkpoint.

## Provenance and ownership

Codex CLI 0.167.1 is the lead, operating in the integration repository on main
at 6f0b64dcdf36071b136bd729f89bae5778088516 plus uncommitted P0/M14 changes.
The active model identifier was not exposed by checked metadata. No new commit,
merge or push occurred. A base SHA does not identify the tested dirty tree;
local source/hash manifests supplement it.

Actual delegated Codex tasks:
- `/root/m14_perf`: exclusive scripts/m14_perf_audit.py,
  docs/M14_PERFORMANCE_AUDIT.md and ignored timing artifacts. A real collaboration
  task was invoked; lead inspected its code, measurements and preservation checks.
- `/root/m14_ux`: exclusive docs/M14_UX_BLUEPRINT.md and
  docs/prototypes/m14/*. A real collaboration task was invoked; lead independently
  browser-tested desktop/mobile states and inspected screenshots. The lead rejected
  a non-exclusive allocation legend and the specialist corrected it.

These are Codex specialists, not Gemini. They did not change production decisions.
The lead owns API status guard/tests, browser harness, review and shared documents.

## Genuine Gemini launch state

BLOCKED / WAITING_FOR_AGENT. `gemini --version` failed: command not found.
`Get-Command gemini` and `where.exe gemini` found no executable. Antigravity IDE
is installed and running (public version 1.107.0); no callable Gemini-agent tool
or independently identifiable Gemini session was available. No auth secrets
were inspected, no agent installation attempted and no paid call authorized.

The complete G1-G7 assignment and exact startup steps are in
`handoffs/GEMINI_M14_QUANT_TASK.md`. Target existing isolated worktree:
`C:/Users/Thinkcenter/Desktop/BVMT/bvmt-gemini-dashboard` on gemini/dashboard
at fdfae2a228c919793f1c125bbe2b61a3a74f60f9. Preserve existing dirty
playwright_worker.py and portfolio_service.py. Audit the newer integration source
READ-ONLY and hash its files; write the research deliverables in that worktree.
No blind merge/reset/stash or production model changes.

## Required return package (not received)

| Deliverable | Owner | Status | Review dependency |
|---|---|---|---|
| M14_SCORING_AUDIT.md | Gemini | BLOCKED | actual agent launch, current source hashes |
| M14_ICF_CASE_STUDY.md | Gemini | BLOCKED | cutoff/source audit and reproducible reconstruction |
| M14_FUNDAMENTAL_DATA_GAPS.md | Gemini | BLOCKED | accessible source evidence, availability times |
| M14_DECISION_ENGINE_V2_PROPOSAL.md | Gemini | BLOCKED | scoring/source audit accepted by Codex |
| M14_EXPERIMENT_PLAN.md | Gemini | BLOCKED | frozen hypotheses, PIT cohorts and validation gates |

Codex must verify commands, raw input/config hashes, outputs and assertions;
agent narrative is insufficient. Do not fabricate placeholder Gemini-authored
reports or treat absence as a passed audit. No v2 numerical comparison exists.

## Static review seeds, not completed quantitative audit

The lead observed these current source paths while preparing the handoff:
- multi_horizon.py evaluate_multi_horizon_intelligence defaults the session and
  fixes the macro cutoff at 2026-11-06; it also retains a 10000 TND turnover
  fallback. This is an implementation/default risk requiring G1 unit/data-path
  analysis, not proof of a profitable alternative. The P0 API guard remains.
- The same function accepts momentum from multiple representations; G1 must
  establish ratio/percentage units before changing thresholds or explanations.
- macro_events.py contains a static catalog and a fixed fallback cutoff. A
  catalog entry is not proof of a locally ingested, timestamp-verified filing.
- holding_period.py contains fixed horizon/return narrative claims. G3/G5 must
  separate recorded scenario descriptions from robust horizon selection.
- Existing ICF autopsy separates reservation-status quarantine from negative
  pre-November momentum, low liquidity and fill failures. Existing sparse
  comparison reports FPR 0.6058 above its 0.45 threshold. These are inherited
  reports, NOT independently rerun M14 experiments or validated improvements.

See ICF_MISSED_OPPORTUNITY_AUTOPSY.md and STRATEGY_COMPARISON.md as evidence to
reproduce, not instructions or settled findings for a new model. Current data
extends beyond their reported cutoff; do not silently change the audit period.

## Integration contract and stopping rules

All seven evidence layers remain independent. Proposed UX dimensions are
opportunity strength, evidence coverage, uncertainty, trading eligibility and
portfolio suitability; they do not define accepted weights or a production score.
Never convert absent values to neutral numeric inputs. Keep EOD session,
publication, retrieval and account capture/confirmation clocks distinct.

Keep Model G, sparse_research_v1, configurations and historical results frozen.
An experimental implementation is BLOCKED until Codex accepts audit and experiment
specification. Subsequent comparison requires purged chronological folds,
training-only fitting, costs/fills/capacity, all trials/cohorts, false positives,
outlier and capital sensitivity, and independent forward data when genuinely
available. No retrospective result automatically promotes a model.

The full redesign is also BLOCKED pending review of the blueprint and contracts.
Only standalone prototypes exist. Operator-authenticated sync acceptance remains
NOT TESTED; the checklist does not authorize account confirmation or trading.
