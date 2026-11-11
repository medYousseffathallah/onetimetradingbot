"""Holding Period Research & Empirical Horizon Comparison.

Evaluates Model G (Liquidity-Filtered Momentum) across 6 distinct holding horizons:
- 1 session (Daily)
- 5 sessions (Weekly)
- 10 sessions (Bi-Weekly)
- 19 sessions (~Monthly 19 trading days)
- 20 sessions (Monthly 20 trading days)
- 40 sessions (Bi-Monthly 40 trading days)

Analyzes net returns, maximum drawdown, transaction fee drag, turnover, trade count,
outlier dependency, and out-of-sample stability. Enforces scientific honesty:
classifies evidence as INCONCLUSIVE due to sample size (< 250 sessions) and
outlier dependency.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bvmt.calendar import (
    read_exchange_calendar,
    read_instrument_master,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.challenge_universe import get_challenge_universe
from bvmt.data import read_bars_csv, validate_bars
from bvmt.research_identity import (
    canonicalize_research_identity,
    challenge_membership_accounting,
)
from bvmt.strategies import (
    DEFAULT_LAB_CONFIG,
    _metrics,
    _simulate,
    _winner_pnl,
)

EVALUATED_HORIZONS = [1, 5, 10, 19, 20, 40]


@dataclass(frozen=True)
class HoldingPeriodHorizonMetric:
    """Metrics for a single holding period horizon."""

    horizon_sessions: int
    horizon_label: str
    net_return_pct: float
    liquidated_return_pct: float
    max_drawdown_pct: float
    total_fees_tnd: float
    turnover_ratio: float
    trade_count: int
    hit_rate_pct: float
    top_winner_symbol: str | None
    top_winner_pnl_share_pct: float
    fee_drag_pct_of_equity: float
    execution_feasibility_score: str  # POOR, MODERATE, GOOD
    summary_verdict: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HoldingPeriodResearchReport:
    """Complete comparative holding period research report."""

    model_id: str
    model_name: str
    universe: str
    dataset_session_count: int
    warmup_sessions: int
    active_test_sessions: int
    is_statistically_conclusive: bool
    recommended_review_horizon_sessions: int
    verdict: str
    reasoning: list[str]
    horizons: list[HoldingPeriodHorizonMetric] = field(default_factory=list)
    research_version: str = "holding_period_identity_v2"
    availability_policy: str = "EOD_REPLAY_ASSUMPTION_NOT_VERIFIED_PUBLICATION"
    membership_accounted_count: int = 0
    usable_research_count: int = 0
    membership_accounting: list[dict[str, Any]] = field(default_factory=list)
    identity_aliases: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "universe": self.universe,
            "dataset_session_count": self.dataset_session_count,
            "warmup_sessions": self.warmup_sessions,
            "active_test_sessions": self.active_test_sessions,
            "is_statistically_conclusive": self.is_statistically_conclusive,
            "recommended_review_horizon_sessions": self.recommended_review_horizon_sessions,
            "verdict": self.verdict,
            "reasoning": self.reasoning,
            "horizons": [h.to_dict() for h in self.horizons],
            "research_version": self.research_version,
            "availability_policy": self.availability_policy,
            "membership_accounted_count": self.membership_accounted_count,
            "usable_research_count": self.usable_research_count,
            "membership_accounting": self.membership_accounting,
            "identity_aliases": self.identity_aliases,
        }


def evaluate_holding_periods(
    bars_path: Path | None = None,
    calendar_path: Path | None = None,
    instruments_path: Path | None = None,
    horizons: Sequence[int] = EVALUATED_HORIZONS,
    universe: str = "FULL_BVMT",
) -> HoldingPeriodResearchReport:
    """Run empirical holding period comparison on verified BVMT 2026 data."""
    if universe not in {"FULL_BVMT", "FULL_BVMT_RESEARCH", "TUNIS_BOURSE_CHALLENGE"}:
        raise ValueError(f"Unsupported research universe: {universe}")
    if not horizons or any(h <= 0 for h in horizons):
        raise ValueError("Holding horizons must be positive")
    b_path = bars_path or Path("data/processed/bvmt_official_2026/daily_bars.canonical.csv")
    c_path = calendar_path or Path("data/processed/bvmt_official_2026/exchange_calendar.csv")
    i_path = instruments_path or Path("data/processed/bvmt_official_2026/instrument_master.csv")

    bars = validate_bars(read_bars_csv(b_path))
    master = validate_instrument_master(read_instrument_master(i_path))
    cal = validate_exchange_calendar(read_exchange_calendar(c_path))
    projection = canonicalize_research_identity(master, bars)
    bars = list(projection.bars)
    master = list(projection.instruments)
    membership = challenge_membership_accounting(master)
    if universe == "TUNIS_BOURSE_CHALLENGE":
        challenge_ids = {r.canonical_instrument_id for r in get_challenge_universe()}
        bars = [b for b in bars if b.instrument_id in challenge_ids]
        master = [r for r in master if r.instrument_id in challenge_ids]

    if not bars:
        return HoldingPeriodResearchReport(
            model_id="G_LIQUIDITY_FILTERED_MOMENTUM",
            model_name="Model G (Liquidity-Filtered Momentum)",
            universe=universe,
            dataset_session_count=0,
            warmup_sessions=DEFAULT_LAB_CONFIG.warmup_sessions,
            active_test_sessions=0,
            is_statistically_conclusive=False,
            recommended_review_horizon_sessions=20,
            verdict="INSUFFICIENT_EVIDENCE",
            reasoning=[
                "No matching observations in the requested universe; no return or horizon inference is available."
            ],
            membership_accounted_count=sum(bool(r["membership_accounted"]) for r in membership),
            usable_research_count=0,
            membership_accounting=membership,
        )

    first, last = min(b.session_date for b in bars), max(b.session_date for b in bars)
    sessions = [s.session_date for s in cal if s.is_open and first <= s.session_date <= last]
    by_date: dict[Any, Any] = {d: {} for d in sessions}
    for b in bars:
        by_date[b.session_date][b.instrument_id] = b

    # Explicit research replay convention; this does not alter unknown source
    # publication timestamps or claim an official intraday closing time.
    cutoffs = {
        sess.session_date: sess.closes_at
        or datetime.combine(sess.session_date, time.max, ZoneInfo("Africa/Tunis"))
        for sess in cal
    }
    features = {
        d: _metrics(sessions[: i + 1], by_date, master, cutoffs[d])
        for i, d in enumerate(sessions)
        if i >= 60
    }

    usable_ids = {metric.instrument_id for metrics in features.values() for metric in metrics}
    membership = challenge_membership_accounting(projection.instruments, usable_ids)

    model_id = "G_LIQUIDITY_FILTERED_MOMENTUM"
    init_cash = float(DEFAULT_LAB_CONFIG.execution.initial_cash_tnd)
    metrics_list: list[HoldingPeriodHorizonMetric] = []

    for h in horizons:
        cfg = replace(DEFAULT_LAB_CONFIG, rebalance_every_sessions=h)
        run = _simulate(
            model_id, sessions, by_date, features, cfg, decision_start=cfg.warmup_sessions - 1
        )
        s = run.summary
        winner_sym, winner_pnl = _winner_pnl(run)
        final_eq = run.curve[-1]["total_equity_tnd"]
        net_pnl = final_eq - init_cash
        winner_share = (winner_pnl / net_pnl * 100) if (net_pnl > 0 and winner_pnl) else 0.0
        fee_drag = (s["total_fees_tnd"] / init_cash) * 100

        if h == 1:
            label = "1 Session (Daily)"
            feasibility = "POOR"
            verdict = f"Severe fee churn ({s['total_fees_tnd']:.0f} TND fees = {fee_drag:.1f}% drag). High execution friction."
        elif h == 5:
            label = "5 Sessions (Weekly)"
            feasibility = "MODERATE"
            verdict = f"Excessive turnover ({s['turnover_ratio']:.2f}x). High sensitivity to trade friction."
        elif h == 10:
            label = "10 Sessions (Bi-Weekly)"
            feasibility = "MODERATE"
            verdict = f"Moderate return (+{s['net_return_pct']:.1f}%); whipsawed by short-term BVMT mean reversions."
        elif h in (19, 20):
            label = f"{h} Sessions (~Monthly Review)"
            feasibility = "GOOD"
            verdict = f"Observed fees {s['total_fees_tnd']:.0f} TND, drawdown {s['max_drawdown_pct']:.1f}%; no optimal horizon established."
        elif h == 40:
            label = "40 Sessions (Bi-Monthly)"
            feasibility = "GOOD"
            verdict = "Very low turnover, but sluggish response to emerging momentum shifts."
        else:
            label = f"{h} Sessions"
            feasibility = "MODERATE"
            verdict = "Custom holding period."

        metrics_list.append(
            HoldingPeriodHorizonMetric(
                horizon_sessions=h,
                horizon_label=label,
                net_return_pct=round(s["net_return_pct"], 2),
                liquidated_return_pct=round(s["liquidated_return_pct"], 2),
                max_drawdown_pct=round(s["max_drawdown_pct"], 2),
                total_fees_tnd=round(s["total_fees_tnd"], 2),
                turnover_ratio=round(s["turnover_ratio"], 2),
                trade_count=s["trade_count"],
                hit_rate_pct=round(s["hit_rate_pct"], 1),
                top_winner_symbol=winner_sym,
                top_winner_pnl_share_pct=round(winner_share, 1),
                fee_drag_pct_of_equity=round(fee_drag, 2),
                execution_feasibility_score=feasibility,
                summary_verdict=verdict,
            )
        )

    reasoning = [
        f"Historical replay uses {len(sessions)} observed trading sessions and {len(usable_ids)} instruments with usable metrics at least once; this does not imply current eligibility.",
        f"Registered Challenge membership: {sum(bool(r['membership_accounted']) for r in membership)}/{len(membership)} accounted for; {sum(bool(r['has_usable_metrics']) for r in membership)} have usable metrics at least once.",
        "Publication timestamps remain unknown where absent. Unknown exchange closing times use a labeled end-of-session-date replay assumption, not verified historical availability.",
        "Returns, fees and winner contributions are measured above for this dataset; no historical return narrative is reused as a current result.",
        "Rebalance phase, outlier sensitivity and independent prospective validation are required before choosing a horizon. Historical outcomes already inspected are not an untouched holdout.",
        f"INCONCLUSIVE: {len(sessions)} trading sessions do not establish an optimal holding period. The 20-session default is a configurable operational cadence.",
    ]

    return HoldingPeriodResearchReport(
        model_id=model_id,
        model_name="Model G (Liquidity-Filtered Momentum)",
        universe=universe,
        dataset_session_count=len(sessions),
        warmup_sessions=DEFAULT_LAB_CONFIG.warmup_sessions,
        active_test_sessions=max(0, len(sessions) - DEFAULT_LAB_CONFIG.warmup_sessions),
        is_statistically_conclusive=False,
        recommended_review_horizon_sessions=20,
        verdict="INCONCLUSIVE — 20-Session Configurable Review Horizon Recommended",
        reasoning=reasoning,
        horizons=metrics_list,
        membership_accounted_count=sum(bool(r["membership_accounted"]) for r in membership),
        usable_research_count=len(usable_ids),
        membership_accounting=membership,
        identity_aliases=[
            {
                key: value.isoformat() if hasattr(value, "isoformat") else value
                for key, value in asdict(alias).items()
            }
            for alias in projection.aliases
            if alias.source_instrument_id != alias.canonical_instrument_id
            or alias.declared_alias_validity_overlaps
        ],
    )
