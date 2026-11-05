Review this diff without changing files. Read AGENTS.md, rules.md, and the task's acceptance
criteria. Prioritize future-data leakage, data loss, money arithmetic, fictitious fills,
permission bypasses, secrets, and unverified assumptions. Check that tests exercise the
changed behavior rather than only checking implementation details.
Return concrete findings with severity, path/line, reproduction, consequence, and minimal
fix. Distinguish blockers from suggestions. Run read-only checks when available; state
what you did not verify. Do not approve on the strength of a README or synthetic P&L.
