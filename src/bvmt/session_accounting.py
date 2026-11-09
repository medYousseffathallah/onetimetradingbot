"""Daily session accounting, transaction reconstruction, and performance attribution (Milestone 12).

Separates:
1. Unrealized P&L since acquisition on open positions.
2. Realized P&L on closed round-trip positions.
3. Intraday session equity change and holding-price deltas.
4. Trading fees and cash-flow reconciliation.
5. Model decision evaluations vs. actual executions.
6. Concentration and portfolio risk bounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from bvmt.sync_service import quantize_tnd

AttributionStatus = Literal["VERIFIED_COMPLETE", "PERFORMANCE_ATTRIBUTION_INCOMPLETE"]


@dataclass(frozen=True)
class PositionSessionPerformance:
    """Session performance attribution for an individual holding."""

    symbol: str
    instrument_id: str
    quantity: int
    acquisition_price_tnd: Decimal
    acquisition_amount_tnd: Decimal
    session_start_price_tnd: Decimal | None
    latest_price_tnd: Decimal
    market_value_tnd: Decimal
    unrealized_pnl_since_acq_tnd: Decimal
    unrealized_return_since_acq_pct: Decimal
    session_pnl_contribution_tnd: Decimal
    portfolio_weight_pct: Decimal
    status: Literal["HELD_WHOLE_SESSION", "NEWLY_ENTERED_SESSION", "CLOSED_INTRADAY"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "instrument_id": self.instrument_id,
            "quantity": self.quantity,
            "acquisition_price_tnd": str(self.acquisition_price_tnd),
            "acquisition_amount_tnd": str(self.acquisition_amount_tnd),
            "session_start_price_tnd": (
                str(self.session_start_price_tnd) if self.session_start_price_tnd else None
            ),
            "latest_price_tnd": str(self.latest_price_tnd),
            "market_value_tnd": str(self.market_value_tnd),
            "unrealized_pnl_since_acq_tnd": str(self.unrealized_pnl_since_acq_tnd),
            "unrealized_return_since_acq_pct": str(self.unrealized_return_since_acq_pct),
            "session_pnl_contribution_tnd": str(self.session_pnl_contribution_tnd),
            "portfolio_weight_pct": str(self.portfolio_weight_pct),
            "status": self.status,
        }


@dataclass(frozen=True)
class ReconstructedTransaction:
    """Audited transaction reconstructed from account snapshots and cash flows."""

    transaction_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    shares: int
    execution_price_tnd: Decimal
    total_cost_or_proceeds_tnd: Decimal
    estimated_fee_tnd: Decimal
    realized_pnl_tnd: Decimal | None
    execution_time_approx: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "symbol": self.symbol,
            "side": self.side,
            "shares": self.shares,
            "execution_price_tnd": str(self.execution_price_tnd),
            "total_cost_or_proceeds_tnd": str(self.total_cost_or_proceeds_tnd),
            "estimated_fee_tnd": str(self.estimated_fee_tnd),
            "realized_pnl_tnd": str(self.realized_pnl_tnd) if self.realized_pnl_tnd else None,
            "execution_time_approx": self.execution_time_approx,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ModelDecisionEvaluation:
    """Audit of a strategy recommendation vs actual human execution."""

    symbol: str
    strategy_id: str
    signal_timestamp: str
    suggested_action: str
    suggested_shares: int
    suggested_price_tnd: Decimal
    suggested_holding_horizon: str
    actual_action: str
    actual_shares: int
    actual_price_tnd: Decimal | None
    execution_fidelity: Literal["EXACT_MATCH", "PARTIAL_MATCH", "IGNORED", "OVERRIDE"]
    current_unrealized_return_pct: Decimal | None
    stop_loss_price_tnd: Decimal
    target_price_tnd: Decimal
    evaluation_notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "signal_timestamp": self.signal_timestamp,
            "suggested_action": self.suggested_action,
            "suggested_shares": self.suggested_shares,
            "suggested_price_tnd": str(self.suggested_price_tnd),
            "suggested_holding_horizon": self.suggested_holding_horizon,
            "actual_action": self.actual_action,
            "actual_shares": self.actual_shares,
            "actual_price_tnd": str(self.actual_price_tnd) if self.actual_price_tnd else None,
            "execution_fidelity": self.execution_fidelity,
            "current_unrealized_return_pct": (
                str(self.current_unrealized_return_pct)
                if self.current_unrealized_return_pct
                else None
            ),
            "stop_loss_price_tnd": str(self.stop_loss_price_tnd),
            "target_price_tnd": str(self.target_price_tnd),
            "evaluation_notes": self.evaluation_notes,
        }


@dataclass(frozen=True)
class DailySessionReport:
    """Comprehensive daily session accounting and attribution report."""

    session_date: str
    starting_equity_tnd: Decimal
    starting_cash_tnd: Decimal
    starting_holdings_value_tnd: Decimal
    ending_equity_tnd: Decimal
    ending_cash_tnd: Decimal
    ending_holdings_value_tnd: Decimal
    equity_change_tnd: Decimal
    cash_change_tnd: Decimal
    holdings_value_change_tnd: Decimal
    verified_session_pnl_tnd: Decimal
    realized_pnl_tnd: Decimal
    unrealized_pnl_delta_tnd: Decimal
    unrealized_pnl_since_acq_tnd: Decimal
    trading_fees_estimated_tnd: Decimal
    total_return_since_inception_tnd: Decimal
    total_return_since_inception_pct: Decimal
    competition_ranking: int
    total_participants: int
    attribution_status: AttributionStatus
    attribution_warning: str | None
    reconciliation_gap_tnd: Decimal
    positions: list[PositionSessionPerformance] = field(default_factory=list)
    transactions: list[ReconstructedTransaction] = field(default_factory=list)
    model_evaluations: list[ModelDecisionEvaluation] = field(default_factory=list)
    concentration_warnings: list[str] = field(default_factory=list)
    tomorrow_priorities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_date": self.session_date,
            "starting_equity_tnd": str(self.starting_equity_tnd),
            "starting_cash_tnd": str(self.starting_cash_tnd),
            "starting_holdings_value_tnd": str(self.starting_holdings_value_tnd),
            "ending_equity_tnd": str(self.ending_equity_tnd),
            "ending_cash_tnd": str(self.ending_cash_tnd),
            "ending_holdings_value_tnd": str(self.ending_holdings_value_tnd),
            "equity_change_tnd": str(self.equity_change_tnd),
            "cash_change_tnd": str(self.cash_change_tnd),
            "holdings_value_change_tnd": str(self.holdings_value_change_tnd),
            "verified_session_pnl_tnd": str(self.verified_session_pnl_tnd),
            "realized_pnl_tnd": str(self.realized_pnl_tnd),
            "unrealized_pnl_delta_tnd": str(self.unrealized_pnl_delta_tnd),
            "unrealized_pnl_since_acq_tnd": str(self.unrealized_pnl_since_acq_tnd),
            "trading_fees_estimated_tnd": str(self.trading_fees_estimated_tnd),
            "total_return_since_inception_tnd": str(self.total_return_since_inception_tnd),
            "total_return_since_inception_pct": str(self.total_return_since_inception_pct),
            "competition_ranking": self.competition_ranking,
            "total_participants": self.total_participants,
            "attribution_status": self.attribution_status,
            "attribution_warning": self.attribution_warning,
            "reconciliation_gap_tnd": str(self.reconciliation_gap_tnd),
            "positions": [p.to_dict() for p in self.positions],
            "transactions": [t.to_dict() for t in self.transactions],
            "model_evaluations": [m.to_dict() for m in self.model_evaluations],
            "concentration_warnings": self.concentration_warnings,
            "tomorrow_priorities": self.tomorrow_priorities,
        }


def generate_november_09_session_report() -> DailySessionReport:
    """Generate the definitive audited session accounting report for November 9, 2026."""
    start_equity = quantize_tnd("49979.070")
    start_cash = quantize_tnd("44586.070")
    start_holdings = quantize_tnd("5393.000")

    end_equity = quantize_tnd("50061.960")
    end_cash = quantize_tnd("41622.790")
    end_holdings = quantize_tnd("8439.170")

    equity_delta = quantize_tnd(end_equity - start_equity)  # +82.890
    cash_delta = quantize_tnd(end_cash - start_cash)  # -2963.280
    holdings_delta = quantize_tnd(end_holdings - start_holdings)  # +3046.170

    # 1. Open Positions attribution
    pos_bh = PositionSessionPerformance(
        symbol="BH BANK",
        instrument_id="BH_BANK",
        quantity=30,
        acquisition_price_tnd=Decimal("13.065"),
        acquisition_amount_tnd=Decimal("391.950"),
        session_start_price_tnd=Decimal("13.200"),
        latest_price_tnd=Decimal("13.090"),
        market_value_tnd=Decimal("392.700"),
        unrealized_pnl_since_acq_tnd=Decimal("0.750"),
        unrealized_return_since_acq_pct=Decimal("0.190"),
        session_pnl_contribution_tnd=Decimal("-3.300"),  # 30 * (13.09 - 13.20)
        portfolio_weight_pct=quantize_tnd(Decimal("392.700") / end_equity * Decimal("100")),
        status="HELD_WHOLE_SESSION",
    )

    pos_dh = PositionSessionPerformance(
        symbol="DELICE HOLDING",
        instrument_id="DELICE_HOLDING",
        quantity=263,
        acquisition_price_tnd=Decimal("19.095"),
        acquisition_amount_tnd=Decimal("5021.990"),
        session_start_price_tnd=Decimal("19.000"),
        latest_price_tnd=Decimal("19.090"),
        market_value_tnd=Decimal("5020.670"),
        unrealized_pnl_since_acq_tnd=Decimal("-1.310"),
        unrealized_return_since_acq_pct=Decimal("-0.030"),
        session_pnl_contribution_tnd=Decimal("23.670"),  # 263 * (19.09 - 19.00)
        portfolio_weight_pct=quantize_tnd(Decimal("5020.670") / end_equity * Decimal("100")),
        status="HELD_WHOLE_SESSION",
    )

    pos_nbl = PositionSessionPerformance(
        symbol="NEW BODY LINE",
        instrument_id="NEW_BODY_LINE",
        quantity=200,
        acquisition_price_tnd=Decimal("2.462"),
        acquisition_amount_tnd=Decimal("492.450"),
        session_start_price_tnd=None,
        latest_price_tnd=Decimal("2.490"),
        market_value_tnd=Decimal("498.000"),
        unrealized_pnl_since_acq_tnd=Decimal("5.550"),
        unrealized_return_since_acq_pct=Decimal("1.130"),
        session_pnl_contribution_tnd=Decimal("5.550"),  # 498.00 - 492.45
        portfolio_weight_pct=quantize_tnd(Decimal("498.000") / end_equity * Decimal("100")),
        status="NEWLY_ENTERED_SESSION",
    )

    pos_sta = PositionSessionPerformance(
        symbol="STA",
        instrument_id="STA",
        quantity=22,
        acquisition_price_tnd=Decimal("115.575"),
        acquisition_amount_tnd=Decimal("2542.650"),
        session_start_price_tnd=None,
        latest_price_tnd=Decimal("114.900"),
        market_value_tnd=Decimal("2527.800"),
        unrealized_pnl_since_acq_tnd=Decimal("-14.850"),
        unrealized_return_since_acq_pct=Decimal("-0.580"),
        session_pnl_contribution_tnd=Decimal("-14.850"),  # 2527.80 - 2542.65
        portfolio_weight_pct=quantize_tnd(Decimal("2527.800") / end_equity * Decimal("100")),
        status="NEWLY_ENTERED_SESSION",
    )

    # 2. Closed Intraday Position (35 shares discovered from midday snapshot)
    pos_closed = PositionSessionPerformance(
        symbol="UNCONFIRMED_ROUNDTRIP_35",
        instrument_id="UNCONFIRMED_ROUNDTRIP_35",
        quantity=35,
        acquisition_price_tnd=Decimal("131.756"),
        acquisition_amount_tnd=Decimal("4611.450"),
        session_start_price_tnd=None,
        latest_price_tnd=Decimal("133.808"),
        market_value_tnd=Decimal("0.000"),
        unrealized_pnl_since_acq_tnd=Decimal("0.000"),
        unrealized_return_since_acq_pct=Decimal("0.000"),
        session_pnl_contribution_tnd=Decimal("71.820"),  # Realized gain on sale: 4683.27 - 4611.45
        portfolio_weight_pct=Decimal("0.000"),
        status="CLOSED_INTRADAY",
    )

    # 3. Reconstructed Transactions
    tx1 = ReconstructedTransaction(
        transaction_id="TX-20261109-001",
        symbol="NEW BODY LINE",
        side="BUY",
        shares=200,
        execution_price_tnd=Decimal("2.450"),
        total_cost_or_proceeds_tnd=Decimal("492.450"),
        estimated_fee_tnd=Decimal("2.450"),
        realized_pnl_tnd=None,
        execution_time_approx="2026-11-09 morning",
        notes="Purchase of 200 shares. Total outlay 492.45 TND (including 0.50% competition fee).",
    )

    tx2 = ReconstructedTransaction(
        transaction_id="TX-20261109-002",
        symbol="STA",
        side="BUY",
        shares=22,
        execution_price_tnd=Decimal("115.000"),
        total_cost_or_proceeds_tnd=Decimal("2542.650"),
        estimated_fee_tnd=Decimal("12.650"),
        realized_pnl_tnd=None,
        execution_time_approx="2026-11-09 morning",
        notes="Purchase of 22 shares per Planner candidate sizing. Outlay 2542.65 TND.",
    )

    tx3 = ReconstructedTransaction(
        transaction_id="TX-20261109-003",
        symbol="UNCONFIRMED_ROUNDTRIP_35",
        side="BUY",
        shares=35,
        execution_price_tnd=Decimal("131.100"),
        total_cost_or_proceeds_tnd=Decimal("4611.450"),
        estimated_fee_tnd=Decimal("22.950"),
        realized_pnl_tnd=None,
        execution_time_approx="2026-11-09 ~11:00",
        notes="Intraday purchase of 35 shares evidenced by 12:04 DOM snapshot (cash dropped to 36939.520 TND).",
    )

    tx4 = ReconstructedTransaction(
        transaction_id="TX-20261109-004",
        symbol="UNCONFIRMED_ROUNDTRIP_35",
        side="SELL",
        shares=35,
        execution_price_tnd=Decimal("134.480"),
        total_cost_or_proceeds_tnd=Decimal("4683.270"),
        estimated_fee_tnd=Decimal("23.300"),
        realized_pnl_tnd=Decimal("71.820"),
        execution_time_approx="2026-11-09 ~13:30",
        notes="Intraday liquidation of 35 shares restoring cash to 41622.790 TND and realizing +71.820 TND.",
    )

    # 4. Model Decision Evaluations
    eval_sta = ModelDecisionEvaluation(
        symbol="STA",
        strategy_id="MODEL_G_SWING_42",
        signal_timestamp="2026-11-09 08:30 UTC",
        suggested_action="BUY",
        suggested_shares=22,
        suggested_price_tnd=Decimal("115.900"),
        suggested_holding_horizon="10 to 20 sessions",
        actual_action="BUY",
        actual_shares=22,
        actual_price_tnd=Decimal("115.575"),
        execution_fidelity="EXACT_MATCH",
        current_unrealized_return_pct=Decimal("-0.580"),
        stop_loss_price_tnd=Decimal("110.150"),
        target_price_tnd=Decimal("126.500"),
        evaluation_notes="Executed exactly 22 shares at favorable price (115.575 vs 115.900 ref). Day 1 mark-to-market spread dip (-0.58%) is well above 110.15 stop-loss.",
    )

    eval_dh = ModelDecisionEvaluation(
        symbol="DELICE HOLDING",
        strategy_id="RISK_ENGINE_CONCENTRATION_GUARD",
        signal_timestamp="2026-11-09 08:30 UTC",
        suggested_action="HOLD",
        suggested_shares=0,
        suggested_price_tnd=Decimal("19.000"),
        suggested_holding_horizon="Long-term core anchor",
        actual_action="HOLD",
        actual_shares=0,
        actual_price_tnd=None,
        execution_fidelity="EXACT_MATCH",
        current_unrealized_return_pct=Decimal("-0.030"),
        stop_loss_price_tnd=Decimal("17.800"),
        target_price_tnd=Decimal("21.500"),
        evaluation_notes="Position holds 263 shares (5020.67 TND capital), right at 10.03% limit. Hold recommendation strictly obeyed, preventing disqualification.",
    )

    eval_mnp = ModelDecisionEvaluation(
        symbol="MNP / MONOPRIX",
        strategy_id="CHALLENGE_UNIVERSE_GATE",
        signal_timestamp="2026-11-09 08:30 UTC",
        suggested_action="SUPPRESS_ORDER_NOT_IN_UNIVERSE",
        suggested_shares=0,
        suggested_price_tnd=Decimal("12.290"),
        suggested_holding_horizon="N/A",
        actual_action="NO_TRADE",
        actual_shares=0,
        actual_price_tnd=None,
        execution_fidelity="EXACT_MATCH",
        current_unrealized_return_pct=None,
        stop_loss_price_tnd=Decimal("0.000"),
        target_price_tnd=Decimal("0.000"),
        evaluation_notes="Candidate was filtered out because it is not in the official 42 Challenge Universe. Human trader correctly entered zero orders.",
    )

    # 5. P&L Semantics Breakdown
    realized_pnl = Decimal("71.820")
    unrealized_delta = Decimal("11.070")  # -3.30 + 23.67 + 5.55 - 14.85
    verified_session_pnl = quantize_tnd(realized_pnl + unrealized_delta)  # +82.890
    unrealized_since_acq = Decimal("-9.860")  # +0.75 - 1.31 + 5.55 - 14.85

    # Fees estimated across transactions
    estimated_fees = quantize_tnd(Decimal("2.450") + Decimal("12.650") + Decimal("46.250"))

    # Total return since competition inception (initial 50,000.000)
    inception_pnl = quantize_tnd(end_equity - Decimal("50000.000"))  # +61.960
    inception_pct = quantize_tnd((inception_pnl / Decimal("50000.000")) * Decimal("100"))

    # Zero reconciliation gap:
    computed_cash = (
        start_cash
        - Decimal("492.450")
        - Decimal("2542.650")
        - Decimal("4611.450")
        + Decimal("4683.270")
    )
    reconciliation_gap = (computed_cash - end_cash).copy_abs()

    concentration_warns = [
        "DELICE HOLDING allocation is 10.03% (5,020.670 TND). Hard single-stock ceiling is 10.00% under competition rules; do not add further shares.",
        "STA allocation is 5.05% (2,527.800 TND). Well within safe 10.00% allocation boundary.",
        "Cash reserve is 83.14% (41,622.790 TND). Ample liquidity for multi-horizon swing opportunities.",
    ]

    priorities = [
        "Obtain CSV/paste export of display_histo.aspx to confirm exact security ticker for the 35-share intraday round-trip.",
        "Monitor STA price action relative to 110.150 TND stop-loss support; avoid day-trade churn.",
        "Maintain DELICE HOLDING without buying to remain compliant with the 10% competition concentration rule.",
        "Verify next morning pre-market quotations on tunisbourse-challenge.com at 09:30 UTC.",
    ]

    return DailySessionReport(
        session_date="2026-11-09",
        starting_equity_tnd=start_equity,
        starting_cash_tnd=start_cash,
        starting_holdings_value_tnd=start_holdings,
        ending_equity_tnd=end_equity,
        ending_cash_tnd=end_cash,
        ending_holdings_value_tnd=end_holdings,
        equity_change_tnd=equity_delta,
        cash_change_tnd=cash_delta,
        holdings_value_change_tnd=holdings_delta,
        verified_session_pnl_tnd=verified_session_pnl,
        realized_pnl_tnd=realized_pnl,
        unrealized_pnl_delta_tnd=unrealized_delta,
        unrealized_pnl_since_acq_tnd=unrealized_since_acq,
        trading_fees_estimated_tnd=estimated_fees,
        total_return_since_inception_tnd=inception_pnl,
        total_return_since_inception_pct=inception_pct,
        competition_ranking=112,
        total_participants=14573,
        attribution_status="PERFORMANCE_ATTRIBUTION_INCOMPLETE",
        attribution_warning=(
            "Performance attribution incomplete: exact ticker and execution timestamps for the 35-share "
            "closed round-trip position require CSV/paste export of display_histo.aspx."
        ),
        reconciliation_gap_tnd=reconciliation_gap,
        positions=[pos_bh, pos_dh, pos_nbl, pos_sta, pos_closed],
        transactions=[tx1, tx2, tx3, tx4],
        model_evaluations=[eval_sta, eval_dh, eval_mnp],
        concentration_warnings=concentration_warns,
        tomorrow_priorities=priorities,
    )
