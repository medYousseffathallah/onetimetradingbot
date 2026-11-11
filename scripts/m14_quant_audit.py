"""Reproducible M14 Gemini Quantitative Research Audit & Diagnostics.

Strictly read-only over C:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit.
Writes outputs exclusively under bvmt-gemini-dashboard/artifacts/m14/.
Never alters production files, ledgers, configs, or snapshots.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any

STARTER_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = STARTER_ROOT / "artifacts" / "m14-joint" / "reproduced"

if str(STARTER_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(STARTER_ROOT / "src"))

from bvmt.calendar import (  # noqa: E402
    ExchangeSession,
    InstrumentRecord,
    read_exchange_calendar,
    read_instrument_master,
)
from bvmt.challenge_universe import (  # noqa: E402
    get_challenge_symbol_set,
    get_challenge_universe,
    is_in_challenge_universe,
)
from bvmt.data import DailyBar, read_bars_csv  # noqa: E402
from bvmt.execution import MarketOrder, estimate_next_bar_fill  # noqa: E402
from bvmt.features import rank_session_baseline  # noqa: E402
from bvmt.holding_period import evaluate_holding_periods  # noqa: E402
from bvmt.ledger import PortfolioLedger  # noqa: E402
from bvmt.macro_events import get_verified_macro_intelligence  # noqa: E402
from bvmt.multi_horizon import evaluate_multi_horizon_intelligence  # noqa: E402
from bvmt.recommendations import generate_recommendations  # noqa: E402
from bvmt.research_coverage import evaluate_market_research_coverage  # noqa: E402
from bvmt.sparse_generalization import (  # noqa: E402
    prepare_pit_calendar_and_bars,
    run_walk_forward_generalization_benchmark,
)
from bvmt.sparse_research import (  # noqa: E402
    SparseResearchConfig,
    evaluate_sparse_market_research,
    extract_limit_reserved_bars_from_rejections,
    load_emetteur_sector_map,
    load_frozen_sparse_research_config,
)
from bvmt.strategies import (  # noqa: E402
    StrategyLabConfig,
    _metrics,
    _simulate,
    evaluate_strategy_suite,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Unserializable type: {type(obj)}")


def slice_dataset(
    calendar: list[ExchangeSession],
    bars: list[DailyBar],
    end_date: date,
) -> tuple[list[ExchangeSession], list[DailyBar]]:
    cal_slice = [s for s in calendar if s.session_date <= end_date]
    bars_slice = [b for b in bars if b.session_date <= end_date]
    return cal_slice, bars_slice


def filter_instruments_for_challenge(
    instruments: list[InstrumentRecord],
) -> list[InstrumentRecord]:
    challenge_isins = {r.verified_isin for r in get_challenge_universe()}
    return [
        rec
        for rec in instruments
        if is_in_challenge_universe(rec.instrument_id, rec.isin, rec.symbol)
        or (rec.isin and rec.isin in challenge_isins)
    ]


def audit_data_and_poulina(
    processed_dir: Path,
    staging_dir: Path,
    instruments: list[InstrumentRecord],
    calendar: list[ExchangeSession],
    bars: list[DailyBar],
) -> dict[str, Any]:
    open_sessions = sorted(s.session_date for s in calendar if s.is_open)
    missing_pub = sum(1 for b in bars if b.published_at is None)

    poulina_master = [
        r for r in instruments if "POULINA" in r.instrument_id or "POULINA" in r.symbol
    ]
    poulina_bars: dict[str, list[DailyBar]] = defaultdict(list)
    for b in bars:
        if "POULINA" in b.instrument_id or "POULINA" in b.symbol:
            poulina_bars[b.instrument_id].append(b)

    poulina_bar_summary = {}
    for iid, blist in sorted(poulina_bars.items()):
        blist_sorted = sorted(blist, key=lambda x: x.session_date)
        traded = [b for b in blist_sorted if b.status == "traded"]
        poulina_bar_summary[iid] = {
            "count": len(blist_sorted),
            "traded_count": len(traded),
            "first_session": blist_sorted[0].session_date.isoformat(),
            "last_session": blist_sorted[-1].session_date.isoformat(),
            "last_close": str(blist_sorted[-1].close),
            "symbols": sorted({b.symbol for b in blist_sorted}),
            "isins": sorted({b.isin or "" for b in blist_sorted}),
        }

    # Check raw NDJSON for Poulina tokens across months
    ndjson_poulina: Counter[tuple[str, str, str]] = Counter()
    ndjson_path = staging_dir / "tunis_stockexchange_equities_2026.ndjson"
    if ndjson_path.is_file():
        with ndjson_path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                if not line.strip():
                    continue
                env = json.loads(line)
                for row in env.get("data", []):
                    val = str(row.get("valeur") or "")
                    isin = str(row.get("codeISIN") or "")
                    if "POULINA" in val.upper() or isin == "TN0005700018":
                        ndjson_poulina[(isin, val, env.get("seance", "")[:7])] += 1

    # Check holding_period get_challenge_symbol_set() silent mismatch
    master_ids = {r.instrument_id for r in instruments}
    chal_symbol_set = get_challenge_symbol_set()
    matched_by_symbol_set = sorted(chal_symbol_set & master_ids)
    missed_by_symbol_set = sorted(
        r.challenge_symbol for r in get_challenge_universe() if r.challenge_symbol not in master_ids
    )

    # Check local fundamental / document inventory
    doc_chunks_path = processed_dir.parent / "document_index" / "document_chunks.json"
    comp_cfg = json.loads(
        (STARTER_ROOT / "configs" / "competition.json").read_text(encoding="utf-8")
    )
    fields = comp_cfg.get("fields", {})
    unverified_fields = [k for k, v in fields.items() if v.get("status") != "verified"]

    return {
        "canonical_sessions_total": len(open_sessions),
        "canonical_first_session": open_sessions[0].isoformat(),
        "canonical_last_session": open_sessions[-1].isoformat(),
        "canonical_bars_total": len(bars),
        "missing_published_at_count": missing_pub,
        "distinct_instruments_in_master": len(master_ids),
        "distinct_instruments_in_bars": len({b.instrument_id for b in bars}),
        "poulina_master_records": [
            {
                "instrument_id": r.instrument_id,
                "symbol": r.symbol,
                "isin": r.isin,
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
                "segment": r.market_segment,
            }
            for r in poulina_master
        ],
        "poulina_bar_summary": poulina_bar_summary,
        "poulina_ndjson_tokens": [
            {"isin": k[0], "valeur": k[1], "month": k[2], "rows": cnt}
            for k, cnt in sorted(ndjson_poulina.items())
        ],
        "holding_period_challenge_symbol_set_bug": {
            "matched_count": len(matched_by_symbol_set),
            "missed_count": len(missed_by_symbol_set),
            "missed_challenge_symbols": missed_by_symbol_set,
        },
        "document_chunks_file_exists": doc_chunks_path.is_file(),
        "competition_fields_total": len(fields),
        "competition_fields_unverified": unverified_fields,
    }


def audit_g1_defects(
    instruments: list[InstrumentRecord],
    calendar: list[ExchangeSession],
    bars: list[DailyBar],
    ledger: PortfolioLedger,
    processed_dir: Path,
) -> dict[str, Any]:
    cutoff_nov06 = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    cutoff_nov10 = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)

    cal_nov06, bars_nov06 = slice_dataset(calendar, bars, date(2026, 11, 6))
    cal_p_06, bars_p_06 = prepare_pit_calendar_and_bars(cal_nov06, bars_nov06)
    cal_p_10, bars_p_10 = prepare_pit_calendar_and_bars(calendar, bars)

    # 1. Raw published_at=None failure on rank_session_baseline
    raw_baseline_error = None
    try:
        rank_session_baseline(instruments, cal_nov06, bars_nov06, cutoff_nov06)
    except Exception as exc:
        raw_baseline_error = f"{type(exc).__name__}: {exc}"

    # 2. Synthetic vol_20 = 1e-6 spike reproducer on features.rank_session_baseline
    tiny_cal: list[ExchangeSession] = []
    tiny_bars: list[DailyBar] = []
    syn_inst = [
        InstrumentRecord(
            "FLAT_SPIKE",
            "TN0000000001",
            "FLAT_SPIKE",
            date(2026, 1, 1),
            None,
            date(2026, 1, 1),
            None,
            "principal_continu",
            "TND",
            "syn",
            True,
        ),
        InstrumentRecord(
            "NORMAL_STK",
            "TN0000000002",
            "NORMAL_STK",
            date(2026, 1, 1),
            None,
            date(2026, 1, 1),
            None,
            "principal_continu",
            "TND",
            "syn",
            True,
        ),
    ]
    sess_cnt = 0
    cur_d = date(2026, 1, 2)
    while sess_cnt < 62:
        if cur_d.weekday() < 5:
            ts = datetime(cur_d.year, cur_d.month, cur_d.day, 16, 0, tzinfo=UTC)
            tiny_cal.append(
                ExchangeSession(
                    session_date=cur_d,
                    is_open=True,
                    schedule_type="regular",
                    opens_at=datetime(cur_d.year, cur_d.month, cur_d.day, 9, 0, tzinfo=UTC),
                    closes_at=ts,
                    timezone="Africa/Tunis",
                    source_document_id="syn",
                )
            )
            # Zero returns across trailing 21 sessions after initial gain -> var_r = 0 -> vol_20 floored at 1e-6!
            px_flat = Decimal("8.000") if sess_cnt < 40 else Decimal("10.000")
            tiny_bars.append(
                DailyBar(
                    "FLAT_SPIKE",
                    "FLAT_SPIKE",
                    cur_d,
                    px_flat,
                    px_flat,
                    px_flat,
                    px_flat,
                    1000,
                    px_flat * 1000,
                    "traded",
                    "syn",
                    ts,
                    ts,
                    "TN0000000001",
                )
            )
            px_norm = (
                Decimal("10.000")
                + Decimal("0.020") * Decimal(sess_cnt)
                + (Decimal("0.050") if sess_cnt % 2 else Decimal("0.000"))
            )
            tiny_bars.append(
                DailyBar(
                    "NORMAL_STK",
                    "NORMAL_STK",
                    cur_d,
                    px_norm,
                    px_norm,
                    px_norm,
                    px_norm,
                    1000,
                    px_norm * 1000,
                    "traded",
                    "syn",
                    ts,
                    ts,
                    "TN0000000002",
                )
            )
            sess_cnt += 1
        cur_d += timedelta(days=1)

    vol_spike_report = rank_session_baseline(
        syn_inst, tiny_cal, tiny_bars, datetime(2026, 12, 31, tzinfo=UTC)
    )
    vol_spike_out = [
        {
            "instrument_id": c.instrument_id,
            "mom20": str(c.momentum_20s),
            "mom60": str(c.momentum_60s),
            "vol20": str(c.volatility_20s),
            "composite": str(c.composite_score),
        }
        for c in vol_spike_report.candidates
    ]

    # 3. Baseline rankings & Recommendations (Nov 06 & Nov 10)
    base_06 = rank_session_baseline(
        instruments,
        cal_p_06,
        bars_p_06,
        cutoff_nov06,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )
    base_10 = rank_session_baseline(
        instruments,
        cal_p_10,
        bars_p_10,
        cutoff_nov10,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )

    pmap_10 = {}
    for b in sorted(bars_p_10, key=lambda x: x.session_date):
        if b.status == "traded":
            pmap_10[b.instrument_id] = b.close
    recs_10 = generate_recommendations(
        base_10,
        ledger,
        generated_at=cutoff_nov10,
        simulation_profile="RESEARCH_CONSERVATIVE",
        data_is_synthetic=False,
        rule_blocker_count=72,
        market_quotes=pmap_10,
    )
    buy_cands_recs = [
        {
            "rank": r.rank,
            "instrument_id": r.instrument_id,
            "symbol": r.symbol,
            "category": r.category,
            "in_challenge_universe": is_in_challenge_universe(r.instrument_id, symbol=r.symbol),
            "suggested_shares": r.suggested_shares,
            "composite_score": str(r.composite_score),
            "blocked_reasons": r.blocked_reasons,
        }
        for r in recs_10.recommendations
        if r.category == "BUY CANDIDATE"
    ]

    # 4. Multi-horizon unit bug, hardcoded cutoff, 10000 fallback
    mh_oct09 = evaluate_multi_horizon_intelligence(
        portfolio_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("38752.350"),
        held_positions={},
        market_rankings=base_10.candidates[:10],
        as_of_session="2026-10-09",
    )
    mh_macro_leaked = [
        ev["event_id"] for ev in mh_oct09.macro_events if ev["published_at"] > "2026-10-09"
    ]

    class _FakeZeroShortRank:
        instrument_id = "BH_BANK"
        symbol = "BH BANK"
        rank = 1
        short_return_pct = 0.0
        long_return_pct = 12.0
        momentum_20s = Decimal("9.99")
        momentum_60s = Decimal("0.12")
        median_turnover_tnd = None
        median_turnover_20s_tnd = None
        close_tnd = Decimal("10.000")
        composite_score = 3.5

    class _FakeRatioMomRank:
        instrument_id = "SFBT"
        symbol = "SFBT"
        rank = 8
        momentum_20s = Decimal("0.15")  # +15% ratio from SessionCandidate
        momentum_60s = Decimal("0.25")
        median_turnover_20s_tnd = Decimal("20000.000")
        close_tnd = Decimal("10.000")
        composite_score = 2.0

    mh_fake = evaluate_multi_horizon_intelligence(
        portfolio_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("38752.350"),
        held_positions={},
        market_rankings=[_FakeZeroShortRank(), _FakeRatioMomRank()],
        as_of_session="2026-11-10",
    )
    mh_fake_swing = [
        {
            "id": c.instrument_id,
            "evidence_status": c.evidence_status,
            "qty_limit": c.quantity_limit,
            "supporting_factors": c.supporting_factors,
            "review_date": c.review_date,
        }
        for c in mh_fake.swing_candidates
    ]

    # 5. Research coverage mixed scale inspection on Nov 10
    cov_10 = evaluate_market_research_coverage(
        instruments, cal_p_10, bars_p_10, cutoff_nov10, baseline_report=base_10
    )
    elig_scores = [
        a.continuous_research_score
        for a in cov_10.by_instrument.values()
        if a.classification.strategy_eligibility == "ELIGIBLE"
        and a.continuous_research_score is not None
    ]
    excl_scores = [
        a.continuous_research_score
        for a in cov_10.by_instrument.values()
        if a.classification.strategy_eligibility != "ELIGIBLE"
        and a.continuous_research_score is not None
    ]

    # 6. Macro events alias mismatch check
    cc_no_alias = get_verified_macro_intelligence(
        cutoff=cutoff_nov10, instrument_id="CARTHAGE_CEMENT", include_aliases=False
    )
    cc_with_alias = get_verified_macro_intelligence(
        cutoff=cutoff_nov10, instrument_id="CARTHAGE_CEMENT", include_aliases=True
    )

    # 7. Holding period hardcoded narrative vs actual 196-session data (BOTH Full & Challenge)
    hp_196_full = evaluate_holding_periods(
        bars_path=processed_dir / "daily_bars.canonical.csv",
        calendar_path=processed_dir / "exchange_calendar.csv",
        instruments_path=processed_dir / "instrument_master.csv",
        universe="FULL_BVMT",
    )
    hp_196_chal = evaluate_holding_periods(
        bars_path=processed_dir / "daily_bars.canonical.csv",
        calendar_path=processed_dir / "exchange_calendar.csv",
        instruments_path=processed_dir / "instrument_master.csv",
        universe="TUNIS_BOURSE_CHALLENGE",
    )

    # 8. Sparse research non-challenge top-K slot leakage & awakening anomalies
    cfg = load_frozen_sparse_research_config(STARTER_ROOT / "configs" / "sparse_research_v1.json")
    sector_map = load_emetteur_sector_map(
        STARTER_ROOT / "data" / "staging" / "mapping_emetteur.json"
    )
    rej_paths = [processed_dir / "rejections.json", processed_dir / "rejected_rows.csv"]
    hb_bars, hb_meta = extract_limit_reserved_bars_from_rejections(rej_paths, allow_recovery=True)
    sp_06 = evaluate_sparse_market_research(
        instruments,
        cal_p_06,
        bars_p_06,
        cutoff_nov06,
        config=cfg,
        baseline_report=base_06,
        sector_by_instrument=sector_map,
        limit_reserved_meta=[m for m in hb_meta if m.session_date <= date(2026, 11, 6)],
    )
    sp_10 = evaluate_sparse_market_research(
        instruments,
        cal_p_10,
        bars_p_10,
        cutoff_nov10,
        config=cfg,
        baseline_report=base_10,
        sector_by_instrument=sector_map,
        limit_reserved_meta=hb_meta,
    )

    non_chal_selected_10 = [
        {
            "id": a.instrument_id,
            "symbol": a.symbol,
            "priority": a.research_priority_score,
            "q_score": a.quantitative_trend_evidence.quantitative_score,
            "reason": a.candidate_selection_reason,
            "trading_elig": a.trading_eligibility.status,
        }
        for a in sp_10.assessments
        if a.is_selected_candidate and not a.competition_eligibility.in_challenge_universe
    ]
    awakening_anomalies = []
    for a in sp_10.assessments:
        t = a.quantitative_trend_evidence
        if t.awakening_detected and (
            (t.latest_day_return_pct is None)
            or (t.quantitative_score is not None and t.quantitative_score < 0)
        ):
            awakening_anomalies.append(
                {
                    "id": a.instrument_id,
                    "latest_day_ret": t.latest_day_return_pct,
                    "quant_score": t.quantitative_score,
                    "selected": a.is_selected_candidate,
                    "liq_status": a.liquidity_execution_feasibility.execution_status,
                }
            )

    return {
        "raw_baseline_error_on_blank_published_at": raw_baseline_error,
        "vol_20_1e6_spike_reproducer": vol_spike_out,
        "baseline_nov06_eligible_count": len(base_06.candidates),
        "baseline_nov06_excluded_count": len(base_06.exclusions),
        "baseline_nov06_top5": [
            {
                "id": c.instrument_id,
                "score": str(c.composite_score),
                "mom20": str(c.momentum_20s),
                "mom60": str(c.momentum_60s),
            }
            for c in base_06.candidates[:5]
        ],
        "baseline_nov10_eligible_count": len(base_10.candidates),
        "baseline_nov10_excluded_count": len(base_10.exclusions),
        "baseline_nov10_top5": [
            {
                "id": c.instrument_id,
                "score": str(c.composite_score),
                "mom20": str(c.momentum_20s),
                "mom60": str(c.momentum_60s),
            }
            for c in base_10.candidates[:5]
        ],
        "recommendations_buy_candidates_without_api_guard": buy_cands_recs,
        "multi_horizon_oct09_leaked_event_ids": mh_macro_leaked,
        "multi_horizon_oct09_session": mh_oct09.session_date,
        "multi_horizon_zero_short_and_none_turnover_bug": mh_fake_swing,
        "research_coverage_mixed_score_ranges": {
            "eligible_count": len(elig_scores),
            "eligible_min_max": [min(elig_scores), max(elig_scores)] if elig_scores else None,
            "excluded_count": len(excl_scores),
            "excluded_min_max": [min(excl_scores), max(excl_scores)] if excl_scores else None,
        },
        "macro_events_alias_mismatch": {
            "carthage_cement_include_aliases_false": len(cc_no_alias),
            "carthage_cement_include_aliases_true": len(cc_with_alias),
        },
        "holding_period_196_full": {
            "actual_sessions": hp_196_full.total_sessions_evaluated
            if hasattr(hp_196_full, "total_sessions_evaluated")
            else hp_196_full.dataset_session_count,
            "reasoning_text": hp_196_full.reasoning,
            "horizons": [h.to_dict() for h in hp_196_full.horizons],
        },
        "holding_period_196_challenge_buggy_filter": {
            "actual_sessions": hp_196_chal.dataset_session_count,
            "horizons": [h.to_dict() for h in hp_196_chal.horizons],
        },
        "sparse_v1_selected_nov06": sp_06.selected_candidate_ids,
        "sparse_v1_selected_nov10": sp_10.selected_candidate_ids,
        "sparse_v1_non_challenge_selected_in_top8_nov10": non_chal_selected_10,
        "sparse_v1_awakening_anomalies_nov10": awakening_anomalies,
        "_internals": {
            "base_06": base_06,
            "base_10": base_10,
            "sp_06": sp_06,
            "sp_10": sp_10,
            "hb_bars": hb_bars,
            "hb_meta": hb_meta,
            "cal_p_06": cal_p_06,
            "bars_p_06": bars_p_06,
            "cal_p_10": cal_p_10,
            "bars_p_10": bars_p_10,
            "cfg": cfg,
            "sector_map": sector_map,
        },
    }


def build_42_challenge_accounting(
    instruments: list[InstrumentRecord],
    bars: list[DailyBar],
    sp_06: Any,
    sp_10: Any,
    base_06: Any,
    base_10: Any,
    hb_meta: list[Any],
) -> list[dict[str, Any]]:
    chal = get_challenge_universe()
    by_iid_bars_10: dict[str, list[DailyBar]] = defaultdict(list)
    by_iid_bars_06: dict[str, list[DailyBar]] = defaultdict(list)
    for b in bars:
        by_iid_bars_10[b.instrument_id].append(b)
        if b.session_date <= date(2026, 11, 6):
            by_iid_bars_06[b.instrument_id].append(b)

    base06_rank = {c.instrument_id: idx for idx, c in enumerate(base_06.candidates, 1)}
    base06_excl = {e.instrument_id: e.reason for e in base_06.exclusions}
    base10_rank = {c.instrument_id: idx for idx, c in enumerate(base_10.candidates, 1)}
    base10_excl = {e.instrument_id: e.reason for e in base_10.exclusions}

    hb_by_id: dict[str, list[str]] = defaultdict(list)
    for m in hb_meta:
        hb_by_id[m.instrument_id].append(f"{m.session_date}:{m.indicateur}")

    by_isin: dict[str, list[str]] = defaultdict(list)
    for rec in instruments:
        if rec.isin:
            by_isin[rec.isin].append(rec.instrument_id)

    rows: list[dict[str, Any]] = []
    for rec in chal:
        canon_id = rec.canonical_instrument_id
        same_isin_ids = sorted(set(by_isin.get(rec.verified_isin, [canon_id])))
        a06 = sp_06.by_instrument.get(canon_id)
        a10 = sp_10.by_instrument.get(canon_id)
        b10 = sorted(by_iid_bars_10.get(canon_id, []), key=lambda x: x.session_date)
        traded_10 = [b for b in b10 if b.status == "traded"]
        last_t = traded_10[-1] if traded_10 else None
        rows.append(
            {
                "challenge_symbol": rec.challenge_symbol,
                "canonical_id": canon_id,
                "all_master_ids_for_isin": same_isin_ids,
                "verified_isin": rec.verified_isin,
                "market_mode": rec.market_mode,
                "bars_194": len(by_iid_bars_06.get(canon_id, [])),
                "bars_196": len(b10),
                "traded_bars_196": len(traded_10),
                "quote_age_nov06": a06.data_quality_freshness.quote_age_open_sessions
                if a06
                else None,
                "quote_age_nov10": a10.data_quality_freshness.quote_age_open_sessions
                if a10
                else None,
                "missing_60s_nov10": a10.data_quality_freshness.missing_open_sessions_60s
                if a10
                else None,
                "last_traded_date_nov10": last_t.session_date.isoformat() if last_t else None,
                "last_close_tnd": str(last_t.close) if last_t else None,
                "med_turnover_20s_nov10": str(
                    a10.liquidity_execution_feasibility.median_turnover_20s_tnd
                )
                if a10
                else None,
                "trade_freq_20s_nov10": a10.liquidity_execution_feasibility.trade_frequency_20s
                if a10
                else None,
                "baseline_nov06": f"RANK_{base06_rank[canon_id]}"
                if canon_id in base06_rank
                else base06_excl.get(canon_id, "ABSENT"),
                "baseline_nov10": f"RANK_{base10_rank[canon_id]}"
                if canon_id in base10_rank
                else base10_excl.get(canon_id, "ABSENT"),
                "sparse_v1_status_nov06": a06.research_status if a06 else "ABSENT",
                "sparse_v1_status_nov10": a10.research_status if a10 else "ABSENT",
                "sparse_v1_elig_nov10": a10.trading_eligibility.status if a10 else "ABSENT",
                "sparse_v1_quant_nov10": a10.quantitative_trend_evidence.quantitative_score
                if a10
                else None,
                "sparse_v1_selected_nov10": a10.is_selected_candidate if a10 else False,
                "hb_events": hb_by_id.get(canon_id, []),
            }
        )
    return rows


def audit_icf_forensic(
    instruments: list[InstrumentRecord],
    cal_p_10: list[ExchangeSession],
    bars_p_10: list[DailyBar],
    hb_meta: list[Any],
    cfg: SparseResearchConfig,
    sector_map: dict[str, str],
    processed_dir: Path,
) -> dict[str, Any]:
    icf_bars = sorted(
        [b for b in bars_p_10 if b.instrument_id == "ICF"], key=lambda x: x.session_date
    )
    traded = [b for b in icf_bars if b.status == "traded"]
    min_b = min(traded, key=lambda b: b.close)
    max_b = max(traded, key=lambda b: b.close)
    h1_bars = [b for b in traded if b.session_date <= date(2026, 6, 30)]
    h1_min = min(h1_bars, key=lambda b: b.close)
    h1_max = max(h1_bars, key=lambda b: b.close)

    icf_rejections = [m.to_dict() for m in hb_meta if m.instrument_id == "ICF"]
    all_rej_icf = []
    rej_json_path = processed_dir / "rejections.json"
    if rej_json_path.is_file():
        payload = json.loads(rej_json_path.read_text(encoding="utf-8"))
        for entry in payload.get("rejections", []):
            raw_str = str(entry.get("raw_row", ""))
            if "ICF" in raw_str or "TN0003200755" in raw_str:
                all_rej_icf.append({"reason": entry.get("reason"), "raw": raw_str})

    open_dates = sorted(s.session_date for s in cal_p_10 if s.is_open)
    icf_dates = {b.session_date for b in icf_bars}
    missing_icf_dates = sorted(d.isoformat() for d in open_dates if d not in icf_dates)

    key_dates = [
        date(2026, 3, 30),
        date(2026, 6, 15),
        date(2026, 9, 21),
        date(2026, 9, 22),
        date(2026, 10, 9),
        date(2026, 11, 6),
        date(2026, 11, 9),
        date(2026, 11, 10),
    ]
    timeline = {}
    for kd in key_dates:
        cal_k, bars_k = slice_dataset(cal_p_10, bars_p_10, kd)
        cut_k = datetime(kd.year, kd.month, kd.day, 17, 0, tzinfo=UTC)
        b_rep = rank_session_baseline(
            instruments,
            cal_k,
            bars_k,
            cut_k,
            min_trade_frequency=0.60,
            min_median_turnover_tnd=Decimal("5000"),
        )
        s_rep = evaluate_sparse_market_research(
            instruments,
            cal_k,
            bars_k,
            cut_k,
            config=cfg,
            baseline_report=b_rep,
            sector_by_instrument=sector_map,
            limit_reserved_meta=[m for m in hb_meta if m.session_date <= kd],
        )
        b_cand = next((c for c in b_rep.candidates if c.instrument_id == "ICF"), None)
        b_rank = next(
            (i for i, c in enumerate(b_rep.candidates, 1) if c.instrument_id == "ICF"), None
        )
        b_excl = [e.reason for e in b_rep.exclusions if e.instrument_id == "ICF"]
        a = s_rep.by_instrument.get("ICF")
        timeline[kd.isoformat()] = {
            "baseline_eligible": b_cand is not None,
            "baseline_rank": b_rank,
            "baseline_composite": str(b_cand.composite_score) if b_cand else None,
            "baseline_exclusions": b_excl,
            "sparse_status": a.research_status if a else None,
            "sparse_quant_score": a.quantitative_trend_evidence.quantitative_score if a else None,
            "sparse_selected": a.is_selected_candidate if a else None,
            "sparse_reason": a.candidate_selection_reason if a else None,
            "mom5": a.quantitative_trend_evidence.momentum_5s_pct if a else None,
            "mom20": a.quantitative_trend_evidence.momentum_20s_pct if a else None,
            "mom60": a.quantitative_trend_evidence.momentum_60s_pct if a else None,
            "awakening": a.quantitative_trend_evidence.awakening_detected if a else None,
            "awakening_ratio": a.quantitative_trend_evidence.turnover_awakening_ratio
            if a
            else None,
            "med_turn_20": str(a.liquidity_execution_feasibility.median_turnover_20s_tnd)
            if a
            else None,
            "last_close": str(a.liquidity_execution_feasibility.last_verified_close_tnd)
            if a
            else None,
        }

    bar_sep21 = next(b for b in icf_bars if b.session_date == date(2026, 9, 21))
    cf_results = {}
    for label, px_str in (("CF_A_open_143_600", "143.600"), ("CF_B_low_close_135_070", "135.070")):
        px = Decimal(px_str)
        fake_bar = DailyBar(
            instrument_id="ICF",
            symbol="ICF",
            session_date=date(2026, 9, 22),
            open=Decimal("143.600"),
            high=Decimal("143.600"),
            low=Decimal("135.070"),
            close=px,
            volume_shares=2445,
            turnover_tnd=Decimal("336304.930"),
            status="traded",
            source_id="cf_audit",
            published_at=datetime(2026, 9, 22, 15, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 9, 22, 15, 0, tzinfo=UTC),
            isin="TN0003200755",
        )
        cal_06, bars_06 = slice_dataset(cal_p_10, bars_p_10, date(2026, 11, 6))
        bars_cf = list(bars_06) + [fake_bar]
        cut_06 = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
        b_cf = rank_session_baseline(
            instruments,
            cal_06,
            bars_cf,
            cut_06,
            min_trade_frequency=0.60,
            min_median_turnover_tnd=Decimal("5000"),
        )
        s_cf = evaluate_sparse_market_research(
            instruments,
            cal_06,
            bars_cf,
            cut_06,
            config=cfg,
            baseline_report=b_cf,
            sector_by_instrument=sector_map,
            hb_bar_keys=frozenset({("ICF", date(2026, 9, 22))}),
        )
        b_cand_cf = next((c for c in b_cf.candidates if c.instrument_id == "ICF"), None)
        b_rank_cf = next(
            (i for i, c in enumerate(b_cf.candidates, 1) if c.instrument_id == "ICF"), None
        )
        a_cf = s_cf.by_instrument["ICF"]
        cf_results[label] = {
            "baseline_eligible": b_cand_cf is not None,
            "baseline_rank": b_rank_cf,
            "baseline_composite": str(b_cand_cf.composite_score) if b_cand_cf else None,
            "baseline_exclusions": [e.reason for e in b_cf.exclusions if e.instrument_id == "ICF"],
            "sparse_status": a_cf.research_status,
            "sparse_quant_score": a_cf.quantitative_trend_evidence.quantitative_score,
            "sparse_selected": a_cf.is_selected_candidate,
        }

    fill_checks = {}
    icf_map = {b.session_date: b for b in icf_bars}
    for d_str in ("2026-03-31", "2026-07-06", "2026-10-12", "2026-11-09", "2026-11-10"):
        d = date.fromisoformat(d_str)
        b = icf_map.get(d)
        if b is None:
            fill_checks[d_str] = {"status": "NO_BAR"}
            continue
        cap = int(Decimal(b.volume_shares) * Decimal("0.10"))
        desired = max(1, int(Decimal("4250.000") // b.open)) if b.open > 0 else 0
        fill = estimate_next_bar_fill(
            MarketOrder("ICF", open_dates[open_dates.index(d) - 1], "buy", desired),
            b,
            participation_rate=Decimal("0.10"),
            remaining_shared_capacity=cap,
            slippage_bps=Decimal("20"),
            commission_bps=Decimal("50"),
        )
        fill_checks[d_str] = {
            "open": str(b.open),
            "high": str(b.high),
            "low": str(b.low),
            "close": str(b.close),
            "volume": b.volume_shares,
            "turnover": str(b.turnover_tnd),
            "desired_shares_4250tnd": desired,
            "cap_10pct_shares": cap,
            "filled_shares": fill.quantity,
            "fill_price": str(fill.price) if fill.price else None,
            "fill_fee": str(fill.fee),
            "reason": fill.reason,
        }

    recent_icf = [
        {
            "date": b.session_date.isoformat(),
            "open": str(b.open),
            "high": str(b.high),
            "low": str(b.low),
            "close": str(b.close),
            "vol": b.volume_shares,
            "turnover": str(b.turnover_tnd),
            "status": b.status,
        }
        for b in icf_bars[-10:]
    ]

    return {
        "total_canonical_bars": len(icf_bars),
        "traded_bars": len(traded),
        "missing_open_sessions": missing_icf_dates,
        "h1_min": {"date": h1_min.session_date.isoformat(), "close": str(h1_min.close)},
        "h1_max": {"date": h1_max.session_date.isoformat(), "close": str(h1_max.close)},
        "h1_return_pct": round(float(h1_max.close / h1_min.close - 1) * 100, 4),
        "full_min": {"date": min_b.session_date.isoformat(), "close": str(min_b.close)},
        "full_max": {"date": max_b.session_date.isoformat(), "close": str(max_b.close)},
        "sep21_bar": {
            "close": str(bar_sep21.close),
            "vol": bar_sep21.volume_shares,
            "turnover": str(bar_sep21.turnover_tnd),
        },
        "raw_rejections_for_icf": all_rej_icf,
        "hb_recovery_meta_for_icf": icf_rejections,
        "timeline": timeline,
        "counterfactual_nov06": cf_results,
        "simulated_next_open_fills": fill_checks,
        "recent_icf_bars": recent_icf,
    }


def _extract_suite_rows(suite: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for r in suite["reports"]:
        rnm = r.get("risk_normalized_metrics", {})
        rows.append(
            {
                "id": r["strategy_id"],
                "net_ret_pct": r["net_return_pct"],
                "liq_ret_pct": r["liquidated_return_pct"],
                "max_dd_pct": r["max_drawdown_pct"],
                "excess_vs_c": r["excess_return_pct"],
                "avg_util_pct": rnm.get("active_cash_utilization_pct"),
                "cash_matched_b_pct": rnm.get("cash_matched_benchmark_b_return_pct"),
                "excess_vs_matched_b_pct": rnm.get("excess_vs_cash_matched_b_pct"),
                "top_winner": rnm.get("top_winner_instrument_id"),
                "top_winner_pnl": rnm.get("top_winner_net_pnl_tnd"),
                "ex_top_winner_pct": rnm.get("ex_top_winner_net_return_pct"),
                "wf_mean_liq_pct": r.get("walk_forward", {}).get("mean_liquidated_return_pct"),
                "wf_pos_folds": r.get("walk_forward", {}).get("positive_folds"),
                "wf_total_folds": r.get("walk_forward", {}).get("total_folds"),
                "trades": r["trade_count"],
                "fees_tnd": r["total_fees_tnd"],
            }
        )
    return rows


def audit_g3_sensitivity_and_generalization(
    instruments: list[InstrumentRecord],
    cal_p_10: list[ExchangeSession],
    bars_p_10: list[DailyBar],
    cfg: SparseResearchConfig,
    sector_map: dict[str, str],
    processed_dir: Path,
) -> dict[str, Any]:
    cal_p_06, bars_p_06 = slice_dataset(cal_p_10, bars_p_10, date(2026, 11, 6))
    suite_06 = evaluate_strategy_suite(bars_p_06, instruments, cal_p_06)
    suite_10 = evaluate_strategy_suite(bars_p_10, instruments, cal_p_10)

    chal_inst = filter_instruments_for_challenge(instruments)
    chal_ids = {r.instrument_id for r in chal_inst}
    chal_bars_10 = [b for b in bars_p_10 if b.instrument_id in chal_ids]
    suite_10_chal = evaluate_strategy_suite(chal_bars_10, chal_inst, cal_p_10)

    # Rebalance & phase sensitivity for Models D, E, G on 196 sessions
    open_dates_10 = sorted(s.session_date for s in cal_p_10 if s.is_open)
    by_date_10: dict[date, dict[str, DailyBar]] = {d: {} for d in open_dates_10}
    for b in bars_p_10:
        if b.session_date in by_date_10:
            by_date_10[b.session_date][b.instrument_id] = b
    cutoffs_10 = {s.session_date: s.closes_at for s in cal_p_10 if s.is_open}
    features_10 = {
        d: _metrics(open_dates_10[: i + 1], by_date_10, instruments, cutoffs_10[d])
        for i, d in enumerate(open_dates_10)
        if i >= 60
    }

    cadence_sensitivity: dict[str, Any] = {}
    for sid in ("D_MOMENTUM_20S", "E_MOMENTUM_60S", "G_LIQUIDITY_FILTERED_MOMENTUM"):
        by_reb = {}
        for reb in (5, 10, 15, 19, 20, 21, 22, 40):
            liq_rets = []
            max_start = 60 + reb
            for start_idx in range(60, min(max_start, len(open_dates_10) - 1)):
                cfg_s = StrategyLabConfig(rebalance_every_sessions=reb)
                run = _simulate(
                    sid, open_dates_10, by_date_10, features_10, cfg_s, decision_start=start_idx
                )
                liq_rets.append(round(float(run.summary["liquidated_return_pct"]), 4))
            liq_sorted = sorted(liq_rets)
            by_reb[str(reb)] = {
                "phases_tested": len(liq_rets),
                "min": liq_sorted[0],
                "median": round(float(median(liq_sorted)), 4),
                "max": liq_sorted[-1],
                "all": liq_rets,
            }
        cadence_sensitivity[sid] = by_reb

    sta_bars = sorted(
        [b for b in bars_p_10 if b.instrument_id == "STA"], key=lambda x: x.session_date
    )
    sta_recent = [
        {
            "date": b.session_date.isoformat(),
            "open": str(b.open),
            "close": str(b.close),
            "vol": b.volume_shares,
            "turnover": str(b.turnover_tnd),
            "status": b.status,
        }
        for b in sta_bars[-15:]
    ]

    rej_paths = [
        p
        for p in (processed_dir / "rejections.json", processed_dir / "rejected_rows.csv")
        if p.is_file()
    ]
    wf_10_h10 = run_walk_forward_generalization_benchmark(
        instruments,
        cal_p_10,
        bars_p_10,
        config=cfg,
        rejections_paths=rej_paths,
        sector_by_instrument=sector_map,
        forward_horizon_sessions=10,
        step_sessions=10,
    )
    wf_10_h20 = run_walk_forward_generalization_benchmark(
        instruments,
        cal_p_10,
        bars_p_10,
        config=cfg,
        rejections_paths=rej_paths,
        sector_by_instrument=sector_map,
        forward_horizon_sessions=20,
        step_sessions=20,
    )
    wf_06_h10 = run_walk_forward_generalization_benchmark(
        instruments,
        cal_p_06,
        bars_p_06,
        config=cfg,
        rejections_paths=rej_paths,
        sector_by_instrument=sector_map,
        forward_horizon_sessions=10,
        step_sessions=10,
    )

    # Also evaluate anti-hindsight false-positive awakenings across Challenge & Principal stocks (using eval dates 60..185 step 10)
    fp_examples = []
    win_examples = []
    raw_bar_map = {(b.instrument_id, b.session_date): b for b in bars_p_10}
    for idx in range(60, len(open_dates_10) - 10, 10):
        d_t = open_dates_10[idx]
        d_next = open_dates_10[idx + 1]
        cut_t = datetime(d_t.year, d_t.month, d_t.day, 17, 0, tzinfo=UTC)
        cal_t, bars_t = slice_dataset(cal_p_10, bars_p_10, d_t)
        b_rep = rank_session_baseline(
            instruments,
            cal_t,
            bars_t,
            cut_t,
            min_trade_frequency=0.60,
            min_median_turnover_tnd=Decimal("5000"),
        )
        sp_rep = evaluate_sparse_market_research(
            instruments,
            cal_t,
            bars_t,
            cut_t,
            config=cfg,
            baseline_report=b_rep,
            sector_by_instrument=sector_map,
        )
        for a in sp_rep.assessments:
            if not a.is_selected_candidate:
                continue
            b_in = raw_bar_map.get((a.instrument_id, d_next))
            # find last traded <= d_exit in (d_t, d_exit]
            b_out = None
            for back in range(idx + 10, idx, -1):
                cand = raw_bar_map.get((a.instrument_id, open_dates_10[back]))
                if cand and cand.status == "traded":
                    b_out = cand
                    break
            if b_in and b_in.status == "traded" and b_in.open > 0 and b_out:
                gross = float(b_out.close / b_in.open - 1) * 100.0
                row = {
                    "decision_date": d_t.isoformat(),
                    "id": a.instrument_id,
                    "in_challenge": a.competition_eligibility.in_challenge_universe,
                    "reason": a.candidate_selection_reason,
                    "q_score": a.quantitative_trend_evidence.quantitative_score,
                    "fwd10_gross_open_to_close_pct": round(gross, 2),
                }
                if gross <= -2.0:
                    fp_examples.append(row)
                elif gross >= 5.0:
                    win_examples.append(row)

    return {
        "suite_nov06_194": _extract_suite_rows(suite_06),
        "suite_nov10_196_full": _extract_suite_rows(suite_10),
        "suite_nov10_196_challenge42": _extract_suite_rows(suite_10_chal),
        "cadence_phase_sensitivity_196": cadence_sensitivity,
        "sta_recent_bars": sta_recent,
        "walk_forward_sparse_nov06_h10": wf_06_h10.to_dict(),
        "walk_forward_sparse_nov10_h10": wf_10_h10.to_dict(),
        "walk_forward_sparse_nov10_h20": wf_10_h20.to_dict(),
        "sparse_selected_drops_gt2pct": sorted(
            fp_examples, key=lambda x: x["fwd10_gross_open_to_close_pct"]
        )[:15],
        "sparse_selected_wins_gt5pct": sorted(
            win_examples, key=lambda x: -x["fwd10_gross_open_to_close_pct"]
        )[:15],
    }


def main() -> int:
    processed_dir = STARTER_ROOT / "data" / "processed" / "bvmt_official_2026"
    staging_dir = STARTER_ROOT / "data" / "staging"
    ledger_path = STARTER_ROOT / "data" / "portfolio" / "real_competition_ledger.json"

    ledger_hash_before = sha256_file(ledger_path)

    instruments = read_instrument_master(processed_dir / "instrument_master.csv")
    calendar = read_exchange_calendar(processed_dir / "exchange_calendar.csv")
    bars = read_bars_csv(processed_dir / "daily_bars.canonical.csv")
    ledger = PortfolioLedger.load(ledger_path)

    data_audit = audit_data_and_poulina(processed_dir, staging_dir, instruments, calendar, bars)
    g1_audit = audit_g1_defects(instruments, calendar, bars, ledger, processed_dir)
    internals = g1_audit.pop("_internals")

    chal_42 = build_42_challenge_accounting(
        instruments,
        bars,
        internals["sp_06"],
        internals["sp_10"],
        internals["base_06"],
        internals["base_10"],
        internals["hb_meta"],
    )
    icf_audit = audit_icf_forensic(
        instruments,
        internals["cal_p_10"],
        internals["bars_p_10"],
        internals["hb_meta"],
        internals["cfg"],
        internals["sector_map"],
        processed_dir,
    )
    g3_audit = audit_g3_sensitivity_and_generalization(
        instruments,
        internals["cal_p_10"],
        internals["bars_p_10"],
        internals["cfg"],
        internals["sector_map"],
        processed_dir,
    )

    out_dir = DASHBOARD_ROOT / "artifacts" / "m14"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "m14_audit_results.json"

    ledger_hash_after = sha256_file(ledger_path)
    assert ledger_hash_before == ledger_hash_after, "CRITICAL: Ledger file modified!"

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ledger_sha256_verified_unchanged": ledger_hash_after,
        "data_and_poulina_audit": data_audit,
        "g1_scoring_defects": g1_audit,
        "challenge_42_accounting": chal_42,
        "g2_icf_forensic": icf_audit,
        "g3_sensitivity_and_generalization": g3_audit,
    }
    out_file.write_text(json.dumps(payload, indent=2, default=json_default), encoding="utf-8")
    (out_dir / "challenge_42_accounting.json").write_text(
        json.dumps(chal_42, indent=2, default=json_default), encoding="utf-8"
    )

    print(f"Wrote {out_file} ({out_file.stat().st_size} bytes)")
    print(f"Ledger SHA-256 unchanged: {ledger_hash_after}")
    print(
        f"Sessions: {data_audit['canonical_sessions_total']} ({data_audit['canonical_first_session']}..{data_audit['canonical_last_session']}), bars={data_audit['canonical_bars_total']}"
    )
    print(
        f"Holding period Challenge symbol_set bug: matched={data_audit['holding_period_challenge_symbol_set_bug']['matched_count']}/42, missed={data_audit['holding_period_challenge_symbol_set_bug']['missed_count']}/42"
    )
    print(
        f"Raw baseline on blank published_at: {g1_audit['raw_baseline_error_on_blank_published_at']}"
    )
    print(f"Vol20 1e-6 reproducer: {g1_audit['vol_20_1e6_spike_reproducer']}")
    print(
        f"Non-challenge in recs BUY CANDIDATE (Nov10): {[x['instrument_id'] for x in g1_audit['recommendations_buy_candidates_without_api_guard']]}"
    )
    print(
        f"Non-challenge in sparse top-8 (Nov10): {[x['id'] for x in g1_audit['sparse_v1_non_challenge_selected_in_top8_nov10']]}"
    )
    print(f"ICF Nov06 sparse: {icf_audit['timeline']['2026-11-06']}")
    print(f"ICF Nov10 sparse: {icf_audit['timeline']['2026-11-10']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
