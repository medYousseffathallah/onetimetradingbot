"""Chronological, research-conservative simulation with one cash and settlement ledger."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal as D
from pathlib import Path
from statistics import median, pstdev
from typing import TYPE_CHECKING, Literal

from .contracts import ModelExperiment, PortfolioSnapshot, ProvenanceValue, money, pv
from .market_data import REGISTRY_KNOWN
from .research_engine import bounded_risk_ratio_v2

if TYPE_CHECKING:
    from .market_data import MarketData

ZERO = D(0)
FEE = D("0.005")
CAP = D("0.10")
SOURCE = "v2_backtest_sim"
FAMILIES = (
    "BL-CASH",
    "BL-EW-CHAL",
    "BL-EW-FULL",
    "BL-MOM20",
    "LEGACY-G-APPROX",
    "V2-D-MOM-RISK",
    "V2-F-LIQ-TREND",
    "V2-H-PULLBACK",
    "V2-G-AWAKENING",
)
EXIT_POLICIES = (
    "fixed_horizon",
    "trend_deterioration",
    "trailing_profit_5pct",
    "trailing_profit_8pct",
    "volatility_adjusted_exit",
    "partial_profit_trim",
    "time_stop",
    "opportunity_rotation",
    "combined_risk_trend",
)
Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Fold:
    decision: int
    entry: int
    end: int
    last_training_decision: int


def folds(
    count: int, horizon: int, offset: int = 0, cadence: int | None = None
) -> tuple[Fold, ...]:
    step = horizon if cadence is None else cadence
    if horizon not in (5, 10, 20) or step < horizon or not 0 <= offset < step:
        raise ValueError("invalid horizon, overlapping fold cadence or phase")
    return tuple(
        Fold(i, i + 1, i + horizon, i - horizon - 2)
        for i in range(61 + offset, count - horizon, step)
    )


@dataclass(frozen=True)
class Bar:
    session: date
    open: D
    close: D
    turnover: D | None
    volume: int
    status: str
    available_at: datetime | None
    low: D | None = None
    high: D | None = None

    def fill_price(self, side: Side, bps: D) -> D | None:
        price = money(self.open * (1 + (bps if side == "BUY" else -bps) / 10000))
        if (
            not self.tradable
            or price <= 0
            or (self.low is not None and self.open < self.low)
            or (self.high is not None and self.open > self.high)
        ):
            return None
        return price

    @property
    def tradable(self) -> bool:
        return (
            self.volume > 0
            and self.status.lower() in {"traded", "active", "synthetic_fixture"}
            and min(self.open, self.close) > 0
        )


@dataclass(frozen=True)
class Order:
    instrument: str
    side: Side
    requested: int
    trailing_cap: int

    @property
    def planned_shares(self) -> int:
        """This upper bound is frozen with the signal, before the next bar exists."""
        return min(self.requested, self.trailing_cap)


@dataclass(frozen=True)
class Fill:
    session_index: int
    instrument: str
    side: Side
    quantity: int
    price: D
    gross: D
    fee: D


@dataclass
class Book:
    cash: D
    quantity: dict[str, int] = field(default_factory=dict)
    unsettled: dict[int, D] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    cashflows: dict[str, D] = field(default_factory=dict)
    used_capacity: dict[tuple[str, int], int] = field(default_factory=dict)
    requested_shares: int = 0
    unfilled_orders: int = 0

    def settle(self, index: int) -> None:
        self.cash += self.unsettled.pop(index, ZERO)

    def equity(self, marks: Mapping[str, D]) -> D:
        return (
            self.cash
            + sum(self.unsettled.values(), ZERO)
            + sum((n * marks[s] for s, n in self.quantity.items() if n), ZERO)
        )

    def execute(
        self,
        order: Order,
        bar: Bar | None,
        index: int,
        bps: D,
        settlement: int,
        session_volume: int,
        equity: D,
    ) -> None:
        name, side = order.instrument, order.side
        held = self.quantity.get(name, 0)
        self.requested_shares += order.planned_shares
        key = (name, index)
        consumed = self.used_capacity.get(key, 0)
        if bar is None or not bar.tradable:
            self.unfilled_orders += 1
            return
        capacity = max(0, min(order.trailing_cap, min(bar.volume, session_volume) // 10) - consumed)
        quantity = min(order.planned_shares, capacity)
        price = bar.fill_price(side, bps)
        if price is None:
            self.unfilled_orders += 1
            return
        if side == "BUY":
            room = equity * CAP - held * price
            quantity = min(
                quantity,
                int(max(ZERO, room) / (price * (1 + FEE))),
                int(self.cash / (price * (1 + FEE))),
            )
        else:
            quantity = min(quantity, held)
        if quantity <= 0:
            self.unfilled_orders += 1
            return
        gross = money(quantity * price)
        fee = money(gross * FEE)
        flow = -(gross + fee) if side == "BUY" else gross - fee
        if side == "SELL" and settlement:
            release = index + settlement
            self.unsettled[release] = self.unsettled.get(release, ZERO) + flow
        else:
            self.cash += flow
        self.quantity[name] = held + (quantity if side == "BUY" else -quantity)
        self.cashflows[name] = self.cashflows.get(name, ZERO) + flow
        self.used_capacity[key] = consumed + quantity
        self.fills.append(Fill(index, name, side, quantity, price, gross, fee))


@dataclass(frozen=True)
class Features:
    close: D
    adv: D | None
    volume_cap: int
    ret5: D | None
    ret20: D | None
    ret60: D | None
    risk: D | None
    vol: D | None
    awakening: bool


@dataclass
class Simulation:
    book: Book
    marks: dict[str, D]
    equities: list[D]
    utilizations: list[D]
    fold_count: int
    initial: D
    known_candidates: int
    missing_candidates: int

    @property
    def net(self) -> D:
        return (self.equities[-1] / self.initial - 1) * 100

    @property
    def drawdown(self) -> D:
        peak = self.initial
        dd = ZERO
        for value in self.equities:
            peak = max(value, peak)
            dd = max(dd, (peak - value) / peak * 100)
        return dd


@dataclass(frozen=True)
class PhaseSensitivity:
    phase_returns: tuple[ProvenanceValue, ...]
    minimum: ProvenanceValue
    p25: ProvenanceValue
    median: ProvenanceValue
    p75: ProvenanceValue
    maximum: ProvenanceValue
    iqr_pp: ProvenanceValue


@dataclass(frozen=True)
class ExitComparison:
    net_return_pct: ProvenanceValue
    max_drawdown_pct: ProvenanceValue
    profit_retention_pct: ProvenanceValue
    false_exit_rate_pct: ProvenanceValue
    missed_subsequent_upside_pct: ProvenanceValue
    feasibility_pct: ProvenanceValue
    sample_count: int
    exit_opportunities: int


class Backtester:
    """Daily bar clocks use a 17:00 Tunis research cutoff (16:00 UTC).

    Decision features require actual source availability and contiguous calendar sessions.
    Fills and equity marks are evaluated retrospectively using realized session bars.
    """

    def __init__(
        self,
        sessions: tuple[date, ...],
        series: dict[str, tuple[Bar, ...]],
        challenge: frozenset[str],
        challenge_known_from: date | None = None,
        *,
        run_mode: Literal[
            "STRICT_PIT", "RETROSPECTIVE_EXPLORATORY", "SYNTHETIC_DEMO"
        ] = "STRICT_PIT",
    ):
        if not sessions or tuple(sorted(set(sessions))) != sessions:
            raise ValueError("expected sorted unique exchange sessions")
        self.sessions = sessions
        self.series = series
        self.challenge = challenge
        self.challenge_known_from = challenge_known_from
        self.run_mode: Literal["STRICT_PIT", "RETROSPECTIVE_EXPLORATORY", "SYNTHETIC_DEMO"] = (
            run_mode
        )
        self.rows = {s: {b.session: b for b in series[s]} for s in sorted(series)}
        if any(len(rows) != len(series[s]) for s, rows in self.rows.items()):
            raise ValueError("duplicate instrument/session")
        self.features: dict[tuple[int, str], Features | None] = {}
        digest = hashlib.sha256(repr((sessions, sorted(challenge), challenge_known_from)).encode())
        for name, rows in self.rows.items():
            digest.update(name.encode())
            for session in sorted(rows):
                digest.update(repr(rows[session]).encode())
        self.data_hash = digest.hexdigest()
        self.source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.evaluation_cutoff = max(
            datetime.combine(sessions[-1], time(16), UTC),
            max(
                (b.available_at for bars in series.values() for b in bars if b.available_at),
                default=datetime.combine(sessions[-1], time(16), UTC),
            ),
        )

    @classmethod
    def from_market(cls, market: MarketData) -> Backtester:
        series = {}
        for name, observations in market.bars.items():
            values = []
            for bar in observations:
                p = bar.provenance
                values.append(
                    Bar(
                        bar.session_date,
                        bar.open_tnd.value or ZERO,
                        bar.close_tnd.value or ZERO,
                        bar.turnover_tnd.value,
                        bar.volume_shares,
                        bar.status,
                        p.available_at,
                        bar.low_tnd.value,
                        bar.high_tnd.value,
                    )
                )
            series[name] = tuple(values)
        is_demo = any(
            b.provenance.data_quality_status == "SYNTHETIC_FIXTURE"
            for bars in market.bars.values()
            for b in bars
        )
        return cls(
            market.sessions,
            series,
            frozenset(k for k, v in market.instruments.items() if v.challenge_member),
            None if is_demo else REGISTRY_KNOWN.date(),
            run_mode="SYNTHETIC_DEMO" if is_demo else "STRICT_PIT",
        )

    def _features(self, index: int, name: str) -> Features | None:
        key = (index, name)
        if key in self.features:
            return self.features[key]
        at = datetime.combine(self.sessions[index], time(16), UTC)
        window = []
        for session in reversed(self.sessions[max(0, index - 60) : index + 1]):
            bar = self.rows[name].get(session)
            if bar is None or bar.available_at is None or bar.available_at > at or bar.close <= 0:
                break
            window.append(bar)
        result = None
        if len(window) >= 20:
            recent = window[:20]
            volumes = [D(b.volume) for b in recent]
            turnover = [b.turnover for b in recent if b.turnover is not None]
            close = recent[0].close

            def change(lag: int) -> D | None:
                return close / window[lag].close - 1 if len(window) > lag else None

            ret5, ret20, ret60 = change(5), change(20), change(60)
            vol = (
                pstdev([window[i].close / window[i + 1].close - 1 for i in range(20)])
                if len(window) > 20
                else None
            )
            risk = None if ret20 is None or vol is None else bounded_risk_ratio_v2(ret20, vol)
            previous_volumes = [D(b.volume) for b in window[1:21]]
            med_prev = median(previous_volumes)
            awakening = (
                len(previous_volumes) == 20
                and med_prev > 0
                and volumes[0] >= med_prev * 2
                and close > window[1].close
                and ret20 is not None
                and ret20 > 0
                and ret5 is not None
                and ret5 > 0
                and sum(v == 0 for v in previous_volumes) <= 3
            )
            result = Features(
                close,
                median(turnover) if len(turnover) == 20 else None,
                int(median(volumes) * CAP),
                ret5,
                ret20,
                ret60,
                risk,
                vol,
                awakening,
            )
        self.features[key] = result
        return result

    def _ranks(
        self, family: str, index: int, excluded: str | None
    ) -> tuple[list[str], dict[str, Features], int]:
        if family not in FAMILIES:
            raise ValueError("unknown hypothesis")
        names = [
            s
            for s in self.rows
            if s != excluded and (family == "BL-EW-FULL" or s in self.challenge)
        ]
        known: dict[str, Features] = {}
        if (
            family != "BL-EW-FULL"
            and self.challenge_known_from
            and self.sessions[index] < self.challenge_known_from
        ):
            return [], known, len(names)
        for name in names:
            feature = self._features(index, name)
            if feature is not None:
                known[name] = feature
        if family == "BL-CASH":
            return [], known, len(names)
        if family.startswith("BL-EW"):
            return list(known), known, len(names)
        ranked = []
        for name, x in known.items():
            if x.ret20 is None or x.adv is None or x.adv < 5000 or x.volume_cap <= 0:
                continue
            rank = x.ret20
            if family not in {"BL-MOM20", "V2-H-PULLBACK"}:
                if x.ret20 <= 0 or x.risk is None:
                    continue
                rank = x.risk
            if family == "V2-F-LIQ-TREND":
                rank *= min(D(1), x.adv / 50000)
            if family == "V2-H-PULLBACK":
                if x.ret5 is None or x.ret60 is None or x.ret60 <= 0 or x.ret5 >= 0:
                    continue
                rank = -x.ret5
            if family == "V2-G-AWAKENING" and not x.awakening:
                continue
            ranked.append((name, rank))
        ordered = [s for s, _ in sorted(ranked, key=lambda p: (-p[1], p[0]))]
        if family == "V2-F-LIQ-TREND":
            ordered = ordered[:5] + [s for s in ordered[5:] if (known[s].adv or ZERO) >= 50000][:5]
        else:
            ordered = ordered[: 3 if family == "LEGACY-G-APPROX" else 5]
        return ordered, known, len(names)

    def simulate(
        self,
        family: str,
        horizon: int = 10,
        *,
        offset: int = 0,
        cadence: int | None = None,
        initial: D = D("50000.000"),
        bps: D = ZERO,
        settlement: int = 0,
        excluded: str | None = None,
    ) -> Simulation:
        if (
            family not in FAMILIES
            or bps < 0
            or bps >= 10000
            or settlement not in (0, 3)
            or initial <= 0
        ):
            raise ValueError("invalid experiment parameters")
        step = cadence or (20 if family == "LEGACY-G-APPROX" else horizon)
        periods = folds(len(self.sessions), horizon, offset, step)
        if not periods:
            raise ValueError("insufficient history for a complete purged fold")
        decisions = {f.decision for f in periods}
        book = Book(money(initial))
        marks: dict[str, D] = {}
        path = [book.cash]
        utilization = []
        pending: list[Order] = []
        known_total = missing = 0
        for i in range(periods[0].decision, periods[-1].end + 1):
            day = self.sessions[i]
            book.settle(i)
            opening = dict(marks)
            for name in book.quantity:
                bar = self.rows[name].get(day)
                if bar and bar.tradable:
                    opening[name] = bar.open
            equity = book.equity(opening)
            for order in pending:
                bar = self.rows[order.instrument].get(day)
                book.execute(order, bar, i, bps, settlement, bar.volume if bar else 0, equity)
            for name, quantity in book.quantity.items():
                if quantity:
                    bar = self.rows[name].get(day)
                    if bar and bar.close > 0:
                        marks[name] = bar.close
            equity = book.equity(marks)
            path.append(equity)
            utilization.append(
                sum((n * marks[s] for s, n in book.quantity.items() if n), ZERO) / equity * 100
            )
            pending = []
            if i not in decisions:
                continue
            selected, known, names = self._ranks(family, i, excluded)
            known_total += len(known)
            missing += names - len(known)
            # Revalue at decision using only marks available by this cutoff.
            # A previously purchased holding can temporarily lack a fresh released mark.
            pit_marks = {f.instrument: f.price for f in book.fills}
            pit_marks.update({name: x.close for name, x in known.items()})
            budget = book.equity(pit_marks)
            target = budget * min(CAP, D(1) / len(selected)) if selected else ZERO
            for name in dict.fromkeys([*book.quantity, *selected]):
                feature = known.get(name)
                held_qty = book.quantity.get(name, 0)
                if feature is None:
                    if held_qty > 0 and name not in selected:
                        recent_vols = [
                            D(b.volume)
                            for s in self.sessions[max(0, i - 19) : i + 1]
                            if (b := self.rows.get(name, {}).get(s)) is not None
                            and b.available_at is not None
                            and b.available_at <= datetime.combine(self.sessions[i], time(16), UTC)
                        ]
                        cap_shares = int(median(recent_vols) * CAP) if recent_vols else held_qty
                        if cap_shares > 0:
                            pending.append(Order(name, "SELL", held_qty, cap_shares))
                    continue
                desired = int(target / feature.close) if name in selected else 0
                delta = desired - held_qty
                if delta:
                    pending.append(
                        Order(name, "BUY" if delta > 0 else "SELL", abs(delta), feature.volume_cap)
                    )
            pending.sort(key=lambda o: o.side == "BUY")
        return Simulation(
            book, marks, path, utilization, len(periods), initial, known_total, missing
        )

    def _metric(
        self, value: D | int | None, unit: str = "PCT", reason: str | None = None
    ) -> ProvenanceValue:
        at = self.evaluation_cutoff
        return pv(value, unit, "UNAVAILABLE" if value is None else "SIMULATED", SOURCE, at, reason)

    def initial_holdings_baseline(
        self, snapshot: PortfolioSnapshot, end: date
    ) -> dict[str, ProvenanceValue]:
        """BL-BH-INIT starts with the captured shares and cash, with no intervening trades."""
        if (
            snapshot.verification_status not in {"OBSERVED", "SIMULATED"}
            or snapshot.captured_at is None
        ):
            raise ValueError("Requires a dated observed account or synthetic demo snapshot")
        if end not in self.sessions or end < snapshot.captured_at.date():
            raise ValueError("End must be an exchange session on or after capture")
        initial = snapshot.equity_tnd.value
        cash = snapshot.cash_tnd.value
        if initial is None or initial <= 0 or cash is None:
            raise ValueError("Missing initial valuation")
        source = f"BL-BH-INIT/{snapshot.snapshot_id}"
        value = cash
        sell_fee = ZERO
        cutoff = datetime.combine(end, time(16), UTC)
        # Valuation of an observed past session can be calculated only once its inputs arrive.
        calculated = max(cutoff, snapshot.captured_at)
        reason = None
        for holding in snapshot.holdings:
            if not holding.quantity:
                continue
            bar = self.rows.get(holding.instrument_id, {}).get(end)
            if bar is None or bar.close <= 0 or bar.available_at is None:
                reason = f"Missing terminal mark for {holding.instrument_id}"
                break
            calculated = max(calculated, bar.available_at)
            gross = holding.quantity * bar.close
            value += gross
            sell_fee += money(gross * FEE)
        outputs = {
            "ending_equity_tnd": (value, "TND"),
            "net_return_pct": ((value / initial - 1) * 100, "PCT"),
            "liquidated_return_pct": (((value - sell_fee) / initial - 1) * 100, "PCT"),
        }
        return {
            key: pv(
                None if reason else v,
                unit,
                "UNAVAILABLE" if reason else "SIMULATED",
                source,
                calculated,
                reason,
            )
            for key, (v, unit) in outputs.items()
        }

    def _outcomes(self, fills: list[Fill], horizon: int, bps: D) -> tuple[int, int, int, int]:
        """Matched buy fills, hypothetically sold at their t+H+1 open after both fees."""
        wins = known = unknown = blocked = 0
        for fill in fills:
            if fill.side != "BUY":
                continue
            exit_index = fill.session_index + horizon
            if exit_index >= len(self.sessions):
                unknown += 1
                continue
            bar = self.rows[fill.instrument].get(self.sessions[exit_index])
            available = self._features(exit_index - 1, fill.instrument)
            if bar is None or available is None:
                unknown += 1
                continue
            exit_price = bar.fill_price("SELL", bps)
            if exit_price is None or fill.quantity > min(bar.volume // 10, available.volume_cap):
                blocked += 1
                continue
            proceeds = exit_price * fill.quantity
            wins += int(proceeds - money(proceeds * FEE) > fill.gross + fill.fee)
            known += 1
        return wins, known, unknown, blocked

    def run(
        self,
        family: str,
        horizon: int = 10,
        *,
        offset: int = 0,
        cadence: int | None = None,
        bps: D = ZERO,
        settlement: int = 0,
    ) -> ModelExperiment:
        step = cadence or (20 if family == "LEGACY-G-APPROX" else horizon)

        def replay(name: str, excluded: str | None = None) -> Simulation:
            return self.simulate(
                name,
                horizon,
                offset=offset,
                cadence=step,
                bps=bps,
                settlement=settlement,
                excluded=excluded,
            )

        sim = replay(family)
        book = sim.book
        contribution = {
            s: flow + book.quantity[s] * sim.marks[s] for s, flow in book.cashflows.items()
        }
        top = min(contribution, key=lambda s: (-contribution[s], s)) if contribution else None
        excl = replay(family, top).net if top else sim.net
        baseline = "BL-EW-FULL" if family == "BL-EW-FULL" else "BL-EW-CHAL"
        ew = sim.net if family == baseline else replay(baseline).net
        liquidation_cost = sum(
            (money(n * sim.marks[s] * FEE) for s, n in book.quantity.items() if n), ZERO
        )
        average = sum(sim.equities, ZERO) / len(sim.equities)
        wins, known, unknown, blocked = self._outcomes(book.fills, horizon, bps)
        fingerprint = hashlib.sha256(
            repr((family, horizon, offset, step, bps, settlement, FEE, CAP, sim.initial)).encode()
        ).hexdigest()
        return ModelExperiment(
            experiment_id=f"{family}-{fingerprint[:12]}",
            family=family,
            horizon=horizon,
            scope="FULL_BVMT_RESEARCH" if family == "BL-EW-FULL" else "TUNIS_BOURSE_CHALLENGE",
            fold_count=sim.fold_count,
            net_return_pct=self._metric(sim.net),
            alpha_vs_cash_pct=self._metric(sim.net),
            alpha_vs_ew_pct=self._metric(sim.net - ew),
            max_drawdown_pct=self._metric(sim.drawdown),
            top1_excluded_return_pct=self._metric(excl),
            top1_excluded_instrument=top,
            turnover_pct=self._metric(sum((f.gross for f in book.fills), ZERO) * 50 / average),
            fees_paid_tnd=self._metric(sum((f.fee for f in book.fills), ZERO), "TND"),
            win_rate=self._metric(
                D(wins) / known if known else None,
                "RATIO",
                None if known else "No known executable entry and terminal-exit pairs",
            ),
            sample_count=known,
            run_mode=self.run_mode,
            provenance_status="SIMULATED",
            limitations=(
                f"{self.run_mode}: {'all bars lack published_at and pre-Nov-9 Challenge history; zero historical fills' if self.run_mode == 'STRICT_PIT' else 'exploratory diagnostics using EOD session close clock and retrospective Challenge membership'}",
                "Unadjusted EOD prices; executable depth and official benchmark unavailable",
                "Availability gated on archived observation and ingestion times; unavailable history stays cash",
                f"Known candidate observations: {sim.known_candidates}; unavailable: {sim.missing_candidates}; zero-fill orders: {book.unfilled_orders}",
                f"Matched buy labels with unknown exits: {unknown}; unexecutable exits: {blocked}",
            ),
            liquidated_return_pct=self._metric(
                (sim.equities[-1] - liquidation_cost) / sim.initial * 100 - 100
            ),
            active_utilization_pct=self._metric(
                sum(sim.utilizations, ZERO) / len(sim.utilizations)
            ),
            config_hash=fingerprint,
            data_hash=self.data_hash,
            source_hash=self.source_hash,
            trial_count=1 + int(top is not None) + int(family != baseline),
        )

    def phase_sensitivity(
        self,
        family: str,
        horizon: int = 10,
        *,
        cadence: int | None = None,
        bps: D = ZERO,
        settlement: int = 0,
    ) -> PhaseSensitivity:
        step = cadence or (20 if family == "LEGACY-G-APPROX" else horizon)
        values = [
            self.simulate(
                family, horizon, offset=i, cadence=step, bps=bps, settlement=settlement
            ).net
            for i in range(step)
        ]
        ordered = sorted(values)

        def quantile(p: D) -> D:
            index = p * (len(values) - 1)
            a = int(index)
            return ordered[a] + (ordered[min(a + 1, len(values) - 1)] - ordered[a]) * (index - a)

        q1, q3 = quantile(D(".25")), quantile(D(".75"))
        return PhaseSensitivity(
            tuple(self._metric(v) for v in values),
            self._metric(ordered[0]),
            self._metric(q1),
            self._metric(median(ordered)),
            self._metric(q3),
            self._metric(ordered[-1]),
            self._metric(q3 - q1),
        )

    def compare_exit_policies(
        self, instrument: str, horizon: int = 10, *, bps: D = ZERO
    ) -> dict[str, ExitComparison]:
        """Matched non-overlapping entry cohorts, one 5,000 TND sleeve per 50,000 TND account.

        Signals always trade at the following open. Fixed-horizon sales are preplanned
        for t+H+1. Unfilled residuals stay marked and incur a terminal sell-fee estimate.
        False exits compare early-sale proceeds against the matched terminal open.
        """
        if instrument not in self.rows or not 0 <= bps < 10000:
            raise ValueError("invalid instrument or slippage")
        periods = folds(len(self.sessions) - 1, horizon)
        return {p: self._compare_policy(instrument, p, periods, bps) for p in EXIT_POLICIES}

    def _compare_policy(
        self, name: str, policy: str, periods: tuple[Fold, ...], bps: D
    ) -> ExitComparison:
        compound = peak = D(1)
        drawdown = retained = peak_profit = missed = ZERO
        attempted = samples = false_exits = early_sells = offered = filled = 0
        for f in periods:
            signal = self._features(f.decision, name)
            terminal = self.rows[name].get(self.sessions[f.end + 1])
            if signal is None:
                continue
            attempted += 1
            book = Book(D("50000.000"))
            entry_bar = self.rows[name].get(self.sessions[f.entry])
            requested = int(5000 / signal.close)
            book.execute(
                Order(name, "BUY", requested, signal.volume_cap),
                entry_bar,
                f.entry,
                bps,
                0,
                entry_bar.volume if entry_bar else 0,
                book.cash,
            )
            if not book.fills:
                continue
            samples += 1
            entry = book.fills[0]
            mark = high = entry.price
            peak_equity = book.cash + entry.quantity * mark
            staged = liquidating = False
            sale = 0
            cap = 0
            for index in range(f.entry, f.end + 2):
                bar = self.rows[name].get(self.sessions[index])
                if sale > 0:
                    old_count = len(book.fills)
                    offered += sale
                    book.execute(
                        Order(name, "SELL", sale, cap),
                        bar,
                        index,
                        bps,
                        0,
                        bar.volume if bar else 0,
                        book.equity({name: mark}),
                    )
                    if len(book.fills) > old_count:
                        fill = book.fills[-1]
                        filled += fill.quantity
                        terminal_capacity = self._features(f.end, name)
                        if (
                            index <= f.end
                            and terminal is not None
                            and (terminal_price := terminal.fill_price("SELL", bps)) is not None
                            and terminal_capacity is not None
                            and fill.quantity
                            <= min(terminal_capacity.volume_cap, terminal.volume // 10)
                        ):
                            early_sells += fill.quantity
                            excess = max(ZERO, terminal_price - fill.price)
                            if excess > 0:
                                false_exits += fill.quantity
                            missed += excess * (1 - FEE) * fill.quantity
                if bar and bar.close > 0:
                    # Compare at terminal open (or last mark when the opening is missing).
                    if index <= f.end:
                        mark = bar.close
                    elif bar.tradable:
                        mark = bar.open
                equity = book.equity({name: mark})
                peak_equity = max(peak_equity, equity)
                level = compound * equity / D(50000)
                peak = max(peak, level)
                drawdown = max(drawdown, (peak - level) / peak * 100)
                sale = 0
                qty = book.quantity[name]
                if qty == 0 or index > f.end:
                    continue
                x = self._features(index, name)
                if x is None:
                    if liquidating or index == f.end:
                        sale, cap = qty, 0
                    continue
                high = max(high, x.close)
                trail = x.close / high - 1
                profit = x.close / entry.price - 1
                age = index - f.entry + 1
                falling = x.ret5 is not None and x.ret5 < 0
                rotate = False
                if policy == "opportunity_rotation":
                    ranked, _, _ = self._ranks("V2-D-MOM-RISK", index, None)
                    rotate = bool(ranked) and ranked[0] != name
                thresholds = {
                    "fixed_horizon": False,
                    "trend_deterioration": falling,
                    "trailing_profit_5pct": high > entry.price and trail <= D("-.05"),
                    "trailing_profit_8pct": high > entry.price and trail <= D("-.08"),
                    "volatility_adjusted_exit": x.vol is not None
                    and trail <= -max(D(".02"), 3 * x.vol),
                    "partial_profit_trim": False,
                    "time_stop": age * 2 >= f.end - f.decision and profit <= 0,
                    "opportunity_rotation": rotate,
                    "combined_risk_trend": falling and (profit < 0 or trail <= D("-.05")),
                }
                liquidating = liquidating or index == f.end or thresholds[policy]
                if liquidating:
                    sale = qty
                elif policy == "partial_profit_trim" and profit >= D(".05") and not staged:
                    sale = max(1, qty // 2)
                    staged = True
                cap = x.volume_cap
            final = book.equity({name: mark}) - money(book.quantity[name] * mark * FEE)
            compound *= final / 50000
            peak = max(peak, compound)
            drawdown = max(drawdown, (peak - compound) / peak * 100)
            retained += final - 50000
            peak_profit += max(ZERO, peak_equity - 50000)

        def ratio(num: D | int, den: D | int, reason: str) -> ProvenanceValue:
            return self._metric(
                D(num) * 100 / den if den else None, "PCT", reason if not den else None
            )

        return ExitComparison(
            self._metric(
                (compound - 1) * 100 if samples else None,
                "PCT",
                None if samples else "No executable matched entries",
            ),
            self._metric(
                drawdown if samples else None,
                "PCT",
                None if samples else "No executable matched entries",
            ),
            ratio(retained, peak_profit, "No positive peak profit"),
            ratio(false_exits, early_sells, "No evaluable early exit"),
            ratio(missed, samples * 50000, "No executable matched entries"),
            ratio(filled, offered, "No offered exit shares"),
            samples,
            attempted,
        )
