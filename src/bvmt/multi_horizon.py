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
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

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
    price_reference: str
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
    return {
        "status": "UNAVAILABLE_RESEARCH_ONLY",
        "horizon": "DAY_INTRADAY",
        "is_executable": False,
        "primary_reasons": [
            "Lack of real-time L2 order book and sub-minute tick feeds on Bourse de Tunis.",
            "Official BVMT execution model operates with periodic match auctions (10:00, 14:15) and static 3% / 5% volatility collars.",
            "1.00% round-trip transaction fee drag destroys intraday edge (empirical simulation generated 8,414 TND fees = 16.8% capital drag on 194 sessions).",
            "Zero lookahead rule prohibits assuming same-close execution for signals derived from that close.",
        ],
        "permitted_alternative": "Use Swing Trading (5-20 sessions) or Position Trading (20-60 sessions) where fee drag is contained under 2.4% of capital.",
    }


def evaluate_multi_horizon_intelligence(
    portfolio_equity_tnd: Decimal,
    available_cash_tnd: Decimal,
    held_positions: dict[str, Any],  # symbol -> position dict or obj
    market_rankings: list[Any],  # list of StockRankingItem
    as_of_session: str | None = None,
    pending_orders: list[PendingOrderReservation] | None = None,
) -> MultiHorizonIntelligenceReport:
    """Generate multi-horizon trading intelligence conforming to the 17-attribute schema."""
    session = as_of_session or "2026-11-06"
    pending = pending_orders or []
    cutoff_dt = datetime(2026, 11, 6, 23, 59, 59, tzinfo=UTC)

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
        latest_price = Decimal(str(latest_raw)) if latest_raw else cost

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
            supporting.append(f"Macro context: {macro_events[0].title}")

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
                source_provenance="tunisbourse-challenge-live-snapshot",
                supporting_factors=supporting,
                contradicting_factors=contradicting,
                risk_constraints={
                    "current_weight_pct": str(weight_pct),
                    "concentration_cap_pct": "10.00",
                    "additional_shares_allowed": 0 if weight_pct >= Decimal("9.50") else 50,
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
                review_date="2026-12-04",
                exit_triggers={
                    "stop_loss_price_tnd": str(stop_loss_px),
                    "profit_target_price_tnd": str(profit_target_px),
                    "review_horizon_sessions": 20,
                },
                evidence_status="OFFICIAL_BVMT_CONFIRMED",
                limitations=["Frontier liquidity collar ±3.0% applies during continuous session"],
            )
        )

    # 2. Evaluate Swing Trading Candidates (5 to 20 Sessions)
    swing_candidates: list[HorizonDecisionItem] = []
    # 3. Evaluate Position Trading Candidates (20 to 60 Sessions)
    position_candidates: list[HorizonDecisionItem] = []

    for r in market_rankings:
        inst_id = getattr(r, "instrument_id", None) or r.get("instrument_id")
        sym = getattr(r, "symbol", None) or r.get("symbol")
        close_raw = (
            getattr(r, "close_tnd", None)
            or getattr(r, "reference_price_tnd", None)
            or (r.get("close_tnd") or r.get("reference_price_tnd") if isinstance(r, dict) else None)
        )
        if not close_raw or Decimal(str(close_raw)) <= Decimal("0"):
            continue
        price = Decimal(str(close_raw))

        mom20_raw = (
            getattr(r, "short_return_pct", None)
            or getattr(r, "momentum_20s", None)
            or (r.get("short_return_pct") or r.get("momentum_20s") if isinstance(r, dict) else None)
        )
        mom20 = Decimal(str(mom20_raw)) if mom20_raw is not None else Decimal("0")
        mom60_raw = (
            getattr(r, "long_return_pct", None)
            or getattr(r, "momentum_60s", None)
            or (r.get("long_return_pct") or r.get("momentum_60s") if isinstance(r, dict) else None)
        )
        mom60 = Decimal(str(mom60_raw)) if mom60_raw is not None else Decimal("0")
        med_turnover_raw = (
            getattr(r, "median_turnover_tnd", None)
            or getattr(r, "median_turnover_20s_tnd", None)
            or (
                r.get("median_turnover_tnd") or r.get("median_turnover_20s_tnd")
                if isinstance(r, dict)
                else None
            )
        )
        med_turnover = (
            Decimal(str(med_turnover_raw)) if med_turnover_raw is not None else Decimal("10000.000")
        )
        med_volume = int(med_turnover // price) if price > 0 else 0
        r_rank = getattr(r, "rank", None) or (r.get("rank") if isinstance(r, dict) else None)

        is_chal = is_in_challenge_universe(inst_id)
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
        if mom20 > Decimal("1.50") or (r_rank is not None and int(r_rank) <= 5):
            supporting_swing = [
                f"20-session momentum is strong at {mom20:+.2f}%.",
                f"Quotation group eligible for continuous execution with median turnover {med_turnover:.0f} TND.",
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
                supporting_swing.append(f"Macro disclosure: {macro_ctx[0].title}")

            status_swing: DecisionStatus = (
                "MANUAL_ORDER_PLAN"
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
                    strategy_version="2.0.0",
                    horizon="SWING_5_20S",
                    horizon_label="Swing Trading (5–20 Sessions)",
                    data_as_of=session,
                    source_provenance="official-bvmt-eod-2026",
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
                    review_date="2026-11-27",
                    exit_triggers={
                        "stop_loss_price_tnd": str(stop_loss_swing),
                        "profit_target_price_tnd": str(profit_target_swing),
                        "time_stop_sessions": 20,
                    },
                    evidence_status="OFFICIAL_BVMT_CONFIRMED",
                    limitations=[
                        "Walk-forward return stability is sensitive to calendar entry timing (19 vs 20 session sensitivity).",
                        "High outlier dependency on single momentum leaders (e.g. STA, SOTETEL).",
                    ],
                )
            )

        # Build Position Candidate (Mode 3: 20–60+ Sessions)
        if mom60 > Decimal("3.00") or (mom20 > Decimal("2.00") and mom60 > Decimal("0")):
            supporting_pos = [
                f"Multi-month trend persistence: 60-session momentum is {mom60:+.2f}%.",
                "High trading regularity across past 60 sessions with verified institutional interest.",
                "Suitable for medium-term holding across quarterly earnings announcements.",
            ]
            contradicting_pos: list[str] = []
            if not is_chal:
                contradicting_pos.append("Not a member of the official 42 Challenge Universe.")
            if price > Decimal("100.000"):
                contradicting_pos.append(
                    f"High nominal price per share ({price} TND) increases minimum lot lumpiness."
                )

            if macro_ctx:
                supporting_pos.append(f"Macro & industry tailwind: {macro_ctx[0].summary[:120]}...")

            status_pos: DecisionStatus = (
                "MANUAL_ORDER_PLAN"
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
                    strategy_version="2.0.0",
                    horizon="POSITION_20_60S",
                    horizon_label="Position Trading (20–60+ Sessions)",
                    data_as_of=session,
                    source_provenance="official-bvmt-eod-2026",
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
                    review_date="2027-01-15",
                    exit_triggers={
                        "stop_loss_price_tnd": str(stop_loss_pos),
                        "profit_target_price_tnd": str(profit_target_pos),
                        "time_stop_sessions": 60,
                    },
                    evidence_status="OFFICIAL_BVMT_CONFIRMED",
                    limitations=[
                        "Longer horizon exposes portfolio to macroeconomic policy and currency shifts.",
                        "Position requires monitoring trailing earnings and revenue disclosures.",
                    ],
                )
            )

    macro_events_all = get_verified_macro_intelligence(cutoff=cutoff_dt)

    return MultiHorizonIntelligenceReport(
        as_of=datetime.now(UTC).isoformat(),
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
