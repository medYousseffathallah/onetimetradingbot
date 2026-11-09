"""Deterministic position sizing engine for BVMT equity trading decision support.

Enforces:
1. Actual available competition cash, minus cash reserved for open/pending buy orders.
2. Existing position exposure and single-stock concentration limits (10% hard cap, 8.5% target).
3. Round-trip transaction friction: 0.50% purchase fee + 0.50% sale fee.
4. Liquidity constraints: maximum 10% participation in 20-session median daily volume.
5. Exact TND 3-decimal monetary precision and integer share truncation (floor).
6. Risk budget constraints (optional maximum capital at risk based on stop-loss).
7. Minimum useful order size threshold.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

DEFAULT_PURCHASE_FEE_RATE = Decimal("0.0050")  # 0.50%
DEFAULT_SALE_FEE_RATE = Decimal("0.0050")  # 0.50%
DEFAULT_MAX_CONCENTRATION_RATIO = Decimal("0.1000")  # 10.0% competition cap
DEFAULT_TARGET_ALLOCATION_RATIO = Decimal("0.0850")  # 8.5% safe target allocation
DEFAULT_MAX_TURNOVER_PARTICIPATION = Decimal("0.1000")  # 10.0% median daily volume
MINIMUM_ORDER_NOTIONAL_TND = Decimal("100.000")  # Minimum useful order size in TND
TND_PRECISION = Decimal("0.001")


def quantize_tnd(val: Decimal | str | float | None) -> Decimal:
    """Quantize to 3 decimal places (millimes) using standard financial rounding."""
    if val is None:
        return Decimal("0.000")
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(TND_PRECISION)


@dataclass(frozen=True)
class PendingOrderReservation:
    """Represents reserved cash or shares committed to open/pending orders."""

    order_id: str
    instrument_id: str
    side: str  # BUY or SELL
    remaining_shares: int
    limit_price_tnd: Decimal
    fee_rate: Decimal = DEFAULT_PURCHASE_FEE_RATE

    @property
    def reserved_cash_tnd(self) -> Decimal:
        """Cash reserved by an open buy order, including purchase fee."""
        if self.side.upper() != "BUY":
            return Decimal("0.000")
        gross = quantize_tnd(Decimal(self.remaining_shares) * self.limit_price_tnd)
        fee = quantize_tnd(gross * self.fee_rate)
        return gross + fee


@dataclass(frozen=True)
class PositionSizeInput:
    """Input parameters for sizing a manual trade plan."""

    instrument_id: str
    symbol: str
    limit_price_tnd: Decimal
    portfolio_total_equity_tnd: Decimal
    raw_available_cash_tnd: Decimal
    existing_shares: int = 0
    existing_average_cost_tnd: Decimal = Decimal("0.000")
    median_daily_turnover_20s_tnd: Decimal = Decimal("0.000")
    median_daily_volume_20s: int = 0
    pending_orders: Sequence[PendingOrderReservation] = ()
    target_weight_ratio: Decimal = DEFAULT_TARGET_ALLOCATION_RATIO
    max_concentration_ratio: Decimal = DEFAULT_MAX_CONCENTRATION_RATIO
    purchase_fee_rate: Decimal = DEFAULT_PURCHASE_FEE_RATE
    sale_fee_rate: Decimal = DEFAULT_SALE_FEE_RATE
    risk_budget_tnd: Decimal | None = None
    stop_loss_pct: Decimal = Decimal("0.0500")  # 5% default assumed stop-loss
    minimum_order_notional_tnd: Decimal = MINIMUM_ORDER_NOTIONAL_TND
    max_turnover_participation_ratio: Decimal = DEFAULT_MAX_TURNOVER_PARTICIPATION
    is_stale_quote: bool = False
    quote_age_sessions: int = 0
    market_segment: str = "PRINCIPAL"


@dataclass(frozen=True)
class PositionSizeResult:
    """Detailed deterministic position sizing breakdown."""

    instrument_id: str
    symbol: str
    limit_price_tnd: Decimal
    suggested_shares: int
    gross_order_value_tnd: Decimal
    purchase_fee_tnd: Decimal
    total_purchase_cost_tnd: Decimal
    estimated_sale_fee_tnd: Decimal
    break_even_price_tnd: Decimal
    break_even_gain_pct: Decimal

    # Cash and Exposure
    effective_available_cash_tnd: Decimal
    cash_reserved_for_pending_orders_tnd: Decimal
    cash_remaining_after_purchase_tnd: Decimal
    existing_position_shares: int
    existing_position_value_tnd: Decimal
    proposed_total_shares: int
    proposed_position_value_tnd: Decimal
    proposed_position_weight_pct: Decimal

    # Constraint Capacities (in shares)
    cash_capacity_shares: int
    concentration_capacity_shares: int
    liquidity_capacity_shares: int
    risk_budget_capacity_shares: int | None
    binding_constraint: str

    # Warnings and Rejection Reasons
    is_actionable: bool
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "limit_price_tnd": str(self.limit_price_tnd),
            "suggested_shares": self.suggested_shares,
            "gross_order_value_tnd": str(self.gross_order_value_tnd),
            "purchase_fee_tnd": str(self.purchase_fee_tnd),
            "total_purchase_cost_tnd": str(self.total_purchase_cost_tnd),
            "estimated_sale_fee_tnd": str(self.estimated_sale_fee_tnd),
            "break_even_price_tnd": str(self.break_even_price_tnd),
            "break_even_gain_pct": str(self.break_even_gain_pct),
            "effective_available_cash_tnd": str(self.effective_available_cash_tnd),
            "cash_reserved_for_pending_orders_tnd": str(self.cash_reserved_for_pending_orders_tnd),
            "cash_remaining_after_purchase_tnd": str(self.cash_remaining_after_purchase_tnd),
            "existing_position_shares": self.existing_position_shares,
            "existing_position_value_tnd": str(self.existing_position_value_tnd),
            "proposed_total_shares": self.proposed_total_shares,
            "proposed_position_value_tnd": str(self.proposed_position_value_tnd),
            "proposed_position_weight_pct": str(self.proposed_position_weight_pct),
            "cash_capacity_shares": self.cash_capacity_shares,
            "concentration_capacity_shares": self.concentration_capacity_shares,
            "liquidity_capacity_shares": self.liquidity_capacity_shares,
            "risk_budget_capacity_shares": self.risk_budget_capacity_shares,
            "binding_constraint": self.binding_constraint,
            "is_actionable": self.is_actionable,
            "rejection_reasons": self.rejection_reasons,
            "warnings": self.warnings,
        }


def compute_position_size(inp: PositionSizeInput) -> PositionSizeResult:
    """Calculate deterministic manual purchase position sizing respecting all constraints."""
    rejection_reasons: list[str] = []
    warnings: list[str] = []

    # 1. Price validity checks
    if inp.limit_price_tnd <= Decimal("0"):
        return PositionSizeResult(
            instrument_id=inp.instrument_id,
            symbol=inp.symbol,
            limit_price_tnd=Decimal("0.000"),
            suggested_shares=0,
            gross_order_value_tnd=Decimal("0.000"),
            purchase_fee_tnd=Decimal("0.000"),
            total_purchase_cost_tnd=Decimal("0.000"),
            estimated_sale_fee_tnd=Decimal("0.000"),
            break_even_price_tnd=Decimal("0.000"),
            break_even_gain_pct=Decimal("0.000"),
            effective_available_cash_tnd=quantize_tnd(inp.raw_available_cash_tnd),
            cash_reserved_for_pending_orders_tnd=Decimal("0.000"),
            cash_remaining_after_purchase_tnd=quantize_tnd(inp.raw_available_cash_tnd),
            existing_position_shares=inp.existing_shares,
            existing_position_value_tnd=Decimal("0.000"),
            proposed_total_shares=inp.existing_shares,
            proposed_position_value_tnd=Decimal("0.000"),
            proposed_position_weight_pct=Decimal("0.000"),
            cash_capacity_shares=0,
            concentration_capacity_shares=0,
            liquidity_capacity_shares=0,
            risk_budget_capacity_shares=None,
            binding_constraint="invalid_limit_price",
            is_actionable=False,
            rejection_reasons=[
                "invalid_limit_price: Proposed limit price must be strictly positive"
            ],
            warnings=[],
        )

    # 2. Staleness & quote quality checks
    if inp.is_stale_quote or inp.quote_age_sessions > 3:
        warnings.append(
            f"stale_reference_price: Last trade occurred {inp.quote_age_sessions} sessions ago. Real executable price may diverge."
        )

    # 3. Calculate reserved cash from active pending buy orders
    reserved_cash = Decimal("0.000")
    for po in inp.pending_orders:
        if po.side.upper() == "BUY":
            reserved_cash += po.reserved_cash_tnd
    reserved_cash = quantize_tnd(reserved_cash)

    effective_cash = max(Decimal("0.000"), quantize_tnd(inp.raw_available_cash_tnd - reserved_cash))
    if reserved_cash > Decimal("0.000"):
        warnings.append(
            f"cash_reserved_for_pending: {reserved_cash} TND reserved for open buy orders; effective available cash is {effective_cash} TND."
        )

    # 4. Existing position exposure
    existing_mv = quantize_tnd(Decimal(inp.existing_shares) * inp.limit_price_tnd)

    # 5. Concentration Cap & Target Allocation
    total_eq = max(Decimal("0.001"), quantize_tnd(inp.portfolio_total_equity_tnd))
    max_conc_tnd = quantize_tnd(total_eq * inp.max_concentration_ratio)
    target_alloc_tnd = quantize_tnd(total_eq * inp.target_weight_ratio)

    remaining_target_tnd = max(Decimal("0.000"), target_alloc_tnd - existing_mv)

    # 6. Capacity 1: Cash constraint
    # cost = shares * limit * (1 + fee_rate) <= effective_cash
    cost_per_share = inp.limit_price_tnd * (Decimal("1") + inp.purchase_fee_rate)
    cash_cap_shares = int(effective_cash // cost_per_share) if cost_per_share > 0 else 0

    # 7. Capacity 2: Concentration constraint
    # (existing_shares + shares) * limit <= target_alloc_tnd (or hard max_conc_tnd)
    conc_cap_shares = (
        int(remaining_target_tnd // inp.limit_price_tnd) if inp.limit_price_tnd > 0 else 0
    )

    # 8. Capacity 3: Executable Liquidity constraint (10% of median daily volume or turnover)
    if inp.median_daily_volume_20s > 0:
        liq_cap_shares = int(
            Decimal(inp.median_daily_volume_20s) * inp.max_turnover_participation_ratio
        )
    elif inp.median_daily_turnover_20s_tnd > Decimal("0"):
        liq_cap_shares = int(
            (inp.median_daily_turnover_20s_tnd * inp.max_turnover_participation_ratio)
            // inp.limit_price_tnd
        )
    else:
        liq_cap_shares = 0
        warnings.append(
            "untraded_or_zero_volume: Median daily turnover is 0.000 TND. Executable liquidity cannot be verified."
        )

    # 9. Capacity 4: Risk Budget constraint (if configured)
    risk_cap_shares: int | None = None
    if inp.risk_budget_tnd is not None and inp.risk_budget_tnd > Decimal("0"):
        loss_per_share = quantize_tnd(inp.limit_price_tnd * inp.stop_loss_pct)
        if loss_per_share > Decimal("0"):
            risk_cap_shares = int(inp.risk_budget_tnd // loss_per_share)

    # 10. Combine constraints (take minimum of active bounds)
    capacities = [
        ("cash", cash_cap_shares),
        ("concentration", conc_cap_shares),
        ("liquidity", liq_cap_shares),
    ]
    if risk_cap_shares is not None:
        capacities.append(("risk_budget", risk_cap_shares))

    # Identify binding constraint
    sorted_caps = sorted(capacities, key=lambda x: x[1])
    binding_name, min_shares = sorted_caps[0]

    # Verify concentration drift against absolute 10% cap
    # Even if target is 8.5%, total exposure must never breach 10.0%
    while min_shares > 0:
        gross_try = quantize_tnd(Decimal(min_shares) * inp.limit_price_tnd)
        fee_try = quantize_tnd(gross_try * inp.purchase_fee_rate)
        if (gross_try + fee_try <= effective_cash) and (existing_mv + gross_try <= max_conc_tnd):
            break
        min_shares -= 1

    final_shares = max(0, min_shares)

    # 11. Minimum Useful Order Size Gate
    gross_val = quantize_tnd(Decimal(final_shares) * inp.limit_price_tnd)
    if final_shares > 0 and gross_val < inp.minimum_order_notional_tnd:
        rejection_reasons.append(
            f"below_minimum_order_size: Sized order ({gross_val} TND / {final_shares} shares) is below the minimum useful threshold ({inp.minimum_order_notional_tnd} TND)."
        )
        final_shares = 0
        gross_val = Decimal("0.000")

    # 12. Evaluate Rejection Reasons
    if final_shares == 0:
        if effective_cash < inp.limit_price_tnd:
            rejection_reasons.append(
                f"insufficient_cash: Effective available cash ({effective_cash} TND) is less than the price of a single share ({inp.limit_price_tnd} TND)."
            )
        if existing_mv >= target_alloc_tnd:
            rejection_reasons.append(
                f"concentration_cap_reached: Existing position ({existing_mv} TND) already meets or exceeds the target allocation limit ({target_alloc_tnd} TND)."
            )
        if liq_cap_shares <= 0:
            rejection_reasons.append(
                "insufficient_liquidity: 10% daily volume participation allows 0 shares. Market depth is too thin."
            )

    # 13. Financial Computations
    purchase_fee = quantize_tnd(gross_val * inp.purchase_fee_rate)
    total_purchase_cost = gross_val + purchase_fee
    estimated_sale_fee = quantize_tnd(gross_val * inp.sale_fee_rate)
    remaining_cash = quantize_tnd(effective_cash - total_purchase_cost)

    # Break-even price including round-trip fees:
    # Net sale proceeds = P_exit * (1 - sale_fee) == P_entry * (1 + buy_fee)
    # P_exit = P_entry * (1 + buy_fee) / (1 - sale_fee)
    if Decimal("1") - inp.sale_fee_rate > 0:
        break_even_price = quantize_tnd(
            inp.limit_price_tnd
            * (Decimal("1") + inp.purchase_fee_rate)
            / (Decimal("1") - inp.sale_fee_rate)
        )
        break_even_pct = quantize_tnd(
            ((break_even_price - inp.limit_price_tnd) / inp.limit_price_tnd) * Decimal("100")
        )
    else:
        break_even_price = inp.limit_price_tnd
        break_even_pct = Decimal("1.000")

    proposed_tot_shares = inp.existing_shares + final_shares
    proposed_pos_val = quantize_tnd(Decimal(proposed_tot_shares) * inp.limit_price_tnd)
    proposed_pos_wt = quantize_tnd((proposed_pos_val / total_eq) * Decimal("100"))

    # Add descriptive liquidity warnings if applicable
    if final_shares > 0 and inp.median_daily_turnover_20s_tnd < Decimal("25000.000"):
        warnings.append(
            f"thin_daily_turnover: Median daily turnover is {inp.median_daily_turnover_20s_tnd} TND. Sized to {final_shares} shares (10% participation cap)."
        )

    is_actionable = final_shares > 0 and len(rejection_reasons) == 0

    return PositionSizeResult(
        instrument_id=inp.instrument_id,
        symbol=inp.symbol,
        limit_price_tnd=inp.limit_price_tnd,
        suggested_shares=final_shares,
        gross_order_value_tnd=gross_val,
        purchase_fee_tnd=purchase_fee,
        total_purchase_cost_tnd=total_purchase_cost,
        estimated_sale_fee_tnd=estimated_sale_fee,
        break_even_price_tnd=break_even_price,
        break_even_gain_pct=break_even_pct,
        effective_available_cash_tnd=effective_cash,
        cash_reserved_for_pending_orders_tnd=reserved_cash,
        cash_remaining_after_purchase_tnd=remaining_cash,
        existing_position_shares=inp.existing_shares,
        existing_position_value_tnd=existing_mv,
        proposed_total_shares=proposed_tot_shares,
        proposed_position_value_tnd=proposed_pos_val,
        proposed_position_weight_pct=proposed_pos_wt,
        cash_capacity_shares=cash_cap_shares,
        concentration_capacity_shares=conc_cap_shares,
        liquidity_capacity_shares=liq_cap_shares,
        risk_budget_capacity_shares=risk_cap_shares,
        binding_constraint=binding_name,
        is_actionable=is_actionable,
        rejection_reasons=rejection_reasons,
        warnings=warnings,
    )
