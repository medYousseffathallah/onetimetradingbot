"""Strict point-in-time walk-forward generalization benchmark (Phase 5).

Evaluates ``Baseline`` (``rank_session_baseline``) vs ``sparse_research_v1``
(both raw canonical bars and non-destructive ``'H'/'B'`` threshold-close sensitivity)
across non-overlapping chronological folds without lookahead or survivorship leakage.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any, Literal

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    read_exchange_calendar,
    read_instrument_master,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.challenge_universe import resolve_challenge_record
from bvmt.data import DailyBar, read_bars_csv, validate_bars
from bvmt.execution import MarketOrder, estimate_next_bar_fill
from bvmt.features import SessionBaselineReport, rank_session_baseline
from bvmt.llm import DocumentChunk
from bvmt.research_identity import canonicalize_research_identity
from bvmt.sparse_research import (
    SPARSE_OPPORTUNITY_MODEL_VERSION,
    FundamentalSnapshotRecord,
    SparseResearchConfig,
    evaluate_sparse_market_research,
    extract_limit_reserved_bars_from_rejections,
    load_emetteur_sector_map,
    load_frozen_sparse_research_config,
    merge_canonical_with_hb_recovery,
)

CohortName = Literal[
    "ICF",
    "OTHER_EXCLUDED_CHALLENGE",
    "SPARSE_LATER_ROSE",
    "SPARSE_LATER_FELL",
    "FREQUENT_BENCHMARK",
    "NO_MEANINGFUL_MOVE",
]

COHORT_NAMES: tuple[CohortName, ...] = (
    "ICF",
    "OTHER_EXCLUDED_CHALLENGE",
    "SPARSE_LATER_ROSE",
    "SPARSE_LATER_FELL",
    "FREQUENT_BENCHMARK",
    "NO_MEANINGFUL_MOVE",
)


@dataclass(frozen=True)
class ObservationOutcome:
    """One purged walk-forward `(decision_session, instrument_id)` audit row."""

    session_date: str
    instrument_id: str
    symbol: str
    in_challenge_universe: bool
    baseline_eligible: bool
    baseline_selected: bool
    baseline_rank: int | None
    baseline_exclusion_reasons: list[str]
    research_status: str
    research_selected: bool
    research_priority_score: float | None
    awakening_detected: bool
    quote_age_open_sessions: int | None
    observation_coverage_ratio: float
    trade_frequency_20s: float | None
    median_turnover_20s_tnd: Decimal | None
    missing_open_sessions_60s: int
    executable_feasible: bool
    executable_net_return_pct: float | None
    mark_to_mark_net_return_pct: float | None
    allocated_weight_pct: float
    is_sparse_at_decision: bool
    is_frequent_benchmark_at_decision: bool
    cohorts: list[CohortName]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "median_turnover_20s_tnd": str(self.median_turnover_20s_tnd)
            if self.median_turnover_20s_tnd is not None
            else None,
        }


@dataclass(frozen=True)
class ModelBenchmarkMetrics:
    """All 10 standardized Phase 5 metrics for a model (overall or per-cohort)."""

    model_label: str
    total_observations: int
    selected_count: int
    research_coverage_rate: float
    missed_opportunity_rate: float | None
    false_positive_rate: float | None
    top_k_candidate_precision: float | None
    mean_forward_net_return_pct: float | None
    median_forward_net_return_pct: float | None
    liquidity_feasibility_rate: float | None
    portfolio_max_drawdown_pct: float | None
    cumulative_portfolio_return_pct: float | None
    avg_active_exposure_pct: float
    max_single_weight_pct: float
    sparse_candidate_share: float | None
    signal_stability_jaccard: float | None
    mean_quote_age_sessions: float | None
    mean_observation_coverage_ratio: float
    evaluated_selected_count: int = 0
    unevaluated_selected_count: int = 0
    executable_observation_count: int = 0
    executable_winner_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WalkForwardBenchmarkReport:
    """Full Phase 5 comparative benchmark across Baseline, sparse_research_v1, and H/B recovery."""

    model_version: str
    config_sha256: str
    evaluation_dates: list[str]
    forward_horizon_sessions: int
    step_sessions: int
    baseline_metrics: ModelBenchmarkMetrics
    sparse_raw_metrics: ModelBenchmarkMetrics
    sparse_hb_recovered_metrics: ModelBenchmarkMetrics
    cohort_comparison: dict[str, dict[str, ModelBenchmarkMetrics]]
    hb_recovered_bars_count: int
    notes: list[str]
    evaluation_version: str = "executable_cohort_evaluation_v2"
    universe: str = "FULL_BVMT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "config_sha256": self.config_sha256,
            "evaluation_dates": self.evaluation_dates,
            "forward_horizon_sessions": self.forward_horizon_sessions,
            "step_sessions": self.step_sessions,
            "baseline_metrics": self.baseline_metrics.to_dict(),
            "sparse_raw_metrics": self.sparse_raw_metrics.to_dict(),
            "sparse_hb_recovered_metrics": self.sparse_hb_recovered_metrics.to_dict(),
            "cohort_comparison": {
                cohort: {k: v.to_dict() for k, v in models.items()}
                for cohort, models in self.cohort_comparison.items()
            },
            "hb_recovered_bars_count": self.hb_recovered_bars_count,
            "notes": self.notes,
            "evaluation_version": self.evaluation_version,
            "universe": self.universe,
        }


def _round4(v: float) -> float:
    return round(float(v), 4)


def _compute_forward_outcomes(
    inst_id: str,
    decision_date: date,
    last_ref_close: Decimal | None,
    target_horizon_dates: Sequence[date],
    bars_by_inst_date: Mapping[tuple[str, date], DailyBar],
    config: SparseResearchConfig,
    capital_slice_tnd: Decimal,
) -> tuple[bool, float | None, float | None]:
    """Compute realistic executable net return & mark-to-mark net move strictly on `(t, t+H]`."""
    if not target_horizon_dates:
        return False, None, None
    if (
        list(target_horizon_dates) != sorted(set(target_horizon_dates))
        or target_horizon_dates[0] <= decision_date
    ):
        raise ValueError("Forward horizon must contain distinct increasing later sessions")
    exit_bar = bars_by_inst_date.get((inst_id, target_horizon_dates[-1]))
    if exit_bar is None or exit_bar.status != "traded" or exit_bar.volume_shares <= 0:
        return False, None, None

    slip_frac = config.slippage_bps / Decimal("10000")
    mark_to_mark_net: float | None = None
    if last_ref_close is not None and last_ref_close > 0 and exit_bar is not None:
        buy_gross = last_ref_close * (Decimal(1) + slip_frac) * (Decimal(1) + config.buy_fee_rate)
        sell_net = exit_bar.close * (Decimal(1) - slip_frac) * (Decimal(1) - config.sell_fee_rate)
        mark_to_mark_net = _round4(float(sell_net / buy_gross - Decimal(1)) * 100.0)

    entry_bar = bars_by_inst_date.get((inst_id, target_horizon_dates[0]))
    if entry_bar is None or exit_bar is None or entry_bar.open <= 0:
        return False, None, mark_to_mark_net

    cap_shares = int(Decimal(entry_bar.volume_shares) * config.liquidity_participation_cap)
    if cap_shares <= 0:
        return False, None, mark_to_mark_net

    assumed_buy_price = entry_bar.open * (Decimal(1) + slip_frac)
    desired = int(capital_slice_tnd // (assumed_buy_price * (Decimal(1) + config.buy_fee_rate)))
    if desired <= 0 or cap_shares < desired:
        return False, None, mark_to_mark_net
    fill = estimate_next_bar_fill(
        MarketOrder(
            instrument_id=inst_id,
            decision_session=decision_date,
            side="buy",
            quantity=desired,
        ),
        entry_bar,
        participation_rate=config.liquidity_participation_cap,
        remaining_shared_capacity=cap_shares,
        slippage_bps=config.slippage_bps,
        commission_bps=config.buy_fee_rate * Decimal("10000"),
    )
    if fill.quantity != desired or fill.price is None:
        return False, None, mark_to_mark_net

    filled_notional = Decimal(fill.quantity) * fill.price
    if filled_notional < config.minimum_order_notional_tnd:
        return False, None, mark_to_mark_net

    # Exit is precommitted at the exact horizon close, not chosen from the last
    # tradable observation. Whole-slice liquidation must fit that session's cap.
    exit_capacity = int(Decimal(exit_bar.volume_shares) * config.liquidity_participation_cap)
    required_capacity = fill.quantity * (
        2 if entry_bar.session_date == exit_bar.session_date else 1
    )
    exit_price = exit_bar.close * (Decimal(1) - slip_frac)
    if exit_capacity < required_capacity or not exit_bar.low <= exit_price <= exit_bar.high:
        return False, None, mark_to_mark_net

    buy_cost = fill.price * (Decimal(1) + config.buy_fee_rate)
    sell_net = exit_price * (Decimal(1) - config.sell_fee_rate)
    exec_net = _round4(float(sell_net / buy_cost - Decimal(1)) * 100.0)
    return True, exec_net, mark_to_mark_net


def _aggregate_metrics(
    model_label: str,
    observations: Sequence[ObservationOutcome],
    *,
    use_baseline: bool,
    winner_threshold_pct: float = 2.0,
) -> ModelBenchmarkMetrics:
    total = len(observations)
    if total == 0:
        return ModelBenchmarkMetrics(
            model_label=model_label,
            total_observations=0,
            selected_count=0,
            research_coverage_rate=0.0,
            missed_opportunity_rate=None,
            false_positive_rate=None,
            top_k_candidate_precision=None,
            mean_forward_net_return_pct=None,
            median_forward_net_return_pct=None,
            liquidity_feasibility_rate=None,
            portfolio_max_drawdown_pct=None,
            cumulative_portfolio_return_pct=None,
            avg_active_exposure_pct=0.0,
            max_single_weight_pct=0.0,
            sparse_candidate_share=None,
            signal_stability_jaccard=None,
            mean_quote_age_sessions=None,
            mean_observation_coverage_ratio=0.0,
        )

    if use_baseline:
        covered_cnt = sum(1 for o in observations if o.baseline_eligible)
        selected = [o for o in observations if o.baseline_selected]
    else:
        covered_cnt = sum(
            1
            for o in observations
            if o.research_status
            in {"FULL_RESEARCH_AVAILABLE", "PARTIAL_RESEARCH_AVAILABLE", "EVENT_RESEARCH_AVAILABLE"}
        )
        selected = [o for o in observations if o.research_selected]

    coverage_rate = _round4(covered_cnt / total)

    executable = [
        o for o in observations if o.executable_feasible and o.executable_net_return_pct is not None
    ]
    evaluated_selected = [
        o for o in selected if o.executable_feasible and o.executable_net_return_pct is not None
    ]
    winners = [
        o
        for o in executable
        if o.executable_net_return_pct is not None
        and o.executable_net_return_pct >= winner_threshold_pct
    ]
    missed = [o for o in winners if o not in selected]
    missed_rate = _round4(len(missed) / len(winners)) if winners else None

    if selected:
        fp_cnt = 0
        win_cnt = 0
        exec_rets: list[float] = []
        feas_cnt = 0
        sparse_cnt = 0
        q_ages: list[int] = []
        for o in selected:
            if o.executable_feasible and o.executable_net_return_pct is not None:
                feas_cnt += 1
                exec_rets.append(o.executable_net_return_pct)
                if o.executable_net_return_pct > 0.0:
                    win_cnt += 1
                else:
                    fp_cnt += 1
            if o.is_sparse_at_decision:
                sparse_cnt += 1
            if o.quote_age_open_sessions is not None:
                q_ages.append(o.quote_age_open_sessions)

        fp_rate = _round4(fp_cnt / len(evaluated_selected)) if evaluated_selected else None
        precision = _round4(win_cnt / len(evaluated_selected)) if evaluated_selected else None
        feas_rate = _round4(feas_cnt / len(selected))
        sparse_share = _round4(sparse_cnt / len(selected))
        mean_ret = _round4(sum(exec_rets) / len(exec_rets)) if exec_rets else None
        med_ret = _round4(float(median(exec_rets))) if exec_rets else None
        mean_q_age = _round4(sum(q_ages) / len(q_ages)) if q_ages else None
    else:
        fp_rate = None
        precision = None
        feas_rate = None
        sparse_share = None
        mean_ret = None
        med_ret = None
        all_ages = [
            o.quote_age_open_sessions for o in observations if o.quote_age_open_sessions is not None
        ]
        mean_q_age = _round4(sum(all_ages) / len(all_ages)) if all_ages else None

    # Portfolio drawdown & exposure across evaluation sessions
    by_sess_all: dict[str, list[ObservationOutcome]] = defaultdict(list)
    by_sess_sel: dict[str, list[ObservationOutcome]] = defaultdict(list)
    for o in observations:
        by_sess_all[o.session_date].append(o)
    for o in selected:
        by_sess_sel[o.session_date].append(o)

    exposures: list[float] = []
    max_single = 0.0
    jaccards: list[float] = []
    prev_sel_set: set[str] | None = None

    for s_date in sorted(by_sess_all.keys()):
        s_sel = by_sess_sel.get(s_date, [])
        cur_set = {o.instrument_id for o in s_sel}
        if prev_sel_set is not None and (prev_sel_set or cur_set):
            union = len(prev_sel_set | cur_set)
            if union > 0:
                jaccards.append(len(prev_sel_set & cur_set) / union)
        prev_sel_set = cur_set

        period_exp = 0.0
        for o in s_sel:
            if o.executable_feasible and o.executable_net_return_pct is not None:
                period_exp += o.allocated_weight_pct
                max_single = max(max_single, o.allocated_weight_pct)
        exposures.append(period_exp)

    mean_cov = _round4(sum(o.observation_coverage_ratio for o in observations) / total)
    avg_exp = _round4(sum(exposures) / len(exposures)) if exposures else 0.0
    stability = _round4(sum(jaccards) / len(jaccards)) if jaccards else None

    return ModelBenchmarkMetrics(
        model_label=model_label,
        total_observations=total,
        selected_count=len(selected),
        research_coverage_rate=coverage_rate,
        missed_opportunity_rate=missed_rate,
        false_positive_rate=fp_rate,
        top_k_candidate_precision=precision,
        mean_forward_net_return_pct=mean_ret,
        median_forward_net_return_pct=med_ret,
        liquidity_feasibility_rate=feas_rate,
        portfolio_max_drawdown_pct=None,
        cumulative_portfolio_return_pct=None,
        avg_active_exposure_pct=avg_exp,
        max_single_weight_pct=_round4(max_single),
        sparse_candidate_share=sparse_share,
        signal_stability_jaccard=stability,
        mean_quote_age_sessions=mean_q_age,
        mean_observation_coverage_ratio=mean_cov,
        evaluated_selected_count=len(evaluated_selected),
        unevaluated_selected_count=len(selected) - len(evaluated_selected),
        executable_observation_count=len(executable),
        executable_winner_count=len(winners),
    )


def prepare_pit_calendar_and_bars(
    calendar: Sequence[ExchangeSession],
    bars: Sequence[DailyBar],
) -> tuple[list[ExchangeSession], list[DailyBar]]:
    """Backfill deterministic BVMT session EOD bounds when raw CSV uses null schedule timestamps."""
    cal_p = [
        replace(
            s,
            opens_at=datetime.fromisoformat(f"{s.session_date}T09:00:00+01:00"),
            closes_at=datetime.fromisoformat(f"{s.session_date}T16:00:00+01:00"),
            schedule_type="research_assumed_daily_bounds",
        )
        if s.is_open and s.closes_at is None
        else s
        for s in calendar
    ]
    bars_p = [
        replace(
            b,
            published_at=datetime.fromisoformat(f"{b.session_date}T16:00:00+01:00")
            if b.published_at is None
            else b.published_at,
            ingested_at=datetime.fromisoformat(f"{b.session_date}T16:00:00+01:00")
            if b.published_at is None
            and b.ingested_at > datetime.fromisoformat(f"{b.session_date}T16:00:00+01:00")
            else b.ingested_at,
        )
        for b in bars
    ]
    return cal_p, bars_p


def run_walk_forward_generalization_benchmark(
    instruments: Sequence[InstrumentRecord],
    calendar: Sequence[ExchangeSession],
    bars: Sequence[DailyBar],
    *,
    config: SparseResearchConfig | None = None,
    rejections_paths: Sequence[Path] = (),
    document_chunks: Sequence[DocumentChunk] = (),
    fundamental_records: Sequence[FundamentalSnapshotRecord] = (),
    sector_by_instrument: Mapping[str, str] | None = None,
    warmup_sessions: int = 61,
    forward_horizon_sessions: int = 10,
    step_sessions: int = 10,
    baseline_min_trade_freq: float = 0.60,
    baseline_min_median_turnover_tnd: Decimal | None = None,
    portfolio_equity_tnd: Decimal = Decimal("50000.000"),
    universe: str = "FULL_BVMT",
) -> WalkForwardBenchmarkReport:
    """Execute strict PIT walk-forward comparison across all 6 diagnostic cohorts & 10 dimensions."""
    cfg = config or load_frozen_sparse_research_config()
    if universe not in {"FULL_BVMT", "TUNIS_BOURSE_CHALLENGE"}:
        raise ValueError("Unknown research universe")
    if forward_horizon_sessions < 1 or step_sessions < 1 or warmup_sessions < 61:
        raise ValueError("Require positive horizon/step and at least 61 warmup sessions")
    threshold = cfg.liquidity_feasible_median_turnover_tnd
    if (
        baseline_min_median_turnover_tnd is not None
        and baseline_min_median_turnover_tnd != threshold
    ):
        raise ValueError("Baseline and sparse median turnover thresholds must match")
    inst_list = validate_instrument_master(instruments)
    source_master = inst_list
    cal_prep, bars_prep = prepare_pit_calendar_and_bars(
        validate_exchange_calendar(calendar), validate_bars(bars)
    )
    projection = canonicalize_research_identity(inst_list, bars_prep)
    inst_list, bars_prep = list(projection.instruments), list(projection.bars)
    alias_ids = {a.source_instrument_id: a.canonical_instrument_id for a in projection.aliases}
    if universe == "TUNIS_BOURSE_CHALLENGE":
        inst_list = [r for r in inst_list if resolve_challenge_record(r.instrument_id) is not None]
        ids = {r.instrument_id for r in inst_list}
        bars_prep = [b for b in bars_prep if b.instrument_id in ids]

    open_sessions = sorted(
        (s for s in cal_prep if s.is_open and s.closes_at is not None),
        key=lambda s: s.session_date,
    )
    if len(open_sessions) <= warmup_sessions + forward_horizon_sessions:
        raise ValueError("Insufficient open sessions for walk-forward warmup and horizon")

    hb_bars, hb_meta = extract_limit_reserved_bars_from_rejections(
        rejections_paths, allow_recovery=True
    )
    hb_projection = canonicalize_research_identity(source_master, hb_bars)
    hb_bars = list(hb_projection.bars)
    if universe == "TUNIS_BOURSE_CHALLENGE":
        hb_bars = [b for b in hb_bars if b.instrument_id in ids]
    hb_meta = [
        replace(m, instrument_id=alias_ids.get(m.instrument_id, m.instrument_id)) for m in hb_meta
    ]
    merged_bars, hb_keys = merge_canonical_with_hb_recovery(bars_prep, hb_bars)

    raw_bar_map = {(b.instrument_id, b.session_date): b for b in bars_prep}
    merged_bar_map = {(b.instrument_id, b.session_date): b for b in merged_bars}

    eval_indices = list(
        range(
            warmup_sessions - 1,
            len(open_sessions) - forward_horizon_sessions,
            step_sessions,
        )
    )
    eval_dates = [open_sessions[idx].session_date.isoformat() for idx in eval_indices]

    capital_slice = (portfolio_equity_tnd * cfg.target_position_weight).quantize(Decimal("0.001"))
    alloc_weight_pct = float(cfg.target_position_weight * Decimal("100"))

    baseline_obs: list[ObservationOutcome] = []
    sparse_raw_obs: list[ObservationOutcome] = []
    sparse_hb_obs: list[ObservationOutcome] = []

    def _run_one_slice(
        idx: int,
        bars_in: Sequence[DailyBar],
        bar_map: Mapping[tuple[str, date], DailyBar],
        *,
        with_hb: bool,
        base_rep_override: SessionBaselineReport | None = None,
        cohorts_by_inst_override: Mapping[str, tuple[bool, bool, list[CohortName]]] | None = None,
    ) -> tuple[
        list[ObservationOutcome],
        list[ObservationOutcome] | None,
        SessionBaselineReport,
        dict[str, tuple[bool, bool, list[CohortName]]],
    ]:
        sess = open_sessions[idx]
        d_t = sess.session_date
        cutoff = sess.closes_at
        assert cutoff is not None  # open_sessions excludes unknown closes after replay preparation
        fut_dates = [
            open_sessions[j].session_date
            for j in range(idx + 1, idx + 1 + forward_horizon_sessions)
        ]

        pit_slice = [b for b in bars_in if b.session_date <= d_t]
        base_rep = (
            base_rep_override
            if base_rep_override is not None
            else rank_session_baseline(
                inst_list,
                cal_prep,
                pit_slice,
                cutoff,
                min_trade_frequency=baseline_min_trade_freq,
                min_median_turnover_tnd=threshold,
                universe=universe,
            )
        )
        base_pos_top_k = {
            c.instrument_id: rank_i
            for rank_i, c in enumerate(
                [c for c in base_rep.candidates if c.composite_score > 0.0][: cfg.candidate_top_k],
                1,
            )
        }
        base_rank_all = {c.instrument_id: idx_r for idx_r, c in enumerate(base_rep.candidates, 1)}

        pit_meta = [m for m in hb_meta if m.session_date <= d_t]
        pit_hb_keys = (
            frozenset((iid, sd) for (iid, sd) in hb_keys if sd <= d_t) if with_hb else frozenset()
        )
        sp_rep = evaluate_sparse_market_research(
            inst_list,
            cal_prep,
            pit_slice,
            cutoff,
            config=cfg,
            baseline_report=base_rep,
            document_chunks=document_chunks,
            fundamental_records=fundamental_records,
            portfolio_equity_tnd=portfolio_equity_tnd,
            sector_by_instrument=sector_by_instrument,
            limit_reserved_meta=pit_meta,
            limit_reserved_recovery_applied=with_hb,
            hb_bar_keys=pit_hb_keys,
            universe=universe,
        )

        # Anchor cohorts to canonical raw evaluation so all 3 models compare identical cohort N
        sp_rows: list[ObservationOutcome] = []
        b_rows: list[ObservationOutcome] | None = [] if not with_hb else None
        computed_cohorts: dict[str, tuple[bool, bool, list[CohortName]]] = {}

        for a in sp_rep.assessments:
            iid = a.instrument_id
            ref_px = (
                a.liquidity_execution_feasibility.executable_reference_price_tnd
                or a.liquidity_execution_feasibility.last_verified_close_tnd
            )
            exec_ok, exec_net, m2m_net = _compute_forward_outcomes(
                iid, d_t, ref_px, fut_dates, bar_map, cfg, capital_slice
            )

            chal_rec = resolve_challenge_record(iid) or (
                resolve_challenge_record(a.isin) if a.isin else None
            )
            in_chal = chal_rec is not None
            tf20 = a.liquidity_execution_feasibility.trade_frequency_20s
            med_t = a.liquidity_execution_feasibility.median_turnover_20s_tnd
            miss60 = a.data_quality_freshness.missing_open_sessions_60s

            if cohorts_by_inst_override is not None and iid in cohorts_by_inst_override:
                is_sparse, is_bench, cohorts = cohorts_by_inst_override[iid]
            else:
                is_sparse = (
                    (tf20 is None or tf20 < 0.75)
                    or miss60 > 0
                    or (med_t is None or med_t < cfg.liquidity_feasible_median_turnover_tnd)
                )
                is_bench = (
                    (tf20 is not None and tf20 >= 0.90)
                    and miss60 == 0
                    and (med_t is not None and med_t >= Decimal("20000.000"))
                    and a.competition_eligibility.is_competition_permitted
                )

                cohorts = []
                if iid == "ICF":
                    cohorts.append("ICF")
                if (
                    in_chal
                    and iid != "ICF"
                    and not a.baseline_eligible
                    and any(
                        r
                        in {
                            "missing_observation",
                            "untraded_lookback_anchor",
                            "insufficient_liquidity",
                        }
                        for r in a.baseline_exclusion_reasons
                    )
                ):
                    cohorts.append("OTHER_EXCLUDED_CHALLENGE")
                if is_sparse and m2m_net is not None and m2m_net >= 2.0:
                    cohorts.append("SPARSE_LATER_ROSE")
                if is_sparse and m2m_net is not None and m2m_net <= -2.0:
                    cohorts.append("SPARSE_LATER_FELL")
                if is_bench:
                    cohorts.append("FREQUENT_BENCHMARK")
                if m2m_net is not None and -2.0 < m2m_net < 2.0:
                    cohorts.append("NO_MEANINGFUL_MOVE")
                computed_cohorts[iid] = (is_sparse, is_bench, cohorts)

            row_sp = ObservationOutcome(
                session_date=d_t.isoformat(),
                instrument_id=iid,
                symbol=a.symbol,
                in_challenge_universe=in_chal,
                baseline_eligible=a.baseline_eligible,
                baseline_selected=(iid in base_pos_top_k),
                baseline_rank=base_rank_all.get(iid),
                baseline_exclusion_reasons=list(a.baseline_exclusion_reasons),
                research_status=a.research_status,
                research_selected=a.is_selected_candidate,
                research_priority_score=a.research_priority_score,
                awakening_detected=a.quantitative_trend_evidence.awakening_detected,
                quote_age_open_sessions=a.data_quality_freshness.quote_age_open_sessions,
                observation_coverage_ratio=a.data_quality_freshness.observation_coverage_ratio,
                trade_frequency_20s=tf20,
                median_turnover_20s_tnd=med_t,
                missing_open_sessions_60s=miss60,
                executable_feasible=exec_ok,
                executable_net_return_pct=exec_net,
                mark_to_mark_net_return_pct=m2m_net,
                allocated_weight_pct=alloc_weight_pct,
                is_sparse_at_decision=is_sparse,
                is_frequent_benchmark_at_decision=is_bench,
                cohorts=cohorts,
            )
            sp_rows.append(row_sp)
            if b_rows is not None:
                b_rows.append(row_sp)

        return sp_rows, b_rows, base_rep, computed_cohorts

    for idx in eval_indices:
        sp_raw_slice, base_slice, raw_base_rep, raw_cohorts = _run_one_slice(
            idx, bars_prep, raw_bar_map, with_hb=False
        )
        sparse_raw_obs.extend(sp_raw_slice)
        if base_slice is not None:
            baseline_obs.extend(base_slice)

        if hb_bars:
            sp_hb_slice, _, _, _ = _run_one_slice(
                idx,
                merged_bars,
                merged_bar_map,
                with_hb=True,
                base_rep_override=raw_base_rep,
                cohorts_by_inst_override=raw_cohorts,
            )
            sparse_hb_obs.extend(sp_hb_slice)
        else:
            sparse_hb_obs.extend(sp_raw_slice)

    overall_base = _aggregate_metrics("Baseline", baseline_obs, use_baseline=True)
    overall_sp_raw = _aggregate_metrics(
        "sparse_research_v1 (raw)", sparse_raw_obs, use_baseline=False
    )
    overall_sp_hb = _aggregate_metrics(
        "sparse_research_v1 (H/B recovered)", sparse_hb_obs, use_baseline=False
    )

    cohort_comp: dict[str, dict[str, ModelBenchmarkMetrics]] = {}
    for cohort in COHORT_NAMES:
        c_base = [o for o in baseline_obs if cohort in o.cohorts]
        c_raw = [o for o in sparse_raw_obs if cohort in o.cohorts]
        c_hb = [o for o in sparse_hb_obs if cohort in o.cohorts]
        cohort_comp[cohort] = {
            "Baseline": _aggregate_metrics(f"Baseline [{cohort}]", c_base, use_baseline=True),
            "sparse_research_v1_raw": _aggregate_metrics(
                f"sparse_research_v1 (raw) [{cohort}]", c_raw, use_baseline=False
            ),
            "sparse_research_v1_hb": _aggregate_metrics(
                f"sparse_research_v1 (H/B) [{cohort}]", c_hb, use_baseline=False
            ),
        }

    notes = [
        f"Evaluated {len(eval_dates)} retrospective {forward_horizon_sessions}-session cohorts with {step_sessions}-session spacing; overlapping={step_sessions < forward_horizon_sessions}.",
        "Execution requires next-open entry and precommitted exact horizon-close exit, whole-slice capacity at both ends and slippage prices inside observed bars; costs and participation come from the reported frozen config.",
        "Precision, false-positive rate and mean return share the executable-known selected sample; missing or unfillable outcomes are excluded with explicit counts, not counted as losses. Missed opportunities use executable winners only.",
        "Cumulative portfolio return and drawdown are unavailable: independent horizon outcomes cannot be compounded without a non-overlapping cash/share timeline and shared capacity accounting. Exposure is descriptive per-cohort allocation only.",
        "Archive EOD replay assumes availability for absent timestamps; this does not certify historical publication or ingestion availability. Ex-post cohorts are diagnostic only; inspected outcomes are not an independent holdout.",
        f"Universe={universe}; baseline and sparse median-turnover requirement={threshold} TND.",
    ]
    return WalkForwardBenchmarkReport(
        model_version=SPARSE_OPPORTUNITY_MODEL_VERSION,
        config_sha256=cfg.config_sha256(),
        evaluation_dates=eval_dates,
        forward_horizon_sessions=forward_horizon_sessions,
        step_sessions=step_sessions,
        baseline_metrics=overall_base,
        sparse_raw_metrics=overall_sp_raw,
        sparse_hb_recovered_metrics=overall_sp_hb,
        cohort_comparison=cohort_comp,
        hb_recovered_bars_count=len(hb_bars),
        notes=notes,
        universe=universe,
    )


def run_benchmark_from_data_dir(
    processed_dir: Path,
    *,
    staging_dir: Path | None = None,
    config_path: Path | None = None,
    forward_horizon_sessions: int = 10,
    step_sessions: int = 10,
    universe: str = "FULL_BVMT",
) -> WalkForwardBenchmarkReport:
    """Convenience read-only loader for running the Phase 5 benchmark against an official data dir."""
    bars = read_bars_csv(processed_dir / "daily_bars.canonical.csv")
    master = read_instrument_master(processed_dir / "instrument_master.csv")
    cal = read_exchange_calendar(processed_dir / "exchange_calendar.csv")
    rej_paths = [
        p
        for p in (processed_dir / "rejections.json", processed_dir / "rejected_rows.csv")
        if p.is_file()
    ]
    sector_map = (
        load_emetteur_sector_map(staging_dir / "mapping_emetteur.json")
        if staging_dir is not None
        else {}
    )
    cfg = load_frozen_sparse_research_config(config_path)
    return run_walk_forward_generalization_benchmark(
        master,
        cal,
        bars,
        config=cfg,
        rejections_paths=rej_paths,
        sector_by_instrument=sector_map,
        forward_horizon_sessions=forward_horizon_sessions,
        step_sessions=step_sessions,
        universe=universe,
    )
