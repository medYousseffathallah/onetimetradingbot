import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bvmt.data import (
    _parse_csv_lines,
    audit_official_ndjson_archive,
    export_official_master_and_calendar,
    inspect_market_dataset_provenance,
)

FIXTURE_BARS = Path(__file__).parent / "fixtures" / "daily_bars.csv"


def test_inspect_imported_market_dataset(tmp_path):
    # Small deterministic imported-directory fixture; no private local data dependency.
    bars_path = tmp_path / "daily_bars.canonical.csv"
    bars_path.write_text(
        FIXTURE_BARS.read_text().replace("synthetic-fixture", "official-import"),
        encoding="utf-8",
    )
    (tmp_path / "provenance.json").write_text(
        json.dumps({"source_url": "https://example.test/authorized.csv"})
    )
    (tmp_path / "import_timestamp.json").write_text(
        json.dumps({"retrieved_at": "2026-02-01T12:00:00+00:00"})
    )
    result = inspect_market_dataset_provenance(bars_path)
    assert result == {
        "is_synthetic": False,
        "first_session_date": "2026-01-05",
        "latest_session_date": "2026-01-09",
        "total_bars": 15,
        "unique_sessions": 5,
        "unique_instruments": 3,
        "source_ids": ["official-import"],
        "source_url": "https://example.test/authorized.csv",
        "retrieved_at": "2026-02-01T12:00:00+00:00",
    }


def test_inspect_synthetic_market_dataset():
    result = inspect_market_dataset_provenance(FIXTURE_BARS)
    assert result["is_synthetic"] is True
    assert result["source_ids"] == ["synthetic-fixture"]
    assert result["source_url"] is None
    assert result["retrieved_at"] is None


@pytest.mark.parametrize("location", ["copied.csv", "tests/fixtures/bars.csv"])
def test_inspect_detects_synthetic_sources_or_fixture_directory(tmp_path, location):
    bars_path = tmp_path / location
    bars_path.parent.mkdir(parents=True, exist_ok=True)
    text = FIXTURE_BARS.read_text()
    if location.startswith("tests/"):
        text = text.replace("synthetic-fixture", "official-import")
    else:
        text = text.replace("synthetic-fixture", "Mixed-SYNTHETIC-source", 1)
    bars_path.write_text(text)
    assert inspect_market_dataset_provenance(bars_path)["is_synthetic"] is True


@pytest.mark.parametrize("filename", ["manifest.json", "quality_report.json"])
def test_inspect_metadata_fallback_and_precedence(tmp_path, filename):
    bars_path = tmp_path / "bars.csv"
    bars_path.write_bytes(FIXTURE_BARS.read_bytes())
    metadata = {"source_url": "https://example.test/source", "retrieved_at": "2026-02-01Z"}
    payload = {"provenance": metadata} if filename == "manifest.json" else metadata
    (tmp_path / filename).write_text(json.dumps(payload))
    result = inspect_market_dataset_provenance(bars_path)
    assert result["source_url"] == metadata["source_url"]
    assert result["retrieved_at"] == metadata["retrieved_at"]
    (tmp_path / "provenance.json").write_text(
        json.dumps({"source_url": "https://example.test/primary", "retrieved_at": "primary"})
    )
    result = inspect_market_dataset_provenance(bars_path)
    assert result["source_url"] == "https://example.test/primary"
    assert result["retrieved_at"] == "primary"


def test_inspect_missing_market_dataset_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_market_dataset_provenance(tmp_path / "missing.csv")


def test_inspect_does_not_substitute_import_time_for_retrieval(tmp_path):
    bars_path = tmp_path / "bars.csv"
    bars_path.write_bytes(FIXTURE_BARS.read_bytes())
    (tmp_path / "import_timestamp.json").write_text(
        json.dumps({"imported_at": "2026-02-01T12:00:00+00:00"})
    )
    assert inspect_market_dataset_provenance(bars_path)["retrieved_at"] is None


@pytest.mark.parametrize("payload", ["broken json", "[]"])
def test_inspect_rejects_malformed_metadata(tmp_path, payload):
    bars_path = tmp_path / "bars.csv"
    bars_path.write_bytes(FIXTURE_BARS.read_bytes())
    (tmp_path / "provenance.json").write_text(payload)
    with pytest.raises(ValueError, match="metadata"):
        inspect_market_dataset_provenance(bars_path)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "broken csv",
        FIXTURE_BARS.read_text().splitlines()[0],
        FIXTURE_BARS.read_text().replace("10.000", "invalid", 1),
    ],
)
def test_inspect_empty_or_corrupted_market_dataset_fails(tmp_path, content):
    bars_path = tmp_path / "bars.csv"
    bars_path.write_text(content)
    with pytest.raises(ValueError):
        inspect_market_dataset_provenance(bars_path)


@pytest.mark.parametrize("quantity,accepted", [(667.0, 1), (667.5, 0), (True, 0)])
def test_official_numeric_integer_fields(tmp_path, quantity, accepted):
    row = {
        "dateSeance": "2026-01-02",
        "codeISIN": "TN0001000108",
        "valeur": "MONOPRIX",
        "coursOuvert": 5.97,
        "plusHaut": 5.97,
        "plusBas": 5.97,
        "cloture": 5.97,
        "quantites": quantity,
        "capitaux": 3981.99,
        "echanges": 5.0,
        "groupe": 12.0,
    }
    text = json.dumps({"seance": "2026-01-02", "data": [row]})
    bars, rejected = _parse_csv_lines(
        text,
        input_format="tunis_stockexchange_ndjson",
        source_id="official",
        ingested_at=datetime.now(UTC),
    )
    assert len(bars) == accepted
    assert len(rejected) == 1 - accepted
    if accepted:
        assert bars[0].volume_shares == 667
        path = tmp_path / "numeric.ndjson"
        path.write_text(text)
        master, _ = export_official_master_and_calendar(path, tmp_path / "out")
        assert "principal_fixing" in master.read_text()


def test_archive_audit_counts_raw_envelopes_and_monthly_nulls(tmp_path):
    monthly = {"seance": "2025-12-31", "data": [{"quantites": None}, {"quantites": 0}]}
    daily = {"seance": "2026-01-02", "data": [{"quantites": 10}, {"quantites": 0}]}
    later = {"seance": "2026-01-05", "data": [{"quantites": 20.0}]}
    path = tmp_path / "archive.ndjson"
    path.write_text("\n".join(json.dumps(p) for p in [monthly, daily, daily, later]))
    audit = audit_official_ndjson_archive(path)
    assert audit["total_lines"] == 4
    assert audit["unique_sessions"] == 3
    monthly_year = audit["years"]["2025"]
    assert monthly_year["null_quantity_rows"] == 1
    assert monthly_year["traded_rows"] == 0
    year = audit["years"]["2026"]
    assert year["total_lines"] == 3
    assert year["unique_sessions"] == 2
    assert year["first_session"] == "2026-01-02"
    assert year["last_session"] == "2026-01-05"
    assert year["duplicate_session_envelopes"] == 1
    assert year["duplicate_sessions"] == {"2026-01-02": 2}
    assert year["traded_rows"] == 3  # Raw counts include duplicate envelopes.
    assert year["unique_session_traded_rows"] == 2
    assert year["conflicting_duplicate_sessions"] == []
    assert year["null_quantity_rows"] == 0


def test_archive_audit_reports_conflicting_replays(tmp_path):
    path = tmp_path / "archive.ndjson"
    path.write_text(
        "\n".join(
            json.dumps({"seance": "2026-01-02", "data": rows})
            for rows in [[{"quantites": 1}], [{"quantites": 2}]]
        )
    )
    year = audit_official_ndjson_archive(path)["years"]["2026"]
    assert year["conflicting_duplicate_sessions"] == ["2026-01-02"]


@pytest.mark.parametrize("payload", ["not json", '{"seance":"2026-01-02","data":{}}'])
def test_archive_audit_rejects_malformed_envelopes(tmp_path, payload):
    path = tmp_path / "archive.ndjson"
    path.write_text(payload)
    with pytest.raises(ValueError, match="line 1"):
        audit_official_ndjson_archive(path)


def test_archive_audit_empty_file(tmp_path):
    path = tmp_path / "empty.ndjson"
    path.touch()
    assert audit_official_ndjson_archive(path)["unique_sessions"] == 0
