"""Isolated Milestone 14 regression tests verifying G1 scoring defects,
POULINA ISIN split identity bug, Challenge universe leakage, and G2 ICF forensics.

Strictly read-only over C:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit.
Run against the integration code tree with:
    PYTHONPATH=C:\\Users\\Thinkcenter\\Desktop\\BVMT\\bvmt-starter-kit\\src pytest -q tests/test_m14_quant_audit.py
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    read_exchange_calendar,
    read_instrument_master,
)
from bvmt.challenge_universe import (
    get_challenge_symbol_set,
    get_challenge_universe,
    is_in_challenge_universe,
)
from bvmt.data import DailyBar, read_bars_csv
from bvmt.execution import MarketOrder, estimate_next_bar_fill
from bvmt.features import rank_session_baseline
from bvmt.holding_period import evaluate_holding_periods
from bvmt.ledger import PortfolioLedger
from bvmt.macro_events import get_verified_macro_intelligence
from bvmt.multi_horizon import evaluate_multi_horizon_intelligence
from bvmt.recommendations import generate_recommendations
from bvmt.sparse_generalization import prepare_pit_calendar_and_bars
from bvmt.sparse_research import (
    evaluate_sparse_market_research,
    extract_limit_reserved_bars_from_rejections,
    load_emetteur_sector_map,
    load_frozen_sparse_research_config,
)

STARTER_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = STARTER_ROOT / "data" / "processed" / "bvmt_official_2026"
STAGING_DIR = STARTER_ROOT / "data" / "staging"
LEDGER_PATH = STARTER_ROOT / "data" / "portfolio" / "real_competition_ledger.json"

pytestmark = pytest.mark.skipif(
    not PROCESSED_DIR.is_dir(),
    reason="Official BVMT processed dataset in integration workspace not available.",
)


@pytest.fixture(scope="module")
def official_dataset():
    instruments = read_instrument_master(PROCESSED_DIR / "instrument_master.csv")
    calendar = read_exchange_calendar(PROCESSED_DIR / "exchange_calendar.csv")
    bars = read_bars_csv(PROCESSED_DIR / "daily_bars.canonical.csv")
    cal_pit, bars_pit = prepare_pit_calendar_and_bars(calendar, bars)
    sector_map = load_emetteur_sector_map(STAGING_DIR / "mapping_emetteur.json")
    sparse_cfg = load_frozen_sparse_research_config(
        STARTER_ROOT / "configs" / "sparse_research_v1.json"
    )
    return {
        "instruments": instruments,
        "calendar_raw": calendar,
        "bars_raw": bars,
        "cal_pit": cal_pit,
        "bars_pit": bars_pit,
        "sector_map": sector_map,
        "sparse_cfg": sparse_cfg,
    }


def test_g1_blank_published_at_raises_on_raw_canonical_bars(official_dataset) -> None:
    bars_raw = official_dataset["bars_raw"]
    assert len(bars_raw) == 17110
    assert sum(1 for b in bars_raw if b.published_at is None) == 17110

    with pytest.raises(ValueError, match="No completed open exchange sessions on or before cutoff"):
        rank_session_baseline(
            official_dataset["instruments"],
            official_dataset["calendar_raw"],
            bars_raw,
            datetime(2026, 11, 10, 17, 0, tzinfo=UTC),
        )


def test_g1_zero_volatility_score_is_bounded() -> None:
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
    tiny_cal: list[ExchangeSession] = []
    tiny_bars: list[DailyBar] = []
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

    report = rank_session_baseline(
        syn_inst, tiny_cal, tiny_bars, datetime(2026, 12, 31, tzinfo=UTC)
    )
    top = next(c for c in report.candidates if c.instrument_id == "FLAT_SPIKE")
    other = next(c for c in report.candidates if c.instrument_id == "NORMAL_STK")
    assert top.instrument_id == "FLAT_SPIKE"
    assert top.volatility_20s == 0
    assert top.composite_score == pytest.approx(0.5)
    assert other.instrument_id == "NORMAL_STK"
    assert all(-1 <= c.composite_score <= 1 for c in report.candidates)


def test_g1_recommendations_excludes_non_challenge_buy_candidates(official_dataset) -> None:
    cut_10 = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
    base_10 = rank_session_baseline(
        official_dataset["instruments"],
        official_dataset["cal_pit"],
        official_dataset["bars_pit"],
        cut_10,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )
    ledger = PortfolioLedger.load(LEDGER_PATH)
    pmap_10 = {
        b.instrument_id: b.close
        for b in sorted(official_dataset["bars_pit"], key=lambda x: x.session_date)
        if b.status == "traded"
    }
    recs = generate_recommendations(
        base_10,
        ledger,
        generated_at=cut_10,
        simulation_profile="RESEARCH_CONSERVATIVE",
        data_is_synthetic=False,
        rule_blocker_count=72,
        market_quotes=pmap_10,
    )
    non_challenge_buys = [
        r.instrument_id
        for r in recs.recommendations
        if r.category == "BUY CANDIDATE"
        and not is_in_challenge_universe(r.instrument_id, symbol=r.symbol)
    ]
    assert "MONOPRIX" not in non_challenge_buys
    assert not non_challenge_buys


def test_g1_multi_horizon_excludes_future_events_and_preserves_zero(official_dataset) -> None:
    cut_10 = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
    base_10 = rank_session_baseline(
        official_dataset["instruments"],
        official_dataset["cal_pit"],
        official_dataset["bars_pit"],
        cut_10,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )
    mh_oct09 = evaluate_multi_horizon_intelligence(
        portfolio_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("38752.350"),
        held_positions={},
        market_rankings=base_10.candidates[:10],
        as_of_session="2026-10-09",
    )
    leaked_ids = [
        ev["event_id"] for ev in mh_oct09.macro_events if ev["published_at"] > "2026-10-09"
    ]
    assert leaked_ids == []

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

    mh_fake = evaluate_multi_horizon_intelligence(
        portfolio_equity_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("38752.350"),
        held_positions={},
        market_rankings=[_FakeZeroShortRank()],
        as_of_session="2026-11-10",
    )
    assert mh_fake.swing_candidates == []
    # Zero momentum cannot become a positive swing through a falsy fallback.


def test_g1_holding_period_symbol_set_drops_27_of_42_and_hardcodes_194(official_dataset) -> None:
    symbol_set = get_challenge_symbol_set()
    matched = [m for m in official_dataset["instruments"] if m.instrument_id in symbol_set]
    assert len(get_challenge_universe()) == 42
    assert len(matched) == 15

    hp_chal = evaluate_holding_periods(
        bars_path=PROCESSED_DIR / "daily_bars.canonical.csv",
        calendar_path=PROCESSED_DIR / "exchange_calendar.csv",
        instruments_path=PROCESSED_DIR / "instrument_master.csv",
        universe="TUNIS_BOURSE_CHALLENGE",
    )
    assert hp_chal.dataset_session_count == 196
    assert not any("194 trading sessions" in line for line in hp_chal.reasoning)
    assert hp_chal.membership_accounted_count == 42


def test_g1_macro_events_alias_mismatch() -> None:
    cut_10 = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
    no_alias = get_verified_macro_intelligence(
        cutoff=cut_10, instrument_id="CARTHAGE_CEMENT", include_aliases=False
    )
    with_alias = get_verified_macro_intelligence(
        cutoff=cut_10, instrument_id="CARTHAGE_CEMENT", include_aliases=True
    )
    assert len(no_alias) == 0
    assert len(with_alias) >= 1


def test_g1_sparse_v1_non_challenge_slot_displacement_and_negative_awakening(
    official_dataset,
) -> None:
    cut_10 = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
    base_10 = rank_session_baseline(
        official_dataset["instruments"],
        official_dataset["cal_pit"],
        official_dataset["bars_pit"],
        cut_10,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )
    _, hb_meta = extract_limit_reserved_bars_from_rejections(
        [PROCESSED_DIR / "rejections.json", PROCESSED_DIR / "rejected_rows.csv"],
        allow_recovery=True,
    )
    sp_10 = evaluate_sparse_market_research(
        official_dataset["instruments"],
        official_dataset["cal_pit"],
        official_dataset["bars_pit"],
        cut_10,
        config=official_dataset["sparse_cfg"],
        baseline_report=base_10,
        sector_by_instrument=official_dataset["sector_map"],
        limit_reserved_meta=hb_meta,
    )
    non_chal_selected = [
        a.instrument_id
        for a in sp_10.assessments
        if a.is_selected_candidate and not a.competition_eligibility.in_challenge_universe
    ]
    assert set(non_chal_selected) == {"MONOPRIX", "ESSOUKNA", "CIL"}
    challenge = evaluate_sparse_market_research(
        official_dataset["instruments"],
        official_dataset["cal_pit"],
        official_dataset["bars_pit"],
        cut_10,
        config=official_dataset["sparse_cfg"],
        baseline_report=base_10,
        universe="TUNIS_BOURSE_CHALLENGE",
    )
    assert all(is_in_challenge_universe(i) for i in challenge.selected_candidate_ids)
    assert not set(non_chal_selected) & set(challenge.selected_candidate_ids)
    assert all(
        not a.is_selected_candidate
        for a in challenge.assessments
        if not a.competition_eligibility.in_challenge_universe
    )

    by_id = sp_10.by_instrument
    icf = by_id["ICF"]
    assert icf.quantitative_trend_evidence.awakening_detected is True
    assert icf.quantitative_trend_evidence.turnover_awakening_ratio == pytest.approx(
        357.83, abs=0.05
    )
    assert icf.is_selected_candidate is False
    assert "Below candidate_top_k=8 cap" in (icf.candidate_selection_reason or "")

    assert by_id["BNA"].quantitative_trend_evidence.awakening_detected is True
    assert (by_id["BNA"].quantitative_trend_evidence.quantitative_score or 0.0) < 0.0


def test_poulina_isin_split_regression(official_dataset) -> None:
    poulina_master = [r for r in official_dataset["instruments"] if r.isin == "TN0005700018"]
    ids = {r.instrument_id: r for r in poulina_master}
    assert set(ids.keys()) == {"POULINA_GP_HOLDING", "POULINA_GROUP_HOLDING"}
    assert ids["POULINA_GROUP_HOLDING"].valid_to is None
    assert ids["POULINA_GP_HOLDING"].valid_to is None

    bars_by_id: dict[str, list[DailyBar]] = defaultdict(list)
    for b in official_dataset["bars_raw"]:
        if b.instrument_id in ids:
            bars_by_id[b.instrument_id].append(b)

    grp_dates = sorted(b.session_date for b in bars_by_id["POULINA_GROUP_HOLDING"])
    gp_dates = sorted(b.session_date for b in bars_by_id["POULINA_GP_HOLDING"])
    assert len(grp_dates) == 68
    assert grp_dates[-1] == date(2026, 4, 8)
    assert len(gp_dates) == 128
    assert gp_dates[0] == date(2026, 4, 10)
    assert not (set(grp_dates) & set(gp_dates))


def test_g2_icf_sep22_hb_counterfactual_and_nov9_nov10_fills(official_dataset) -> None:
    cal_pit = official_dataset["cal_pit"]
    bars_pit = official_dataset["bars_pit"]
    cal_06 = [s for s in cal_pit if s.session_date <= date(2026, 11, 6)]
    bars_06 = [b for b in bars_pit if b.session_date <= date(2026, 11, 6)]
    cut_06 = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)

    icf_bars = [b for b in bars_pit if b.instrument_id == "ICF"]
    assert len(icf_bars) == 195
    open_set = {s.session_date for s in cal_pit if s.is_open}
    assert sorted(open_set - {b.session_date for b in icf_bars}) == [date(2026, 9, 22)]

    # Counterfactual restoration of 2026-09-22 B-status bar does NOT rescue ICF on Nov 06 (liquidity < 5000 TND)
    for px in (Decimal("143.600"), Decimal("135.070")):
        cf_bar = DailyBar(
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
            source_id="cf_test",
            published_at=datetime(2026, 9, 22, 15, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 9, 22, 15, 0, tzinfo=UTC),
            isin="TN0003200755",
        )
        b_cf = rank_session_baseline(
            official_dataset["instruments"],
            cal_06,
            list(bars_06) + [cf_bar],
            cut_06,
            min_trade_frequency=0.60,
            min_median_turnover_tnd=Decimal("5000"),
        )
        exclusions = [e.reason for e in b_cf.exclusions if e.instrument_id == "ICF"]
        assert exclusions == ["insufficient_liquidity"]

    # Simulated next-open fills with 10% participation cap
    open_dates = sorted(open_set)
    bar_oct12 = next(b for b in icf_bars if b.session_date == date(2026, 10, 12))
    bar_nov09 = next(b for b in icf_bars if b.session_date == date(2026, 11, 9))
    bar_nov10 = next(b for b in icf_bars if b.session_date == date(2026, 11, 10))

    fill_oct12 = estimate_next_bar_fill(
        MarketOrder("ICF", open_dates[open_dates.index(date(2026, 10, 12)) - 1], "buy", 31),
        bar_oct12,
        participation_rate=Decimal("0.10"),
        remaining_shared_capacity=int(Decimal(bar_oct12.volume_shares) * Decimal("0.10")),
        slippage_bps=Decimal("20"),
        commission_bps=Decimal("50"),
    )
    fill_nov09 = estimate_next_bar_fill(
        MarketOrder("ICF", open_dates[open_dates.index(date(2026, 11, 9)) - 1], "buy", 31),
        bar_nov09,
        participation_rate=Decimal("0.10"),
        remaining_shared_capacity=int(Decimal(bar_nov09.volume_shares) * Decimal("0.10")),
        slippage_bps=Decimal("20"),
        commission_bps=Decimal("50"),
    )
    fill_nov10 = estimate_next_bar_fill(
        MarketOrder("ICF", open_dates[open_dates.index(date(2026, 11, 10)) - 1], "buy", 31),
        bar_nov10,
        participation_rate=Decimal("0.10"),
        remaining_shared_capacity=int(Decimal(bar_nov10.volume_shares) * Decimal("0.10")),
        slippage_bps=Decimal("20"),
        commission_bps=Decimal("50"),
    )
    assert fill_oct12.quantity == 0
    assert fill_nov09.quantity == 31
    assert fill_nov10.quantity == 31


def test_real_competition_ledger_sha256_preserved() -> None:
    if not LEDGER_PATH.is_file():
        pytest.skip("Ledger file not present")
    digest = hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest().upper()
    assert digest == "0A1B86CB281187A0E9AB88A4CDE6D4DE173A5DF162111266CE1988DCBF91D395"
