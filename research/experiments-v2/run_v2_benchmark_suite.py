"""Reproducible V2 Strategy, Baseline & Exit-Policy Benchmark Suite.

Executes bvmt_v2.backtester against the equity-only canonical V2 archive
(15,080 rows, 75 canonical ISINs, 202 sessions 2026-01-02..2026-11-18) under:
  1. STRICT_PIT_AVAILABILITY (Backtester.from_market(load_market()) as shipped)
  2. RETROSPECTIVE_EXPLORATORY (explicit unverified publication-clock & retrospective
     Challenge-42 membership assumption, matching legacy M14 comparison conditions
     without relabeling it as PIT-certified).

Saves immutable output to artifacts/v2/v2-benchmark-results.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, time
from decimal import Decimal as D
from pathlib import Path
from typing import Any

from bvmt_v2.backtester import EXIT_POLICIES, FAMILIES, Backtester
from bvmt_v2.market_data import load_market


def _to_json(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json(v) for v in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return _to_json(asdict(obj))
    if isinstance(obj, D):
        return format(obj, "f")
    return obj


def _exploratory_backtester(strict_bt: Backtester) -> Backtester:
    """Create explicit retrospective-exploratory clone using EOD session retrieval clock
    (16:00 UTC same session) and retrospective Challenge-42 membership for fair comparison
    against legacy Model G (never presented as PIT-certified)."""
    exp_rows: dict[str, dict[Any, Any]] = {}
    for inst, by_sess in strict_bt.rows.items():
        exp_rows[inst] = {
            sess: replace(bar, available_at=datetime.combine(sess, time(16), UTC))
            for sess, bar in by_sess.items()
        }
    exp_series = {
        inst: tuple(exp_rows[inst][s] for s in strict_bt.sessions if s in exp_rows[inst])
        for inst in strict_bt.series
    }
    return Backtester(
        sessions=strict_bt.sessions,
        series=exp_series,
        challenge=strict_bt.challenge,
        challenge_known_from=None,
        run_mode="RETROSPECTIVE_EXPLORATORY",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    market = load_market()
    strict_bt = Backtester.from_market(market)
    exp_bt = _exploratory_backtester(strict_bt)

    strict_runs: dict[str, dict[str, Any]] = {}
    for h in (5, 10, 20):
        strict_runs[f"H={h}"] = {
            fam: strict_bt.run(fam, h).model_dump(mode="json") for fam in FAMILIES
        }

    exploratory_runs: dict[str, dict[str, Any]] = {}
    exploratory_phases: dict[str, dict[str, Any]] = {}
    for h in (5, 10, 20):
        exploratory_runs[f"H={h}"] = {
            fam: exp_bt.run(fam, h).model_dump(mode="json") for fam in FAMILIES
        }
        exploratory_phases[f"H={h}"] = {
            fam: _to_json(exp_bt.phase_sensitivity(fam, h))
            for fam in ("BL-MOM20", "LEGACY-G-APPROX", "V2-D-MOM-RISK", "V2-F-LIQ-TREND")
        }

    slippage_t3_sensitivity = {
        "V2-D-MOM-RISK_H10_50bps_T0": exp_bt.run(
            "V2-D-MOM-RISK", 10, bps=D(50), settlement=0
        ).model_dump(mode="json"),
        "V2-D-MOM-RISK_H10_0bps_T3": exp_bt.run(
            "V2-D-MOM-RISK", 10, bps=D(0), settlement=3
        ).model_dump(mode="json"),
        "V2-F-LIQ-TREND_H10_50bps_T0": exp_bt.run(
            "V2-F-LIQ-TREND", 10, bps=D(50), settlement=0
        ).model_dump(mode="json"),
        "V2-F-LIQ-TREND_H10_0bps_T3": exp_bt.run(
            "V2-F-LIQ-TREND", 10, bps=D(0), settlement=3
        ).model_dump(mode="json"),
    }

    exit_comparisons = {
        inst: {
            pol: _to_json(cmp)
            for pol, cmp in exp_bt.compare_exit_policies(inst, horizon=10).items()
        }
        for inst in ("EURO-CYCLES", "DELICE_HOLDING", "MPBS")
    }

    out = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dataset": {
            "sessions_count": len(market.sessions),
            "first_session": market.sessions[0].isoformat(),
            "last_session": market.sessions[-1].isoformat(),
            "canonical_equities": len(market.instruments),
            "challenge_members": sum(1 for i in market.instruments.values() if i.challenge_member),
            "data_hash": strict_bt.data_hash,
            "source_hash": strict_bt.source_hash,
        },
        "families": list(FAMILIES),
        "exit_policies": list(EXIT_POLICIES),
        "strict_pit_runs": strict_runs,
        "retrospective_exploratory_runs": exploratory_runs,
        "retrospective_phase_sensitivity": exploratory_phases,
        "cost_and_settlement_sensitivity": slippage_t3_sensitivity,
        "exit_policy_comparisons_H10": exit_comparisons,
    }
    out_path = root / "artifacts/v2/v2-benchmark-results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("=== RETROSPECTIVE EXPLORATORY H=5, H=10, H=20 SUMMARY ===")
    for h_key in ("H=5", "H=10", "H=20"):
        print(f"--- {h_key} ---")
        for fam in FAMILIES:
            r = exploratory_runs[h_key][fam]
            print(
                f"{fam:16s} | net={str(r['net_return_pct']['value']):>8s}% | "
                f"alphaEW={str(r['alpha_vs_ew_pct']['value']):>8s}% | "
                f"maxDD={str(r['max_drawdown_pct']['value']):>7s}% | "
                f"top1Excl={str(r['top1_excluded_return_pct']['value']):>8s}% ({r['top1_excluded_instrument']}) | "
                f"util={str(r['active_utilization_pct']['value']):>6s}% | N={r['sample_count']}"
            )
    print("=== PHASE SENSITIVITY (H=10) ===")
    for fam, ps in exploratory_phases["H=10"].items():
        print(
            f"{fam:16s} | min={ps['minimum']['value']} | med={ps['median']['value']} | "
            f"max={ps['maximum']['value']} | IQR={ps['iqr_pp']['value']}"
        )
    print("=== SLIPPAGE 50bps & T+3 SETTLEMENT SENSITIVITY ===")
    for key, r in slippage_t3_sensitivity.items():
        print(
            f"{key:30s} | net={str(r['net_return_pct']['value'])}% | "
            f"maxDD={str(r['max_drawdown_pct']['value'])}%"
        )
    print("=== EXIT POLICY COMPARISON (EURO-CYCLES, H=10) ===")
    for pol in EXIT_POLICIES:
        ec = exit_comparisons["EURO-CYCLES"][pol]
        print(
            f"{pol:24s} | net={str(ec['net_return_pct']['value']):>8s}% | "
            f"retProf={str(ec['profit_retention_pct']['value']):>7s}% | "
            f"falseExit={str(ec['false_exit_rate_pct']['value']):>6s}% | "
            f"missedUp={str(ec['missed_subsequent_upside_pct']['value']):>6s}% | "
            f"samples={ec['sample_count']}/{ec['exit_opportunities']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
