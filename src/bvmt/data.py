"""Canonical daily-bar parsing, French BVMT adapter, validation, and local CSV ingestion.

No silent source-format guessing: the canonical parser accepts dot-decimal ISO records only,
while the French BVMT adapter explicitly converts French dates and comma decimals.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from bvmt import __version__
from bvmt.snapshots import (
    atomic_write_text,
    ensure_no_symlink_ancestors,
    sha256_file,
    snapshot_local_file,
    validate_permission_status,
    validate_safe_id,
)

CANONICAL_PARSER_VERSION = "canonical_csv_v1"
FRENCH_BVMT_PARSER_VERSION = "french_bvmt_csv_v1"
INSTRUMENT_ID_RE = re.compile(r"[A-Za-z0-9._-]+")
FRENCH_DECIMAL_RE = re.compile(r"[+-]?\d+(?:[.,]\d+)?")
FRENCH_INT_RE = re.compile(r"\d+")
FRENCH_STATUS_MAP: dict[str, str] = {
    "traded": "traded",
    "cotee": "traded",
    "coté": "traded",
    "cotée": "traded",
    "no_trade": "no_trade",
    "non_cotee": "no_trade",
    "non_coté": "no_trade",
    "non_cotée": "no_trade",
    "aucune_transaction": "no_trade",
    "suspended": "suspended",
    "suspendu": "suspended",
    "suspendue": "suspended",
}
CANONICAL_COLUMNS = (
    "instrument_id",
    "symbol",
    "session_date",
    "open",
    "high",
    "low",
    "close",
    "volume_shares",
    "turnover_tnd",
    "status",
    "source_id",
    "published_at",
    "ingested_at",
)
FRENCH_BVMT_REQUIRED_COLUMNS = frozenset(
    {
        "code_isin",
        "valeur",
        "seance",
        "ouverture",
        "plus_haut",
        "plus_bas",
        "cloture",
        "quantite_negociee",
        "capitaux_tnd",
    }
)
FRENCH_BVMT_OPTIONAL_COLUMNS = frozenset({"statut", "date_publication"})


@dataclass(frozen=True)
class DailyBar:
    instrument_id: str
    symbol: str
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_shares: int
    turnover_tnd: Decimal
    status: str
    source_id: str
    published_at: datetime | None
    ingested_at: datetime


@dataclass(frozen=True)
class RejectedRow:
    line_number: int
    raw_row: str
    reason: str


@dataclass(frozen=True)
class ImportSummary:
    source_id: str
    input_format: str
    permission_status: str
    parser_version: str
    retrieved_at: str
    raw_snapshot_path: str
    raw_sha256: str
    canonical_csv_path: str
    canonical_sha256: str
    rejections_path: str
    rejections_sha256: str
    manifest_path: str
    manifest_sha256: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    status_counts: dict[str, int]
    missing_published_at_rows: int


def aware_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and reject an unspecified timezone."""
    stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("A timezone-aware timestamp is required")
    return stamp


def optional_aware_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO timestamp or return None when explicitly blank/unknown."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"null", "unknown"}:
        return None
    return aware_timestamp(cleaned)


def parse_french_session_date(value: str) -> date:
    """Parse ISO YYYY-MM-DD or explicit French DD/MM/YYYY date strings."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Session date is required")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        return date.fromisoformat(cleaned)
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", cleaned)
    if match:
        day_str, month_str, year_str = match.groups()
        return date(int(year_str), int(month_str), int(day_str))
    raise ValueError(f"Unsupported or ambiguous date '{value}'; expected YYYY-MM-DD or DD/MM/YYYY")


def parse_french_decimal(value: str, field_name: str = "decimal") -> Decimal:
    """Parse a French comma-decimal or dot-decimal number without thousands-separator guessing."""
    cleaned = value.strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if not cleaned:
        raise ValueError(f"Missing {field_name}")
    if "," in cleaned and "." in cleaned:
        raise ValueError(
            f"Ambiguous mixed separators in {field_name} '{value}'; do not mix '.' and ','"
        )
    if cleaned.count(",") > 1 or cleaned.count(".") > 1:
        raise ValueError(f"Ambiguous multiple separators in {field_name} '{value}'")
    if not FRENCH_DECIMAL_RE.fullmatch(cleaned):
        raise ValueError(f"Malformed {field_name} '{value}'")
    normalized = cleaned.replace(",", ".")
    return Decimal(normalized)


def parse_french_int(value: str, field_name: str = "integer") -> int:
    """Parse a nonnegative integer share count without allowing fractional shares."""
    cleaned = value.strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if not cleaned:
        raise ValueError(f"Missing {field_name}")
    if cleaned.startswith("-"):
        raise ValueError(f"Volume must be a nonnegative integer share count in {field_name}")
    if not FRENCH_INT_RE.fullmatch(cleaned):
        raise ValueError(f"Invalid integer share count in {field_name}: '{value}'")
    return int(cleaned)


def validate_bar(bar: DailyBar) -> None:
    if not all(s.strip() for s in (bar.instrument_id, bar.symbol, bar.source_id)):
        raise ValueError("Instrument, symbol and source are required")
    if not INSTRUMENT_ID_RE.fullmatch(bar.instrument_id.strip()):
        raise ValueError(f"Invalid instrument_id '{bar.instrument_id}'")
    for value in (bar.open, bar.high, bar.low, bar.close):
        if not value.is_finite() or value <= 0:
            raise ValueError("Quoted OHLC must be finite and positive")
    if not (bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
        raise ValueError("OHLC bounds are inconsistent")
    if type(bar.volume_shares) is not int or bar.volume_shares < 0:
        raise ValueError("Volume must be a nonnegative integer share count")
    if not bar.turnover_tnd.is_finite() or bar.turnover_tnd < 0:
        raise ValueError("Turnover must be finite and nonnegative")
    if bar.status not in {"traded", "no_trade", "suspended"}:
        raise ValueError("Unknown trading status")
    if bar.status == "traded" and (bar.volume_shares == 0 or bar.turnover_tnd == 0):
        raise ValueError("A traded bar requires positive shares and turnover")
    if bar.status != "traded" and (bar.volume_shares != 0 or bar.turnover_tnd != 0):
        raise ValueError("A non-traded bar cannot have traded shares or turnover")
    if bar.ingested_at.tzinfo is None or bar.ingested_at.utcoffset() is None:
        raise ValueError("Publication and ingestion timestamps must be aware")
    if bar.published_at is not None:
        if bar.published_at.tzinfo is None or bar.published_at.utcoffset() is None:
            raise ValueError("Publication and ingestion timestamps must be aware")
        if bar.ingested_at < bar.published_at:
            raise ValueError("Ingestion cannot precede publication")


def validate_bars(bars: Iterable[DailyBar]) -> list[DailyBar]:
    result = list(bars)
    if not result:
        raise ValueError("Dataset is empty")
    seen: set[tuple[str, date]] = set()
    for bar in result:
        validate_bar(bar)
        key = (bar.instrument_id, bar.session_date)
        if key in seen:
            raise ValueError(f"Duplicate instrument/session: {key}")
        seen.add(key)
    return result


def _parse_canonical_row(
    row: dict[str | None, str | None],
    *,
    default_source_id: str | None = None,
    default_ingested_at: datetime | None = None,
) -> DailyBar:
    if None in row or any(value is None for value in row.values()):
        raise ValueError("Column count mismatch")
    for field_name in ("open", "high", "low", "close", "turnover_tnd"):
        raw_val = (row[field_name] or "").strip()
        if "," in raw_val:
            raise ValueError(
                f"Comma decimal not allowed in canonical column '{field_name}'; use french_bvmt adapter"
            )
    raw_source = (row["source_id"] or "").strip()
    if default_source_id is not None and raw_source and raw_source != default_source_id:
        raise ValueError(
            f"Row source_id '{raw_source}' does not match declared source_id '{default_source_id}'"
        )
    source_id = raw_source or (default_source_id or "")
    raw_ingested = (row["ingested_at"] or "").strip()
    ingested_at = (
        aware_timestamp(raw_ingested)
        if raw_ingested
        else (
            default_ingested_at
            if default_ingested_at is not None
            else aware_timestamp(raw_ingested)
        )
    )
    bar = DailyBar(
        instrument_id=(row["instrument_id"] or "").strip(),
        symbol=(row["symbol"] or "").strip(),
        session_date=date.fromisoformat((row["session_date"] or "").strip()),
        open=Decimal((row["open"] or "").strip()),
        high=Decimal((row["high"] or "").strip()),
        low=Decimal((row["low"] or "").strip()),
        close=Decimal((row["close"] or "").strip()),
        volume_shares=int((row["volume_shares"] or "").strip()),
        turnover_tnd=Decimal((row["turnover_tnd"] or "").strip()),
        status=(row["status"] or "").strip(),
        source_id=source_id,
        published_at=optional_aware_timestamp(row["published_at"]),
        ingested_at=ingested_at,
    )
    validate_bar(bar)
    return bar


def read_bars_csv(path: Path) -> list[DailyBar]:
    """Read canonical dot-decimal CSV; reject the whole batch on invalid records."""
    required = set(CANONICAL_COLUMNS)
    bars: list[DailyBar] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or set(header) != required:
            raise ValueError(f"Expected unique canonical columns: {sorted(required)}")
        for line_number, row in enumerate(reader, start=2):
            try:
                bars.append(_parse_canonical_row(row))
            except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
                raise ValueError(f"Invalid canonical CSV row {line_number}: {exc}") from exc
    return validate_bars(bars)


def _parse_french_bvmt_row(
    row: dict[str | None, str | None],
    *,
    source_id: str,
    ingested_at: datetime,
) -> DailyBar:
    if None in row or any(value is None for value in row.values()):
        raise ValueError("Column count mismatch")
    volume_shares = parse_french_int(row["quantite_negociee"] or "", "quantite_negociee")
    turnover_tnd = parse_french_decimal(row["capitaux_tnd"] or "", "capitaux_tnd")
    raw_status = (row.get("statut") or "").strip().lower()
    if raw_status:
        if raw_status not in FRENCH_STATUS_MAP:
            raise ValueError(f"Unknown trading status '{row.get('statut')}'")
        status = FRENCH_STATUS_MAP[raw_status]
    else:
        status = "no_trade" if (volume_shares == 0 and turnover_tnd == 0) else "traded"
    published_at = optional_aware_timestamp(row.get("date_publication"))
    bar = DailyBar(
        instrument_id=(row["code_isin"] or "").strip(),
        symbol=(row["valeur"] or "").strip(),
        session_date=parse_french_session_date(row["seance"] or ""),
        open=parse_french_decimal(row["ouverture"] or "", "ouverture"),
        high=parse_french_decimal(row["plus_haut"] or "", "plus_haut"),
        low=parse_french_decimal(row["plus_bas"] or "", "plus_bas"),
        close=parse_french_decimal(row["cloture"] or "", "cloture"),
        volume_shares=volume_shares,
        turnover_tnd=turnover_tnd,
        status=status,
        source_id=source_id,
        published_at=published_at,
        ingested_at=ingested_at,
    )
    validate_bar(bar)
    return bar


def parse_french_bvmt_csv(
    path: Path,
    *,
    source_id: str,
    ingested_at: datetime,
) -> tuple[list[DailyBar], list[RejectedRow]]:
    """Parse an explicit French BVMT CSV file, returning valid bars and quarantined rows."""
    validate_safe_id(source_id, "source identifier")
    if ingested_at.tzinfo is None or ingested_at.utcoffset() is None:
        raise ValueError("Ingestion timestamp must be timezone-aware")
    text = path.read_text(encoding="utf-8-sig")
    return _parse_csv_lines(
        text,
        input_format="french_bvmt",
        source_id=source_id,
        ingested_at=ingested_at,
    )


def _parse_csv_lines(
    text: str,
    *,
    input_format: Literal["canonical", "french_bvmt"],
    source_id: str,
    ingested_at: datetime,
) -> tuple[list[DailyBar], list[RejectedRow]]:
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ValueError("CSV file is empty")
    header_line = lines[0]
    delimiter = ";" if (input_format == "french_bvmt" and ";" in header_line) else ","
    header_reader = csv.reader([header_line], delimiter=delimiter)
    raw_header = next(header_reader, [])
    header = [col.strip() for col in raw_header]
    if len(header) != len(set(header)) or any(not col for col in header):
        raise ValueError(f"CSV header contains duplicate or empty column names: {header}")
    if input_format == "canonical":
        if set(header) != set(CANONICAL_COLUMNS):
            raise ValueError(f"Expected unique canonical columns: {sorted(CANONICAL_COLUMNS)}")
    elif input_format == "french_bvmt":
        header_set = set(header)
        if not FRENCH_BVMT_REQUIRED_COLUMNS.issubset(header_set):
            missing = sorted(FRENCH_BVMT_REQUIRED_COLUMNS - header_set)
            raise ValueError(f"Missing required french_bvmt columns: {missing}")
        unknown = sorted(header_set - FRENCH_BVMT_REQUIRED_COLUMNS - FRENCH_BVMT_OPTIONAL_COLUMNS)
        if unknown:
            raise ValueError(
                f"Unsupported or ambiguous columns in french_bvmt CSV: {unknown}. "
                "Use explicit 'quantite_negociee' (shares) and 'capitaux_tnd' (TND)."
            )
    else:
        raise ValueError(f"Unsupported input_format '{input_format}'")

    accepted: list[DailyBar] = []
    rejected: list[RejectedRow] = []
    seen_keys: dict[tuple[str, date], int] = {}

    for line_number, raw_line in enumerate(lines[1:], start=2):
        if not raw_line.strip():
            rejected.append(RejectedRow(line_number, raw_line, "Empty row"))
            continue
        row_list = next(csv.reader([raw_line], delimiter=delimiter), [])
        if len(row_list) != len(header):
            rejected.append(
                RejectedRow(
                    line_number,
                    raw_line,
                    f"Column count mismatch: expected {len(header)}, got {len(row_list)}",
                )
            )
            continue
        row_dict: dict[str | None, str | None] = dict(zip(header, row_list, strict=True))
        try:
            if input_format == "canonical":
                bar = _parse_canonical_row(
                    row_dict, default_source_id=source_id, default_ingested_at=ingested_at
                )
            else:
                bar = _parse_french_bvmt_row(row_dict, source_id=source_id, ingested_at=ingested_at)
            key = (bar.instrument_id, bar.session_date)
            if key in seen_keys:
                first_line = seen_keys[key]
                raise ValueError(
                    f"Duplicate instrument/session ({bar.instrument_id}, {bar.session_date.isoformat()}) "
                    f"already seen on line {first_line}"
                )
            seen_keys[key] = line_number
            accepted.append(bar)
        except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
            rejected.append(RejectedRow(line_number, raw_line, str(exc)))

    accepted.sort(key=lambda b: (b.instrument_id, b.session_date))
    return accepted, rejected


def format_canonical_csv(bars: Iterable[DailyBar]) -> str:
    """Serialize DailyBar records into deterministic canonical CSV text."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CANONICAL_COLUMNS)
    for bar in sorted(bars, key=lambda b: (b.instrument_id, b.session_date)):
        writer.writerow(
            [
                bar.instrument_id,
                bar.symbol,
                bar.session_date.isoformat(),
                str(bar.open),
                str(bar.high),
                str(bar.low),
                str(bar.close),
                str(bar.volume_shares),
                str(bar.turnover_tnd),
                bar.status,
                bar.source_id,
                bar.published_at.isoformat() if bar.published_at is not None else "",
                bar.ingested_at.isoformat(),
            ]
        )
    return buffer.getvalue()


def import_local_csv(
    source_path: Path,
    *,
    source_id: str,
    input_format: Literal["canonical", "french_bvmt"],
    permission_status: str,
    retrieved_at: datetime,
    raw_dir: Path,
    output_dir: Path,
) -> ImportSummary:
    """Ingest a local CSV file, snapshot raw bytes, validate rows, and write deterministic artifacts."""
    validate_safe_id(source_id, "source identifier")
    validate_permission_status(permission_status)
    if input_format not in {"canonical", "french_bvmt"}:
        raise ValueError(f"Unsupported input_format '{input_format}'")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("Retrieval time must be timezone-aware")
    ensure_no_symlink_ancestors(source_path)
    ensure_no_symlink_ancestors(raw_dir)
    ensure_no_symlink_ancestors(output_dir)

    parser_version = (
        CANONICAL_PARSER_VERSION if input_format == "canonical" else FRENCH_BVMT_PARSER_VERSION
    )
    snapshot_path = snapshot_local_file(
        source_path,
        raw_dir,
        source_id=source_id,
        retrieved_at=retrieved_at,
        permission_status=permission_status,
        parser_version=parser_version,
    )
    raw_sha256 = sha256_file(snapshot_path)
    raw_text = snapshot_path.read_bytes().decode("utf-8-sig")

    accepted, rejected = _parse_csv_lines(
        raw_text,
        input_format=input_format,
        source_id=source_id,
        ingested_at=retrieved_at,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_csv_path = output_dir / "daily_bars.canonical.csv"
    rejections_path = output_dir / "rejections.json"
    manifest_path = output_dir / "manifest.json"

    canonical_text = format_canonical_csv(accepted)
    atomic_write_text(canonical_csv_path, canonical_text, allow_identical=True)
    canonical_sha256 = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    rejections_payload = {
        "input_format": input_format,
        "parser_version": parser_version,
        "raw_sha256": raw_sha256,
        "rejected_count": len(rejected),
        "rejections": [
            {
                "line_number": item.line_number,
                "raw_row": item.raw_row,
                "reason": item.reason,
            }
            for item in rejected
        ],
        "source_id": source_id,
    }
    rejections_text = (
        json.dumps(rejections_payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    atomic_write_text(rejections_path, rejections_text, allow_identical=True)
    rejections_sha256 = hashlib.sha256(rejections_text.encode("utf-8")).hexdigest()

    status_counts = dict(sorted(Counter(bar.status for bar in accepted).items()))
    missing_published = sum(1 for bar in accepted if bar.published_at is None)
    instruments = sorted({bar.instrument_id for bar in accepted})
    min_session = min((bar.session_date.isoformat() for bar in accepted), default=None)
    max_session = max((bar.session_date.isoformat() for bar in accepted), default=None)

    manifest_payload = {
        "application_version": __version__,
        "artifacts": {
            "canonical_csv": {
                "filename": canonical_csv_path.name,
                "rows": len(accepted),
                "sha256": canonical_sha256,
            },
            "raw_snapshot": {
                "filename": snapshot_path.name,
                "sha256": raw_sha256,
            },
            "rejections_json": {
                "filename": rejections_path.name,
                "rejected_rows": len(rejected),
                "sha256": rejections_sha256,
            },
        },
        "data_quality_summary": {
            "accepted_rows": len(accepted),
            "distinct_instruments": len(instruments),
            "instruments": instruments,
            "max_session_date": max_session,
            "min_session_date": min_session,
            "missing_published_at_rows": missing_published,
            "rejected_rows": len(rejected),
            "status_counts": status_counts,
            "total_rows": len(accepted) + len(rejected),
        },
        "provenance": {
            "input_format": input_format,
            "parser_version": parser_version,
            "permission_status": permission_status,
            "retrieved_at": retrieved_at.isoformat(),
            "source_filename": source_path.name,
            "source_id": source_id,
        },
        "schema_version": 1,
    }
    manifest_text = json.dumps(manifest_payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    atomic_write_text(manifest_path, manifest_text, allow_identical=True)
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    return ImportSummary(
        source_id=source_id,
        input_format=input_format,
        permission_status=permission_status,
        parser_version=parser_version,
        retrieved_at=retrieved_at.isoformat(),
        raw_snapshot_path=snapshot_path.as_posix(),
        raw_sha256=raw_sha256,
        canonical_csv_path=canonical_csv_path.as_posix(),
        canonical_sha256=canonical_sha256,
        rejections_path=rejections_path.as_posix(),
        rejections_sha256=rejections_sha256,
        manifest_path=manifest_path.as_posix(),
        manifest_sha256=manifest_sha256,
        total_rows=len(accepted) + len(rejected),
        accepted_rows=len(accepted),
        rejected_rows=len(rejected),
        status_counts=status_counts,
        missing_published_at_rows=missing_published,
    )
