from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest

from bvmt.execution import (
    BacktestConfig,
    BacktestSignal,
    MarketOrder,
    OrderSide,
    estimate_next_bar_fill,
    run_historical_backtest,
)


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


def history(bars, *, volumes=(1000, 1000, 1000, 1000), prices=("10", "10", "10", "10")):
    return [
        replace(
            bars[0],
            session_date=date(2026, 1, 5 + i),
            open=Decimal(p),
            close=Decimal(p),
            high=Decimal(p) * Decimal("1.1"),
            low=Decimal(p) * Decimal("0.9"),
            volume_shares=v,
            turnover_tnd=Decimal(v) * Decimal(p),
            status="traded" if v else "no_trade",
        )
        for i, (v, p) in enumerate(zip(volumes, prices, strict=True))
    ]


def settings(**kwargs):
    return replace(
        BacktestConfig(), slippage_bps=Decimal(0), max_position_weight=Decimal(1), **kwargs
    )


def test_historical_t_plus_one_and_zero_volume(bars):
    series = history(bars, volumes=(1000, 0, 1000, 1000))
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 10)
    result = run_historical_backtest(series, [sig], config=settings())
    assert [f.session_date for f in result.fills] == [series[2].session_date]
    assert result.total_fees_tnd == Decimal("0.500")
    assert result.session_snapshots[0].cash_tnd == Decimal("100000")
    assert result.final_equity_tnd == Decimal("99999.500")


def test_partial_fills_expire_and_share_session_capacity(bars):
    series = history(bars, volumes=(100, 100, 100, 100))
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 25)
    result = run_historical_backtest(series, [sig, sig], config=settings(max_order_age_sessions=2))
    assert [f.quantity for f in result.fills] == [10, 10]
    assert result.orders[0].filled_quantity == 20
    assert result.orders[0].remaining_quantity == 5
    assert result.orders[1].filled_quantity == 0
    assert result.expired_or_unfilled_order_count == 2
    assert result.partial_fill_count == 1


def test_partial_carry_fully_fills(bars):
    series = history(bars, volumes=(100, 100, 100, 100))
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 25)
    result = run_historical_backtest(series, [sig], config=settings())
    assert [f.quantity for f in result.fills] == [10, 10, 5]
    assert result.orders[0].status == "FILLED"
    assert result.partial_fill_count == 1


def test_reject_ineligible_and_no_shorts(bars):
    series = history(bars)
    key = series[0].instrument_id
    sigs = [
        BacktestSignal(series[0].session_date, "UNKNOWN", OrderSide.BUY, 1),
        BacktestSignal(series[0].session_date, key, OrderSide.SELL, 1),
    ]
    result = run_historical_backtest(series, sigs, eligible_instruments={key})
    assert [o.rejection_reason for o in result.orders] == [
        "ineligible_instrument",
        "insufficient_holdings",
    ]
    assert result.rejected_order_count == 2
    assert not result.fills


def test_hand_calculated_fee_benchmark_and_drawdown(bars):
    series = history(bars, prices=("10", "10", "8", "9"))
    cfg = settings(initial_cash_tnd=Decimal("1000"), max_volume_participation=Decimal(1))
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 100)
    result = run_historical_backtest(series, [sig], config=cfg)
    # Both portfolios buy 99 shares at 10; fees 4.950; cash 5.050.
    assert result.fills[0].quantity == 99
    assert result.total_fees_tnd == Decimal("4.950")
    assert result.final_equity_tnd == Decimal("896.050")
    assert result.total_return_pct == Decimal("-10.395")
    assert result.equal_weight_benchmark_return_pct == result.total_return_pct
    assert result.max_drawdown_pct == Decimal("20.295")
    assert result.turnover_ratio == Decimal("0.99")
    assert result.cash_benchmark_return_pct == 0
    assert len(result.config_hash) == 64
    assert result.config_hash == run_historical_backtest(series, [sig], config=cfg).config_hash


@pytest.mark.parametrize("kwargs", [{"carry_pending_orders": False}, {"max_order_age_sessions": 1}])
def test_limits_and_no_carry(bars, kwargs):
    series = history(bars)
    sig = BacktestSignal(
        series[0].session_date, series[0].instrument_id, OrderSide.BUY, 10, Decimal("9")
    )
    result = run_historical_backtest(series, [sig], config=settings(**kwargs))
    assert not result.fills
    assert result.orders[0].status == "EXPIRED"


def test_buy_concentration_cap(bars):
    series = history(bars)
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 10000)
    result = run_historical_backtest(series, [sig], config=BacktestConfig())
    for snapshot in result.session_snapshots:
        assert snapshot.cash_tnd >= 0
        assert snapshot.holdings_value_tnd / snapshot.total_equity_tnd <= Decimal("0.20")


def test_calendar_counts_marketwide_missing_session_for_expiry(bars):
    from bvmt.calendar import ExchangeSession
    from bvmt.execution import TradingCalendar

    series = history(bars)
    missing = series[1].session_date
    calendar = TradingCalendar(
        tuple(
            ExchangeSession(
                b.session_date,
                True,
                "regular",
                datetime.combine(b.session_date, time(9), UTC),
                datetime.combine(b.session_date, time(14), UTC),
                "Africa/Tunis",
                "synthetic",
            )
            for b in series
        )
    )
    sparse = [b for b in series if b.session_date != missing]
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 10)
    result = run_historical_backtest(
        sparse, [sig], config=settings(max_order_age_sessions=1), calendar=calendar
    )
    assert result.session_count == 4
    assert not result.fills and result.orders[0].status == "EXPIRED"
    assert result.session_snapshots[1].session_date == missing


def test_sell_caps_to_owned_shares_and_charges_fee(bars):
    series = history(bars)
    key = series[0].instrument_id
    sigs = [
        BacktestSignal(series[0].session_date, key, OrderSide.BUY, 10),
        BacktestSignal(series[1].session_date, key, OrderSide.SELL, 20),
    ]
    result = run_historical_backtest(series, sigs, config=settings())
    assert [f.quantity for f in result.fills] == [10, 10]
    assert result.total_fees_tnd == Decimal("1.000")
    assert result.final_equity_tnd == Decimal("99999.000")
    assert all(s.holdings_value_tnd >= 0 for s in result.session_snapshots)


def test_future_prices_do_not_change_earlier_equity(bars):
    series = history(bars)
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 10)
    original = run_historical_backtest(series, [sig], config=settings())
    series[-1] = replace(
        series[-1], open=Decimal("20"), close=Decimal("20"), high=Decimal("22"), low=Decimal("18")
    )
    changed = run_historical_backtest(series, [sig], config=settings())
    assert original.session_snapshots[:-1] == changed.session_snapshots[:-1]
    assert original.fills == changed.fills


def test_next_typical_uses_next_session_bar(bars):
    series = history(bars)
    series[1] = replace(series[1], high=Decimal("12"), low=Decimal("9"), close=Decimal("12"))
    sig = BacktestSignal(series[0].session_date, series[0].instrument_id, OrderSide.BUY, 10)
    result = run_historical_backtest(series, [sig], config=settings(fill_price_mode="next_typical"))
    assert result.fills[0].price_tnd == Decimal("11")
    assert result.fills[0].session_date == series[1].session_date
