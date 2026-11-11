# M14 corrected strategy results

## Interpretation and status

All comparisons are **retrospective, contaminated, research-conservative price-return
studies**, not verified competition performance, total returns or a pristine holdout.
No model is promoted. Missing publication/first-availability timestamps, incomplete
historical universe evidence, absent corporate-action adjustments and a short 2026
sample prevent a validated predictive-edge claim.

Original experiment records remain intact. The corrected harness writes a new
hash-addressed experiment file and refuses to overwrite an existing result. It
hashes source, data, configuration and harness, checks for changes during the run,
and discards a mixed run. One intermediate run was deliberately rejected by this
check because final review repairs changed source while it was executing; no
numbers from that discarded run are reported as accepted results.

## Independently reproduced original claims

The original Gemini audit JSON, fold/peer JSON and Challenge accounting JSON
reproduced exactly (generation timestamp excluded where present).

| Original study | G marked return | G ex-top-winner return | C benchmark |
|---|---:|---:|---:|
| Full BVMT, through Nov6 (194 sessions) | 18.811715% | 7.431954% | 14.026112% |
| Full BVMT, through Nov10 (196 sessions) | 19.256070% | 7.857788% | 14.653892% |
| Challenge42, through Nov10 (196 sessions) | 19.424436% | 7.040627% | 14.653892% |

The reported “19.42%, 7.86% excluding SOTETEL, 14.65% benchmark” combines the
Challenge return with the **full-market** ex-top-winner number. It is not one
consistent-scope comparison. This matters independently of subsequent formula fixes.

## Corrected experiment contract

```powershell
.venv/Scripts/python.exe scripts/m14_joint_research_evaluation.py --sparse
```

Corrected identity and `bounded_risk_ratio_v2` scoring apply to all shared A–I
paths; baselines are rerun rather than compared with stale cached results. Tables
are separated by Full BVMT/Challenge and Nov6/Nov10 cutoff. The latest-date studies
also run every start phase for cadence5/10/20 and repeat without SOTETEL. Detailed
outputs include returns, liquidation estimates, drawdown, utilization, fees, fill/
order counts, outlier contributions and all phase samples.

Top-k diagnostics use later-session entry, exact ten-session exits, identical
known-outcome denominators and disclosed feasibility/unknown counts. Missed
opportunities use an explicitly stated executable-net-winner definition. Selection
precision is distinct from sold-slice hit rates in the portfolio simulator.

Sparse selection/configuration remains the frozen model; the evaluator is versioned
`executable_cohort_evaluation_v2`. Exact entry/exit feasibility, matching liquidity
thresholds and null unsupported compounded performance replace the old evaluator's
mixed-denominator and overlapping-capital numbers. Sparse portfolio return/drawdown
remain unavailable until a real joint cash/position timeline is implemented; an
average executable sleeve return is not a portfolio return.

## Rejection and promotion

No historical table here supplies independent confirmation. D/F ordering equivalence
does not create another independent strategy. Removing one historical winner is a
descriptive stress test, not an unbiased model-selection rule. All hypotheses,
scopes, phases and failed/unknown outcomes must remain visible. Prospective locked
signals and independent review are required under
[the next gates](M14_NEXT_RESEARCH_GATES.md).

The numerical tables below are from the accepted final-source run. Three earlier
in-flight runs were discarded by source-change checks during review; none supplied
accepted results. Their failed status is not hidden or relabeled as validation.

## Accepted corrected results

Experiment: `m14_correctness_192f2d93ee102f6e`. Local immutable artifact: `artifacts/m14-joint/corrected-192f2d93ee102f6e.json` (SHA-256 recorded in the final manifest). All source/input checks passed.

### Portfolio simulation results

| Scope / cutoff | Model | Net % | Liquidated estimate % | Max DD % | Active utilization % | Fees TND |
|---|---|---:|---:|---:|---:|---:|
| FULL_BVMT_2026-11-06 | A | 0.0000 | 0.0000 | 0.0000 | 0.00 | 0.00 |
| FULL_BVMT_2026-11-06 | B | 15.3106 | 14.7455 | 18.0984 | 94.41 | 660.34 |
| FULL_BVMT_2026-11-06 | C | 15.1024 | 14.6783 | 13.4286 | 72.70 | 346.89 |
| FULL_BVMT_2026-11-06 | D | 17.0506 | 16.9027 | 5.3533 | 26.81 | 1192.79 |
| FULL_BVMT_2026-11-06 | E | 13.8536 | 13.7591 | 8.3148 | 30.01 | 878.96 |
| FULL_BVMT_2026-11-06 | F | 17.0506 | 16.9027 | 5.3533 | 26.81 | 1192.79 |
| FULL_BVMT_2026-11-06 | G | 18.9754 | 18.8927 | 5.1066 | 25.92 | 1422.58 |
| FULL_BVMT_2026-11-06 | H | 11.3272 | 11.2129 | 6.5125 | 30.37 | 1401.86 |
| FULL_BVMT_2026-11-06 | I | 12.3076 | 12.2967 | 5.5822 | 25.85 | 1237.71 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | A | 0.0000 | 0.0000 | 0.0000 | 0.00 | 0.00 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | B | 15.3106 | 14.7455 | 18.0984 | 94.41 | 660.34 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | C | 15.1024 | 14.6783 | 13.4286 | 72.70 | 346.89 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | D | 17.2308 | 17.1251 | 6.5239 | 31.46 | 1300.85 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | E | 13.8677 | 13.7731 | 8.3139 | 31.69 | 963.48 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | F | 17.2308 | 17.1251 | 6.5239 | 31.46 | 1300.85 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | G | 18.6482 | 18.5357 | 4.8835 | 25.42 | 1379.68 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | H | 11.4254 | 11.3445 | 6.5125 | 29.49 | 1368.11 |
| TUNIS_BOURSE_CHALLENGE_2026-11-06 | I | 12.3076 | 12.2967 | 5.5822 | 25.85 | 1237.71 |
| FULL_BVMT_2026-11-10 | A | 0.0000 | 0.0000 | 0.0000 | 0.00 | 0.00 |
| FULL_BVMT_2026-11-10 | B | 15.9773 | 15.4032 | 18.0984 | 94.47 | 673.30 |
| FULL_BVMT_2026-11-10 | C | 15.6825 | 15.2554 | 13.4286 | 72.72 | 346.89 |
| FULL_BVMT_2026-11-10 | D | 17.6130 | 17.5075 | 5.3533 | 26.68 | 1315.17 |
| FULL_BVMT_2026-11-10 | E | 13.9420 | 13.9201 | 8.3148 | 29.63 | 994.64 |
| FULL_BVMT_2026-11-10 | F | 17.6130 | 17.5075 | 5.3533 | 26.68 | 1315.17 |
| FULL_BVMT_2026-11-10 | G | 19.4206 | 19.3367 | 5.1066 | 25.75 | 1458.38 |
| FULL_BVMT_2026-11-10 | H | 11.4898 | 11.4080 | 6.5125 | 30.14 | 1530.51 |
| FULL_BVMT_2026-11-10 | I | 12.3083 | 12.2974 | 5.5822 | 25.50 | 1237.71 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | A | 0.0000 | 0.0000 | 0.0000 | 0.00 | 0.00 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | B | 15.9773 | 15.4032 | 18.0984 | 94.47 | 673.30 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | C | 15.6825 | 15.2554 | 13.4286 | 72.72 | 346.89 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | D | 17.3586 | 17.2554 | 6.5239 | 31.26 | 1447.91 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | E | 13.6997 | 13.6518 | 8.3139 | 31.35 | 1106.26 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | F | 17.3586 | 17.2554 | 6.5239 | 31.26 | 1447.91 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | G | 18.5995 | 18.5527 | 4.8835 | 25.17 | 1445.39 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | H | 11.4412 | 11.3727 | 6.5125 | 29.24 | 1475.84 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | I | 12.3083 | 12.2974 | 5.5822 | 25.50 | 1237.71 |

### G phase and outlier stress tests

| Scope | Cadence | Minimum % | Median % | Maximum % | IQR pp |
|---|---:|---:|---:|---:|---:|
| FULL_BVMT_2026-11-10 | 5 | 6.8714 | 11.5235 | 18.6794 | 3.6337 |
| FULL_BVMT_2026-11-10 | 10 | 2.6303 | 9.3248 | 19.6215 | 2.2399 |
| FULL_BVMT_2026-11-10 | 20 | 2.8206 | 9.3319 | 17.3438 | 8.9888 |

Whole-universe exclusion of SOTETEL, FULL_BVMT_2026-11-10: G net **6.3468%**. This differs from an arithmetic subtraction of the old winner contribution.

| Scope | Cadence | Minimum % | Median % | Maximum % | IQR pp |
|---|---:|---:|---:|---:|---:|
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | 5 | 4.6764 | 10.7149 | 15.1782 | 3.6849 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | 10 | 1.7294 | 8.6536 | 17.7168 | 4.5786 |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | 20 | 2.4228 | 8.2956 | 17.3949 | 7.2912 |

Whole-universe exclusion of SOTETEL, TUNIS_BOURSE_CHALLENGE_2026-11-10: G net **8.0331%**. This differs from an arithmetic subtraction of the old winner contribution.

### Candidate diagnostics

Fixed ten-session forward labels; identical executable-known sample for precision/FPR. Unknown selections remain in feasibility denominator. A/B/C candidate diagnostics are fixed-budget selection diagnostics, distinct from actual portfolio fill hit rates. Execution assumptions are saved per row.

| Scope | Model | Selected | Known executable | Precision | FPR | Feasibility | Missed executable winners |
|---|---|---:|---:|---:|---:|---:|---:|
| FULL_BVMT_2026-11-10 | A | 0 | 0 | unknown | unknown | unknown | 100.00% |
| FULL_BVMT_2026-11-10 | B | 90 | 37 | 59.46% | 40.54% | 41.11% | 44.83% |
| FULL_BVMT_2026-11-10 | C | 90 | 37 | 59.46% | 40.54% | 41.11% | 44.83% |
| FULL_BVMT_2026-11-10 | D | 45 | 10 | 40.00% | 60.00% | 22.22% | 93.10% |
| FULL_BVMT_2026-11-10 | E | 45 | 17 | 47.06% | 52.94% | 37.78% | 86.21% |
| FULL_BVMT_2026-11-10 | F | 45 | 10 | 40.00% | 60.00% | 22.22% | 93.10% |
| FULL_BVMT_2026-11-10 | G | 42 | 14 | 64.29% | 35.71% | 33.33% | 82.76% |
| FULL_BVMT_2026-11-10 | H | 42 | 20 | 50.00% | 50.00% | 47.62% | 75.86% |
| FULL_BVMT_2026-11-10 | I | 35 | 19 | 52.63% | 47.37% | 54.29% | 75.86% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | A | 0 | 0 | unknown | unknown | unknown | 100.00% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | B | 90 | 37 | 59.46% | 40.54% | 41.11% | 42.86% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | C | 90 | 37 | 59.46% | 40.54% | 41.11% | 42.86% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | D | 45 | 12 | 41.67% | 58.33% | 26.67% | 89.29% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | E | 45 | 20 | 45.00% | 55.00% | 44.44% | 82.14% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | F | 45 | 12 | 41.67% | 58.33% | 26.67% | 89.29% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | G | 40 | 15 | 60.00% | 40.00% | 37.50% | 82.14% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | H | 40 | 20 | 50.00% | 50.00% | 50.00% | 75.00% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | I | 35 | 19 | 52.63% | 47.37% | 54.29% | 75.00% |

### Sparse evaluator: coverage versus false positives

The frozen sparse configuration uses 20 bps slippage; the A–I suite uses 10 bps. Sparse is compared with its own matched-cost baseline here, not with A–I raw portfolio returns. No unsupported compounded return or drawdown is supplied.

| Scope | Model | Coverage | Selected | Evaluated | Unknown | Precision | FPR | Feasibility | Mean executable net % | Missed winners |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL_BVMT_2026-11-10 | Baseline | 48.00% | 69 | 26 | 43 | 57.69% | 42.31% | 37.68% | 2.059 | 75.61% |
| FULL_BVMT_2026-11-10 | sparse_research_v1 (raw) | 82.96% | 72 | 24 | 48 | 58.33% | 41.67% | 33.33% | 4.3794 | 73.17% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | Baseline | 73.81% | 66 | 27 | 39 | 59.26% | 40.74% | 40.91% | 3.2558 | 74.36% |
| TUNIS_BOURSE_CHALLENGE_2026-11-10 | sparse_research_v1 (raw) | 100.00% | 72 | 26 | 46 | 57.69% | 42.31% | 36.11% | 3.9114 | 71.79% |

Higher research coverage is not permission to trade and does not establish better precision. Tight feasibility can leave a very small evaluated sample; its hit rate must not be generalized to unexecutable selections. Full candidate/outcome counts and all nine-model phase samples remain in the immutable artifact.

## Cold-load performance

`scripts/m14_joint_performance.py --browser` ran after tests/experiments finished.
Five alternating paired measurements use the same final code, copies of actual
EOD/account inputs, and config. Reference mode disables only validation-proof cache
hits, retaining all validation; reuse mode enables them. Application caches are
cleared between samples; OS/browser assets remain warm. User background load is
uncontrolled, so these are local diagnostic medians without statistical guarantees.

| Measured path | Reference median ms | Reuse median ms | Reduction |
|---|---:|---:|---:|
| Cold `/api/overview` |2950.303|2189.013|25.80%|
| Cold `/api/rankings` |3821.362|3317.703|13.18%|
| Overview page, including backend callbacks |6156.997|5486.929|10.88%|
| Market page, including backend callbacks |6207.165|5387.429|13.21%|

API timing uses TestClient. Page timing uses the current Next production build with
browser requests intercepted into that same copied-data TestClient, including550ms
for scheduled effects. This includes real backend computation, but is not TCP API,
disk-cold startup, authenticated competition synchronization or a production SLO.
All compared API responses were equal.77 page API responses succeeded; runtime
errors, external attempts and writes were zero; protected source/input/account
files were unchanged. Full samples: `artifacts/m14-joint/paired-cold-api.json`.
The earlier 41.96% figure describes validation CPU alone, not whole-application gain.
Cold pages remain slow despite the measured reduction.

## Final decision

Corrected Challenge G is **18.599541%**, below the original 19.424436%; its cadence20
phase IQR is 7.2912 percentage points and excluding SOTETEL still leaves substantial
dependence on assumptions and allocation. The sparse Challenge diagnostic improves
coverage while worsening precision/feasibility. No predictive improvement or
promotion is justified. 516 automated tests and a successful frontend build verify
engineering contracts, not investment skill.
