"""Dated instrument master, official BVMT exchange calendar, and observation coverage diagnostics.

Separates BVMT exchange sessions from Tunis Bourse Challenge simulator execution windows.
Never hardcodes unverified regular, Ramadan, or summer trading hours, and never forward-fills
prices or fabricates volume across missing, suspended, or holiday sessions.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from bvmt.data import DailyBar, aware_timestamp, validate_bar
from bvmt.snapshots import validate_safe_id

INSTRUMENT_ID_RE = re.compile(r"[A-Za-z0-9._-]+")
ISIN_RE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")

INSTRUMENT_COLUMNS = (
    "instrument_id",
    "isin",
    "symbol",
    "valid_from",
    "valid_to",
    "listed_from",
    "listed_to",
    "market_segment",
    "currency",
    "source_document_id",
)

CALENDAR_COLUMNS = (
    "session_date",
    "is_open",
    "schedule_type",
    "opens_at",
    "closes_at",
    "timezone",
    "source_document_id",
)

ObservationClass = Literal[
    "traded",
    "no_trade",
    "suspended",
    "holiday",
    "missing_observation",
    "stale_quote",
    "unlisted_or_delisted",
]


@dataclass(frozen=True)
class InstrumentRecord:
    instrument_id: str
    isin: str | None
    symbol: str
    valid_from: date
    valid_to: date | None
    listed_from: date
    listed_to: date | None
    market_segment: str
    currency: str
    source_document_id: str


@dataclass(frozen=True)
class ExchangeSession:
    session_date: date
    is_open: bool
    schedule_type: str
    opens_at: datetime | None
    closes_at: datetime | None
    timezone: str
    source_document_id: str


@dataclass(frozen=True)
class SuspensionRecord:
    instrument_id: str
    session_date: date
    source_document_id: str
    reason: str = "official_suspension"


@dataclass(frozen=True)
class ClassifiedObservation:
    instrument_id: str
    symbol: str | None
    session_date: date
    classification: ObservationClass
    detail: str


@dataclass(frozen=True)
class CoverageReport:
    start_date: str
    end_date: str
    total_instrument_sessions_evaluated: int
    classification_counts: dict[str, int]
    missing_exchange_sessions: list[str]
    calendar_coverage_gaps: list[str]
    missing_instrument_observations: list[dict[str, str]]
    duplicated_historical_symbols: list[str]
    unsupported_instrument_histories: list[str]
    unexplained_stale_quotes: list[dict[str, str]]
    listing_and_delisting_inconsistencies: list[str]
    unverified_suspensions: list[dict[str, str]]
    observations: list[ClassifiedObservation]


def _optional_date(value: object, field_name: str) -> date | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() == "null":
        return None
    try:
        return date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date for {field_name}: '{value}'") from exc


def _required_date(value: object, field_name: str) -> date:
    parsed = _optional_date(value, field_name)
    if parsed is None:
        raise ValueError(f"Missing required date for {field_name}")
    return parsed


def _parse_bool(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    cleaned = str(value).strip().lower()
    if cleaned in {"true", "1"}:
        return True
    if cleaned in {"false", "0"}:
        return False
    raise ValueError(f"Invalid boolean for {field_name}: '{value}'")


def validate_instrument_record(record: InstrumentRecord) -> None:
    if not INSTRUMENT_ID_RE.fullmatch(record.instrument_id.strip()):
        raise ValueError(f"Invalid instrument_id '{record.instrument_id}'")
    if record.isin is not None:
        cleaned_isin = record.isin.strip()
        if not ISIN_RE.fullmatch(cleaned_isin):
            raise ValueError(f"Invalid ISIN '{record.isin}'")
    if not record.symbol.strip():
        raise ValueError("Instrument symbol is required")
    if not record.market_segment.strip():
        raise ValueError("Instrument market_segment is required")
    if not record.currency.strip():
        raise ValueError("Instrument currency is required")
    validate_safe_id(record.source_document_id, "source_document_id")
    if record.valid_to is not None and record.valid_to < record.valid_from:
        raise ValueError(
            f"Instrument '{record.instrument_id}' valid_to ({record.valid_to}) "
            f"precedes valid_from ({record.valid_from})"
        )
    if record.listed_to is not None and record.listed_to < record.listed_from:
        raise ValueError(
            f"Instrument '{record.instrument_id}' listed_to ({record.listed_to}) "
            f"precedes listed_from ({record.listed_from})"
        )
    if record.valid_from < record.listed_from:
        raise ValueError(
            f"Instrument '{record.instrument_id}' valid_from ({record.valid_from}) "
            f"precedes listed_from ({record.listed_from})"
        )
    if record.listed_to is not None and (
        record.valid_to is None or record.valid_to > record.listed_to
    ):
        raise ValueError(
            f"Instrument '{record.instrument_id}' validity window extends beyond "
            f"listed_to ({record.listed_to})"
        )


def _ranges_overlap(start_a: date, end_a: date | None, start_b: date, end_b: date | None) -> bool:
    max_start = max(start_a, start_b)
    if end_a is None and end_b is None:
        return True
    if end_a is None:
        return end_b is not None and max_start <= end_b
    if end_b is None:
        return max_start <= end_a
    return max_start <= min(end_a, end_b)


def validate_instrument_master(records: Iterable[InstrumentRecord]) -> list[InstrumentRecord]:
    result = list(records)
    if not result:
        raise ValueError("Instrument master is empty")
    for record in result:
        validate_instrument_record(record)

    by_instrument: dict[str, list[InstrumentRecord]] = defaultdict(list)
    by_symbol: dict[str, list[InstrumentRecord]] = defaultdict(list)
    for record in result:
        by_instrument[record.instrument_id].append(record)
        by_symbol[record.symbol].append(record)

    for instrument_id, inst_records in by_instrument.items():
        inst_records.sort(key=lambda r: r.valid_from)
        listed_pairs = {(r.listed_from, r.listed_to) for r in inst_records}
        if len(listed_pairs) > 1:
            raise ValueError(
                f"Inconsistent listing bounds across records for instrument '{instrument_id}'"
            )
        for idx in range(len(inst_records)):
            for jdx in range(idx + 1, len(inst_records)):
                a = inst_records[idx]
                b = inst_records[jdx]
                if _ranges_overlap(a.valid_from, a.valid_to, b.valid_from, b.valid_to):
                    raise ValueError(
                        f"Overlapping validity ranges for instrument '{instrument_id}': "
                        f"({a.valid_from}..{a.valid_to}) and ({b.valid_from}..{b.valid_to})"
                    )

    for symbol, sym_records in by_symbol.items():
        sym_records.sort(key=lambda r: r.valid_from)
        for idx in range(len(sym_records)):
            for jdx in range(idx + 1, len(sym_records)):
                a = sym_records[idx]
                b = sym_records[jdx]
                if _ranges_overlap(a.valid_from, a.valid_to, b.valid_from, b.valid_to):
                    raise ValueError(
                        f"Overlapping symbol assignment for symbol '{symbol}' between "
                        f"'{a.instrument_id}' and '{b.instrument_id}'"
                    )

    return sorted(result, key=lambda r: (r.instrument_id, r.valid_from))


def _instrument_from_mapping(row: dict[str, object]) -> InstrumentRecord:
    raw_isin = row.get("isin")
    isin = str(raw_isin).strip() if raw_isin is not None and str(raw_isin).strip() else None
    if isin and isin.lower() == "null":
        isin = None
    record = InstrumentRecord(
        instrument_id=str(row.get("instrument_id") or "").strip(),
        isin=isin,
        symbol=str(row.get("symbol") or "").strip(),
        valid_from=_required_date(row.get("valid_from"), "valid_from"),
        valid_to=_optional_date(row.get("valid_to"), "valid_to"),
        listed_from=_required_date(row.get("listed_from"), "listed_from"),
        listed_to=_optional_date(row.get("listed_to"), "listed_to"),
        market_segment=str(row.get("market_segment") or "").strip(),
        currency=str(row.get("currency") or "").strip(),
        source_document_id=str(row.get("source_document_id") or "").strip(),
    )
    validate_instrument_record(record)
    return record


def read_instrument_master(path: Path) -> list[InstrumentRecord]:
    """Load and validate a dated instrument master from CSV or JSON."""
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON instrument master must be a list of objects")
        records: list[InstrumentRecord] = []
        for idx, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Instrument master item {idx} must be an object")
            if set(item.keys()) != set(INSTRUMENT_COLUMNS):
                raise ValueError(
                    f"Expected instrument master keys {sorted(INSTRUMENT_COLUMNS)}, "
                    f"got {sorted(item.keys())}"
                )
            records.append(_instrument_from_mapping(item))
        return validate_instrument_master(records)

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or set(header) != set(INSTRUMENT_COLUMNS):
            raise ValueError(
                f"Expected unique instrument master columns: {sorted(INSTRUMENT_COLUMNS)}"
            )
        records = []
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(val is None for val in row.values()):
                raise ValueError(f"Column count mismatch on instrument master row {line_number}")
            clean_row: dict[str, object] = {str(k): v for k, v in row.items() if k is not None}
            try:
                records.append(_instrument_from_mapping(clean_row))
            except ValueError as exc:
                raise ValueError(f"Invalid instrument master row {line_number}: {exc}") from exc
    return validate_instrument_master(records)


def resolve_instrument_on_date(
    records: Iterable[InstrumentRecord], instrument_id: str, session_date: date
) -> InstrumentRecord | None:
    """Return the active InstrumentRecord for instrument_id on session_date, or None."""
    for record in records:
        if record.instrument_id != instrument_id:
            continue
        if record.valid_from <= session_date and (
            record.valid_to is None or session_date <= record.valid_to
        ):
            return record
    return None


def validate_exchange_session(session: ExchangeSession) -> None:
    if session.timezone != "Africa/Tunis":
        raise ValueError(
            f"Exchange session timezone must be 'Africa/Tunis', got '{session.timezone}'"
        )
    if not session.schedule_type.strip():
        raise ValueError("Exchange session schedule_type is required")
    validate_safe_id(session.source_document_id, "source_document_id")
    if session.is_open:
        if session.opens_at is None or session.closes_at is None:
            raise ValueError(
                f"Open exchange session {session.session_date} requires explicit "
                "opens_at and closes_at timestamps (never infer default hours)"
            )
        if session.opens_at >= session.closes_at:
            raise ValueError(
                f"Exchange session {session.session_date} opens_at must precede closes_at"
            )
        if (
            session.opens_at.date() != session.session_date
            or session.closes_at.date() != session.session_date
        ):
            raise ValueError(
                f"Exchange session {session.session_date} timestamps must fall on session_date"
            )
    else:
        if session.opens_at is not None or session.closes_at is not None:
            raise ValueError(
                f"Closed/holiday session {session.session_date} must not have opens_at/closes_at"
            )


def validate_exchange_calendar(sessions: Iterable[ExchangeSession]) -> list[ExchangeSession]:
    result = list(sessions)
    if not result:
        raise ValueError("Exchange calendar is empty")
    seen: set[date] = set()
    for session in result:
        validate_exchange_session(session)
        if session.session_date in seen:
            raise ValueError(f"Duplicate exchange session_date: {session.session_date}")
        seen.add(session.session_date)
    return sorted(result, key=lambda s: s.session_date)


def _session_from_mapping(row: dict[str, object]) -> ExchangeSession:
    raw_opens = row.get("opens_at")
    raw_closes = row.get("closes_at")
    opens_str = str(raw_opens).strip() if raw_opens is not None else ""
    closes_str = str(raw_closes).strip() if raw_closes is not None else ""
    opens_at = aware_timestamp(opens_str) if opens_str and opens_str.lower() != "null" else None
    closes_at = aware_timestamp(closes_str) if closes_str and closes_str.lower() != "null" else None
    session = ExchangeSession(
        session_date=_required_date(row.get("session_date"), "session_date"),
        is_open=_parse_bool(row.get("is_open"), "is_open"),
        schedule_type=str(row.get("schedule_type") or "").strip(),
        opens_at=opens_at,
        closes_at=closes_at,
        timezone=str(row.get("timezone") or "").strip(),
        source_document_id=str(row.get("source_document_id") or "").strip(),
    )
    validate_exchange_session(session)
    return session


def read_exchange_calendar(path: Path) -> list[ExchangeSession]:
    """Load and validate an official-source-backed exchange calendar from CSV or JSON."""
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON exchange calendar must be a list of objects")
        sessions: list[ExchangeSession] = []
        for idx, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Exchange calendar item {idx} must be an object")
            if set(item.keys()) != set(CALENDAR_COLUMNS):
                raise ValueError(
                    f"Expected exchange calendar keys {sorted(CALENDAR_COLUMNS)}, "
                    f"got {sorted(item.keys())}"
                )
            sessions.append(_session_from_mapping(item))
        return validate_exchange_calendar(sessions)

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or set(header) != set(CALENDAR_COLUMNS):
            raise ValueError(
                f"Expected unique exchange calendar columns: {sorted(CALENDAR_COLUMNS)}"
            )
        sessions = []
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(val is None for val in row.values()):
                raise ValueError(f"Column count mismatch on exchange calendar row {line_number}")
            clean_row: dict[str, object] = {str(k): v for k, v in row.items() if k is not None}
            try:
                sessions.append(_session_from_mapping(clean_row))
            except ValueError as exc:
                raise ValueError(f"Invalid exchange calendar row {line_number}: {exc}") from exc
    return validate_exchange_calendar(sessions)


def evaluate_coverage(
    instruments: Iterable[InstrumentRecord],
    calendar: Iterable[ExchangeSession],
    bars: Iterable[DailyBar],
    *,
    suspensions: Iterable[SuspensionRecord] = (),
    start_date: date | None = None,
    end_date: date | None = None,
    stale_after_open_sessions: int = 3,
) -> CoverageReport:
    """Classify instrument/date observations and report calendar, master, and quote anomalies.

    Never forward-fills missing bars, never infers suspension from zero volume alone, and
    requires explicit suspension evidence (SuspensionRecord) for any suspended bar.
    """
    if stale_after_open_sessions < 1:
        raise ValueError("stale_after_open_sessions must be >= 1")
    inst_list = list(instruments)
    cal_list = validate_exchange_calendar(calendar)
    bar_list = list(bars)
    for bar in bar_list:
        validate_bar(bar)

    duplicated_symbols: list[str] = []
    listing_inconsistencies: list[str] = []
    unsupported_histories: list[str] = []

    by_inst: dict[str, list[InstrumentRecord]] = defaultdict(list)
    by_sym: dict[str, list[InstrumentRecord]] = defaultdict(list)
    for rec in inst_list:
        validate_instrument_record(rec)
        by_inst[rec.instrument_id].append(rec)
        by_sym[rec.symbol].append(rec)

    for inst_id, recs in sorted(by_inst.items()):
        recs.sort(key=lambda r: r.valid_from)
        if len({(r.listed_from, r.listed_to) for r in recs}) > 1:
            listing_inconsistencies.append(
                f"Instrument '{inst_id}' has conflicting listed_from/listed_to bounds across records"
            )
        for idx in range(len(recs)):
            for jdx in range(idx + 1, len(recs)):
                if _ranges_overlap(
                    recs[idx].valid_from,
                    recs[idx].valid_to,
                    recs[jdx].valid_from,
                    recs[jdx].valid_to,
                ):
                    unsupported_histories.append(
                        f"Overlapping validity ranges for instrument '{inst_id}'"
                    )

    for sym, recs in sorted(by_sym.items()):
        recs.sort(key=lambda r: r.valid_from)
        for idx in range(len(recs)):
            for jdx in range(idx + 1, len(recs)):
                if _ranges_overlap(
                    recs[idx].valid_from,
                    recs[idx].valid_to,
                    recs[jdx].valid_from,
                    recs[jdx].valid_to,
                ):
                    duplicated_symbols.append(
                        f"Overlapping symbol '{sym}' between '{recs[idx].instrument_id}' "
                        f"and '{recs[jdx].instrument_id}'"
                    )

    suspension_map: dict[tuple[str, date], SuspensionRecord] = {}
    for susp in suspensions:
        validate_safe_id(susp.source_document_id, "suspension source_document_id")
        suspension_map[(susp.instrument_id, susp.session_date)] = susp

    calendar_by_date: dict[date, ExchangeSession] = {s.session_date: s for s in cal_list}
    all_dates: set[date] = set(calendar_by_date.keys()) | {b.session_date for b in bar_list}
    if not all_dates:
        raise ValueError("No dates available to evaluate")

    eval_start = start_date if start_date is not None else min(all_dates)
    eval_end = end_date if end_date is not None else max(all_dates)
    if eval_end < eval_start:
        raise ValueError("end_date cannot precede start_date")

    missing_exchange_sessions: list[str] = []
    calendar_coverage_gaps: list[str] = []
    cursor = eval_start
    while cursor <= eval_end:
        if cursor.weekday() < 5 and cursor not in calendar_by_date:
            calendar_coverage_gaps.append(cursor.isoformat())
        cursor = date.fromordinal(cursor.toordinal() + 1)

    bar_by_key: dict[tuple[str, date], DailyBar] = {}
    for bar in bar_list:
        if bar.session_date not in calendar_by_date:
            if bar.session_date.isoformat() not in missing_exchange_sessions:
                missing_exchange_sessions.append(bar.session_date.isoformat())
        else:
            cal_session = calendar_by_date[bar.session_date]
            if not cal_session.is_open:
                unsupported_histories.append(
                    f"Bar observed for '{bar.instrument_id}' on closed/holiday session "
                    f"{bar.session_date.isoformat()}"
                )
        if bar.instrument_id not in by_inst:
            unsupported_histories.append(
                f"Bar observed for unknown instrument_id '{bar.instrument_id}' on "
                f"{bar.session_date.isoformat()}"
            )
        else:
            inst_bounds = by_inst[bar.instrument_id][0]
            if bar.session_date < inst_bounds.listed_from or (
                inst_bounds.listed_to is not None and bar.session_date > inst_bounds.listed_to
            ):
                listing_inconsistencies.append(
                    f"Bar observed for '{bar.instrument_id}' on {bar.session_date.isoformat()} "
                    f"outside listing range ({inst_bounds.listed_from}..{inst_bounds.listed_to})"
                )
            active_rec = resolve_instrument_on_date(inst_list, bar.instrument_id, bar.session_date)
            if active_rec is None:
                unsupported_histories.append(
                    f"No valid symbol mapping for '{bar.instrument_id}' on "
                    f"{bar.session_date.isoformat()}"
                )
            elif active_rec.symbol != bar.symbol:
                unsupported_histories.append(
                    f"Symbol mismatch for '{bar.instrument_id}' on {bar.session_date.isoformat()}: "
                    f"bar has '{bar.symbol}', master expects '{active_rec.symbol}'"
                )
        bar_by_key[(bar.instrument_id, bar.session_date)] = bar

    observations: list[ClassifiedObservation] = []
    missing_instrument_observations: list[dict[str, str]] = []
    unexplained_stale_quotes: list[dict[str, str]] = []
    unverified_suspensions: list[dict[str, str]] = []

    eval_sessions = [s for s in cal_list if eval_start <= s.session_date <= eval_end]

    for inst_id in sorted(by_inst.keys()):
        inst_recs = by_inst[inst_id]
        listed_from = inst_recs[0].listed_from
        listed_to = inst_recs[0].listed_to
        consecutive_no_trade = 0

        for session in eval_sessions:
            s_date = session.session_date
            active_rec = resolve_instrument_on_date(inst_recs, inst_id, s_date)
            symbol = active_rec.symbol if active_rec is not None else None
            is_listed = s_date >= listed_from and (listed_to is None or s_date <= listed_to)

            if not is_listed:
                observations.append(
                    ClassifiedObservation(
                        instrument_id=inst_id,
                        symbol=symbol,
                        session_date=s_date,
                        classification="unlisted_or_delisted",
                        detail="Outside instrument listed_from..listed_to range",
                    )
                )
                continue

            if not session.is_open:
                observations.append(
                    ClassifiedObservation(
                        instrument_id=inst_id,
                        symbol=symbol,
                        session_date=s_date,
                        classification="holiday",
                        detail=f"Exchange closed ({session.schedule_type})",
                    )
                )
                continue

            obs_bar = bar_by_key.get((inst_id, s_date))
            susp_evidence = suspension_map.get((inst_id, s_date))

            if obs_bar is None:
                if susp_evidence is not None:
                    consecutive_no_trade = 0
                    observations.append(
                        ClassifiedObservation(
                            instrument_id=inst_id,
                            symbol=symbol,
                            session_date=s_date,
                            classification="suspended",
                            detail=f"Suspended without bar ({susp_evidence.source_document_id})",
                        )
                    )
                else:
                    missing_instrument_observations.append(
                        {
                            "instrument_id": inst_id,
                            "session_date": s_date.isoformat(),
                            "symbol": symbol or "",
                        }
                    )
                    observations.append(
                        ClassifiedObservation(
                            instrument_id=inst_id,
                            symbol=symbol,
                            session_date=s_date,
                            classification="missing_observation",
                            detail="Listed instrument has no bar or suspension record on open session",
                        )
                    )
                continue

            if obs_bar.status == "suspended":
                consecutive_no_trade = 0
                if susp_evidence is None:
                    unverified_suspensions.append(
                        {
                            "instrument_id": inst_id,
                            "session_date": s_date.isoformat(),
                            "reason": "Bar claims status='suspended' without supporting SuspensionRecord",
                        }
                    )
                    unsupported_histories.append(
                        f"Unverified suspension for '{inst_id}' on {s_date.isoformat()}"
                    )
                observations.append(
                    ClassifiedObservation(
                        instrument_id=inst_id,
                        symbol=symbol,
                        session_date=s_date,
                        classification="suspended",
                        detail=(
                            f"Verified suspension ({susp_evidence.source_document_id})"
                            if susp_evidence is not None
                            else "Unverified suspension (missing SuspensionRecord)"
                        ),
                    )
                )
            elif obs_bar.status == "no_trade":
                consecutive_no_trade += 1
                if consecutive_no_trade >= stale_after_open_sessions:
                    unexplained_stale_quotes.append(
                        {
                            "consecutive_open_sessions": str(consecutive_no_trade),
                            "instrument_id": inst_id,
                            "reference_close": str(obs_bar.close),
                            "session_date": s_date.isoformat(),
                        }
                    )
                    observations.append(
                        ClassifiedObservation(
                            instrument_id=inst_id,
                            symbol=symbol,
                            session_date=s_date,
                            classification="stale_quote",
                            detail=(
                                f"Zero-volume reference quote unchanged/untraded for "
                                f"{consecutive_no_trade} consecutive open sessions"
                            ),
                        )
                    )
                else:
                    observations.append(
                        ClassifiedObservation(
                            instrument_id=inst_id,
                            symbol=symbol,
                            session_date=s_date,
                            classification="no_trade",
                            detail="Open session with zero traded shares",
                        )
                    )
            else:
                consecutive_no_trade = 0
                observations.append(
                    ClassifiedObservation(
                        instrument_id=inst_id,
                        symbol=symbol,
                        session_date=s_date,
                        classification="traded",
                        detail=f"Traded {obs_bar.volume_shares} shares",
                    )
                )

    counts: dict[str, int] = {
        str(k): v for k, v in sorted(Counter(o.classification for o in observations).items())
    }
    return CoverageReport(
        start_date=eval_start.isoformat(),
        end_date=eval_end.isoformat(),
        total_instrument_sessions_evaluated=len(observations),
        classification_counts=counts,
        missing_exchange_sessions=sorted(missing_exchange_sessions),
        calendar_coverage_gaps=sorted(calendar_coverage_gaps),
        missing_instrument_observations=missing_instrument_observations,
        duplicated_historical_symbols=duplicated_symbols,
        unsupported_instrument_histories=unsupported_histories,
        unexplained_stale_quotes=unexplained_stale_quotes,
        listing_and_delisting_inconsistencies=listing_inconsistencies,
        unverified_suspensions=unverified_suspensions,
        observations=observations,
    )
