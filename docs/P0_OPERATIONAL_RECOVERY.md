# P0 Operational Recovery - 2026-11-11

## Verified starting state

- Integration root: `C:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit`.
- CLI: `codex-cli 0.167.1` (actual `codex --version`). Active model was not
  exposed by the version output or the checked top-level model configuration.
- `main`: `6f0b64dcdf36071b136bd729f89bae5778088516`; uncommitted
  `src/bvmt/data.py` and `tests/test_gateway.py` preserved without editing.
- `codex/data-research`: `4a57b441c3322b33ac3c4fbd5cdd3d1fb5066a16`, clean.
- `gemini/dashboard`: `fdfae2a228c919793f1c125bbe2b61a3a74f60f9`, dirty
  `src/bvmt/playwright_worker.py` and `src/bvmt/portfolio_service.py`; untouched.
- `where.exe gemini` found no command. No Gemini invocation occurred.
- Local canonical bars: 17,110 records through 2026-11-10; calendar: 196
  observed sessions through 2026-11-10. All 17,110 publication timestamps are
  absent. This is EOD evidence, not a current intraday quotation feed.
- Latest confirmed ledger capture: 2026-11-10T09:21:29.393000+00:00.
  Later snapshots remain pending, including 2026-11-10T11:07:02.522000+00:00.
  Ledger transaction-history and pending-order verification flags are false.
  Repeated historical confirmation entries were observed; no account repair
  or deduplication was applied to the private ledger.

## Execution plan and implemented API slice

1. Preserve existing files and account artifacts; add offline failure cases.
2. Guard real-account rankings, overview actionable count, both planner routes
   and multi-horizon intelligence against unverified competition rules, nonmembers, conflicting IDs, absent,
   future or stale quote evidence, pending sync and unverified account history.
3. Verify targeted and full quality gates; document the remaining owned UI task.

The API now reports zero actionable shares and explicit blockers when these
checks fail. Blocked plans also zero order notional and fees, retain effective
cash, and retain existing exposure. A user-entered limit is separate from the
observed reference price; missing reference prices and quote ages remain null.
Session dates are displayed without the previous invented 16:00 quote time.
`current_quote_timestamp` remains null because no intraday evidence exists.
The frontend contract accepts these null values and explains missing quote age.

Mapping checks reject contradictory symbol/ISIN/displayed-symbol combinations,
including unknown primary names and known aliases. Challenge classification
requires supplied identifiers to agree. Registry membership no longer asserts
static `FRESH` quote status. The mapping document now agrees with the existing
registry for TJL/TLS and the TJARI/TRE/WIFAK ISIN entries. This is a consistency
check against saved code, not an independent official-source verification.

Test changes strengthen the contract: the old API assertion requested positive
STA sizing with no STA evidence, now explicitly blocked; two planner fixtures
used a different ISIN for STA and were corrected to the existing registry value
while their positive sizing and insufficient-cash assertions remain unchanged.

## Ownership and Gemini worktree handoff (not executed)

**Task G-P0: apply operational recovery semantics to legacy Streamlit views.**
Target: `C:/Users/Thinkcenter/Desktop/BVMT/bvmt-gemini-dashboard`,
branch `gemini/dashboard`. Preserve its two existing uncommitted files first;
do not reset, merge over, or discard them. The primary integrator owns the API
contract and final integration review on main.

- Owner files: `src/bvmt/dashboard.py`, `src/bvmt/recommendations.py`,
  `tests/test_milestone_1c.py`; avoid unrelated ledger changes.
- Bring the new API recovery contract to Streamlit presentation and explain
  pending synchronization, missing quote timestamps and non-challenge research.
- Acceptance: nonmembers and unresolved quotes cannot display actionable
  competition quantities; pending snapshots show review-required status;
  null timestamps stay unknown; research rankings remain available.
- Use temporary portfolio fixtures; full offline gate required before review.
- Forbidden: account snapshot replacement, confirming pending trades or syncs,
  autonomous orders, paid APIs, pushes, or editing the other worktree's files.
- This is a documented worktree task, not a claim that Gemini ran or that the
  legacy Streamlit path has received the API presentation guard.

A Codex read-only reviewer was actually invoked through collaboration tools;
its findings on identity conflicts, plan arithmetic and future quote evidence
were addressed. This reviewer was not Gemini.

## Preservation and limitations

Ignored local preservation evidence is in `artifacts/p0-recovery/`: original
bytes for the two user files and SHA-256 hashes for them plus all 15 existing
account JSON files. The real ledger hash is
`0a1b86cb281187a0e9ab88a4cde6d4de173a5df162111266ce1988dcbf91d395`.
No account files were overwritten, snapshots confirmed, orders submitted,
branches pushed or paid APIs called.

Quote freshness is relative to the dataset decision cutoff. A zero EOD quote
age does not establish current market freshness. Live Browser Companion and
manual account confirmation remain user-assisted acceptance work. The account
remains operationally blocked until evidence is reviewed and verified.

## Validation

- Initial failure evidence: unguarded nonmember BUY signal, positive plan size
  without quote evidence, and fabricated 16:00 timestamp reproduced offline.
- `python -m pytest -q tests/test_operational_recovery.py`: 14 passed.
- `npm.cmd run typecheck` (frontend directory): exit 0.
- Synthetic demo: exit 0, execution_authorized false; output retained under
  ignored `artifacts/p0-recovery/demo-report.json`.
- Rules check: exit 2 as expected, 72 evidence blockers, execution_authorized false.
- Final `uv run python scripts/check.py`: exit 0; format 75 files, Ruff clean,
  mypy 35 source files clean, 10 skills valid, **439 tests passed**, 1 Starlette
  deprecation warning in 157.52s.
- `git diff --check`: exit 0. Final preservation check: 17/17 hashes unchanged.

The first pytest attempt hit Windows temporary-directory permissions; an
approved rerun executed the tests. No dependency installs were needed.
