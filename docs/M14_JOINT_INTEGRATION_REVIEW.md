# M14 joint integration review

Date: 2026-11-11. Integration owner: actual Codex CLI session in the main workspace.
This report supersedes waiting-for-Gemini status in the earlier M14 reports.

## Preservation and integration boundary

Starting branches were main `6f0b64d`, Gemini `fdfae2a`, Codex research `4a57b44`.
Main contained uncommitted P0/reuse work and unrelated user changes; Gemini contained
uncommitted `playwright_worker.py` and `portfolio_service.py` changes plus nine new
research files. No reset, clean, branch merge or cherry-pick was used. The index
was empty at inspection. The two old Gemini sync files were not imported.

The six research documents, two scripts and one test module were copied using an
explicit allowlist after review. Original bytes, original numerical artifacts,
starting source bytes and preservation hashes are in ignored
`artifacts/m14-joint/`. Reproduction output was written under that separate tree,
never over Gemini's output or the old experiment registry. Script path adaptation
points at the integration source and local outputs; no mixed-worktree PYTHONPATH
was used. Imported tests initially ran unchanged against main.

Starting real-ledger SHA-256:
`0A1B86CB281187A0E9AB88A4CDE6D4DE173A5DF162111266CE1988DCBF91D395`.
All existing account JSON paths/hashes were recorded before implementation.

## Evidence classification

| Finding or contribution | Classification | Review result |
|---|---|---|
| Gemini's nine allowlisted files | VERIFIED | Located in the separate worktree and reviewed; user-managed Antigravity provenance is recorded in the handoff, vendor model ID is not independently exposed |
| Ten original focused tests | VERIFIED | 10 passed against starting main code in 11.89s; they characterize bugs, not correct behavior |
| Main quant audit JSON | VERIFIED | Reproduced exactly excluding generation timestamp |
| Folds/peers JSON | VERIFIED | Reproduced exactly excluding generation timestamp |
| Challenge accounting JSON | VERIFIED | Reproduced exactly |
| Previously uncommitted research files | REPRODUCIBLE BUT NOT INTEGRATED at receipt | Imported by explicit file allowlist, not treated as commits |
| Reported audited-source hashes | PARTIALLY VERIFIED | 20/22 recorded file hashes match inspected starting evidence; data.py/calendar.py differ due to newer work; do not claim identical whole-source provenance |
| Original holding filter 15/42 | VERIFIED | ID-vs-symbol comparison drops 27 members |
| POULINA 68+128 split | VERIFIED | Same registered ISIN, disjoint observed sessions, overlapping declared source validity retained as evidence |
| November cutoff exposed to October9 | VERIFIED | Original reports/tests reproduce future catalog exposure |
| 125000 flat/spike score | VERIFIED | Original baseline reproduces 125000 versus 16.762861 |
| MONOPRIX/ESSOUKNA/CIL displacement | VERIFIED | Reproduced in original full-market selection; explicit Challenge selection must isolate before top-k/budget |
| New numerical/source corrections | See correctness report | Focused regressions and final-tree gate required; no new strategy promotion |
| Proposed 0.0025 floor, softer history, directional awakening thresholds | HYPOTHESIS | Not adopted as established improvements; historical winners cannot select parameters |
| Seven-layer Decision Engine v2 | HYPOTHESIS | Design report only; no production v2 model or promotion |
| 20-session final period as pristine holdout | INVALIDATED | November9–10 outcomes and ICF-specific research were already inspected |
| Old sparse compounded portfolio returns and mixed-denominator comparisons | INVALIDATED for scientific comparison | Evaluation repaired/versioned; original files retained |
| Macro/fundamental source truth | BLOCKED | Static catalog labels are not saved authoritative source evidence |
| Exact competition readiness | BLOCKED | Official-rule evidence gaps and account/history/order verification remain |
| Authenticated Companion acceptance | BLOCKED / not tested | Fixture browser success is not authenticated account acceptance |

The specifically named `moduleoutput(20261111-182329).txt` was not located in the
inspected project/worktree/Desktop locations. Desktop `moduleoutput.txt` contains
older T02 material and was not substituted for it. Actual research files and
numerical artifacts, rather than a transcript, supplied the reproducible evidence.

## Reproduction details

Commands run from the integration root with its own environment:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_m14_quant_audit.py
.venv/Scripts/python.exe scripts/m14_quant_audit.py
.venv/Scripts/python.exe scripts/m14_g5_folds_and_peers.py
```

The scripts import main's source and write only ignored local audit output. The
original versions in Gemini hardcode both roots and do not actually implement the
documented `--repo-root` argument; their prose command examples are not proof of
argument handling. The imported versions use the repository containing the script.
The original 10-test source and pre-fix modules are preserved; corrected tests
invert the demonstrated defect assertions into precise safety invariants, rather
than retaining requirements that bugs continue to exist.

Saved comparison: `artifacts/m14-joint/reproduction-comparison.json`.
Input data: 17,110 bars, 196 observed sessions, Jan2–Nov10 2026; all original
publication timestamps absent. Research replay bounds are assumptions, not
recovered historical publication times.

## Actual engineering delegation

Codex invoked two actual collaboration tasks, `identity_repair` and `pit_repair`,
with exclusive module ownership, then cross-assigned read-only reviews. Additional
bounded risk/coverage and sparse-evaluation repairs were assigned explicitly.
These are Codex specialists, not Gemini. Their findings on alias gaps, dated
resolution, suspension IDs, metadata-only fingerprinting, scope branches and
cost-price valuation were integrated by the lead. No callable Gemini session was
invoked by Codex. A separate self-contained follow-up is supplied for Antigravity.

## Acceptance and trust verdict

See [correctness fixes](M14_QUANT_CORRECTNESS_FIXES.md),
[corrected results](M14_CORRECTED_STRATEGY_RESULTS.md), and
[next research gates](M14_NEXT_RESEARCH_GATES.md) for final validation and limits.
The original research engine cannot be trusted as validated predictive or
competition-exact evidence. Corrected outputs remain retrospective research, with
explicit source-availability, corporate-action, sample-size and selection limits.
No model promotion, account confirmation, autonomous order, deployment or remote
push is implied by this integration.

## Final acceptance evidence

- `uv run python scripts/check.py`: exit0, **516 passed**, one Starlette
  deprecation warning, 103.21s;94 files formatted, Ruff clean, mypy37 modules
  clean,10 skills validated. Earlier 504/510 passes were intermediate trees;
  the final516 result supersedes them. No test deletion or assertion relaxation.
- `npm.cmd run typecheck` in frontend: exit0. Current-source Next15.5.29 production
  build in a disposable copy: exit0,13 static entries generated; original local
  frontend build/runtime left in place. The final type-only addition accepts
  `INSUFFICIENT_EVIDENCE`; it changes no rendered JavaScript behavior.
- Chrome157.0.8103.39: prototype and nine-page production fixture suites PASS.
  Desktop/mobile prototype screenshots and interaction evidence are under
  `artifacts/m14-joint/screenshots`; JSON in `artifacts/m14-joint/browser-results.json`.
  Authenticated competition capture remains untested.
- Paired cold performance: five alternating reference/reuse pairs, identical
  responses, no protected files changed, zero external attempts. Browser's real
  copied-data callbacks:77 successful API responses, zero runtime errors,
  external requests or write requests. See the performance table in the results
  report; this is not a production SLO or a41.96% whole-app speedup.
- Immutable corrected experiment `m14_correctness_192f2d93ee102f6e` completed with
  all27 consumed-source/data/config/harness hashes unchanged during its run.
  Final input and preservation hashes are recorded in ignored local manifests.
- Final preservation: all16 account JSONs unchanged, no additions; real ledger
  matches the starting SHA. Original data.py, test_gateway.py and the coupled
  pipeline review-test bytes match session start. All nine Gemini research
  originals remain unchanged in its worktree. A sanitized, committed summary is
  [M14_JOINT_VALIDATION.json](evidence/M14_JOINT_VALIDATION.json); full private
  runtime copies and source/experiment artifacts remain ignored local evidence.

## Local commits and remaining working-tree scope

1. `62fa30d` — imported independently reproduced Gemini evidence.
2. `149bc03` — research identities, scopes, cutoffs, source/unknown semantics,
   numerical/evaluation contracts and regression tests; includes reviewed P0 guards.
3. `641cb2d` — immutable validation reuse and audit harnesses. Data staging used a
   checked, validation-only index patch; source-refresh user hunks and their import
   remain unstaged. Source-refresh review tests stay alongside that uncommitted work.

The final documentation commit is recorded in Git history. No push occurred.
Tests certify the recorded **working tree**, which includes preserved user pipeline
and gateway-test edits; they are not a claim of a clean-checkout516-test result for
one SHA alone. `.vscode/` and unrelated user work are not staged. Gemini's old sync
files and research originals remain in its worktree; no branch merge was used.
