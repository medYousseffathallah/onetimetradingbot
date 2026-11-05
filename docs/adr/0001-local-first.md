# ADR 0001: local-first modular application
Status: accepted as an engineering starting decision.
Context: one small team, unknown competition rules and unvalidated data.
Decision: a Python package/CLI, one local data store, optional later dashboard. Reuse audited
libraries via narrow interfaces. Do not begin with autonomous agents or microservices.
Consequence: easier deterministic tests, fewer credentials and lower integration burden.
Revisit when multi-user concurrency or measured throughput requires it, not for appearance.
