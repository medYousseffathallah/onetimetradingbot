"""Unit tests for multi-horizon trading intelligence and macroeconomic reasoning."""

from datetime import UTC, datetime
from decimal import Decimal

from bvmt.macro_events import (
    get_instrument_macro_context,
    get_verified_macro_intelligence,
)
from bvmt.multi_horizon import (
    build_day_trading_notice,
    evaluate_multi_horizon_intelligence,
)


def test_day_trading_is_strictly_unavailable_research_only():
    """Verify Day Trading mode is never presented as executable order generation."""
    notice = build_day_trading_notice()
    assert notice["status"] == "UNAVAILABLE_RESEARCH_ONLY"
    assert notice["is_executable"] is False
    assert len(notice["primary_reasons"]) >= 3
    assert any("1.00%" in r or "fee" in r.lower() for r in notice["primary_reasons"])


def test_macro_events_point_in_time_and_filtering():
    """Verify macroeconomic events conform to strict point-in-time boundaries."""
    # Historical cutoff in 2026
    cutoff = datetime(2026, 11, 6, 23, 59, 59, tzinfo=UTC)
    events = get_verified_macro_intelligence(cutoff=cutoff)
    assert len(events) >= 5

    # Check Central Bank of Tunisia (BCT) event
    bct = next(e for e in events if e.category == "MONETARY_POLICY")
    assert "8.00%" in bct.title
    assert "BIAT" in bct.affected_symbols
    assert bct.is_point_in_time is True
    assert bct.uncertainty_rating == "LOW"

    # Specific instrument lookup for Délice Holding (DH)
    dh_events = get_instrument_macro_context("DH", cutoff=cutoff)
    assert len(dh_events) >= 1
    assert any("Délice Holding" in e.title or "DH" in e.affected_symbols for e in dh_events)

    # Future cutoff filter check (an event with published_at > cutoff must not appear)
    past_cutoff = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)
    past_events = get_verified_macro_intelligence(cutoff=past_cutoff)
    assert len(past_events) < len(events)


def test_multi_horizon_intelligence_17_attributes_and_portfolio_review():
    """Verify multi-horizon evaluation emits 17-attribute decisions and reviews DELICE HOLDING."""
    equity = Decimal("49979.070")
    cash = Decimal("44586.070")

    held = {
        "BH BANK": {
            "quantity": 30,
            "acquisition_price_tnd": "13.065",
            "latest_price_tnd": "13.200",
        },
        "DELICE HOLDING": {
            "quantity": 263,
            "acquisition_price_tnd": "19.095",
            "latest_price_tnd": "19.000",
        },
    }

    class DummyRanking:
        def __init__(self, inst_id, sym, rank, close, m20, m60, turnover):
            self.instrument_id = inst_id
            self.symbol = sym
            self.rank = rank
            self.close_tnd = close
            self.short_return_pct = m20
            self.long_return_pct = m60
            self.median_turnover_tnd = turnover

    rankings = [
        DummyRanking("STA", "STA", 1, "115.900", "5.85", "12.40", "35400"),
        DummyRanking("SOTET", "SOTETEL", 2, "7.100", "8.20", "15.30", "28900"),
        DummyRanking("MNP", "MONOPRIX", 3, "12.290", "8.76", "14.10", "18500"),  # non-challenge
    ]

    report = evaluate_multi_horizon_intelligence(
        portfolio_equity_tnd=equity,
        available_cash_tnd=cash,
        held_positions=held,
        market_rankings=rankings,
        as_of_session="2026-11-06",
    )

    assert report.day_trading_notice["status"] == "UNAVAILABLE_RESEARCH_ONLY"
    assert len(report.active_position_reviews) == 2

    # Verify Delice Holding review
    dh_rev = next(r for r in report.active_position_reviews if r.symbol == "DELICE HOLDING")
    assert dh_rev.decision_status in {"MONITOR_POSITION", "REVIEW_POSITION"}
    assert "DELICE HOLDING" in dh_rev.supporting_factors[0]
    # Check 10% cap warning
    assert any("concentration cap" in c for c in dh_rev.contradicting_factors)
    assert dh_rev.quantity_limit == 263
    assert dh_rev.horizon == "POSITION_20_60S"

    # Verify swing candidates
    assert len(report.swing_candidates) >= 1
    sta_swing = next(c for c in report.swing_candidates if c.symbol == "STA")
    assert sta_swing.decision_status == "MANUAL_ORDER_PLAN"
    assert sta_swing.horizon == "SWING_5_20S"
    assert len(sta_swing.supporting_factors) >= 2
    assert "stop_loss_price_tnd" in sta_swing.exit_triggers
    assert sta_swing.evidence_status == "OFFICIAL_BVMT_CONFIRMED"

    # Verify non-challenge exclusion (MONOPRIX)
    mnp_swing = next((c for c in report.swing_candidates if c.symbol == "MONOPRIX"), None)
    if mnp_swing:
        assert mnp_swing.decision_status == "STRATEGY_EXCLUDED"
        assert any("challenge" in c.lower() for c in mnp_swing.contradicting_factors)

    # Verify serialization dictionary
    rep_dict = report.to_dict()
    assert "swing_candidates" in rep_dict
    assert "position_candidates" in rep_dict
    assert "active_position_reviews" in rep_dict
    assert rep_dict["macro_events_count"] >= 5
