"""Tests for Phases 4, 5, and 7: multi-layer sparse research, generalization & forward ledger."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    SuspensionRecord,
    read_exchange_calendar,
    read_instrument_master,
)
from bvmt.data import DailyBar, read_bars_csv, validate_bars
from bvmt.features import rank_session_baseline
from bvmt.llm import DocumentChunk
from bvmt.macro_events import get_instrument_macro_context, resolve_instrument_aliases
from bvmt.position_sizing import PendingOrderReservation
from bvmt.research_coverage import evaluate_market_research_coverage
from bvmt.sparse_generalization import (
    COHORT_NAMES,
    prepare_pit_calendar_and_bars,
    run_benchmark_from_data_dir,
    run_walk_forward_generalization_benchmark,
)
from bvmt.sparse_research import (
    SPARSE_OPPORTUNITY_MODEL_VERSION,
    FundamentalSnapshotRecord,
    SettledSignalOutcome,
    SparseResearchConfig,
    evaluate_promotion_readiness,
    evaluate_sparse_market_research,
    extract_limit_reserved_bars_from_rejections,
    load_frozen_sparse_research_config,
    merge_canonical_with_hb_recovery,
    record_prospective_report_signals,
    record_prospective_signal,
    settle_pending_prospective_signals,
)

STARTER_OFFICIAL_DIR = (
    Path(__file__).resolve().parents[2]
    / "bvmt-starter-kit"
    / "data"
    / "processed"
    / "bvmt_official_2026"
)
STARTER_STAGING_DIR = Path(__file__).resolve().parents[2] / "bvmt-starter-kit" / "data" / "staging"


def _session_days(count: int, start: date = date(2026, 1, 2)) -> list[date]:
    days: list[date] = []
    cur = start
    while len(days) < count:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _make_calendar(dates: list[date]) -> list[ExchangeSession]:
    return [
        ExchangeSession(
            session_date=d,
            is_open=True,
            schedule_type="research_assumed_daily_bounds",
            opens_at=datetime.fromisoformat(f"{d.isoformat()}T09:00:00+01:00"),
            closes_at=datetime.fromisoformat(f"{d.isoformat()}T16:00:00+01:00"),
            timezone="Africa/Tunis",
            source_document_id="test",
        )
        for d in dates
    ]


def _make_inst(
    inst_id: str,
    symbol: str,
    *,
    segment: str = "principal_continu",
    eligible: bool = True,
    isin: str | None = None,
) -> InstrumentRecord:
    return InstrumentRecord(
        instrument_id=inst_id,
        symbol=symbol,
        isin=isin or f"TN00000{abs(hash(inst_id)) % 100000:05d}",
        market_segment=segment,
        currency="TND",
        listed_from=date(2025, 1, 1),
        listed_to=None,
        valid_from=date(2025, 1, 1),
        valid_to=None,
        source_document_id="test",
        is_competition_eligible=eligible,
    )


def _make_bar(
    inst_id: str,
    symbol: str,
    session_date: date,
    close: str,
    volume: int,
    *,
    open_px: str | None = None,
    high_px: str | None = None,
    low_px: str | None = None,
    status: str | None = None,
    source_id: str = "test-feed",
) -> DailyBar:
    c = Decimal(close)
    o = Decimal(open_px) if open_px is not None else c
    h = Decimal(high_px) if high_px is not None else max(o, c)
    lo = Decimal(low_px) if low_px is not None else min(o, c)
    eff_status = status or ("traded" if volume > 0 else "untraded")
    turn = (
        (c * Decimal(volume)).quantize(Decimal("0.001"))
        if eff_status == "traded"
        else Decimal("0.000")
    )
    ts = datetime.fromisoformat(f"{session_date.isoformat()}T16:00:00+01:00")
    return DailyBar(
        instrument_id=inst_id,
        symbol=symbol,
        session_date=session_date,
        open=o,
        high=h,
        low=lo,
        close=c,
        volume_shares=volume if eff_status == "traded" else 0,
        turnover_tnd=turn,
        status=eff_status,
        source_id=source_id,
        published_at=ts,
        ingested_at=ts,
    )


def test_frozen_config_and_auto_order_guard() -> None:
    cfg = load_frozen_sparse_research_config()
    assert cfg.model_version == SPARSE_OPPORTUNITY_MODEL_VERSION == "sparse_research_v1"
    assert cfg.auto_order_submission is False
    assert cfg.hb_recovery_enabled_by_default is False
    assert len(cfg.config_sha256()) == 64

    with pytest.raises(ValueError, match="auto_order_submission"):
        SparseResearchConfig(auto_order_submission=True)


def test_canonical_alias_resolution_and_20s_window_fix() -> None:
    cc_events = get_instrument_macro_context(
        "CARTHAGE_CEMENT", cutoff=datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    )
    stpap_events = get_instrument_macro_context(
        "SOTIPAPIER", cutoff=datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    )
    icf_events = get_instrument_macro_context(
        "ICF", cutoff=datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    )
    pgh_events = get_instrument_macro_context(
        "POULINA_GROUP_HOLDING", cutoff=datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    )
    assert any(e.event_id == "LOI_FINANCES_2026_ENERGY_TRANSITION" for e in cc_events)
    assert any(e.event_id == "LOI_FINANCES_2026_ENERGY_TRANSITION" for e in stpap_events)
    assert any(e.event_id == "LOI_FINANCES_2026_ENERGY_TRANSITION" for e in icf_events)
    assert any(e.event_id == "INS_CPI_INFLATION_OCT2026" for e in pgh_events)
    assert "CARTHAGE_CEMENT" in resolve_instrument_aliases("CC")

    # Verify research_coverage.py 20-session frequency fix (anchor + 20 sessions = 21 total)
    dates = _session_days(25)
    cal = _make_calendar(dates)
    inst = _make_inst("ICF", "ICF", isin="TN0003200755")
    # Make anchor (index 4) traded, then 14 of last 20 sessions traded, 6 untraded -> exactly 0.70
    bars = []
    for idx, d in enumerate(dates):
        vol = 0 if 10 <= idx <= 15 else 100
        bars.append(_make_bar("ICF", "ICF", d, "134.200", vol))
    cutoff = datetime.fromisoformat(f"{dates[-1].isoformat()}T17:00:00+01:00").astimezone(UTC)
    cov = evaluate_market_research_coverage([inst], cal, bars, cutoff)
    assert cov.by_instrument["ICF"].trade_frequency_20s == Decimal("0.7")


def test_seven_layers_five_states_no_zero_coercion_and_no_stale_fill() -> None:
    dates = _session_days(65)
    cal = _make_calendar(dates)
    cutoff = datetime.fromisoformat(f"{dates[-1].isoformat()}T17:00:00+01:00").astimezone(UTC)

    insts = [
        _make_inst("STA", "STA", isin="TNNGTFLC2986"),  # Full continuous + challenge
        _make_inst("ICF", "ICF", isin="TN0003200755"),  # Partial: 1 missing bar in 60s
        _make_inst("BH_ASSURANCE", "BH ASSURANCE"),  # Stale untraded 30 sessions -> Event or Insuff
        _make_inst("CARTHAGE_CEMENT", "CARTHAGE CEMENT", isin="TN0007400013"),  # Stale + Event
        _make_inst("MONOPRIX", "MONOPRIX", segment="principal_fixing"),  # Full, NOT challenge
        _make_inst("AETECH", "AETECH", segment="surveillance"),  # Restricted segment w/ partial
    ]

    bars: list[DailyBar] = []
    for idx, d in enumerate(dates):
        # STA: steady uptrend, active daily
        px_sta = Decimal("100.000") + Decimal(idx) * Decimal("0.500")
        bars.append(_make_bar("STA", "STA", d, str(px_sta), 500))

        # ICF: missing index 30, traded others with moderate turnover
        if idx != 30:
            px_icf = Decimal("120.000") + Decimal(idx) * Decimal("0.100")
            bars.append(_make_bar("ICF", "ICF", d, str(px_icf), 50))

        # BH_ASSURANCE: traded once early, untraded for final 30 sessions -> INSUFFICIENT_EVIDENCE
        if idx == 5:
            bars.append(_make_bar("BH_ASSURANCE", "BH ASSURANCE", d, "75.000", 10))
        else:
            bars.append(_make_bar("BH_ASSURANCE", "BH ASSURANCE", d, "75.000", 0))

        # CARTHAGE_CEMENT: untraded last 25 sessions, but macro event matches via alias
        if idx < 40:
            bars.append(_make_bar("CARTHAGE_CEMENT", "CARTHAGE CEMENT", d, "1.800", 5000))
        else:
            bars.append(_make_bar("CARTHAGE_CEMENT", "CARTHAGE CEMENT", d, "1.800", 0))

        # MONOPRIX: full history, active, non-challenge
        px_mnp = Decimal("10.000") + Decimal(idx) * Decimal("0.050")
        bars.append(_make_bar("MONOPRIX", "MONOPRIX", d, str(px_mnp), 1000))

        # AETECH: surveillance segment, traded 10 bars including latest
        vol_aet = 200 if idx >= 55 else 0
        bars.append(_make_bar("AETECH", "AETECH", d, "0.450", vol_aet))

    # Add PIT document chunk for CARTHAGE_CEMENT and future-dated chunk (must be excluded)
    pit_chunk = DocumentChunk(
        chunk_id="cc-q3-ok",
        source_document_id="cmf_cc_q3_2026",
        instrument_ids=["CC"],
        published_at=datetime.fromisoformat(f"{dates[-2].isoformat()}T12:00:00+00:00").isoformat(),
        ingested_at=datetime.fromisoformat(f"{dates[-2].isoformat()}T12:05:00+00:00").isoformat(),
        language="fr",
        section_locator="p.1",
        chunk_index=0,
        chunk_text="Carthage Cement Q3 activity update.",
        chunk_sha256="a" * 64,
    )
    future_chunk = replace(
        pit_chunk,
        chunk_id="future-leak",
        published_at=(cutoff + timedelta(days=2)).isoformat(),
        ingested_at=(cutoff + timedelta(days=2)).isoformat(),
    )
    synthetic_chunk = replace(
        pit_chunk,
        chunk_id="synth-drop",
        source_document_id="synthetic-fixture-doc",
    )

    rep = evaluate_sparse_market_research(
        insts,
        cal,
        bars,
        cutoff,
        document_chunks=[pit_chunk, future_chunk, synthetic_chunk],
        fundamental_records=[
            FundamentalSnapshotRecord(
                instrument_id="STA",
                period_label="2026Q3",
                published_at=cutoff - timedelta(days=5),
                ingested_at=cutoff - timedelta(days=5),
                source_label="BVMT Q3",
                revenue_yoy_pct=14.2,
                pe_ratio=11.5,
                dividend_yield_pct=3.8,
            )
        ],
        held_positions={"STA": {"quantity": 30, "latest_price_tnd": "132.000"}},
        pending_orders=[
            PendingOrderReservation("P1", "STA", "BUY", 5, Decimal("132.000")),
        ],
        sector_by_instrument={"STA": "DISTRIBUTEURS"},
    )

    assert rep.model_version == "sparse_research_v1"
    assert set(rep.status_counts.keys()) == {
        "FULL_RESEARCH_AVAILABLE",
        "PARTIAL_RESEARCH_AVAILABLE",
        "EVENT_RESEARCH_AVAILABLE",
        "INSUFFICIENT_EVIDENCE",
        "RESTRICTED_FOR_TRADING",
    }

    sta = rep.by_instrument["STA"]
    assert sta.research_status == "FULL_RESEARCH_AVAILABLE"
    assert sta.trading_eligibility.status == "CHALLENGE_ORDER_ELIGIBLE"
    assert sta.fundamental_evidence.availability_status == "AVAILABLE"
    assert sta.portfolio_risk.held_shares == 30
    assert sta.portfolio_risk.cap_headroom_tnd < Decimal("5000.000")

    icf = rep.by_instrument["ICF"]
    assert icf.research_status == "PARTIAL_RESEARCH_AVAILABLE"
    assert icf.data_quality_freshness.missing_open_sessions_60s == 1
    assert icf.fundamental_evidence.availability_status == "UNAVAILABLE"
    assert icf.fundamental_evidence.gap_reason is not None
    # Verify non-zero observed turnover is NEVER coerced to 0
    assert icf.liquidity_execution_feasibility.median_turnover_20s_tnd is not None
    assert icf.liquidity_execution_feasibility.median_turnover_20s_tnd > Decimal("0")

    cc = rep.by_instrument["CARTHAGE_CEMENT"]
    assert cc.research_status == "EVENT_RESEARCH_AVAILABLE"
    assert cc.liquidity_execution_feasibility.executable_reference_price_tnd is None
    assert cc.liquidity_execution_feasibility.last_verified_close_tnd == Decimal("1.800")
    assert cc.event_disclosure_evidence.events_count == 1
    assert cc.event_disclosure_evidence.synthetic_excluded_count == 1
    assert cc.quantitative_trend_evidence.quantitative_score is None

    bha = rep.by_instrument["BH_ASSURANCE"]
    assert bha.research_status == "INSUFFICIENT_EVIDENCE"
    assert bha.quantitative_trend_evidence.quantitative_score is None
    assert bha.liquidity_execution_feasibility.executable_reference_price_tnd is None

    mnp = rep.by_instrument["MONOPRIX"]
    assert mnp.research_status == "FULL_RESEARCH_AVAILABLE"
    assert mnp.trading_eligibility.status == "RESEARCH_ONLY_NOT_IN_CHALLENGE"
    assert mnp.explanation.is_tradable is False

    aet = rep.by_instrument["AETECH"]
    assert aet.research_status == "RESTRICTED_FOR_TRADING"
    assert aet.trading_eligibility.status == "MARKET_SEGMENT_RESTRICTED"
    assert aet.trading_eligibility.underlying_research_status == "PARTIAL_RESEARCH_AVAILABLE"

    # Serialization check: None fields serialize cleanly as JSON null (no NaN)
    serialized = json.dumps(rep.to_dict(), allow_nan=False)
    assert "NaN" not in serialized
    assert "automatic BUY" in sta.explanation.disclaimer


def test_awakening_detection_and_future_data_mutation_invariance() -> None:
    dates = _session_days(66)
    cal = _make_calendar(dates)
    cutoff_day = dates[-3]
    cutoff = datetime.fromisoformat(f"{cutoff_day.isoformat()}T17:00:00+01:00").astimezone(UTC)

    inst = _make_inst("SPARSE_X", "SPARSE X")
    bars_before: list[DailyBar] = []
    for idx, d in enumerate(dates[:-2]):
        if d == cutoff_day:
            # Awakening: 25,000 TND vs ~500 TND baseline, +3% day
            bars_before.append(_make_bar("SPARSE_X", "SPARSE X", d, "10.300", 2500))
        else:
            bars_before.append(
                _make_bar("SPARSE_X", "SPARSE X", d, "10.000", 50 if idx % 2 == 0 else 0)
            )

    bars_with_future = list(bars_before) + [
        _make_bar("SPARSE_X", "SPARSE X", dates[-2], "15.000", 50000),
        _make_bar("SPARSE_X", "SPARSE X", dates[-1], "18.000", 80000),
    ]

    rep_a = evaluate_sparse_market_research([inst], cal, bars_before, cutoff)
    rep_b = evaluate_sparse_market_research([inst], cal, bars_with_future, cutoff)

    assert rep_a.input_data_sha256 == rep_b.input_data_sha256
    assert rep_a.selected_candidate_ids == rep_b.selected_candidate_ids == ["SPARSE_X"]
    a_x = rep_a.by_instrument["SPARSE_X"]
    b_x = rep_b.by_instrument["SPARSE_X"]
    assert a_x.quantitative_trend_evidence.awakening_detected is True
    assert a_x.quantitative_trend_evidence.turnover_awakening_ratio is not None
    assert a_x.quantitative_trend_evidence.turnover_awakening_ratio >= 3.0
    assert a_x.to_dict() == b_x.to_dict()


def test_non_destructive_hb_recovery_and_suspensions(tmp_path: Path) -> None:
    rej_file = tmp_path / "rejections.json"
    rej_payload = {
        "rejections": [
            {
                "line_number": 10,
                "reason": "OHLC bounds are inconsistent",
                "raw_row": json.dumps(
                    {
                        "dateSeance": "2026-09-22",
                        "codeISIN": "TN0003200755",
                        "mnemo": "ICF",
                        "valeur": "ICF",
                        "coursOuvert": "143.6",
                        "plusHaut": "143.6",
                        "plusBas": "143.6",
                        "cloture": "135.07",
                        "indicateur": "B",
                        "quantites": 31,
                        "capitaux": "4451.6",
                    }
                ),
            }
        ]
    }
    rej_file.write_text(json.dumps(rej_payload), encoding="utf-8")

    hb_bars, hb_meta = extract_limit_reserved_bars_from_rejections([rej_file], allow_recovery=True)
    assert len(hb_bars) == 1
    assert len(hb_meta) == 1
    assert hb_bars[0].close == Decimal("135.07")
    assert hb_bars[0].low == Decimal("135.07")
    assert hb_bars[0].high == Decimal("143.6")
    validate_bars(hb_bars)

    dates = _session_days(5, start=date(2026, 9, 21))
    cal = _make_calendar(dates)
    inst = _make_inst("ICF", "ICF", isin="TN0003200755")
    canonical = [_make_bar("ICF", "ICF", d, "136.000", 20) for d in dates if d != date(2026, 9, 22)]
    merged, keys = merge_canonical_with_hb_recovery(canonical, hb_bars)
    assert ("ICF", date(2026, 9, 22)) in keys
    assert len(merged) == len(canonical) + 1

    # Verify official suspension on cutoff marks RESTRICTED_FOR_TRADING / SUSPENDED_AT_CUTOFF
    cutoff = datetime.fromisoformat(f"{dates[-1].isoformat()}T17:00:00+01:00").astimezone(UTC)
    susp_rep = evaluate_sparse_market_research(
        [inst],
        cal,
        merged,
        cutoff,
        suspensions=[SuspensionRecord("ICF", dates[-1], "CMFTEST", "test suspension")],
    )
    assert susp_rep.by_instrument["ICF"].research_status == "RESTRICTED_FOR_TRADING"
    assert susp_rep.by_instrument["ICF"].trading_eligibility.status == "SUSPENDED_AT_CUTOFF"


def test_walk_forward_generalization_and_phase7_forward_ledger(tmp_path: Path) -> None:
    dates = _session_days(95)
    cal = _make_calendar(dates)
    insts = [
        _make_inst("BENCH_WIN", "BENCH WIN"),
        _make_inst("ICF", "ICF", isin="TN0003200755"),
        _make_inst("SPARSE_ROSE", "SPARSE ROSE"),
        _make_inst("SPARSE_FELL", "SPARSE FELL"),
        _make_inst("FLAT_BENCH", "FLAT BENCH"),
    ]
    bars: list[DailyBar] = []
    for idx, d in enumerate(dates):
        # Continuous benchmark winner
        bars.append(
            _make_bar(
                "BENCH_WIN",
                "BENCH WIN",
                d,
                str(Decimal("20.000") + Decimal(idx) * Decimal("0.200")),
                2000,
            )
        )
        # ICF: missing idx 55, rises after idx 70
        if idx != 55:
            px_icf = Decimal("100.000") + Decimal(max(0, idx - 70)) * Decimal("1.200")
            vol_icf = 400 if idx >= 70 else 50
            bars.append(_make_bar("ICF", "ICF", d, str(px_icf), vol_icf))
        # SPARSE_ROSE: silent until idx 68, awakens then climbs
        if idx < 68:
            bars.append(
                _make_bar("SPARSE_ROSE", "SPARSE ROSE", d, "10.000", 10 if idx % 3 == 0 else 0)
            )
        else:
            px_sr = Decimal("10.500") + Decimal(idx - 68) * Decimal("0.400")
            bars.append(_make_bar("SPARSE_ROSE", "SPARSE ROSE", d, str(px_sr), 3000))
        # SPARSE_FELL: drops sharply
        px_sf = max(Decimal("2.000"), Decimal("20.000") - Decimal(idx) * Decimal("0.150"))
        bars.append(
            _make_bar("SPARSE_FELL", "SPARSE FELL", d, str(px_sf), 30 if idx % 2 == 0 else 0)
        )
        # FLAT_BENCH
        bars.append(_make_bar("FLAT_BENCH", "FLAT BENCH", d, "15.000", 2500))

    wf = run_walk_forward_generalization_benchmark(
        insts,
        cal,
        bars,
        warmup_sessions=61,
        forward_horizon_sessions=10,
        step_sessions=10,
    )
    assert len(wf.evaluation_dates) >= 2
    assert set(wf.cohort_comparison.keys()) == set(COHORT_NAMES)
    assert (
        wf.sparse_raw_metrics.research_coverage_rate >= wf.baseline_metrics.research_coverage_rate
    )

    # Phase 7: record prospective signals & test conservative promotion gate
    sig_ledger = tmp_path / "signals.jsonl"
    settle_ledger = tmp_path / "settled.jsonl"
    cut_day = dates[72]
    cut_dt = datetime.fromisoformat(f"{cut_day.isoformat()}T17:00:00+01:00").astimezone(UTC)
    pit_bars = [b for b in bars if b.session_date <= cut_day]
    base_r = rank_session_baseline(insts, cal, pit_bars, cut_dt, min_trade_frequency=0.60)
    sp_r = evaluate_sparse_market_research(insts, cal, pit_bars, cut_dt, baseline_report=base_r)

    recs = record_prospective_report_signals(
        sig_ledger, sp_r, recorded_at=cut_dt, baseline_report=base_r, horizon_sessions=10
    )
    assert len(recs) == len(insts)
    # Duplicate ID protection
    with pytest.raises(ValueError, match="Duplicate signal_id"):
        record_prospective_signal(sig_ledger, recs[0])

    # Immature settlement must return empty list when only bars <= cut_day are supplied
    assert (
        settle_pending_prospective_signals(sig_ledger, settle_ledger, calendar=cal, bars=pit_bars)
        == []
    )
    # Mature settlement using full bars
    settled = settle_pending_prospective_signals(sig_ledger, settle_ledger, calendar=cal, bars=bars)
    assert len(settled) == len(insts)

    # Retrospective ICF-only success MUST remain BLOCKED for promotion
    icf_only_outcomes = [
        SettledSignalOutcome(
            signal_id=f"icf-{i}",
            recorded_at=cut_dt.isoformat(),
            session_date=dates[60 + i].isoformat(),
            settlement_session_date=dates[70 + i].isoformat(),
            horizon_sessions=10,
            instrument_id="ICF",
            symbol="ICF",
            model_version=SPARSE_OPPORTUNITY_MODEL_VERSION,
            entry_bar_date=dates[61 + i].isoformat(),
            entry_fill_price_tnd="100.000",
            entry_fill_shares=40,
            exit_bar_date=dates[70 + i].isoformat(),
            exit_price_tnd="115.000",
            executable_fill_status="FILLED",
            gross_return_pct=15.0,
            net_return_after_costs_pct=13.5,
            baseline_selected=False,
            model_selected=True,
            is_false_positive=False,
            is_missed_opportunity=False,
            settlement_notes="test",
        )
        for i in range(22)
    ]
    blocked_gate = evaluate_promotion_readiness(icf_only_outcomes)
    assert blocked_gate.eligible_for_promotion is False
    assert any("non_icf" in g.lower() for g in blocked_gate.failed_gates)

    # Diverse multi-stock positive prospective outcomes pass all gates
    diverse_outcomes = [
        replace(
            icf_only_outcomes[0],
            signal_id=f"div-{i}",
            instrument_id=f"ST{i % 5}",
            symbol=f"S{i % 5}",
            session_date=dates[50 + i].isoformat(),
        )
        for i in range(22)
    ]
    approved_gate = evaluate_promotion_readiness(diverse_outcomes)
    assert approved_gate.eligible_for_promotion is True
    assert approved_gate.failed_gates == []


@pytest.mark.skipif(
    not STARTER_OFFICIAL_DIR.is_dir(),
    reason="Read-only bvmt_official_2026 starter-kit snapshot unavailable",
)
def test_official_bvmt_2026_icf_and_cohort_generalization_readonly() -> None:
    bars = read_bars_csv(STARTER_OFFICIAL_DIR / "daily_bars.canonical.csv")
    master = read_instrument_master(STARTER_OFFICIAL_DIR / "instrument_master.csv")
    cal = read_exchange_calendar(STARTER_OFFICIAL_DIR / "exchange_calendar.csv")
    cal_p, bars_p = prepare_pit_calendar_and_bars(cal, bars)
    hb_bars, hb_meta = extract_limit_reserved_bars_from_rejections(
        [STARTER_OFFICIAL_DIR / "rejections.json", STARTER_OFFICIAL_DIR / "rejected_rows.csv"],
        allow_recovery=False,
    )
    assert hb_bars == []
    assert any(m.instrument_id == "ICF" and m.session_date == date(2026, 9, 22) for m in hb_meta)

    cutoff = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    base_rep = rank_session_baseline(
        master,
        cal_p,
        bars_p,
        cutoff,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("1000"),
    )
    sp_rep = evaluate_sparse_market_research(
        master, cal_p, bars_p, cutoff, baseline_report=base_rep, limit_reserved_meta=hb_meta
    )

    icf = sp_rep.by_instrument["ICF"]
    assert icf.research_status == "PARTIAL_RESEARCH_AVAILABLE"
    assert icf.trading_eligibility.status == "CHALLENGE_ORDER_ELIGIBLE"
    assert icf.is_selected_candidate is False
    assert icf.liquidity_execution_feasibility.median_turnover_20s_tnd == Decimal("1364.090")
    assert icf.liquidity_execution_feasibility.trade_frequency_20s == 0.7
    assert icf.data_quality_freshness.missing_open_sessions_60s == 1
    # No saved ICF disclosure was supplied. Static catalog assertions are not evidence.
    assert icf.event_disclosure_evidence.events_count == 0
    assert icf.event_disclosure_evidence.availability_status == "NO_VERIFIED_EVENTS"
    assert sp_rep.by_instrument["BH_ASSURANCE"].research_status == "INSUFFICIENT_EVIDENCE"
    assert (
        sp_rep.by_instrument[
            "BH_ASSURANCE"
        ].liquidity_execution_feasibility.executable_reference_price_tnd
        is None
    )
    assert sp_rep.by_instrument["AETECH"].research_status == "RESTRICTED_FOR_TRADING"

    wf = run_benchmark_from_data_dir(
        STARTER_OFFICIAL_DIR,
        staging_dir=STARTER_STAGING_DIR if STARTER_STAGING_DIR.is_dir() else None,
        forward_horizon_sessions=10,
        step_sessions=10,
    )
    assert wf.sparse_raw_metrics.research_coverage_rate > wf.baseline_metrics.research_coverage_rate
    assert wf.sparse_raw_metrics.false_positive_rate is not None
    assert wf.baseline_metrics.false_positive_rate is not None
    assert (
        wf.sparse_raw_metrics.false_positive_rate <= wf.baseline_metrics.false_positive_rate + 0.05
    )
    assert (
        wf.cohort_comparison["OTHER_EXCLUDED_CHALLENGE"]["sparse_research_v1_raw"].selected_count
        > 0
    )
