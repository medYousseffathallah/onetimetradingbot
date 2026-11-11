"""Multi-horizon quantitative trading intelligence and explainable reasoning (Milestone 9).

Separates investment and trading decisions across three distinct operational horizons:
1. Mode 1: Day Trading (Intraday)
   - Status: UNAVAILABLE_RESEARCH_ONLY.
   - Grounded in BVMT reality: EOD-settled frontier market with daily match auctions,
     lacking real-time L2 order book or sub-minute tick feeds. 1.00% round-trip fee
     erodes alpha. Strictly generates ZERO executable orders.
2. Mode 2: Swing Trading (5 to 20 Trading Sessions — ~1 to 4 Weeks)
   - Factors: 20-session momentum, relative strength, 20-session volatility, median turnover.
   - Sizing: 8.5% target buffer, 10% volume participation cap.
   - Exits: -5.0% Stop Loss, +12.0% Profit Target, 20-session Time Stop.
3. Mode 3: Position Trading (20 to 60+ Trading Sessions — ~1 to 3 Months)
   - Factors: 60-session momentum persistence, dividend history, earnings indicators, low drawdown.
   - Exits: -8.0% Trend Breakdown Stop, +20.0% Fundamental Target, 60-session Time Stop.

Every decision conforms strictly to the 17-attribute explainable decision schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from bvmt.challenge_universe import (
    is_in_challenge_universe,
)
from bvmt.macro_events import get_instrument_macro_context, get_verified_macro_intelligence
from bvmt.position_sizing import (
    DEFAULT_PURCHASE_FEE_RATE,
    DEFAULT_SALE_FEE_RATE,
    PendingOrderReservation,
    PositionSizeInput,
    compute_position_size,
    quantize_tnd,
)

DecisionStatus = Literal[
    "MANUAL_ORDER_PLAN",
    "MONITOR_POSITION",
    "REVIEW_POSITION",
    "RESEARCH_CANDIDATE",
    "STRATEGY_EXCLUDED",
    "INSUFFICIENT_EVIDENCE",
    "UNAVAILABLE_RESEARCH_ONLY",
]

HorizonType = Literal["SWING_5_20S", "POSITION_20_60S", "DAY_INTRADAY"]
EvidenceStatus = Literal["OFFICIAL_BVMT_CONFIRMED", "PROVISIONAL", "UNVERIFIED"]


@dataclass(frozen=True)
class HorizonDecisionItem:
    """Standardized 17-attribute decision object for human-centered decision support."""

    decision_status: DecisionStatus
    symbol: str
    instrument_id: str
    strategy_id: str
    strategy_version: str
    horizon: HorizonType
    horizon_label: str
    data_as_of: str
    source_provenance: str
    supporting_factors: list[str]
    contradicting_factors: list[str]
    risk_constraints: dict[str, Any]
    price_reference: str | None
    quantity_limit: int
    fee_estimate: dict[str, str]
    review_date: str
    exit_triggers: dict[str, Any]
    evidence_status: EvidenceStatus
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MultiHorizonIntelligenceReport:
    """Complete multi-horizon decision report."""

    as_of: str
    session_date: str
    portfolio_equity_tnd: str
    available_cash_tnd: str
    day_trading_notice: dict[str, Any]
    swing_candidates: list[HorizonDecisionItem]
    position_candidates: list[HorizonDecisionItem]
    active_position_reviews: list[HorizonDecisionItem]
    macro_events_count: int = 0
    macro_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "session_date": self.session_date,
            "portfolio_equity_tnd": self.portfolio_equity_tnd,
            "available_cash_tnd": self.available_cash_tnd,
            "day_trading_notice": self.day_trading_notice,
            "swing_candidates": [c.to_dict() for c in self.swing_candidates],
            "position_candidates": [c.to_dict() for c in self.position_candidates],
            "active_position_reviews": [r.to_dict() for r in self.active_position_reviews],
            "macro_events_count": self.macro_events_count,
            "macro_events": self.macro_events,
        }


def build_day_trading_notice() -> dict[str, Any]:
    """Explicitly documents why day trading is UNAVAILABLE for actionable order execution."""
    reasons = [
        "Lack of real-time L2 order book and sub-minute tick feeds on Bourse de Tunis.",
        "Exchange execution and competition matching rules require official evidence review; no intraday execution feed is available.",
        "1.00% round-trip transaction fee drag destroys intraday edge (empirical simulation generated 8,414 TND fees = 16.8% capital drag on 194 sessions).",
        "Zero lookahead rule prohibits assuming same-close execution for signals derived from that close.",
    ]
    return {
        "status": "UNAVAILABLE_RESEARCH_ONLY",
        "horizon": "DAY_INTRADAY",
        "is_executable": False,
        "headline": "Intraday Day Trading Is Structurally Unfeasible on BVMT",
        "disclaimer": "Discrete fixing auctions, static circuit breaker collars, and round-trip fee friction eliminate intraday scalping viability.",
        "reasons": reasons,
        "primary_reasons": reasons,
        "fee_drag_pct": "16.8% of capital",
        "intraday_volatility_cap": "±3.0% to ±5.0%",
        "permitted_alternative": "Use Swing Trading (5-20 sessions) or Position Trading (20-60 sessions) where fee drag is contained under 2.4% of capital.",
    }


def _value(record: Any, key: str) -> Any:
    """Read named evidence without treating a legitimate zero as missing."""
    return record.get(key) if isinstance(record, dict) else getattr(record, key, None)


def _first_known(record: Any, *keys: str) -> Any:
    for key in keys:
        value = _value(record, key)
        if value is not None:
            return value
    return None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    result = Decimal(str(value))
    return result if result.is_finite() else None


def _return_percent(record: Any, pct_key: str, ratio_key: str) -> Decimal | None:
    percent = _decimal(_value(record, pct_key))
    if percent is not None:
        return percent
    ratio = _decimal(_value(record, ratio_key))
    return ratio * Decimal("100") if ratio is not None else None


def evaluate_multi_horizon_intelligence(
    portfolio_equity_tnd: Decimal,
    available_cash_tnd: Decimal,
    held_positions: dict[str, Any],  # symbol -> position dict or obj
    market_rankings: list[Any],  # list of StockRankingItem
    as_of_session: str | None = None,
    pending_orders: list[PendingOrderReservation] | None = None,
    decision_timestamp: datetime | None = None,
) -> MultiHorizonIntelligenceReport:
    """Generate multi-horizon trading intelligence conforming to the 17-attribute schema."""
    if decision_timestamp is None:
        if as_of_session is None:
            raise ValueError("An explicit decision_timestamp or as_of_session is required")
        # Legacy date-only callers get a conservative start-of-day boundary. This
        # is a declared availability convention, never an invented market close.
        decision_timestamp = datetime.combine(
            date.fromisoformat(as_of_session), time.min, tzinfo=ZoneInfo("Africa/Tunis")
        )
    if decision_timestamp.tzinfo is None or decision_timestamp.utcoffset() is None:
        raise ValueError("decision_timestamp must be timezone-aware")
    session = decision_timestamp.astimezone(ZoneInfo("Africa/Tunis")).date().isoformat()
    if as_of_session is not None and session != as_of_session:
        raise ValueError("decision_timestamp and as_of_session disagree on session")
    pending = pending_orders or []
    cutoff_dt = decision_timestamp

    # 1. Review Existing Portfolio Positions (e.g. DELICE HOLDING, BH BANK)
    active_position_reviews: list[HorizonDecisionItem] = []
    for sym, pos in held_positions.items():
        if hasattr(pos, "total_shares"):
            qty = pos.total_shares
        elif hasattr(pos, "quantity"):
            qty = pos.quantity
        elif isinstance(pos, dict):
            qty = pos.get("total_shares", pos.get("quantity", 0))
        else:
            qty = 0

        if hasattr(pos, "average_cost_tnd"):
            cost_raw = pos.average_cost_tnd
        elif hasattr(pos, "acquisition_price_tnd"):
            cost_raw = pos.acquisition_price_tnd
        elif isinstance(pos, dict):
            cost_raw = pos.get("average_cost_tnd", pos.get("acquisition_price_tnd", "0"))
        else:
            cost_raw = "0"
        cost = Decimal(str(cost_raw))

        latest_raw = (
            getattr(pos, "latest_price_tnd", None)
            if hasattr(pos, "latest_price_tnd")
            else (pos.get("latest_price_tnd") if isinstance(pos, dict) else None)
        )
        latest_price = _decimal(latest_raw)
        if latest_price is None or latest_price <= 0 or cost <= 0:
            active_position_reviews.append(
                HorizonDecisionItem(
                    decision_status="INSUFFICIENT_EVIDENCE",
                    symbol=sym,
                    instrument_id=sym,
                    strategy_id="POSITION_PORTFOLIO_REVIEW",
                    strategy_version="2.1.0_pit",
                    horizon="POSITION_20_60S",
                    horizon_label="Position Holding (Held Asset)",
                    data_as_of=session,
                    source_provenance="unverified-position-input",
                    supporting_factors=[f"Recorded holding in {sym}: {qty} shares."],
                    contradicting_factors=[
                        "Observed quote or acquisition-cost evidence unavailable."
                    ],
                    risk_constraints={"current_weight_pct": None, "additional_shares_allowed": 0},
                    price_reference=str(latest_price)
                    if latest_price is not None and latest_price > 0
                    else None,
                    quantity_limit=0,
                    fee_estimate={},
                    review_date=session,
                    exit_triggers={},
                    evidence_status="UNVERIFIED",
                    limitations=[
                        "Missing quote cannot be replaced with acquisition cost; exposure and P&L are unknown."
                    ],
                )
            )
            continue

        gain_pct = ((latest_price - cost) / cost * Decimal("100")) if cost > 0 else Decimal("0")
        current_exp = quantize_tnd(Decimal(qty) * latest_price)
        weight_pct = quantize_tnd(
            (current_exp / portfolio_equity_tnd * Decimal("100"))
            if portfolio_equity_tnd > 0
            else Decimal("0")
        )

        supporting = [
            f"Currently held position in {sym}: {qty} shares @ {quantize_tnd(cost)} TND cost.",
            f"Position value: {current_exp} TND ({weight_pct}% of total equity).",
            f"Unrealized return: {gain_pct:+.2f}% vs acquisition cost.",
        ]
        contradicting: list[str] = []
        if weight_pct >= Decimal("9.50"):
            contradicting.append(
                f"Position weight ({weight_pct}%) is near the 10.0% single-stock concentration cap. No additional sizing permitted."
            )
        if gain_pct <= Decimal("-3.50"):
            contradicting.append(
                f"Unrealized loss ({gain_pct:.2f}%) is approaching the -5.0% risk stop-loss threshold."
            )

        macro_events = get_instrument_macro_context(sym, cutoff=cutoff_dt)
        if macro_events:
            supporting.append(f"Unverified catalog context: {macro_events[0].title}")

        decision_status: DecisionStatus = (
            "REVIEW_POSITION"
            if (
                gain_pct <= Decimal("-4.50")
                or gain_pct >= Decimal("10.00")
                or weight_pct > Decimal("10.00")
            )
            else "MONITOR_POSITION"
        )

        stop_loss_px = quantize_tnd(cost * Decimal("0.950"))
        profit_target_px = quantize_tnd(cost * Decimal("1.120"))
        break_even_px = quantize_tnd(
            cost
            * (Decimal("1.000") + DEFAULT_PURCHASE_FEE_RATE)
            / (Decimal("1.000") - DEFAULT_SALE_FEE_RATE)
        )

        active_position_reviews.append(
            HorizonDecisionItem(
                decision_status=decision_status,
                symbol=sym,
                instrument_id=sym,
                strategy_id="POSITION_PORTFOLIO_REVIEW",
                strategy_version="2.0.0",
                horizon="POSITION_20_60S",
                horizon_label="Position Holding (Held Asset)",
                data_as_of=session,
                source_provenance="caller-supplied-position-evidence",
                supporting_factors=supporting,
                contradicting_factors=contradicting,
                risk_constraints={
                    "current_weight_pct": str(weight_pct),
                    "concentration_cap_pct": "10.00",
                    "additional_shares_allowed": 0,
                },
                price_reference=str(latest_price),
                quantity_limit=qty,
                fee_estimate={
                    "purchase_fee_paid_tnd": str(
                        quantize_tnd(Decimal(qty) * cost * DEFAULT_PURCHASE_FEE_RATE)
                    ),
                    "estimated_exit_fee_tnd": str(
                        quantize_tnd(current_exp * DEFAULT_SALE_FEE_RATE)
                    ),
                    "break_even_price_tnd": str(break_even_px),
                },
                review_date=session,
                exit_triggers={
                    "stop_loss_price_tnd": str(stop_loss_px),
                    "profit_target_price_tnd": str(profit_target_px),
                    "review_horizon_sessions": 20,
                },
                evidence_status="UNVERIFIED",
                limitations=["Frontier liquidity collar ±3.0% applies during continuous session"],
            )
        )

    # 2. Evaluate Swing Trading Candidates (5 to 20 Sessions)
    swing_candidates: list[HorizonDecisionItem] = []
    # 3. Evaluate Position Trading Candidates (20 to 60 Sessions)
    position_candidates: list[HorizonDecisionItem] = []

    for r in market_rankings:
        inst_id = _value(r, "instrument_id")
        sym = _value(r, "symbol")
        if not inst_id or not sym:
            continue
        close_raw = _first_known(r, "close_tnd", "reference_price_tnd")
        if not close_raw or Decimal(str(close_raw)) <= Decimal("0"):
            continue
        price = Decimal(str(close_raw))

        mom20 = _return_percent(r, "short_return_pct", "momentum_20s")
        mom60 = _return_percent(r, "long_return_pct", "momentum_60s")
        med_turnover = _decimal(_first_known(r, "median_turnover_tnd", "median_turnover_20s_tnd"))
        # Turnover divided by the observed reference is only a volume proxy.
        # Missing liquidity yields no capacity, never a fabricated turnover.
        med_volume = (
            int(med_turnover // price) if med_turnover is not None and med_turnover > 0 else 0
        )

        is_chal = is_in_challenge_universe(inst_id, symbol=sym)
        existing_pos = held_positions.get(sym) or held_positions.get(inst_id)
        if existing_pos:
            if hasattr(existing_pos, "total_shares"):
                existing_sh = existing_pos.total_shares
            elif hasattr(existing_pos, "quantity"):
                existing_sh = existing_pos.quantity
            elif isinstance(existing_pos, dict):
                existing_sh = existing_pos.get("total_shares", existing_pos.get("quantity", 0))
            else:
                existing_sh = 0

            if hasattr(existing_pos, "average_cost_tnd"):
                existing_cost = Decimal(str(existing_pos.average_cost_tnd))
            elif hasattr(existing_pos, "acquisition_price_tnd"):
                existing_cost = Decimal(str(existing_pos.acquisition_price_tnd))
            elif isinstance(existing_pos, dict):
                existing_cost = Decimal(
                    str(
                        existing_pos.get(
                            "average_cost_tnd", existing_pos.get("acquisition_price_tnd", 0)
                        )
                    )
                )
            else:
                existing_cost = Decimal("0")
        else:
            existing_sh = 0
            existing_cost = Decimal("0")

        # Position Sizing
        sizing_input = PositionSizeInput(
            instrument_id=inst_id,
            symbol=sym,
            limit_price_tnd=price,
            portfolio_total_equity_tnd=portfolio_equity_tnd,
            raw_available_cash_tnd=available_cash_tnd,
            existing_shares=existing_sh,
            existing_average_cost_tnd=existing_cost,
            median_daily_volume_20s=med_volume,
            pending_orders=pending,
            is_challenge_member=is_chal,
        )
        sizing_res = compute_position_size(sizing_input)

        # Macro Context
        macro_ctx = get_instrument_macro_context(inst_id, cutoff=cutoff_dt)

        # Build Swing Candidate (Mode 2)
        if mom20 is not None and mom20 > Decimal("1.50"):
            supporting_swing = [
                f"20-session momentum is strong at {mom20:+.2f}%.",
                (
                    f"Observed median turnover {med_turnover:.0f} TND."
                    if med_turnover is not None
                    else "Median turnover unavailable; liquidity capacity is unknown."
                ),
                f"Sized quantity: {sizing_res.suggested_shares} shares respects cash and 10% concentration cap.",
            ]
            contradicting_swing: list[str] = []
            if not is_chal:
                contradicting_swing.append(
                    "Excluded from 42 Tunis Bourse Challenge securities. Cannot be entered as a manual order."
                )
            if sizing_res.binding_constraint == "volume_participation_cap":
                contradicting_swing.append(
                    f"Position size constrained by 10% daily volume participation ({med_volume} shares daily median)."
                )
            if existing_sh > 0:
                contradicting_swing.append(
                    f"Already own {existing_sh} shares. Incremental capacity limited by 10% portfolio cap."
                )

            if macro_ctx:
                supporting_swing.append(f"Unverified catalog context: {macro_ctx[0].title}")

            status_swing: DecisionStatus = (
                "INSUFFICIENT_EVIDENCE"
                if med_turnover is None
                else "MANUAL_ORDER_PLAN"
                if (is_chal and sizing_res.is_actionable and sizing_res.suggested_shares > 0)
                else ("RESEARCH_CANDIDATE" if is_chal else "STRATEGY_EXCLUDED")
            )

            stop_loss_swing = quantize_tnd(price * Decimal("0.950"))
            profit_target_swing = quantize_tnd(price * Decimal("1.120"))
            break_even_swing = quantize_tnd(
                price
                * (Decimal("1.000") + DEFAULT_PURCHASE_FEE_RATE)
                / (Decimal("1.000") - DEFAULT_SALE_FEE_RATE)
            )

            swing_candidates.append(
                HorizonDecisionItem(
                    decision_status=status_swing,
                    symbol=sym,
                    instrument_id=inst_id,
                    strategy_id="SWING_MOMENTUM_20S",
                    strategy_version="2.1.0_pit",
                    horizon="SWING_5_20S",
                    horizon_label="Swing Trading (5–20 Sessions)",
                    data_as_of=session,
                    source_provenance="caller-supplied-ranking-evidence",
                    supporting_factors=supporting_swing,
                    contradicting_factors=contradicting_swing,
                    risk_constraints={
                        "suggested_shares": sizing_res.suggested_shares,
                        "binding_constraint": sizing_res.binding_constraint,
                        "concentration_cap_pct": "10.00",
                        "max_volume_participation_pct": "10.00",
                    },
                    price_reference=str(price),
                    quantity_limit=sizing_res.suggested_shares,
                    fee_estimate={
                        "estimated_purchase_fee_tnd": str(sizing_res.purchase_fee_tnd),
                        "estimated_sale_fee_tnd": str(sizing_res.estimated_sale_fee_tnd),
                        "break_even_price_tnd": str(break_even_swing),
                    },
                    review_date=session,
                    exit_triggers={
                        "stop_loss_price_tnd": str(stop_loss_swing),
                        "profit_target_price_tnd": str(profit_target_swing),
                        "time_stop_sessions": 20,
                    },
                    evidence_status="UNVERIFIED",
                    limitations=[
                        "Liquidity capacity uses observed turnover/reference-price proxy, not order-book depth; missing liquidity blocks sizing.",
                        "Macro catalog entries require source-document verification; cutoff filtering alone does not verify the claims.",
                        "Walk-forward return stability is sensitive to calendar entry timing (19 vs 20 session sensitivity).",
                        "High outlier dependency on single momentum leaders (e.g. STA, SOTETEL).",
                    ],
                )
            )

        # Build Position Candidate (Mode 3: 20–60+ Sessions)
        if mom60 is not None and (
            mom60 > Decimal("3.00")
            or (mom20 is not None and mom20 > Decimal("2.00") and mom60 > Decimal("0"))
        ):
            supporting_pos = [
                f"Multi-month trend persistence: 60-session momentum is {mom60:+.2f}%.",
                "Research scenario only; institutional participation and financial quality are unverified.",
            ]
            contradicting_pos: list[str] = []
            if not is_chal:
                contradicting_pos.append("Not a member of the official 42 Challenge Universe.")
            if price > Decimal("100.000"):
                contradicting_pos.append(
                    f"High nominal price per share ({price} TND) increases minimum lot lumpiness."
                )

            if macro_ctx:
                supporting_pos.append(
                    f"Unverified catalog context: {macro_ctx[0].summary[:120]}..."
                )

            status_pos: DecisionStatus = (
                "INSUFFICIENT_EVIDENCE"
                if med_turnover is None
                else "MANUAL_ORDER_PLAN"
                if (is_chal and sizing_res.is_actionable and sizing_res.suggested_shares > 0)
                else ("RESEARCH_CANDIDATE" if is_chal else "STRATEGY_EXCLUDED")
            )

            stop_loss_pos = quantize_tnd(
                price * Decimal("0.920")
            )  # -8% wider stop for position trading
            profit_target_pos = quantize_tnd(price * Decimal("1.200"))  # +20% fundamental target
            break_even_pos = quantize_tnd(
                price
                * (Decimal("1.000") + DEFAULT_PURCHASE_FEE_RATE)
                / (Decimal("1.000") - DEFAULT_SALE_FEE_RATE)
            )

            position_candidates.append(
                HorizonDecisionItem(
                    decision_status=status_pos,
                    symbol=sym,
                    instrument_id=inst_id,
                    strategy_id="POSITION_TREND_60S",
                    strategy_version="2.1.0_pit",
                    horizon="POSITION_20_60S",
                    horizon_label="Position Trading (20–60+ Sessions)",
                    data_as_of=session,
                    source_provenance="caller-supplied-ranking-evidence",
                    supporting_factors=supporting_pos,
                    contradicting_factors=contradicting_pos,
                    risk_constraints={
                        "suggested_shares": sizing_res.suggested_shares,
                        "binding_constraint": sizing_res.binding_constraint,
                        "concentration_cap_pct": "10.00",
                    },
                    price_reference=str(price),
                    quantity_limit=sizing_res.suggested_shares,
                    fee_estimate={
                        "estimated_purchase_fee_tnd": str(sizing_res.purchase_fee_tnd),
                        "estimated_sale_fee_tnd": str(sizing_res.estimated_sale_fee_tnd),
                        "break_even_price_tnd": str(break_even_pos),
                    },
                    review_date=session,
                    exit_triggers={
                        "stop_loss_price_tnd": str(stop_loss_pos),
                        "profit_target_price_tnd": str(profit_target_pos),
                        "time_stop_sessions": 60,
                    },
                    evidence_status="UNVERIFIED",
                    limitations=[
                        "Liquidity capacity uses observed turnover/reference-price proxy; missing liquidity blocks sizing.",
                        "Macro catalog entries require source-document verification.",
                        "Longer horizon exposes portfolio to macroeconomic policy and currency shifts.",
                        "Position requires monitoring trailing earnings and revenue disclosures.",
                    ],
                )
            )

    macro_events_all = get_verified_macro_intelligence(cutoff=cutoff_dt)

    return MultiHorizonIntelligenceReport(
        as_of=cutoff_dt.isoformat(),
        session_date=session,
        portfolio_equity_tnd=str(quantize_tnd(portfolio_equity_tnd)),
        available_cash_tnd=str(quantize_tnd(available_cash_tnd)),
        day_trading_notice=build_day_trading_notice(),
        swing_candidates=swing_candidates[:10],
        position_candidates=position_candidates[:10],
        active_position_reviews=active_position_reviews,
        macro_events_count=len(macro_events_all),
        macro_events=[ev.to_dict() for ev in macro_events_all],
    )
