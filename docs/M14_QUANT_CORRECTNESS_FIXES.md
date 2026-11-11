# M14 quantitative correctness fixes

## P0-A — holding-period universe

Reproduced 15/42 matching from comparing canonical instrument IDs with Challenge
symbols. The corrected research projection uses the saved registry's exact ISIN
identity, filters before metrics/simulation, and reports all 42 membership rows
separately from instruments having usable observations. Usability at least once
does not mean current eligibility, complete coverage or statistical sufficiency.
Hardcoded 194-session/return narratives were removed; unknown exchange times use
an explicit EOD replay convention rather than midnight or an asserted official close.

## P0-B — POULINA identity

Registered ISIN `TN0005700018` links `POULINA_GROUP_HOLDING` (68 observations,
Jan2–Apr8) and `POULINA_GP_HOLDING` (128, Apr10–Nov10). Calculations use an in-memory
canonical projection. Original symbols, source IDs, timestamps and raw files remain.
Alias evidence exposes observed ranges and declared validity separately. Conflicting
ISINs, overlapping canonical/session rows, unsupported disjoint validity/listing
unions and out-of-period aliases reject rather than silently merge. Suspension IDs
use the same canonical mapping. Coverage, baseline, sparse research and strategy
studies must share this identity boundary.

## P0-C — decision cutoffs and event truth

Removed fixed November6 evaluation cutoff. Multi-horizon accepts an explicit aware
`decision_timestamp`; API passes its actual research cutoff. Date-only compatibility
uses conservative Tunisia start-of-day and cannot include later same-day events.
Unknown, malformed or naive publication times are excluded. Macro API uses the
same cutoff. Static catalog entries are labeled `UNVERIFIED_CATALOG`; temporal
filtering does not independently verify their asserted financial facts. Generic
input rankings/positions no longer receive hardcoded official/live provenance.

Original future-event narratives are invalidated. A–I price-only backtests do not
consume these macro inputs, so their numerical returns are not automatically
invalidated by this particular leakage; their shared identity/scoring/availability
paths require separate reruns, supplied in the results report.

## P0-D — bounded numerical scoring

Original flat/spike fixture: momentum20=0, momentum60=.25, denominator=1e-6,
score=125000; normal score=16.762861. New version `bounded_risk_ratio_v2` uses
`b(x,v)=x/hypot(x,v)` with `b(0,0)=0`; the momentum score is the mean of the two
bounded terms. It is the monotone transform of a risk ratio, bounded in [-1,1],
scale invariant and requires no fitted or arbitrary volatility floor. It changes
the research formula and therefore has a new version; historical results remain.
H/I downside and drawdown ratios use bounded terms too. True flat volatility can
be zero; too few observed returns are excluded rather than called stable prices.
Nonfinite inputs reject. Sparse scores were already bounded, but their distinct
units/formula are not represented as the same calibrated scale.

## P0-E — scope before selection and budgets

Explicit Challenge scope filters membership before baseline ranking, recommendation
top-buy counting/cash allocation, sparse top-k and scientific outcome maps. Full
BVMT research remains available separately. API scope must propagate into both
rankings and sparse explanations, including explicit Challenge scope in paper/demo
mode. Nonmember diagnostic rows may remain visible as excluded, with no ranked
candidate slot or allocation. Final-order blocking alone was insufficient.

## P0-F — missing evidence and evaluation semantics

- Explicit percentage fields preserve zero; ratio momentum is multiplied by100.
- Missing turnover no longer becomes fabricated 10000 TND liquidity.
- Missing position quotes cannot become acquisition cost reference prices.
- Unknown quotes/ages remain null; API missing-equity evidence cannot become a
  fabricated portfolio balance. Zero capacity is a constraint, not an observed price.
- Fixed future review dates and arbitrary quantity100 defaults were removed.
- D and F share ordering whenever enough stocks exceed the cross-sectional mean:
  subtracting a common benchmark preserves rank. They remain separately reported
  historical hypotheses, not counted as independent evidence of robustness.
- Original missing publication metadata remains unknown on disk. EOD replay is
  explicitly hypothetical and cannot certify historical information availability.
- Sparse evaluator now requires exact horizon exit observations, whole-slice
  entry/exit capacity and in-range prices. Unavailable outcomes are not losses or
  zero returns. Precision/FPR/mean share one executable-known denominator, with
  evaluated and unevaluated counts disclosed; missed opportunities use executable
  winners. Baseline liquidity thresholds match the same frozen configuration.
- Sparse compounded portfolio return/drawdown remain null without an actual cash
  and position timeline. This removes overlapping-horizon pseudo-performance.

The proposed coverage relaxation, directional awakening rule and new fundamental
factors remain experiments, not correctness fixes or accepted predictive gains.

Unverified static catalog entries are also excluded from sparse catalyst counts and
the event score bonus; labeling alone was insufficient. They remain inspectable as
unverified catalog context. `m14_scope_identity_source_v2` identifies the corrected
sparse wrapper separately from its unchanged configuration. Known publication and
ingestion timestamps are preserved during replay; only missing-publication rows
receive the explicitly hypothetical replay convention. No ICF catalyst is invented.

Sparse explanation caches include ledger content/equity, frozen configuration,
source hashes, cutoff, scope and generation; pending reservations are passed through.
Both GET and POST planning paths propagate scope. An empty matching universe returns
`INSUFFICIENT_EVIDENCE` instead of failing or inventing a holding-period result.

## Validation reuse

Private proofs retain exact immutable row identities with strong references,
validation version and global generation. Parser versions/content fingerprints
invalidate file caches; config/cutoff research decisions are recomputed outside
the validation proof. Duplicate/empty coverage diagnostics and defensive lists
are preserved. Same-size source rewrites with restored mtime now invalidate both
file and sibling-discovery fingerprints through content hashes. Validation was
not removed. Paired cold API measurements must be read independently of the
earlier 41.96% validation-only microbenchmark.

## Test evidence

Original 10 characterization tests passed before repairs. Focused identity,
cutoff, bounded-score, source-mutation, route-scope and executable-outcome tests
exercise the corrected contracts. Intermediate full gate: 504 passed; later review
hardening requires the final gate recorded in the joint integration review/state.
Old tests expecting future macro events or official provenance for arbitrary
fixtures were replaced with exact exclusion/source-status assertions. No unrelated
assertions or account-reconciliation checks were loosened.

Final full gate: **516 passed**, one deprecation warning; Ruff/format/mypy/skills
all clean. Typecheck and isolated final-source production build passed. Browser
fixture/prototype checks passed. An old ICF test expected at least one catalog event
without supplying a verified disclosure; it now asserts exact zero and
`NO_VERIFIED_EVENTS`, consistent with the newly enforced source boundary.
