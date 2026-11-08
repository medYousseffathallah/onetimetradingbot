"""Hand-accounted strategy ledger, temporal isolation and registry contracts."""

from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.calendar import ExchangeSession, InstrumentRecord
from bvmt.data import DailyBar
from bvmt.execution import BacktestConfig
from bvmt.strategies import (
    STRATEGY_IDS,
    StrategyLabConfig,
    _Metrics,
    _metrics,
    _simulate,
    _targets,
    audit_historical_coverage_and_blockers,
    evaluate_strategy_suite,
)

D = Decimal


def sample(count: int = 80) -> tuple[list[DailyBar], list[InstrumentRecord], list[ExchangeSession]]:
    days = [date(2026, 1, 2) + timedelta(days=i) for i in range(count)]
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    bars = [
        DailyBar(
            "X",
            "X",
            day,
            D(10),
            D(12),
            D(8),
            D(10),
            10000,
            D(100000),
            "traded",
            "fixture",
            stamp,
            stamp,
        )
        for day in days
    ]
    master = [
        InstrumentRecord(
            "X", None, "X", days[0], None, days[0], None, "principal", "TND", "fixture"
        )
    ]
    calendar = [
        ExchangeSession(
            day,
            True,
            "regular",
            datetime.combine(day, datetime.min.time(), UTC),
            datetime.combine(day, datetime.max.time(), UTC),
            "Africa/Tunis",
            "fixture",
        )
        for day in days
    ]
    return bars, master, calendar


def test_cash_and_identical_windows() -> None:
    bars, master, calendar = sample()
    suite = evaluate_strategy_suite(bars, master, calendar)
    reports = suite["reports"]
    assert [r["strategy_id"] for r in reports] == list(STRATEGY_IDS)
    cash = reports[0]
    for field in (
        "net_return_pct",
        "liquidated_return_pct",
        "trade_count",
        "order_count",
        "total_fees_tnd",
        "avg_cash_utilization_pct",
    ):
        assert cash[field] == 0
    assert all(r["session_count"] == 80 for r in reports)
    assert all(r["sample_Classification"] == "exploratory" for r in reports)
    assert all(r["promotion_status"] == "research_only_requires_human_approval" for r in reports)
    assert all(len(r["fee_and_liquidity_sensitivity"]["scenarios"]) == 9 for r in reports)
    assert suite["ml_promotion_gate"]["eligible"] is False
    for r in reports:
        assert r["benchmark_return_pct"] == reports[2]["net_return_pct"]
        assert len(r["equity_curve"]) == 80
        assert r["walk_forward"]["total_folds"] == 1
        fold = r["walk_forward"]["folds"][0]
        assert fold["train_end"] < fold["test_start"]
        assert fold["test_sessions"] == 19
        for point in r["equity_curve"]:
            assert point["cash_tnd"] + point["holdings_value_tnd"] == pytest.approx(
                point["total_equity_tnd"], abs=1e-5
            )


def test_hand_accounted_next_open_and_terminal_fee() -> None:
    bars, _, _ = sample(63)
    days = [b.session_date for b in bars]
    metrics = [_Metrics("X", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)]
    cfg = StrategyLabConfig(
        execution=BacktestConfig(
            initial_cash_tnd=D(1000), max_position_weight=D(".1"), carry_pending_orders=False
        ),
        target_weight=D(".085"),
    )
    result = _simulate(
        STRATEGY_IDS[3],
        days,
        {b.session_date: {"X": b} for b in bars},
        {days[60]: metrics},
        cfg,
        decision_start=60,
    )
    assert result.fills == [
        {
            "instrument_id": "X",
            "decision_session": days[60].isoformat(),
            "session_date": days[61].isoformat(),
            "side": "buy",
            "quantity": 8,
            "price_tnd": "10.010",
            "fee_tnd": "0.400",
        }
    ]
    assert result.curve[60]["holdings_value_tnd"] == 0
    assert result.curve[61]["cash_tnd"] == 919.52
    assert result.summary["net_return_pct"] == -0.048
    assert result.summary["liquidated_return_pct"] == -0.088
    assert result.summary["hit_rate_pct"] == 0
    assert result.summary["win_loss_Init_summary"]["losing_positions"] == 1


@pytest.mark.parametrize("change", ["zero", "suspended", "missing", "out_of_range"])
def test_unexecutable_next_bar_expires(change: str) -> None:
    bars, _, _ = sample(63)
    days = [b.session_date for b in bars]
    today = {b.session_date: {"X": b} for b in bars}
    bar = bars[61]
    if change == "zero":
        today[days[61]]["X"] = replace(bar, volume_shares=0, status="untraded", turnover_tnd=D(0))
    elif change == "suspended":
        today[days[61]]["X"] = replace(bar, status="suspended", volume_shares=0, turnover_tnd=D(0))
    elif change == "missing":
        today[days[61]] = {}
    else:
        today[days[61]]["X"] = replace(bar, high=D(10), low=D(10))
    result = _simulate(
        STRATEGY_IDS[3],
        days,
        today,
        {days[60]: [_Metrics("X", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)]},
        StrategyLabConfig(),
        decision_start=60,
    )
    assert result.fills == []
    assert result.summary["order_count"] == 1


def test_capacity_and_cash_cap() -> None:
    bars, _, _ = sample(63)
    days = [b.session_date for b in bars]
    bars[61] = replace(bars[61], volume_shares=25)
    result = _simulate(
        STRATEGY_IDS[3],
        days,
        {b.session_date: {"X": b} for b in bars},
        {days[60]: [_Metrics("X", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)]},
        StrategyLabConfig(),
        decision_start=60,
    )
    assert result.fills[0]["quantity"] == 2
    assert all(p["cash_tnd"] >= 0 for p in result.curve)
    assert result.summary["max_single_stock_weight_pct"] <= 10


def test_ranking_regime_and_hurdles() -> None:
    cfg = StrategyLabConfig(top_k=1)
    low = _Metrics("LOW", 0.02, 0.1, 0.02, 1, 10000, 0.03, 0.25, 0.4)
    high = _Metrics("HIGH", 0.04, 0.05, 0.02, 1, 10000, 0.001, 0.02, 0.9)
    assert list(_targets(STRATEGY_IDS[3], [low, high], cfg, [])) == ["HIGH"]
    assert list(_targets(STRATEGY_IDS[4], [low, high], cfg, [])) == ["LOW"]
    assert list(_targets(STRATEGY_IDS[5], [low, high], cfg, [])) == ["HIGH"]
    assert list(_targets(STRATEGY_IDS[7], [low, high], cfg, [])) == ["HIGH"]
    assert _targets(STRATEGY_IDS[6], [replace(high, turnover=4999)], cfg, []) == {}
    assert _targets(STRATEGY_IDS[6], [replace(high, frequency=0.59)], cfg, []) == {}
    assert _targets(STRATEGY_IDS[6], [replace(high, mom20=0.014)], cfg, []) == {}
    bear = replace(low, mom20=-0.20)
    assert _targets(STRATEGY_IDS[8], [bear, high], cfg, []) == {"HIGH": D(".0425")}
    assert _targets(STRATEGY_IDS[8], [bear, replace(high, drawdown=0.11)], cfg, []) == {}


def test_features_prefix_missing_and_future_independence() -> None:
    bars, master, _ = sample(80)
    days = [b.session_date for b in bars]
    by_date = {b.session_date: {"X": b} for b in bars}
    before = _metrics(days[:61], by_date, master)
    by_date[days[79]]["X"] = replace(bars[-1], close=D(11))
    assert _metrics(days[:61], by_date, master) == before
    by_date[days[20]] = {}
    assert _metrics(days[:61], by_date, master) == []


def test_deterministic_hash_and_config_validation() -> None:
    bars, master, calendar = sample()
    first = evaluate_strategy_suite(bars, master, calendar)
    assert first == evaluate_strategy_suite(list(reversed(bars)), master, calendar)
    other = evaluate_strategy_suite(
        bars, master, calendar, config=StrategyLabConfig(rebalance_every_sessions=20)
    )
    assert first["config_hash"] != other["config_hash"]
    with pytest.raises(ValueError):
        StrategyLabConfig(target_weight=D(".11"))
    with pytest.raises(ValueError):
        evaluate_strategy_suite(*sample(61))
    assert asdict(StrategyLabConfig())["execution"]["max_position_weight"] == D(".10")


def test_absent_history_audit_is_explicit(tmp_path: Path) -> None:
    audit = audit_historical_coverage_and_blockers(tmp_path / "missing.ndjson", tmp_path)
    assert set(audit["coverage_2020_2026"]) == {str(y) for y in range(2020, 2027)}
    assert all(not row["daily_ohlcv_available"] for row in audit["coverage_2020_2026"].values())
    assert audit["retrieved_at"] is None
    assert audit["canonical_checksum_matches"] is None
    assert audit["corporate_actions_available"] is False
    assert audit["legacy_zip_access"]["reported_response_bytes"] is None


def test_seven_folds_on_194_sessions() -> None:
    suite = evaluate_strategy_suite(*sample(194))
    for report in suite["reports"]:
        assert report["walk_forward"]["total_folds"] == 7
        folds = report["walk_forward"]["folds"]
        assert all(a["test_end"] < b["test_start"] for a, b in zip(folds, folds[1:], strict=False))
        assert report["is_statistically_conclusive"] is False


def test_known_late_publication_and_dated_membership_are_excluded() -> None:
    bars, master, _ = sample()
    days = [b.session_date for b in bars]
    by_date = {b.session_date: {"X": b} for b in bars}
    by_date[days[60]]["X"] = replace(
        bars[60], published_at=datetime.combine(days[61], datetime.min.time(), UTC)
    )
    assert _metrics(days[:61], by_date, master) == []
    by_date[days[60]]["X"] = bars[60]
    assert _metrics(days[:61], by_date, [replace(master[0], listed_to=days[59])]) == []
    assert _metrics(days[:61], by_date, [replace(master[0], market_segment="surveillance")]) == []
    for segment in ("principal_continu", "principal_fixing"):
        assert len(_metrics(days[:61], by_date, [replace(master[0], market_segment=segment)])) == 1


def test_market_drift_is_reported_without_same_close_liquidation() -> None:
    bars, _, _ = sample(63)
    days = [b.session_date for b in bars]
    bars[62] = replace(bars[62], open=D(20), close=D(20), high=D(21), low=D(19))
    cfg = StrategyLabConfig(
        execution=BacktestConfig(
            initial_cash_tnd=D(1000), max_position_weight=D(".1"), carry_pending_orders=False
        )
    )
    result = _simulate(
        STRATEGY_IDS[3],
        days,
        {b.session_date: {"X": b} for b in bars},
        {days[60]: [_Metrics("X", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)]},
        cfg,
        decision_start=60,
    )
    assert len(result.fills) == 1
    assert result.summary["max_single_stock_weight_pct"] > 10
    assert result.summary["diagnostics"]["concentration_cap_compliant"] is False
    assert result.summary["diagnostics"]["market_drift_breach_sessions"] == 1


def test_offline_writer_and_provenance_timestamp_separation(tmp_path: Path) -> None:
    import json

    from bvmt.data import format_canonical_csv
    from bvmt.strategies import generate_experiment_registry

    bars, master, calendar = sample()
    # Use public reader-compatible fixture exports, retaining real source claims as claims.
    import csv

    for name, records in (("instrument_master.csv", master), ("exchange_calendar.csv", calendar)):
        rows = [
            {
                k: ("" if v is None else v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in asdict(r).items()
            }
            for r in records
        ]
        with (tmp_path / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (tmp_path / "daily_bars.canonical.csv").write_text(format_canonical_csv(bars), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "provenance": {
                    "source_url": "https://example.test/official.ndjson",
                    "source_retrieved_at": None,
                    "processed_at": "2026-11-07T00:00:00+00:00",
                    "older_history_access_user_reported": "Legacy ZIP requests returned zero bytes",
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "provenance.json").write_text(
        json.dumps({"retrieved_at": "2026-11-07T00:00:00+00:00"}), encoding="utf-8"
    )
    archive = tmp_path / "archive.ndjson"
    archive.write_text(
        json.dumps({"seance": "2025-12-31", "data": [{"quantites": None}]}) + "\n", encoding="utf-8"
    )
    output = tmp_path / "registry.json"
    result = generate_experiment_registry(tmp_path, archive, output)
    audit = result["historical_audit"]
    assert audit["retrieved_at"] is None
    assert audit["processed_at"] == "2026-11-07T00:00:00+00:00"
    assert audit["coverage_2020_2026"]["2025"]["status"] == "monthly_summaries_not_daily"
    assert audit["coverage_2020_2026"]["2026"]["canonical_sessions"] == 80
    assert audit["instrument_count"] == 1
    assert audit["legacy_zip_access"]["reported_response_bytes"] == 0
    first = output.read_bytes()
    generate_experiment_registry(tmp_path, archive, output)
    assert output.read_bytes() == first


@pytest.mark.parametrize(
    "exit_price,expected_return,winning", [(D(10), -0.096, 0), (D(11), 0.6992, 1)]
)
def test_sold_position_reconciles_both_commissions(
    exit_price: Decimal, expected_return: float, winning: int
) -> None:
    bars, _, _ = sample(63)
    days = [b.session_date for b in bars]
    bars[62] = replace(bars[62], open=exit_price, close=exit_price)
    cfg = StrategyLabConfig(
        execution=BacktestConfig(
            initial_cash_tnd=D(1000), max_position_weight=D(".1"), carry_pending_orders=False
        ),
        rebalance_every_sessions=1,
    )
    result = _simulate(
        STRATEGY_IDS[3],
        days,
        {b.session_date: {"X": b} for b in bars},
        {days[60]: [_Metrics("X", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)], days[61]: []},
        cfg,
        decision_start=60,
    )
    assert [f["side"] for f in result.fills] == ["buy", "sell"]
    assert result.summary["net_return_pct"] == expected_return
    assert result.summary["liquidated_return_pct"] == expected_return
    assert result.curve[-1]["holdings_value_tnd"] == 0
    assert result.summary["win_loss_Init_summary"]["winning_positions"] == winning
    assert result.summary["hit_rate_pct"] == winning * 100


def test_initial_sleeves_are_capped_and_ties_are_stable() -> None:
    cfg = StrategyLabConfig()
    keys = [f"S{i}" for i in range(10)]
    assert set(_targets(STRATEGY_IDS[1], [], cfg, keys).values()) == {D(".1")}
    assert set(_targets(STRATEGY_IDS[2], [], cfg, keys).values()) == {D(".1")}
    assert _targets(STRATEGY_IDS[1], [], cfg, []) == {}
    one = _Metrics("Z", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)
    assert list(
        _targets(STRATEGY_IDS[3], [one, replace(one, instrument_id="A")], replace(cfg, top_k=1), [])
    ) == ["A"]


def test_risk_metrics_cash_and_benchmark_conventions() -> None:
    from bvmt.strategies import _bootstrap_interval

    suite = evaluate_strategy_suite(*sample(194))
    assert suite["audit_summary"]["model_g_promotion_eligible"] is False
    assert len(suite["audit_summary"]["key_findings"]) == 10
    assert suite["robustness_v2"]["version"] == "2.0"
    b, c = suite["reports"][1:3]
    for report in suite["reports"]:
        risk = report["risk_normalized_metrics"]
        assert risk["active_session_count"] == 134
        points = report["equity_curve"][60:]
        util = sum(p["holdings_value_tnd"] / p["total_equity_tnd"] * 100 for p in points) / 134
        assert risk["active_cash_utilization_pct"] == round(util, 6)
        for label, field in (
            ("return", "net_return_pct"),
            ("liquidated_return", "liquidated_return_pct"),
            ("max_drawdown", "max_drawdown_pct"),
        ):
            assert risk[f"exposure_normalized_{label}_pct"] == (
                round(report[field] / (risk["active_cash_utilization_pct"] / 100), 6)
                if util
                else 0.0
            )
        for key, bench in (("b", b), ("c", c)):
            assert risk[f"excess_vs_{key}_marked_pct"] == round(
                report["net_return_pct"] - bench["net_return_pct"], 6
            )
            assert risk[f"excess_vs_{key}_liquidated_pct"] == round(
                report["liquidated_return_pct"] - bench["liquidated_return_pct"], 6
            )
        ci = risk["bootstrap_return_ci_95"]
        assert ci["lower_pct"] <= ci["upper_pct"]
        assert ci["resamples"] == 500 and ci["block_size"] == 5
    cash = suite["reports"][0]["risk_normalized_metrics"]
    assert cash["top_winner_instrument_id"] is None
    assert cash["realized_annualized_volatility_pct"] == 0
    assert cash["ex_top_winner_net_return_pct"] == 0
    assert _bootstrap_interval([1.0] * 10)["lower_pct"] == 0
    factors = [1.01, 0.97, 1.04, 1.02, 0.99] * 4
    assert _bootstrap_interval(factors) == _bootstrap_interval(factors)


def test_continuous_trim_is_later_and_does_not_guarantee_hard_cap() -> None:
    bars, _, _ = sample(65)
    days = [b.session_date for b in bars]
    for i in range(62, 65):
        bars[i] = replace(bars[i], open=D(20), close=D(20), high=D(21), low=D(19))
    cfg = StrategyLabConfig(
        execution=BacktestConfig(
            initial_cash_tnd=D(1000), max_position_weight=D(".1"), carry_pending_orders=False
        )
    )
    args = (
        STRATEGY_IDS[3],
        days,
        {b.session_date: {"X": b} for b in bars},
        {days[60]: [_Metrics("X", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)]},
        cfg,
    )
    baseline = _simulate(*args, decision_start=60)
    trimmed = _simulate(*args, decision_start=60, continuous_trim=True)
    assert len(baseline.fills) == 1
    assert trimmed.fills[1]["side"] == "sell"
    assert trimmed.fills[1]["decision_session"] == days[62].isoformat()
    assert trimmed.fills[1]["session_date"] == days[63].isoformat()
    assert trimmed.summary["diagnostics"]["market_drift_breach_sessions"] == 1
    assert trimmed.summary["max_single_stock_weight_pct"] > 10


def test_winner_pnl_includes_open_positions_and_fees() -> None:
    from bvmt.strategies import _winner_pnl

    bars, _, _ = sample(63)
    days = [b.session_date for b in bars]
    bars[-1] = replace(bars[-1], open=D(11), close=D(11))
    config = StrategyLabConfig(
        execution=BacktestConfig(
            initial_cash_tnd=D(1000), max_position_weight=D(".1"), carry_pending_orders=False
        )
    )
    run = _simulate(
        STRATEGY_IDS[3],
        days,
        {b.session_date: {"X": b} for b in bars},
        {days[60]: [_Metrics("X", 0.1, 0.2, 0.01, 1, 100000, 0.01, 0.03, 0.7)]},
        config,
        decision_start=60,
    )
    key, pnl = _winner_pnl(run)
    assert key == "X"
    assert pnl == pytest.approx(run.summary["net_return_pct"] * 10)


def test_equal_budget_comparison_is_an_independent_resimulation() -> None:
    bars, master, calendar = sample(80)
    # One rising, liquid instrument gives a hand-verifiable difference in share sizing.
    bars = [replace(b, close=D(10) + D(i) / 100) for i, b in enumerate(bars)]
    config = StrategyLabConfig(
        execution=BacktestConfig(
            initial_cash_tnd=D(10000), max_position_weight=D(".1"), carry_pending_orders=False
        )
    )
    suite = evaluate_strategy_suite(bars, master, calendar, config=config)
    days = [b.session_date for b in bars]
    by_date = {b.session_date: {"X": b} for b in bars}
    features = {d: _metrics(days[: i + 1], by_date, master) for i, d in enumerate(days) if i >= 60}
    independent = _simulate(
        STRATEGY_IDS[6],
        days,
        by_date,
        features,
        replace(config, top_k=10, target_weight=D(".095")),
        decision_start=60,
    )
    report = suite["reports"][6]
    risk = report["risk_normalized_metrics"]
    assert risk["equal_budget_10slot_net_return_pct"] == independent.summary["net_return_pct"]
    assert (
        risk["equal_budget_10slot_liquidated_return_pct"]
        == independent.summary["liquidated_return_pct"]
    )
    assert risk["equal_budget_10slot_max_drawdown_pct"] == independent.summary["max_drawdown_pct"]
    assert risk["equal_budget_10slot_active_utilization_pct"] > risk["active_cash_utilization_pct"]
    assert risk["top_winner_instrument_id"] == "X"
    assert risk["ex_top_winner_net_return_pct"] == 0
    b = suite["reports"][1]
    assert risk["cash_matched_benchmark_b_return_pct"] == pytest.approx(
        b["net_return_pct"]
        * risk["active_cash_utilization_pct"]
        / b["risk_normalized_metrics"]["active_cash_utilization_pct"],
        abs=1e-6,
    )
    assert risk["realized_annualized_volatility_pct"] > 0


def test_robustness_supports_lower_base_purchase_caps() -> None:
    config = StrategyLabConfig(
        execution=BacktestConfig(max_position_weight=D(".05"), carry_pending_orders=False),
        target_weight=D(".04"),
    )
    suite = evaluate_strategy_suite(*sample(80), config=config)
    # Equal-budget reruns explicitly use the requested 10% cap / 9.5% target;
    # the base run and its daily trims retain the user's lower purchase cap.
    assert (
        suite["reports"][3]["risk_normalized_metrics"]["equal_budget_10slot_active_utilization_pct"]
        > suite["reports"][3]["risk_normalized_metrics"]["active_cash_utilization_pct"]
    )
