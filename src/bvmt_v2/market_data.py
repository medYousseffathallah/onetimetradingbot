"""Local equity archive and November 9 Challenge registry (version 2026.11.09-v1)."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from hashlib import file_digest, sha256
from pathlib import Path
from typing import Literal

from .contracts import Instrument, MarketObservation, PriceProvenance, ValueStatus, pv, utc

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/v2_market"
REGISTRY_KNOWN = datetime(2026, 11, 9, 8, 30, tzinfo=UTC)
# Source-checked ISIN, canonical ID, Challenge symbol, quotation mode.
REGISTRY = {
    isin: (key, symbol, mode)
    for isin, key, symbol, mode in (
        ("TN0003400058", "AMEN_BANK", "AB", "Continu"),
        ("TN0003600350", "ATB", "ATB", "Continu"),
        ("TN0004700100", "ATL", "ATL", "Continu"),
        ("TN0007300015", "ARTES", "ARTES", "Continu"),
        ("TN0001600154", "ATTIJARI_BANK", "TJARI", "Continu"),
        ("TN0006610018", "ATTIJARI_LEASING", "TJL", "Continu"),
        ("TN0002200053", "BT", "BT", "Continu"),
        ("TN0003100609", "BNA", "BNA", "Continu"),
        ("TN0001900604", "BH_BANK", "BH", "Continu"),
        ("TN0001800457", "BIAT", "BIAT", "Continu"),
        ("TN0007400013", "CARTHAGE_CEMENT", "CC", "Continu"),
        ("TN0007550015", "CITY_CARS", "CITY", "Continu"),
        ("TN0007670011", "DELICE_HOLDING", "DH", "Continu"),
        ("TN0007410012", "ENNAKL_AUTOMOBILES", "NAKL", "Continu"),
        ("TN0007570013", "EURO-CYCLES", "ECYCL", "Continu"),
        ("TN0003200755", "ICF", "ICF", "Continu"),
        ("TN0007510019", "LAND_OR", "LNDOR", "Continu"),
        ("TNDKJ8O68X14", "ASSU_MAGHREBIA_VIE", "AMV", "Continu"),
        ("TN0007740012", "ATELIER_MEUBLE_INT", "SAM", "Continu"),
        ("TN0007620016", "MPBS", "MPBS", "Continu"),
        ("TN0007540016", "NEW_BODY_LINE", "NBL", "Continu"),
        ("TN0007530017", "ONE_TECH_HOLDING", "OTH", "Continu"),
        ("TN0005700018", "POULINA_GROUP_HOLDING", "PGH", "Continu"),
        ("TN0007610017", "SAH", "SAH", "Continu"),
        ("TN0001100254", "SFBT", "SFBT", "Continu"),
        ("TN0006590012", "SIAME", "SIAME", "Continu"),
        ("TNQPQXRODTH8", "SMART_TUNISIE", "SMART", "Continu"),
        ("TN0006530018", "SOTETEL", "SOTET", "Continu"),
        ("TN0007630015", "SOTIPAPIER", "STPAP", "Continu"),
        ("TN0006660013", "SOTRAPIL", "STPIL", "Continu"),
        ("TN0006580013", "SOTUMAG", "MGR", "Continu"),
        ("TN0006560015", "SOTUVER", "SOTUV", "Continu"),
        ("TN0001400704", "SPDIT_-_SICAF", "SPDIT", "Continu"),
        ("TNNGTFLC2986", "STA", "STA", "Continu"),
        ("TN0002600955", "STB", "STB", "Continu"),
        ("TN0007440019", "TELNET_HOLDING", "TLNET", "Continu"),
        ("TN0007270010", "TPR", "TPR", "Continu"),
        ("TN0007380017", "TUNIS_RE", "TRE", "Fixing"),
        ("TN0002100907", "TUNISIE_LEASING_F", "TLS", "Continu"),
        ("TN0003900107", "UIB", "UIB", "Continu"),
        ("TN0007720014", "UNIMED", "UMED", "Continu"),
        ("TN0007200017", "WIFACK_INT_BANK", "WIFAK", "Fixing"),
    )
}
ALIASES = {"POULINA_GP_HOLDING": "POULINA_GROUP_HOLDING", "MNP": "MONOPRIX", "SCN": "ESSOUKNA"}


@dataclass(frozen=True)
class MarketData:
    instruments: dict[str, Instrument]
    bars: dict[str, tuple[MarketObservation, ...]]
    sessions: tuple[date, ...]
    rejected_non_equity_count: int = 0

    def resolve(self, identifier: str) -> str:
        token = identifier.strip().upper()
        token = ALIASES.get(token, token)
        if token in self.instruments:
            return token
        for key, i in self.instruments.items():
            if token in (i.isin, i.symbol) or (i.challenge_member and REGISTRY[i.isin][1] == token):
                return key
        raise KeyError(identifier)


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _timestamp(value: str | None) -> datetime | None:
    return utc(datetime.fromisoformat(value)) if value else None


def _instrument(
    key: str,
    isin: str,
    symbol: str,
    listed: date | None,
    end: date | None,
    sector: str | None = None,
) -> Instrument:
    registry = REGISTRY.get(isin)
    normalized_symbol = symbol.upper().replace(" ", "_")
    member = (
        registry is not None
        and key == registry[0]
        and (ALIASES.get(normalized_symbol, normalized_symbol) == key or symbol == registry[1])
    )
    return Instrument(
        instrument_id=key,
        isin=isin,
        symbol=symbol,
        challenge_member=member,
        order_entry_eligibility="CONFIRMED" if member else "NOT_IN_UNIVERSE",
        market_mode=registry[2] if member and registry else "Unknown",
        listed_from=listed,
        listed_to=end,
        sector=sector,
    )


def _observation(
    row: dict[str, str],
    key: str,
    session: date,
    digest: str,
    validated: datetime,
    synthetic: bool = False,
) -> MarketObservation:
    ingested = _timestamp(row["ingested_at"])
    if ingested is None:
        raise ValueError("ingested_at required for PIT archive")
    published = _timestamp(row.get("published_at"))
    retrieved = _timestamp(row.get("retrieved_at"))
    observed = _timestamp(row.get("first_observed_at")) or retrieved or ingested
    source = row["source_id"]
    status: ValueStatus = "SIMULATED" if synthetic else "OBSERVED"
    prices = {
        col: pv(row[col], "TND", status, source, validated, observed=observed)
        if row.get(col)
        else pv(None, "TND", "UNAVAILABLE", source, validated, "Missing source price")
        for col in ("open", "high", "low", "close", "turnover_tnd")
    }
    volume = int(row["volume_shares"])
    if volume < 0:
        raise ValueError("Negative share volume")
    opening, high, low, close = (prices[k].value for k in ("open", "high", "low", "close"))
    if (
        opening is not None
        and high is not None
        and low is not None
        and close is not None
        and not (low <= min(opening, close) <= max(opening, close) <= high)
    ):
        raise ValueError(f"Inconsistent OHLC for {key} on {session}")
    quality: Literal[
        "SYNTHETIC_FIXTURE",
        "STALE_NO_TRADE",
        "EOD_UNVERIFIED_PUB_TIME",
        "VERIFIED_PIT",
        "SUSPENDED",
    ]
    if synthetic:
        quality = "SYNTHETIC_FIXTURE"
    elif row["status"].lower() == "suspended":
        quality = "SUSPENDED"
    elif volume == 0 or row["status"] == "untraded":
        quality = "STALE_NO_TRADE"
    else:
        quality = "VERIFIED_PIT" if published else "EOD_UNVERIFIED_PUB_TIME"
    provenance = PriceProvenance(
        event_time=session,
        exchange_session=session,
        source_publication_time=published,
        first_observed_at=observed,
        retrieved_at=retrieved,
        ingested_at=ingested,
        validated_at=validated,
        source_id=source,
        source_hash=digest,
        data_quality_status=quality,
        historical_eod_close_tnd=prices["close"],
        current_executable_quote_tnd=pv(
            None,
            "TND",
            "UNAVAILABLE",
            source,
            validated,
            "EOD archive contains no executable quote",
        ),
    )
    return MarketObservation(
        instrument_id=key,
        session_date=session,
        open_tnd=prices["open"],
        high_tnd=prices["high"],
        low_tnd=prices["low"],
        close_tnd=prices["close"],
        volume_shares=volume,
        turnover_tnd=prices["turnover_tnd"],
        status=row["status"],
        provenance=provenance,
    )


def load_market(
    bars_path: Path = DATA / "daily_bars.equity_only.csv",
    master_path: Path = DATA / "instrument_master.csv",
    calendar_path: Path = DATA / "exchange_calendar.csv",
    *,
    validated_at: datetime | None = None,
) -> MarketData:
    checked = utc(validated_at or datetime.now(UTC))
    with calendar_path.open(encoding="utf-8-sig", newline="") as handle:
        calendar = {
            date.fromisoformat(r["session_date"])
            for r in csv.DictReader(handle)
            if r["is_open"].lower() in {"true", "1"}
        }
    instruments: dict[str, Instrument] = {}
    aliases: dict[str, str] = {}
    with master_path.open(encoding="utf-8-sig", newline="") as handle:
        for r in csv.DictReader(handle):
            if (r.get("asset_type") or r.get("instrument_type") or "equity").lower() not in {
                "equity",
                "stock",
                "share",
            }:
                continue
            original = r["instrument_id"]
            key = (
                "POULINA_GROUP_HOLDING"
                if r["isin"] == "TN0005700018"
                and original in {"POULINA_GP_HOLDING", "POULINA_GROUP_HOLDING"}
                else original
            )
            if r.get("currency", "TND") != "TND":
                raise ValueError("Only TND instruments supported")
            aliases[original] = key
            candidate = _instrument(
                key,
                r["isin"],
                key.replace("_", " ") if key != original else r["symbol"],
                _date(r.get("listed_from")),
                _date(r.get("listed_to")),
                r.get("sector") or None,
            )
            if key in instruments:
                previous = instruments[key]
                if candidate.isin != previous.isin:
                    raise ValueError(f"Conflicting ISIN for {key}")
                starts = [d for d in (previous.listed_from, candidate.listed_from) if d]
                ends = (previous.listed_to, candidate.listed_to)
                candidate = candidate.model_copy(
                    update={
                        "listed_from": min(starts, default=None),
                        "listed_to": max(d for d in ends if d) if all(ends) else None,
                    }
                )
            instruments[key] = candidate
    rows: dict[str, dict[date, MarketObservation]] = defaultdict(dict)
    rejected = 0
    with bars_path.open("rb") as binary:
        digest = file_digest(binary, "sha256").hexdigest()
    with bars_path.open(encoding="utf-8-sig", newline="") as handle:
        for r in csv.DictReader(handle):
            key = aliases.get(r["instrument_id"])
            if key is None or (r.get("asset_type") or "equity").lower() not in {
                "equity",
                "stock",
                "share",
            }:
                rejected += 1
                continue
            session = date.fromisoformat(r["session_date"])
            if session not in calendar:
                raise ValueError(f"Bar outside open calendar: {session}")
            bar = _observation(r, key, session, digest, checked)
            prev = rows[key].get(session)
            if prev and prev != bar:
                raise ValueError(f"Conflicting observations for {key} {session}")
            rows[key][session] = bar
    return MarketData(
        instruments,
        {k: tuple(s[d] for d in sorted(s)) for k, s in rows.items()},
        tuple(sorted(calendar)),
        rejected,
    )


def synthetic_market() -> MarketData:
    """Standalone, deterministic simulated weekday calendar and prices."""
    start = date(2026, 1, 2)
    sessions = tuple(d for n in range(321) if (d := start + timedelta(days=n)).weekday() < 5)
    instruments = {}
    bars = {}
    entries = [
        (isin, record[0])
        for isin, record in REGISTRY.items()
        if record[0] in {"AMEN_BANK", "ATB", "EURO-CYCLES", "DELICE_HOLDING"}
    ]
    entries.extend([("TN0001000108", "MONOPRIX"), ("TN0004000055", "SIMPAR")])
    for j, (isin, key) in enumerate(entries):
        instruments[key] = _instrument(key, isin, key, start, None)
        series = []
        for n, day in enumerate(sessions):
            at = datetime.combine(day, time(15), UTC)
            price = Decimal(10 + j) + Decimal(n + j * (n % 7)) / 100
            volume = 12000 + j * 200
            row = {
                "open": str(price),
                "high": str(price + 1),
                "low": str(price - 1),
                "close": str(price),
                "turnover_tnd": str(volume * price),
                "volume_shares": str(volume),
                "source_id": "SYNTHETIC_DEMO",
                "status": "traded",
                "ingested_at": at.isoformat(),
                "published_at": at.isoformat(),
            }
            series.append(
                _observation(row, key, day, sha256(repr(row).encode()).hexdigest(), at, True)
            )
        bars[key] = tuple(series)
    return MarketData(instruments, bars, sessions)
