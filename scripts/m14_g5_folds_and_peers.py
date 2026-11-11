"""M14 Supplementary Diagnostics: G5 Purged Walk-Forward Folds, SOTETEL Sensitivity,
Challenge vs Non-Challenge Displacement, and Anti-Hindsight Peer Cohort Statistics.

Strictly read-only over C:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit.
Writes exclusively to bvmt-gemini-dashboard/artifacts/m14/m14_g5_folds_and_peers.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any

STARTER_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = STARTER_ROOT / "artifacts" / "m14-joint" / "reproduced"

if str(STARTER_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(STARTER_ROOT / "src"))

from bvmt.calendar import (  # noqa: E402
    read_exchange_calendar,
    read_instrument_master,
)
from bvmt.challenge_universe import (  # noqa: E402
    get_challenge_universe,
    is_in_challenge_universe,
)
from bvmt.data import read_bars_csv  # noqa: E402
from bvmt.features import rank_session_baseline  # noqa: E402
from bvmt.sparse_generalization import prepare_pit_calendar_and_bars  # noqa: E402
from bvmt.sparse_research import (  # noqa: E402
    evaluate_sparse_market_research,
    load_emetteur_sector_map,
    load_frozen_sparse_research_config,
)
from bvmt.strategies import evaluate_strategy_suite  # noqa: E402


def _cutoff_for(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 15, 0, tzinfo=UTC)


def _norm(o: Any) -> Any:
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, dict):
        return {str(k): _norm(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_norm(x) for x in o]
    return o


def _extract_suite_rows(suite: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for r in suite["reports"]:
        rnm = r.get("risk_normalized_metrics", {})
        wf = r.get("walk_forward", {})
        rows.append(
            {
                "strategy_id": r["strategy_id"],
                "net_return_pct": r["net_return_pct"],
                "liquidated_return_pct": r["liquidated_return_pct"],
                "max_drawdown_pct": r["max_drawdown_pct"],
                "excess_vs_c_pct": r["excess_return_pct"],
                "avg_utilization_pct": rnm.get("active_cash_utilization_pct"),
                "cash_matched_b_pct": rnm.get("cash_matched_benchmark_b_return_pct"),
                "excess_vs_matched_b_pct": rnm.get("excess_vs_cash_matched_b_pct"),
                "top_winner_symbol": rnm.get("top_winner_instrument_id"),
                "top_winner_pnl_tnd": rnm.get("top_winner_net_pnl_tnd"),
                "ex_top_winner_pct": rnm.get("ex_top_winner_net_return_pct"),
                "wf_mean_liq_pct": wf.get("mean_liquidated_return_pct"),
                "wf_pos_folds": wf.get("positive_folds"),
                "wf_total_folds": wf.get("total_folds"),
                "trade_count": r["trade_count"],
                "total_fees_tnd": r["total_fees_tnd"],
            }
        )
    return rows


def main() -> None:
    data_dir = STARTER_ROOT / "data" / "processed" / "bvmt_official_2026"
    bars = read_bars_csv(data_dir / "daily_bars.canonical.csv")
    master_list = read_instrument_master(data_dir / "instrument_master.csv")
    master = {m.instrument_id: m for m in master_list}
    calendar = read_exchange_calendar(data_dir / "exchange_calendar.csv")
    sector_map = load_emetteur_sector_map(
        STARTER_ROOT / "data" / "staging" / "mapping_emetteur.json"
    )

    cal_pit, fixed_bars = prepare_pit_calendar_and_bars(calendar, bars)
    open_sessions = sorted(s.session_date for s in cal_pit if s.is_open)

    # 1. Exact G5 Purged + Embargoed Walk-Forward Folds over 196 open sessions
    # Reserve final 20 open sessions (idx 176..195) as untouched final holdout.
    holdout_start_idx = 176
    horizon_h = 10
    embargo_sessions = 2
    warmup_sessions = 60

    dev_folds: list[dict[str, Any]] = []
    for idx_num, dec_idx in enumerate(range(71, 162, 15), start=1):
        max_train_label_dec_idx = dec_idx - horizon_h - embargo_sessions
        eval_start_idx = dec_idx + 1
        eval_end_idx = dec_idx + horizon_h
        dev_folds.append(
            {
                "fold": idx_num,
                "train_feature_start": open_sessions[0].isoformat(),
                "warmup_end": open_sessions[warmup_sessions - 1].isoformat(),
                "max_train_decision_date": open_sessions[max_train_label_dec_idx].isoformat(),
                "max_train_label_bar_date": open_sessions[
                    max_train_label_dec_idx + horizon_h
                ].isoformat(),
                "purge_sessions": horizon_h,
                "embargo_sessions": embargo_sessions,
                "oos_decision_idx": dec_idx,
                "oos_decision_date": open_sessions[dec_idx].isoformat(),
                "oos_fill_open_date": open_sessions[eval_start_idx].isoformat(),
                "oos_eval_end_date": open_sessions[eval_end_idx].isoformat(),
                "strictly_before_holdout": eval_end_idx < holdout_start_idx,
            }
        )

    holdout_spec = {
        "holdout_start_idx": holdout_start_idx,
        "holdout_start_date": open_sessions[holdout_start_idx].isoformat(),
        "holdout_end_idx": len(open_sessions) - 1,
        "holdout_end_date": open_sessions[-1].isoformat(),
        "holdout_session_count": len(open_sessions) - holdout_start_idx,
        "holdout_block_1_decision_date": open_sessions[175].isoformat(),
        "holdout_block_1_eval_window": f"{open_sessions[176].isoformat()}..{open_sessions[185].isoformat()}",
        "holdout_block_2_decision_date": open_sessions[185].isoformat(),
        "holdout_block_2_eval_window": f"{open_sessions[186].isoformat()}..{open_sessions[195].isoformat()}",
        "nov06_session_idx": open_sessions.index(date(2026, 11, 6)),
        "nov09_session_idx": open_sessions.index(date(2026, 11, 9)),
        "nov10_session_idx": open_sessions.index(date(2026, 11, 10)),
    }

    # 2. SOTETEL leave-one-out on 196-session strategy suite
    bars_no_sotetel = [b for b in fixed_bars if b.instrument_id != "SOTETEL"]
    cal_196 = [s for s in cal_pit if s.session_date <= date(2026, 11, 10)]
    suite_no_sotetel = evaluate_strategy_suite(
        bars_no_sotetel,
        [m for m in master_list if m.instrument_id != "SOTETEL"],
        cal_196,
    )

    # 3. Challenge vs Non-Challenge Baseline & Sparse displacement on Nov 06 & Nov 10
    sparse_cfg = load_frozen_sparse_research_config(
        STARTER_ROOT / "configs" / "sparse_research_v1.json"
    )
    bars_nov06 = [b for b in fixed_bars if b.session_date <= date(2026, 11, 6)]
    cal_nov06 = [s for s in cal_pit if s.session_date <= date(2026, 11, 6)]

    base_nov06 = rank_session_baseline(
        master_list,
        cal_nov06,
        bars_nov06,
        _cutoff_for(date(2026, 11, 6)),
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )
    base_nov10 = rank_session_baseline(
        master_list,
        cal_196,
        fixed_bars,
        _cutoff_for(date(2026, 11, 10)),
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )

    def _top_displaced(candidates: list[Any], top_n: int = 15) -> list[dict[str, Any]]:
        rows = []
        for idx_rank, r in enumerate(candidates[:top_n], start=1):
            inst = master.get(r.instrument_id)
            sym = inst.symbol if inst else r.instrument_id
            in_ch = is_in_challenge_universe(r.instrument_id, inst.isin if inst else None, sym)
            rows.append(
                {
                    "rank": idx_rank,
                    "instrument_id": r.instrument_id,
                    "symbol": sym,
                    "in_challenge": in_ch,
                    "composite_score": float(r.composite_score),
                }
            )
        return rows

    # 4. Anti-Hindsight Peer Cohorts across Challenge Excluded Securities on Nov 06 -> Nov 10
    by_inst_sorted_closes: dict[str, list[tuple[date, Decimal]]] = {}
    for b in sorted(fixed_bars, key=lambda x: x.session_date):
        if b.volume_shares > 0:
            by_inst_sorted_closes.setdefault(b.instrument_id, []).append((b.session_date, b.close))

    def _last_close_on_or_before(inst_id: str, d: date) -> tuple[date | None, float | None]:
        pts = [x for x in by_inst_sorted_closes.get(inst_id, []) if x[0] <= d]
        if not pts:
            return None, None
        return pts[-1][0], float(pts[-1][1])

    sparse_nov06 = evaluate_sparse_market_research(
        master_list,
        cal_nov06,
        bars_nov06,
        _cutoff_for(date(2026, 11, 6)),
        config=sparse_cfg,
        baseline_report=base_nov06,
        sector_by_instrument=sector_map,
    )
    sp06_by_id = {a.instrument_id: a for a in sparse_nov06.assessments}
    b06_excl: dict[str, list[str]] = defaultdict(list)
    for e in base_nov06.exclusions:
        b06_excl[e.instrument_id].append(e.reason)
    b10_excl: dict[str, list[str]] = defaultdict(list)
    for e in base_nov10.exclusions:
        b10_excl[e.instrument_id].append(e.reason)

    challenge_peers_excluded_nov06: list[dict[str, Any]] = []
    for entry in get_challenge_universe():
        cid = entry.canonical_instrument_id
        if cid in b06_excl:
            d06, p06 = _last_close_on_or_before(cid, date(2026, 11, 6))
            d10, p10 = _last_close_on_or_before(cid, date(2026, 11, 10))
            _, p_oct20 = _last_close_on_or_before(cid, date(2026, 10, 20))
            ret_06_10 = ((p10 / p06) - 1.0) * 100.0 if (p06 and p10) else None
            ret_oct20_nov06 = ((p06 / p_oct20) - 1.0) * 100.0 if (p06 and p_oct20) else None
            sp = sp06_by_id.get(cid)
            t = sp.quantitative_trend_evidence if sp else None
            med20 = sp.liquidity_execution_feasibility.median_turnover_20s_tnd if sp else None
            challenge_peers_excluded_nov06.append(
                {
                    "challenge_symbol": entry.challenge_symbol,
                    "canonical_id": cid,
                    "nov06_exclusion_reasons": b06_excl[cid],
                    "nov10_exclusion_reasons": b10_excl[cid] if cid in b10_excl else ["ELIGIBLE"],
                    "last_traded_on_or_before_nov06": d06.isoformat() if d06 else None,
                    "close_nov06": p06,
                    "last_traded_on_or_before_nov10": d10.isoformat() if d10 else None,
                    "close_nov10": p10,
                    "ret_nov06_to_nov10_pct": round(ret_06_10, 4)
                    if ret_06_10 is not None
                    else None,
                    "ret_oct20_to_nov06_pct": round(ret_oct20_nov06, 4)
                    if ret_oct20_nov06 is not None
                    else None,
                    "sparse_v1_nov06_status": sp.research_status if sp else None,
                    "sparse_v1_nov06_quant": t.quantitative_score if t else None,
                    "sparse_v1_nov06_awakening_ratio": t.turnover_awakening_ratio if t else None,
                    "sparse_v1_nov06_med_turn_20": float(med20) if med20 is not None else None,
                }
            )

    # 5. All Sparse-v1 Awakening Triggers across the 13 WF dates in 196 sessions -> 10s forward open-to-close outcomes
    bars_by_inst_date: dict[str, dict[date, Any]] = {}
    for b in fixed_bars:
        bars_by_inst_date.setdefault(b.instrument_id, {})[b.session_date] = b

    eval_dates_13 = [open_sessions[idx] for idx in range(60, len(open_sessions) - 10, 10)]
    awakening_triggers: list[dict[str, Any]] = []
    for d in eval_dates_13:
        d_idx = open_sessions.index(d)
        d_next = open_sessions[d_idx + 1]
        b_slice = [b for b in fixed_bars if b.session_date <= d]
        c_slice = [s for s in cal_pit if s.session_date <= d]
        b_rep = rank_session_baseline(
            master_list,
            c_slice,
            b_slice,
            _cutoff_for(d),
            min_trade_frequency=0.60,
            min_median_turnover_tnd=Decimal("5000"),
        )
        sp_res = evaluate_sparse_market_research(
            master_list,
            c_slice,
            b_slice,
            _cutoff_for(d),
            config=sparse_cfg,
            baseline_report=b_rep,
            sector_by_instrument=sector_map,
        )
        for a in sp_res.assessments:
            t = a.quantitative_trend_evidence
            if t.awakening_detected:
                b_in = bars_by_inst_date.get(a.instrument_id, {}).get(d_next)
                b_out = None
                for back in range(d_idx + 10, d_idx, -1):
                    cand = bars_by_inst_date.get(a.instrument_id, {}).get(open_sessions[back])
                    if cand and cand.volume_shares > 0:
                        b_out = cand
                        break
                fwd_o2c = None
                entry_traded = bool(b_in and b_in.volume_shares > 0)
                if entry_traded and b_out and b_in.open > 0:
                    fwd_o2c = round(((float(b_out.close) / float(b_in.open)) - 1.0) * 100.0, 2)
                awakening_triggers.append(
                    {
                        "decision_date": d.isoformat(),
                        "instrument_id": a.instrument_id,
                        "in_challenge": a.competition_eligibility.in_challenge_universe,
                        "awakening_ratio": t.turnover_awakening_ratio,
                        "quant_score": t.quantitative_score,
                        "latest_day_return_pct": t.latest_day_return_pct,
                        "selected": a.is_selected_candidate,
                        "entry_session": d_next.isoformat(),
                        "entry_traded": entry_traded,
                        "fwd10_open_to_close_pct": fwd_o2c,
                    }
                )

    traded_awak = [
        x
        for x in awakening_triggers
        if x["entry_traded"] and x["fwd10_open_to_close_pct"] is not None
    ]
    pos_q_awak = [x for x in traded_awak if (x["quant_score"] or 0.0) >= 0.0]
    neg_q_awak = [x for x in traded_awak if (x["quant_score"] or 0.0) < 0.0]

    awakening_summary = {
        "eval_dates_count": len(eval_dates_13),
        "eval_dates": [d.isoformat() for d in eval_dates_13],
        "total_awakening_flags": len(awakening_triggers),
        "traded_entry_count": len(traded_awak),
        "all_traded_mean_fwd10_pct": round(
            sum(x["fwd10_open_to_close_pct"] for x in traded_awak) / len(traded_awak), 2
        )
        if traded_awak
        else None,
        "all_traded_median_fwd10_pct": round(
            median(x["fwd10_open_to_close_pct"] for x in traded_awak), 2
        )
        if traded_awak
        else None,
        "all_traded_hit_pos_pct": round(
            sum(1 for x in traded_awak if x["fwd10_open_to_close_pct"] > 0)
            / len(traded_awak)
            * 100.0,
            2,
        )
        if traded_awak
        else None,
        "quant_ge_0_count": len(pos_q_awak),
        "quant_ge_0_mean_fwd10_pct": round(
            sum(x["fwd10_open_to_close_pct"] for x in pos_q_awak) / len(pos_q_awak), 2
        )
        if pos_q_awak
        else None,
        "quant_ge_0_median_fwd10_pct": round(
            median(x["fwd10_open_to_close_pct"] for x in pos_q_awak), 2
        )
        if pos_q_awak
        else None,
        "quant_ge_0_hit_pos_pct": round(
            sum(1 for x in pos_q_awak if x["fwd10_open_to_close_pct"] > 0)
            / len(pos_q_awak)
            * 100.0,
            2,
        )
        if pos_q_awak
        else None,
        "quant_lt_0_count": len(neg_q_awak),
        "quant_lt_0_mean_fwd10_pct": round(
            sum(x["fwd10_open_to_close_pct"] for x in neg_q_awak) / len(neg_q_awak), 2
        )
        if neg_q_awak
        else None,
        "quant_lt_0_median_fwd10_pct": round(
            median(x["fwd10_open_to_close_pct"] for x in neg_q_awak), 2
        )
        if neg_q_awak
        else None,
        "quant_lt_0_hit_pos_pct": round(
            sum(1 for x in neg_q_awak if x["fwd10_open_to_close_pct"] > 0)
            / len(neg_q_awak)
            * 100.0,
            2,
        )
        if neg_q_awak
        else None,
    }

    payload = _norm(
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "g5_purged_folds_dev": dev_folds,
            "g5_holdout_spec": holdout_spec,
            "sotetel_sensitivity_196": {
                "without_sotetel": _extract_suite_rows(suite_no_sotetel),
            },
            "baseline_top15_displacement": {
                "nov06_top15": _top_displaced(base_nov06.candidates, 15),
                "nov10_top15": _top_displaced(base_nov10.candidates, 15),
                "nov10_non_challenge_in_top15": sum(
                    1 for r in _top_displaced(base_nov10.candidates, 15) if not r["in_challenge"]
                ),
            },
            "challenge_excluded_nov06_peer_cohort": challenge_peers_excluded_nov06,
            "sparse_v1_awakening_cohort_196": {
                "summary": awakening_summary,
                "triggers": awakening_triggers,
            },
        }
    )

    out_path = DASHBOARD_ROOT / "artifacts" / "m14" / "m14_g5_folds_and_peers.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    print(
        "G5 dev folds:",
        len(dev_folds),
        "| Holdout:",
        holdout_spec["holdout_start_date"],
        "..",
        holdout_spec["holdout_end_date"],
    )
    print(
        "Non-challenge in Nov 10 Baseline Top 15:",
        payload["baseline_top15_displacement"]["nov10_non_challenge_in_top15"],
    )
    print("Excluded Nov 06 Challenge count:", len(challenge_peers_excluded_nov06))
    print("Awakening cohort summary:", json.dumps(awakening_summary))


if __name__ == "__main__":
    main()
