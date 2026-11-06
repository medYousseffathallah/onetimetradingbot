from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bvmt.calendar import ExchangeSession, InstrumentRecord, SuspensionRecord
from bvmt.data import DailyBar, aware_timestamp
from bvmt.features import rank_demo_momentum, rank_session_baseline

CUTOFF = aware_timestamp("2026-01-09T17:00:00Z")


def test_demo_ranking_and_no_trade_exclusion(bars):
    ranking = rank_demo_momentum(bars, CUTOFF)
    assert [item.symbol for item in ranking] == ["DEMO_A", "DEMO_B"]
    assert ranking[0].score == pytest.approx(10.8 / 10.2 - 1)


def test_future_mutation_cannot_change_past_ranking(bars):
    cutoff = aware_timestamp("2026-01-08T17:00:00Z")
    before = rank_demo_momentum(bars, cutoff)
    altered = [
        replace(
            bar, open=Decimal("999"), high=Decimal("1000"), low=Decimal("998"), close=Decimal("999")
        )
        if bar.session_date.day == 9
        else bar
        for bar in bars
    ]
    assert rank_demo_momentum(altered, cutoff) == before


def test_delayed_ingestion_is_not_known_yet(bars):
    altered = [
        replace(bar, ingested_at=aware_timestamp("2026-02-01T17:00:00Z"))
        if bar.symbol == "DEMO_A"
        else bar
        for bar in bars
    ]
    assert [x.symbol for x in rank_demo_momentum(altered, CUTOFF)] == ["DEMO_B"]


def test_demo_cannot_be_used_as_real_strategy(bars):
    altered = [replace(bar, source_id="real-source") for bar in bars]
    with pytest.raises(ValueError, match="synthetic"):
        rank_demo_momentum(altered, CUTOFF)


def test_stale_data_returns_no_candidates(bars):
    assert rank_demo_momentum(bars, aware_timestamp("2026-02-01T17:00:00Z")) == []


def test_input_order_does_not_change_output(bars):
    assert rank_demo_momentum(list(reversed(bars)), CUTOFF) == rank_demo_momentum(bars, CUTOFF)


def test_future_session_with_bad_availability_cannot_enter_ranking(bars):
    future = replace(bars[4], session_date=bars[4].session_date.replace(year=2027))
    altered = [bar for bar in bars if bar is not bars[4]] + [future]
    result = rank_demo_momentum(altered, CUTOFF)
    assert next(item for item in result if item.symbol == "DEMO_A").last_session == "2026-01-08"


def _build_session_baseline_dataset(num_open_sessions: int = 65):
    tunis_tz = timezone(timedelta(hours=1))
    start = date(2026, 1, 1)
    sessions: list[ExchangeSession] = []
    open_dates: list[date] = []
    cur = start
    while len(open_dates) < num_open_sessions:
        if cur.weekday() < 5:
            # Make one mid-window weekday a holiday to verify session-based (not calendar-day) indexing
            if len(open_dates) == 30 and not any(not s.is_open for s in sessions):
                sessions.append(
                    ExchangeSession(
                        session_date=cur,
                        is_open=False,
                        schedule_type="synthetic_holiday",
                        opens_at=None,
                        closes_at=None,
                        timezone="Africa/Tunis",
                        source_document_id="cal_doc_1",
                    )
                )
            else:
                opens = datetime(cur.year, cur.month, cur.day, 9, 0, tzinfo=tunis_tz)
                closes = datetime(cur.year, cur.month, cur.day, 14, 15, tzinfo=tunis_tz)
                sessions.append(
                    ExchangeSession(
                        session_date=cur,
                        is_open=True,
                        schedule_type="synthetic_regular",
                        opens_at=opens,
                        closes_at=closes,
                        timezone="Africa/Tunis",
                        source_document_id="cal_doc_1",
                    )
                )
                open_dates.append(cur)
        cur += timedelta(days=1)

    instruments = [
        InstrumentRecord(
            instrument_id="TN0001000010",
            isin="TN0001000010",
            symbol="ALPHA",
            valid_from=start,
            valid_to=None,
            listed_from=start,
            listed_to=None,
            market_segment="Continu_Principal",
            currency="TND",
            source_document_id="master_doc_1",
        ),
        InstrumentRecord(
            instrument_id="TN0002000020",
            isin="TN0002000020",
            symbol="BETA",
            valid_from=start,
            valid_to=None,
            listed_from=start,
            listed_to=None,
            market_segment="Continu_Principal",
            currency="TND",
            source_document_id="master_doc_1",
        ),
        InstrumentRecord(
            instrument_id="TN0003000030",
            isin="TN0003000030",
            symbol="STALE",
            valid_from=start,
            valid_to=None,
            listed_from=start,
            listed_to=None,
            market_segment="Continu_Principal",
            currency="TND",
            source_document_id="master_doc_1",
        ),
        InstrumentRecord(
            instrument_id="TN0004000040",
            isin="TN0004000040",
            symbol="ILLIQ",
            valid_from=start,
            valid_to=None,
            listed_from=start,
            listed_to=None,
            market_segment="Continu_Principal",
            currency="TND",
            source_document_id="master_doc_1",
        ),
        InstrumentRecord(
            instrument_id="TN0005000050",
            isin="TN0005000050",
            symbol="FIXING_STOCK",
            valid_from=start,
            valid_to=None,
            listed_from=start,
            listed_to=None,
            market_segment="Fixing_Principal",
            currency="TND",
            source_document_id="master_doc_1",
        ),
        InstrumentRecord(
            instrument_id="TN0006000060",
            isin="TN0006000060",
            symbol="DELISTED_STOCK",
            valid_from=start,
            valid_to=open_dates[20],
            listed_from=start,
            listed_to=open_dates[20],
            market_segment="Continu_Principal",
            currency="TND",
            source_document_id="master_doc_1",
        ),
    ]

    bars: list[DailyBar] = []
    for idx, s_date in enumerate(open_dates):
        pub = datetime(s_date.year, s_date.month, s_date.day, 16, 0, tzinfo=tunis_tz)
        ing = datetime(s_date.year, s_date.month, s_date.day, 16, 5, tzinfo=tunis_tz)

        # ALPHA: strong steady uptrend (+0.5% per session), high turnover
        p_alpha = (Decimal("10.000") * (Decimal("1.005") ** idx)).quantize(Decimal("0.001"))
        bars.append(
            DailyBar(
                instrument_id="TN0001000010",
                symbol="ALPHA",
                session_date=s_date,
                open=p_alpha,
                high=p_alpha + Decimal("0.100"),
                low=p_alpha - Decimal("0.100"),
                close=p_alpha,
                volume_shares=2000,
                turnover_tnd=p_alpha * Decimal(2000),
                status="traded",
                source_id="synthetic-fixture",
                published_at=pub,
                ingested_at=ing,
            )
        )

        # BETA: mild uptrend (+0.1% per session), high turnover
        p_beta = (Decimal("20.000") * (Decimal("1.001") ** idx)).quantize(Decimal("0.001"))
        bars.append(
            DailyBar(
                instrument_id="TN0002000020",
                symbol="BETA",
                session_date=s_date,
                open=p_beta,
                high=p_beta + Decimal("0.100"),
                low=p_beta - Decimal("0.100"),
                close=p_beta,
                volume_shares=1500,
                turnover_tnd=p_beta * Decimal(1500),
                status="traded",
                source_id="synthetic-fixture",
                published_at=pub,
                ingested_at=ing,
            )
        )

        # STALE: no_trade on the last 4 open sessions
        is_stale_tail = idx >= num_open_sessions - 4
        bars.append(
            DailyBar(
                instrument_id="TN0003000030",
                symbol="STALE",
                session_date=s_date,
                open=Decimal("15.000"),
                high=Decimal("15.000"),
                low=Decimal("15.000"),
                close=Decimal("15.000"),
                volume_shares=0 if is_stale_tail else 1000,
                turnover_tnd=Decimal("0.000") if is_stale_tail else Decimal("15000.000"),
                status="no_trade" if is_stale_tail else "traded",
                source_id="synthetic-fixture",
                published_at=pub,
                ingested_at=ing,
            )
        )

        # ILLIQ: tiny turnover (50 TND < 1000 TND minimum)
        bars.append(
            DailyBar(
                instrument_id="TN0004000040",
                symbol="ILLIQ",
                session_date=s_date,
                open=Decimal("5.000"),
                high=Decimal("5.100"),
                low=Decimal("4.900"),
                close=Decimal("5.000"),
                volume_shares=10,
                turnover_tnd=Decimal("50.000"),
                status="traded",
                source_id="synthetic-fixture",
                published_at=pub,
                ingested_at=ing,
            )
        )

    cutoff = datetime(
        open_dates[-1].year, open_dates[-1].month, open_dates[-1].day, 17, 0, tzinfo=tunis_tz
    )
    return instruments, sessions, bars, open_dates, cutoff


def test_session_baseline_20_60_momentum_and_exclusion_reasons():
    instruments, sessions, bars, _, cutoff = _build_session_baseline_dataset(65)
    report = rank_session_baseline(
        instruments,
        sessions,
        bars,
        cutoff,
        short_lookback=20,
        long_lookback=60,
        min_trade_frequency=0.75,
        min_median_turnover_tnd=Decimal("1000"),
    )
    assert [c.symbol for c in report.candidates] == ["ALPHA", "BETA"]
    alpha = report.candidates[0]
    beta = report.candidates[1]
    assert alpha.momentum_20s > beta.momentum_20s > 0
    assert alpha.momentum_60s > beta.momentum_60s > 0
    assert alpha.relative_strength_20s > 0
    assert beta.relative_strength_20s < 0

    excl_reasons = {e.symbol: e.reason for e in report.exclusions}
    assert excl_reasons["STALE"] == "stale_quote"
    assert excl_reasons["ILLIQ"] == "insufficient_liquidity"
    assert excl_reasons["FIXING_STOCK"] == "ineligible_market_segment"
    assert excl_reasons["DELISTED_STOCK"] == "unlisted_or_delisted"


def test_session_baseline_future_mutation_invariance_and_suspension_exclusion():
    instruments, sessions, bars, open_dates, _ = _build_session_baseline_dataset(65)
    tunis_tz = timezone(timedelta(hours=1))
    # Evaluate at session index 61 (leaving sessions 62, 63, 64 in the future)
    cutoff_past = datetime(
        open_dates[61].year, open_dates[61].month, open_dates[61].day, 17, 0, tzinfo=tunis_tz
    )
    before = rank_session_baseline(instruments, sessions, bars, cutoff_past)

    # Mutate future bars (session index >= 62)
    mutated_bars = [
        replace(
            b,
            open=Decimal("999.000"),
            high=Decimal("1000.000"),
            low=Decimal("998.000"),
            close=Decimal("999.000"),
        )
        if b.session_date > open_dates[61]
        else b
        for b in bars
    ]
    after = rank_session_baseline(instruments, sessions, mutated_bars, cutoff_past)
    assert after == before

    # Suspending ALPHA on cutoff_past date excludes ALPHA with reason='suspended'
    susp = [
        SuspensionRecord(
            instrument_id="TN0001000010",
            session_date=open_dates[61],
            source_document_id="cmf_susp_1",
        )
    ]
    with_susp = rank_session_baseline(instruments, sessions, bars, cutoff_past, suspensions=susp)
    assert [c.symbol for c in with_susp.candidates] == ["BETA"]
    assert any(e.symbol == "ALPHA" and e.reason == "suspended" for e in with_susp.exclusions)


@pytest.mark.parametrize("segment", ["principal", "principal_continu", "principal_fixing"])
def test_official_principal_segments_and_eligibility(segment):
    instruments, sessions, bars, _, cutoff = _build_session_baseline_dataset(65)
    instruments = [replace(r, market_segment=segment) for r in instruments]
    ranked = rank_session_baseline(instruments, sessions, bars, cutoff)
    assert any(c.symbol == "ALPHA" for c in ranked.candidates)
    blocked = [replace(r, is_competition_eligible=False) for r in instruments]
    assert not rank_session_baseline(blocked, sessions, bars, cutoff).candidates
