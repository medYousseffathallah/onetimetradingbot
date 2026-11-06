"""Synthetic observed-bar demo ranking and T04 session-aware quantitative baseline ranking."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from statistics import median

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    SuspensionRecord,
    resolve_instrument_on_date,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.data import DailyBar, validate_bars


@dataclass(frozen=True)
class RankedCandidate:
    instrument_id: str
    symbol: str
    score: float
    close: str
    last_session: str
    observed_bars: int


@dataclass(frozen=True)
class SessionCandidate:
    instrument_id: str
    symbol: str
    market_segment: str
    last_session: str
    close: str
    momentum_20s: float
    momentum_60s: float
    relative_strength_20s: float
    volatility_20s: float
    median_turnover_20s: str
    trade_frequency_20s: float
    composite_score: float


@dataclass(frozen=True)
class ExcludedInstrument:
    instrument_id: str
    symbol: str | None
    reason: str
    detail: str


@dataclass(frozen=True)
class SessionBaselineReport:
    decision_cutoff: str
    latest_open_session: str
    short_lookback_sessions: int
    long_lookback_sessions: int
    benchmark_return_20s: float
    candidates: list[SessionCandidate]
    exclusions: list[ExcludedInstrument]


def rank_demo_momentum(
    bars: list[DailyBar], cutoff: datetime, *, lookback: int = 3, max_age_days: int = 7
) -> list[RankedCandidate]:
    """Rank only synthetic data available to this workflow by the cutoff.

    A production implementation must replace observed-bar lookbacks and calendar-day
    freshness with verified exchange sessions and corporate-action-aware features.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("The decision cutoff must be timezone-aware")
    if type(lookback) is not int or lookback < 1 or max_age_days < 0:
        raise ValueError("Invalid lookback or freshness limit")
    validate_bars(bars)
    if any(bar.source_id != "synthetic-fixture" for bar in bars):
        raise ValueError("Demo ranking is restricted to explicitly synthetic fixtures")
    grouped: dict[str, list[DailyBar]] = defaultdict(list)
    for bar in bars:
        if (
            bar.published_at is not None
            and bar.published_at <= cutoff
            and bar.ingested_at <= cutoff
            and bar.session_date <= cutoff.date()
        ):
            grouped[bar.instrument_id].append(bar)
    candidates: list[RankedCandidate] = []
    for instrument_id, history in grouped.items():
        history.sort(key=lambda bar: bar.session_date)
        if len(history) < lookback + 1:
            continue
        window = history[-(lookback + 1) :]
        last = window[-1]
        if last.status != "traded" or (cutoff.date() - last.session_date).days > max_age_days:
            continue
        if any(bar.status != "traded" for bar in window):
            continue
        score = float(last.close / window[0].close - 1)
        candidates.append(
            RankedCandidate(
                instrument_id=instrument_id,
                symbol=last.symbol,
                score=score,
                close=str(last.close),
                last_session=last.session_date.isoformat(),
                observed_bars=len(window),
            )
        )
    return sorted(candidates, key=lambda item: (-item.score, item.instrument_id))


def rank_session_baseline(
    instruments: Iterable[InstrumentRecord],
    calendar: Iterable[ExchangeSession],
    bars: Iterable[DailyBar],
    cutoff: datetime,
    *,
    suspensions: Iterable[SuspensionRecord] = (),
    short_lookback: int = 20,
    long_lookback: int = 60,
    min_trade_frequency: float = 0.75,
    min_median_turnover_tnd: Decimal = Decimal("1000"),
    stale_after_open_sessions: int = 3,
    eligible_segment: str = "Continu_Principal",
    benchmark_return_override: float | None = None,
    allowed_segments: tuple[str, ...] = ("principal", "principal_continu", "principal_fixing"),
) -> SessionBaselineReport:
    """Rank point-in-time eligible instruments over verified open exchange sessions (T04).

    Strictly enforces:
    - Lookbacks over actual open ExchangeSessions (never calendar-day approximations).
    - No forward-filling across missing, no_trade, or suspended sessions.
    - Explicit exclusion reasons for every rejected instrument.
    - Point-in-time cutoff invariance (`published_at <= cutoff`, `ingested_at <= cutoff`,
      and session `closes_at <= cutoff`).
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("The decision cutoff must be timezone-aware")
    if short_lookback < 2 or long_lookback < short_lookback:
        raise ValueError("Require 2 <= short_lookback <= long_lookback")
    if not (0.0 < min_trade_frequency <= 1.0):
        raise ValueError("min_trade_frequency must be in (0, 1]")
    if min_median_turnover_tnd < 0:
        raise ValueError("min_median_turnover_tnd must be nonnegative")

    inst_list = validate_instrument_master(instruments)
    cal_list = validate_exchange_calendar(calendar)
    bar_list = validate_bars(bars)

    open_sessions = [
        s for s in cal_list if s.is_open and s.closes_at is not None and s.closes_at <= cutoff
    ]
    if not open_sessions:
        raise ValueError("No completed open exchange sessions on or before cutoff")

    latest_session = open_sessions[-1]
    latest_date = latest_session.session_date

    pit_bars: dict[tuple[str, date], DailyBar] = {}
    for bar in bar_list:
        if (
            bar.published_at is not None
            and bar.published_at <= cutoff
            and bar.ingested_at <= cutoff
            and bar.session_date <= latest_date
        ):
            pit_bars[(bar.instrument_id, bar.session_date)] = bar

    suspended_keys = {(s.instrument_id, s.session_date) for s in suspensions}

    by_inst: dict[str, list[InstrumentRecord]] = defaultdict(list)
    for rec in inst_list:
        by_inst[rec.instrument_id].append(rec)

    exclusions: list[ExcludedInstrument] = []
    raw_metrics: list[dict[str, object]] = []

    for inst_id in sorted(by_inst.keys()):
        recs = by_inst[inst_id]
        listed_from = recs[0].listed_from
        listed_to = recs[0].listed_to
        active_rec = resolve_instrument_on_date(recs, inst_id, latest_date)
        symbol = active_rec.symbol if active_rec is not None else recs[-1].symbol

        if latest_date < listed_from or (listed_to is not None and latest_date > listed_to):
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="unlisted_or_delisted",
                    detail=f"Not listed on {latest_date.isoformat()} ({listed_from}..{listed_to})",
                )
            )
            continue

        if active_rec is None or (
            not active_rec.is_competition_eligible
            or active_rec.market_segment not in (*allowed_segments, eligible_segment)
        ):
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="ineligible_market_segment",
                    detail=(
                        f"Segment '{active_rec.market_segment if active_rec else None}' "
                        f"!= '{eligible_segment}'"
                    ),
                )
            )
            continue

        if len(open_sessions) < long_lookback + 1:
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="insufficient_session_history",
                    detail=f"Have {len(open_sessions)} open sessions, need {long_lookback + 1}",
                )
            )
            continue

        window_long = open_sessions[-(long_lookback + 1) :]
        window_short = open_sessions[-(short_lookback + 1) :]

        if (inst_id, latest_date) in suspended_keys:
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="suspended",
                    detail=f"Official suspension active on {latest_date.isoformat()}",
                )
            )
            continue

        missing_dates = [
            s.session_date.isoformat()
            for s in window_long
            if (inst_id, s.session_date) not in pit_bars
        ]
        if missing_dates:
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="missing_observation",
                    detail=f"Missing point-in-time bar on {len(missing_dates)} open session(s)",
                )
            )
            continue

        long_bars = [pit_bars[(inst_id, s.session_date)] for s in window_long]
        short_bars = [pit_bars[(inst_id, s.session_date)] for s in window_short]
        last_bar = long_bars[-1]

        if any(b.status == "suspended" for b in short_bars):
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="suspended",
                    detail="Suspended during short lookback window",
                )
            )
            continue

        trailing_no_trade = 0
        for b in reversed(short_bars):
            if b.status in {"no_trade", "untraded"}:
                trailing_no_trade += 1
            else:
                break
        if trailing_no_trade >= stale_after_open_sessions:
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="stale_quote",
                    detail=f"{trailing_no_trade} consecutive no_trade sessions at cutoff",
                )
            )
            continue

        if (
            last_bar.status != "traded"
            or short_bars[0].status != "traded"
            or long_bars[0].status != "traded"
        ):
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="untraded_lookback_anchor",
                    detail="Lookback start or decision-date bar was not traded (never forward-fill)",
                )
            )
            continue

        recent_20 = short_bars[1:]
        traded_count_20 = sum(1 for b in recent_20 if b.status == "traded")
        trade_freq_20 = traded_count_20 / len(recent_20)
        med_turnover_20 = Decimal(str(median([b.turnover_tnd for b in recent_20])))

        if trade_freq_20 < min_trade_frequency or med_turnover_20 < min_median_turnover_tnd:
            exclusions.append(
                ExcludedInstrument(
                    instrument_id=inst_id,
                    symbol=symbol,
                    reason="insufficient_liquidity",
                    detail=(
                        f"trade_freq={trade_freq_20:.2f} (min {min_trade_frequency:.2f}), "
                        f"median_turnover={med_turnover_20} (min {min_median_turnover_tnd})"
                    ),
                )
            )
            continue

        mom_20 = float(last_bar.close / short_bars[0].close - Decimal(1))
        mom_60 = float(last_bar.close / long_bars[0].close - Decimal(1))

        # Compute session-to-session returns strictly between traded bars in the short window
        traded_closes = [float(b.close) for b in short_bars if b.status == "traded"]
        step_returns = [
            traded_closes[i] / traded_closes[i - 1] - 1.0 for i in range(1, len(traded_closes))
        ]
        mean_r = sum(step_returns) / len(step_returns) if step_returns else 0.0
        var_r = (
            sum((r - mean_r) ** 2 for r in step_returns) / max(1, len(step_returns) - 1)
            if len(step_returns) > 1
            else 0.0
        )
        vol_20 = max(1e-6, var_r**0.5)

        raw_metrics.append(
            {
                "close": str(last_bar.close),
                "instrument_id": inst_id,
                "last_session": last_bar.session_date.isoformat(),
                "market_segment": active_rec.market_segment,
                "med_turnover_20": str(med_turnover_20.quantize(Decimal("0.001"))),
                "mom_20": mom_20,
                "mom_60": mom_60,
                "symbol": symbol,
                "trade_freq_20": round(trade_freq_20, 4),
                "vol_20": vol_20,
            }
        )

    if benchmark_return_override is not None:
        bench_20 = benchmark_return_override
    elif raw_metrics:
        bench_20 = sum(float(str(m["mom_20"])) for m in raw_metrics) / len(raw_metrics)
    else:
        bench_20 = 0.0

    candidates: list[SessionCandidate] = []
    for item in raw_metrics:
        m20 = float(str(item["mom_20"]))
        m60 = float(str(item["mom_60"]))
        v20 = float(str(item["vol_20"]))
        rs20 = m20 - bench_20
        composite = 0.5 * (m20 / v20) + 0.5 * (m60 / v20)
        candidates.append(
            SessionCandidate(
                instrument_id=str(item["instrument_id"]),
                symbol=str(item["symbol"]),
                market_segment=str(item["market_segment"]),
                last_session=str(item["last_session"]),
                close=str(item["close"]),
                momentum_20s=round(m20, 6),
                momentum_60s=round(m60, 6),
                relative_strength_20s=round(rs20, 6),
                volatility_20s=round(v20, 6),
                median_turnover_20s=str(item["med_turnover_20"]),
                trade_frequency_20s=float(str(item["trade_freq_20"])),
                composite_score=round(composite, 6),
            )
        )

    candidates.sort(key=lambda c: (-c.composite_score, c.instrument_id))
    exclusions.sort(key=lambda e: (e.instrument_id, e.reason))

    return SessionBaselineReport(
        decision_cutoff=cutoff.isoformat(),
        latest_open_session=latest_date.isoformat(),
        short_lookback_sessions=short_lookback,
        long_lookback_sessions=long_lookback,
        benchmark_return_20s=round(bench_20, 6),
        candidates=candidates,
        exclusions=exclusions,
    )
