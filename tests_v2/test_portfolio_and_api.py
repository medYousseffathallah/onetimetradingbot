"""Account evidence, independent monitoring gates and the complete read-only HTTP surface."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bvmt_v2 import portfolio_engine
from bvmt_v2.contracts import pv
from bvmt_v2.market_data import MarketData, load_market, synthetic_market
from bvmt_v2.portfolio_engine import (
    PortfolioBook,
    freeze_signal,
    load_portfolio,
    read_signal_journal,
)

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = ROOT.parent / "bvmt-starter-kit" / "data" / "portfolio"


@pytest.fixture(scope="module")
def real_market() -> MarketData:
    return load_market()


@pytest.fixture(scope="module")
def demo_market() -> MarketData:
    return synthetic_market()


@pytest.fixture(scope="module")
def real(real_market: MarketData) -> PortfolioBook:
    return load_portfolio(real_market)


@pytest.fixture(scope="module")
def demo(demo_market: MarketData) -> PortfolioBook:
    return load_portfolio(demo_market, "SYNTHETIC_DEMO")


def test_signed_sources_and_eod_attribution(real: PortfolioBook) -> None:
    snapshots = real.snapshots()
    ledger = snapshots["confirmed_ledger"]
    dom = snapshots["latest_dom_capture"]
    report = snapshots["unverified_screenshot"]
    mark = snapshots["eod_mark_portfolio"]
    assert ledger.equity_tnd.value == Decimal("49993.430")
    assert ledger.captured_at.date() == date(2026, 11, 10)
    assert dom.snapshot_id == "ext_1794476128406" and len(dom.holdings) == 8
    assert dom.equity_tnd.value == Decimal("50093.190") and dom.verification_status == "OBSERVED"
    assert report.captured_at is None and report.equity_tnd.value == Decimal("50647.640")
    assert report.return_pct.value == Decimal("1.30")
    assert report.equity_tnd.source == report.source_id == "unverified_user_screenshot_2026_11"
    assert report.equity_tnd.status == report.verification_status == "UNVERIFIED"
    assert (report.rank, report.total_participants, report.reported_holdings_count) == (
        111,
        14541,
        9,
    )
    assert [(h.instrument_id, h.quantity) for h in report.holdings] == [("AMEN_BANK", 45)]
    assert all(h.instrument_id != "AMEN_BANK" for h in dom.holdings)
    assert (
        mark.equity_tnd.value == Decimal("50355.830") and mark.verification_status == "CALCULATED"
    )
    assert mark.cash_tnd == dom.cash_tnd
    assert len(real.rejected_captures) == 3 and real.account_state_conflict
    audit = real.attribution
    assert audit.unrealized_pnl_tnd.value == Decimal("284.000")
    assert audit.realized_pnl_tnd.status == "UNAVAILABLE"
    assert audit.unexplained_residual_tnd.value == Decimal("71.830")
    assert audit.benchmarks["TUNINDEX"].status == "UNAVAILABLE"
    assert audit.benchmarks["ew_challenge_42_open_nov09_net"].value == Decimal("-0.013")


def test_real_position_monitoring_and_blockers(real: PortfolioBook) -> None:
    for iid, percent in (("EURO-CYCLES", "10.29"), ("DELICE_HOLDING", "10.17")):
        decision = real.position(iid)
        assert (decision.risk.position_weight.value * 100).quantize(Decimal(".01")) == Decimal(
            percent
        )
        assert (
            decision.monitoring_state == "CONSIDER_TRIM"
            and decision.execution_state == "EXECUTION_BLOCKED"
        )
        assert decision.risk.concentration_breach and decision.risk.liquidity_days_to_exit.value > 0
        assert decision.realized_pnl_tnd.status == "UNAVAILABLE"
        assert decision.thesis.origin == "UNVERIFIED_NONE"
        assert "ACCOUNT_STATE_CONFLICT" in decision.blockers
        assert "verified entry timestamp" in decision.exit_scenarios[-1]
    sale = real.scenario("SELL", "EURO-CYCLES", 50, Decimal("10.160"))
    assert sale.gross_tnd.value == Decimal("508.000") and sale.estimated_fee_tnd.value == Decimal(
        "2.540"
    )
    assert sale.stress_proceeds_tnd.value == Decimal(
        "505.460"
    ) and sale.post_trade_weight.value < Decimal(".10")
    assert (
        not sale.is_valid
        and "ACCOUNT_STATE_CONFLICT" in sale.rejection_reasons
        and not sale.is_executed
    )


def test_demo_scenarios_and_positive_protection(demo: PortfolioBook) -> None:
    assert all(s.verification_status == "SIMULATED" for s in demo.snapshots().values())
    with pytest.raises(ValueError, match="cannot mark"):
        load_portfolio(demo.market, "REAL_COMPETITION")
    assert demo.position("EURO-CYCLES").execution_state == "ELIGIBLE_MANUAL_ONLY"
    for side in ("SELL", "PROTECTION"):
        scenario = demo.scenario(side, "EURO-CYCLES", 20, Decimal("10.001"))
        assert scenario.is_valid and not scenario.is_executed
        assert scenario.estimated_fee_tnd.value == Decimal("1.000")
        assert scenario.stress_proceeds_tnd.value == Decimal("199.020")
        assert scenario.post_trade_cash_tnd.value == demo.current.cash_tnd.value + Decimal(
            "199.020"
        )
    assert demo.scenario("BUY", "AMEN_BANK", 1, Decimal("12")).is_valid
    for iid in ("MNP", "SCN", "MONOPRIX"):
        assert (
            "RESTRICTED_CHALLENGE" in demo.scenario("BUY", iid, 1, Decimal("10")).rejection_reasons
        )
    assert (
        "INSUFFICIENT_UNRESERVED_SHARES"
        in demo.scenario("SELL", "EURO-CYCLES", 101, Decimal("10")).rejection_reasons
    )
    buy = demo.scenario("BUY", "AMEN_BANK", 5000, Decimal("100"))
    assert {"INSUFFICIENT_CASH", "SINGLE_STOCK_CAP", "ONE_SESSION_LIQUIDITY_CAP"} <= set(
        buy.rejection_reasons
    )


def test_monitoring_states_and_verified_trailing_history(demo: PortfolioBook) -> None:
    iid = "EURO-CYCLES"
    assert demo.position(iid).monitoring_state == "HOLD"
    bars = demo.market.bars[iid]
    bar = bars[-1]
    # Re-price the final close below the verified post-entry peak and 20-session trend.
    new_price = pv(10, "TND", "SIMULATED", "test price stress", demo.at)
    stressed_bar = bar.model_copy(update={"close_tnd": new_price})
    market = replace(demo.market, bars={**demo.market.bars, iid: bars[:-1] + (stressed_bar,)})
    held = demo.eod_mark_portfolio.holdings[0].model_copy(
        update={"eod_reference_close_tnd": new_price}
    )
    marked = demo.eod_mark_portfolio.model_copy(update={"holdings": (held,)})
    stressed = replace(demo, market=market, eod_mark_portfolio=marked)
    assert stressed.position(iid).monitoring_state == "CONSIDER_EXIT"
    assert replace(stressed, verified_entries={}).position(iid).monitoring_state == "REVIEW"
    short = replace(market, bars={**market.bars, iid: (stressed_bar,)})
    assert replace(stressed, market=short).position(iid).monitoring_state == "INSUFFICIENT_DATA"
    # A synthetic label cannot bypass a conflicting account.
    conflict = replace(demo, account_state_conflict=True).scenario("SELL", iid, 1, Decimal(10))
    assert not conflict.is_valid and "ACCOUNT_STATE_CONFLICT" in conflict.rejection_reasons


def test_journal_freezes_once_and_rejects_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parent / f"journal-{uuid4().hex}"
    root.mkdir()
    try:
        (root / "research").mkdir()
        monkeypatch.setattr(portfolio_engine, "ROOT", root)
        forecast = datetime.now(UTC).date() + timedelta(days=3)
        record = freeze_signal("prospective-1", "EURO-CYCLES", "WATCH", "5_10", forecast)
        assert record == freeze_signal("prospective-1", "EURO-CYCLES", "WATCH", "5_10", forecast)
        assert read_signal_journal() == (record,)
        with pytest.raises(ValueError, match="different"):
            freeze_signal("prospective-1", "AMEN_BANK", "WATCH", "5_10", forecast)
        with pytest.raises(ValueError, match="future"):
            freeze_signal("expired", "AMEN_BANK", "WATCH", "5_10", date(2020, 1, 1))
        path = root / "research" / "v2_signal_journal.json"
        raw = json.loads(path.read_text())
        raw[0]["action_state"] = "RESEARCH_CANDIDATE"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="hash"):
            read_signal_journal()
    finally:
        (root / "research" / "v2_signal_journal.json").unlink(missing_ok=True)
        (root / "research").rmdir()
        root.rmdir()


def _hashes() -> dict[str, str]:
    paths = [ACCOUNT / "real_competition_ledger.json", *(ACCOUNT / "snapshots").glob("*.json")]
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def http_client(app: FastAPI, peer: str) -> AsyncClient:
    return AsyncClient(
        base_url="http://localhost", transport=ASGITransport(app=app, client=(peer, 50000))
    )


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["REAL_COMPETITION", "SYNTHETIC_DEMO"])
async def test_all_local_api_endpoints_are_read_only(
    mode: str, real_market: MarketData, demo_market: MarketData
) -> None:
    from bvmt_v2.api import create_v2_app

    before = _hashes()
    app = create_v2_app(market=real_market, demo_market=demo_market)
    async with http_client(app, "127.0.0.1") as client:
        base = "/api/v2/"
        for path in (
            "overview",
            "portfolio",
            "positions/EURO-CYCLES",
            "discovery",
            "stocks/EURO-CYCLES",
            "attribution",
            "research-lab",
            "health",
        ):
            response = await client.get(base + path, params={"mode": mode})
            assert response.status_code == 200, (path, response.text)
            data = response.json()
            if path == "portfolio":
                assert data["account_state_conflict"] == (mode == "REAL_COMPETITION")
                assert ("confirmed_ledger" in data["snapshots"]) == (mode == "REAL_COMPETITION")
            if path == "attribution":
                assert data["benchmarks"]["TUNINDEX"]["value"] is None
            if path == "research-lab":
                assert len(data["experiments"]) == 9
                assert len(data["phase_sensitivity"]["LEGACY-G-APPROX"]["phase_returns"]) == 20
                if mode == "REAL_COMPETITION":
                    assert all(e["sample_count"] == 0 for e in data["experiments"])
        for path in (
            "decisions/buy-scenario",
            "positions/sell-scenario",
            "positions/protection-scenario",
        ):
            response = await client.post(
                base + path,
                params={"mode": mode},
                json={"instrument_id": "EURO-CYCLES", "quantity": 1, "limit_price_tnd": "10.160"},
            )
            assert response.status_code == 200, (path, response.text)
            data = response.json()
            assert data["is_executed"] is False and data["gross_tnd"]["status"] == "SIMULATED"
            if mode == "REAL_COMPETITION":
                assert (
                    not data["is_valid"] and "ACCOUNT_STATE_CONFLICT" in data["rejection_reasons"]
                )
        for symbol in ("MNP", "SCN"):
            response = await client.post(
                base + "decisions/buy-scenario",
                params={"mode": mode},
                json={"instrument_id": symbol, "quantity": 1, "limit_price_tnd": "10.00"},
            )
            assert response.status_code == 200
            assert "RESTRICTED_CHALLENGE" in response.json()["rejection_reasons"]
        for origin in (
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "https://external.example",
        ):
            response = await client.options(
                base + "health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
            )
            assert response.headers.get("access-control-allow-origin") == (
                None if "external" in origin else origin
            )
        assert (
            await client.get(base + "health", headers={"Host": "external.example"})
        ).status_code == 403
        invalid = await client.post(
            base + "positions/sell-scenario",
            params={"mode": mode},
            json={
                "instrument_id": "EURO-CYCLES",
                "quantity": 1,
                "limit_price_tnd": "10.000",
                "is_executed": True,
            },
        )
        assert invalid.status_code == 422
    async with http_client(app, "192.0.2.1") as remote:
        assert (await remote.get("/api/v2/health")).status_code == 403
    assert _hashes() == before


@pytest.mark.anyio
async def test_loopback_boundary_and_mode_consistency(demo_market: MarketData) -> None:
    from bvmt_v2.api import create_v2_app

    app = create_v2_app(demo_market=demo_market)
    path = "/api/v2/positions/protection-scenario"
    body = {
        "mode": "SYNTHETIC_DEMO",
        "instrument_id": "EURO-CYCLES",
        "quantity": 1,
        "limit_price_tnd": "8.000",
    }
    async with http_client(app, "127.0.0.1") as client:
        result = await client.post(path, json=body)
        assert (
            result.status_code == 200
            and result.json()["is_valid"]
            and result.json()["downside_loss_tnd"]["status"] == "SIMULATED"
        )
        assert (
            await client.post(path, params={"mode": "REAL_COMPETITION"}, json=body)
        ).status_code == 422
        assert (await client.post(path, json={**body, "limit_price_tnd": 8.1})).status_code == 422
        assert (
            await client.get("/api/v2/health", headers={"Host": "elsewhere.example"})
        ).status_code == 403
        assert (
            await client.post(path, json=body, headers={"Origin": "https://external.example"})
        ).status_code == 403
        result = await client.get(
            "/api/v2/research-lab",
            params={"mode": "SYNTHETIC_DEMO", "exit_instrument_id": "EURO-CYCLES", "horizon": "5"},
        )
        assert len(result.json()["exit_policy_comparison"]) == 9
        bars_resp = await client.get(
            "/api/v2/stocks/EURO-CYCLES/bars", params={"mode": "SYNTHETIC_DEMO", "limit": 10}
        )
        assert bars_resp.status_code == 200
        bars_payload = bars_resp.json()
        assert len(bars_payload["bars"]) == 10
        assert bars_payload["bars"][-1]["provenance"]["data_quality_status"] == "SYNTHETIC_FIXTURE"
        real_bars = await client.get(
            "/api/v2/stocks/EURO-CYCLES/bars", params={"mode": "REAL_COMPETITION", "limit": 5}
        )
        assert real_bars.status_code == 200
        real_prov = real_bars.json()["bars"][-1]["provenance"]
        assert real_prov["source_publication_time"] is None
        assert real_prov["data_quality_status"] == "EOD_UNVERIFIED_PUB_TIME"
        assert (
            await client.get("/api/v2/stocks/UNKNOWN_CORP/bars", params={"mode": "SYNTHETIC_DEMO"})
        ).status_code == 404
        health_payload = (
            await client.get("/api/v2/health", params={"mode": "SYNTHETIC_DEMO"})
        ).json()
        assert health_payload["execution_enabled"] is False
        assert health_payload["llm_live_enabled"] is False
        assert health_payload["rules_blocker_count"] == 72
        assert health_payload["published_at_present_count"] > 0
        real_health = (
            await client.get("/api/v2/health", params={"mode": "REAL_COMPETITION"})
        ).json()
        assert real_health["published_at_present_count"] == 0
    async with http_client(app, "192.0.2.1") as external:
        assert (await external.get("/api/v2/health")).status_code == 403
