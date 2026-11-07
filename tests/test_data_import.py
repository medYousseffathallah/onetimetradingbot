import json
from datetime import UTC, datetime

import pytest

from bvmt.data import (
    _parse_csv_lines,
    audit_official_ndjson_archive,
    export_official_master_and_calendar,
)


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
