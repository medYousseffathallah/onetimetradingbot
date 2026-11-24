# BVMT Trading Intelligence V2 — Master Program Plan

**Orchestrator**: NEON (Antigravity Primary Multi-Agent Orchestrator)  
**Created**: 2026-11-24  
**Isolated Worktree**: `C:\Users\Thinkcenter\Desktop\BVMT\bvmt-v2` (branch `v2/reconstruction`, branched cleanly from `70fff9002478e4b82447d36e17db9d85d4ea70b3`)  
**Scope**: Research-first greenfield reimplementation of BVMT Trading Intelligence V2 alongside intact M14/M15 legacy baselines.

---

## 1. Mission & Non-Negotiable Safety Boundaries

BVMT Trading Intelligence V2 is a **100% localhost, human-operated investment management research terminal**. Success is measured by data/accounting correctness, reproducible scientific evaluation, transparent risk and exit management, honest uncertainty reporting, and calm institutional usability—never by promised return percentages.

### Non-Negotiable Rules
1. **100% Localhost & Manual Execution**: Zero autonomous order submission, zero competition portal automation of trading forms (`bysell.aspx`, `acheter`, `vendre`), zero broker credentials stored.
2. **Zero Legacy Destruction**: Never modify, reset, clean, commit, or push `bvmt-starter-kit`, `bvmt-gemini-dashboard`, `bvmt-codex-research`, `data/portfolio/real_competition_ledger.json`, `data/portfolio/snapshots/*`, or `configs/*.json`. All 37 protected hashes are tracked in [artifacts/v2/preservation-manifest.json](../../artifacts/v2/preservation-manifest.json).
3. **Zero Fabricated Evidence**: Never invent prices, `published_at` timestamps, `TUNINDEX` series, fundamental financial statements, calibrated win probabilities, or agent provenance. Unknowns stay `UNAVAILABLE` or `UNVERIFIED`.
4. **Strict Separation of Truth States**: Every monetary or quantitative output carries an explicit provenance tag: `OBSERVED`, `CALCULATED`, `SIMULATED`, `UNVERIFIED`, or `UNAVAILABLE`.
5. **No Unapproved Paid APIs or Cloud Deployment**: Zero live LLM API spend (`BVMT_ALLOW_LIVE_LLM=0`), zero external database dependencies.

---

## 2. Clean Greenfield Boundary in `bvmt-v2`

| Path | Ownership | Purpose |
|---|---|---|
| `data/v2_market/` | Orchestrator (NEON) | Equity-only canonical copy of official BVMT archive (`15,080` rows, `76` equities, `202` sessions `2026-01-02..2026-11-18`, excluding `2,480` non-equity bond/debt/rights rows) + manifest |
| `docs/v2/` | Orchestrator / Design / Quant / Reviewer | Program charter, R1–R3 research reports, UX1 design specifications, V2 status & review reports |
| `docs/v2/prototypes/` | Product Design (`v2_product_designer`) | High-fidelity responsive HTML prototypes for Overview, Portfolio, Stock Research, Position Management, and Attribution |
| `research/experiments-v2/` | Quantitative Research (`v2_quant_researcher`) | Reproducible R1–R3 scripts, strategy evaluation runner, failure autopsy & validation outputs |
| `src/bvmt_v2/` | Implementation Lead (OpenAI Codex CLI) | Clean modular V2 backend: `contracts.py`, `market_data.py`, `research_engine.py`, `backtester.py`, `portfolio_engine.py`, `api.py` |
| `tests_v2/` | Implementation Lead (OpenAI Codex CLI) | Unit, contract, PIT anti-leakage, execution-realism, position-exit, and API preservation tests |
| `apps/terminal-v2/` | Implementation Lead (OpenAI Codex CLI) | Next.js 15 / React 19 / TypeScript V2 terminal implementing all 9 destinations against `/api/v2/*` |
| `scripts/v2_*.py` & `artifacts/v2/` | Orchestrator (NEON) | Playwright V2 visual/mobile audit, cold/warm performance profiling, agent execution logs, preservation manifest |

Legacy `src/bvmt/` and `frontend/` remain untouched inside `bvmt-v2` solely as the historical comparison baseline.

---

## 3. Dependency Graph & 5 Integration Gates

```text
[Gate 0: Worktree, Manifest & Contracts] (NEON)
   |
   +---> [Workstream A: Quant Research R1-R3] (v2_quant_researcher + External Gemini Handoff)
   |
   +---> [Workstream C: Product Design UX1] (v2_product_designer -> docs/v2/ UX specs + prototypes/)
   |
   v
[INTEGRATION GATE 1] Approved Research Findings + Design System + /api/v2/* Contracts
   |
   +---> [Workstream B1: Codex CLI Task 1] -> src/bvmt_v2/* + tests_v2/*
   |
   v
[INTEGRATION GATE 2] Tested V2 Backend, Clean Equity Dataset, Reproducible Benchmark Runs
   |
   +---> [Workstream B2: Codex CLI Task 2] -> apps/terminal-v2/* (9 Destinations)
   |
   v
[INTEGRATION GATE 3] Typechecked & Built V2 Production Frontend + Live API Integration
   |
   +---> [Workstream D: Browser Audit, Performance Profiling & Adversarial Review (v2_adversarial_reviewer)]
   |
   v
[INTEGRATION GATE 4] Reproducibility, Lookahead/Overfitting & UI Honesty Fixes Verified
   |
   v
[INTEGRATION GATE 5] Final Local Commits on v2/reconstruction & 15-Point Human Acceptance Package
```

---

## 4. Agent Runtime Provenance Policy

Verified on `2026-11-24`:
- **OpenAI Codex CLI**: Installed at `C:\Users\Thinkcenter\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe` (`codex-cli 0.171.0`), authenticated (`Logged in using ChatGPT`). Invoked directly via `codex exec -C C:\Users\Thinkcenter\Desktop\BVMT\bvmt-v2 -s workspace-write` with full output logged under `artifacts/v2/agent-logs/`.
- **Gemini CLI**: `NOT_FOUND` on system `PATH`. External Gemini CLI runs cannot be executed natively; therefore, quantitative research is delegated to an isolated Antigravity subagent (`v2_quant_researcher`) with its real `conversationId` logged, and an explicit standalone handoff is saved in `docs/v2/handoffs/EXTERNAL_GEMINI_CLI_HANDOFF.md` with status `WAITING_FOR_AGENT` for any external Gemini CLI sign-off.
- **Product Design & Adversarial Review**: Executed via separate, single-responsibility Antigravity subagents (`v2_product_designer` and read-only `v2_adversarial_reviewer`) so the implementation agent never self-certifies its own output.
