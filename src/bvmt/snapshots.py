"""Content-addressed local snapshots with integrity checks and idempotent metadata."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

SAFE_ID_RE = re.compile(r"[A-Za-z0-9_-]+")
ALLOWED_PERMISSION_STATUSES = frozenset(
    {
        "authorized_local_import",
        "synthetic_fixture",
        "public_read_only_reference",
        "must_be_recorded_by_import_workflow",
    }
)


def validate_safe_id(value: str, label: str = "source identifier") -> str:
    cleaned = value.strip()
    if not SAFE_ID_RE.fullmatch(cleaned):
        raise ValueError(f"Unsafe or empty {label}")
    return cleaned


def validate_permission_status(permission_status: str) -> str:
    cleaned = permission_status.strip()
    if cleaned not in ALLOWED_PERMISSION_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_PERMISSION_STATUSES))
        raise ValueError(
            f"Unsupported permission_status '{permission_status}'; expected one of: {allowed}"
        )
    return cleaned


def ensure_no_symlink_ancestors(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"Path must not be a symlink: {path}")
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError(f"Ancestor directory must not be a symlink: {parent}")


def atomic_write_bytes(target: Path, payload: bytes, *, allow_identical: bool = True) -> None:
    ensure_no_symlink_ancestors(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not target.is_file():
            raise ValueError(f"Target path is not a regular file: {target}")
        if allow_identical and target.read_bytes() == payload:
            return
        raise ValueError(f"Refusing to overwrite existing file with different content: {target}")
    temp_path = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        with temp_path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            if allow_identical and target.read_bytes() == payload:
                temp_path.unlink(missing_ok=True)
                return
            raise ValueError(
                f"Refusing to overwrite existing file with different content: {target}"
            )
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def atomic_write_text(target: Path, text: str, *, allow_identical: bool = True) -> None:
    atomic_write_bytes(target, text.encode("utf-8"), allow_identical=allow_identical)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_local_file(
    source: Path,
    destination: Path,
    *,
    source_id: str,
    retrieved_at: datetime,
    permission_status: str = "must_be_recorded_by_import_workflow",
    parser_version: str | None = None,
) -> Path:
    """Snapshot an authorized local file. No network or permission inference.

    Single-process foundation only: concurrent ingestion needs the planned writer lock.
    Existing metadata retains its first retrieval timestamp rather than being overwritten.
    """
    validate_safe_id(source_id, "source identifier")
    validate_permission_status(permission_status)
    if parser_version is not None and not parser_version.strip():
        raise ValueError("Parser version must not be empty when provided")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("Retrieval time must be timezone-aware")
    if source.is_symlink() or not source.is_file():
        raise ValueError("Source must be an existing regular local file (not a symlink)")
    ensure_no_symlink_ancestors(destination)
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    folder = destination / source_id
    ensure_no_symlink_ancestors(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{digest}.bin"
    if target.is_symlink():
        raise ValueError("Snapshot target must not be a symlink")
    if target.exists():
        if sha256_file(target) != digest:
            raise ValueError("Existing raw snapshot failed its integrity check")
    else:
        atomic_write_bytes(target, payload, allow_identical=True)
    metadata = folder / f"{digest}.json"
    if metadata.is_symlink():
        raise ValueError("Snapshot metadata must not be a symlink")
    if metadata.exists():
        recorded = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(recorded, dict) or recorded.get("sha256") != digest:
            raise ValueError("Existing metadata failed its integrity check")
    else:
        meta_payload: dict[str, object] = {
            "bytes": len(payload),
            "permission_status": permission_status,
            "retrieved_at": retrieved_at.isoformat(),
            "sha256": digest,
            "source_filename": source.name,
            "source_id": source_id,
        }
        if parser_version is not None:
            meta_payload["parser_version"] = parser_version.strip()
        text = json.dumps(meta_payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        atomic_write_text(metadata, text, allow_identical=True)
    return target
