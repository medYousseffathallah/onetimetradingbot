import json
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.calendar import (
    InstrumentRecord,
    SuspensionRecord,
    evaluate_coverage,
    read_exchange_calendar,
    read_instrument_master,
    resolve_instrument_on_date,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.cli import main
from bvmt.data import DailyBar, aware_timestamp

ROOT = Path(__file__).resolve().parents[1]


def test_read_instrument_master_and_historical_symbol_changes(tmp_path):
    records = read_instrument_master(ROOT / "tests/fixtures/instrument_master.csv")
    assert len(records) == 5
    old = resolve_instrument_on_date(records, "DEMO_A", date(2026, 1, 2))
    current = resolve_instrument_on_date(records, "DEMO_A", date(2026, 1, 5))
    assert old is not None and old.symbol == "DEMO_A_OLD"
    assert current is not None and current.symbol == "DEMO_A"

    # Also test JSON loading round-trip
    json_path = tmp_path / "instruments.json"
    json_path.write_text(json.dumps([asdict(r) for r in records], default=str), encoding="utf-8")
    assert read_instrument_master(json_path) == records


def test_overlapping_symbol_and_validity_histories_rejected():
    base = InstrumentRecord(
        instrument_id="DEMO_A",
        isin="TN0001000010",
        symbol="DEMO_A",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 1, 10),
        listed_from=date(2026, 1, 1),
        listed_to=None,
        market_segment="Continu_Principal",
        currency="TND",
        source_document_id="doc_1",
    )
    overlap_same_inst = replace(base, valid_from=date(2026, 1, 10), valid_to=None)
    with pytest.raises(ValueError, match="Overlapping validity ranges"):
        validate_instrument_master([base, overlap_same_inst])

    overlap_same_symbol = replace(
        base,
        instrument_id="DEMO_B",
        isin="TN0001000028",
        valid_from=date(2026, 1, 5),
    )
    with pytest.raises(ValueError, match="Overlapping symbol assignment"):
        validate_instrument_master([base, overlap_same_symbol])


def test_invalid_listing_date_ranges_rejected():
    base = InstrumentRecord(
        instrument_id="DEMO_A",
        isin="TN0001000010",
        symbol="DEMO_A",
        valid_from=date(2026, 1, 5),
        valid_to=date(2026, 1, 10),
        listed_from=date(2026, 1, 6),
        listed_to=date(2026, 1, 9),
        market_segment="Continu_Principal",
        currency="TND",
        source_document_id="doc_1",
    )
    with pytest.raises(ValueError, match="precedes listed_from"):
        validate_instrument_master([base])

    bad_end = replace(base, valid_from=date(2026, 1, 6), valid_to=date(2026, 1, 12))
    with pytest.raises(ValueError, match="extends beyond listed_to"):
        validate_instrument_master([bad_end])


def test_exchange_calendar_requires_africa_tunis_and_official_evidence(tmp_path):
    sessions = read_exchange_calendar(ROOT / "tests/fixtures/exchange_calendar.csv")
    assert len(sessions) == 6
    assert sessions[-1].is_open is False

    # JSON round-trip
    json_path = tmp_path / "calendar.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "session_date": s.session_date.isoformat(),
                    "is_open": s.is_open,
                    "schedule_type": s.schedule_type,
                    "opens_at": s.opens_at.isoformat() if s.opens_at else None,
                    "closes_at": s.closes_at.isoformat() if s.closes_at else None,
                    "timezone": s.timezone,
                    "source_document_id": s.source_document_id,
                }
                for s in sessions
            ]
        ),
        encoding="utf-8",
    )
    assert read_exchange_calendar(json_path) == sessions

    # Reject wrong timezone, missing open hours, or unsafe source_document_id
    with pytest.raises(ValueError, match="Africa/Tunis"):
        validate_exchange_calendar([replace(sessions[0], timezone="UTC")])
    with pytest.raises(ValueError, match="requires explicit opens_at"):
        validate_exchange_calendar([replace(sessions[0], opens_at=None)])
    with pytest.raises(ValueError, match="Unsafe"):
        validate_exchange_calendar([replace(sessions[0], source_document_id="../unverified")])
    with pytest.raises(ValueError, match="must not have opens_at"):
        validate_exchange_calendar([replace(sessions[-1], opens_at=sessions[0].opens_at)])


def test_coverage_classification_and_diagnostics(bars):
    instruments = read_instrument_master(ROOT / "tests/fixtures/instrument_master.csv")
    calendar = read_exchange_calendar(ROOT / "tests/fixtures/exchange_calendar.csv")

    report = evaluate_coverage(instruments, calendar, bars, stale_after_open_sessions=3)
    assert report.classification_counts["traded"] == 10
    assert report.classification_counts["no_trade"] == 2
    assert report.classification_counts["stale_quote"] == 3
    assert report.classification_counts["holiday"] == 3
    assert report.classification_counts["missing_observation"] == 2
    assert report.classification_counts["unlisted_or_delisted"] == 4
    assert len(report.unexplained_stale_quotes) == 3
    assert len(report.missing_instrument_observations) == 2


def test_suspension_requires_explicit_supporting_evidence(bars):
    instruments = read_instrument_master(ROOT / "tests/fixtures/instrument_master.csv")
    calendar = read_exchange_calendar(ROOT / "tests/fixtures/exchange_calendar.csv")
    suspended_bar = DailyBar(
        instrument_id="DEMO_DELIST",
        symbol="DEMO_DELIST",
        session_date=date(2026, 1, 5),
        open=Decimal("5.000"),
        high=Decimal("5.000"),
        low=Decimal("5.000"),
        close=Decimal("5.000"),
        volume_shares=0,
        turnover_tnd=Decimal("0.000"),
        status="suspended",
        source_id="synthetic-fixture",
        published_at=aware_timestamp("2026-01-05T16:00:00+00:00"),
        ingested_at=aware_timestamp("2026-01-05T16:05:00+00:00"),
    )
    # Without SuspensionRecord -> flagged in unverified_suspensions
    rep_unverified = evaluate_coverage(instruments, calendar, list(bars) + [suspended_bar])
    assert len(rep_unverified.unverified_suspensions) == 1

    # With SuspensionRecord -> verified, no unverified_suspensions
    evidence = SuspensionRecord(
        instrument_id="DEMO_DELIST",
        session_date=date(2026, 1, 5),
        source_document_id="cmf_notice_01",
    )
    rep_verified = evaluate_coverage(
        instruments, calendar, list(bars) + [suspended_bar], suspensions=[evidence]
    )
    assert rep_verified.unverified_suspensions == []
    assert rep_verified.classification_counts["suspended"] == 1


def test_deterministic_coverage_and_cli_command(tmp_path, capsys):
    instruments = read_instrument_master(ROOT / "tests/fixtures/instrument_master.csv")
    calendar = read_exchange_calendar(ROOT / "tests/fixtures/exchange_calendar.csv")
    bars = [
        DailyBar(
            instrument_id="DEMO_A",
            symbol="DEMO_A",
            session_date=date(2026, 1, 5),
            open=Decimal("10.0"),
            high=Decimal("10.5"),
            low=Decimal("9.5"),
            close=Decimal("10.0"),
            volume_shares=100,
            turnover_tnd=Decimal("1000.0"),
            status="traded",
            source_id="synthetic-fixture",
            published_at=aware_timestamp("2026-01-05T16:00:00+00:00"),
            ingested_at=aware_timestamp("2026-01-05T16:05:00+00:00"),
        )
    ]
    r1 = evaluate_coverage(instruments, calendar, bars)
    r2 = evaluate_coverage(list(reversed(instruments)), list(reversed(calendar)), bars)
    assert r1 == r2

    out = tmp_path / "coverage.json"
    assert main(["coverage-check", "--output", str(out)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["classification_counts"]["traded"] == 10
    assert out.is_file()
