"""Tests for research coverage, sparse-data analytics, and continuous liquidity ranking (P0)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from bvmt.api import app
from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    read_exchange_calendar,
    read_instrument_master,
)
from bvmt.data import DailyBar, read_bars_csv
from bvmt.features import rank_session_baseline
from bvmt.research_coverage import (
    evaluate_market_research_coverage,
)


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


def _make_instrument(
    inst_id: str,
    symbol: str,
    segment: str = "principal_continu",
    is_eligible: bool = True,
    isin: str | None = None,
) -> InstrumentRecord:
    import hashlib

    clean_hash = hashlib.md5(inst_id.encode()).hexdigest()[:9].upper()
    return InstrumentRecord(
        instrument_id=inst_id,
        symbol=symbol,
        isin=isin or f"TN{clean_hash}0",
        market_segment=segment,
        currency="TND",
        listed_from=date(2026, 1, 1),
        listed_to=None,
        valid_from=date(2026, 1, 1),
        valid_to=None,
        source_document_id="test",
        is_competition_eligible=is_eligible,
    )


def test_missing_observations_preserves_latest_traded_price() -> None:
    """Missing observations in lookback window mark PARTIAL_HISTORY but never set price to zero."""
    d0 = date(2026, 1, 1)
    d1 = date(2026, 1, 2)
    d2 = date(2026, 1, 3)
    cal = _make_calendar([d0, d1, d2])
    inst = _make_instrument("STOCK_A", "STOCK A")
    cutoff = datetime(2026, 1, 3, 17, 0, tzinfo=UTC)

    # Missing bar on d1
    bars = [
        DailyBar(
            instrument_id="STOCK_A",
            symbol="STOCK A",
            session_date=d0,
            open=Decimal("10.000"),
            high=Decimal("10.500"),
            low=Decimal("10.000"),
            close=Decimal("10.200"),
            volume_shares=100,
            turnover_tnd=Decimal("1020.000"),
            status="traded",
            source_id="test",
            published_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
        ),
        DailyBar(
            instrument_id="STOCK_A",
            symbol="STOCK A",
            session_date=d2,
            open=Decimal("10.200"),
            high=Decimal("11.000"),
            low=Decimal("10.200"),
            close=Decimal("10.800"),
            volume_shares=200,
            turnover_tnd=Decimal("2160.000"),
            status="traded",
            source_id="test",
            published_at=datetime(2026, 1, 3, 16, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 1, 3, 16, 0, tzinfo=UTC),
        ),
    ]

    report = evaluate_market_research_coverage([inst], cal, bars, cutoff)
    an = report.by_instrument["STOCK_A"]

    assert an.last_verified_price == Decimal("10.800")
    assert an.last_traded_date == d2
    assert an.observed_bars == 2
    assert an.total_open_sessions == 3
    assert an.classification.research_coverage_status in ("PARTIAL_HISTORY", "SPARSE_DATA")
    assert an.classification.data_quality_status == "MISSING_SESSIONS"
    assert an.observed_trade_return_pct is not None
    # Return between 10.200 and 10.800 is (10.800 / 10.200 - 1) * 100 = 5.8824%
    assert abs(float(an.observed_trade_return_pct) - 5.8824) < 0.01


def test_genuine_zero_volume_sessions_never_forward_filled() -> None:
    """Untraded sessions retain status='untraded' and zero turnover without fabricating trades."""
    d0 = date(2026, 1, 1)
    d1 = date(2026, 1, 2)
    cal = _make_calendar([d0, d1])
    inst = _make_instrument("STOCK_B", "STOCK B")
    cutoff = datetime(2026, 1, 2, 17, 0, tzinfo=UTC)

    bars = [
        DailyBar(
            instrument_id="STOCK_B",
            symbol="STOCK B",
            session_date=d0,
            open=Decimal("5.000"),
            high=Decimal("5.000"),
            low=Decimal("5.000"),
            close=Decimal("5.000"),
            volume_shares=500,
            turnover_tnd=Decimal("2500.000"),
            status="traded",
            source_id="test",
            published_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
        ),
        DailyBar(
            instrument_id="STOCK_B",
            symbol="STOCK B",
            session_date=d1,
            open=Decimal("5.000"),
            high=Decimal("5.000"),
            low=Decimal("5.000"),
            close=Decimal("5.000"),
            volume_shares=0,
            turnover_tnd=Decimal("0.000"),
            status="untraded",
            source_id="test",
            published_at=datetime(2026, 1, 2, 16, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 1, 2, 16, 0, tzinfo=UTC),
        ),
    ]

    report = evaluate_market_research_coverage([inst], cal, bars, cutoff)
    an = report.by_instrument["STOCK_B"]

    assert an.latest_bar_status == "untraded"
    assert an.last_verified_price == Decimal("5.000")
    assert an.last_traded_date == d0
    assert an.quote_age_sessions == 1
    assert an.trailing_untraded_sessions == 1


def test_sparse_instrument_quote_age_and_observed_trade_return() -> None:
    """Sparse instruments track quote age and actual observed trade return."""
    dates = [date(2026, 1, i) for i in range(1, 11)]  # 10 sessions
    cal = _make_calendar(dates)
    inst = _make_instrument("SPARSE_C", "SPARSE C")
    cutoff = datetime(2026, 1, 10, 17, 0, tzinfo=UTC)

    # Trades on day 1 (close=20) and day 4 (close=22), no trade days 5..10
    bars = []
    for d in dates:
        if d == date(2026, 1, 1):
            bars.append(
                DailyBar(
                    instrument_id="SPARSE_C",
                    symbol="SPARSE C",
                    session_date=d,
                    open=Decimal("20.000"),
                    high=Decimal("20.000"),
                    low=Decimal("20.000"),
                    close=Decimal("20.000"),
                    volume_shares=100,
                    turnover_tnd=Decimal("2000.000"),
                    status="traded",
                    source_id="test",
                    published_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
                    ingested_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
                )
            )
        elif d == date(2026, 1, 4):
            bars.append(
                DailyBar(
                    instrument_id="SPARSE_C",
                    symbol="SPARSE C",
                    session_date=d,
                    open=Decimal("22.000"),
                    high=Decimal("22.000"),
                    low=Decimal("22.000"),
                    close=Decimal("22.000"),
                    volume_shares=50,
                    turnover_tnd=Decimal("1100.000"),
                    status="traded",
                    source_id="test",
                    published_at=datetime(2026, 1, 4, 16, 0, tzinfo=UTC),
                    ingested_at=datetime(2026, 1, 4, 16, 0, tzinfo=UTC),
                )
            )
        else:
            bars.append(
                DailyBar(
                    instrument_id="SPARSE_C",
                    symbol="SPARSE C",
                    session_date=d,
                    open=Decimal("22.000"),
                    high=Decimal("22.000"),
                    low=Decimal("22.000"),
                    close=Decimal("22.000"),
                    volume_shares=0,
                    turnover_tnd=Decimal("0.000"),
                    status="untraded",
                    source_id="test",
                    published_at=datetime(d.year, d.month, d.day, 16, 0, tzinfo=UTC),
                    ingested_at=datetime(d.year, d.month, d.day, 16, 0, tzinfo=UTC),
                )
            )

    report = evaluate_market_research_coverage([inst], cal, bars, cutoff)
    an = report.by_instrument["SPARSE_C"]

    assert an.last_verified_price == Decimal("22.000")
    assert an.last_traded_date == date(2026, 1, 4)
    assert an.quote_age_sessions == 6  # days 5,6,7,8,9,10
    assert an.observed_trade_return_pct == Decimal("10.0000")  # (22/20 - 1) * 100 = 10.0%
    assert an.observed_trade_interval_sessions == 3  # days 2, 3, 4
    assert an.classification.data_quality_status == "STALE_QUOTES"
    assert an.classification.execution_feasibility == "ZERO_VOLUME_BLOCKED"


def test_missing_versus_zero_price_representation() -> None:
    """An instrument with zero trades returns None (never 0.000) for last_verified_price."""
    d0 = date(2026, 1, 1)
    cal = _make_calendar([d0])
    inst = _make_instrument("ZERO_TRADES", "ZERO TRADES")
    cutoff = datetime(2026, 1, 1, 17, 0, tzinfo=UTC)

    # Bar exists but was untraded
    bars = [
        DailyBar(
            instrument_id="ZERO_TRADES",
            symbol="ZERO TRADES",
            session_date=d0,
            open=Decimal("15.000"),
            high=Decimal("15.000"),
            low=Decimal("15.000"),
            close=Decimal("15.000"),
            volume_shares=0,
            turnover_tnd=Decimal("0.000"),
            status="untraded",
            source_id="test",
            published_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
        )
    ]

    report = evaluate_market_research_coverage([inst], cal, bars, cutoff)
    an = report.by_instrument["ZERO_TRADES"]

    assert an.last_verified_price is None
    assert an.last_traded_date is None
    assert an.classification.research_coverage_status == "UNTRADED_HISTORY"


def test_restricted_market_segment_classification() -> None:
    """Surveillance or alternatif segments are labeled MARKET_RESTRICTED while retaining valid quotes."""
    d0 = date(2026, 1, 1)
    cal = _make_calendar([d0])
    inst = _make_instrument("SURV_STOCK", "SURV STOCK", segment="surveillance")
    cutoff = datetime(2026, 1, 1, 17, 0, tzinfo=UTC)

    bars = [
        DailyBar(
            instrument_id="SURV_STOCK",
            symbol="SURV STOCK",
            session_date=d0,
            open=Decimal("0.450"),
            high=Decimal("0.450"),
            low=Decimal("0.450"),
            close=Decimal("0.450"),
            volume_shares=1000,
            turnover_tnd=Decimal("450.000"),
            status="traded",
            source_id="test",
            published_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
        )
    ]

    report = evaluate_market_research_coverage([inst], cal, bars, cutoff)
    an = report.by_instrument["SURV_STOCK"]

    assert an.last_verified_price == Decimal("0.450")
    assert an.classification.competition_eligibility == "MARKET_RESTRICTED"
    assert an.classification.data_quality_status == "RESTRICTED_SEGMENT"
    assert an.classification.execution_feasibility == "MARKET_RESTRICTED"


def test_conservative_order_capacity_zero_intraday_lookahead() -> None:
    """Hypothetical order capacity strictly uses trailing median turnover up to cutoff, never next-day volume."""
    d0 = date(2026, 1, 1)
    cal = _make_calendar([d0])
    inst = _make_instrument("CAP_TEST", "CAP TEST")
    cutoff = datetime(2026, 1, 1, 17, 0, tzinfo=UTC)

    # 10,000 TND turnover observed
    bars = [
        DailyBar(
            instrument_id="CAP_TEST",
            symbol="CAP TEST",
            session_date=d0,
            open=Decimal("20.000"),
            high=Decimal("20.000"),
            low=Decimal("20.000"),
            close=Decimal("20.000"),
            volume_shares=500,
            turnover_tnd=Decimal("10000.000"),
            status="traded",
            source_id="test",
            published_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
        )
    ]

    report = evaluate_market_research_coverage(
        [inst],
        cal,
        bars,
        cutoff,
        portfolio_equity=Decimal("50000.000"),
        max_position_weight=Decimal("0.085"),
        liquidity_participation_cap=Decimal("0.10"),
    )
    an = report.by_instrument["CAP_TEST"]

    # 10% of 10,000 TND = 1,000 TND. Concentration cap is 8.5% of 50,000 = 4,250 TND.
    # Capacity is min(1000, 4250) = 1,000 TND.
    assert an.conservative_order_capacity_tnd == Decimal("1000.000")
    # 1,000 TND / 20 TND = 50 shares
    assert an.hypothetical_order_shares == 50


def test_api_rankings_includes_research_fields_and_deduplicates_warnings() -> None:
    """FastAPI /api/rankings returns research coverage fields and clean deduplicated warnings."""
    client = TestClient(app)
    response = client.get("/api/rankings?mode=REAL_COMPETITION")
    assert response.status_code == 200
    data = response.json()

    assert "rankings" in data
    assert "total_instruments" in data
    assert "eligible_count" in data
    assert "excluded_count" in data

    rankings = data["rankings"]
    assert len(rankings) > 0

    for item in rankings:
        # Field completeness
        assert "research_coverage_status" in item
        assert "signal_availability" in item
        assert "data_quality_status" in item
        assert "competition_eligibility" in item
        assert "strategy_eligibility" in item
        assert "execution_feasibility" in item
        assert "hypothetical_order_shares" in item

        # Deduplication check: no warning is also listed as blocked reason
        for w in item["eligibility_warnings"]:
            assert w not in item["blocked_reasons"]


def test_regression_verified_instruments() -> None:
    """Verify BH BANK, ATB, POULINA GP HOLDING, ASTREE, NEW BODY LINE, BH ASSURANCE, and AETECH."""
    bars_path = Path("data/processed/bvmt_official_2026/daily_bars.canonical.csv")
    master_path = Path("data/processed/bvmt_official_2026/instrument_master.csv")
    cal_path = Path("data/processed/bvmt_official_2026/exchange_calendar.csv")

    bars = read_bars_csv(bars_path)
    master = read_instrument_master(master_path)
    calendar = read_exchange_calendar(cal_path)

    cutoff = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    from dataclasses import replace

    cal_prepared = [
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

    def _replay_dt(day: date) -> datetime:
        return datetime.fromisoformat(f"{day.isoformat()}T16:00:00+01:00")

    bars_prepared = [
        replace(
            b,
            published_at=_replay_dt(b.session_date) if b.published_at is None else b.published_at,
            ingested_at=_replay_dt(b.session_date)
            if b.ingested_at is None or b.ingested_at > cutoff
            else b.ingested_at,
        )
        for b in bars
    ]

    base = rank_session_baseline(
        master,
        cal_prepared,
        bars_prepared,
        cutoff,
        short_lookback=20,
        long_lookback=60,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("1000"),
    )

    report = evaluate_market_research_coverage(
        master,
        cal_prepared,
        bars_prepared,
        cutoff,
        baseline_report=base,
    )

    by_id = report.by_instrument

    # 1. BH BANK
    bh = by_id["BH_BANK"]
    assert bh.last_verified_price == Decimal("13.090")
    assert bh.last_traded_date == date(2026, 11, 6)
    assert bh.quote_age_sessions == 0
    assert bh.classification.competition_eligibility == "COMPETITION_PERMITTED"

    # 2. ATB
    atb = by_id["ATB"]
    assert atb.last_verified_price == Decimal("3.400")
    assert atb.last_traded_date == date(2026, 11, 6)
    assert atb.quote_age_sessions == 0

    # 3. POULINA GP HOLDING
    pgh = by_id["POULINA_GP_HOLDING"]
    assert pgh.last_verified_price == Decimal("26.600")
    assert pgh.last_traded_date == date(2026, 11, 6)
    assert pgh.isin == "TN0005700018"

    # 4. ASTREE
    ast = by_id["ASTREE"]
    assert ast.last_verified_price == Decimal("79.000")
    assert ast.last_traded_date == date(2026, 11, 6)
    assert not ast.strategy_eligible  # excluded by 60% liquidity hurdle
    assert "insufficient_liquidity" in ast.exclusion_reasons

    # 5. NEW BODY LINE
    nbl = by_id["NEW_BODY_LINE"]
    assert nbl.last_verified_price == Decimal("2.450")
    assert nbl.strategy_eligible  # passes baseline gates

    # 6. BH ASSURANCE
    bha = by_id["BH_ASSURANCE"]
    assert bha.last_verified_price == Decimal("75.980")
    assert bha.last_traded_date == date(2026, 9, 28)
    assert bha.quote_age_sessions > 20
    assert bha.classification.data_quality_status == "STALE_QUOTES"

    # 7. AETECH
    aet = by_id["AETECH"]
    assert aet.last_verified_price == Decimal("0.420")
    assert aet.classification.competition_eligibility == "MARKET_RESTRICTED"
    assert aet.classification.data_quality_status == "RESTRICTED_SEGMENT"
