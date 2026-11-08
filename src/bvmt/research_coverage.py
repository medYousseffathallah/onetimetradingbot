"""Research coverage, sparse-data analytics, and continuous liquidity ranking (P0).

Strictly enforces:
- Complete point-in-time boundary: uses only exchange sessions and bars on or before cutoff.
- No forward-filling across untraded or missing sessions.
- No fabricated prices or synthetic returns.
- Separation of research analytics from strategy execution eligibility.
- Zero lookahead in order capacity (uses trailing median turnover up to cutoff, never next-day volume).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from statistics import median
from typing import Literal

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    resolve_instrument_on_date,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.data import DailyBar, validate_bars
from bvmt.features import SessionBaselineReport

ResearchCoverageStatus = Literal[
    "FULL_COVERAGE",
    "SPARSE_DATA",
    "PARTIAL_HISTORY",
    "UNTRADED_HISTORY",
    "MISSING_DATA",
]

SignalAvailability = Literal[
    "FULL_SIGNALS",
    "RESEARCH_ONLY_SIGNALS",
    "INSUFFICIENT_OBSERVATIONS",
    "NO_SIGNALS",
    "NO_DATA",
]

DataQualityStatus = Literal[
    "VERIFIED_EOD",
    "SPARSE_VOLUME",
    "STALE_QUOTES",
    "UNTRADED_ANCHOR",
    "MISSING_SESSIONS",
    "RESTRICTED_SEGMENT",
    "ZERO_VOLUME",
    "NO_BARS",
    "REVIEW_REQUIRED",
]

CompetitionEligibility = Literal[
    "COMPETITION_PERMITTED",
    "MARKET_RESTRICTED",
    "UNKNOWN",
]

StrategyEligibility = Literal[
    "ELIGIBLE",
    "STRATEGY_EXCLUDED",
    "NEEDS_REVIEW",
]

ExecutionFeasibility = Literal[
    "FEASIBLE",
    "LIQUIDITY_LIMITED",
    "ZERO_VOLUME_BLOCKED",
    "MARKET_RESTRICTED",
    "REVIEW_REQUIRED",
]


@dataclass(frozen=True)
class ResearchClassification:
    research_coverage_status: ResearchCoverageStatus
    signal_availability: SignalAvailability
    data_quality_status: DataQualityStatus
    competition_eligibility: CompetitionEligibility
    strategy_eligibility: StrategyEligibility
    execution_feasibility: ExecutionFeasibility

    def to_dict(self) -> dict[str, str]:
        return {
            "competition_eligibility": self.competition_eligibility,
            "data_quality_status": self.data_quality_status,
            "execution_feasibility": self.execution_feasibility,
            "research_coverage_status": self.research_coverage_status,
            "signal_availability": self.signal_availability,
            "strategy_eligibility": self.strategy_eligibility,
        }


@dataclass(frozen=True)
class SparseInstrumentAnalytics:
    instrument_id: str
    symbol: str
    isin: str | None
    market_segment: str
    classification: ResearchClassification
    total_open_sessions: int
    observed_bars: int
    traded_bars: int
    untraded_bars: int
    trailing_untraded_sessions: int
    observation_coverage_ratio: Decimal
    latest_bar_date: date | None
    latest_bar_status: str | None
    latest_bar_close: Decimal | None
    last_verified_price: Decimal | None
    last_traded_date: date | None
    quote_age_sessions: int
    observed_trade_return_pct: Decimal | None
    observed_trade_interval_sessions: int | None
    safe_calendar_return_20s_pct: Decimal | None
    safe_calendar_return_60s_pct: Decimal | None
    trade_frequency_20s: Decimal
    median_turnover_20s_tnd: Decimal
    median_traded_turnover_tnd: Decimal
    research_confidence_score: float
    continuous_liquidity_factor: float
    continuous_research_score: float | None
    conservative_order_capacity_tnd: Decimal
    hypothetical_order_shares: int
    strategy_eligible: bool
    strategy_composite_score: float | None
    strategy_momentum_20s: float | None
    strategy_momentum_60s: float | None
    exclusion_reasons: list[str] = field(default_factory=list)
    exclusion_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "classification": self.classification.to_dict(),
            "conservative_order_capacity_tnd": str(self.conservative_order_capacity_tnd),
            "continuous_liquidity_factor": round(self.continuous_liquidity_factor, 4),
            "continuous_research_score": (
                round(self.continuous_research_score, 4)
                if self.continuous_research_score is not None
                else None
            ),
            "exclusion_details": self.exclusion_details,
            "exclusion_reasons": self.exclusion_reasons,
            "hypothetical_order_shares": self.hypothetical_order_shares,
            "instrument_id": self.instrument_id,
            "isin": self.isin,
            "last_traded_date": self.last_traded_date.isoformat()
            if self.last_traded_date
            else None,
            "last_verified_price": str(self.last_verified_price)
            if self.last_verified_price
            else None,
            "latest_bar_close": str(self.latest_bar_close) if self.latest_bar_close else None,
            "latest_bar_date": self.latest_bar_date.isoformat() if self.latest_bar_date else None,
            "latest_bar_status": self.latest_bar_status,
            "market_segment": self.market_segment,
            "median_traded_turnover_tnd": str(self.median_traded_turnover_tnd),
            "median_turnover_20s_tnd": str(self.median_turnover_20s_tnd),
            "observation_coverage_ratio": str(self.observation_coverage_ratio),
            "observed_bars": self.observed_bars,
            "observed_trade_interval_sessions": self.observed_trade_interval_sessions,
            "observed_trade_return_pct": (
                str(self.observed_trade_return_pct)
                if self.observed_trade_return_pct is not None
                else None
            ),
            "quote_age_sessions": self.quote_age_sessions,
            "research_confidence_score": round(self.research_confidence_score, 4),
            "safe_calendar_return_20s_pct": (
                str(self.safe_calendar_return_20s_pct)
                if self.safe_calendar_return_20s_pct is not None
                else None
            ),
            "safe_calendar_return_60s_pct": (
                str(self.safe_calendar_return_60s_pct)
                if self.safe_calendar_return_60s_pct is not None
                else None
            ),
            "strategy_composite_score": self.strategy_composite_score,
            "strategy_eligible": self.strategy_eligible,
            "strategy_momentum_20s": self.strategy_momentum_20s,
            "strategy_momentum_60s": self.strategy_momentum_60s,
            "symbol": self.symbol,
            "total_open_sessions": self.total_open_sessions,
            "trade_frequency_20s": str(self.trade_frequency_20s),
            "traded_bars": self.traded_bars,
            "trailing_untraded_sessions": self.trailing_untraded_sessions,
            "untraded_bars": self.untraded_bars,
        }


@dataclass(frozen=True)
class MarketResearchReport:
    as_of: str
    latest_open_session: str
    total_instruments: int
    eligible_count: int
    excluded_count: int
    analytics: list[SparseInstrumentAnalytics]
    by_instrument: dict[str, SparseInstrumentAnalytics] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "analytics": [a.to_dict() for a in self.analytics],
            "as_of": self.as_of,
            "eligible_count": self.eligible_count,
            "excluded_count": self.excluded_count,
            "latest_open_session": self.latest_open_session,
            "total_instruments": self.total_instruments,
        }


def evaluate_market_research_coverage(
    instruments: list[InstrumentRecord],
    calendar: list[ExchangeSession],
    bars: list[DailyBar],
    cutoff: datetime,
    *,
    baseline_report: SessionBaselineReport | None = None,
    portfolio_equity: Decimal = Decimal("50000.000"),
    max_position_weight: Decimal = Decimal("0.085"),
    liquidity_participation_cap: Decimal = Decimal("0.10"),
    turnover_norm_hurdle_tnd: Decimal = Decimal("5000.000"),
) -> MarketResearchReport:
    """Evaluate point-in-time research coverage and sparse analytics for all listed instruments.

    Preserves separation between market researchability and strategy execution rules.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")

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
    total_sessions = len(open_sessions)

    # 20-session and 60-session windows
    window_20 = open_sessions[-21:] if len(open_sessions) >= 21 else open_sessions
    window_60 = open_sessions[-61:] if len(open_sessions) >= 61 else open_sessions
    dates_in_60 = {s.session_date for s in window_60}
    dates_in_20 = {s.session_date for s in window_20}

    # Point-in-time bars on or before cutoff
    pit_bars: dict[tuple[str, date], DailyBar] = {}
    bars_by_inst: dict[str, list[DailyBar]] = defaultdict(list)
    for b in bar_list:
        if (
            b.published_at is not None
            and b.published_at <= cutoff
            and b.ingested_at <= cutoff
            and b.session_date <= latest_date
        ):
            pit_bars[(b.instrument_id, b.session_date)] = b
            bars_by_inst[b.instrument_id].append(b)

    for iid in bars_by_inst:
        bars_by_inst[iid].sort(key=lambda x: x.session_date)

    # Baseline candidate and exclusion lookup
    cand_by_id = {}
    excl_by_id = defaultdict(list)
    if baseline_report is not None:
        for c in baseline_report.candidates:
            cand_by_id[c.instrument_id] = c
        for e in baseline_report.exclusions:
            excl_by_id[e.instrument_id].append(e)

    by_inst_master: dict[str, list[InstrumentRecord]] = defaultdict(list)
    for rec in inst_list:
        by_inst_master[rec.instrument_id].append(rec)

    analytics_list: list[SparseInstrumentAnalytics] = []

    for inst_id, recs in sorted(by_inst_master.items()):
        active_rec = resolve_instrument_on_date(recs, inst_id, latest_date)
        rec = active_rec if active_rec is not None else recs[-1]
        symbol = rec.symbol
        isin = rec.isin
        segment = rec.market_segment
        is_comp_eligible = rec.is_competition_eligible

        inst_bars = bars_by_inst.get(inst_id, [])
        total_bars = len(inst_bars)
        traded_bars = [b for b in inst_bars if b.status == "traded"]
        untraded_bars = [b for b in inst_bars if b.status in ("no_trade", "untraded")]

        latest_bar = inst_bars[-1] if inst_bars else None
        last_traded = traded_bars[-1] if traded_bars else None

        # Missing dates in 60-session window
        inst_bar_dates = {b.session_date for b in inst_bars}
        missing_60 = [d for d in dates_in_60 if d not in inst_bar_dates]

        # 20-session window metrics
        bars_in_20 = [b for b in inst_bars if b.session_date in dates_in_20]
        traded_in_20 = [b for b in bars_in_20 if b.status == "traded"]
        trade_freq_20_flt = (
            len(traded_in_20) / max(1, len(window_20) - 1) if len(window_20) > 1 else 0.0
        )
        trade_freq_20 = Decimal(str(round(trade_freq_20_flt, 4)))

        turnovers_20 = (
            [b.turnover_tnd for b in bars_in_20[1:]]
            if len(bars_in_20) > 1
            else ([b.turnover_tnd for b in bars_in_20] if bars_in_20 else [Decimal("0")])
        )
        med_turnover_20 = (
            Decimal(str(median(turnovers_20))).quantize(Decimal("0.001"))
            if turnovers_20
            else Decimal("0.000")
        )

        traded_turnovers = [b.turnover_tnd for b in traded_bars]
        med_traded_turnover = (
            Decimal(str(median(traded_turnovers))).quantize(Decimal("0.001"))
            if traded_turnovers
            else Decimal("0.000")
        )

        # Trailing untraded sessions at cutoff
        trailing_untraded = 0
        for b in reversed(inst_bars):
            if b.status in ("no_trade", "untraded"):
                trailing_untraded += 1
            else:
                break

        # Quote age in open sessions
        if last_traded is not None:
            quote_age = sum(1 for s in open_sessions if s.session_date > last_traded.session_date)
        else:
            quote_age = total_sessions

        # Observed return between last two traded bars
        if len(traded_bars) >= 2:
            last_bar_traded = traded_bars[-1]
            prev_traded = traded_bars[-2]
            ret_flt = float((last_bar_traded.close / prev_traded.close - Decimal(1)) * 100)
            observed_trade_return_pct = Decimal(str(round(ret_flt, 4)))
            observed_trade_interval = len(
                [
                    s
                    for s in open_sessions
                    if prev_traded.session_date < s.session_date <= last_bar_traded.session_date
                ]
            )
        else:
            observed_trade_return_pct = None
            observed_trade_interval = None

        # Safe calendar return over 20 open sessions (strictly when both anchors traded)
        bar_anchor_0 = pit_bars.get((inst_id, window_20[-1].session_date))
        bar_anchor_20 = (
            pit_bars.get((inst_id, window_20[0].session_date)) if len(window_20) >= 21 else None
        )
        if (
            bar_anchor_0 is not None
            and bar_anchor_20 is not None
            and bar_anchor_0.status == "traded"
            and bar_anchor_20.status == "traded"
        ):
            c_ret_20 = float((bar_anchor_0.close / bar_anchor_20.close - Decimal(1)) * 100)
            safe_cal_return_20 = Decimal(str(round(c_ret_20, 4)))
        else:
            safe_cal_return_20 = None

        # Safe calendar return over 60 open sessions
        bar_anchor_60 = (
            pit_bars.get((inst_id, window_60[0].session_date)) if len(window_60) >= 61 else None
        )
        if (
            bar_anchor_0 is not None
            and bar_anchor_60 is not None
            and bar_anchor_0.status == "traded"
            and bar_anchor_60.status == "traded"
        ):
            c_ret_60 = float((bar_anchor_0.close / bar_anchor_60.close - Decimal(1)) * 100)
            safe_cal_return_60 = Decimal(str(round(c_ret_60, 4)))
        else:
            safe_cal_return_60 = None

        obs_coverage_ratio = Decimal(str(round(len(traded_bars) / max(1, total_sessions), 4)))

        cand = cand_by_id.get(inst_id)
        excls = excl_by_id.get(inst_id, [])
        excl_reasons = [e.reason for e in excls]
        excl_details = [e.detail for e in excls]

        # Determine 6 Phase 1 classification dimensions
        is_restricted_segment = segment not in ("principal_continu", "principal_fixing")
        comp_elig: CompetitionEligibility = (
            "COMPETITION_PERMITTED"
            if is_comp_eligible and not is_restricted_segment
            else "MARKET_RESTRICTED"
        )
        strat_elig: StrategyEligibility = "ELIGIBLE" if cand is not None else "STRATEGY_EXCLUDED"

        if cand is not None:
            research_status: ResearchCoverageStatus = "FULL_COVERAGE"
            signal_avail: SignalAvailability = "FULL_SIGNALS"
            data_quality: DataQualityStatus = "VERIFIED_EOD"
            exec_feas: ExecutionFeasibility = "FEASIBLE"
        else:
            if total_bars == 0:
                research_status = "MISSING_DATA"
                signal_avail = "NO_DATA"
                data_quality = "NO_BARS"
                exec_feas = "ZERO_VOLUME_BLOCKED"
            elif len(traded_bars) == 0:
                research_status = "UNTRADED_HISTORY"
                signal_avail = "NO_SIGNALS"
                data_quality = "ZERO_VOLUME"
                exec_feas = "ZERO_VOLUME_BLOCKED"
            elif is_restricted_segment:
                research_status = "SPARSE_DATA" if len(traded_bars) < 30 else "FULL_COVERAGE"
                signal_avail = (
                    "RESEARCH_ONLY_SIGNALS"
                    if len(traded_bars) >= 2
                    else "INSUFFICIENT_OBSERVATIONS"
                )
                data_quality = "RESTRICTED_SEGMENT"
                exec_feas = "MARKET_RESTRICTED"
            elif missing_60:
                research_status = "PARTIAL_HISTORY"
                signal_avail = (
                    "RESEARCH_ONLY_SIGNALS"
                    if len(traded_bars) >= 2
                    else "INSUFFICIENT_OBSERVATIONS"
                )
                data_quality = "MISSING_SESSIONS"
                exec_feas = (
                    "FEASIBLE"
                    if latest_bar is not None and latest_bar.status == "traded"
                    else "LIQUIDITY_LIMITED"
                )
            elif "stale_quote" in excl_reasons or trailing_untraded >= 3:
                research_status = "SPARSE_DATA"
                signal_avail = (
                    "RESEARCH_ONLY_SIGNALS"
                    if len(traded_bars) >= 2
                    else "INSUFFICIENT_OBSERVATIONS"
                )
                data_quality = "STALE_QUOTES"
                exec_feas = "ZERO_VOLUME_BLOCKED"
            elif "insufficient_liquidity" in excl_reasons:
                research_status = "SPARSE_DATA"
                signal_avail = "RESEARCH_ONLY_SIGNALS"
                data_quality = "SPARSE_VOLUME"
                exec_feas = "LIQUIDITY_LIMITED"
            elif "untraded_lookback_anchor" in excl_reasons:
                research_status = "SPARSE_DATA"
                signal_avail = "RESEARCH_ONLY_SIGNALS"
                data_quality = "UNTRADED_ANCHOR"
                exec_feas = "LIQUIDITY_LIMITED"
            else:
                research_status = "PARTIAL_HISTORY"
                signal_avail = "INSUFFICIENT_OBSERVATIONS"
                data_quality = "REVIEW_REQUIRED"
                exec_feas = "REVIEW_REQUIRED"

        # Continuous liquidity penalty and research confidence
        # Freshness weight: drops linearly to zero as quote age exceeds 20 sessions
        freshness_factor = max(0.0, 1.0 - (quote_age / 20.0))
        # Coverage factor: ratio of traded bars
        coverage_factor = float(obs_coverage_ratio)
        # Volume factor: continuous saturation curve vs 5000 TND hurdle
        vol_factor = min(1.0, float(med_turnover_20 / turnover_norm_hurdle_tnd))
        continuous_liq_factor = round(vol_factor * float(trade_freq_20), 4)

        research_confidence = round(
            0.4 * freshness_factor + 0.3 * coverage_factor + 0.3 * continuous_liq_factor, 4
        )

        # Continuous research score
        # If strategy score exists, damp by continuous liquidity factor
        # If strategy score is excluded but observed trade return exists, construct research-only score
        if cand is not None:
            continuous_score = cand.composite_score * max(0.1, continuous_liq_factor)
        elif observed_trade_return_pct is not None and quote_age <= 20:
            # Scaled research proxy score based on observed return and confidence
            continuous_score = float(observed_trade_return_pct) * continuous_liq_factor * 0.1
        else:
            continuous_score = None

        # Conservative hypothetical order sizing (Zero Intraday Lookahead)
        # Sizing is strictly based on trailing median turnover observed up to cutoff
        ref_price = last_traded.close if last_traded is not None else None
        if ref_price is not None and ref_price > 0:
            turnover_capacity_tnd = med_turnover_20 * liquidity_participation_cap
            portfolio_cap_tnd = portfolio_equity * max_position_weight
            capped_capacity_tnd = min(turnover_capacity_tnd, portfolio_cap_tnd).quantize(
                Decimal("0.001")
            )
            hypothetical_shares = int(capped_capacity_tnd / ref_price)
        else:
            capped_capacity_tnd = Decimal("0.000")
            hypothetical_shares = 0

        classification = ResearchClassification(
            competition_eligibility=comp_elig,
            data_quality_status=data_quality,
            execution_feasibility=exec_feas,
            research_coverage_status=research_status,
            signal_availability=signal_avail,
            strategy_eligibility=strat_elig,
        )

        analytics = SparseInstrumentAnalytics(
            classification=classification,
            conservative_order_capacity_tnd=capped_capacity_tnd,
            continuous_liquidity_factor=continuous_liq_factor,
            continuous_research_score=continuous_score,
            exclusion_details=excl_details,
            exclusion_reasons=excl_reasons,
            hypothetical_order_shares=hypothetical_shares,
            instrument_id=inst_id,
            isin=isin,
            last_traded_date=last_traded.session_date if last_traded else None,
            last_verified_price=last_traded.close if last_traded else None,
            latest_bar_close=latest_bar.close if latest_bar else None,
            latest_bar_date=latest_bar.session_date if latest_bar else None,
            latest_bar_status=latest_bar.status if latest_bar else None,
            market_segment=segment,
            median_traded_turnover_tnd=med_traded_turnover,
            median_turnover_20s_tnd=med_turnover_20,
            observation_coverage_ratio=obs_coverage_ratio,
            observed_bars=total_bars,
            observed_trade_interval_sessions=observed_trade_interval,
            observed_trade_return_pct=observed_trade_return_pct,
            quote_age_sessions=quote_age,
            research_confidence_score=research_confidence,
            safe_calendar_return_20s_pct=safe_cal_return_20,
            safe_calendar_return_60s_pct=safe_cal_return_60,
            strategy_composite_score=cand.composite_score if cand else None,
            strategy_eligible=cand is not None,
            strategy_momentum_20s=cand.momentum_20s if cand else None,
            strategy_momentum_60s=cand.momentum_60s if cand else None,
            symbol=symbol,
            total_open_sessions=total_sessions,
            trade_frequency_20s=trade_freq_20,
            traded_bars=len(traded_bars),
            trailing_untraded_sessions=trailing_untraded,
            untraded_bars=len(untraded_bars),
        )
        analytics_list.append(analytics)

    analytics_dict = {a.instrument_id: a for a in analytics_list}

    return MarketResearchReport(
        analytics=analytics_list,
        as_of=cutoff.isoformat(),
        by_instrument=analytics_dict,
        eligible_count=sum(1 for a in analytics_list if a.strategy_eligible),
        excluded_count=sum(1 for a in analytics_list if not a.strategy_eligible),
        latest_open_session=latest_date.isoformat(),
        total_instruments=len(analytics_list),
    )
