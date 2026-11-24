# External Gemini CLI Independent Research Handoff (V2)

**Status**: `WAITING_FOR_AGENT`  
**Reason**: Automated runtime discovery on `2026-11-24` confirmed `gemini` CLI is `NOT_FOUND` on system `PATH` (`codex-cli 0.171.0` was found and logged in via ChatGPT). Per V2 orchestration policy, NEON never impersonates an external Gemini CLI session.

## Purpose
Allow an external Gemini CLI / Gemini Antigravity operator to independently audit and replicate the V2 quantitative findings generated inside `C:\Users\Thinkcenter\Desktop\BVMT\bvmt-v2\research\experiments-v2\`.

## Exact Files to Review
1. `docs/v2/RECENT_PORTFOLIO_AUTOPSY.md` & `research/experiments-v2/r1_portfolio_autopsy.py`
2. `docs/v2/MARKET_MICROSTRUCTURE_RESEARCH.md` & `research/experiments-v2/r2_microstructure_audit.py`
3. `docs/v2/DATA_SOURCE_AND_PROVENANCE_SPEC.md`
4. `docs/v2/STRATEGY_RESEARCH.md` & `docs/v2/BACKTEST_VALIDATION_PLAN.md`
5. `src/bvmt_v2/research_engine.py` & `src/bvmt_v2/backtester.py`
6. `artifacts/v2/v2-benchmark-results.json`

## Reproduction Commands (Read-Only of Legacy `bvmt-starter-kit`)
```powershell
cd C:\Users\Thinkcenter\Desktop\BVMT\bvmt-v2
$env:PYTHONPATH = "C:\Users\Thinkcenter\Desktop\BVMT\bvmt-v2\src"
..\bvmt-starter-kit\.venv\Scripts\python.exe research\experiments-v2\r1_portfolio_autopsy.py
..\bvmt-starter-kit\.venv\Scripts\python.exe research\experiments-v2\r2_microstructure_audit.py
..\bvmt-starter-kit\.venv\Scripts\python.exe research\experiments-v2\run_v2_benchmark_suite.py
..\bvmt-starter-kit\.venv\Scripts\python.exe -m pytest tests_v2 -q
```

## Return Requirements
Record actual Gemini model/CLI version, UTC run timestamps, independent check of outlier sensitivity (`top1_excluded_return_pct`), walk-forward purging/embargo verification, and any disconfirming evidence without touching protected competition ledgers or configs.
