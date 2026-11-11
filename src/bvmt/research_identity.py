"""Non-destructive research projections using the saved, ISIN-backed registry.

Source names and dated source records are evidence, not interchangeable keys.
Only identities in the existing registry may be joined by this projection.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from bvmt.calendar import InstrumentRecord
from bvmt.challenge_universe import get_challenge_universe, resolve_challenge_record
from bvmt.data import DailyBar

RESEARCH_IDENTITY_VERSION = "registered_isin_projection_v1"


@dataclass(frozen=True)
class ResearchAliasEvidence:
    canonical_instrument_id: str
    source_instrument_id: str
    source_symbol: str
    isin: str | None
    declared_valid_from: date
    declared_valid_to: date | None
    observed_first_session: date | None
    observed_last_session: date | None
    source_document_id: str
    declared_alias_validity_overlaps: bool


@dataclass(frozen=True)
class ResearchIdentityProjection:
    instruments: tuple[InstrumentRecord, ...]
    bars: tuple[DailyBar, ...]
    aliases: tuple[ResearchAliasEvidence, ...]


def _canonical_id(instrument_id: str, isin: str | None) -> str:
    by_id = resolve_challenge_record(instrument_id)
    by_isin = resolve_challenge_record(isin) if isin else None
    if by_id is not None and isin is not None and by_id.verified_isin != isin:
        raise ValueError(f"Conflicting registered ISIN for {instrument_id}: {isin}")
    # ID-only matching does not establish a new alias. It can retain an existing
    # canonical name; joining two source names requires ISIN evidence.
    return by_isin.canonical_instrument_id if by_isin is not None else instrument_id


def _require_connected_ranges(
    records: list[InstrumentRecord], start_field: str, end_field: str
) -> None:
    """A min/max projection must not fabricate coverage across a dated gap."""
    ordered = sorted(records, key=lambda record: getattr(record, start_field))
    end = getattr(ordered[0], end_field) or date.max
    for record in ordered[1:]:
        start = getattr(record, start_field)
        if start.toordinal() > end.toordinal() + 1:
            raise ValueError(f"Unsupported disjoint alias {start_field} coverage")
        end = max(end, getattr(record, end_field) or date.max)


def canonicalize_research_identity(
    instruments: Iterable[InstrumentRecord], bars: Iterable[DailyBar]
) -> ResearchIdentityProjection:
    """Join verified aliases in memory, retaining original symbol and provenance.

    Declared overlapping validity ranges are exposed in alias evidence. Observed
    ranges are not silently relabeled as authoritative alias effective dates.
    Overlapping canonical-session bars always reject the projection.
    """
    master = tuple(instruments)
    grouped: dict[str, list[InstrumentRecord]] = defaultdict(list)
    source_records: dict[str, list[InstrumentRecord]] = defaultdict(list)
    for record in master:
        grouped[_canonical_id(record.instrument_id, record.isin)].append(record)
        source_records[record.instrument_id].append(record)
    projected_bars: list[DailyBar] = []
    observed: dict[str, list[date]] = defaultdict(list)
    seen: set[tuple[str, date]] = set()
    for bar in bars:
        declared_records = source_records.get(bar.instrument_id, [])
        dated_records = [
            record
            for record in declared_records
            if record.valid_from <= bar.session_date <= (record.valid_to or date.max)
            and record.listed_from <= bar.session_date <= (record.listed_to or date.max)
        ]
        if declared_records and not dated_records:
            raise ValueError(f"Bar outside dated alias validity for {bar.instrument_id}")
        evidence_isins = {record.isin for record in dated_records if record.isin}
        if len(evidence_isins) > 1:
            raise ValueError(f"Ambiguous dated alias ISIN for {bar.instrument_id}")
        if bar.isin and evidence_isins and bar.isin not in evidence_isins:
            raise ValueError(f"Bar ISIN conflicts with master for {bar.instrument_id}")
        isin = bar.isin
        if isin is None and len(evidence_isins) == 1:
            isin = next(iter(evidence_isins))
        canonical_id = _canonical_id(bar.instrument_id, isin)
        key = canonical_id, bar.session_date
        if key in seen:
            raise ValueError(f"Canonical alias overlap for {key}")
        seen.add(key)
        observed[bar.instrument_id].append(bar.session_date)
        projected_bars.append(
            replace(bar, instrument_id=canonical_id) if canonical_id != bar.instrument_id else bar
        )
    normalized_master: list[InstrumentRecord] = []
    aliases: list[ResearchAliasEvidence] = []
    for canonical_id, records in sorted(grouped.items()):
        source_ids = {r.instrument_id for r in records}
        joins_aliases = len(source_ids) > 1
        if joins_aliases:
            if len({r.isin for r in records}) != 1 or records[0].isin is None:
                raise ValueError(f"Ambiguous ISIN alias group for {canonical_id}")
            if (
                len({(r.currency, r.market_segment, r.is_competition_eligible) for r in records})
                != 1
            ):
                raise ValueError(f"Conflicting alias classification for {canonical_id}")
            _require_connected_ranges(records, "valid_from", "valid_to")
            _require_connected_ranges(records, "listed_from", "listed_to")
            preferred = next((r for r in records if r.instrument_id == canonical_id), records[-1])
            # This is a canonical security lifetime, not a fabricated alias date.
            normalized_master.append(
                replace(
                    preferred,
                    instrument_id=canonical_id,
                    valid_from=min(r.valid_from for r in records),
                    valid_to=None
                    if any(r.valid_to is None for r in records)
                    else max(r.valid_to for r in records if r.valid_to is not None),
                    listed_from=min(r.listed_from for r in records),
                    listed_to=None
                    if any(r.listed_to is None for r in records)
                    else max(r.listed_to for r in records if r.listed_to is not None),
                )
            )
        else:
            normalized_master.extend(replace(r, instrument_id=canonical_id) for r in records)
        for record in records:
            dates = observed.get(record.instrument_id, [])
            overlaps = any(
                other.instrument_id != record.instrument_id
                and record.valid_from <= (other.valid_to or date.max)
                and other.valid_from <= (record.valid_to or date.max)
                for other in records
            )
            aliases.append(
                ResearchAliasEvidence(
                    canonical_id,
                    record.instrument_id,
                    record.symbol,
                    record.isin,
                    record.valid_from,
                    record.valid_to,
                    min(dates) if dates else None,
                    max(dates) if dates else None,
                    record.source_document_id,
                    overlaps,
                )
            )
    return ResearchIdentityProjection(
        tuple(normalized_master), tuple(projected_bars), tuple(aliases)
    )


def challenge_membership_accounting(
    instruments: Iterable[InstrumentRecord], evaluable_ids: Iterable[str] = ()
) -> list[dict[str, Any]]:
    """Account for every registered member without asserting data sufficiency."""
    master = tuple(instruments)
    usable = set(evaluable_ids)
    rows = []
    for registered in get_challenge_universe():
        matches = [r for r in master if r.isin == registered.verified_isin]
        rows.append(
            {
                "challenge_symbol": registered.challenge_symbol,
                "isin": registered.verified_isin,
                "canonical_instrument_id": registered.canonical_instrument_id,
                "source_instrument_ids": sorted({r.instrument_id for r in matches}),
                "membership_accounted": bool(matches),
                "has_usable_metrics": registered.canonical_instrument_id in usable,
            }
        )
    return rows
