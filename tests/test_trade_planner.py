"""Unit tests for the BVMT trade planner service."""

from datetime import date
from decimal import Decimal

from bvmt.trade_planner import build_manual_trade_plan


def test_build_manual_trade_plan_actionable_top_rank():
    """Verify complete trade plan construction for a top ranked candidate."""
    plan = build_manual_trade_plan(
        instrument_id="STA",
        symbol="STA",
        stock_name="Société Tunisienne d'Automobiles",
        isin="TN0007800014",
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("115.900"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49608.050"),
        median_daily_turnover_20s_tnd=Decimal("25500.000"),
        median_daily_volume_20s=220,
        research_rank=1,
        composite_score=Decimal("10.2069"),
        momentum_20s=Decimal("0.0585"),
        momentum_60s=Decimal("0.1240"),
        intended_holding_horizon_sessions=20,
        as_of_session=date(2026, 11, 6),
    )

    assert plan.plan_id == "PLAN-2026-11-06-STA"
    assert plan.plan_category == "MANUAL_ORDER_PLAN"
    assert plan.is_actionable is True
    assert plan.suggested_max_shares == 22
    assert plan.estimated_gross_order_value_tnd == Decimal("2549.800")
    assert plan.estimated_purchase_fee_tnd == Decimal("12.749")
    assert plan.break_even_price_tnd == Decimal("117.065")
    assert plan.intended_holding_horizon_sessions == 20
    assert plan.confidence_status == "EXPLORATORY_RESEARCH"
    assert plan.validation_status == "INSUFFICIENT_MULTI_YEAR_EVIDENCE"
    assert plan.exit_conditions.stop_loss_price_tnd == Decimal("110.105")
    assert plan.exit_conditions.profit_target_price_tnd == Decimal("129.808")

    d = plan.to_dict()
    assert d["symbol"] == "STA"
    assert d["suggested_max_shares"] == 22


def test_build_manual_trade_plan_insufficient_cash():
    """Verify non-actionable trade plan with rejection reason when cash is zero."""
    plan = build_manual_trade_plan(
        instrument_id="STA",
        symbol="STA",
        stock_name="STA",
        isin="TN0007800014",
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("115.900"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("50.000"),
        median_daily_turnover_20s_tnd=Decimal("25500.000"),
        median_daily_volume_20s=220,
        research_rank=1,
    )

    assert plan.is_actionable is False
    assert plan.suggested_max_shares == 0
    assert any("insufficient_cash" in r for r in plan.rejection_reasons)
    assert plan.plan_category == "RESEARCH_CANDIDATE"


def test_trade_planner_blocks_non_challenge_member():
    """Verify non-challenge candidates (e.g. MONOPRIX, ESSOUKNA) are strictly non-actionable in challenge mode."""
    # MONOPRIX (MNP)
    mnp_plan = build_manual_trade_plan(
        instrument_id="MONOPRIX",
        symbol="MNP",
        stock_name="Société Nouvelle Maison de la Ville de Tunis",
        isin="TN0001000108",
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("12.290"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49608.050"),
        median_daily_turnover_20s_tnd=Decimal("45000.000"),
        median_daily_volume_20s=3600,
        research_rank=2,
        universe="TUNIS_BOURSE_CHALLENGE",
    )

    assert mnp_plan.is_actionable is False
    assert mnp_plan.suggested_max_shares == 0
    assert mnp_plan.plan_category == "RESEARCH_CANDIDATE"
    assert mnp_plan.in_challenge_universe is False
    assert mnp_plan.order_entry_eligibility == "NOT_IN_UNIVERSE"
    assert any("not_in_challenge_universe" in r for r in mnp_plan.rejection_reasons)

    # ESSOUKNA (SCN)
    scn_plan = build_manual_trade_plan(
        instrument_id="ESSOUKNA",
        symbol="SCN",
        stock_name="Société Essoukna",
        isin="TN0007210016",
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("4.640"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49608.050"),
        median_daily_turnover_20s_tnd=Decimal("5800.000"),
        median_daily_volume_20s=1250,
        research_rank=3,
        universe="TUNIS_BOURSE_CHALLENGE",
    )

    assert scn_plan.is_actionable is False
    assert scn_plan.suggested_max_shares == 0
    assert scn_plan.plan_category == "RESEARCH_CANDIDATE"
    assert scn_plan.in_challenge_universe is False
    assert scn_plan.order_entry_eligibility == "NOT_IN_UNIVERSE"


def test_trade_planner_permits_non_challenge_member_in_full_bvmt_research():
    """Verify non-challenge candidates can be sized when explicitly requesting FULL_BVMT_RESEARCH."""
    mnp_plan = build_manual_trade_plan(
        instrument_id="MONOPRIX",
        symbol="MNP",
        stock_name="Société Nouvelle Maison de la Ville de Tunis",
        isin="TN0001000108",
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("12.290"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49608.050"),
        median_daily_turnover_20s_tnd=Decimal("45000.000"),
        median_daily_volume_20s=3600,
        research_rank=2,
        universe="FULL_BVMT_RESEARCH",
    )

    assert mnp_plan.is_actionable is True
    assert mnp_plan.suggested_max_shares == 345
    assert mnp_plan.plan_category == "MANUAL_ORDER_PLAN"
    assert mnp_plan.universe == "FULL_BVMT_RESEARCH"


def test_trade_planner_pre_market_non_cote():
    """Verify pre-market non-cote sets awaiting opening match status without permanent disqualification."""
    plan = build_manual_trade_plan(
        instrument_id="STA",
        symbol="STA",
        stock_name="Société Tunisienne d'Automobiles",
        isin="TNNGTFLC2986",
        market_segment="PRINCIPAL",
        limit_price_tnd=Decimal("115.900"),
        portfolio_total_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49608.050"),
        median_daily_turnover_20s_tnd=Decimal("25500.000"),
        median_daily_volume_20s=220,
        research_rank=1,
        trading_activity_status="non_cote",
    )

    assert plan.trading_activity_status == "non_cote"
    assert plan.execution_feasibility_status == "AWAITING_OPENING_MATCH"
    assert any("non coté" in w for w in plan.execution_warnings)
    assert plan.in_challenge_universe is True
