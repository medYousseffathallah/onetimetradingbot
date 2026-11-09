"""Offline integration contract for the localhost portfolio API."""

import json
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bvmt.api import LOCAL_ORIGINS, app, create_app
from bvmt.browser import (
    AuthenticationExpiredError,
    BrowserCollectorError,
    BrowserHoldingItem,
    BrowserPendingOrderItem,
    BrowserTransactionItem,
    CompetitionPortfolioDOMSnapshot,
    save_browser_snapshot,
)
from bvmt.data import DailyMarketRefreshResult, read_bars_csv
from bvmt.gateway import MarketDataGateway
from bvmt.ledger import PortfolioLedger
from bvmt.llm import DocumentChunk
from bvmt.portfolio_service import PortfolioStateService

ROOT = Path(__file__).resolve().parents[1]
CAPTURED = datetime.fromisoformat("2026-11-07T12:20:06+00:00")


@pytest.fixture
def service(tmp_path: Path) -> PortfolioStateService:
    active = PortfolioStateService(
        bars_path=ROOT / "tests/fixtures/daily_bars.csv",
        ledger_path=tmp_path / "ledger.json",
        real_snapshot_path=tmp_path / "opening.json",
        snapshots_dir=tmp_path / "snapshots",
        alerts_path=tmp_path / "alerts.json",
        calendar_path=ROOT / "tests/fixtures/exchange_calendar.csv",
        instruments_path=ROOT / "tests/fixtures/instrument_master.csv",
        competition_config_path=ROOT / "configs/competition.json",
        llm_config_path=ROOT / "configs/llm_budget.example.json",
        doc_index_path=tmp_path / "index.json",
        processed_root=tmp_path / "processed",
    )
    state = active.load_state()
    state.ledger.save(state.ledger_path)
    return active


@pytest.fixture
def snapshot() -> CompetitionPortfolioDOMSnapshot:
    return CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=CAPTURED,
        portfolio_total_tnd=Decimal("50000.75"),
        available_cash_tnd=Decimal("49608.05"),
        holdings_market_value_tnd=Decimal("392.70"),
        holdings=(
            BrowserHoldingItem(
                symbol="BH BANK",
                quantity=30,
                acquisition_price_tnd=Decimal("13.065"),
                acquisition_amount_tnd=Decimal("391.95"),
                latest_price_tnd=Decimal("13.09"),
                market_value_tnd=Decimal("392.70"),
                gain_tnd=Decimal("0.75"),
                gain_pct=Decimal("0.19"),
                displayed_symbol="BH",
                displayed_identifier="223375",
            ),
        ),
        competition_rank=118,
        total_participants=14530,
        displayed_overall_performance_pct=Decimal("0.00"),
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
        challenge_period_text="2026-10-01 to 2027-05-31",
        movements_page_captured=True,
    )


def ledger_bytes(service: PortfolioStateService) -> bytes:
    return service.resolve_context().ledger_path.read_bytes()


def test_opening_baseline(service: PortfolioStateService) -> None:
    with TestClient(create_app(service)) as client:
        response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_mode"] == "REAL_COMPETITION"
    assert body["website_reported"]["portfolio_total_tnd"] == "49998.050"
    assert body["website_reported"]["capture_timestamp"] is None
    assert body["website_reported"]["holdings_value_tnd"] == "390.000"
    assert body["website_reported"]["unrealized_pnl_tnd"] == "-1.950"
    assert body["sync_status"]["is_stale"] is True
    assert body["sync_status"]["has_pending_snapshot"] is False


def test_pending_snapshot_is_read_only(
    service: PortfolioStateService, snapshot: CompetitionPortfolioDOMSnapshot
) -> None:
    saved = save_browser_snapshot(snapshot, service.snapshots_dir)
    assert saved.name == "sync_20261107_122006.json"
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        overview = client.get("/api/overview").json()
        snapshots = client.get("/api/snapshots").json()
        preview = client.get("/api/sync/preview").json()
    assert overview["website_reported"]["portfolio_total_tnd"] == "49998.050"
    assert overview["sync_status"]["has_pending_snapshot"] is True
    assert overview["sync_status"]["pending_snapshot_total_tnd"] == "50000.750"
    assert overview["sync_status"]["pending_snapshot_rank"] == 118
    assert datetime.fromisoformat(overview["sync_status"]["pending_snapshot_timestamp"]) == CAPTURED
    candidate = snapshots["pending_confirmation"]
    assert candidate == snapshots["unconfirmed_browser_snapshots"][0]
    assert candidate["portfolio_total_tnd"] == "50000.750"
    assert candidate["available_cash_tnd"] == "49608.050"
    assert candidate["holdings_market_value_tnd"] == "392.700"
    assert candidate["holdings_count"] == 1
    assert candidate["competition_rank"] == 118
    assert candidate["total_participants"] == 14530
    assert candidate["is_confirmed"] is False
    assert preview["has_pending"] is True
    assert preview["status_label"] == "Snapshot captured — awaiting confirmation"
    assert preview["requires_confirmation"] is True
    assert preview["equity_before_tnd"] == "49998.050"
    assert preview["equity_after_tnd"] == "50000.750"
    assert preview["cash_before_tnd"] == preview["cash_after_tnd"] == "49608.050"
    assert preview["cash_delta_tnd"] == "0.000"
    assert preview["position_deltas"] == []
    assert ledger_bytes(service) == before


def test_confirmation_gate_and_restart(
    service: PortfolioStateService, snapshot: CompetitionPortfolioDOMSnapshot
) -> None:
    save_browser_snapshot(snapshot, service.snapshots_dir)
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        rejected = client.post("/api/sync/confirm", json={"confirmed_by_user": False})
        assert rejected.status_code == 400
        assert (
            rejected.json()["detail"]
            == "Explicit user confirmation (confirmed_by_user=True) is required."
        )
        assert ledger_bytes(service) == before
        response = client.post("/api/sync/confirm", json={"confirmed_by_user": True})
        assert response.status_code == 200, response.text
        website = response.json()["overview"]["website_reported"]
        assert website["portfolio_total_tnd"] == "50000.750"
        assert website["holdings_value_tnd"] == "392.700"
        assert website["unrealized_pnl_tnd"] == "0.750"
        assert website["available_cash_tnd"] == "49608.050"
        assert website["competition_rank"] == 118
        assert website["competition_participants"] == 14530
        assert website["live_synchronized"] is True
        assert datetime.fromisoformat(website["capture_timestamp"]) == CAPTURED
    persisted = ledger_bytes(service)
    assert persisted != before
    # Rebuild both objects, preserving the explicit local paths as a restarted process does.
    restarted = PortfolioStateService(
        bars_path=service.requested_bars_path,
        ledger_path=service.requested_ledger_path,
        real_snapshot_path=service.real_snapshot_path,
        snapshots_dir=service.snapshots_dir,
        alerts_path=service.alerts_path,
        calendar_path=service.calendar_path,
        instruments_path=service.instruments_path,
        competition_config_path=service.competition_config_path,
        llm_config_path=service.llm_config_path,
        doc_index_path=service.doc_index_path,
        processed_root=service.processed_root,
    )
    with TestClient(create_app(restarted)) as client:
        overview = client.get("/api/overview").json()
        assert overview["website_reported"] == website
        assert overview["local_valuation"]["total_equity_tnd"] == "50000.750"
        assert overview["sync_status"]["has_pending_snapshot"] is False
        holdings = client.get("/api/holdings").json()
        assert holdings["portfolio_total_tnd"] == "50000.750"
        bh = holdings["holdings"][0]
        assert bh["symbol"] == "BH BANK"
        assert bh["quantity"] == 30
        assert bh["website_last_price_tnd"] == "13.090"
        assert bh["website_market_value_tnd"] == "392.700"
        assert bh["website_unrealized_pnl_tnd"] == "0.750"
        assert bh["verified_market_price_tnd"] is None
        history = client.get("/api/snapshots").json()
        assert len(history["confirmed_history"]) == 2
        assert history["confirmed_history"][0]["portfolio_total_tnd"] == "49998.050"
        assert history["unconfirmed_browser_snapshots"] == []
        assert history["pending_confirmation"] is None
        assert client.get("/api/sync/preview").json()["status_label"] == "Up to date"
    assert ledger_bytes(service) == persisted


@pytest.mark.parametrize(
    "body",
    [{}, {"confirmed_by_user": "true"}, {"confirmed_by_user": 1}, {"confirmed_by_user": None}],
)
def test_confirmation_requires_boolean(service: PortfolioStateService, body: dict) -> None:
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        assert client.post("/api/sync/confirm", json=body).status_code == 422
    assert ledger_bytes(service) == before


def test_no_snapshot_preview_and_confirm(service: PortfolioStateService) -> None:
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        preview = client.get("/api/sync/preview").json()
        assert preview["has_pending"] is False
        assert preview["candidate_snapshot"] is None
        assert preview["status_label"] == "Up to date"
        assert client.post("/api/sync/confirm", json={"confirmed_by_user": True}).status_code == 400
    assert ledger_bytes(service) == before


def test_read_endpoints_and_synthetic_blocker(service: PortfolioStateService) -> None:
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        market_response = client.get("/api/market-status")
        assert market_response.status_code == 200, market_response.text
        market = market_response.json()
        assert market["market_status"]["is_synthetic"] is True
        assert market["market_status"]["total_bars"] > 0
        assert market["market_status"]["retrieved_at"] is None
        assert market["coverage_summary"]
        assert sum(d["is_active"] for d in market["available_datasets"]) == 1
        for dataset in market["available_datasets"]:
            assert "/" not in dataset["label"] and "\\" not in dataset["label"]
        rankings = client.get("/api/rankings").json()
        assert rankings["data_is_synthetic"] is True
        assert rankings["simulation_profile"] == "SYNTHETIC_DEMO"
        assert datetime.fromisoformat(rankings["as_of"]).tzinfo is not None
        assert rankings["rankings"]
        for row in rankings["rankings"]:
            assert row["recommendation_category"] == "NO TRADE"
            assert any(
                "synthetic_data_on_real_portfolio" in reason for reason in row["blocked_reasons"]
            )
            assert row["suggested_shares"] == 0
        assert client.get("/api/transactions").json() == {"transactions": []}
        assert client.get("/api/orders/pending").json() == {"pending_orders": []}
        health = client.get("/api/health").json()
        assert health["status"] == "degraded"
        assert health["version"]
        assert health["autonomous_trading_enabled"] is False
        assert health["localhost_only"] is True
        assert health["llm_status"]["network_enabled"] is False
        assert health["rule_blockers"]
        assert "api_key" not in json.dumps(health)
    assert ledger_bytes(service) == before


def test_browser_sync_capture_only(
    service: PortfolioStateService, snapshot: CompetitionPortfolioDOMSnapshot
) -> None:
    before = ledger_bytes(service)

    def collect(**kwargs):
        assert kwargs["snapshots_dir"] == service.snapshots_dir
        assert kwargs["user_data_dir"] == service.snapshots_dir.parent / "browser_profile"
        assert kwargs["timeout_seconds"] == 180
        return snapshot, save_browser_snapshot(snapshot, kwargs["snapshots_dir"])

    with patch("bvmt.api.run_browser_sync_subprocess", side_effect=collect) as collector:
        with TestClient(create_app(service)) as client:
            response = client.post("/api/sync/browser", json={})
            assert response.status_code == 200, response.text
            assert response.json()["captured_snapshot"]["portfolio_total_tnd"] == "50000.750"
            assert response.json()["reconciliation_preview"]["requires_confirmation"] is True
            assert (
                client.get("/api/overview").json()["website_reported"]["portfolio_total_tnd"]
                == "49998.050"
            )
        collector.assert_called_once()
    assert ledger_bytes(service) == before


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (AuthenticationExpiredError("password=secret"), 400),
        (BrowserCollectorError("<html>cookie=secret C:/private</html>"), 422),
    ],
)
def test_browser_errors_are_safe(
    service: PortfolioStateService, error: Exception, status: int
) -> None:
    before = ledger_bytes(service)
    with patch("bvmt.api.run_browser_sync_subprocess", side_effect=error):
        with TestClient(create_app(service)) as client:
            response = client.post("/api/sync/browser", json={"timeout_seconds": 30})
    assert response.status_code == status
    assert (
        "secret" not in response.text
        and "private" not in response.text
        and "<html>" not in response.text
    )
    assert ledger_bytes(service) == before


@pytest.mark.parametrize("timeout", [0, -1, 601, "invalid"])
def test_browser_timeout_validation(service: PortfolioStateService, timeout: object) -> None:
    with patch("bvmt.api.run_browser_sync_subprocess") as collector:
        with TestClient(create_app(service)) as client:
            assert (
                client.post("/api/sync/browser", json={"timeout_seconds": timeout}).status_code
                == 422
            )
        collector.assert_not_called()


def test_transactions_and_orders_before_and_after_confirmation(
    service: PortfolioStateService, snapshot: CompetitionPortfolioDOMSnapshot
) -> None:
    tx = BrowserTransactionItem(
        "browser-tx",
        "browser-order",
        "BH BANK",
        "BH_BANK",
        "BUY",
        30,
        Decimal("13.065"),
        Decimal("0"),
        CAPTURED.isoformat(),
    )
    pending = BrowserPendingOrderItem(
        "pending-1",
        "DEMO_A",
        "DEMO_A",
        "BUY",
        10,
        0,
        10,
        Decimal("10"),
        "PENDING",
        CAPTURED.isoformat(),
    )
    snapshot = replace(snapshot, transactions=(tx,), pending_orders=(pending,))
    save_browser_snapshot(snapshot, service.snapshots_dir)
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        transactions = client.get("/api/transactions").json()["transactions"]
        assert transactions[0]["transaction_id"] == "browser-tx"
        assert transactions[0]["execution_price_tnd"] == "13.065"
        assert transactions[0]["is_confirmed"] is False
        orders = client.get("/api/orders/pending").json()["pending_orders"]
        assert orders[0]["order_id"] == "pending-1"
        assert orders[0]["is_confirmed"] is False
        assert ledger_bytes(service) == before
        assert client.post("/api/sync/confirm", json={"confirmed_by_user": True}).status_code == 200
        transactions = client.get("/api/transactions").json()["transactions"]
        assert len(transactions) == 1
        assert transactions[0]["is_confirmed"] is True
        assert client.get("/api/orders/pending").json()["pending_orders"][0]["is_confirmed"] is True


def test_local_fills_and_pending_orders(service: PortfolioStateService) -> None:
    path = service.resolve_context().ledger_path
    ledger = PortfolioLedger.load(path)
    ledger.record_pending_order(
        order_id="local",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="BUY",
        quantity=10,
        limit_price_tnd="10",
        submitted_at=CAPTURED,
    )
    ledger.record_execution_fill(
        order_id="local", filled_shares=4, execution_price_tnd="10", executed_at=CAPTURED
    )
    ledger.save(path)
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        txs = client.get("/api/transactions").json()["transactions"]
        assert len(txs) == 1
        assert txs[0]["source"] == "ledger"
        assert txs[0]["filled_shares"] == 4
        assert txs[0]["fee_tnd"] == "0.200"
        orders = client.get("/api/orders/pending").json()["pending_orders"]
        assert orders[0]["remaining_shares"] == 6
        assert orders[0]["status"] == "PARTIALLY_FILLED"
    assert ledger_bytes(service) == before


def test_mode_preserves_all_overrides(service: PortfolioStateService) -> None:
    before = ledger_bytes(service)
    with patch("bvmt.api.PortfolioStateService", wraps=PortfolioStateService) as constructor:
        with TestClient(create_app(service)) as client:
            response = client.get("/api/overview?mode=SYNTHETIC_DEMO")
            assert response.status_code == 200, response.text
            assert response.json()["portfolio_mode"] == "SYNTHETIC_DEMO"
            assert response.json()["website_reported"]["snapshot_id"] is None
        kwargs = constructor.call_args.kwargs
        assert kwargs.pop("portfolio_mode") == "SYNTHETIC_DEMO"
        assert kwargs.pop("bars_path") == service.requested_bars_path
        assert kwargs.pop("ledger_path") == service.requested_ledger_path
        assert all(value == getattr(service, key) for key, value in kwargs.items())
        assert len(kwargs) == 9
    assert ledger_bytes(service) == before


@pytest.mark.parametrize(
    "endpoint",
    [
        "overview",
        "holdings",
        "snapshots",
        "transactions",
        "orders/pending",
        "market-status",
        "rankings",
        "research",
        "health",
        "sync/preview",
    ],
)
def test_read_mode_validation(service: PortfolioStateService, endpoint: str) -> None:
    with TestClient(create_app(service)) as client:
        assert client.get(f"/api/{endpoint}?mode=UNKNOWN").status_code == 422


@pytest.mark.parametrize(
    "origin", [*LOCAL_ORIGINS, "https://evil.example", "http://localhost:3001", "null"]
)
def test_strict_cors(service: PortfolioStateService, origin: str) -> None:
    with TestClient(create_app(service)) as client:
        response = client.options(
            "/api/overview", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
    if origin in LOCAL_ORIGINS:
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    else:
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-origin") != "*"


def test_research_search_cutoff_and_plain_text(
    service: PortfolioStateService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = service.load_state()
    chunk = DocumentChunk(
        "eligible",
        "source-doc",
        ["DEMO_A"],
        "2026-01-08T10:00:00+00:00",
        "2026-01-08T11:00:00+00:00",
        "en",
        "section 1",
        0,
        "<p>Revenue growth</p><script>secret()</script>\nCookie: private-token",
        "test-hash",
    )
    state.document_chunks = [
        chunk,
        replace(chunk, chunk_id="future", published_at="2027-01-01T00:00:00+00:00"),
        replace(chunk, chunk_id="unknown", published_at=None),
        replace(chunk, chunk_id="late-ingested", ingested_at="2027-01-01T00:00:00+00:00"),
    ]
    monkeypatch.setattr(service, "load_state", lambda: state)
    monkeypatch.chdir(tmp_path)
    with patch(
        "bvmt.api.search_document_index",
        wraps=__import__("bvmt.llm", fromlist=["search_document_index"]).search_document_index,
    ) as search:
        with TestClient(create_app(service)) as client:
            listing = client.get("/api/research").json()
            assert listing["query"] is None
            assert [c["chunk_id"] for c in listing["document_results"]] == ["eligible"]
            result = client.get("/api/research?q=revenue").json()
            assert result["query"] == "revenue"
            assert result["document_results"][0]["method"] == "bm25_lexical_fallback"
            assert result["document_results"][0]["is_synthetic"] is True
            assert "<p>" not in json.dumps(result)
            assert "private-token" not in json.dumps(result)
            assert "secret()" not in json.dumps(result)
            assert result["backtest_summary"]["status"] == "unavailable"
            assert result["backtest_summary"]["total_return_pct"] is None
        search.assert_called_once()


def test_recorded_backtest_metrics(
    service: PortfolioStateService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    # Explicit artifact fixture exercises metric projection; these are test values, not results.
    (artifacts / "backtest_audit_2026.json").write_text(
        json.dumps(
            {
                "generated_at": CAPTURED.isoformat(),
                "full_period_backtest": {
                    "start_session": "2026-01-02",
                    "end_session": "2026-11-06",
                    "session_count": 194,
                    "total_return_pct": "1.1254",
                    "liquidated_total_return_pct": "1.000",
                    "equal_weight_benchmark_return_pct": "0.500",
                    "max_drawdown_pct": "2.000",
                },
                "walk_forward": {
                    "total_folds": 7,
                    "mean_fold_return_pct": "0.100",
                    "mean_liquidated_return_pct": "0.050",
                    "mean_benchmark_return_pct": "0.025",
                    "positive_fold_ratio": "0.8571",
                    "is_statistically_conclusive": False,
                },
                "cookies": "must-not-leak",
                "source_path": "C:/private/path",
            }
        ),
        encoding="utf-8",
    )
    with TestClient(create_app(service)) as client:
        response = client.get("/api/research")
        assert response.status_code == 200, response.text
        summary = response.json()["backtest_summary"]
        assert summary["status"] == "available"
        assert summary["total_return_pct"] == "1.125"
        assert summary["walk_forward_total_folds"] == 7
        assert summary["is_statistically_conclusive"] is False
        assert "Historical simulation" in summary["label"]
        assert "must-not-leak" not in response.text and "private/path" not in response.text
        (artifacts / "backtest_audit_2026.json").write_text("{}", encoding="utf-8")
        assert client.get("/api/research").json()["backtest_summary"]["status"] == "unavailable"


def test_missing_data_returns_safe_error(service: PortfolioStateService, tmp_path: Path) -> None:
    service.requested_bars_path = tmp_path / "private-missing.csv"
    with TestClient(create_app(service)) as client:
        response = client.get("/api/overview")
    assert response.status_code == 503
    assert "private-missing" not in response.text


@pytest.mark.parametrize(
    "publication,ingestion",
    [
        ("2026-01-08T16:00:00+00:00", "2026-01-08T16:05:00+00:00"),
        ("2027-01-01T00:00:00+00:00", "2026-01-08T16:05:00+00:00"),
        ("2026-01-08T16:00:00+00:00", "2027-01-01T00:00:00+00:00"),
        (None, "2026-01-08T16:05:00+00:00"),
    ],
)
def test_verified_holding_prices_require_source_availability(
    service: PortfolioStateService,
    monkeypatch: pytest.MonkeyPatch,
    publication: str | None,
    ingestion: str,
) -> None:
    state = service.load_state()
    state.data_is_synthetic = False
    bar = replace(
        read_bars_csv(ROOT / "tests/fixtures/daily_bars.csv")[0],
        instrument_id="BH_BANK",
        symbol="BH BANK",
        close=Decimal("13.09"),
        published_at=datetime.fromisoformat(publication) if publication else None,
        ingested_at=datetime.fromisoformat(ingestion),
    )
    monkeypatch.setattr(service, "load_state", lambda: state)
    with patch("bvmt.api.read_bars_csv", return_value=[bar]):
        with TestClient(create_app(service)) as client:
            response = client.get("/api/holdings")
    assert response.status_code == 200, response.text
    holding = response.json()["holdings"][0]
    if publication and publication.startswith("2026") and ingestion.startswith("2026"):
        assert holding["verified_market_price_tnd"] == "13.090"
        assert holding["verified_market_value_tnd"] == "392.700"
        assert holding["price_drift_tnd"] == "0.090"
    else:
        assert holding["verified_market_price_tnd"] is None
        assert holding["verified_market_value_tnd"] is None
        assert holding["price_drift_tnd"] is None


def test_json_secrets_and_html_are_not_echoed(service: PortfolioStateService) -> None:
    with TestClient(create_app(service)) as client:
        response = client.get(
            "/api/research",
            params={"q": '<script>secret-script()</script>{"password": "private-password"}'},
        )
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "secret-script" not in response.text
    assert "private-password" not in response.text


def test_sync_cannot_apply_real_snapshot_to_demo(
    service: PortfolioStateService, snapshot: CompetitionPortfolioDOMSnapshot
) -> None:
    service.portfolio_mode = "SYNTHETIC_DEMO"
    save_browser_snapshot(snapshot, service.snapshots_dir)
    before = ledger_bytes(service)
    with patch("bvmt.api.run_browser_sync_subprocess") as collector:
        with TestClient(create_app(service)) as client:
            assert client.post("/api/sync/browser", json={}).status_code == 400
            assert (
                client.post("/api/sync/confirm", json={"confirmed_by_user": True}).status_code
                == 400
            )
        collector.assert_not_called()
    assert ledger_bytes(service) == before


def test_module_app_and_openapi() -> None:
    assert app.title == "BVMT local research API"
    schema = create_app().openapi()
    assert set(schema["paths"]) == {
        "/api/overview",
        "/api/holdings",
        "/api/snapshots",
        "/api/transactions",
        "/api/orders/pending",
        "/api/market-status",
        "/api/rankings",
        "/api/research",
        "/api/strategy-lab",
        "/api/paper-trading",
        "/api/paper-trading/record-signal",
        "/api/health",
        "/api/glossary",
        "/api/market-research",
        "/api/sync/browser",
        "/api/sync/preview",
        "/api/sync/confirm",
        "/api/market-data/status",
        "/api/market-data/refresh",
        "/api/trade-plans",
        "/api/trade-plans/calculate",
        "/api/holding-periods",
        "/api/challenge-universe",
    }
    assert schema["paths"]["/api/overview"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("AccountOverviewResponse")


def test_strategy_lab_missing_registry_is_read_only(
    service: PortfolioStateService, tmp_path: Path
) -> None:
    path = tmp_path / "missing_registry.json"
    before = ledger_bytes(service)
    with TestClient(create_app(service, strategy_registry_path=path)) as client:
        body = client.get("/api/strategy-lab").json()
        assert body["status"] == "unavailable"
        assert body["registry"] is None
        assert client.get("/api/research").json()["strategy_comparison"] is None
    assert not path.exists()
    assert ledger_bytes(service) == before


@pytest.mark.parametrize("content", ["{broken", "[]", '{"status":"available","reports":[]}'])
def test_strategy_lab_invalid_registry(
    service: PortfolioStateService, tmp_path: Path, content: str
) -> None:
    path = tmp_path / "invalid_registry.json"
    path.write_text(content, encoding="utf-8")
    with TestClient(create_app(service, strategy_registry_path=path)) as client:
        body = client.get("/api/strategy-lab").json()
        assert body["status"] == "invalid"
        assert body["registry"] is None


def test_strategy_lab_and_research_share_saved_registry(
    service: PortfolioStateService, tmp_path: Path
) -> None:
    from bvmt.strategies import STRATEGY_IDS

    registry = {
        "status": "available",
        "reports": [
            {
                "strategy_id": s,
                "equity_curve": [{"session_date": "2026-01-02", "total_equity_tnd": 100000}],
                "walk_forward": {"total_folds": 7},
                "fee_and_liquidity_sensitivity": {"scenarios": []},
            }
            for s in STRATEGY_IDS
        ],
        "historical_audit": {"retrieved_at": None},
        "robustness_v2": {"version": "2.0"},
        "audit_summary": {"model_g_promotion_eligible": False},
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    before = ledger_bytes(service)
    with TestClient(create_app(service, strategy_registry_path=path)) as client:
        lab = client.get("/api/strategy-lab")
        assert lab.status_code == 200
        assert lab.json()["registry"] == registry
        assert lab.json()["robustness_v2"] == {"version": "2.0"}
        assert client.get("/api/research").json()["strategy_comparison"] == registry
        assert client.post("/api/strategy-lab").status_code == 405
    assert ledger_bytes(service) == before


def test_paper_api_is_separate_from_competition(service: PortfolioStateService) -> None:
    from bvmt.paper_trading import PaperJournalState

    before = ledger_bytes(service)
    state = PaperJournalState()
    with patch("bvmt.api.load_or_init_paper_journal", return_value=state) as load:
        with patch("bvmt.api.record_forward_paper_signal", return_value=state) as record:
            with TestClient(create_app(service)) as client:
                body = client.get("/api/paper-trading").json()
                assert body["status"] == "available"
                assert body["journal"]["is_paper_only"] is True
                assert body["journal"]["autonomous_trading_enabled"] is False
                assert client.post("/api/paper-trading/record-signal", json={}).status_code == 200
                assert (
                    client.post(
                        "/api/paper-trading/record-signal", json={"as_of_session": "not-date"}
                    ).status_code
                    == 422
                )
                assert (
                    client.post(
                        "/api/paper-trading/record-signal",
                        json={"autonomous_trading_enabled": True},
                    ).status_code
                    == 422
                )
            assert load.call_count == record.call_count == 1
    assert ledger_bytes(service) == before


def test_paper_api_rejects_invalid_signal(service: PortfolioStateService) -> None:
    before = ledger_bytes(service)
    with patch(
        "bvmt.api.record_forward_paper_signal", side_effect=ValueError("secret internal path")
    ):
        with TestClient(create_app(service)) as client:
            response = client.post("/api/paper-trading/record-signal", json={"strategy_id": "bad"})
            assert response.status_code == 400
            assert "secret internal path" not in response.text
    assert ledger_bytes(service) == before


def test_market_data_status_and_refresh_endpoints(service: PortfolioStateService) -> None:
    before = ledger_bytes(service)
    with TestClient(create_app(service)) as client:
        # Check /api/market-data/status
        status_resp = client.get("/api/market-data/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert "active_provider_id" in status_data
        assert "health_status" in status_data
        assert "calendar_status" in status_data

        # Check /api/health includes market_gateway
        health_resp = client.get("/api/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert "market_gateway" in health_data
        assert health_data["market_gateway"] is not None

        # Check /api/market-data/refresh (mocking sync to prevent remote download in test)
        mock_result = DailyMarketRefreshResult(
            source_id="mock_source",
            source_path="mock_path",
            source_url="http://mock",
            retrieved_at="2026-11-08T12:00:00+00:00",
            previous_bars_count=100,
            new_bars_count=0,
            total_bars_count=100,
            previous_sessions_count=10,
            new_sessions_count=0,
            total_sessions_count=10,
            first_session="2026-01-01",
            latest_session="2026-01-10",
            duplicate_rows_detected=0,
            rejected_rows_count=0,
            stale_instruments_count=0,
            quality_report_path="",
            canonical_bars_path="data/test.csv",
            is_data_fresh=True,
            freshness_status="fresh",
        )
        with patch.object(MarketDataGateway, "refresh", return_value=mock_result):
            refresh_resp = client.post("/api/market-data/refresh", json={"force": False})
            assert refresh_resp.status_code == 200
            refresh_data = refresh_resp.json()
            assert refresh_data["success"] is True
            assert refresh_data["total_bars_count"] == 100

    # Ensure zero mutation to competition ledger
    assert ledger_bytes(service) == before


def test_trade_plans_endpoints(service: PortfolioStateService) -> None:
    with TestClient(create_app(service)) as client:
        # GET /api/trade-plans
        res = client.get("/api/trade-plans")
        assert res.status_code == 200
        data = res.json()
        assert "plans" in data
        assert "portfolio_total_equity_tnd" in data
        assert "available_cash_tnd" in data
        assert len(data["plans"]) > 0

        # POST /api/trade-plans/calculate
        calc_req = {
            "instrument_id": "STA",
            "symbol": "STA",
            "limit_price_tnd": "115.900",
            "target_weight_ratio": "0.0850",
            "intended_holding_horizon_sessions": 20,
            "portfolio_mode": "REAL_COMPETITION",
        }
        calc_res = client.post("/api/trade-plans/calculate", json=calc_req)
        assert calc_res.status_code == 200
        calc_data = calc_res.json()
        assert calc_data["symbol"] == "STA"
        assert calc_data["suggested_max_shares"] > 0
        assert "break_even_price_tnd" in calc_data
        assert "exit_conditions" in calc_data

        # GET /api/holding-periods
        hp_res = client.get("/api/holding-periods")
        assert hp_res.status_code == 200
        hp_data = hp_res.json()
        assert "horizons" in hp_data
        assert hp_data["is_statistically_conclusive"] is False
        assert "INCONCLUSIVE" in hp_data["verdict"]

        # GET /api/challenge-universe
        cu_res = client.get("/api/challenge-universe")
        assert cu_res.status_code == 200
        cu_data = cu_res.json()
        assert cu_data["count"] == 42
        assert len(cu_data["securities"]) == 42
