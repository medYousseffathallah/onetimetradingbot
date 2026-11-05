from datetime import date
from decimal import Decimal

import pytest

from bvmt.execution import MarketOrder, estimate_next_bar_fill


def test_no_same_session_fill(bars):
    bar = bars[0]
    order = MarketOrder(bar.instrument_id, bar.session_date, "buy", 100)
    result = estimate_next_bar_fill(
        order, bar, participation_rate=Decimal("0.05"), remaining_shared_capacity=50
    )
    assert result.quantity == 0 and result.reason == "not_a_later_session"


def test_zero_volume_never_fills(bars):
    bar = bars[-1]
    order = MarketOrder(bar.instrument_id, date(2026, 1, 1), "buy", 100)
    result = estimate_next_bar_fill(
        order, bar, participation_rate=Decimal("0.05"), remaining_shared_capacity=0
    )
    assert result.quantity == 0 and result.reason == "not_tradable"


def test_decimal_cost_and_partial_fill(bars):
    bar = bars[0]
    order = MarketOrder(bar.instrument_id, date(2026, 1, 1), "buy", 100)
    result = estimate_next_bar_fill(
        order, bar, participation_rate=Decimal("0.05"), remaining_shared_capacity=50
    )
    assert result.quantity == 50
    assert result.price == Decimal("10.020")
    assert result.fee == Decimal("1.503")


def test_shared_capacity_must_be_consumed_by_caller(bars):
    bar = bars[0]
    order = MarketOrder(bar.instrument_id, date(2026, 1, 1), "buy", 30)
    first = estimate_next_bar_fill(
        order, bar, participation_rate=Decimal("0.05"), remaining_shared_capacity=50
    )
    second = estimate_next_bar_fill(
        order,
        bar,
        participation_rate=Decimal("0.05"),
        remaining_shared_capacity=50 - first.quantity,
    )
    assert first.quantity == 30 and second.quantity == 20
    assert first.quantity + second.quantity == 50


def test_capacity_larger_than_assumption_is_rejected(bars):
    order = MarketOrder(bars[0].instrument_id, date(2026, 1, 1), "buy", 100)
    with pytest.raises(ValueError, match="capacity"):
        estimate_next_bar_fill(
            order, bars[0], participation_rate=Decimal("0.05"), remaining_shared_capacity=51
        )


def test_out_of_range_slippage_is_not_a_fictitious_fill(bars):
    order = MarketOrder(bars[0].instrument_id, date(2026, 1, 1), "buy", 100)
    result = estimate_next_bar_fill(
        order,
        bars[0],
        participation_rate=Decimal("0.05"),
        remaining_shared_capacity=50,
        slippage_bps=Decimal("1000"),
    )
    assert result.quantity == 0
    assert result.reason == "assumed_price_outside_observed_bar"


def test_sell_slippage_is_unfavorable(bars):
    order = MarketOrder(bars[0].instrument_id, date(2026, 1, 1), "sell", 10)
    result = estimate_next_bar_fill(
        order, bars[0], participation_rate=Decimal("0.05"), remaining_shared_capacity=50
    )
    assert result.price < bars[0].open


@pytest.mark.parametrize("rate", [Decimal("0"), Decimal("-1"), Decimal("2"), Decimal("NaN")])
def test_bad_participation_rate_rejected(bars, rate):
    order = MarketOrder(bars[0].instrument_id, date(2026, 1, 1), "buy", 10)
    with pytest.raises(ValueError, match="Participation"):
        estimate_next_bar_fill(order, bars[0], participation_rate=rate, remaining_shared_capacity=0)


def test_wrong_security_rejected(bars):
    order = MarketOrder("WRONG", date(2026, 1, 1), "buy", 10)
    with pytest.raises(ValueError, match="mismatch"):
        estimate_next_bar_fill(
            order, bars[0], participation_rate=Decimal("0.05"), remaining_shared_capacity=50
        )
