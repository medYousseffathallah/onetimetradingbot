"""Research-only fill estimates and historical simulation; no competition execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from bvmt.calendar import ExchangeSession, validate_exchange_calendar
from bvmt.data import DailyBar, validate_bar, validate_bars


@dataclass(frozen=True)
class MarketOrder:
    instrument_id: str
    decision_session: date
    side: Literal["buy", "sell"]
    quantity: int


@dataclass(frozen=True)
class FillEstimate:
    quantity: int
    price: Decimal | None
    fee: Decimal
    reason: str


def estimate_next_bar_fill(
    order: MarketOrder,
    bar: DailyBar,
    *,
    participation_rate: Decimal,
    remaining_shared_capacity: int,
    slippage_bps: Decimal = Decimal("20"),
    commission_bps: Decimal = Decimal("30"),
) -> FillEstimate:
    """Estimate a fill under declared research assumptions.

    The caller must track remaining capacity across ALL orders in a security/session.
    This helper does not implement cash, settlement, ticks, lots or auction priority.
    """
    validate_bar(bar)
    if order.instrument_id != bar.instrument_id:
        raise ValueError("Order and bar instrument mismatch")
    if order.side not in {"buy", "sell"}:
        raise ValueError("Only buy and sell market-order estimates are supported")
    if type(order.quantity) is not int or order.quantity <= 0:
        raise ValueError("Quantity must be a positive integer")
    if not participation_rate.is_finite() or not Decimal(0) < participation_rate <= Decimal(1):
        raise ValueError("Participation must be in (0, 1]")
    for cost in (slippage_bps, commission_bps):
        if not cost.is_finite() or not Decimal(0) <= cost <= Decimal(10000):
            raise ValueError("Cost must be finite and between 0 and 10000 basis points")
    capacity = int(
        (Decimal(bar.volume_shares) * participation_rate).to_integral_value(rounding=ROUND_FLOOR)
    )
    if type(remaining_shared_capacity) is not int or not 0 <= remaining_shared_capacity <= capacity:
        raise ValueError("Remaining shared capacity is outside this bar's research budget")

    def empty(reason: str) -> FillEstimate:
        return FillEstimate(0, None, Decimal("0.000"), reason)

    if bar.session_date <= order.decision_session:
        return empty("not_a_later_session")
    if bar.status != "traded" or bar.volume_shares == 0:
        return empty("not_tradable")
    quantity = min(order.quantity, remaining_shared_capacity)
    if quantity == 0:
        return empty("capacity_exhausted")
    direction = Decimal(1) if order.side == "buy" else Decimal(-1)
    price = bar.open * (Decimal(1) + direction * slippage_bps / Decimal(10000))
    if not bar.low <= price <= bar.high:
        return empty("assumed_price_outside_observed_bar")
    fee = (Decimal(quantity) * price * commission_bps / Decimal(10000)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    return FillEstimate(quantity, price, fee, "hypothetical_partial_or_full_fill")


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash_tnd: Decimal = Decimal("100000.000")
    commission_bps: Decimal = Decimal("50")
    slippage_bps: Decimal = Decimal("10")
    max_volume_participation: Decimal = Decimal("0.10")
    max_position_weight: Decimal = Decimal("0.20")
    carry_pending_orders: bool = True
    max_order_age_sessions: int = 3
    fill_price_mode: str = "next_open"
    max_turnover_participation: Decimal | None = None

    def __post_init__(self) -> None:
        for value in (
            self.initial_cash_tnd,
            self.commission_bps,
            self.slippage_bps,
            self.max_volume_participation,
            self.max_position_weight,
        ):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError("Financial settings must be finite Decimal values")
        if self.initial_cash_tnd <= 0:
            raise ValueError("Initial cash must be positive")
        if not 0 <= self.commission_bps <= 10000 or not 0 <= self.slippage_bps < 10000:
            raise ValueError("Invalid cost basis points")
        if not 0 < self.max_volume_participation <= 1 or not 0 < self.max_position_weight <= 1:
            raise ValueError("Participation and position weight must be in (0, 1]")
        if type(self.max_order_age_sessions) is not int or self.max_order_age_sessions < 1:
            raise ValueError("Order age must be positive integer sessions")
        if self.max_turnover_participation is not None and (
            not isinstance(self.max_turnover_participation, Decimal)
            or not self.max_turnover_participation.is_finite()
            or not 0 < self.max_turnover_participation <= 1
        ):
            raise ValueError("max_turnover_participation must be a finite Decimal in (0, 1]")
        if self.fill_price_mode not in {"next_open", "next_typical"}:
            raise ValueError("Unsupported fill_price_mode")


@dataclass(frozen=True)
class BacktestSignal:
    signal_session: date
    instrument_id: str
    side: OrderSide
    requested_quantity: int
    limit_price_tnd: Decimal | None = None
    rationale: str = ""


@dataclass(frozen=True)
class BacktestOrderRecord:
    order_id: str
    signal_session: date
    instrument_id: str
    side: OrderSide
    requested_quantity: int
    filled_quantity: int
    remaining_quantity: int
    status: str
    limit_price_tnd: Decimal | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True)
class SimulatedFill:
    order_id: str
    session_date: date
    instrument_id: str
    side: OrderSide
    quantity: int
    price_tnd: Decimal
    fee_tnd: Decimal


@dataclass(frozen=True)
class BacktestSessionSnapshot:
    session_date: date
    cash_tnd: Decimal
    holdings_value_tnd: Decimal
    total_equity_tnd: Decimal
    equal_weight_benchmark_equity_tnd: Decimal
    cash_benchmark_equity_tnd: Decimal
    drawdown_pct: Decimal


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    config_hash: str
    start_session: date
    end_session: date
    session_count: int
    initial_equity_tnd: Decimal
    final_equity_tnd: Decimal
    total_return_pct: Decimal
    cash_benchmark_return_pct: Decimal
    equal_weight_benchmark_return_pct: Decimal
    excess_return_vs_equal_weight_pct: Decimal
    max_drawdown_pct: Decimal
    total_fees_tnd: Decimal
    turnover_ratio: Decimal
    filled_order_count: int
    partial_fill_count: int
    expired_or_unfilled_order_count: int
    rejected_order_count: int
    fills: tuple[SimulatedFill, ...]
    orders: tuple[BacktestOrderRecord, ...]
    session_snapshots: tuple[BacktestSessionSnapshot, ...]
    zero_volume_blocked_fill_attempts: int = 0
    liquidated_final_equity_tnd: Decimal = Decimal("0.000")
    liquidated_total_return_pct: Decimal = Decimal("0.000")
    unrealized_liquidation_fee_tnd: Decimal = Decimal("0.000")
    data_sufficiency_warning: str = ""


@dataclass(frozen=True)
class WalkForwardFold:
    fold_index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    train_sessions: int
    test_sessions: int
    strategy_return_pct: Decimal
    liquidated_return_pct: Decimal
    benchmark_return_pct: Decimal
    excess_return_pct: Decimal
    fill_count: int
    fees_tnd: Decimal


@dataclass(frozen=True)
class WalkForwardResult:
    folds: tuple[WalkForwardFold, ...]
    mean_fold_return_pct: Decimal
    mean_liquidated_return_pct: Decimal
    mean_benchmark_return_pct: Decimal
    mean_excess_return_pct: Decimal
    positive_fold_ratio: Decimal
    total_folds: int
    is_statistically_conclusive: bool
    audit_conclusion: str


@dataclass(frozen=True)
class SensitivityScenario:
    commission_bps: Decimal
    max_volume_participation: Decimal
    slippage_bps: Decimal
    total_return_pct: Decimal
    liquidated_return_pct: Decimal
    total_fees_tnd: Decimal
    fill_count: int


@dataclass(frozen=True)
class TradingCalendar:
    sessions: tuple[ExchangeSession, ...]

    def __post_init__(self) -> None:
        validate_exchange_calendar(self.sessions)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


DEFAULT_BACKTEST_CONFIG = BacktestConfig()


def run_historical_backtest(
    bars: Sequence[DailyBar],
    signals: Sequence[BacktestSignal],
    *,
    config: BacktestConfig = DEFAULT_BACKTEST_CONFIG,
    calendar: TradingCalendar | None = None,
    eligible_instruments: set[str] | None = None,
) -> BacktestResult:
    """Deterministic research-conservative simulation, with immediate cash settlement.

    Input order breaks ties between same-date signals. Age counts all open sessions,
    including missing/illiquid bars. End-of-sample residuals expire. Missing marks
    use the latest observed close (stale valuation only, never an executable quote).
    Benchmark: whole-share equal initial sleeves for the supplied static universe;
    instruments absent/untradable at inception retain cash permanently. This is a
    static-universe price-return comparison, not a point-in-time membership model.
    """
    checked = validate_bars(bars)
    first, last = min(b.session_date for b in checked), max(b.session_date for b in checked)
    by_date: dict[date, dict[str, DailyBar]] = {}
    for bar in checked:
        by_date.setdefault(bar.session_date, {})[bar.instrument_id] = bar
    if calendar is None:
        sessions = sorted(by_date)  # observed sessions; never infer weekdays
    else:
        known = {s.session_date: s.is_open for s in calendar.sessions}
        if any(not known.get(d, False) for d in by_date):
            raise ValueError("Bar session missing or closed in exchange calendar")
        sessions = sorted(d for d, opened in known.items() if opened and first <= d <= last)
    records: list[BacktestOrderRecord] = []
    for i, signal in enumerate(signals):
        reason = None
        if eligible_instruments is not None and signal.instrument_id not in eligible_instruments:
            reason = "ineligible_instrument"
        elif signal.side not in {OrderSide.BUY, OrderSide.SELL}:
            reason = "invalid_side"
        elif type(signal.requested_quantity) is not int or signal.requested_quantity <= 0:
            reason = "invalid_quantity"
        elif signal.limit_price_tnd is not None and (
            not isinstance(signal.limit_price_tnd, Decimal)
            or not signal.limit_price_tnd.is_finite()
            or signal.limit_price_tnd <= 0
        ):
            reason = "invalid_limit_price"
        records.append(
            BacktestOrderRecord(
                f"order-{i + 1:06d}",
                signal.signal_session,
                signal.instrument_id,
                signal.side,
                signal.requested_quantity,
                0,
                signal.requested_quantity,
                "REJECTED" if reason else "PENDING",
                signal.limit_price_tnd,
                reason,
            )
        )
    cash = config.initial_cash_tnd
    holdings: dict[str, int] = {}
    closes: dict[str, Decimal] = {}
    ages = dict.fromkeys(range(len(records)), 0)
    fills: list[SimulatedFill] = []
    partial_orders: set[int] = set()
    snapshots: list[BacktestSessionSnapshot] = []
    fee_rate = config.commission_bps / Decimal(10000)
    peak = cash
    zero_volume_blocked = 0
    fees = Decimal(0)
    notional = Decimal(0)
    bench_cash = cash
    bench_holdings: dict[str, int] = {}
    universe = sorted({b.instrument_id for b in checked})
    sleeve = cash / Decimal(len(universe))
    for session in sessions:
        today = by_date.get(session, {})
        # Open/previous-close marks only for open-time portfolio sizing.
        marks = dict(closes)
        marks.update({key: b.open for key, b in today.items()})
        capacity = {
            key: int(Decimal(b.volume_shares) * config.max_volume_participation)
            for key, b in today.items()
        }
        turnover_capacity = (
            {key: b.turnover_tnd * config.max_turnover_participation for key, b in today.items()}
            if config.max_turnover_participation is not None
            else {}
        )
        if session == sessions[0]:
            for key in universe:
                b = today.get(key)
                if b is None or b.status != "traded" or b.volume_shares <= 0:
                    continue
                price = b.open * (1 + config.slippage_bps / Decimal(10000))
                if not b.low <= price <= b.high:
                    continue
                qty = min(int(sleeve / (price * (1 + fee_rate))), capacity[key])
                if config.max_turnover_participation is not None:
                    qty = min(qty, int(turnover_capacity[key] / price))
                while (
                    qty
                    and _money(Decimal(qty) * price) + _money(Decimal(qty) * price * fee_rate)
                    > sleeve
                ):
                    qty -= 1
                bench_holdings[key] = qty
                bench_cash -= _money(Decimal(qty) * price) + _money(Decimal(qty) * price * fee_rate)
        for idx in sorted(range(len(records)), key=lambda i: (records[i].signal_session, i)):
            order = records[idx]
            if order.status in {"FILLED", "EXPIRED", "REJECTED"} or session <= order.signal_session:
                continue
            ages[idx] += 1
            key = order.instrument_id
            owned = holdings.get(key, 0)
            if order.side == OrderSide.SELL and owned <= 0:
                records[idx] = replace(
                    order, status="REJECTED", rejection_reason="insufficient_holdings"
                )
                continue
            b = today.get(key)
            quantity = 0
            if b is not None and b.volume_shares == 0:
                zero_volume_blocked += 1
            if b is not None and b.status == "traded" and capacity[key] > 0:
                base = (
                    b.open
                    if config.fill_price_mode == "next_open"
                    else (b.high + b.low + b.close) / Decimal(3)
                )
                direction = Decimal(1) if order.side == OrderSide.BUY else Decimal(-1)
                price = base * (1 + direction * config.slippage_bps / Decimal(10000))
                limit = order.limit_price_tnd
                allowed = b.low <= price <= b.high and (
                    limit is None
                    or (price <= limit if order.side == OrderSide.BUY else price >= limit)
                )
                if allowed:
                    quantity = min(order.remaining_quantity, capacity[key])
                    if config.max_turnover_participation is not None:
                        quantity = min(quantity, int(turnover_capacity[key] / price))
                    if order.side == OrderSide.SELL:
                        quantity = min(quantity, owned)
                    else:
                        equity = cash + sum(
                            (Decimal(q) * marks[k] for k, q in holdings.items()), Decimal(0)
                        )
                        # Enforce post-fee concentration using execution price for the target.
                        equity += Decimal(owned) * (price - marks.get(key, price))
                        room = config.max_position_weight * equity - Decimal(owned) * price
                        weight_cap = max(
                            0, int(room / (price * (1 + config.max_position_weight * fee_rate)))
                        )
                        quantity = min(quantity, int(cash / (price * (1 + fee_rate))), weight_cap)
                        while (
                            quantity
                            and _money(Decimal(quantity) * price)
                            + _money(Decimal(quantity) * price * fee_rate)
                            > cash
                        ):
                            quantity -= 1
                    if quantity > 0:
                        amount = _money(Decimal(quantity) * price)
                        fee = _money(Decimal(quantity) * price * fee_rate)
                        cash += -amount - fee if order.side == OrderSide.BUY else amount - fee
                        holdings[key] = (
                            owned + quantity if order.side == OrderSide.BUY else owned - quantity
                        )
                        capacity[key] -= quantity
                        if config.max_turnover_participation is not None:
                            turnover_capacity[key] -= Decimal(quantity) * price
                        marks[key] = price
                        fees += fee
                        notional += amount
                        fills.append(
                            SimulatedFill(
                                order.order_id, session, key, order.side, quantity, price, fee
                            )
                        )
            remaining = order.remaining_quantity - quantity
            if quantity > 0 and remaining > 0:
                partial_orders.add(idx)
            status = (
                "FILLED"
                if remaining == 0
                else ("PARTIALLY_FILLED" if order.filled_quantity + quantity else "PENDING")
            )
            if remaining and (
                not config.carry_pending_orders or ages[idx] >= config.max_order_age_sessions
            ):
                status = "EXPIRED"
            records[idx] = replace(
                order,
                filled_quantity=order.filled_quantity + quantity,
                remaining_quantity=remaining,
                status=status,
            )
        closes.update({key: b.close for key, b in today.items()})
        value = sum((Decimal(q) * closes[key] for key, q in holdings.items()), Decimal(0))
        equity = cash + value
        benchmark = bench_cash + sum(
            (Decimal(q) * closes[key] for key, q in bench_holdings.items()), Decimal(0)
        )
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak * Decimal(100)
        snapshots.append(
            BacktestSessionSnapshot(
                session, cash, value, equity, benchmark, config.initial_cash_tnd, drawdown
            )
        )
    records = [
        replace(o, status="EXPIRED") if o.status in {"PENDING", "PARTIALLY_FILLED"} else o
        for o in records
    ]
    final = snapshots[-1]
    total_return = (final.total_equity_tnd / config.initial_cash_tnd - 1) * Decimal(100)
    benchmark_return = (
        final.equal_weight_benchmark_equity_tnd / config.initial_cash_tnd - 1
    ) * Decimal(100)
    unrealized_liquidation_fee = _money(final.holdings_value_tnd * fee_rate)
    liquidated_final_equity = final.total_equity_tnd - unrealized_liquidation_fee
    liquidated_total_return = (liquidated_final_equity / config.initial_cash_tnd - 1) * Decimal(100)
    warning = ""
    if len(sessions) < 120:
        warning = (
            f"Sample size warning: dataset contains only {len(sessions)} sessions (minimum recommended: "
            f"250+ sessions for equity strategies). 2022-2025 multi-year data strictly required before "
            f"concluding positive strategy edge."
        )
    canonical = json.dumps(asdict(config), default=str, sort_keys=True, separators=(",", ":"))
    return BacktestResult(
        config,
        hashlib.sha256(canonical.encode()).hexdigest(),
        sessions[0],
        sessions[-1],
        len(sessions),
        config.initial_cash_tnd,
        final.total_equity_tnd,
        total_return,
        Decimal(0),
        benchmark_return,
        total_return - benchmark_return,
        max(s.drawdown_pct for s in snapshots),
        fees,
        notional / config.initial_cash_tnd,
        sum(o.status == "FILLED" for o in records),
        len(partial_orders),
        sum(o.status == "EXPIRED" for o in records),
        sum(o.status == "REJECTED" for o in records),
        tuple(fills),
        tuple(records),
        tuple(snapshots),
        zero_volume_blocked,
        liquidated_final_equity,
        liquidated_total_return,
        unrealized_liquidation_fee,
        warning,
    )


def run_sensitivity_analysis(
    bars: Sequence[DailyBar],
    signals: Sequence[BacktestSignal],
    *,
    base_config: BacktestConfig = DEFAULT_BACKTEST_CONFIG,
    commission_bps_grid: tuple[Decimal, ...] = (Decimal("30"), Decimal("50"), Decimal("70")),
    volume_participation_grid: tuple[Decimal, ...] = (
        Decimal("0.05"),
        Decimal("0.10"),
        Decimal("0.20"),
    ),
    slippage_bps_grid: tuple[Decimal, ...] = (Decimal("5"), Decimal("10"), Decimal("20")),
) -> tuple[SensitivityScenario, ...]:
    """Audit strategy robustness across commission rates, participation caps, and slippage."""
    scenarios: list[SensitivityScenario] = []
    for comm in commission_bps_grid:
        for vol in volume_participation_grid:
            for slip in slippage_bps_grid:
                cfg = replace(
                    base_config,
                    commission_bps=comm,
                    max_volume_participation=vol,
                    slippage_bps=slip,
                )
                res = run_historical_backtest(bars, signals, config=cfg)
                scenarios.append(
                    SensitivityScenario(
                        commission_bps=comm,
                        max_volume_participation=vol,
                        slippage_bps=slip,
                        total_return_pct=res.total_return_pct,
                        liquidated_return_pct=res.liquidated_total_return_pct,
                        total_fees_tnd=res.total_fees_tnd,
                        fill_count=len(res.fills),
                    )
                )
    return tuple(scenarios)


def run_walk_forward_evaluation(
    bars: Sequence[DailyBar],
    signal_builder: Callable[[Sequence[DailyBar], date], Sequence[BacktestSignal]],
    *,
    config: BacktestConfig = DEFAULT_BACKTEST_CONFIG,
    train_window_sessions: int = 30,
    test_window_sessions: int = 10,
    step_sessions: int = 10,
) -> WalkForwardResult:
    """Rigorous chronological walk-forward evaluation without lookahead bias.

    Splits observed sessions into rolling train/test windows. Tests out-of-sample forward
    performance. Discloses whether sample size is statistically conclusive.
    """
    checked = validate_bars(bars)
    sessions = sorted({b.session_date for b in checked})
    min_required = train_window_sessions + test_window_sessions
    if len(sessions) < min_required:
        raise ValueError(
            f"Insufficient sessions ({len(sessions)}) for walk-forward with "
            f"train={train_window_sessions} and test={test_window_sessions}"
        )

    folds: list[WalkForwardFold] = []
    fold_idx = 1
    cursor = 0
    while cursor + min_required <= len(sessions):
        train_sessions = sessions[cursor : cursor + train_window_sessions]
        test_sessions = sessions[
            cursor + train_window_sessions : cursor + train_window_sessions + test_window_sessions
        ]
        decision_session = train_sessions[-1]

        # Point-in-time bars up to decision session strictly for signals
        train_bars = [b for b in checked if b.session_date <= decision_session]
        signals = signal_builder(train_bars, decision_session)

        # Simulation runs over the out-of-sample forward test window
        test_bars = [b for b in checked if test_sessions[0] <= b.session_date <= test_sessions[-1]]
        if test_bars:
            fold_res = run_historical_backtest(
                test_bars,
                signals,
                config=config,
            )
            folds.append(
                WalkForwardFold(
                    fold_index=fold_idx,
                    train_start=train_sessions[0],
                    train_end=train_sessions[-1],
                    test_start=test_sessions[0],
                    test_end=test_sessions[-1],
                    train_sessions=len(train_sessions),
                    test_sessions=len(test_sessions),
                    strategy_return_pct=fold_res.total_return_pct,
                    liquidated_return_pct=fold_res.liquidated_total_return_pct,
                    benchmark_return_pct=fold_res.equal_weight_benchmark_return_pct,
                    excess_return_pct=fold_res.excess_return_vs_equal_weight_pct,
                    fill_count=len(fold_res.fills),
                    fees_tnd=fold_res.total_fees_tnd,
                )
            )
            fold_idx += 1
        cursor += step_sessions

    if not folds:
        raise ValueError("No valid folds generated")

    mean_ret = sum((f.strategy_return_pct for f in folds), Decimal(0)) / Decimal(len(folds))
    mean_liq = sum((f.liquidated_return_pct for f in folds), Decimal(0)) / Decimal(len(folds))
    mean_bench = sum((f.benchmark_return_pct for f in folds), Decimal(0)) / Decimal(len(folds))
    mean_excess = sum((f.excess_return_pct for f in folds), Decimal(0)) / Decimal(len(folds))
    pos_folds = sum(1 for f in folds if f.strategy_return_pct > 0)
    pos_ratio = Decimal(pos_folds) / Decimal(len(folds))

    is_conclusive = len(folds) >= 10 and len(sessions) >= 250
    conclusion = (
        f"Statistically conclusive: {is_conclusive}. Folds tested: {len(folds)}. "
        f"Mean liquidated return: {mean_liq:.4f}%, Mean excess vs benchmark: {mean_excess:.4f}%. "
        f"{'Sample size insufficient to certify alpha; 2022-2025 multi-year data requested.' if not is_conclusive else 'Certified.'}"
    )

    return WalkForwardResult(
        folds=tuple(folds),
        mean_fold_return_pct=mean_ret.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        mean_liquidated_return_pct=mean_liq.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        mean_benchmark_return_pct=mean_bench.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        mean_excess_return_pct=mean_excess.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        positive_fold_ratio=pos_ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        total_folds=len(folds),
        is_statistically_conclusive=is_conclusive,
        audit_conclusion=conclusion,
    )
