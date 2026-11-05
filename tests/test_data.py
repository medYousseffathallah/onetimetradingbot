import json
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.data import (
    aware_timestamp,
    import_local_csv,
    parse_french_bvmt_csv,
    parse_french_decimal,
    parse_french_session_date,
    read_bars_csv,
    validate_bar,
    validate_bars,
)

ROOT = Path(__file__).resolve().parents[1]
STAMP = aware_timestamp("2026-01-15T18:00:00+00:00")


@pytest.mark.parametrize(
    "field,value",
    [
        ("open", Decimal("NaN")),
        ("close", Decimal("Infinity")),
        ("low", Decimal("0")),
        ("high", Decimal("1")),
        ("volume_shares", -1),
        ("volume_shares", True),
        ("turnover_tnd", Decimal("-1")),
        ("turnover_tnd", Decimal("NaN")),
        ("symbol", ""),
        ("status", "unknown"),
        ("volume_shares", 0),
    ],
)
def test_invalid_bar_rejected(bars, field, value):
    with pytest.raises(ValueError):
        validate_bar(replace(bars[0], **{field: value}))


def test_duplicate_rejected(bars):
    with pytest.raises(ValueError, match="Duplicate"):
        validate_bars([bars[0], bars[0]])


def test_naive_time_rejected():
    with pytest.raises(ValueError, match="timezone"):
        aware_timestamp("2026-01-09T17:00:00")


def test_ingestion_cannot_precede_publication(bars):
    with pytest.raises(ValueError, match="precede"):
        validate_bar(replace(bars[0], ingested_at=aware_timestamp("2026-01-05T15:00:00Z")))


def test_no_trade_reference_prices_are_valid(bars):
    validate_bar(bars[-1])
    with pytest.raises(ValueError, match="non-traded"):
        validate_bar(replace(bars[-1], volume_shares=10))


def test_empty_dataset_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_bars([])


def test_malformed_csv_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("date,close\n2026-01-01,10\n")
    with pytest.raises(ValueError, match="canonical columns"):
        read_bars_csv(path)


def test_naive_bar_rejected(bars):
    with pytest.raises(ValueError, match="aware"):
        validate_bar(replace(bars[0], published_at=datetime(2026, 1, 5, 16)))


def test_canonical_parser_rejects_french_comma_decimals(tmp_path):
    csv_text = (
        "instrument_id,symbol,session_date,open,high,low,close,volume_shares,"
        "turnover_tnd,status,source_id,published_at,ingested_at\n"
        "DEMO_A,DEMO_A,2026-01-05,10,000,10.300,9.700,10.000,1000,10000.000,"
        "traded,synthetic-fixture,2026-01-05T16:00:00+00:00,2026-01-05T16:05:00+00:00\n"
    )
    path = tmp_path / "comma.csv"
    path.write_text(csv_text, encoding="utf-8")
    with pytest.raises(ValueError):
        read_bars_csv(path)


def test_french_decimal_and_date_parsing():
    assert parse_french_decimal("10,800") == Decimal("10.800")
    assert parse_french_decimal("10 200,50") == Decimal("10200.50")
    assert parse_french_session_date("05/01/2026") == date(2026, 1, 5)
    assert parse_french_session_date("2026-01-05") == date(2026, 1, 5)
    for bad_num in ("1.000,50", "1,000.50", "10,20,30", "", "abc"):
        with pytest.raises(ValueError):
            parse_french_decimal(bad_num)
    for bad_date in ("2026/01/05", "05-01-2026", "32/01/2026", ""):
        with pytest.raises(ValueError):
            parse_french_session_date(bad_date)


def test_french_adapter_rejects_ambiguous_volume_column(tmp_path):
    path = tmp_path / "ambiguous.csv"
    path.write_text(
        "code_isin;valeur;seance;ouverture;plus_haut;plus_bas;cloture;volume\n"
        "TN0001000010;DEMO_A;05/01/2026;10,0;10,5;9,5;10,0;1000\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Missing required french_bvmt columns"):
        parse_french_bvmt_csv(path, source_id="bvmt_hist", ingested_at=STAMP)


def test_french_bvmt_sample_import_and_quarantine(tmp_path):
    fixture = ROOT / "tests/fixtures/french_bvmt_sample.csv"
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    summary = import_local_csv(
        fixture,
        source_id="bvmt_hist_sample",
        input_format="french_bvmt",
        permission_status="authorized_local_import",
        retrieved_at=STAMP,
        raw_dir=raw_dir,
        output_dir=out_dir,
    )
    assert summary.total_rows == 11
    assert summary.accepted_rows == 4
    assert summary.rejected_rows == 7
    assert summary.missing_published_at_rows == 2
    assert summary.status_counts == {"no_trade": 1, "suspended": 1, "traded": 2}

    imported_bars = read_bars_csv(out_dir / "daily_bars.canonical.csv")
    assert len(imported_bars) == 4
    assert imported_bars[1].published_at is None

    rejections = json.loads((out_dir / "rejections.json").read_text(encoding="utf-8"))
    assert rejections["rejected_count"] == 7
    reasons = {item["line_number"]: item["reason"] for item in rejections["rejections"]}
    assert "Duplicate instrument/session" in reasons[6]
    assert "OHLC bounds are inconsistent" in reasons[7]
    assert "Ambiguous mixed separators" in reasons[8]
    assert "Unsupported or ambiguous date" in reasons[9]
    assert "nonnegative integer share count" in reasons[10]
    assert "Ingestion cannot precede publication" in reasons[11]
    assert "Column count mismatch" in reasons[12]


def test_deterministic_repeated_imports(tmp_path):
    fixture = ROOT / "tests/fixtures/daily_bars.csv"
    raw_dir = tmp_path / "raw"
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    s1 = import_local_csv(
        fixture,
        source_id="synthetic-fixture",
        input_format="canonical",
        permission_status="synthetic_fixture",
        retrieved_at=STAMP,
        raw_dir=raw_dir,
        output_dir=out1,
    )
    s2 = import_local_csv(
        fixture,
        source_id="synthetic-fixture",
        input_format="canonical",
        permission_status="synthetic_fixture",
        retrieved_at=STAMP,
        raw_dir=raw_dir,
        output_dir=out2,
    )
    assert s1.canonical_sha256 == s2.canonical_sha256
    assert s1.rejections_sha256 == s2.rejections_sha256
    assert s1.manifest_sha256 == s2.manifest_sha256
    assert (out1 / "daily_bars.canonical.csv").read_bytes() == (
        out2 / "daily_bars.canonical.csv"
    ).read_bytes()
    assert (out1 / "manifest.json").read_bytes() == (out2 / "manifest.json").read_bytes()
    # Re-running into the exact same output directory is idempotent when content matches
    s1_repeat = import_local_csv(
        fixture,
        source_id="synthetic-fixture",
        input_format="canonical",
        permission_status="synthetic_fixture",
        retrieved_at=STAMP,
        raw_dir=raw_dir,
        output_dir=out1,
    )
    assert s1_repeat == s1


def test_overwrite_safeguard_refuses_differing_existing_output(tmp_path):
    fixture = ROOT / "tests/fixtures/daily_bars.csv"
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    (out_dir / "manifest.json").write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        import_local_csv(
            fixture,
            source_id="synthetic-fixture",
            input_format="canonical",
            permission_status="synthetic_fixture",
            retrieved_at=STAMP,
            raw_dir=raw_dir,
            output_dir=out_dir,
        )


def test_unsafe_source_id_and_permission_rejected(tmp_path):
    fixture = ROOT / "tests/fixtures/daily_bars.csv"
    with pytest.raises(ValueError, match="Unsafe"):
        import_local_csv(
            fixture,
            source_id="../bad",
            input_format="canonical",
            permission_status="synthetic_fixture",
            retrieved_at=STAMP,
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
        )
    with pytest.raises(ValueError, match="Unsupported permission_status"):
        import_local_csv(
            fixture,
            source_id="synthetic-fixture",
            input_format="canonical",
            permission_status="unverified_scraping",
            retrieved_at=STAMP,
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
        )
