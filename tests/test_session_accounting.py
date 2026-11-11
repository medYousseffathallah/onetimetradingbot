"""Tests for daily session accounting, transaction reconstruction, and performance attribution (Milestone 12)."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from bvmt.api import app
from bvmt.session_accounting import generate_november_09_session_report


def test_session_accounting_reconciliation() -> None:
    report = generate_november_09_session_report()

    # 1. Equity and Cash balances
    assert report.starting_equity_tnd == Decimal("49979.070")
    assert report.ending_equity_tnd == Decimal("50061.960")
    assert report.equity_change_tnd == Decimal("82.890")

    assert report.starting_cash_tnd == Decimal("44586.070")
    assert report.ending_cash_tnd == Decimal("41622.790")
    assert report.cash_change_tnd == Decimal("-2963.280")

    # 2. Strict cash flow reconciliation
    assert report.reconciliation_gap_tnd == Decimal("0.000")

    # 3. P&L separation
    assert report.realized_pnl_tnd == Decimal("71.820")
    assert report.unrealized_pnl_delta_tnd == Decimal("11.070")
    assert report.verified_session_pnl_tnd == Decimal("82.890")
    assert report.unrealized_pnl_since_acq_tnd == Decimal("-9.860")
    assert report.total_return_since_inception_tnd == Decimal("61.960")

    # 4. Positions coverage (4 open + 1 closed round-trip)
    assert len(report.positions) == 5
    open_positions = [p for p in report.positions if p.status != "CLOSED_INTRADAY"]
    assert len(open_positions) == 4

    h_map = {p.symbol: p for p in report.positions}
    assert "STA" in h_map
    assert h_map["STA"].quantity == 22
    assert h_map["STA"].unrealized_pnl_since_acq_tnd == Decimal("-14.850")

    assert "NEW BODY LINE" in h_map
    assert h_map["NEW BODY LINE"].quantity == 200
    assert h_map["NEW BODY LINE"].unrealized_pnl_since_acq_tnd == Decimal("5.550")

    assert "DELICE HOLDING" in h_map
    assert h_map["DELICE HOLDING"].quantity == 263
    assert h_map["DELICE HOLDING"].portfolio_weight_pct > Decimal("10.000")

    assert "BH BANK" in h_map
    assert h_map["BH BANK"].quantity == 30

    # 5. Status disclaimer for incomplete transaction history
    assert report.attribution_status == "PERFORMANCE_ATTRIBUTION_INCOMPLETE"
    assert report.attribution_warning is not None
    assert "Performance attribution incomplete" in report.attribution_warning

    # 6. Model evaluations
    assert len(report.model_evaluations) >= 3
    sta_eval = next(m for m in report.model_evaluations if m.symbol == "STA")
    assert sta_eval.execution_fidelity == "EXACT_MATCH"
    assert sta_eval.actual_shares == 22


def test_api_session_summary_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/api/session/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["session_date"] == "2026-11-09"
    assert data["starting_equity_tnd"] == "49979.070"
    assert data["ending_equity_tnd"] == "50061.960"
    assert data["equity_change_tnd"] == "82.890"
    assert data["realized_pnl_tnd"] == "71.820"
    assert data["unrealized_pnl_delta_tnd"] == "11.070"
    assert data["attribution_status"] == "PERFORMANCE_ATTRIBUTION_INCOMPLETE"
    assert "Performance attribution incomplete" in data["attribution_warning"]
    assert len(data["positions"]) == 5
    assert len(data["transactions"]) == 4
    assert len(data["model_evaluations"]) >= 3
