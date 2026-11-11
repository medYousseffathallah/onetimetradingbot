"""Missing marks cannot manufacture portfolio exposure or concentration capacity."""

from datetime import UTC, date, datetime
from decimal import Decimal

from bvmt.calendar import ExchangeSession, InstrumentRecord, SuspensionRecord
from bvmt.data import DailyBar
from bvmt.research_coverage import evaluate_market_research_coverage
from bvmt.sparse_research import evaluate_sparse_market_research


def _record(key, *, isin=None, valid_from=date(2026, 1, 1)):
    return InstrumentRecord(
        key,
        isin,
        key,
        valid_from,
        None,
        valid_from,
        None,
        "principal_continu",
        "TND",
        "synthetic-risk-test",
    )


def _bar(key, day, price, *, isin=None):
    px = Decimal(price)
    ts = datetime(2026, 1, day, 16, tzinfo=UTC)
    return DailyBar(
        key,
        key,
        ts.date(),
        px,
        px,
        px,
        px,
        1000 if px > 0 else 0,
        px * 1000,
        "traded" if px > 0 else "untraded",
        "synthetic-risk-test",
        ts,
        ts,
        isin,
    )


def _calendar():
    return [
        ExchangeSession(
            date(2026, 1, day),
            True,
            "synthetic",
            datetime(2026, 1, day, 9, tzinfo=UTC),
            datetime(2026, 1, day, 16, tzinfo=UTC),
            "Africa/Tunis",
            "test",
        )
        for day in (1, 2, 3)
    ]


def _report(held, sectors=None):
    return evaluate_sparse_market_research(
        [_record("ALPHA"), _record("BETA")],
        _calendar(),
        [_bar("ALPHA", day, "10") for day in (1, 2, 3)],
        datetime(2026, 1, 3, 17, tzinfo=UTC),
        held_positions=held,
        sector_by_instrument=sectors or {"ALPHA": "BANK", "BETA": "INDUSTRY"},
    )


def test_missing_quote_does_not_value_holdings_at_cost_or_create_headroom():
    result = _report({"BETA": {"quantity": 10, "average_cost_tnd": "100"}})
    risk = result.by_instrument["BETA"].portfolio_risk
    assert risk.held_shares == 10
    assert risk.held_value_tnd is None
    assert risk.held_weight_pct is None
    assert risk.cap_headroom_tnd is None
    assert risk.cap_headroom_shares is None
    assert risk.sector_exposure_pct is None
    assert risk.risk_evidence_warnings
    payload = risk.to_dict()
    for field in ("held_value_tnd", "held_weight_pct", "cap_headroom_tnd", "sector_exposure_pct"):
        assert payload[field] is None
    assert result.by_instrument["BETA"].explanation.missing_data


def test_unknown_held_sector_cannot_imply_zero_sector_exposure():
    result = _report({"UNMAPPED": {"quantity": 10, "latest_price_tnd": "30"}})
    assert all(a.portfolio_risk.sector_exposure_pct is None for a in result.assessments)
    assert all(a.portfolio_risk.sector_concentration_warning for a in result.assessments)


def test_empty_portfolio_has_known_zero_exposure_without_quotes():
    result = _report({})
    risk = result.by_instrument["BETA"].portfolio_risk
    assert risk.held_value_tnd == 0
    assert risk.held_weight_pct == 0
    assert risk.sector_exposure_pct == 0
    assert risk.cap_headroom_shares is None


def test_known_mark_preserves_real_exposure_without_using_cost():
    result = _report(
        {"BETA": {"quantity": 10, "average_cost_tnd": "100", "latest_price_tnd": "20"}}
    )
    risk = result.by_instrument["BETA"].portfolio_risk
    assert risk.held_value_tnd == 200
    assert risk.held_weight_pct == Decimal("0.400")
    assert risk.cap_headroom_tnd == 4800
    assert risk.sector_exposure_pct == Decimal("0.400")


def test_coverage_joins_verified_poulina_source_periods():
    old, new = "POULINA_GROUP_HOLDING", "POULINA_GP_HOLDING"
    isin = "TN0005700018"
    result = evaluate_market_research_coverage(
        [_record(old, isin=isin), _record(new, isin=isin, valid_from=date(2026, 1, 3))],
        _calendar(),
        [
            _bar(old, 1, "10", isin=isin),
            _bar(old, 2, "11", isin=isin),
            _bar(new, 3, "12", isin=isin),
        ],
        datetime(2026, 1, 3, 17, tzinfo=UTC),
    )
    assert set(result.by_instrument) == {new}
    assert result.by_instrument[new].observed_bars == 3


def test_alias_projection_retains_suspension_on_canonical_security():
    old, new = "POULINA_GROUP_HOLDING", "POULINA_GP_HOLDING"
    isin = "TN0005700018"
    result = evaluate_sparse_market_research(
        [_record(old, isin=isin), _record(new, isin=isin, valid_from=date(2026, 1, 3))],
        _calendar(),
        [
            _bar(old, 1, "10", isin=isin),
            _bar(old, 2, "11", isin=isin),
            _bar(new, 3, "12", isin=isin),
        ],
        datetime(2026, 1, 3, 17, tzinfo=UTC),
        suspensions=[SuspensionRecord(old, date(2026, 1, 3), "synthetic-suspension")],
    )
    assert result.by_instrument[new].trading_eligibility.status == "SUSPENDED_AT_CUTOFF"
    assert not result.by_instrument[new].is_selected_candidate
