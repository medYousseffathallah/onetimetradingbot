"""Decision cutoffs and missing market evidence must not be invented."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from bvmt import macro_events
from bvmt.multi_horizon import evaluate_multi_horizon_intelligence


def _report(rankings=(), **kwargs):
    return evaluate_multi_horizon_intelligence(
        portfolio_equity_tnd=Decimal("50000"),
        available_cash_tnd=Decimal("40000"),
        held_positions=kwargs.pop("held_positions", {}),
        market_rankings=list(rankings),
        **kwargs,
    )


def _rank(**kwargs):
    values = dict(
        instrument_id="BH_BANK",
        symbol="BH BANK",
        rank=1,
        close_tnd=Decimal("10"),
        short_return_pct=Decimal("5"),
        long_return_pct=Decimal("12"),
        median_turnover_tnd=Decimal("20000"),
    )
    return SimpleNamespace(**(values | kwargs))


def test_october_decision_excludes_all_six_future_macro_events():
    cutoff = datetime(2026, 10, 9, 16, tzinfo=UTC)
    report = _report(decision_timestamp=cutoff)
    assert report.session_date == "2026-10-09"
    assert report.macro_events == []
    assert report.as_of == cutoff.isoformat()


def test_exact_publication_boundary_and_unknown_dates(monkeypatch):
    cutoff = datetime(2026, 10, 15, 14, 30, tzinfo=UTC)
    original = macro_events.VERIFIED_MACRO_EVENTS[0]
    monkeypatch.setattr(
        macro_events,
        "VERIFIED_MACRO_EVENTS",
        [
            original,
            replace(original, event_id="unknown", published_at=None),
            replace(original, event_id="date-only", published_at="2026-10-15"),
            replace(original, event_id="naive", published_at="2026-10-15T14:00:00"),
        ],
    )
    assert [e.event_id for e in macro_events.get_verified_macro_intelligence(cutoff)] == [
        original.event_id
    ]
    assert (
        macro_events.get_verified_macro_intelligence(datetime(2026, 10, 15, 14, 29, tzinfo=UTC))
        == []
    )
    assert macro_events.get_verified_macro_intelligence() == []
    with pytest.raises(ValueError, match="aware"):
        macro_events.get_verified_macro_intelligence(datetime(2026, 10, 15))


def test_decision_requires_date_and_rejects_conflicting_or_naive_timestamp():
    with pytest.raises(ValueError):
        _report()
    with pytest.raises(ValueError, match="aware"):
        _report(decision_timestamp=datetime(2026, 10, 9))
    with pytest.raises(ValueError, match="session"):
        _report(
            as_of_session="2026-10-08", decision_timestamp=datetime(2026, 10, 9, 16, tzinfo=UTC)
        )


def test_date_only_compatibility_never_exposes_same_day_publication():
    report = _report(as_of_session="2026-10-15")
    assert report.macro_events == []


def test_zero_momentum_does_not_fall_back_to_conflicting_ratio_or_rank():
    report = _report(
        [
            _rank(
                short_return_pct=Decimal("0"),
                momentum_20s=Decimal("9.99"),
                long_return_pct=Decimal("0"),
            )
        ],
        as_of_session="2026-11-10",
    )
    assert report.swing_candidates == []
    assert report.position_candidates == []


def test_ratio_inputs_have_same_percent_meaning_as_percent_inputs():
    ratio = _rank()
    del ratio.short_return_pct
    del ratio.long_return_pct
    ratio.momentum_20s = Decimal("0.05")
    ratio.momentum_60s = Decimal("0.12")
    explicit = _report([_rank()], as_of_session="2026-11-10")
    converted = _report([ratio], as_of_session="2026-11-10")
    assert (
        converted.swing_candidates[0].supporting_factors
        == explicit.swing_candidates[0].supporting_factors
    )
    assert (
        converted.position_candidates[0].supporting_factors
        == explicit.position_candidates[0].supporting_factors
    )


def test_missing_liquidity_cannot_create_actionable_quantity():
    report = _report([_rank(median_turnover_tnd=None)], as_of_session="2026-11-10")
    candidate = report.swing_candidates[0]
    assert candidate.quantity_limit == 0
    assert candidate.decision_status == "INSUFFICIENT_EVIDENCE"
    assert not any("10000 TND" in factor for factor in candidate.supporting_factors)
    assert any("liquidity" in x.lower() for x in candidate.limitations)


def test_missing_quote_does_not_use_cost_price_for_held_position():
    report = _report(
        as_of_session="2026-11-10",
        held_positions={"BH BANK": {"quantity": 30, "average_cost_tnd": "13.065"}},
    )
    item = report.active_position_reviews[0]
    assert item.price_reference is None
    assert item.quantity_limit == 0
    assert item.decision_status == "INSUFFICIENT_EVIDENCE"
    assert item.risk_constraints["current_weight_pct"] is None
    assert not any("Unrealized return: +0" in factor for factor in item.supporting_factors)


def test_review_dates_follow_decision_without_inventing_exchange_sessions():
    report = _report([_rank()], as_of_session="2026-10-09")
    for item in report.swing_candidates + report.position_candidates:
        assert item.review_date == "2026-10-09"
        assert item.exit_triggers["time_stop_sessions"] in {20, 60}
