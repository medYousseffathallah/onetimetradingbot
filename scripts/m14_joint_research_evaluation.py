"""Hash-addressed retrospective M14 correctness reruns; never loads an account."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from statistics import median, quantiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bvmt.calendar import read_exchange_calendar, read_instrument_master  # noqa: E402
from bvmt.challenge_universe import is_in_challenge_universe  # noqa: E402
from bvmt.data import read_bars_csv  # noqa: E402
from bvmt.research_identity import (  # noqa: E402
    canonicalize_research_identity,
    challenge_membership_accounting,
)
from bvmt.sparse_generalization import (  # noqa: E402
    _compute_forward_outcomes,
    prepare_pit_calendar_and_bars,
    run_walk_forward_generalization_benchmark,
)
from bvmt.sparse_research import load_frozen_sparse_research_config  # noqa: E402
from bvmt.strategies import (  # noqa: E402
    DEFAULT_LAB_CONFIG,
    STRATEGY_IDS,
    _metrics,
    _simulate,
    _targets,
    evaluate_strategy_suite,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sparse", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "data/processed/bvmt_official_2026"
    paths = [
        *folder.glob("*.csv"),
        *(
            Path(module.__file__).resolve()
            for name, module in tuple(sys.modules.items())
            if name.startswith("bvmt")
            and getattr(module, "__file__", None)
            and Path(module.__file__).suffix == ".py"
        ),
        *ROOT.glob("configs/*.json"),
        Path(__file__).resolve(),
    ]
    manifest = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}
    experiment = hashlib.sha256(
        json.dumps([manifest, args.sparse], sort_keys=True).encode()
    ).hexdigest()[:16]
    output = ROOT / f"artifacts/m14-joint/corrected-{experiment}.json"
    if output.exists():
        print(f"Immutable result already exists: {output}")
        return 0
    raw_bars = read_bars_csv(folder / "daily_bars.canonical.csv")
    raw_master = read_instrument_master(folder / "instrument_master.csv")
    raw_cal = read_exchange_calendar(folder / "exchange_calendar.csv")
    projection = canonicalize_research_identity(raw_master, raw_bars)
    master = list(projection.instruments)
    cal, bars = prepare_pit_calendar_and_bars(raw_cal, list(projection.bars))
    results = {}
    for cutoff in (date(2026, 11, 6), date(2026, 11, 10)):
        for scope in ("FULL_BVMT", "TUNIS_BOURSE_CHALLENGE"):
            selected_master = [
                r
                for r in master
                if scope == "FULL_BVMT"
                or is_in_challenge_universe(r.instrument_id, r.isin, r.symbol)
            ]
            ids = {r.instrument_id for r in selected_master}
            selected_bars = [b for b in bars if b.session_date <= cutoff and b.instrument_id in ids]
            selected_cal = [s for s in cal if s.session_date <= cutoff]
            key = f"{scope}_{cutoff}"
            suite = evaluate_strategy_suite(selected_bars, selected_master, selected_cal)
            results[key] = {"suite": suite}
            print(key, "suite complete", flush=True)
            if cutoff == date(2026, 11, 10):
                sessions = [s.session_date for s in selected_cal if s.is_open]
                by_date = {d: {} for d in sessions}
                for bar in selected_bars:
                    by_date[bar.session_date][bar.instrument_id] = bar
                closes = {s.session_date: s.closes_at for s in selected_cal}
                features = {
                    d: _metrics(sessions[: i + 1], by_date, selected_master, closes[d])
                    for i, d in enumerate(sessions)
                    if i >= 60
                }
                phase_results = {}
                for strategy in STRATEGY_IDS:
                    phases = {}
                    for cadence in (5, 10, 20):
                        cfg = replace(DEFAULT_LAB_CONFIG, rebalance_every_sessions=cadence)
                        returns = [
                            _simulate(
                                strategy,
                                sessions,
                                by_date,
                                features,
                                cfg,
                                decision_start=cfg.warmup_sessions - 1 + offset,
                            ).summary["liquidated_return_pct"]
                            for offset in range(cadence)
                        ]
                        quartiles = quantiles(returns, n=4, method="inclusive")
                        phases[str(cadence)] = {
                            "all_phases": returns,
                            "median": median(returns),
                            "min": min(returns),
                            "max": max(returns),
                            "iqr": quartiles[2] - quartiles[0],
                        }
                    phase_results[strategy] = phases
                results[key]["phase_sensitivity"] = phase_results
                bar_map = {(b.instrument_id, b.session_date): b for b in selected_bars}
                sparse_config = load_frozen_sparse_research_config()
                sparse_config = replace(
                    sparse_config,
                    slippage_bps=DEFAULT_LAB_CONFIG.execution.slippage_bps,
                    buy_fee_rate=DEFAULT_LAB_CONFIG.execution.commission_bps / 10000,
                    sell_fee_rate=DEFAULT_LAB_CONFIG.execution.commission_bps / 10000,
                    liquidity_participation_cap=DEFAULT_LAB_CONFIG.execution.max_volume_participation,
                )
                known_at_decision = features[sessions[60]]
                initial_ids = [
                    m.instrument_id
                    for m in sorted(
                        known_at_decision, key=lambda m: (-m.turnover, m.instrument_id)
                    )[:10]
                ]
                selection_metrics = {}
                for strategy in STRATEGY_IDS:
                    selected_count = known_count = positive = executable_winners = missed = 0
                    for index in range(60, len(sessions) - 10, 15):
                        metrics = features[sessions[index]]
                        picks = _targets(strategy, metrics, DEFAULT_LAB_CONFIG, initial_ids)
                        selected_count += len(picks)
                        for metric in metrics:
                            feasible, net, _ = _compute_forward_outcomes(
                                metric.instrument_id,
                                sessions[index],
                                None,
                                sessions[index + 1 : index + 11],
                                bar_map,
                                sparse_config,
                                DEFAULT_LAB_CONFIG.execution.initial_cash_tnd
                                * DEFAULT_LAB_CONFIG.target_weight,
                            )
                            if feasible and net is not None:
                                if net >= 2:
                                    executable_winners += 1
                                    missed += metric.instrument_id not in picks
                                if metric.instrument_id in picks:
                                    known_count += 1
                                    positive += net > 0
                    selection_metrics[strategy] = {
                        "selected_count": selected_count,
                        "executable_known_count": known_count,
                        "unevaluated_count": selected_count - known_count,
                        "top_k_precision": positive / known_count if known_count else None,
                        "false_positive_rate": (known_count - positive) / known_count
                        if known_count
                        else None,
                        "liquidity_feasibility": known_count / selected_count
                        if selected_count
                        else None,
                        "missed_opportunity_rate": missed / executable_winners
                        if executable_winners
                        else None,
                        "winner_definition": "executable 10-session net return >=2%; diagnostic only, not a tuned selection threshold",
                        "capital_slice_tnd": str(
                            DEFAULT_LAB_CONFIG.execution.initial_cash_tnd
                            * DEFAULT_LAB_CONFIG.target_weight
                        ),
                        "execution_config": sparse_config.to_dict(),
                    }
                results[key]["selection_diagnostics"] = selection_metrics
                results[key]["without_sotetel"] = evaluate_strategy_suite(
                    [b for b in selected_bars if b.instrument_id != "SOTETEL"],
                    [r for r in selected_master if r.instrument_id != "SOTETEL"],
                    selected_cal,
                )
                if args.sparse:
                    # H=10, step=15 yields disjoint forward labels. No parameter fitting.
                    sparse = run_walk_forward_generalization_benchmark(
                        selected_master,
                        selected_cal,
                        selected_bars,
                        forward_horizon_sessions=10,
                        step_sessions=15,
                        universe=scope,
                    )
                    results[key]["sparse_corrected_evaluation"] = sparse.to_dict()
            output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": f"m14_correctness_{experiment}",
        "status": "RETROSPECTIVE_CONTAMINATED_RESEARCH_ONLY",
        "promotion_eligible": False,
        "availability_policy": "Explicit synthetic EOD replay bounds over unknown publication/ingestion history; original source values retained unchanged on disk. Not certified PIT.",
        "holdout_status": "INVALIDATED_AS_PRISTINE: inspected November9-10 and ICF outcomes; no independent holdout claimed",
        "model_formula_version": "bounded_risk_ratio_v2",
        "trial_disclosure": "Nine frozen hypotheses, two cutoffs/scopes; all 5/10/20 rebalance phases; ex-SOTETEL. No fitted parameters or winner-based tuning.",
        "source_hashes": manifest,
        "config": asdict(DEFAULT_LAB_CONFIG),
        "challenge_membership": challenge_membership_accounting(master),
        "results": results,
    }
    assert all(sha(ROOT / name) == digest for name, digest in manifest.items()), (
        "Inputs/code changed during evaluation; discard mixed run"
    )
    with output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, default=str, indent=2)
    print(output, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
