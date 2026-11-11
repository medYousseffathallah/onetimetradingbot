# M14 browser synchronization acceptance checklist

Status: NOT TESTED for the authenticated competition session. Codex has not
logged in, captured new account pages, confirmed pending snapshots or submitted
trades. Existing automated P0 synchronization tests are separate evidence.

## Entry criteria

- Operator is present and chooses the intended local account and competition
  edition. Confirm correct localhost UI/API; never use a public deployment.
- Record code revision plus dirty-source hashes, Browser Companion version and
  capture schema. Check Chrome/Edge and localhost reachability separately.
- Preserve ledger/snapshots byte hashes locally; never paste full account JSON,
  credentials, cookies or pairing tokens into reports or prompts.
- Show current confirmed snapshot time, latest pending capture time, EOD market
  session, source retrieval time and unknown intraday quote time separately.
- Display rule evidence blockers; a successful account sync does not clear rules
  or make EOD prices executable. Do not use empty history to mean no orders.

## User-assisted read-only capture (not run by this task)

1. In the user's authenticated browser, verify the account on displayp.aspx.
   Navigate only read-only pages; no buy/sell/cancel forms.
2. Configure local pairing in the extension without logging/copying its token
   into evidence files. Check extension permissions and intended localhost port.
3. Extract the holdings table. Operator compares each displayed identity/ISIN,
   quantity, acquisition amount, latest displayed price, market value and gains.
   Check French decimals, thousands separators, action-column skips and totals.
4. Independently compare cash plus holdings with displayed equity. Preserve
   unknown fields; any reconciliation failure blocks ingestion/confirmation.
5. Capture display_histo.aspx movements and pending orders. Verify executed,
   partial, pending, rejected and cancelled statuses, sides, quantities, prices,
   fees and timestamps. Confirm that absent history means unverified, not zero.
6. Transmit to local staging only. Closing the popup must not lose a reported
   upload; upload errors must not display success. Repeated identical capture
   must deduplicate without ledger fills or duplicate account history.

## Preview-only acceptance

- UI surfaces the newest unconfirmed valid capture after reload/restart.
- Read-only preview separates website-reported values from locally calculated
  EOD values and lists all identity/cash/quantity/order/fee discrepancies.
- Portfolio mode isolation holds: demo data cannot replace the real account.
- A new capture between preview and confirmation causes a snapshot-ID conflict;
  errors, rejected captures and corrupt newest files are clearly surfaced.
- Snapshot freshness is based on observed capture time, not local import time.
- Pending verification blocks actionable quantities across ranking, planning
  and multi-horizon views. Local scores remain available as research evidence.
- Compare protected hashes: no confirmed ledger/account file changed during
  capture/preview. Staging additions are expected only after explicit capture.

## Protected action boundary

STOP before Confirm & Apply. This milestone provides a checklist, not approval
to confirm a snapshot, reconcile pending trades or overwrite confirmed state.
Only the operator can authorize a specific reviewed snapshot and discrepancy
set. If later authorized, use the exact expected_snapshot_id and recheck totals,
transaction/pending verification, idempotency and hashes afterwards. This step
remains NOT TESTED here and must never be inferred from unit-test success.

## Recovery and evidence

Exercise stale login, unavailable extension, CORS/pairing rejection, malformed
paste, duplicate capture, failed background job and restart persistence only in
isolated fixtures unless the operator explicitly authorizes a live attempt.
Manual CSV/paste is a fallback; never bypass challenge access restrictions.
Record PASS/FAIL/NOT TESTED per step, timestamp, version, sanitized discrepancy
counts and local evidence path. A live operator sign-off is still required.
