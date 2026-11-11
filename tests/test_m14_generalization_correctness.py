"""Executable-outcome metrics must share denominators and honor the exit session."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from bvmt import sparse_generalization as generalization
from bvmt.calendar import ExchangeSession, InstrumentRecord
from bvmt.data import DailyBar
from bvmt.sparse_generalization import (
    ObservationOutcome,
    _aggregate_metrics,
    _compute_forward_outcomes,
)
from bvmt.sparse_research import SparseResearchConfig


def _bar(day, *, volume=10000, low="9", high="12", close="11"):
    stamp = datetime.combine(day, datetime.min.time(), UTC)
    return DailyBar(
        "ICF",
        "ICF",
        day,
        Decimal("10"),
        Decimal(high),
        Decimal(low),
        Decimal(close),
        volume,
        Decimal(volume) * 10,
        "traded",
        "fixture",
        stamp,
        stamp,
    )


def _outcomes(mapping, dates=(date(2026, 1, 5), date(2026, 1, 6))):
    return _compute_forward_outcomes(
        "ICF",
        date(2026, 1, 2),
        Decimal("10"),
        dates,
        mapping,
        SparseResearchConfig(),
        Decimal("500"),
    )


def test_missing_exact_horizon_exit_does_not_backfill_previous_close():
    first = _bar(date(2026, 1, 5))
    assert _outcomes({("ICF", first.session_date): first}) == (False, None, None)


def test_exit_capacity_must_cover_whole_position():
    entry = _bar(date(2026, 1, 5))
    exit_bar = _bar(date(2026, 1, 6), volume=10)
    ok, executable, diagnostic = _outcomes(
        {("ICF", entry.session_date): entry, ("ICF", exit_bar.session_date): exit_bar}
    )
    assert not ok and executable is None
    assert diagnostic is not None


def test_partial_entry_capacity_is_not_reported_as_full_target_slice():
    entry = _bar(date(2026, 1, 5), volume=10)
    exit_bar = _bar(date(2026, 1, 6))
    ok, executable, _ = _outcomes(
        {("ICF", entry.session_date): entry, ("ICF", exit_bar.session_date): exit_bar}
    )
    assert not ok and executable is None


def test_one_session_roundtrip_shares_one_participation_budget():
    bar = _bar(date(2026, 1, 5), volume=500)
    ok, executable, _ = _outcomes({("ICF", bar.session_date): bar}, (bar.session_date,))
    assert not ok and executable is None


def test_exit_slippage_must_be_inside_observed_range():
    entry = _bar(date(2026, 1, 5))
    exit_bar = _bar(date(2026, 1, 6), low="11", close="11")
    ok, executable, _ = _outcomes(
        {("ICF", entry.session_date): entry, ("ICF", exit_bar.session_date): exit_bar}
    )
    assert not ok and executable is None


def test_next_open_and_exact_horizon_costs_are_reproducible():
    entry, exit_bar = _bar(date(2026, 1, 5)), _bar(date(2026, 1, 6))
    ok, executable, _ = _outcomes(
        {("ICF", entry.session_date): entry, ("ICF", exit_bar.session_date): exit_bar}
    )
    assert ok
    expected = (
        float(
            Decimal("11")
            * Decimal(".998")
            * Decimal(".995")
            / (Decimal("10") * Decimal("1.002") * Decimal("1.005"))
            - 1
        )
        * 100
    )
    assert executable == pytest.approx(round(expected, 4))


def _observation(iid, *, selected=True, feasible=True, result=5.0, mark=5.0):
    return ObservationOutcome(
        "2026-01-02",
        iid,
        iid,
        True,
        True,
        selected,
        1,
        [],
        "FULL_RESEARCH_AVAILABLE",
        selected,
        10.0,
        False,
        0,
        1.0,
        1.0,
        Decimal("10000"),
        0,
        feasible,
        result,
        mark,
        10.0,
        False,
        True,
        [],
    )


def test_missing_and_unexecutable_outcomes_are_not_losses_or_successes():
    rows = [
        _observation("winner", result=5),
        _observation("loser", result=-3),
        _observation("unknown", feasible=False, result=None, mark=100),
        _observation("missed", selected=False, result=4),
        _observation("unfillable-missed", selected=False, feasible=False, result=None, mark=100),
    ]
    metrics = _aggregate_metrics("test", rows, use_baseline=False)
    assert metrics.selected_count == 3
    assert metrics.evaluated_selected_count == 2
    assert metrics.unevaluated_selected_count == 1
    assert metrics.executable_observation_count == 3
    assert metrics.top_k_candidate_precision == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.mean_forward_net_return_pct == 1.0
    assert metrics.missed_opportunity_rate == 0.5
    assert metrics.cumulative_portfolio_return_pct is None
    assert metrics.portfolio_max_drawdown_pct is None


def test_all_unknown_metrics_remain_unavailable():
    row = _observation("unknown", feasible=False, result=None, mark=None)
    metrics = _aggregate_metrics(
        "test", [row, replace(row, session_date="2026-01-03")], use_baseline=False
    )
    assert metrics.top_k_candidate_precision is None
    assert metrics.false_positive_rate is None
    assert metrics.mean_forward_net_return_pct is None
    assert metrics.missed_opportunity_rate is None


def _dataset():
    calendar, bars = [], []
    instruments = [
        InstrumentRecord(
            iid,
            isin,
            iid,
            date(2026, 1, 1),
            None,
            date(2026, 1, 1),
            None,
            "principal_continu",
            "TND",
            "fixture",
            True,
        )
        for iid, isin in [("ICF", "TN0003200755"), ("MONOPRIX", "TN0000000001")]
    ]
    for i in range(74):
        day = date(2026, 1, 2) + timedelta(days=i)
        stamp = datetime.combine(day, datetime.min.time(), UTC)
        calendar.append(
            ExchangeSession(
                day,
                True,
                "synthetic_daily",
                stamp,
                stamp + timedelta(hours=16),
                "Africa/Tunis",
                "fixture",
            )
        )
        for instrument in instruments:
            bar = _bar(day, high="30", close=str(Decimal("10") + Decimal(i) / 100))
            bars.append(
                replace(
                    bar,
                    instrument_id=instrument.instrument_id,
                    symbol=instrument.symbol,
                    isin=instrument.isin,
                )
            )
    return instruments, calendar, bars


def test_challenge_scope_and_equal_thresholds_reach_both_selectors(monkeypatch):
    instruments, calendar, bars = _dataset()
    observed_baseline, observed_sparse = [], []
    baseline_original = generalization.rank_session_baseline
    sparse_original = generalization.evaluate_sparse_market_research

    def baseline(*args, **kwargs):
        observed_baseline.append((kwargs["universe"], kwargs["min_median_turnover_tnd"]))
        return baseline_original(*args, **kwargs)

    def sparse(*args, **kwargs):
        observed_sparse.append(kwargs["universe"])
        report = sparse_original(*args, **kwargs)
        assert all(a.instrument_id == "ICF" for a in report.assessments)
        return report

    monkeypatch.setattr(generalization, "rank_session_baseline", baseline)
    monkeypatch.setattr(generalization, "evaluate_sparse_market_research", sparse)
    report = generalization.run_walk_forward_generalization_benchmark(
        instruments, calendar, bars, universe="TUNIS_BOURSE_CHALLENGE", forward_horizon_sessions=2
    )
    assert report.universe == "TUNIS_BOURSE_CHALLENGE"
    assert report.evaluation_version == "executable_cohort_evaluation_v2"
    assert observed_baseline and all(
        scope == "TUNIS_BOURSE_CHALLENGE" and threshold == Decimal("5000")
        for scope, threshold in observed_baseline
    )
    assert observed_sparse and set(observed_sparse) == {"TUNIS_BOURSE_CHALLENGE"}


def test_asymmetric_threshold_and_unknown_scope_are_rejected():
    instruments, calendar, bars = _dataset()
    with pytest.raises(ValueError, match="thresholds must match"):
        generalization.run_walk_forward_generalization_benchmark(
            instruments, calendar, bars, baseline_min_median_turnover_tnd=Decimal("1000")
        )
    with pytest.raises(ValueError, match="universe"):
        generalization.run_walk_forward_generalization_benchmark(
            instruments, calendar, bars, universe="guessed"
        )
