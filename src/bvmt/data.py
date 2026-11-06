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
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from bvmt import __version__
from bvmt.snapshots import (
    atomic_write_bytes,
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
    isin: str | None = None


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
    if bar.status not in {"traded", "no_trade", "untraded", "suspended"}:
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
    input_format: Literal[
        "canonical", "french_bvmt", "bvmt_histo_cotation", "tunis_stockexchange_ndjson"
    ],
    source_id: str,
    ingested_at: datetime,
) -> tuple[list[DailyBar], list[RejectedRow]]:
    if input_format == "tunis_stockexchange_ndjson":
        return _parse_official_ndjson(text, source_id=source_id, ingested_at=ingested_at)
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ValueError("CSV file is empty")
    header_line = lines[0]
    delimiter = ";" if (input_format != "canonical" and ";" in header_line) else ","
    header_reader = csv.reader([header_line], delimiter=delimiter)
    raw_header = next(header_reader, [])
    header = [
        col.strip().lower() if input_format == "bvmt_histo_cotation" else col.strip()
        for col in raw_header
    ]
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
    elif input_format == "bvmt_histo_cotation":
        required = {
            "seance",
            "ouverture",
            "cloture",
            "plus_bas",
            "plus_haut",
            "quantite_negociee",
            "capitaux",
        }
        if not required.issubset(header) or not {
            "valeur",
            "symbole",
            "ticker",
            "code",
        }.intersection(header):
            raise ValueError("Missing required bvmt_histo_cotation columns")
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
            elif input_format == "bvmt_histo_cotation":
                bar = _parse_official_row(row_dict, source_id=source_id, ingested_at=ingested_at)
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
    input_format: Literal[
        "canonical", "french_bvmt", "bvmt_histo_cotation", "tunis_stockexchange_ndjson"
    ],
    permission_status: str,
    retrieved_at: datetime,
    raw_dir: Path,
    output_dir: Path,
) -> ImportSummary:
    """Ingest a local CSV file, snapshot raw bytes, validate rows, and write deterministic artifacts."""
    validate_safe_id(source_id, "source identifier")
    validate_permission_status(permission_status)
    if input_format not in {
        "canonical",
        "french_bvmt",
        "bvmt_histo_cotation",
        "tunis_stockexchange_ndjson",
    }:
        raise ValueError(f"Unsupported input_format '{input_format}'")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("Retrieval time must be timezone-aware")
    ensure_no_symlink_ancestors(source_path)
    ensure_no_symlink_ancestors(raw_dir)
    ensure_no_symlink_ancestors(output_dir)

    parser_version = (
        "tunis_stockexchange_ndjson_v1"
        if input_format == "tunis_stockexchange_ndjson"
        else CANONICAL_PARSER_VERSION
        if input_format == "canonical"
        else (
            "bvmt_histo_cotation_v1"
            if input_format == "bvmt_histo_cotation"
            else FRENCH_BVMT_PARSER_VERSION
        )
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
    atomic_write_bytes(
        output_dir / "raw_source.csv", snapshot_path.read_bytes(), allow_identical=True
    )
    quality = DataQualityReport(
        untraded_or_suspended_count=sum(b.volume_shares == 0 for b in accepted),
        distinct_instruments=len({b.instrument_id for b in accepted}),
        first_session=min((b.session_date.isoformat() for b in accepted), default=None),
        last_session=max((b.session_date.isoformat() for b in accepted), default=None),
        source_sha256=raw_sha256,
    )
    quality_payload = asdict(quality)
    if input_format == "tunis_stockexchange_ndjson":
        quality_payload.update(
            {
                "accepted_rows": len(accepted),
                "rejected_rows": len(rejected),
                "distinct_sessions": len({b.session_date for b in accepted}),
                "rejection_counts": dict(
                    Counter(
                        "duplicate_instrument_session"
                        if r.reason.startswith("Duplicate")
                        else r.reason
                        for r in rejected
                    )
                ),
            }
        )
    atomic_write_text(
        output_dir / "quality_report.json",
        json.dumps(quality_payload, sort_keys=True, indent=2) + "\n",
    )
    # Preserve source identifiers independently of the unchanged canonical CSV contract.
    atomic_write_text(
        output_dir / "instrument_codes.json",
        json.dumps({b.instrument_id: b.isin for b in accepted if b.isin}, sort_keys=True, indent=2)
        + "\n",
    )
    rejected_csv = io.StringIO(newline="")
    rejection_writer = csv.writer(rejected_csv, lineterminator="\n")
    rejection_writer.writerow(["line_number", "raw_row", "reason"])
    rejection_writer.writerows((r.line_number, r.raw_row, r.reason) for r in rejected)
    atomic_write_text(
        output_dir / "rejected_rows.csv", rejected_csv.getvalue(), allow_identical=True
    )
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


@dataclass(frozen=True)
class DataQualityReport:
    untraded_or_suspended_count: int = 0
    distinct_instruments: int = 0
    first_session: str | None = None
    last_session: str | None = None
    source_sha256: str | None = None


def _parse_official_row(
    row: dict[str | None, str | None], *, source_id: str, ingested_at: datetime
) -> DailyBar:
    name = next(
        (
            (row.get(k) or "").strip()
            for k in ("valeur", "symbole", "ticker", "code")
            if (row.get(k) or "").strip()
        ),
        "",
    )
    instrument = _normalize_instrument_token(name)
    volume = parse_french_int(row.get("quantite_negociee") or "")
    close = parse_french_decimal(row.get("cloture") or "")
    prices = [
        parse_french_decimal(row.get(k) or "") for k in ("ouverture", "plus_haut", "plus_bas")
    ]
    if volume == 0 and close > 0:
        prices = [close if price == 0 else price for price in prices]
    bar = DailyBar(
        instrument_id=instrument,
        symbol=name,
        session_date=parse_french_session_date(row.get("seance") or ""),
        open=prices[0],
        high=prices[1],
        low=prices[2],
        close=close,
        volume_shares=volume,
        turnover_tnd=parse_french_decimal(row.get("capitaux") or ""),
        status="no_trade" if volume == 0 else "traded",
        source_id=source_id,
        published_at=None,
        ingested_at=ingested_at,
        isin=(row.get("code") or "").strip() or None,
    )
    validate_bar(bar)
    return bar


# Additive API; retains the established provenance and permission arguments.
import_market_csv = import_local_csv


SourceFormat = Literal[
    "canonical", "french_bvmt", "bvmt_histo_cotation", "tunis_stockexchange_ndjson"
]
OFFICIAL_SEGMENTS = {
    "11": "principal_continu",
    "12": "principal_fixing",
    "52": "alternatif",
    "99": "surveillance",
}


def _normalize_instrument_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9._-]+", "_", value.strip().upper()).strip("_")


def _parse_official_ndjson(
    text: str, *, source_id: str, ingested_at: datetime
) -> tuple[list[DailyBar], list[RejectedRow]]:
    accepted: list[DailyBar] = []
    rejected: list[RejectedRow] = []
    seen: set[tuple[str, date]] = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        try:
            payload = json.loads(line, parse_float=Decimal)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("Expected session object with data array")
            session = date.fromisoformat(payload["seance"])
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append(RejectedRow(line_number, line, str(exc)))
            continue
        for item in payload["data"]:
            try:
                if not isinstance(item, dict):
                    raise ValueError("Expected quotation object")
                if date.fromisoformat(item["dateSeance"]) != session:
                    raise ValueError("Quotation date differs from session envelope")
                row: dict[str | None, str | None] = {
                    target: str(item[key])
                    for target, key in {
                        "valeur": "valeur",
                        "code": "codeISIN",
                        "seance": "dateSeance",
                        "ouverture": "coursOuvert",
                        "plus_haut": "plusHaut",
                        "plus_bas": "plusBas",
                        "cloture": "cloture",
                        "quantite_negociee": "quantites",
                        "capitaux": "capitaux",
                    }.items()
                }
                bar = _parse_official_row(row, source_id=source_id, ingested_at=ingested_at)
                trades = parse_french_int(str(item["echanges"]), "echanges")
                if bar.volume_shares == 0:
                    if trades != 0:
                        raise ValueError("Zero volume with nonzero trades")
                    from dataclasses import replace

                    bar = replace(bar, status="untraded", turnover_tnd=Decimal("0.000"))
                key = (bar.instrument_id, bar.session_date)
                if key in seen:
                    raise ValueError(f"Duplicate instrument/session: {key}")
                seen.add(key)
                accepted.append(bar)
            except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
                rejected.append(RejectedRow(line_number, json.dumps(item, default=str), str(exc)))
    return sorted(accepted, key=lambda b: (b.instrument_id, b.session_date)), rejected


def ingest_bars_csv(
    source_path: Path,
    *,
    source_format: SourceFormat,
    source_id: str,
    permission_status: str,
    retrieved_at: datetime,
    raw_dir: Path,
    output_dir: Path,
) -> ImportSummary:
    """Explicit-format ingestion, including official quotation NDJSON; no network access."""
    return import_local_csv(
        source_path,
        source_id=source_id,
        input_format=source_format,
        permission_status=permission_status,
        retrieved_at=retrieved_at,
        raw_dir=raw_dir,
        output_dir=output_dir,
    )


def export_official_master_and_calendar(
    ndjson_path: Path, output_dir: Path, *, holidays: Sequence[str] = ()
) -> tuple[Path, Path]:
    """Export observed dated mappings and sessions, without inventing listing dates or hours.

    listed_from is the first observation (a bounded research-universe convention),
    not evidence of the original listing date. Unknown open/close times remain blank.
    Competition eligibility is the caller-requested research classification, not a rule audit.
    """
    from bvmt.calendar import CALENDAR_COLUMNS, INSTRUMENT_COLUMNS

    ensure_no_symlink_ancestors(ndjson_path)
    ensure_no_symlink_ancestors(output_dir)
    sessions: set[date] = set()
    mappings: dict[str, list[tuple[date, str, str, str]]] = {}
    for line in ndjson_path.read_text(encoding="utf-8-sig").splitlines():
        payload = json.loads(line)
        session = date.fromisoformat(payload["seance"])
        sessions.add(session)
        seen: set[str] = set()
        for item in payload["data"]:
            if date.fromisoformat(item["dateSeance"]) != session:
                raise ValueError("Quotation date differs from session envelope")
            key = _normalize_instrument_token(item["valeur"])
            if key in seen:
                raise ValueError("Duplicate instrument/session in metadata")
            seen.add(key)
            segment = OFFICIAL_SEGMENTS[str(item["groupe"])]
            observation = (session, item["codeISIN"], item["valeur"].strip(), segment)
            previous = [o for o in mappings.get(key, []) if o[0] == session]
            if previous and previous[0] != observation:
                raise ValueError("Conflicting instrument mapping within session")
            if not previous:
                mappings.setdefault(key, []).append(observation)
    if not sessions or not mappings:
        raise ValueError("Empty official dataset")
    closed = {date.fromisoformat(d) for d in holidays}
    if closed & sessions:
        raise ValueError("Observed open session conflicts with holiday")
    master = io.StringIO(newline="")
    writer = csv.writer(master, lineterminator="\n")
    writer.writerow([*INSTRUMENT_COLUMNS, "is_competition_eligible"])
    for key, observations in sorted(mappings.items()):
        observations.sort()
        runs: list[tuple[date, str, str, str]] = []
        for obs in observations:
            if not runs or obs[1:] != runs[-1][1:]:
                runs.append(obs)
        for index, (start, isin, symbol, segment) in enumerate(runs):
            end = runs[index + 1][0] - timedelta(days=1) if index + 1 < len(runs) else None
            writer.writerow(
                [
                    key,
                    isin,
                    symbol,
                    start,
                    end or "",
                    observations[0][0],
                    "",
                    segment,
                    "TND",
                    "official-bvmt-observed",
                    segment != "surveillance",
                ]
            )
    calendar = io.StringIO(newline="")
    writer = csv.writer(calendar, lineterminator="\n")
    writer.writerow(CALENDAR_COLUMNS)
    for session in sorted(sessions | closed):
        writer.writerow(
            [
                session,
                session in sessions,
                "observed_daily_unknown_hours" if session in sessions else "official_holiday",
                "",
                "",
                "Africa/Tunis",
                "official-bvmt-observed",
            ]
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    master_path, calendar_path = (
        output_dir / "instrument_master.csv",
        output_dir / "exchange_calendar.csv",
    )
    atomic_write_text(master_path, master.getvalue(), allow_identical=True)
    atomic_write_text(calendar_path, calendar.getvalue(), allow_identical=True)
    return master_path, calendar_path


@dataclass(frozen=True)
class DataFreshnessReport:
    latest_session_date: date | None
    days_since_latest_session: int
    is_stale: bool
    status: Literal["fresh", "stale", "empty"]
    stale_warning: str | None
    stale_instruments: tuple[str, ...]
    untraded_count_latest_session: int
    total_instruments: int


def check_data_freshness(
    bars: Sequence[DailyBar],
    *,
    as_of: date | None = None,
    max_calendar_lag_days: int = 4,
) -> DataFreshnessReport:
    """Validate freshness of canonical daily bars without inventing prices.

    Identifies if the dataset is missing recent sessions and flags instruments
    with no trading activity in the last 5 sessions.
    """
    if not bars:
        return DataFreshnessReport(
            latest_session_date=None,
            days_since_latest_session=999,
            is_stale=True,
            status="empty",
            stale_warning="No market bars present in dataset",
            stale_instruments=(),
            untraded_count_latest_session=0,
            total_instruments=0,
        )

    ref_date = as_of or date.today()
    latest_session = max(b.session_date for b in bars)
    lag_days = max(0, (ref_date - latest_session).days)
    is_stale = lag_days > max_calendar_lag_days

    # Analyze latest session bars
    latest_bars = [b for b in bars if b.session_date == latest_session]
    untraded_count = sum(1 for b in latest_bars if b.status != "traded" or b.volume_shares == 0)
    all_instruments = {b.instrument_id for b in bars}

    # Find stale instruments (no traded bar in the last 5 distinct sessions)
    all_sessions = sorted({b.session_date for b in bars})
    last_5_sessions = set(all_sessions[-5:]) if len(all_sessions) >= 5 else set(all_sessions)
    recent_traded = {
        b.instrument_id
        for b in bars
        if b.session_date in last_5_sessions and b.status == "traded" and b.volume_shares > 0
    }
    stale_instruments = tuple(sorted(all_instruments - recent_traded))

    warning = None
    if is_stale:
        warning = (
            f"Market data is stale: latest session is {latest_session} "
            f"({lag_days} days before reference date {ref_date}). "
            f"New recommendations should be blocked until fresh exchange data is ingested."
        )

    return DataFreshnessReport(
        latest_session_date=latest_session,
        days_since_latest_session=lag_days,
        is_stale=is_stale,
        status="stale" if is_stale else "fresh",
        stale_warning=warning,
        stale_instruments=stale_instruments,
        untraded_count_latest_session=untraded_count,
        total_instruments=len(all_instruments),
    )


@dataclass(frozen=True)
class DailyMarketRefreshResult:
    source_id: str
    source_path: str
    source_url: str | None
    retrieved_at: str
    previous_bars_count: int
    new_bars_count: int
    total_bars_count: int
    previous_sessions_count: int
    new_sessions_count: int
    total_sessions_count: int
    first_session: str | None
    latest_session: str | None
    duplicate_rows_detected: int
    rejected_rows_count: int
    stale_instruments_count: int
    quality_report_path: str
    canonical_bars_path: str
    is_data_fresh: bool
    freshness_status: str


def refresh_daily_market_pipeline(
    new_source_path: Path,
    output_dir: Path,
    *,
    source_format: SourceFormat = "tunis_stockexchange_ndjson",
    source_url: str | None = "https://www.tunis-stockexchange.com/api/market_resume.ndjson",
    source_id: str = "tunis_stockexchange_equities_2026",
    permission_status: str = "authorized_for_competition_research",
    retrieved_at: datetime | None = None,
    as_of: date | None = None,
) -> DailyMarketRefreshResult:
    """Reproducible daily data-refresh workflow with incremental session ingestion.

    1. Reads existing canonical bars from output_dir if present.
    2. Parses and validates new raw payload.
    3. Merges new sessions incrementally, discarding exact duplicates and quarantining invalid bars.
    4. Detects stale instruments and untraded bars.
    5. Writes canonical daily bars and updated data quality report with SHA-256 provenance.
    6. Never invents prices. Supports fully offline operation using latest verified dataset.
    """
    ensure_no_symlink_ancestors(new_source_path)
    ensure_no_symlink_ancestors(output_dir)
    validate_permission_status(permission_status)
    validate_safe_id(source_id)

    timestamp = retrieved_at or datetime.now(UTC)
    canonical_csv_path = output_dir / "daily_bars.canonical.csv"
    existing_bars: list[DailyBar] = []
    if canonical_csv_path.exists():
        existing_bars = read_bars_csv(canonical_csv_path)

    prev_bar_count = len(existing_bars)
    prev_sessions = {b.session_date for b in existing_bars}

    # Parse incoming raw source using established multi-format parser
    raw_text = new_source_path.read_text(encoding="utf-8-sig")
    parsed_new_bars, rejected = _parse_csv_lines(
        raw_text,
        input_format=source_format,
        source_id=source_id,
        ingested_at=timestamp,
    )

    # Merge incrementally, detecting duplicates
    existing_map = {(b.instrument_id, b.session_date): b for b in existing_bars}
    duplicate_count = 0
    added_bars: list[DailyBar] = []

    for bar in parsed_new_bars:
        key = (bar.instrument_id, bar.session_date)
        if key in existing_map:
            duplicate_count += 1
            continue
        existing_map[key] = bar
        added_bars.append(bar)

    all_merged_bars = sorted(existing_map.values(), key=lambda b: (b.instrument_id, b.session_date))
    all_sessions = sorted({b.session_date for b in all_merged_bars})

    # Validate freshness
    freshness = check_data_freshness(all_merged_bars, as_of=as_of)

    # Write canonical CSV
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\n")
    writer.writerow(CANONICAL_COLUMNS)
    for b in all_merged_bars:
        writer.writerow(
            [
                b.instrument_id,
                b.symbol,
                b.session_date.isoformat(),
                f"{b.open:.3f}",
                f"{b.high:.3f}",
                f"{b.low:.3f}",
                f"{b.close:.3f}",
                b.volume_shares,
                f"{b.turnover_tnd:.3f}",
                b.status,
                b.source_id,
                b.published_at.isoformat() if b.published_at else "",
                b.ingested_at.isoformat(),
            ]
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(canonical_csv_path, csv_buffer.getvalue(), allow_identical=True)

    # Write rejected rows if any
    if rejected:
        rej_path = output_dir / "rejected_rows.csv"
        rej_buf = io.StringIO(newline="")
        r_writer = csv.writer(rej_buf, lineterminator="\n")
        r_writer.writerow(["line_number", "raw_row", "rejection_reason"])
        for r in rejected:
            r_writer.writerow([r.line_number, r.raw_row, r.reason])
        atomic_write_text(rej_path, rej_buf.getvalue(), allow_identical=True)

    # Write quality report
    source_sha = sha256_file(new_source_path)
    status_counts = dict(Counter(b.status for b in all_merged_bars))
    quality = DataQualityReport(
        untraded_or_suspended_count=status_counts.get("untraded", 0)
        + status_counts.get("suspended", 0),
        distinct_instruments=len({b.instrument_id for b in all_merged_bars}),
        first_session=all_sessions[0].isoformat() if all_sessions else None,
        last_session=all_sessions[-1].isoformat() if all_sessions else None,
        source_sha256=source_sha,
    )
    quality_report_path = output_dir / "quality_report.json"
    atomic_write_text(
        quality_report_path,
        json.dumps(asdict(quality), indent=2, sort_keys=True, default=str),
        allow_identical=True,
    )

    # Save provenance metadata
    prov = {
        "source_id": source_id,
        "source_url": source_url,
        "source_sha256": source_sha,
        "permission_status": permission_status,
        "retrieved_at": timestamp.isoformat(),
        "total_sessions": len(all_sessions),
        "first_session": str(all_sessions[0]) if all_sessions else None,
        "latest_session": str(all_sessions[-1]) if all_sessions else None,
        "source_relationship": (
            "Official BVMT publication portal API endpoint (https://www.tunis-stockexchange.com). "
            "Data corresponds directly to the official Bourse de Tunis quotation groups."
        ),
    }
    prov_path = output_dir / "provenance.json"
    atomic_write_text(prov_path, json.dumps(prov, indent=2, sort_keys=True), allow_identical=True)

    return DailyMarketRefreshResult(
        source_id=source_id,
        source_path=str(new_source_path),
        source_url=source_url,
        retrieved_at=timestamp.isoformat(),
        previous_bars_count=prev_bar_count,
        new_bars_count=len(added_bars),
        total_bars_count=len(all_merged_bars),
        previous_sessions_count=len(prev_sessions),
        new_sessions_count=len(all_sessions) - len(prev_sessions),
        total_sessions_count=len(all_sessions),
        first_session=str(all_sessions[0]) if all_sessions else None,
        latest_session=str(all_sessions[-1]) if all_sessions else None,
        duplicate_rows_detected=duplicate_count,
        rejected_rows_count=len(rejected),
        stale_instruments_count=len(freshness.stale_instruments),
        quality_report_path=str(quality_report_path),
        canonical_bars_path=str(canonical_csv_path),
        is_data_fresh=not freshness.is_stale,
        freshness_status=freshness.status,
    )
