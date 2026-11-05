"""Offline CLI: synthetic demo, CSV validation/import, coverage check, session baseline, LLM dry-run, manual portfolio ledger, and local dashboard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from bvmt import __version__
from bvmt.calendar import (
    evaluate_coverage,
    read_exchange_calendar,
    read_instrument_master,
)
from bvmt.data import aware_timestamp, import_local_csv, read_bars_csv
from bvmt.features import rank_demo_momentum, rank_session_baseline
from bvmt.ledger import PortfolioLedger
from bvmt.llm import evaluate_dry_run, load_llm_budget_config
from bvmt.recommendations import generate_recommendations
from bvmt.rules import competition_blockers
from bvmt.snapshots import sha256_file


def _emit(payload: object, destination: str | None = None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False, default=str)
    if destination:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run labeled synthetic ranking, never orders")
    demo.add_argument("--fixture", default="tests/fixtures/daily_bars.csv")
    demo.add_argument("--config", default="configs/competition.json")
    demo.add_argument("--cutoff", default="2026-01-09T17:00:00+00:00")
    demo.add_argument("--output")
    rules = commands.add_parser("rules-check", help="Exit 2 while rule evidence is incomplete")
    rules.add_argument("--config", default="configs/competition.json")
    validate = commands.add_parser("validate-csv", help="Validate a canonical local CSV")
    validate.add_argument("path")
    imp = commands.add_parser(
        "import-csv",
        help="Snapshot, validate, and import an authorized local CSV into canonical format",
    )
    imp.add_argument("path", help="Path to local input CSV file")
    imp.add_argument("--source-id", required=True, help="Safe source identifier ([A-Za-z0-9_-]+)")
    imp.add_argument(
        "--format",
        dest="input_format",
        choices=("canonical", "french_bvmt"),
        default="canonical",
        help="Explicit input CSV format (default: canonical)",
    )
    imp.add_argument(
        "--permission-status",
        default="authorized_local_import",
        help="Documented access permission status (default: authorized_local_import)",
    )
    imp.add_argument(
        "--retrieved-at",
        required=True,
        help="Timezone-aware ISO-8601 retrieval timestamp",
    )
    imp.add_argument(
        "--raw-dir",
        default="data/raw",
        help="Directory for immutable content-addressed raw snapshots (default: data/raw)",
    )
    imp.add_argument(
        "--output-dir",
        required=True,
        help="Destination directory for canonical CSV, rejections.json, and manifest.json",
    )
    cov = commands.add_parser(
        "coverage-check",
        help="Evaluate dated instrument master, official calendar, and bar coverage",
    )
    cov.add_argument(
        "--instruments",
        default="tests/fixtures/instrument_master.csv",
        help="Path to dated instrument master CSV or JSON",
    )
    cov.add_argument(
        "--calendar",
        default="tests/fixtures/exchange_calendar.csv",
        help="Path to official exchange calendar CSV or JSON",
    )
    cov.add_argument(
        "--bars",
        default="tests/fixtures/daily_bars.csv",
        help="Path to canonical daily bars CSV",
    )
    cov.add_argument("--output", help="Optional path to write JSON coverage report")

    srank = commands.add_parser(
        "session-rank",
        help="Run T04 session-aware baseline ranking over verified open exchange sessions",
    )
    srank.add_argument("--instruments", default="tests/fixtures/instrument_master.csv")
    srank.add_argument("--calendar", default="tests/fixtures/exchange_calendar.csv")
    srank.add_argument("--bars", default="tests/fixtures/daily_bars.csv")
    srank.add_argument("--cutoff", default="2026-01-09T17:00:00+00:00")
    srank.add_argument("--short-lookback", type=int, default=20)
    srank.add_argument("--long-lookback", type=int, default=60)
    srank.add_argument("--min-trade-frequency", type=float, default=0.75)
    srank.add_argument("--min-median-turnover", default="1000")
    srank.add_argument("--output")

    ldry = commands.add_parser(
        "llm-dry-run",
        help="Evaluate Alibaba Model Studio budget, expiry, and offline/live gates without calling any API",
    )
    ldry.add_argument("--config", default="configs/llm_budget.example.json")
    ldry.add_argument("--model", required=True, help="Console model label from config")
    ldry.add_argument(
        "--role",
        default="financial_statement_analyst",
        help="Research role (e.g., document_chunk_embedding_pilot, financial_statement_analyst)",
    )
    ldry.add_argument("--prompt-version", default="v1")
    ldry.add_argument("--input-file", help="Optional path to input document text")
    ldry.add_argument(
        "--input-text",
        default="Sample financial disclosure text for dry-run token estimation.",
        help="Inline text payload if --input-file is not provided",
    )
    ldry.add_argument(
        "--now",
        default="2026-11-05T18:30:00+01:00",
        help="Timezone-aware evaluation timestamp",
    )
    ldry.add_argument("--output")

    pinit = commands.add_parser("portfolio-init", help="Initialize a local manual portfolio ledger")
    pinit.add_argument("--ledger", default="data/portfolio/ledger.json")
    pinit.add_argument("--initial-cash", default="100000.000")
    pinit.add_argument("--now", default="2026-01-05T08:30:00+00:00")

    pstat = commands.add_parser(
        "portfolio-status", help="Inspect current portfolio holdings, cash, and orders"
    )
    pstat.add_argument("--ledger", default="data/portfolio/ledger.json")
    pstat.add_argument("--output")

    ord_sub = commands.add_parser(
        "order-submit", help="Record a manually submitted PENDING order in local ledger"
    )
    ord_sub.add_argument("--ledger", default="data/portfolio/ledger.json")
    ord_sub.add_argument("--order-id", required=True)
    ord_sub.add_argument("--instrument-id", required=True)
    ord_sub.add_argument("--symbol", required=True)
    ord_sub.add_argument("--side", choices=("BUY", "SELL"), required=True)
    ord_sub.add_argument("--quantity", type=int, required=True)
    ord_sub.add_argument("--limit-price", required=True)
    ord_sub.add_argument("--recommendation-id")
    ord_sub.add_argument("--submitted-at", default="2026-01-09T10:00:00+00:00")
    ord_sub.add_argument("--notes", default="")

    ord_fill = commands.add_parser(
        "order-fill", help="Record a full or partial execution fill for an open order"
    )
    ord_fill.add_argument("--ledger", default="data/portfolio/ledger.json")
    ord_fill.add_argument("--order-id", required=True)
    ord_fill.add_argument("--filled-shares", type=int, required=True)
    ord_fill.add_argument("--execution-price", required=True)
    ord_fill.add_argument("--executed-at", default="2026-01-09T11:30:00+00:00")
    ord_fill.add_argument("--notes", default="")

    ord_close = commands.add_parser(
        "order-close", help="Mark an open order CANCELLED, REJECTED, or EXPIRED"
    )
    ord_close.add_argument("--ledger", default="data/portfolio/ledger.json")
    ord_close.add_argument("--order-id", required=True)
    ord_close.add_argument("--status", choices=("CANCELLED", "REJECTED", "EXPIRED"), required=True)
    ord_close.add_argument("--closed-at", default="2026-01-09T14:15:00+00:00")
    ord_close.add_argument("--reason", default="")

    rec_cmd = commands.add_parser(
        "recommend",
        help="Generate 5-state trading decision-support recommendations connected to the portfolio ledger",
    )
    rec_cmd.add_argument("--ledger", default="data/portfolio/ledger.json")
    rec_cmd.add_argument("--instruments", default="tests/fixtures/instrument_master.csv")
    rec_cmd.add_argument("--calendar", default="tests/fixtures/exchange_calendar.csv")
    rec_cmd.add_argument("--bars", default="tests/fixtures/daily_bars.csv")
    rec_cmd.add_argument("--config", default="configs/competition.json")
    rec_cmd.add_argument("--cutoff", default="2026-01-09T17:00:00+00:00")
    rec_cmd.add_argument("--short-lookback", type=int, default=2)
    rec_cmd.add_argument("--long-lookback", type=int, default=3)
    rec_cmd.add_argument("--min-median-turnover", default="5000")
    rec_cmd.add_argument("--output")

    dash = commands.add_parser(
        "dashboard", help="Launch the local Streamlit decision-support dashboard"
    )
    dash.add_argument("--port", type=int, default=8501)
    dash.add_argument(
        "--headless", action="store_true", help="Run without opening a browser tab automatically"
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "portfolio-init":
            ledger_p = Path(args.ledger)
            ledger = PortfolioLedger(
                initial_cash_tnd=Decimal(str(args.initial_cash)),
                created_at=aware_timestamp(args.now),
            )
            ledger.save(ledger_p)
            _emit(ledger.valuate().to_dict())
            return 0
        if args.command == "portfolio-status":
            ledger = PortfolioLedger.load(Path(args.ledger))
            _emit(
                {
                    "orders": [o.to_dict() for o in ledger.orders.values()],
                    "valuation": ledger.valuate().to_dict(),
                },
                args.output,
            )
            return 0
        if args.command == "order-submit":
            ledger_p = Path(args.ledger)
            ledger = PortfolioLedger.load(ledger_p)
            order = ledger.record_pending_order(
                order_id=args.order_id,
                instrument_id=args.instrument_id,
                symbol=args.symbol,
                side=args.side,
                quantity=args.quantity,
                limit_price_tnd=Decimal(str(args.limit_price)),
                submitted_at=aware_timestamp(args.submitted_at),
                recommendation_id=args.recommendation_id,
                notes=args.notes,
            )
            ledger.save(ledger_p)
            _emit({"order": order.to_dict(), "valuation": ledger.valuate().to_dict()})
            return 0
        if args.command == "order-fill":
            ledger_p = Path(args.ledger)
            ledger = PortfolioLedger.load(ledger_p)
            order = ledger.record_execution_fill(
                order_id=args.order_id,
                filled_shares=args.filled_shares,
                execution_price_tnd=Decimal(str(args.execution_price)),
                executed_at=aware_timestamp(args.executed_at),
                notes=args.notes,
            )
            ledger.save(ledger_p)
            _emit({"order": order.to_dict(), "valuation": ledger.valuate().to_dict()})
            return 0
        if args.command == "order-close":
            ledger_p = Path(args.ledger)
            ledger = PortfolioLedger.load(ledger_p)
            order = ledger.close_open_order(
                order_id=args.order_id,
                terminal_status=args.status,
                closed_at=aware_timestamp(args.closed_at),
                reason=args.reason,
            )
            ledger.save(ledger_p)
            _emit({"order": order.to_dict(), "valuation": ledger.valuate().to_dict()})
            return 0
        if args.command == "recommend":
            ledger_p = Path(args.ledger)
            cutoff_dt = aware_timestamp(args.cutoff)
            ledger = (
                PortfolioLedger.load(ledger_p)
                if ledger_p.is_file()
                else PortfolioLedger(created_at=cutoff_dt)
            )
            instruments = read_instrument_master(Path(args.instruments))
            calendar = read_exchange_calendar(Path(args.calendar))
            bars = read_bars_csv(Path(args.bars))
            comp_doc = json.loads(Path(args.config).read_text(encoding="utf-8"))
            blockers = competition_blockers(comp_doc)
            is_synth = any("synthetic" in b.source_id.lower() for b in bars)
            baseline = rank_session_baseline(
                instruments,
                calendar,
                bars,
                cutoff_dt,
                short_lookback=args.short_lookback,
                long_lookback=args.long_lookback,
                min_trade_frequency=0.60,
                min_median_turnover_tnd=Decimal(str(args.min_median_turnover)),
            )
            rec_report = generate_recommendations(
                baseline,
                ledger,
                generated_at=cutoff_dt,
                simulation_profile="SYNTHETIC_DEMO" if is_synth else "RESEARCH_CONSERVATIVE",
                data_is_synthetic=is_synth,
                rule_blocker_count=len(blockers),
            )
            _emit(rec_report.to_dict(), args.output)
            return 0
        if args.command == "dashboard":
            script_path = Path(__file__).resolve().parent / "dashboard.py"
            cmd = [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(script_path),
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(args.port),
            ]
            if args.headless:
                cmd.extend(["--server.headless", "true"])
            return subprocess.call(cmd)
        if args.command == "llm-dry-run":
            llm_cfg = load_llm_budget_config(Path(args.config))
            payload_text = (
                Path(args.input_file).read_text(encoding="utf-8")
                if args.input_file
                else str(args.input_text)
            )
            dry_report = evaluate_dry_run(
                llm_cfg,
                model_label=args.model,
                role=args.role,
                prompt_version=args.prompt_version,
                text_payload=payload_text,
                now=aware_timestamp(args.now),
            )
            _emit(asdict(dry_report), args.output)
            return 0
        if args.command == "session-rank":
            instruments = read_instrument_master(Path(args.instruments))
            calendar = read_exchange_calendar(Path(args.calendar))
            bars = read_bars_csv(Path(args.bars))
            s_report = rank_session_baseline(
                instruments,
                calendar,
                bars,
                aware_timestamp(args.cutoff),
                short_lookback=args.short_lookback,
                long_lookback=args.long_lookback,
                min_trade_frequency=args.min_trade_frequency,
                min_median_turnover_tnd=Decimal(str(args.min_median_turnover)),
            )
            _emit(asdict(s_report), args.output)
            return 0
        if args.command == "coverage-check":
            instruments = read_instrument_master(Path(args.instruments))
            calendar = read_exchange_calendar(Path(args.calendar))
            bars = read_bars_csv(Path(args.bars))
            report = evaluate_coverage(instruments, calendar, bars)
            _emit(asdict(report), args.output)
            return 0
        if args.command == "validate-csv":
            bars = read_bars_csv(Path(args.path))
            _emit(
                {
                    "status": "valid_canonical_data",
                    "rows": len(bars),
                    "source_ids": sorted({bar.source_id for bar in bars}),
                    "note": "Schema validity does not verify source truth or trading eligibility.",
                }
            )
            return 0
        if args.command == "import-csv":
            summary = import_local_csv(
                Path(args.path),
                source_id=args.source_id,
                input_format=args.input_format,
                permission_status=args.permission_status,
                retrieved_at=aware_timestamp(args.retrieved_at),
                raw_dir=Path(args.raw_dir),
                output_dir=Path(args.output_dir),
            )
            _emit(asdict(summary))
            return 0 if summary.accepted_rows > 0 else 1
        config_path = Path(args.config)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        blockers = competition_blockers(config)
        if args.command == "rules-check":
            _emit(
                {
                    "status": "blocked" if blockers else "ready_for_manual_design_review",
                    "blockers": blockers,
                    "execution_authorized": False,
                    "note": "Evidence completeness is not semantic verification or trading permission.",
                }
            )
            return 2 if blockers else 0
        fixture_path = Path(args.fixture)
        bars = read_bars_csv(fixture_path)
        cutoff = aware_timestamp(args.cutoff)
        rankings = rank_demo_momentum(bars, cutoff)
        _emit(
            {
                "mode": "synthetic_demo",
                "application_version": __version__,
                "decision_cutoff": cutoff.isoformat(),
                "rows": len(bars),
                "dataset_sha256": sha256_file(fixture_path),
                "competition_config_sha256": sha256_file(config_path),
                "rankings": [asdict(item) for item in rankings],
                "competition_readiness": "blocked" if blockers else "manual_design_review_only",
                "rule_blocker_count": len(blockers),
                "execution_authorized": False,
                "warning": "Synthetic data; no real stocks, no backtest, no profitability evidence.",
            },
            args.output,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
