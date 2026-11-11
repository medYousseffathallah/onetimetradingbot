"""Regression tests for Phase 2 content-fingerprinted caches and lightweight API paths."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from bvmt.api import create_app
from bvmt.browser import CompetitionPortfolioDOMSnapshot, save_browser_snapshot
from bvmt.calendar import read_exchange_calendar, read_instrument_master
from bvmt.data import read_bars_csv
from bvmt.gateway import OfficialBvmtNdjsonProvider
from bvmt.ledger import build_verified_user_screenshot_snapshot, save_screenshot_snapshot
from bvmt.perf_cache import invalidate_all_caches
from bvmt.portfolio_service import PortfolioStateService

ROOT = Path(__file__).resolve().parents[1]


def _setup_service(tmp_path: Path) -> PortfolioStateService:
    bars = tmp_path / "daily_bars.csv"
    shutil.copy2(ROOT / "tests/fixtures/daily_bars.csv", bars)
    real_snap_path = tmp_path / "real_snapshot.json"
    save_screenshot_snapshot(build_verified_user_screenshot_snapshot(), real_snap_path)
    return PortfolioStateService(
        portfolio_mode="REAL_COMPETITION",
        bars_path=bars,
        ledger_path=tmp_path / "real_ledger.json",
        alerts_path=tmp_path / "alerts.json",
        calendar_path=ROOT / "tests/fixtures/exchange_calendar.csv",
        instruments_path=ROOT / "tests/fixtures/instrument_master.csv",
        competition_config_path=ROOT / "configs/competition.json",
        llm_config_path=ROOT / "configs/llm_budget.example.json",
        doc_index_path=ROOT / "artifacts/doc_index.json",
        real_snapshot_path=real_snap_path,
        snapshots_dir=tmp_path / "snapshots",
        processed_root=tmp_path / "processed_empty",
    )


def test_csv_readers_cache_defensively_and_invalidate_on_change(tmp_path: Path) -> None:
    invalidate_all_caches()
    bars_path = tmp_path / "bars.csv"
    cal_path = tmp_path / "calendar.csv"
    inst_path = tmp_path / "instruments.csv"
    shutil.copy2(ROOT / "tests/fixtures/daily_bars.csv", bars_path)
    shutil.copy2(ROOT / "tests/fixtures/exchange_calendar.csv", cal_path)
    shutil.copy2(ROOT / "tests/fixtures/instrument_master.csv", inst_path)

    bars_1 = read_bars_csv(bars_path)
    cal_1 = read_exchange_calendar(cal_path)
    inst_1 = read_instrument_master(inst_path)
    count_bars = len(bars_1)

    # Returned lists must be fresh copies so caller mutation cannot poison the cache.
    bars_1.clear()
    cal_1.clear()
    inst_1.clear()

    bars_2 = read_bars_csv(bars_path)
    assert len(bars_2) == count_bars
    assert len(read_exchange_calendar(cal_path)) > 0
    assert len(read_instrument_master(inst_path)) > 0

    # Appending another valid row invalidates the bars cache immediately.
    lines = bars_path.read_text(encoding="utf-8").splitlines()
    last_row = lines[-1]
    assert len(lines) > 2
    bars_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    bars_3 = read_bars_csv(bars_path)
    assert len(bars_3) == count_bars - 1
    assert bars_3[-1] != last_row


def test_portfolio_state_cache_invalidates_on_new_snapshot_without_alerts_churn(
    tmp_path: Path,
) -> None:
    invalidate_all_caches()
    service = _setup_service(tmp_path)

    with patch(
        "bvmt.portfolio_service.build_dashboard_state",
        side_effect=lambda **kw: __import__(
            "bvmt.dashboard", fromlist=["build_dashboard_state"]
        ).build_dashboard_state(**kw),
    ) as build_spy:
        s1 = service.load_state()
        assert service.alerts_path.is_file()
        alerts_mtime_after_first = service.alerts_path.stat().st_mtime_ns
        s2 = service.load_state()
        assert s1 is s2
        assert build_spy.call_count == 1
        assert service.alerts_path.stat().st_mtime_ns == alerts_mtime_after_first

        # Adding a browser DOM snapshot must invalidate cached state immediately.
        dom = CompetitionPortfolioDOMSnapshot(
            source_url="https://www.tunisbourse.com/challenge/displayp.aspx",
            retrieved_at=datetime(2026, 11, 11, 9, 30, tzinfo=UTC),
            portfolio_total_tnd=Decimal("49998.050"),
            available_cash_tnd=Decimal("49998.050"),
            holdings_market_value_tnd=Decimal("0.000"),
            holdings=(),
            competition_rank=12,
            total_participants=100,
            displayed_overall_performance_pct=Decimal("0.00"),
            is_reconciled=True,
            reconciliation_gap_tnd=Decimal("0.000"),
        )
        save_browser_snapshot(dom, service.snapshots_dir)
        s3 = service.load_state()
        assert s3 is not s2
        assert build_spy.call_count == 2
        assert s3.pending_browser_snapshot is not None
        assert s3.pending_browser_snapshot.retrieved_at == dom.retrieved_at


def test_api_lightweight_defaults_and_fast_health_probe(tmp_path: Path) -> None:
    invalidate_all_caches()
    service = _setup_service(tmp_path)
    bars_csv = tmp_path / "daily_bars.csv"
    inst_csv = ROOT / "tests/fixtures/instrument_master.csv"

    # Build a calendar file with unknown hours to verify graceful /api/paper-trading handling.
    unknown_cal = tmp_path / "unknown_cal.csv"
    unknown_cal.write_text(
        "session_date,is_open,schedule_type,opens_at,closes_at,timezone,source_document_id\n"
        "2026-11-06,true,observed_daily_unknown_hours,,,Africa/Tunis,doc_official\n",
        encoding="utf-8",
    )

    registry_path = tmp_path / "strategy_experiments.json"
    registry_path.write_text(
        json.dumps(
            {
                "status": "available",
                "reports": [{"strategy_id": f"S{i}"} for i in range(9)],
            }
        ),
        encoding="utf-8",
    )

    app = create_app(
        service,
        strategy_registry_path=registry_path,
        paper_journal_path=tmp_path / "paper_journal.json",
        paper_bars_path=bars_csv,
        paper_instruments_path=inst_csv,
        paper_calendar_path=unknown_cal,
    )

    with patch.object(
        OfficialBvmtNdjsonProvider,
        "check_health",
        side_effect=AssertionError("default /api/health must not run blocking network probe"),
    ):
        with TestClient(app) as client:
            health_res = client.get("/api/health")
            assert health_res.status_code == 200
            assert health_res.json()["market_gateway"] is not None

            mkt_light = client.get("/api/market-status").json()
            assert mkt_light["coverage_summary"]["observations"] == []
            assert mkt_light["coverage_summary"]["observations_included"] is False
            assert mkt_light["coverage_summary"]["observations_omitted_count"] > 0

            mkt_full = client.get("/api/market-status?include_observations=true").json()
            assert (
                len(mkt_full["coverage_summary"]["observations"])
                == mkt_light["coverage_summary"]["observations_omitted_count"]
            )

            res_light = client.get("/api/research?include_strategy_comparison=false").json()
            assert res_light["strategy_comparison"] is None

            res_full = client.get("/api/research").json()
            assert res_full["strategy_comparison"] is not None

            paper_res = client.get("/api/paper-trading")
            assert paper_res.status_code == 200
            assert paper_res.json()["status"] == "unavailable"
            assert paper_res.json()["journal"] is None
            assert paper_res.json()["limitations"]

            with patch.object(service, "load_state", wraps=service.load_state) as load_spy:
                preview_res = client.get("/api/sync/preview")
                assert preview_res.status_code == 200
                assert load_spy.call_count == 1
