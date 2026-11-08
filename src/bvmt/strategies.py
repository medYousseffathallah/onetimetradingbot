"""Offline comparative research, raw-price simulations and provenance diagnostics.

No fitted models or tuned parameters. Archived bars without historical availability
metadata are exploratory observations, never certified point-in-time OOS evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from dataclasses import field as dataclass_field
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import median, stdev
from typing import Any, Literal
from zoneinfo import ZoneInfo

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    read_exchange_calendar,
    read_instrument_master,
    resolve_instrument_on_date,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.data import DailyBar, audit_official_ndjson_archive, read_bars_csv, validate_bars
from bvmt.execution import BacktestConfig, MarketOrder, estimate_next_bar_fill

D = Decimal
VERSION = "1.0.0"
STRATEGY_IDS = (
    "A_CASH_ONLY",
    "B_EQUAL_WEIGHT_ELIGIBLE",
    "C_BUY_AND_HOLD_BENCHMARK",
    "D_MOMENTUM_20S",
    "E_MOMENTUM_60S",
    "F_RELATIVE_STRENGTH_20S",
    "G_LIQUIDITY_FILTERED_MOMENTUM",
    "H_DOWNSIDE_RISK_TREND_MULTIFACTOR",
    "I_REGIME_FILTERED_QUALITY_MOMENTUM",
)
FORMULAS = (
    "100% cash; no orders",
    "Top 10 initial eligible instruments by trailing turnover/id; equal capped sleeves; periodic rebalance",
    "Same initial equal sleeves as B; buy once and hold",
    "Top K descending mom_20 = close / close[-20] - 1",
    "Top K descending mom_60 = close / close[-60] - 1",
    "Top K rs_20 = mom_20 - eligible mean(mom_20), requiring rs_20 > 0",
    "Top K 0.5*mom_20/vol_20 + 0.5*mom_60/vol_20; frequency >= .60, median turnover >= 5000, mom_20 >= .015",
    "G score - downside_60/vol_20 - drawdown_60/vol_20 + consistency_60 + frequency_20*log1p(turnover_20/5000)",
    "H; if bench_20 < 0, half sleeves, rs_20 >= .02 and drawdown_60 <= .10; event overlay disabled",
)
LIMITATIONS = [
    "Research-conservative hypothetical raw price returns; not verified competition rules.",
    "Pre-2026 daily bars and corporate-action adjustment tables absent from public NDJSON; dividends/splits/rights not modeled.",
    "Historical membership and delistings are incomplete; observed master is not independently verified point-in-time membership.",
    "Missing publication/first-availability timestamps prevent certified historical OOS claims; retrospective ingestion is not historical availability.",
    "Missing marks retain last observed close for valuation only; no missing return is inserted into features.",
    "Immediate settlement, integer shares, half-up .001 TND fees; no exchange tick/auction/queue model.",
    "Orders attempt next open once; residuals expire; rebalance replaces targets; terminal liquidation is a fee-only estimate, not an executable fill.",
    "10% purchase concentration cap; subsequent market drift is measured and can breach the cap; no forced same-close sells.",
    "Fixed hypotheses registered together after data observation; no untouched holdout; no statistical promotion claim.",
]


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _number(value: Decimal | float) -> float:
    return round(float(value), 6)


def _money(value: Decimal) -> Decimal:
    return value.quantize(D(".001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class StrategyLabConfig:
    execution: BacktestConfig = BacktestConfig(
        max_position_weight=D(".10"), carry_pending_orders=False
    )
    warmup_sessions: int = 61
    rebalance_every_sessions: int = 19
    top_k: int = 5
    target_weight: Decimal = D(".085")

    def __post_init__(self) -> None:
        if (
            any(
                type(v) is not int
                for v in (self.warmup_sessions, self.rebalance_every_sessions, self.top_k)
            )
            or self.warmup_sessions < 61
            or self.rebalance_every_sessions < 1
            or self.top_k < 1
        ):
            raise ValueError("Require warmup >= 61 and positive rebalance/top_k")
        if (
            not self.target_weight.is_finite()
            or not 0 < self.target_weight <= self.execution.max_position_weight <= D(".10")
        ):
            raise ValueError("Target and purchase cap must be in (0, .10]")
        if self.execution.fill_price_mode != "next_open":
            raise ValueError("Strategy lab requires next_open execution")
        if (
            self.execution.carry_pending_orders
            or self.execution.max_turnover_participation is not None
        ):
            raise ValueError(
                "Strategy lab uses next-open attempt/expiry and share-volume capacity only"
            )


@dataclass(frozen=True)
class StrategyEvaluationReport:
    strategy_id: str
    name: str
    version: str
    family: Literal["baseline", "enhanced"]
    implementation_status: Literal["implemented"]
    sample_Classification: Literal["exploratory"]
    formula_summary: str
    assumptions: dict[str, Any]
    failure_modes: list[str]
    start_session: str
    end_session: str
    session_count: int
    net_return_pct: float
    liquidated_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    max_drawdown_pct: float
    turnover_ratio: float
    total_fees_tnd: float
    trade_count: int
    order_count: int
    hit_rate_pct: float
    win_loss_Init_summary: dict[str, Any]
    avg_cash_utilization_pct: float
    max_single_stock_weight_pct: float
    walk_forward: dict[str, Any]
    fee_and_liquidity_sensitivity: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    is_statistically_conclusive: Literal[False]
    promotion_status: Literal["research_only_requires_human_approval"]
    config_hash: str
    experiment_id: str
    diagnostics: dict[str, Any]
    risk_normalized_metrics: dict[str, Any] = dataclass_field(default_factory=dict)


def audit_historical_coverage_and_blockers(
    archive_path: Path,
    processed_dir: Path,
) -> dict[str, Any]:
    """Recompute local evidence, preserve source claims and distinguish unknowns.

    Offline: legacy download failures are attributed to the saved manifest, not
    reasserted as a new network observation. No file mtimes become retrieval times.
    """
    manifest_path = processed_dir / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    provenance_path = processed_dir / "provenance.json"
    provenance = (
        json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.exists() else {}
    )
    archive: dict[str, Any] = (
        audit_official_ndjson_archive(archive_path)
        if archive_path.exists()
        else {"years": {}, "source_sha256": None}
    )
    bars_path = processed_dir / "daily_bars.canonical.csv"
    bars = read_bars_csv(bars_path) if bars_path.exists() else []
    master_path = processed_dir / "instrument_master.csv"
    master = read_instrument_master(master_path) if master_path.exists() else []
    saved_provenance = manifest.get("provenance", {})
    coverage: dict[str, Any] = {}
    for year in range(2020, 2027):
        stats = archive["years"].get(str(year), {})
        canonical = [b for b in bars if b.session_date.year == year]
        coverage[str(year)] = {
            "archive": stats,
            "canonical_sessions": len({b.session_date for b in canonical}),
            "instrument_count": len({b.instrument_id for b in canonical}),
            "daily_ohlcv_available": bool(canonical),
            "status": "observed_daily_not_independently_complete"
            if canonical
            else "monthly_summaries_not_daily"
            if stats
            else "absent",
        }
    actual_hash = _file_hash(bars_path) if bars_path.exists() else None
    return {
        "coverage_2020_2026": coverage,
        "source_url": saved_provenance.get("source_url", provenance.get("source_url")),
        "retrieved_at": saved_provenance.get("source_retrieved_at"),
        "processed_at": saved_provenance.get("processed_at", provenance.get("retrieved_at")),
        "saved_provenance": provenance,
        "manifest_provenance": saved_provenance,
        "archive_sha256": archive["source_sha256"],
        "canonical_sha256": actual_hash,
        "manifest_canonical_sha256": manifest.get("canonical_sha256"),
        "canonical_checksum_matches": actual_hash == manifest.get("canonical_sha256")
        if actual_hash and manifest.get("canonical_sha256")
        else None,
        "instrument_count": len({b.instrument_id for b in bars}),
        "observed_delistings": sorted({r.instrument_id for r in master if r.listed_to}),
        "delisting_history_complete": False,
        "suspended_bar_count": sum(b.status == "suspended" for b in bars),
        "suspension_history_complete": False,
        "corporate_actions_available": False,
        "legacy_zip_access": {
            "status": "saved_report_only_not_refetched",
            "reported_response_bytes": 0
            if saved_provenance.get("older_history_access_user_reported")
            else None,
            "evidence": saved_provenance.get("older_history_access_user_reported"),
        },
        "missing_publication_timestamps": sum(b.published_at is None for b in bars),
        "blockers": LIMITATIONS[:4]
        + [
            "2020–2025 local NDJSON contains monthly summaries, not usable daily OHLCV; no authorized older daily archive is present in data/raw. Legacy ZIP zero-byte failures are saved user reports, not newly verified HTTP responses. Request official daily history.",
            "No verified dated dividend, split or rights adjustment table is locally available; raw closes cannot establish total returns. Request official corporate-action records.",
        ],
    }


@dataclass(frozen=True)
class _Metrics:
    instrument_id: str
    mom20: float
    mom60: float
    vol20: float
    frequency: float
    turnover: float
    downside: float
    drawdown: float
    consistency: float


def _metrics(
    history: Sequence[date],
    by_date: dict[date, dict[str, DailyBar]],
    master: Sequence[InstrumentRecord],
    cutoff: datetime | None = None,
) -> list[_Metrics]:
    if len(history) < 61:
        return []
    days = history[-61:]
    decision_cutoff = cutoff or datetime.combine(days[-1], time.max, ZoneInfo("Africa/Tunis"))
    result = []
    for key in sorted(by_date[days[-1]]):
        record = resolve_instrument_on_date(list(master), key, days[-1])
        if (
            record is None
            or not record.is_competition_eligible
            or record.market_segment
            not in {"principal", "principal_continu", "principal_fixing", "Continu_Principal"}
            or record.listed_from > days[-1]
            or (record.listed_to is not None and record.listed_to < days[-1])
        ):
            continue
        window = [by_date[d].get(key) for d in days]
        if any(b is None or b.status == "suspended" for b in window):
            continue
        valid = [b for b in window if b is not None]
        if any(b.published_at is not None and b.published_at > decision_cutoff for b in valid):
            continue
        if any(valid[i].status != "traded" or valid[i].volume_shares <= 0 for i in (0, 40, 60)):
            continue
        traded = [float(b.close) for b in valid if b.status == "traded" and b.volume_shares > 0]
        short = [
            float(b.close) for b in valid[-21:] if b.status == "traded" and b.volume_shares > 0
        ]
        steps = [b / a - 1 for a, b in zip(traded, traded[1:], strict=False)]
        short_steps = [b / a - 1 for a, b in zip(short, short[1:], strict=False)]
        peak = traded[0]
        dd = 0.0
        for price in traded:
            peak = max(peak, price)
            dd = max(dd, 1 - price / peak)
        result.append(
            _Metrics(
                key,
                float(valid[-1].close / valid[-21].close - 1),
                float(valid[-1].close / valid[0].close - 1),
                max(1e-6, stdev(short_steps) if len(short_steps) > 1 else 0),
                sum(b.status == "traded" and b.volume_shares > 0 for b in valid[-20:]) / 20,
                float(median(b.turnover_tnd for b in valid[-20:])),
                math.sqrt(sum(min(r, 0) ** 2 for r in steps) / len(steps)),
                dd,
                sum(r > 0 for r in steps) / len(steps),
            )
        )
    return result


def _targets(
    strategy: str, metrics: Sequence[_Metrics], config: StrategyLabConfig, initial: Sequence[str]
) -> dict[str, Decimal]:
    if strategy == STRATEGY_IDS[0]:
        return {}
    if strategy in STRATEGY_IDS[1:3]:
        return {
            key: min(config.execution.max_position_weight, D(1) / D(len(initial)))
            for key in initial
        }
    bench = sum(m.mom20 for m in metrics) / len(metrics) if metrics else 0
    candidates: list[tuple[float, str]] = []
    for m in metrics:
        rs = m.mom20 - bench
        score = m.mom20
        if strategy == STRATEGY_IDS[4]:
            score = m.mom60
        elif strategy == STRATEGY_IDS[5]:
            if rs <= 0:
                continue
            score = rs
        elif strategy in STRATEGY_IDS[6:]:
            if m.frequency < 0.60 or m.turnover < 5000 or m.mom20 < 0.015:
                continue
            score = 0.5 * (m.mom20 / m.vol20) + 0.5 * (m.mom60 / m.vol20)
            if strategy in STRATEGY_IDS[7:]:
                score += (
                    -m.downside / m.vol20
                    - m.drawdown / m.vol20
                    + m.consistency
                    + m.frequency * math.log1p(m.turnover / 5000)
                )
            if strategy == STRATEGY_IDS[8] and bench < 0 and (rs < 0.02 or m.drawdown > 0.10):
                continue
        candidates.append((score, m.instrument_id))
    weight = config.target_weight
    if strategy == STRATEGY_IDS[8] and bench < 0:
        weight /= 2
    return {
        key: weight for _, key in sorted(candidates, key=lambda x: (-x[0], x[1]))[: config.top_k]
    }


@dataclass
class _Run:
    summary: dict[str, Any]
    curve: list[dict[str, Any]]
    fills: list[dict[str, Any]]


def _simulate(
    strategy: str,
    sessions: Sequence[date],
    by_date: dict[date, dict[str, DailyBar]],
    features: dict[date, list[_Metrics]],
    config: StrategyLabConfig,
    *,
    decision_start: int,
    continuous_trim: bool = False,
) -> _Run:
    """Sequential cash/share ledger. Orders generated at close execute next open once."""
    cash = config.execution.initial_cash_tnd
    initial_cash = cash
    holdings: dict[str, int] = {}
    marks: dict[str, Decimal] = {}
    costs: dict[str, Decimal] = {}
    evaluated: list[Decimal] = []
    pending: list[MarketOrder] = []
    fills: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    fees = D(0)
    notional = D(0)
    peak = cash
    max_weight = D(0)
    utilization = D(0)
    orders = 0
    drift_sessions = 0
    stale_marks = 0
    initial: list[str] | None = None
    for index, session in enumerate(sessions):
        today = by_date[session]
        # Opens are available for execution valuation, never used by previous decisions.
        open_marks = {**marks, **{k: b.open for k, b in today.items()}}
        capacity = {
            k: int(D(b.volume_shares) * config.execution.max_volume_participation)
            for k, b in today.items()
        }
        for order in pending:
            b = today.get(order.instrument_id)
            if b is None:
                continue
            key = order.instrument_id
            owned = holdings.get(key, 0)
            quantity = order.quantity
            if order.side == "sell":
                quantity = min(quantity, owned)
            else:
                equity = cash + sum((D(q) * open_marks[k] for k, q in holdings.items()), D(0))
                price = b.open * (1 + config.execution.slippage_bps / D(10000))
                rate = config.execution.commission_bps / D(10000)
                room = config.execution.max_position_weight * equity - D(owned) * price
                quantity = min(
                    quantity,
                    max(0, int(room / (price * (1 + config.execution.max_position_weight * rate)))),
                    max(0, int(cash / (price * (1 + rate)))),
                )
            if quantity <= 0:
                continue
            fill = estimate_next_bar_fill(
                replace(order, quantity=quantity),
                b,
                participation_rate=config.execution.max_volume_participation,
                remaining_shared_capacity=capacity[key],
                slippage_bps=config.execution.slippage_bps,
                commission_bps=config.execution.commission_bps,
            )
            if not fill.quantity or fill.price is None:
                continue
            amount = _money(D(fill.quantity) * fill.price)
            if order.side == "buy" and amount + fill.fee > cash:
                continue
            capacity[key] -= fill.quantity
            fees += fill.fee
            notional += amount
            if order.side == "buy":
                cash -= amount + fill.fee
                holdings[key] = owned + fill.quantity
                costs[key] = costs.get(key, D(0)) + amount + fill.fee
            else:
                basis = costs[key] * D(fill.quantity) / D(owned)
                evaluated.append((amount - fill.fee) / basis - 1)
                costs[key] -= basis
                cash += amount - fill.fee
                holdings[key] = owned - fill.quantity
            fills.append(
                {
                    "instrument_id": key,
                    "decision_session": order.decision_session.isoformat(),
                    "session_date": session.isoformat(),
                    "side": order.side,
                    "quantity": fill.quantity,
                    "price_tnd": str(fill.price),
                    "fee_tnd": str(fill.fee),
                }
            )
        marks.update({k: b.close for k, b in today.items()})
        stale_marks += sum(
            q > 0 and (k not in today or today[k].status != "traded") for k, q in holdings.items()
        )
        value = sum((D(q) * marks[k] for k, q in holdings.items()), D(0))
        equity = cash + value
        weight = max((D(q) * marks[k] / equity for k, q in holdings.items()), default=D(0))
        max_weight = max(max_weight, weight)
        drift_sessions += weight > config.execution.max_position_weight
        utilization += value / equity
        peak = max(peak, equity)
        curve.append(
            {
                "session_date": session.isoformat(),
                "total_equity_tnd": _number(equity),
                "cash_tnd": _number(cash),
                "holdings_value_tnd": _number(value),
                "drawdown_pct": _number((1 - equity / peak) * 100),
            }
        )
        pending = []
        if continuous_trim and index >= decision_start and index < len(sessions) - 1:
            for key, quantity in holdings.items():
                if D(quantity) * marks[key] > config.execution.max_position_weight * equity:
                    wanted = int(
                        equity * min(D(".085"), config.execution.max_position_weight) / marks[key]
                    )
                    pending.append(MarketOrder(key, session, "sell", quantity - wanted))
            orders += len(pending)
        if (
            index >= decision_start
            and (index - decision_start) % config.rebalance_every_sessions == 0
            and index < len(sessions) - 1
        ):
            metrics = features.get(session, [])
            if initial is None:
                initial = [
                    m.instrument_id
                    for m in sorted(metrics, key=lambda m: (-m.turnover, m.instrument_id))[:10]
                ]
            if strategy == STRATEGY_IDS[2] and index != decision_start:
                continue
            targets = _targets(strategy, metrics, config, initial)
            # A breached holding is trimmed toward 8.5%, including on rebalance dates.
            for order in pending:
                targets[order.instrument_id] = min(
                    targets.get(order.instrument_id, D(0)), D(".085")
                )
            orders -= len(pending)
            pending = []
            for key in sorted(set(holdings) | set(targets)):
                if key not in marks:
                    continue
                wanted = int(equity * targets.get(key, D(0)) / marks[key])
                delta = wanted - holdings.get(key, 0)
                if delta:
                    pending.append(
                        MarketOrder(key, session, "buy" if delta > 0 else "sell", abs(delta))
                    )
            pending.sort(key=lambda o: (o.side == "buy", o.instrument_id))
            orders += len(pending)
    fee_rate = config.execution.commission_bps / D(10000)
    for key, q in holdings.items():
        if q and costs[key] > 0:
            evaluated.append((D(q) * marks[key] * (1 - fee_rate)) / costs[key] - 1)
    final = D(str(curve[-1]["total_equity_tnd"]))
    terminal_fee = _money(value * fee_rate)
    summary = {
        "net_return_pct": _number((final / initial_cash - 1) * 100),
        "liquidated_return_pct": _number(((final - terminal_fee) / initial_cash - 1) * 100),
        "max_drawdown_pct": max(p["drawdown_pct"] for p in curve),
        "turnover_ratio": _number(notional / initial_cash),
        "total_fees_tnd": _number(fees),
        "trade_count": len(fills),
        "order_count": orders,
        "hit_rate_pct": _number(100 * sum(r > 0 for r in evaluated) / len(evaluated))
        if evaluated
        else 0.0,
        "win_loss_Init_summary": {
            "winning_positions": sum(r > 0 for r in evaluated),
            "losing_positions": sum(r < 0 for r in evaluated),
            "flat_positions": sum(r == 0 for r in evaluated),
            "best_position_return_pct": _number(max(evaluated) * 100) if evaluated else None,
            "worst_position_return_pct": _number(min(evaluated) * 100) if evaluated else None,
            "definition": "Average-cost sold slices plus remaining terminal sleeves after exit fee; partial exits count as evaluated slices.",
        },
        "avg_cash_utilization_pct": _number(utilization / D(len(sessions)) * 100),
        "max_single_stock_weight_pct": _number(max_weight * 100),
        "diagnostics": {
            "concentration_cap_compliant": max_weight <= config.execution.max_position_weight,
            "market_drift_breach_sessions": drift_sessions,
            "stale_holding_marks": stale_marks,
            "terminal_exit_fee_tnd": _number(terminal_fee),
            "terminal_marks": {k: str(v) for k, v in marks.items()},
            "fills": fills,
        },
    }
    return _Run(summary, curve, fills)


DEFAULT_LAB_CONFIG = StrategyLabConfig()


AUDIT_FINDINGS = [
    "Marked C excess omitted liquidated and B comparisons; cash exposures differ materially.",
    "Nine hypotheses selected on one 194-session 2026 sample induce specification-selection bias.",
    "D and F rankings are identical when five names exceed the mean: constant translation preserves order.",
    "G's approximately 30% active utilization explains much of its low drawdown; SOTETEL dependency is material but not over 100% of profit in the 100000 TND registry.",
    "Purchase-only 10% checks permit inter-rebalance concentration drift above 14%.",
    "Traded bars include 32.90% open=close, 25.11% flat OHLC and 21.37% volume below 500.",
    "Full-day volume used for next-open capacity is intraday lookahead; opening-auction volume is unknown.",
    "50 bps commissions are rounded to .001 TND; terminal liquidation estimates fees only.",
    "Missing dividends and corporate actions distort raw momentum and buy-and-hold total returns.",
    "Seven 61/19 folds test chronological stability, not untouched structural model selection.",
]


def _active_utilization(run: _Run, start: int) -> float:
    points = run.curve[start:]
    return (
        sum(p["holdings_value_tnd"] / p["total_equity_tnd"] * 100 for p in points) / len(points)
        if points
        else 0.0
    )


def _active_factors(run: _Run, start: int) -> list[float]:
    # Include the return into the initial active mark; it is flat in the base run.
    return [
        p["total_equity_tnd"]
        / (run.curve[i - 1]["total_equity_tnd"] if i else p["total_equity_tnd"])
        for i, p in enumerate(run.curve)
        if i >= start
    ]


def _bootstrap_interval(factors: Sequence[float]) -> dict[str, Any]:
    rng = random.Random(42)
    n = len(factors)
    block = min(5, n)
    returns = []
    for _ in range(500):
        sample: list[float] = []
        while len(sample) < n:
            offset = rng.randrange(n - block + 1)
            sample.extend(factors[offset : offset + block])
        returns.append((math.prod(sample[:n]) - 1) * 100)
    returns.sort()

    def quantile(q: float) -> float:
        index = q * (len(returns) - 1)
        lower = int(index)
        return _number(
            returns[lower] + (returns[min(lower + 1, 499)] - returns[lower]) * (index - lower)
        )

    return {
        "lower_pct": quantile(0.025),
        "upper_pct": quantile(0.975),
        "resamples": 500,
        "block_size": 5,
        "method": "deterministic_moving_block_bootstrap_active_sessions",
    }


def _winner_pnl(run: _Run) -> tuple[str | None, float]:
    """Attribute net marked P&L including both realized cash flows and open shares."""
    shares: dict[str, int] = {}
    pnl: dict[str, Decimal] = {}
    for fill in run.fills:
        key = fill["instrument_id"]
        sign = 1 if fill["side"] == "sell" else -1
        shares[key] = shares.get(key, 0) - sign * fill["quantity"]
        pnl[key] = (
            pnl.get(key, D(0))
            + sign * _money(D(fill["quantity"]) * D(fill["price_tnd"]))
            - D(fill["fee_tnd"])
        )
    # _simulate includes final marks for exact open-position attribution.
    for key, quantity in shares.items():
        pnl[key] += D(quantity) * D(run.summary["diagnostics"]["terminal_marks"][key])
    winner = min(pnl, key=lambda key: (-pnl[key], key)) if pnl else None
    return winner, _number(pnl[winner]) if winner else 0.0


def _risk_metrics(
    strategy: str,
    run: _Run,
    base_runs: dict[str, _Run],
    sessions: Sequence[date],
    by_date: dict[date, dict[str, DailyBar]],
    features: dict[date, list[_Metrics]],
    master: Sequence[InstrumentRecord],
    cutoffs: dict[date, datetime | None],
    config: StrategyLabConfig,
) -> dict[str, Any]:
    start = config.warmup_sessions - 1
    util = _number(_active_utilization(run, start))
    factors = _active_factors(run, start)
    volatility = (
        _number(stdev([f - 1 for f in factors]) * math.sqrt(250) * 100) if len(factors) > 1 else 0.0
    )
    b, c = base_runs[STRATEGY_IDS[1]], base_runs[STRATEGY_IDS[2]]
    b_util = _number(_active_utilization(b, start))
    matched = _number(b.summary["net_return_pct"] * util / b_util) if b_util else 0.0
    equal = _simulate(
        strategy,
        sessions,
        by_date,
        features,
        replace(
            config,
            top_k=10,
            target_weight=D(".095"),
            execution=replace(config.execution, max_position_weight=D(".10")),
        ),
        decision_start=start,
    )
    trim = _simulate(
        strategy, sessions, by_date, features, config, decision_start=start, continuous_trim=True
    )
    winner, pnl = _winner_pnl(run)
    if winner:
        excluded = {
            day: {k: v for k, v in today.items() if k != winner} for day, today in by_date.items()
        }
        excluded_features = {
            day: _metrics(sessions[: i + 1], excluded, master, cutoffs[day])
            for i, day in enumerate(sessions)
            if i >= start
        }
        ex_return = _simulate(
            strategy, sessions, excluded, excluded_features, config, decision_start=start
        ).summary["net_return_pct"]
    else:
        ex_return = run.summary["net_return_pct"]
    result: dict[str, Any] = {
        "active_session_count": len(factors),
        "active_cash_utilization_pct": _number(util),
        "realized_annualized_volatility_pct": _number(volatility),
        "return_to_volatility_ratio": _number(run.summary["net_return_pct"] / volatility)
        if volatility
        else 0.0,
        "cash_matched_benchmark_b_return_pct": _number(matched),
        "excess_vs_cash_matched_b_pct": _number(run.summary["net_return_pct"] - matched),
        "equal_budget_10slot_net_return_pct": equal.summary["net_return_pct"],
        "equal_budget_10slot_liquidated_return_pct": equal.summary["liquidated_return_pct"],
        "equal_budget_10slot_max_drawdown_pct": equal.summary["max_drawdown_pct"],
        "equal_budget_10slot_active_utilization_pct": _number(_active_utilization(equal, start)),
        "continuous_concentration_trim_net_return_pct": trim.summary["net_return_pct"],
        "continuous_concentration_trim_max_weight_pct": trim.summary["max_single_stock_weight_pct"],
        "top_winner_instrument_id": winner,
        "top_winner_net_pnl_tnd": pnl,
        "ex_top_winner_net_return_pct": ex_return,
        "bootstrap_return_ci_95": _bootstrap_interval(factors),
    }
    for label, source in (
        ("return", "net_return_pct"),
        ("liquidated_return", "liquidated_return_pct"),
        ("max_drawdown", "max_drawdown_pct"),
    ):
        result[f"exposure_normalized_{label}_pct"] = (
            _number(run.summary[source] / (util / 100)) if util else 0.0
        )
    for label, bench in (("b", b), ("c", c)):
        for convention, field in (
            ("marked", "net_return_pct"),
            ("liquidated", "liquidated_return_pct"),
        ):
            result[f"excess_vs_{label}_{convention}_pct"] = _number(
                run.summary[field] - bench.summary[field]
            )
    subperiods = {}
    for name, begin, end in (
        ("h1_2026_spring_rally", "2026-03-30", "2026-06-30"),
        ("h2_2026_consolidation", "2026-06-30", "2026-11-06"),
        ("oct_nov_competition_window", "2026-10-01", "2026-11-06"),
    ):
        points = [p for p in run.curve[start:] if begin <= p["session_date"] <= end]
        subperiods[name] = {
            "start_session": points[0]["session_date"] if points else None,
            "end_session": points[-1]["session_date"] if points else None,
            "return_pct": _number(
                (points[-1]["total_equity_tnd"] / points[0]["total_equity_tnd"] - 1) * 100
            )
            if points
            else 0.0,
        }
    result["subperiods"] = subperiods
    return result


def evaluate_strategy_suite(
    bars: Sequence[DailyBar],
    instruments: Sequence[InstrumentRecord],
    calendar: Sequence[ExchangeSession],
    *,
    config: StrategyLabConfig = DEFAULT_LAB_CONFIG,
) -> dict[str, Any]:
    """Evaluate all nine frozen hypotheses, rolling folds and full 3x3 cost grid.

    Warmup has no exposure. Folds use only 61 prior sessions and 19 fresh test
    sessions, reset cash, no training labels or fitted transforms. Seven folds
    for 194 sessions. Availability remains exploratory even with clean splitting.
    """
    checked = validate_bars(bars)
    master = validate_instrument_master(instruments)
    cal = validate_exchange_calendar(calendar)
    first, last = min(b.session_date for b in checked), max(b.session_date for b in checked)
    sessions = [s.session_date for s in cal if s.is_open and first <= s.session_date <= last]
    if len(sessions) <= config.warmup_sessions:
        raise ValueError("Insufficient observed open sessions after warmup")
    by_date: dict[date, dict[str, DailyBar]] = {d: {} for d in sessions}
    for b in checked:
        if b.session_date not in by_date:
            raise ValueError("Bar outside open-session calendar")
        by_date[b.session_date][b.instrument_id] = b
    cutoffs = {s.session_date: s.closes_at for s in cal}
    features = {
        d: _metrics(sessions[: i + 1], by_date, master, cutoffs[d])
        for i, d in enumerate(sessions)
        if i >= 60
    }
    data_hash = _hash(
        [asdict(b) for b in sorted(checked, key=lambda b: (b.session_date, b.instrument_id))]
    )
    contract_hash = _hash(
        {
            "config": asdict(config),
            "version": VERSION,
            "formulas": FORMULAS,
            "data_hash": data_hash,
            "master": [asdict(r) for r in master],
            "calendar": [asdict(s) for s in cal],
            "code_sha256": _file_hash(Path(__file__)),
        }
    )
    base_runs = {
        s: _simulate(
            s, sessions, by_date, features, config, decision_start=config.warmup_sessions - 1
        )
        for s in STRATEGY_IDS
    }
    benchmark = base_runs[STRATEGY_IDS[2]]
    fold_runs: list[dict[str, _Run]] = []
    fold_dates: list[dict[str, Any]] = []
    for cursor in range(0, len(sessions) - 61 - 19 + 1, 19):
        days = sessions[cursor : cursor + 80]
        # Flat capital mark at final training close schedules first next-open test orders.
        execution_days = days[60:]
        fold_features = {
            d: _metrics(days[: j + 1], by_date, master, cutoffs[d])
            for j, d in enumerate(days)
            if j >= 60
        }
        runs = {
            s: _simulate(s, execution_days, by_date, fold_features, config, decision_start=0)
            for s in STRATEGY_IDS
        }
        fold_runs.append(runs)
        fold_dates.append(
            {
                "fold_index": len(fold_runs),
                "train_start": days[0].isoformat(),
                "train_end": days[60].isoformat(),
                "test_start": days[61].isoformat(),
                "test_end": days[-1].isoformat(),
                "train_sessions": 61,
                "test_sessions": 19,
            }
        )
    reports = []
    for i, strategy in enumerate(STRATEGY_IDS):
        run = base_runs[strategy]
        folds = []
        for dates, runs in zip(fold_dates, fold_runs, strict=True):
            result = runs[strategy].summary
            bench = runs[STRATEGY_IDS[2]].summary["net_return_pct"]
            folds.append(
                {
                    **dates,
                    "strategy_return_pct": result["net_return_pct"],
                    "liquidated_return_pct": result["liquidated_return_pct"],
                    "benchmark_return_pct": bench,
                    "excess_return_pct": round(result["net_return_pct"] - bench, 6),
                    "fill_count": result["trade_count"],
                    "fees_tnd": result["total_fees_tnd"],
                }
            )
        walk: dict[str, Any] = {
            "train_sessions": 61,
            "test_sessions": 19,
            "step_sessions": 19,
            "total_folds": len(folds),
            "positive_folds": sum(f["strategy_return_pct"] > 0 for f in folds),
            "folds": folds,
            "classification": "exploratory chronological forward tests; no fitted parameters",
        }
        for field, source in (
            ("mean_fold_return_pct", "strategy_return_pct"),
            ("mean_liquidated_return_pct", "liquidated_return_pct"),
            ("mean_excess_return_pct", "excess_return_pct"),
        ):
            walk[field] = round(sum(f[source] for f in folds) / len(folds), 6) if folds else None
        scenarios = []
        for commission in (30, 50, 70):
            for participation in (".05", ".10", ".20"):
                cfg = replace(
                    config,
                    execution=replace(
                        config.execution,
                        commission_bps=D(commission),
                        max_volume_participation=D(participation),
                    ),
                )
                scenario = (
                    run
                    if commission == 50
                    and participation == ".10"
                    and config.execution.commission_bps == 50
                    and config.execution.max_volume_participation == D(".10")
                    else _simulate(
                        strategy,
                        sessions,
                        by_date,
                        features,
                        cfg,
                        decision_start=config.warmup_sessions - 1,
                    )
                )
                scenarios.append(
                    {
                        "commission_bps": commission,
                        "max_volume_participation": float(participation),
                        **{
                            k: scenario.summary[k]
                            for k in (
                                "net_return_pct",
                                "liquidated_return_pct",
                                "total_fees_tnd",
                                "trade_count",
                            )
                        },
                    }
                )
        curve = [
            {**point, "benchmark_equity_tnd": b["total_equity_tnd"]}
            for point, b in zip(run.curve, benchmark.curve, strict=True)
        ]
        report = StrategyEvaluationReport(
            strategy_id=strategy,
            name=strategy[2:].replace("_", " ").title(),
            version=VERSION,
            family="baseline" if i < 7 else "enhanced",
            implementation_status="implemented",
            sample_Classification="exploratory",
            formula_summary=FORMULAS[i],
            assumptions={
                "profile": "research_conservative",
                **asdict(config),
                "benchmark": "C_BUY_AND_HOLD_BENCHMARK; same warmup, fees, slippage, universe and capital",
                "event_overlay": "disabled: no verified historical event input",
                "warmup_in_average_utilization": True,
                "signal_eligibility": "Dated eligible principal record; complete 61-session history with traded anchors, no suspensions and known publication no later than decision cutoff.",
                "historical_availability_mode": "Exploratory archive-session reconstruction; unknown publication timestamps and retrospective ingestion prevent verified historical availability.",
            },
            failure_modes=LIMITATIONS.copy(),
            start_session=sessions[0].isoformat(),
            end_session=sessions[-1].isoformat(),
            session_count=len(sessions),
            **{k: v for k, v in run.summary.items() if k != "diagnostics"},
            benchmark_return_pct=benchmark.summary["net_return_pct"],
            excess_return_pct=round(
                run.summary["net_return_pct"] - benchmark.summary["net_return_pct"], 6
            ),
            walk_forward=walk,
            fee_and_liquidity_sensitivity={
                "scenarios": scenarios,
                "min_return_pct": min(s["net_return_pct"] for s in scenarios),
                "max_return_pct": max(s["net_return_pct"] for s in scenarios),
                "method": "rerun sequential strategy sizing and execution for every scenario",
            },
            equity_curve=curve,
            is_statistically_conclusive=False,
            promotion_status="research_only_requires_human_approval",
            config_hash=contract_hash,
            experiment_id=_hash({"config_hash": contract_hash, "strategy_id": strategy}),
            diagnostics=run.summary["diagnostics"],
            risk_normalized_metrics=_risk_metrics(
                strategy, run, base_runs, sessions, by_date, features, master, cutoffs, config
            ),
        )
        reports.append(asdict(report))
    return {
        "schema_version": VERSION,
        "status": "available",
        "data_hash": data_hash,
        "config_hash": contract_hash,
        "trial_count": 9,
        "audit_summary": {
            "model_g_audit_status": "exploratory_unvalidated_high_outlier_dependency",
            "model_g_promotion_eligible": False,
            "key_findings": AUDIT_FINDINGS.copy(),
        },
        "robustness_v2": {
            "version": "2.0",
            "metrics_field": "risk_normalized_metrics",
            "interpretation": "Descriptive selected-sample diagnostics; cash matching is linear scaling, not executable leverage. Next-open trims remain capacity limited; bootstrap intervals do not correct selection bias.",
        },
        "reports": reports,
        "ml_promotion_gate": {
            "eligible": False,
            "session_count": len(sessions),
            "minimum_sessions": 250,
            "reason": f"{len(sessions)} sessions. "
            + (
                "Fewer than 250 blocks leak-free multi-year LightGBM promotion. "
                if len(sessions) < 250
                else "Minimum count alone is insufficient. "
            )
            + "Independent multi-year validation, purged labels, untouched holdout and human approval are still required.",
        },
        "limitations": LIMITATIONS.copy(),
    }


def generate_experiment_registry(
    processed_dir: Path, archive_path: Path, output_path: Path
) -> dict[str, Any]:
    """Explicit offline artifact writer; never called on API import or GET."""
    result = evaluate_strategy_suite(
        read_bars_csv(processed_dir / "daily_bars.canonical.csv"),
        read_instrument_master(processed_dir / "instrument_master.csv"),
        read_exchange_calendar(processed_dir / "exchange_calendar.csv"),
    )
    result["historical_audit"] = audit_historical_coverage_and_blockers(archive_path, processed_dir)
    result["code_sha256"] = _file_hash(Path(__file__))
    result["canonical_sha256"] = _file_hash(processed_dir / "daily_bars.canonical.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, default=str, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return result
