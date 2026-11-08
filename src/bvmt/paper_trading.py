"""Immutable decision evidence and forward-only hypothetical fills; no account access.

Daily-volume capacity at an opening price remains an ex-post research assumption,
not an executable opening-auction model. Missing marks retain the prior close.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    read_exchange_calendar,
    read_instrument_master,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.data import DailyBar, read_bars_csv, validate_bars
from bvmt.execution import BacktestConfig, MarketOrder, estimate_next_bar_fill
from bvmt.strategies import (
    STRATEGY_IDS,
    VERSION,
    StrategyLabConfig,
    _file_hash,
    _hash,
    _metrics,
    _money,
    _targets,
)

D = Decimal
DEFAULT_JOURNAL_PATH = Path(
    os.environ.get("BVMT_PAPER_JOURNAL_PATH", "data/portfolio/paper_trading_journal.json")
)
DATA_DIR = Path("data/processed/bvmt_official_2026")
DEFAULT_STRATEGY = "G_LIQUIDITY_FILTERED_MOMENTUM"
PAPER_CONFIG = StrategyLabConfig(
    execution=BacktestConfig(
        initial_cash_tnd=D("50000.000"), max_position_weight=D(".10"), carry_pending_orders=False
    )
)
_LOCK = threading.RLock()


@dataclass(frozen=True)
class PaperOrderRecord:
    order_id: str
    snapshot_id: str
    strategy_id: str
    instrument_id: str
    side: Literal["buy", "sell"]
    signal_session_date: str
    signal_close_price_tnd: str
    requested_shares: int
    filled_shares: int = 0
    remaining_shares: int = 0
    status: Literal[
        "PENDING_NEXT_SESSION", "FILLED", "PARTIALLY_FILLED", "EXPIRED", "BLOCKED_ZERO_VOLUME"
    ] = "PENDING_NEXT_SESSION"
    execution_session_date: str | None = None
    execution_price_tnd: str | None = None
    fee_tnd: str = "0.000"
    notes: str = "One next-session attempt; any residual expires, no carry-forward. Daily-volume capacity is ex-post hypothetical."


@dataclass(frozen=True)
class PaperSignalSnapshot:
    snapshot_id: str
    model_version: str
    config_hash: str
    code_sha256: str
    data_hash: str
    signal_timestamp: str
    market_data_session_date: str
    intended_orders: list[PaperOrderRecord]
    strategy_id: str = DEFAULT_STRATEGY


@dataclass
class PaperJournalState:
    journal_id: str = "paper-forward-v1"
    is_paper_only: Literal[True] = True
    autonomous_trading_enabled: Literal[False] = False
    strategy_id: str = DEFAULT_STRATEGY
    initial_cash_tnd: str = "50000.000"
    cash_tnd: str = "50000.000"
    holdings: dict[str, int] = field(default_factory=dict)
    average_cost_tnd: dict[str, str] = field(default_factory=dict)
    total_fees_tnd: str = "0.000"
    notional_traded_tnd: str = "0.000"
    total_equity_tnd: str = "50000.000"
    net_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    turnover_ratio: float = 0.0
    latest_settled_session: str | None = None
    signal_snapshots: list[PaperSignalSnapshot] = field(default_factory=list)
    orders: list[PaperOrderRecord] = field(default_factory=list)
    equity_history: list[dict[str, Any]] = field(default_factory=list)
    valuation_marks: dict[str, str] = field(default_factory=dict)
    benchmark_units: dict[str, str] = field(default_factory=dict)
    benchmark_cash_tnd: str = "50000.000"
    input_history_hash: str = ""
    baseline_instruments: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


@contextmanager
def _journal_lock(path: Path) -> Iterator[None]:
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = path.with_suffix(path.suffix + ".lock")
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ValueError(
                "Paper journal is busy; retry after the active writer finishes"
            ) from exc
        try:
            os.close(descriptor)
            yield
        finally:
            lock.unlink()


def _save(path: Path, state: PaperJournalState) -> None:
    payload = asdict(state)
    envelope = {"journal": payload, "integrity_sha256": _hash(payload)}
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(envelope, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load(path: Path) -> PaperJournalState:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(envelope, dict) or not isinstance(envelope.get("journal"), dict):
        raise ValueError("Invalid paper journal structure")
    payload = envelope["journal"]
    if envelope.get("integrity_sha256") != _hash(payload):
        raise ValueError("Paper journal integrity check failed")
    try:
        payload["orders"] = [PaperOrderRecord(**o) for o in payload["orders"]]
        payload["signal_snapshots"] = [
            PaperSignalSnapshot(
                **{**s, "intended_orders": [PaperOrderRecord(**o) for o in s["intended_orders"]]}
            )
            for s in payload["signal_snapshots"]
        ]
        state = PaperJournalState(**payload)
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid paper journal records") from exc
    if state.is_paper_only is not True or state.autonomous_trading_enabled is not False:
        raise ValueError("Paper journal safety flags are invalid")
    return state


def _input_hash(
    bars: Sequence[DailyBar],
    master: Sequence[InstrumentRecord],
    calendar: Sequence[ExchangeSession],
    cutoff: date,
) -> str:
    return _hash(
        {
            "bars": [
                asdict(b)
                for b in sorted(bars, key=lambda b: (b.session_date, b.instrument_id))
                if b.session_date <= cutoff
            ],
            "master": [asdict(m) for m in master],
            "calendar": [asdict(s) for s in calendar if s.session_date <= cutoff],
        }
    )


def _mark(state: PaperJournalState, session: date, today: dict[str, DailyBar]) -> None:
    state.valuation_marks.update({k: str(b.close) for k, b in today.items()})
    value = sum((D(q) * D(state.valuation_marks[k]) for k, q in state.holdings.items()), D(0))
    equity = _money(D(state.cash_tnd) + value)
    peak = max(
        [
            D(state.initial_cash_tnd),
            equity,
            *[D(p["total_equity_tnd"]) for p in state.equity_history],
        ]
    )
    drawdown = float((1 - equity / peak) * 100)
    state.total_equity_tnd = str(equity)
    state.net_return_pct = round(float((equity / D(state.initial_cash_tnd) - 1) * 100), 6)
    state.max_drawdown_pct = max(state.max_drawdown_pct, drawdown)
    state.turnover_ratio = float(D(state.notional_traded_tnd) / D(state.initial_cash_tnd))
    benchmark = D(state.benchmark_cash_tnd) + sum(
        (D(q) * D(state.valuation_marks[k]) for k, q in state.benchmark_units.items()), D(0)
    )
    state.equity_history.append(
        {
            "session_date": session.isoformat(),
            "total_equity_tnd": str(equity),
            "cash_tnd": state.cash_tnd,
            "holdings_value_tnd": str(_money(value)),
            "drawdown_pct": round(drawdown, 6),
            "cash_benchmark_equity_tnd": state.initial_cash_tnd,
            "equal_weight_benchmark_equity_tnd": str(_money(benchmark)),
            "benchmark_definition": "Frictionless fractional equal sleeves fixed at journal inception close; analytical only, no fees or volume limits.",
        }
    )
    state.latest_settled_session = session.isoformat()


def _settle(
    state: PaperJournalState,
    sessions: Sequence[ExchangeSession],
    by_date: dict[date, dict[str, DailyBar]],
    target: date,
) -> None:
    for session in sessions:
        day = session.session_date
        if day > target or (
            state.latest_settled_session and day.isoformat() <= state.latest_settled_session
        ):
            continue
        today = by_date.get(day, {})
        capacity = {k: int(D(b.volume_shares) * D(".10")) for k, b in today.items()}
        open_marks = {
            **{k: D(v) for k, v in state.valuation_marks.items()},
            **{k: b.open for k, b in today.items()},
        }
        snapshots = {s.snapshot_id: s for s in state.signal_snapshots}
        for index, order in sorted(
            enumerate(state.orders), key=lambda pair: (pair[1].side == "buy", pair[1].order_id)
        ):
            if (
                order.status != "PENDING_NEXT_SESSION"
                or order.signal_session_date >= day.isoformat()
            ):
                continue
            signal = snapshots[order.snapshot_id]
            next_day = next(
                s for s in sessions if s.session_date.isoformat() > order.signal_session_date
            )
            if next_day.session_date != day:
                raise ValueError("Pending order missed its immediately next session")
            # A newly imported historical session cannot become a fictitious forward fill.
            if session.opens_at is None or session.opens_at <= datetime.fromisoformat(
                signal.signal_timestamp
            ):
                state.orders[index] = replace(
                    order,
                    status="EXPIRED",
                    notes="Next session opened before the signal was recorded; no retrospective fill.",
                )
                continue
            bar = today.get(order.instrument_id)
            if bar is None:
                state.orders[index] = replace(
                    order, status="EXPIRED", notes="Missing next-session bar; residual expires."
                )
                continue
            if not bar.volume_shares or bar.status != "traded":
                state.orders[index] = replace(
                    order,
                    status="BLOCKED_ZERO_VOLUME",
                    notes="Next-session not tradable; residual expires.",
                )
                continue
            key = order.instrument_id
            owned = state.holdings.get(key, 0)
            cash = D(state.cash_tnd)
            quantity = (
                min(order.requested_shares, owned)
                if order.side == "sell"
                else order.requested_shares
            )
            if order.side == "buy":
                equity = cash + sum((D(q) * open_marks[k] for k, q in state.holdings.items()), D(0))
                price = bar.open * D("1.001")
                room = D(".10") * equity - D(owned) * price
                quantity = min(
                    quantity,
                    max(0, int(room / (price * D("1.0005")))),
                    max(0, int(cash / (price * D("1.005")))),
                )
            if quantity <= 0:
                state.orders[index] = replace(
                    order,
                    status="EXPIRED",
                    notes="Cash, holdings or concentration constraint; residual expires.",
                )
                continue
            fill = estimate_next_bar_fill(
                MarketOrder(
                    key, date.fromisoformat(order.signal_session_date), order.side, quantity
                ),
                bar,
                participation_rate=D(".10"),
                remaining_shared_capacity=capacity[key],
                slippage_bps=D(10),
                commission_bps=D(50),
            )
            if not fill.quantity or fill.price is None:
                state.orders[index] = replace(
                    order, status="EXPIRED", notes=fill.reason + "; residual expires."
                )
                continue
            amount = _money(D(fill.quantity) * fill.price)
            if order.side == "buy" and amount + fill.fee > cash:
                state.orders[index] = replace(
                    order,
                    status="EXPIRED",
                    notes="Rounded cash cost exceeds balance; residual expires.",
                )
                continue
            capacity[key] -= fill.quantity
            if order.side == "buy":
                old_basis = D(state.average_cost_tnd.get(key, "0")) * owned
                state.average_cost_tnd[key] = str(
                    (old_basis + amount + fill.fee) / D(owned + fill.quantity)
                )
                state.holdings[key] = owned + fill.quantity
                cash -= amount + fill.fee
            else:
                state.holdings[key] = owned - fill.quantity
                cash += amount - fill.fee
            state.cash_tnd = str(_money(cash))
            state.total_fees_tnd = str(_money(D(state.total_fees_tnd) + fill.fee))
            state.notional_traded_tnd = str(_money(D(state.notional_traded_tnd) + amount))
            state.orders[index] = replace(
                order,
                filled_shares=fill.quantity,
                remaining_shares=order.requested_shares - fill.quantity,
                status="FILLED" if fill.quantity == order.requested_shares else "PARTIALLY_FILLED",
                execution_session_date=day.isoformat(),
                execution_price_tnd=str(fill.price),
                fee_tnd=str(fill.fee),
            )
        _mark(state, day, today)


def _signal(
    state: PaperJournalState,
    target: date,
    bars: Sequence[DailyBar],
    master: Sequence[InstrumentRecord],
    calendar: Sequence[ExchangeSession],
) -> None:
    if any(b.session_date > target for b in bars):
        raise ValueError("Future bar accessed during signal calculation")
    sessions = [
        s
        for s in calendar
        if s.is_open
        and s.session_date <= target
        and s.session_date >= min(b.session_date for b in bars)
    ]
    by_date: dict[date, dict[str, DailyBar]] = {s.session_date: {} for s in sessions}
    for bar in bars:
        by_date[bar.session_date][bar.instrument_id] = bar
    metrics = _metrics([s.session_date for s in sessions], by_date, master, sessions[-1].closes_at)
    initial = [
        m.instrument_id for m in sorted(metrics, key=lambda m: (-m.turnover, m.instrument_id))[:10]
    ]
    if not state.signal_snapshots:
        state.baseline_instruments = initial
    initial = state.baseline_instruments
    targets = _targets(state.strategy_id, metrics, PAPER_CONFIG, initial)
    stamp = _now().isoformat()
    data_hash = _input_hash(bars, master, calendar, target)
    config_hash = _hash(asdict(PAPER_CONFIG))
    # Include both strategy and journal code, not only the HTTP adapter revision.
    code_hash = _hash(
        [
            _file_hash(Path(__file__)),
            _file_hash(Path(__file__).with_name("strategies.py")),
            _file_hash(Path(__file__).with_name("execution.py")),
        ]
    )
    snapshot_id = _hash(
        [state.strategy_id, stamp, target.isoformat(), config_hash, code_hash, data_hash]
    )
    orders = []
    keys = set(targets) | set(state.holdings)
    if state.strategy_id == STRATEGY_IDS[2] and state.signal_snapshots:
        keys = set()  # C buys once at inception and subsequently holds.
    for key in sorted(keys):
        price = D(state.valuation_marks[key])
        wanted = int(D(state.total_equity_tnd) * targets.get(key, D(0)) / price)
        delta = wanted - state.holdings.get(key, 0)
        if delta:
            orders.append(
                PaperOrderRecord(
                    _hash([snapshot_id, key]),
                    snapshot_id,
                    state.strategy_id,
                    key,
                    "buy" if delta > 0 else "sell",
                    target.isoformat(),
                    str(price),
                    abs(delta),
                    remaining_shares=abs(delta),
                )
            )
    orders.sort(key=lambda o: (o.side == "buy", o.instrument_id))
    state.signal_snapshots.append(
        PaperSignalSnapshot(
            snapshot_id,
            VERSION,
            config_hash,
            code_hash,
            data_hash,
            stamp,
            target.isoformat(),
            orders.copy(),
            state.strategy_id,
        )
    )
    state.orders.extend(orders)


def _advance(
    path: Path,
    bars_path: Path,
    instruments_path: Path,
    calendar_path: Path,
    strategy_id: str,
    as_of_session: date | None,
    record: bool,
) -> PaperJournalState:
    if strategy_id not in STRATEGY_IDS:
        raise ValueError("Unknown paper strategy")
    bars = validate_bars(read_bars_csv(bars_path))
    master = validate_instrument_master(read_instrument_master(instruments_path))
    calendar = validate_exchange_calendar(read_exchange_calendar(calendar_path))
    now = _now()
    # Only completed calendar sessions can be used, even if a future row is supplied.
    completed = [
        s
        for s in calendar
        if s.is_open
        and s.closes_at is not None
        and s.closes_at <= now
        and any(b.session_date == s.session_date for b in bars)
    ]
    if not completed:
        raise ValueError("No completed verified market session available")
    latest = max(s.session_date for s in completed)
    target = as_of_session or latest
    if target != latest:
        raise ValueError(
            "Forward signals must use the latest completed observed session; historical or future recording is forbidden"
        )
    prefix = [b for b in bars if b.session_date <= target]
    if any(
        b.ingested_at > now or (b.published_at is not None and b.published_at > now) for b in prefix
    ):
        raise ValueError("Market inputs were not available at the recording timestamp")
    open_sessions = [s for s in calendar if s.is_open and s.session_date <= target]
    by_date: dict[date, dict[str, DailyBar]] = {s.session_date: {} for s in open_sessions}
    for bar in prefix:
        if bar.session_date not in by_date:
            raise ValueError("Bar outside verified open-session calendar")
        by_date[bar.session_date][bar.instrument_id] = bar
    if path.exists():
        state = _load(path)
        if record and state.strategy_id != strategy_id:
            raise ValueError("Cannot change the strategy of an existing paper journal")
        if state.latest_settled_session is None:
            raise ValueError("Existing paper journal lacks inception session")
        settled = date.fromisoformat(state.latest_settled_session)
        if target < settled or state.input_history_hash != _input_hash(
            prefix, master, calendar, settled
        ):
            raise ValueError(
                "Historical inputs revised or removed; immutable journal cannot be replayed"
            )
        if any(datetime.fromisoformat(s.signal_timestamp) > now for s in state.signal_snapshots):
            raise ValueError("Clock moved backward")
        _settle(state, open_sessions, by_date, target)
    else:
        state = PaperJournalState(strategy_id=strategy_id)
        state.valuation_marks = {k: str(b.close) for k, b in by_date[target].items()}
        eligible = [
            k for k, b in by_date[target].items() if b.status == "traded" and b.volume_shares > 0
        ]
        if eligible:
            sleeve = D(state.initial_cash_tnd) / len(eligible)
            state.benchmark_units = {k: str(sleeve / D(state.valuation_marks[k])) for k in eligible}
            state.benchmark_cash_tnd = "0.000"
        _mark(state, target, by_date[target])
        record = True
    if record and not any(
        s.market_data_session_date == target.isoformat() for s in state.signal_snapshots
    ):
        _signal(state, target, prefix, master, open_sessions)
    state.input_history_hash = _input_hash(prefix, master, calendar, target)
    _save(path, state)
    return state


def load_or_init_paper_journal(
    journal_path: Path = DEFAULT_JOURNAL_PATH,
    *,
    bars_path: Path = DATA_DIR / "daily_bars.canonical.csv",
    instruments_path: Path = DATA_DIR / "instrument_master.csv",
    calendar_path: Path = DATA_DIR / "exchange_calendar.csv",
    strategy_id: str = DEFAULT_STRATEGY,
) -> PaperJournalState:
    """Initialize at latest completed close; subsequent reads settle forward only."""
    with _journal_lock(journal_path):
        return _advance(
            journal_path, bars_path, instruments_path, calendar_path, strategy_id, None, False
        )


def record_forward_paper_signal(
    journal_path: Path = DEFAULT_JOURNAL_PATH,
    *,
    as_of_session: date | None = None,
    strategy_id: str = DEFAULT_STRATEGY,
    bars_path: Path = DATA_DIR / "daily_bars.canonical.csv",
    instruments_path: Path = DATA_DIR / "instrument_master.csv",
    calendar_path: Path = DATA_DIR / "exchange_calendar.csv",
) -> PaperJournalState:
    """Append one immutable decision per session; retries are idempotent."""
    with _journal_lock(journal_path):
        return _advance(
            journal_path,
            bars_path,
            instruments_path,
            calendar_path,
            strategy_id,
            as_of_session,
            True,
        )
