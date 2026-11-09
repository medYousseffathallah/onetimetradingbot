"""Unit tests for deterministic BVMT position sizing engine.

Covers:
- Insufficient cash
- Existing position near concentration cap
- Zero quantity
- Fee computation and break-even price
- Pending orders reservation
- Stale prices
- Missing data / zero volume
- Thinly traded securities
- Invalid limit prices
- Portfolio concentration drift
"""

from decimal import Decimal

from bvmt.position_sizing import (
    PendingOrderReservation,
    PositionSizeInput,
    compute_position_size,
    quantize_tnd,
)


def test_standard_position_sizing_within_target_and_cash():
    """Verify standard sizing respecting target allocation and fee deduction."""
    inp = PositionSizeInput(
        instrument_id="STA",
        symbol="STA",
        limit_price_tnd=Decimal("115.900"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("49000.000"),
        median_daily_turnover_20s_tnd=Decimal("25500.000"),
        median_daily_volume_20s=220,
    )
    res = compute_position_size(inp)

    assert res.is_actionable is True
    # 10% of median volume (220) = 22 shares
    assert res.suggested_shares == 22
    assert res.binding_constraint == "liquidity"
    assert res.gross_order_value_tnd == quantize_tnd(Decimal(22) * Decimal("115.900"))
    assert res.gross_order_value_tnd == Decimal("2549.800")
    # Fee: 0.50% of 2549.800 = 12.749 TND
    assert res.purchase_fee_tnd == Decimal("12.749")
    assert res.total_purchase_cost_tnd == Decimal("2562.549")
    # Break-even price: 115.900 * 1.005 / 0.995 = 117.065 TND
    assert res.break_even_price_tnd == Decimal("117.065")
    assert res.proposed_position_weight_pct == Decimal("5.100")


def test_insufficient_cash():
    """Verify clean 0 shares when available cash cannot buy a single share."""
    inp = PositionSizeInput(
        instrument_id="AMEN_BANK",
        symbol="AMEN BANK",
        limit_price_tnd=Decimal("92.300"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("50.000"),  # Less than 92.300 TND
        median_daily_turnover_20s_tnd=Decimal("15000.000"),
        median_daily_volume_20s=160,
    )
    res = compute_position_size(inp)

    assert res.is_actionable is False
    assert res.suggested_shares == 0
    assert any("insufficient_cash" in r for r in res.rejection_reasons)
    assert res.cash_remaining_after_purchase_tnd == Decimal("50.000")


def test_existing_position_near_concentration_cap():
    """Verify position is trimmed so total exposure does not exceed target allocation."""
    # Target 8.5% of 50,000 = 4,250 TND
    # Existing 4,000 TND in stock -> remaining target room = 250 TND
    inp = PositionSizeInput(
        instrument_id="MONOPRIX",
        symbol="MONOPRIX",
        limit_price_tnd=Decimal("10.000"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("30000.000"),
        existing_shares=400,  # 400 * 10 = 4,000 TND
        median_daily_turnover_20s_tnd=Decimal("50000.000"),
        median_daily_volume_20s=5000,
    )
    res = compute_position_size(inp)

    # Room is 250 TND -> 25 shares
    assert res.suggested_shares == 25
    assert res.proposed_total_shares == 425
    assert res.proposed_position_value_tnd == Decimal("4250.000")
    assert res.proposed_position_weight_pct == Decimal("8.500")


def test_existing_position_at_or_above_concentration_cap():
    """Verify rejection when existing position already meets target allocation."""
    inp = PositionSizeInput(
        instrument_id="MONOPRIX",
        symbol="MONOPRIX",
        limit_price_tnd=Decimal("10.000"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("30000.000"),
        existing_shares=450,  # 4,500 TND > 8.5%
        median_daily_turnover_20s_tnd=Decimal("50000.000"),
        median_daily_volume_20s=5000,
    )
    res = compute_position_size(inp)

    assert res.is_actionable is False
    assert res.suggested_shares == 0
    assert any("concentration_cap_reached" in r for r in res.rejection_reasons)


def test_pending_orders_cash_reservation():
    """Verify cash reserved for pending buy orders is subtracted from available cash."""
    # 1,000 TND cash, but pending buy order reserves 800 TND -> effective cash 200 TND
    pending = PendingOrderReservation(
        order_id="po-1",
        instrument_id="OTHER",
        side="BUY",
        remaining_shares=10,
        limit_price_tnd=Decimal("79.600"),  # 796 + 3.98 = 799.98 TND
    )
    inp = PositionSizeInput(
        instrument_id="TEST",
        symbol="TEST",
        limit_price_tnd=Decimal("20.000"),
        portfolio_total_equity_tnd=Decimal("10000.000"),
        raw_available_cash_tnd=Decimal("1000.000"),
        pending_orders=[pending],
        median_daily_turnover_20s_tnd=Decimal("20000.000"),
        median_daily_volume_20s=1000,
    )
    res = compute_position_size(inp)

    assert res.cash_reserved_for_pending_orders_tnd == Decimal("799.980")
    # effective cash = 1000 - 799.980 = 200.020 TND
    assert res.effective_available_cash_tnd == Decimal("200.020")
    # Cost per share = 20 * 1.005 = 20.10 TND -> 200.02 / 20.10 = 9 shares
    assert res.suggested_shares == 9
    assert res.gross_order_value_tnd == Decimal("180.000")
    assert res.total_purchase_cost_tnd == Decimal("180.900")
    assert res.cash_remaining_after_purchase_tnd == Decimal("19.120")


def test_stale_prices_warning():
    """Verify warning when quote is older than 3 sessions."""
    inp = PositionSizeInput(
        instrument_id="STALE_STOCK",
        symbol="STALE",
        limit_price_tnd=Decimal("50.000"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("10000.000"),
        is_stale_quote=True,
        quote_age_sessions=15,
        median_daily_turnover_20s_tnd=Decimal("20000.000"),
        median_daily_volume_20s=400,
    )
    res = compute_position_size(inp)

    assert any("stale_reference_price" in w for w in res.warnings)


def test_missing_data_and_zero_volume():
    """Verify 0 shares and explicit rejection when median volume is 0."""
    inp = PositionSizeInput(
        instrument_id="DEAD_STOCK",
        symbol="DEAD",
        limit_price_tnd=Decimal("10.000"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("10000.000"),
        median_daily_turnover_20s_tnd=Decimal("0.000"),
        median_daily_volume_20s=0,
    )
    res = compute_position_size(inp)

    assert res.is_actionable is False
    assert res.suggested_shares == 0
    assert any("insufficient_liquidity" in r for r in res.rejection_reasons)


def test_thinly_traded_warning():
    """Verify warning when turnover is below 25,000 TND threshold."""
    inp = PositionSizeInput(
        instrument_id="THIN_STOCK",
        symbol="THIN",
        limit_price_tnd=Decimal("5.000"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("10000.000"),
        median_daily_turnover_20s_tnd=Decimal("6000.000"),
        median_daily_volume_20s=1200,
    )
    res = compute_position_size(inp)

    assert res.suggested_shares == 120  # 10% of 1200
    assert any("thin_daily_turnover" in w for w in res.warnings)


def test_invalid_limit_prices():
    """Verify rejection when limit price is zero or negative."""
    for invalid_price in [Decimal("0.000"), Decimal("-10.000")]:
        inp = PositionSizeInput(
            instrument_id="INV",
            symbol="INV",
            limit_price_tnd=invalid_price,
            portfolio_total_equity_tnd=Decimal("50000.000"),
            raw_available_cash_tnd=Decimal("10000.000"),
        )
        res = compute_position_size(inp)
        assert res.is_actionable is False
        assert res.suggested_shares == 0
        assert any("invalid_limit_price" in r for r in res.rejection_reasons)


def test_below_minimum_order_size_threshold():
    """Verify order is rejected if total gross amount is below 100 TND."""
    inp = PositionSizeInput(
        instrument_id="TINY",
        symbol="TINY",
        limit_price_tnd=Decimal("1.000"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("10000.000"),
        median_daily_turnover_20s_tnd=Decimal("500.000"),
        median_daily_volume_20s=50,  # 10% = 5 shares -> 5 TND < 100 TND minimum
    )
    res = compute_position_size(inp)

    assert res.is_actionable is False
    assert res.suggested_shares == 0
    assert any("below_minimum_order_size" in r for r in res.rejection_reasons)


def test_non_challenge_member_blocked_from_sizing():
    """Verify non-challenge securities (e.g. MONOPRIX, ESSOUKNA) are strictly non-actionable."""
    inp = PositionSizeInput(
        instrument_id="MONOPRIX",
        symbol="MNP",
        limit_price_tnd=Decimal("12.290"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("49608.050"),
        median_daily_turnover_20s_tnd=Decimal("45000.000"),
        median_daily_volume_20s=3600,
        is_challenge_member=False,
    )
    res = compute_position_size(inp)

    assert res.is_actionable is False
    assert res.suggested_shares == 0
    assert res.binding_constraint == "not_in_challenge_universe"
    assert any("not_in_challenge_universe" in r for r in res.rejection_reasons)
    assert res.is_challenge_member is False


def test_pre_market_non_cote_warning():
    """Verify pre-opening non-cote generates explicit liquidity warning without permanent disqualification."""
    inp = PositionSizeInput(
        instrument_id="STA",
        symbol="STA",
        limit_price_tnd=Decimal("115.900"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        raw_available_cash_tnd=Decimal("49608.050"),
        median_daily_turnover_20s_tnd=Decimal("25000.000"),
        median_daily_volume_20s=220,
        is_challenge_member=True,
        trading_activity_status="non_cote",
    )
    res = compute_position_size(inp)

    assert any("pre_market_non_cote" in w for w in res.warnings)
    assert res.is_challenge_member is True
    assert res.trading_activity_status == "non_cote"
