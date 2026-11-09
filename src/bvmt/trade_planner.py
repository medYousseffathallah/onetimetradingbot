"""Trading Decision Engine & Manual Trade Planning Service.

Converts quantitative research candidates and portfolio state into structured,
reproducible, and risk-managed manual trade plans for the Tunis Bourse Challenge.

Key Guarantees:
1. 100% Manual Execution: All plans are decision support—never auto-submitted.
2. Complete Cost Accounting: Includes 0.50% purchase fee, 0.50% sale fee, and break-even price.
3. Strict Portfolio Constraints: Concentration limits (10% cap, 8.5% target) and pending order cash reservations.
4. Liquidity & Queue Protections: Caps participation at 10% of 20-session median daily volume.
5. Holding-Period Management: Explicit intended horizon (default 20 sessions) with clear review and exit rules.
6. Scientific Honesty: Clearly labeled confidence and validation status; unvalidated models are never labeled proven buys.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from bvmt.challenge_universe import (
    classify_security_challenge_status,
)
from bvmt.position_sizing import (
    DEFAULT_TARGET_ALLOCATION_RATIO,
    PendingOrderReservation,
    PositionSizeInput,
    compute_position_size,
    quantize_tnd,
)


@dataclass(frozen=True)
class ExitConditions:
    """Pre-defined risk management rules and exit triggers."""

    stop_loss_pct: Decimal = Decimal("-5.000")
    stop_loss_price_tnd: Decimal = Decimal("0.000")
    profit_target_pct: Decimal = Decimal("+12.000")
    profit_target_price_tnd: Decimal = Decimal("0.000")
    trailing_support_rule: str = (
        "Exit if daily closing price closes below 20-session low or breaks lower Bollinger band."
    )
    time_stop_sessions: int = 20
    review_trigger: str = "Weekly review on Friday session or immediate review if price drops > 3.0% in a single session."

    def to_dict(self) -> dict[str, object]:
        return {
            "stop_loss_pct": str(self.stop_loss_pct),
            "stop_loss_price_tnd": str(self.stop_loss_price_tnd),
            "profit_target_pct": str(self.profit_target_pct),
            "profit_target_price_tnd": str(self.profit_target_price_tnd),
            "trailing_support_rule": self.trailing_support_rule,
            "time_stop_sessions": self.time_stop_sessions,
            "review_trigger": self.review_trigger,
        }


@dataclass(frozen=True)
class ManualTradePlan:
    """A comprehensive, actionable manual trade plan for a BVMT security."""

    # 1. Identification & Model Provenance
    plan_id: str
    instrument_id: str
    symbol: str
    stock_name: str
    isin: str | None
    market_segment: str
    model_name: str
    model_version: str
    research_rank: int | None
    research_score: Decimal | None
    composite_score: str | None
    plan_category: str  # RESEARCH_CANDIDATE, PAPER_TRADE_CANDIDATE, MANUAL_ORDER_PLAN

    # 2. Market Data & Pricing
    data_source: str
    data_timestamp: str
    last_verified_price_tnd: Decimal
    current_quote_tnd: Decimal | None
    current_quote_timestamp: str | None
    proposed_limit_price_tnd: Decimal
    quote_age_sessions: int

    # 3. Position Sizing & Cost Accounting
    suggested_max_shares: int
    estimated_gross_order_value_tnd: Decimal
    estimated_purchase_fee_tnd: Decimal
    estimated_total_purchase_cost_tnd: Decimal
    estimated_sale_fee_tnd: Decimal
    break_even_price_tnd: Decimal
    break_even_gain_pct: Decimal

    # 4. Capital & Exposure
    effective_available_cash_tnd: Decimal
    cash_remaining_after_purchase_tnd: Decimal
    existing_position_shares: int
    existing_position_exposure_tnd: Decimal
    proposed_position_weight_pct: Decimal
    binding_constraint: str

    # 5. Holding Horizon & Risk Management
    intended_holding_horizon_sessions: int
    review_date: str
    exit_conditions: ExitConditions
    confidence_status: str  # EXPLORATORY_RESEARCH, PAPER_TRADING_ONLY, INCONCLUSIVE
    validation_status: str  # INSUFFICIENT_MULTI_YEAR_EVIDENCE, HISTORICAL_SAMPLE_ONLY

    # 6. Diagnostics, Warnings & Reasons
    is_actionable: bool
    rejection_reasons: list[str] = field(default_factory=list)
    liquidity_warnings: list[str] = field(default_factory=list)
    execution_warnings: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)

    # 7. Universe & Challenge Governance (Milestone 8)
    in_challenge_universe: bool = True
    challenge_symbol: str | None = None
    order_entry_eligibility: str = "CONFIRMED"
    trading_activity_status: str = "active_quote"
    execution_feasibility_status: str = "CONTINUOUS_LIQUID"
    universe: str = "TUNIS_BOURSE_CHALLENGE"

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "stock_name": self.stock_name,
            "isin": self.isin,
            "market_segment": self.market_segment,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "research_rank": self.research_rank,
            "research_score": str(self.research_score) if self.research_score is not None else None,
            "composite_score": self.composite_score,
            "plan_category": self.plan_category,
            "data_source": self.data_source,
            "data_timestamp": self.data_timestamp,
            "last_verified_price_tnd": str(self.last_verified_price_tnd),
            "current_quote_tnd": str(self.current_quote_tnd)
            if self.current_quote_tnd is not None
            else None,
            "current_quote_timestamp": self.current_quote_timestamp,
            "proposed_limit_price_tnd": str(self.proposed_limit_price_tnd),
            "quote_age_sessions": self.quote_age_sessions,
            "suggested_max_shares": self.suggested_max_shares,
            "estimated_gross_order_value_tnd": str(self.estimated_gross_order_value_tnd),
            "estimated_purchase_fee_tnd": str(self.estimated_purchase_fee_tnd),
            "estimated_total_purchase_cost_tnd": str(self.estimated_total_purchase_cost_tnd),
            "estimated_sale_fee_tnd": str(self.estimated_sale_fee_tnd),
            "break_even_price_tnd": str(self.break_even_price_tnd),
            "break_even_gain_pct": str(self.break_even_gain_pct),
            "effective_available_cash_tnd": str(self.effective_available_cash_tnd),
            "cash_remaining_after_purchase_tnd": str(self.cash_remaining_after_purchase_tnd),
            "existing_position_shares": self.existing_position_shares,
            "existing_position_exposure_tnd": str(self.existing_position_exposure_tnd),
            "proposed_position_weight_pct": str(self.proposed_position_weight_pct),
            "binding_constraint": self.binding_constraint,
            "intended_holding_horizon_sessions": self.intended_holding_horizon_sessions,
            "review_date": self.review_date,
            "exit_conditions": self.exit_conditions.to_dict(),
            "confidence_status": self.confidence_status,
            "validation_status": self.validation_status,
            "is_actionable": self.is_actionable,
            "rejection_reasons": self.rejection_reasons,
            "liquidity_warnings": self.liquidity_warnings,
            "execution_warnings": self.execution_warnings,
            "supporting_evidence": self.supporting_evidence,
            "in_challenge_universe": self.in_challenge_universe,
            "challenge_symbol": self.challenge_symbol,
            "order_entry_eligibility": self.order_entry_eligibility,
            "trading_activity_status": self.trading_activity_status,
            "execution_feasibility_status": self.execution_feasibility_status,
            "universe": self.universe,
        }


def build_manual_trade_plan(
    instrument_id: str,
    symbol: str,
    stock_name: str,
    isin: str | None,
    market_segment: str,
    limit_price_tnd: Decimal,
    portfolio_total_equity_tnd: Decimal,
    available_cash_tnd: Decimal,
    existing_shares: int = 0,
    existing_average_cost_tnd: Decimal = Decimal("0.000"),
    median_daily_turnover_20s_tnd: Decimal = Decimal("0.000"),
    median_daily_volume_20s: int = 0,
    quote_age_sessions: int = 0,
    is_stale_quote: bool = False,
    research_rank: int | None = None,
    composite_score: Decimal | None = None,
    momentum_20s: Decimal | None = None,
    momentum_60s: Decimal | None = None,
    pending_orders: Sequence[PendingOrderReservation] = (),
    target_weight_ratio: Decimal = DEFAULT_TARGET_ALLOCATION_RATIO,
    risk_budget_tnd: Decimal | None = None,
    intended_holding_horizon_sessions: int = 20,
    as_of_session: date | str | None = None,
    universe: str = "TUNIS_BOURSE_CHALLENGE",
    trading_activity_status: str = "active_quote",
) -> ManualTradePlan:
    """Build a complete manual trade plan for a single security with challenge universe safety."""
    as_of = as_of_session or date(2026, 11, 6)
    if isinstance(as_of, str):
        as_of = date.fromisoformat(as_of)
    # Estimate review date (20 trading days is roughly 4 calendar weeks)
    review_dt = as_of + timedelta(days=int(intended_holding_horizon_sessions * 1.4) + 2)

    # 1. Challenge Universe Verification
    chal_info = classify_security_challenge_status(instrument_id, isin=isin, symbol=symbol)
    is_chal_member = bool(chal_info["in_challenge_universe"])
    enforce_challenge_membership = universe == "TUNIS_BOURSE_CHALLENGE"

    # 2. Run deterministic position sizing
    size_input = PositionSizeInput(
        instrument_id=instrument_id,
        symbol=symbol,
        limit_price_tnd=limit_price_tnd,
        portfolio_total_equity_tnd=portfolio_total_equity_tnd,
        raw_available_cash_tnd=available_cash_tnd,
        existing_shares=existing_shares,
        existing_average_cost_tnd=existing_average_cost_tnd,
        median_daily_turnover_20s_tnd=median_daily_turnover_20s_tnd,
        median_daily_volume_20s=median_daily_volume_20s,
        pending_orders=pending_orders,
        target_weight_ratio=target_weight_ratio,
        risk_budget_tnd=risk_budget_tnd,
        is_stale_quote=is_stale_quote,
        quote_age_sessions=quote_age_sessions,
        market_segment=market_segment,
        is_challenge_member=is_chal_member if enforce_challenge_membership else True,
        trading_activity_status=trading_activity_status,
    )
    sizing = compute_position_size(size_input)

    # 3. Exit Conditions Calculation
    stop_loss_pct = Decimal("-5.000")
    stop_price = quantize_tnd(limit_price_tnd * (Decimal("1") + stop_loss_pct / Decimal("100")))
    target_pct = Decimal("+12.000")
    target_price = quantize_tnd(limit_price_tnd * (Decimal("1") + target_pct / Decimal("100")))

    exit_conds = ExitConditions(
        stop_loss_pct=stop_loss_pct,
        stop_loss_price_tnd=stop_price,
        profit_target_pct=target_pct,
        profit_target_price_tnd=target_price,
        time_stop_sessions=intended_holding_horizon_sessions,
        review_trigger="Weekly review on Friday session or immediate review if price drops > 3.0% in a single session.",
    )

    # 4. Categorization & Evidence
    plan_category = "RESEARCH_CANDIDATE"
    if enforce_challenge_membership and not is_chal_member:
        # Non-members can NEVER be manual competition order plans
        plan_category = "RESEARCH_CANDIDATE"
    elif sizing.is_actionable and research_rank is not None and research_rank <= 3:
        plan_category = "MANUAL_ORDER_PLAN"
    elif sizing.is_actionable:
        plan_category = "PAPER_TRADE_CANDIDATE"

    evidence: list[str] = []
    if is_chal_member:
        evidence.append(
            f"Observed member of Tunis Bourse Challenge quotation universe (symbol: {chal_info['challenge_symbol']})."
        )
    else:
        evidence.append(
            "Excluded from competition order plans: not in the 42-instrument challenge quotation list (General BVMT Research only)."
        )

    if research_rank is not None:
        evidence.append(f"Rank #{research_rank} in active quantitative momentum model.")
    if momentum_20s is not None:
        evidence.append(f"20-session momentum: {momentum_20s * 100:+.2f}%.")
    if momentum_60s is not None:
        evidence.append(f"60-session momentum: {momentum_60s * 100:+.2f}%.")
    evidence.append(
        f"Median daily volume (20s): {median_daily_volume_20s} shares ({median_daily_turnover_20s_tnd} TND)."
    )

    exec_warnings = [
        "Orders on tunisbourse-challenge.com execute only 09:00-14:15 Africa/Tunis.",
        "Always place limit orders at or near verified reference prices. Never place market orders in thin order books.",
        "Orders placed on zero-volume days remain PENDING and expire after 1 week.",
    ]

    # Pre-market non-cote awareness
    if trading_activity_status == "non_cote":
        exec_warnings.append(
            "Pre-opening quote indicates 'non coté' (no current matching activity prior to 10:00 opening auction). Execution liquidity unconfirmed."
        )
        exec_feasibility = "AWAITING_OPENING_MATCH"
    elif median_daily_volume_20s >= 50:
        exec_feasibility = "CONTINUOUS_LIQUID"
    else:
        exec_feasibility = "THIN_LIQUIDITY"

    plan_id = f"PLAN-{as_of.isoformat()}-{instrument_id}"

    return ManualTradePlan(
        plan_id=plan_id,
        instrument_id=instrument_id,
        symbol=symbol,
        stock_name=stock_name,
        isin=isin or chal_info["verified_isin"],
        market_segment=market_segment,
        model_name="Model G (Liquidity-Filtered Momentum)",
        model_version="1.2.0-exploratory",
        research_rank=research_rank,
        research_score=composite_score,
        composite_score=f"{composite_score:+.4f}" if composite_score is not None else None,
        plan_category=plan_category,
        data_source="Official BVMT Daily Bars (bvmt_official_2026)",
        data_timestamp=f"{as_of.isoformat()} 16:00:00 Africa/Tunis",
        last_verified_price_tnd=limit_price_tnd,
        current_quote_tnd=None,
        current_quote_timestamp=None,
        proposed_limit_price_tnd=limit_price_tnd,
        quote_age_sessions=quote_age_sessions,
        suggested_max_shares=sizing.suggested_shares,
        estimated_gross_order_value_tnd=sizing.gross_order_value_tnd,
        estimated_purchase_fee_tnd=sizing.purchase_fee_tnd,
        estimated_total_purchase_cost_tnd=sizing.total_purchase_cost_tnd,
        estimated_sale_fee_tnd=sizing.estimated_sale_fee_tnd,
        break_even_price_tnd=sizing.break_even_price_tnd,
        break_even_gain_pct=sizing.break_even_gain_pct,
        effective_available_cash_tnd=sizing.effective_available_cash_tnd,
        cash_remaining_after_purchase_tnd=sizing.cash_remaining_after_purchase_tnd,
        existing_position_shares=sizing.existing_position_shares,
        existing_position_exposure_tnd=sizing.existing_position_value_tnd,
        proposed_position_weight_pct=sizing.proposed_position_weight_pct,
        binding_constraint=sizing.binding_constraint,
        intended_holding_horizon_sessions=intended_holding_horizon_sessions,
        review_date=review_dt.isoformat(),
        exit_conditions=exit_conds,
        confidence_status="EXPLORATORY_RESEARCH",
        validation_status="INSUFFICIENT_MULTI_YEAR_EVIDENCE",
        is_actionable=sizing.is_actionable,
        rejection_reasons=sizing.rejection_reasons,
        liquidity_warnings=sizing.warnings,
        execution_warnings=exec_warnings,
        supporting_evidence=evidence,
        in_challenge_universe=is_chal_member,
        challenge_symbol=chal_info["challenge_symbol"],
        order_entry_eligibility=chal_info["order_entry_eligibility"],
        trading_activity_status=trading_activity_status,
        execution_feasibility_status=exec_feasibility,
        universe=universe,
    )
