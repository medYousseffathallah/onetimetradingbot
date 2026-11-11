# Milestone 14 performance audit

Owner: Codex performance specialist (`/root/m14_perf`), not Gemini.
Measured `2026-11-11T13:30:12.220675+00:00` against the current dirty main working tree
based on `6f0b64d`; the P0 and M14 API changes are not in that commit alone.
No production decisions or cache behavior changed by this performance task.

## Verdict and scope

**PASS**: 21/21 measured routes returned HTTP 200 for every cold/warm call and
warm p95 was below the 500 ms audit target. Worst warm p95: **304.575 ms**
(`/api/holdings`). **PASS**: all four controlled cache checks. **PASS**: all
61 hashed account/config/market/source files unchanged. External connection
attempts: **0**. Windows asyncio created **1 internal loopback socketpair**.

The older report's tighter `<180 ms` warm range was **not reproduced**: holdings
304.575 ms, rankings 222.643 ms and paper trading 250.320 ms exceeded it.
Do not claim a performance improvement from this audit. Different dataset,
transport, sample count and machine load prevent a direct before/after speedup.
Cold load remains a material limitation: state build **5,717.487 ms** and some
cold API routes **2.38-6.58 seconds**. No cold-load optimization was implemented.

This is **in-process FastAPI TestClient**, not TCP-server startup, Next.js render,
browser load or interactive navigation. The lead separately owns browser tests.
No external competition synchronization or trade confirmation was attempted.

## Reproduction and preserved evidence

```powershell
.venv/Scripts/python.exe scripts/m14_perf_audit.py --samples 8 --output artifacts/m14/performance.json
```

Artifacts (ignored local storage): `artifacts/m14/performance.json` contains every
sample, statuses, payload sizes, profile and cache verdict; `performance-inputs.json`
contains source/input and harness hashes captured after the run, whose source
preservation check passed. No response bodies, account balances, tokens or
credentials are in those outputs.

Environment: Windows 10 build 19045, Python **3.13.18**,
**4** logical processors. The lead suspended
its tests/builds while timing; background user applications were not controlled.
Current copied EOD data has 17,110 bars through **2026-11-10**. Import timing is one
fresh interpreter sample; route order is fixed. Eight warm samples provide a
local smoke-level p95, not a production latency SLO or confidence interval.

## Isolation and protocol

The harness copies runtime account/market inputs, configs and saved research
artifacts into a disposable working directory under `artifacts/m14/`. It never
copies browser profiles, cookies, .env or pairing-token files. Mutable ledger,
alert, job, staging, paper-journal and pairing paths resolve inside the disposable
tree. It sets `BVMT_ALLOW_LIVE_LLM=0`, rejects external socket connects and all
urllib calls, and hashes source files before/after. No installs or paid APIs.

Each route is measured after clearing all registered application caches, then
again eight times warm. "Cold" here means **application-cache cold with OS file
cache retained**; it is not disk-cold boot. Interpreter import is not repeated
for each route. p50 is median; p95 uses nearest rank (with n=8, the maximum).
The 500 ms warm threshold was fixed in the harness before execution.

The first sandbox attempt failed before timing because Windows denied creating
nested temporary directories. The approved rerun exposed a harness error:
blocking all sockets also blocked Windows asyncio's wake-up socketpair. It was
corrected to allow loopback only and to leave the temporary CWD before cleanup
on exceptions. The final successful run above supplies all reported metrics.
No numbers from failed attempts are counted as endpoint measurements.

## Startup and state measurements

| Measurement | ms | Samples / definition |
|---|---:|---|
| Import API plus TestClient | 3537.205 | 1 fresh interpreter; excludes process startup |
| `create_app` | 226.064 | isolated configured service |
| Cold state build | 5717.487 | all registered caches cleared |
| Warm state p50 | 17.946 | 8 calls |
| Warm state p95 | 26.737 | nearest rank |

## Route measurements

All route statuses were 200. The verdict column is against warm p95 <500 ms;
a PASS does not mean the cold response was fast or the financial evidence valid.

| Route | Cold ms | Warm p50 ms | Warm p95 ms | Payload bytes | Verdict |
|---|---:|---:|---:|---:|---|
| `/api/health` | 3356.944 | 57.163 | 64.336 | 5,288 | PASS |
| `/api/overview` | 3825.775 | 27.874 | 31.657 | 1,492 | PASS |
| `/api/holdings` | 5817.864 | 199.592 | 304.575 | 2,293 | PASS |
| `/api/snapshots` | 6578.437 | 53.514 | 104.727 | 4,819 | PASS |
| `/api/transactions` | 5978.416 | 22.258 | 27.568 | 19 | PASS |
| `/api/orders/pending` | 3424.212 | 26.227 | 58.500 | 21 | PASS |
| `/api/market-status` | 3306.134 | 87.276 | 100.184 | 381,544 | PASS |
| `/api/rankings` | 3474.638 | 185.956 | 222.643 | 382,283 | PASS |
| `/api/market-research` | 2451.213 | 19.270 | 24.163 | 110,066 | PASS |
| `/api/research?include_strategy_comparison=false` | 3323.883 | 45.079 | 51.426 | 119,699 | PASS |
| `/api/research` | 3792.785 | 112.392 | 122.945 | 554,707 | PASS |
| `/api/strategy-lab` | 62.425 | 59.880 | 115.540 | 435,349 | PASS |
| `/api/paper-trading` | 1430.112 | 185.579 | 250.320 | 212 | PASS |
| `/api/session/summary` | 5.573 | 4.220 | 4.941 | 7,061 | PASS |
| `/api/trade-plans?universe=TUNIS_BOURSE_CHALLENGE` | 3895.205 | 126.385 | 134.581 | 332,767 | PASS |
| `/api/holding-periods?universe=TUNIS_BOURSE_CHALLENGE` | 3739.993 | 5.785 | 6.221 | 4,094 | PASS |
| `/api/trading-intelligence` | 2499.964 | 27.824 | 37.436 | 21,553 | PASS |
| `/api/sync/preview` | 2383.480 | 16.677 | 21.820 | 771 | PASS |
| `/api/glossary` | 4.814 | 4.442 | 5.236 | 33,309 | PASS |
| `/api/challenge-universe` | 5.782 | 4.082 | 5.112 | 24,529 | PASS |
| `/api/market-data/status` | 720.679 | 22.790 | 27.660 | 521 | PASS |

## Cold bottleneck investigation

A separate post-measurement cProfile pass rebuilt state. Profiled times include
profiler overhead and are **not additive** (parent cumulative values include
children); they must not replace the unprofiled latency values above.

| Source and function | Calls | Cumulative ms (profiled) |
|---|---:|---:|
| `portfolio_service.py:227` `load_state` | 1 | 5760.092 |
| `dashboard.py:460` `build_dashboard_state` | 1 | 5714.221 |
| `data.py:288` `read_bars_csv` | 2 | 2340.372 |
| `data.py:192` `validate_bar` | 85,550 | 2032.936 |
| `data.py:235` `_parse_canonical_row` | 17,110 | 1616.451 |
| `data.py:221` `validate_bars` | 3 | 1187.083 |
| `calendar.py:472` `evaluate_coverage` | 1 | 666.356 |
| `research_coverage.py:225` `evaluate_market_research_coverage` | 1 | 498.769 |
| `features.py:117` `rank_session_baseline` | 1 | 460.409 |

`validate_bar` executes **85,550 times for 17,110 bars**, about five passes per
bar, through canonical parsing and downstream `validate_bars` boundaries.
`read_bars_csv` accounts for roughly 2.34 s in the profiled state build; coverage,
research-coverage and session-ranking evaluation add distinct work. Repeated
validation/research construction explains an important part of cold cost.

A bounded next experiment is to measure an immutable validated market artifact
shared across these functions, keyed by complete input/config/cutoff identity.
Keep validation at untrusted boundaries; do not simply remove validation or
weaken assertions for speed. Any optimization needs a separate diff and tests
for file changes, revised data, cutoff changes and mutable-return isolation.

Payload review: `/api/rankings` is 382,283 bytes; trade plans 332,767 bytes; market
status 381,544 bytes; full research 554,707 bytes. Even research without strategy
comparison is 119,699 bytes because sparse explanations remain. A later contract
review can evaluate instrument-scoped explanation loading and pagination, without
hiding missing-data warnings. No such production change was made here.

## Cache and timestamp contracts

Controlled probes in copied runtime files passed:

- Consecutive warm state calls reused the state object.
- A content change to copied ledger metadata invalidated state.
- Adding a duplicate copied snapshot under a new filename invalidated state.
- Explicit global cache-generation invalidation forced a fresh state.

`PortfolioStateService.load_state()` fingerprints ledger, bars, calendar,
master, configs, alerts, snapshot directory and processed dataset discovery.
Warm calls retain fingerprint/discovery I/O for correctness. Small mutable files
are content-hashed each time. Large CSV hashes cache by path/size/mtime; a
malicious equal-size rewrite with restored mtime can evade that shortcut. This
is an existing threat-model limitation, not behavior weakened by M14.

Data cutoff is **2026-11-10T17:00:00+01:00**. Quote age is relative to
the EOD dataset cutoff and does not prove current executable market freshness.
Dashboard replay bounds are research assumptions where official intraday times
are missing. Neither successful HTTP responses nor fast latency verify rules,
point-in-time publication availability or the unconfirmed account state.

## Reliability finding delivered to the lead

Before measurement, `/api/market-data/status` called `gateway.get_status()` whose
default is `probe_remote=True`; unlike `/api/health`, it could probe the external
provider on an ordinary GET. This was identified statically, with no network
call. The lead added explicit `check_remote=False` default and verified two
regressions before this run. The measured default route completed without any
external attempt. The lead owns that production change and test evidence.

Holding-period analysis uses default dataset paths independently of a custom
portfolio service. This mirror keeps those paths identical for comparison; a
custom-data UI should not assume the route follows its selected dataset without
an explicit contract. No baseline results or decision thresholds were changed.

## Exclusions and verification

`docs/PERFORMANCE_AUDIT.md` describes a previous 15,968-bar/194-session snapshot,
three warm samples and other transport/browser measurements. It is historical
context, not an independent rerun by Gemini and not an apples-to-apples baseline.
Pairing-token responses were excluded to avoid inspecting auth material. Remote
health probes and every mutation route were excluded. Actual live browser sync,
trade confirmation and production-browser performance are **NOT TESTED by this
harness**.

`ruff format scripts/m14_perf_audit.py` and `ruff check` on the script: **PASS**.
Harness exit code: **0**. Final full repository gate and independent browser
verification are owned by the Codex lead and recorded in its integration report.
