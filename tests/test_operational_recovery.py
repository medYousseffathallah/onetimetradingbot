"""Offline P0 contracts; all portfolio writes are isolated in pytest temp directories."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bvmt.api import _guard_plan, _operational_blockers, create_app
from bvmt.browser import resolve_canonical_instrument
from bvmt.challenge_universe import classify_security_challenge_status, resolve_challenge_record
from bvmt.trade_planner import build_manual_trade_plan

pytest_plugins = ["test_api"]


def test_distinct_leasing_symbols_and_conflicting_identity():
    assert resolve_challenge_record("TJL").canonical_instrument_id == "ATTIJARI_LEASING"
    assert resolve_challenge_record("TLS").canonical_instrument_id == "TUNISIE_LEASING_F"
    with pytest.raises(ValueError, match="Conflicting"):
        resolve_canonical_instrument("BH", isin="TNNGTFLC2986")


def test_plan_does_not_invent_close_time():
    plan = build_manual_trade_plan(
        instrument_id="STA",
        symbol="STA",
        stock_name="STA",
        isin=None,
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("100"),
        portfolio_total_equity_tnd=Decimal("50000"),
        available_cash_tnd=Decimal("40000"),
        as_of_session=date(2026, 11, 10),
    )
    assert "16:00" not in plan.data_timestamp


def test_rankings_block_nonmembers_even_with_buy_signal(service):
    state = service.load_state()
    card = replace(
        state.recommendations.recommendations[0],
        instrument_id="MONOPRIX",
        symbol="MNP",
        category="BUY CANDIDATE",
        suggested_side="BUY",
        suggested_shares=10,
        blocked_reasons=[],
    )
    state = replace(
        state,
        data_is_synthetic=False,
        recommendations=replace(state.recommendations, recommendations=[card]),
    )
    with patch.object(service, "load_state", return_value=state):
        with TestClient(create_app(service)) as client:
            item = client.get("/api/rankings").json()["rankings"][0]
    assert item["recommendation_category"] == "NO TRADE"
    assert item["suggested_shares"] == 0
    assert "not_in_challenge_universe" in item["blocked_reasons"]


def test_unknown_quote_and_unsynced_account_cannot_create_plan(service):
    before = service.resolve_context().ledger_path.read_bytes()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/api/trade-plans/calculate",
            json={
                "instrument_id": "STA",
                "symbol": "STA",
                "limit_price_tnd": "115.900",
                "portfolio_mode": "REAL_COMPETITION",
            },
        )
    assert response.status_code == 200
    plan = response.json()
    assert plan["is_actionable"] is False
    assert plan["suggested_max_shares"] == 0
    assert "quote_evidence_unavailable" in plan["rejection_reasons"]
    assert "pending_orders_unverified" in plan["rejection_reasons"]
    assert plan["current_quote_timestamp"] is None
    assert service.resolve_context().ledger_path.read_bytes() == before


@pytest.mark.parametrize(
    "instrument_id,symbol,isin",
    [
        ("STA", "BH", None),
        ("MONOPRIX", "STA", None),
        ("BH_BANK", "BH", "TNNGTFLC2986"),
    ],
)
def test_conflicting_identifiers_never_create_membership(instrument_id, symbol, isin):
    status = classify_security_challenge_status(instrument_id, symbol=symbol, isin=isin)
    assert status["in_challenge_universe"] is False
    assert status["quote_freshness"] == "UNKNOWN"


def test_alias_isin_conflict_is_rejected():
    with pytest.raises(ValueError, match="Conflicting"):
        resolve_canonical_instrument("BH ASSURANCE", isin="TNNGTFLC2986")


def verified_state(service):
    state = service.load_state()
    latest = date.fromisoformat(state.latest_bar_session_str)
    analytics = replace(
        state.research_coverage.analytics[0],
        instrument_id="STA",
        symbol="STA",
        isin="TNNGTFLC2986",
        last_traded_date=latest,
        last_verified_price=Decimal("100"),
        quote_age_sessions=0,
    )
    state.ledger.pending_orders_verified = True
    state.ledger.transactions_imported = True
    return replace(
        state,
        data_is_synthetic=False,
        rule_blockers=[],
        pending_browser_snapshot=None,
        data_freshness_sessions_behind=0,
        account_snapshot=replace(
            state.account_snapshot,
            capture_timestamp=f"{latest}T15:00:00+00:00",
            live_synchronized=True,
        ),
        research_coverage=replace(state.research_coverage, by_instrument={"STA": analytics}),
    )


def test_ready_state_and_quote_cutoff(service):
    state = verified_state(service)
    assert _operational_blockers(state, "STA", "STA") == []
    assert "instrument_mapping_conflict" in _operational_blockers(state, "STA", "BH")
    an = state.research_coverage.by_instrument["STA"]
    for changed in (
        replace(an, quote_age_sessions=-1),
        replace(an, last_traded_date=an.last_traded_date + timedelta(days=1)),
    ):
        future = replace(
            state,
            research_coverage=replace(state.research_coverage, by_instrument={"STA": changed}),
        )
        assert "future_quote_evidence" in _operational_blockers(future, "STA", "STA")
    stale = replace(state, data_freshness_sessions_behind=1)
    assert "stale_quote" in _operational_blockers(stale, "STA", "STA")


def test_blocked_plan_has_consistent_financials_and_observed_price(service):
    state = verified_state(service)
    plan = build_manual_trade_plan(
        instrument_id="STA",
        symbol="STA",
        stock_name="STA",
        isin="TNNGTFLC2986",
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("110"),
        portfolio_total_equity_tnd=Decimal("50000"),
        available_cash_tnd=Decimal("40000"),
        median_daily_turnover_20s_tnd=Decimal("100000"),
        median_daily_volume_20s=1000,
        research_rank=1,
        as_of_session=date(2026, 11, 10),
    ).to_dict()
    assert plan["is_actionable"] is True
    ready = _guard_plan(dict(plan), state)
    assert ready["is_actionable"] is True
    assert ready["last_verified_price_tnd"] == "100"
    assert ready["proposed_limit_price_tnd"] == "110"
    state.ledger.pending_orders_verified = False
    blocked = _guard_plan(dict(plan), state)
    assert blocked["suggested_max_shares"] == 0
    for key in (
        "estimated_gross_order_value_tnd",
        "estimated_purchase_fee_tnd",
        "estimated_total_purchase_cost_tnd",
        "estimated_sale_fee_tnd",
    ):
        assert Decimal(blocked[key]) == 0
    assert blocked["cash_remaining_after_purchase_tnd"] == blocked["effective_available_cash_tnd"]


@pytest.mark.parametrize("isin", ["TNNGTFLC2986", "TN_UNKNOWN"])
def test_unknown_name_cannot_hide_isin_display_conflict(isin):
    with pytest.raises(ValueError, match="Conflicting"):
        resolve_canonical_instrument("unrecognized company", isin=isin, displayed_symbol="BH")


def test_pending_sync_blocks_an_otherwise_verified_state(service, snapshot):
    state = replace(verified_state(service), pending_browser_snapshot=snapshot)
    assert _operational_blockers(state, "STA", "STA") == ["portfolio_sync_pending"]


def test_unknown_competition_rules_keep_plans_blocked(service):
    state = replace(verified_state(service), rule_blockers=["edition:not_verified"])
    assert _operational_blockers(state, "STA", "STA") == ["competition_rules_unverified"]
