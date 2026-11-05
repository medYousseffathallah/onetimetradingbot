import json

import pytest

from bvmt.data import aware_timestamp
from bvmt.snapshots import sha256_file, snapshot_local_file

STAMP = aware_timestamp("2026-01-01T12:00:00Z")


def test_idempotent_raw_snapshot_preserves_bytes(tmp_path):
    source = tmp_path / "source.csv"
    source.write_bytes(b"original,bytes\n1,2\n")
    target = snapshot_local_file(source, tmp_path / "raw", source_id="test", retrieved_at=STAMP)
    again = snapshot_local_file(source, tmp_path / "raw", source_id="test", retrieved_at=STAMP)
    assert again == target and target.read_bytes() == source.read_bytes()
    assert target.stem == sha256_file(source)
    assert len(list(target.parent.glob("*.bin"))) == 1


def test_corrupt_existing_snapshot_is_not_overwritten(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"original")
    target = snapshot_local_file(source, tmp_path / "raw", source_id="test", retrieved_at=STAMP)
    target.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="integrity"):
        snapshot_local_file(source, tmp_path / "raw", source_id="test", retrieved_at=STAMP)
    assert target.read_bytes() == b"corrupted"


def test_unsafe_source_id_rejected(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsafe"):
        snapshot_local_file(source, tmp_path / "raw", source_id="../escape", retrieved_at=STAMP)


def test_first_retrieval_time_is_preserved(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"x")
    target = snapshot_local_file(source, tmp_path / "raw", source_id="test", retrieved_at=STAMP)
    snapshot_local_file(
        source,
        tmp_path / "raw",
        source_id="test",
        retrieved_at=aware_timestamp("2026-02-01T12:00:00Z"),
    )
    assert json.loads(target.with_suffix(".json").read_text())["retrieved_at"] == STAMP.isoformat()
