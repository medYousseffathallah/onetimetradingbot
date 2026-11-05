# Implementation sequence

| Stage | Deliverable | Exit gate | Status |
|---|---|---|---|
| Foundation | Existing scaffold, skills, synthetic fixture, local tests | Reproduce on team machine; keep rules blocked | **DONE (T01)** |
| Data | Authorized local-file import, snapshots, session calendar, identifiers | Provenance and quality tests; no silent drops | **DONE (T02, T03)** |
| Baseline | Session-aware liquidity filter and momentum ranking + offline LLM/index pilot | Point-in-time and future-mutation tests; offline budget/expiry gates | **DONE (T04, Milestone 1A/1B)** |
| Simulation | Complete cash/position ledger and execution adapter | Hand-calculated scenarios and reconciliation | **NEXT (T05)** |
| Evaluation | Walk-forward baselines and stress reports | Untouched test period; costs and liquidity disclosed | Planned (T06) |
| Intelligence | Optional event extraction and ML | Incremental out-of-sample improvement and evidence | Planned (T07, T08) |
| Interface | Local dashboard and manual decision journal | Staleness warnings, auditability, no order endpoint | Planned (T09) |
| Operations | Optional scheduled read-only run and alerts | Human-approved schedule, failure drills, restoration | Planned (T10) |

Use tasks and acceptance criteria, not calendar promises. A blocked data source does not
justify installing more models. Reassess the minimum design after each stage.
