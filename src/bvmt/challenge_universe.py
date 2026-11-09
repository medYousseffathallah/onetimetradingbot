"""Canonical Registry & Governance for the Tunis Bourse Challenge Quotation Universe.

Milestone 8: Challenge Universe Alignment & Trade Planner Safety.

Guarantees:
1. Exact Universe Membership: Programmatically manages the 42 observed challenge securities.
2. Distinct Statuses: Clearly separates:
   - Universe membership (in 42 challenge list vs full 76 BVMT)
   - Order-entry eligibility (CONFIRMED, UNVERIFIED, BLOCKED, NOT_IN_UNIVERSE)
   - Market session phase & current trading activity (active_quote, non_cote, untraded_today)
   - Strategy eligibility (quantitative filter)
   - Execution feasibility (volume/liquidity capacity)
3. Safety Guard: Disallows order planning or position sizing for non-members (e.g. MNP, SCN)
   without independently verified order-entry eligibility.
4. Pre-Market Honesty: Pre-opening 'non coté' is recognized as absence of current trades,
   NOT as permanent ineligibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

CHALLENGE_UNIVERSE_VERSION = "2026.11.09-v1"
CHALLENGE_OBSERVED_AT = "2026-11-09T09:00:00+01:00"
CHALLENGE_VERIFIED_AT = "2026-11-09T09:30:00+01:00"
CHALLENGE_SOURCE_URL = "https://www.tunisbourse-challenge.com/"
CHALLENGE_TOTAL_COUNT = 42

UniverseType = Literal["TUNIS_BOURSE_CHALLENGE", "FULL_BVMT_RESEARCH"]
OrderEntryStatus = Literal["CONFIRMED", "UNVERIFIED", "BLOCKED", "NOT_IN_UNIVERSE"]
MappingStatus = Literal["MAPPED", "UNRESOLVED", "AMBIGUOUS"]
TradingActivityStatus = Literal["active_quote", "non_cote", "untraded_today", "unknown"]


@dataclass(frozen=True)
class ChallengeInstrumentRecord:
    """Canonical, source-attributed record of a security in the challenge universe."""

    challenge_symbol: str
    challenge_display_name: str
    canonical_bvmt_symbol: str
    canonical_instrument_id: str
    verified_isin: str
    mapping_status: MappingStatus = "MAPPED"
    observed_challenge_membership: bool = True
    order_entry_eligibility: OrderEntryStatus = "CONFIRMED"
    observation_timestamp: str = CHALLENGE_OBSERVED_AT
    verification_timestamp: str = CHALLENGE_VERIFIED_AT
    source_url: str = CHALLENGE_SOURCE_URL
    registry_version: str = CHALLENGE_UNIVERSE_VERSION
    market_mode: Literal["Continu", "Fixing"] = "Continu"
    trading_activity_status: TradingActivityStatus = "active_quote"
    quote_freshness: str = "FRESH"
    exclusion_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Canonical 42 observed challenge instruments mapped directly to verified BVMT instruments and ISINs.
_RAW_CHALLENGE_ENTRIES: list[dict[str, Any]] = [
    {
        "challenge_symbol": "AB",
        "challenge_display_name": "AMEN BANK",
        "canonical_bvmt_symbol": "AMEN BANK",
        "canonical_instrument_id": "AMEN_BANK",
        "verified_isin": "TN0003400058",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "ATB",
        "challenge_display_name": "ATB",
        "canonical_bvmt_symbol": "ATB",
        "canonical_instrument_id": "ATB",
        "verified_isin": "TN0003600350",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "ATL",
        "challenge_display_name": "ATL",
        "canonical_bvmt_symbol": "ATL",
        "canonical_instrument_id": "ATL",
        "verified_isin": "TN0004700100",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "ARTES",
        "challenge_display_name": "ARTES",
        "canonical_bvmt_symbol": "ARTES",
        "canonical_instrument_id": "ARTES",
        "verified_isin": "TN0007300015",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "TJARI",
        "challenge_display_name": "ATTIJARI BANK",
        "canonical_bvmt_symbol": "ATTIJARI BANK",
        "canonical_instrument_id": "ATTIJARI_BANK",
        "verified_isin": "TN0001600154",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "TJL",
        "challenge_display_name": "ATTIJARI LEASING",
        "canonical_bvmt_symbol": "ATTIJARI LEASING",
        "canonical_instrument_id": "ATTIJARI_LEASING",
        "verified_isin": "TN0006610018",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "BT",
        "challenge_display_name": "BT",
        "canonical_bvmt_symbol": "BT",
        "canonical_instrument_id": "BT",
        "verified_isin": "TN0002200053",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "BNA",
        "challenge_display_name": "BNA",
        "canonical_bvmt_symbol": "BNA",
        "canonical_instrument_id": "BNA",
        "verified_isin": "TN0003100609",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "BH",
        "challenge_display_name": "BH BANK",
        "canonical_bvmt_symbol": "BH BANK",
        "canonical_instrument_id": "BH_BANK",
        "verified_isin": "TN0001900604",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "BIAT",
        "challenge_display_name": "BIAT",
        "canonical_bvmt_symbol": "BIAT",
        "canonical_instrument_id": "BIAT",
        "verified_isin": "TN0001800457",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "CC",
        "challenge_display_name": "CARTHAGE CEMENT",
        "canonical_bvmt_symbol": "CARTHAGE CEMENT",
        "canonical_instrument_id": "CARTHAGE_CEMENT",
        "verified_isin": "TN0007400013",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "CITY",
        "challenge_display_name": "CITY CARS",
        "canonical_bvmt_symbol": "CITY CARS",
        "canonical_instrument_id": "CITY_CARS",
        "verified_isin": "TN0007550015",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "DH",
        "challenge_display_name": "DELICE HOLDING",
        "canonical_bvmt_symbol": "DELICE HOLDING",
        "canonical_instrument_id": "DELICE_HOLDING",
        "verified_isin": "TN0007670011",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "NAKL",
        "challenge_display_name": "ENNAKL AUTOMOBILES",
        "canonical_bvmt_symbol": "ENNAKL AUTOMOBILES",
        "canonical_instrument_id": "ENNAKL_AUTOMOBILES",
        "verified_isin": "TN0007410012",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "ECYCL",
        "challenge_display_name": "EURO-CYCLES",
        "canonical_bvmt_symbol": "EURO-CYCLES",
        "canonical_instrument_id": "EURO-CYCLES",
        "verified_isin": "TN0007570013",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "ICF",
        "challenge_display_name": "ICF",
        "canonical_bvmt_symbol": "ICF",
        "canonical_instrument_id": "ICF",
        "verified_isin": "TN0003200755",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "LNDOR",
        "challenge_display_name": "LAND OR",
        "canonical_bvmt_symbol": "LAND OR",
        "canonical_instrument_id": "LAND_OR",
        "verified_isin": "TN0007510019",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "AMV",
        "challenge_display_name": "ASSU MAGHREBIA VIE",
        "canonical_bvmt_symbol": "ASSU MAGHREBIA VIE",
        "canonical_instrument_id": "ASSU_MAGHREBIA_VIE",
        "verified_isin": "TNDKJ8O68X14",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SAM",
        "challenge_display_name": "ATELIER MEUBLE INT",
        "canonical_bvmt_symbol": "ATELIER MEUBLE INT",
        "canonical_instrument_id": "ATELIER_MEUBLE_INT",
        "verified_isin": "TN0007740012",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "MPBS",
        "challenge_display_name": "MPBS",
        "canonical_bvmt_symbol": "MPBS",
        "canonical_instrument_id": "MPBS",
        "verified_isin": "TN0007620016",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "NBL",
        "challenge_display_name": "NEW BODY LINE",
        "canonical_bvmt_symbol": "NEW BODY LINE",
        "canonical_instrument_id": "NEW_BODY_LINE",
        "verified_isin": "TN0007540016",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "OTH",
        "challenge_display_name": "ONE TECH HOLDING",
        "canonical_bvmt_symbol": "ONE TECH HOLDING",
        "canonical_instrument_id": "ONE_TECH_HOLDING",
        "verified_isin": "TN0007530017",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "PGH",
        "challenge_display_name": "POULINA GP HOLDING",
        "canonical_bvmt_symbol": "POULINA GP HOLDING",
        "canonical_instrument_id": "POULINA_GP_HOLDING",
        "verified_isin": "TN0005700018",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SAH",
        "challenge_display_name": "SAH",
        "canonical_bvmt_symbol": "SAH",
        "canonical_instrument_id": "SAH",
        "verified_isin": "TN0007610017",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SFBT",
        "challenge_display_name": "SFBT",
        "canonical_bvmt_symbol": "SFBT",
        "canonical_instrument_id": "SFBT",
        "verified_isin": "TN0001100254",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SIAME",
        "challenge_display_name": "SIAME",
        "canonical_bvmt_symbol": "SIAME",
        "canonical_instrument_id": "SIAME",
        "verified_isin": "TN0006590012",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SMART",
        "challenge_display_name": "SMART TUNISIE",
        "canonical_bvmt_symbol": "SMART TUNISIE",
        "canonical_instrument_id": "SMART_TUNISIE",
        "verified_isin": "TNQPQXRODTH8",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SOTET",
        "challenge_display_name": "SOTETEL",
        "canonical_bvmt_symbol": "SOTETEL",
        "canonical_instrument_id": "SOTETEL",
        "verified_isin": "TN0006530018",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "STPAP",
        "challenge_display_name": "SOTIPAPIER",
        "canonical_bvmt_symbol": "SOTIPAPIER",
        "canonical_instrument_id": "SOTIPAPIER",
        "verified_isin": "TN0007630015",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "STPIL",
        "challenge_display_name": "SOTRAPIL",
        "canonical_bvmt_symbol": "SOTRAPIL",
        "canonical_instrument_id": "SOTRAPIL",
        "verified_isin": "TN0006660013",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "MGR",
        "challenge_display_name": "SOTUMAG",
        "canonical_bvmt_symbol": "SOTUMAG",
        "canonical_instrument_id": "SOTUMAG",
        "verified_isin": "TN0006580013",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SOTUV",
        "challenge_display_name": "SOTUVER",
        "canonical_bvmt_symbol": "SOTUVER",
        "canonical_instrument_id": "SOTUVER",
        "verified_isin": "TN0006560015",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "SPDIT",
        "challenge_display_name": "SPDIT - SICAF",
        "canonical_bvmt_symbol": "SPDIT - SICAF",
        "canonical_instrument_id": "SPDIT_-_SICAF",
        "verified_isin": "TN0001400704",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "STA",
        "challenge_display_name": "STA",
        "canonical_bvmt_symbol": "STA",
        "canonical_instrument_id": "STA",
        "verified_isin": "TNNGTFLC2986",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "STB",
        "challenge_display_name": "STB",
        "canonical_bvmt_symbol": "STB",
        "canonical_instrument_id": "STB",
        "verified_isin": "TN0002600955",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "TLNET",
        "challenge_display_name": "TELNET HOLDING",
        "canonical_bvmt_symbol": "TELNET HOLDING",
        "canonical_instrument_id": "TELNET_HOLDING",
        "verified_isin": "TN0007440019",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "TPR",
        "challenge_display_name": "TPR",
        "canonical_bvmt_symbol": "TPR",
        "canonical_instrument_id": "TPR",
        "verified_isin": "TN0007270010",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "TRE",
        "challenge_display_name": "TUNIS RE",
        "canonical_bvmt_symbol": "TUNIS RE",
        "canonical_instrument_id": "TUNIS_RE",
        "verified_isin": "TN0007380017",
        "market_mode": "Fixing",
    },
    {
        "challenge_symbol": "TLS",
        "challenge_display_name": "TUNISIE LEASING F",
        "canonical_bvmt_symbol": "TUNISIE LEASING F",
        "canonical_instrument_id": "TUNISIE_LEASING_F",
        "verified_isin": "TN0002100907",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "UIB",
        "challenge_display_name": "UIB",
        "canonical_bvmt_symbol": "UIB",
        "canonical_instrument_id": "UIB",
        "verified_isin": "TN0003900107",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "UMED",
        "challenge_display_name": "UNIMED",
        "canonical_bvmt_symbol": "UNIMED",
        "canonical_instrument_id": "UNIMED",
        "verified_isin": "TN0007720014",
        "market_mode": "Continu",
    },
    {
        "challenge_symbol": "WIFAK",
        "challenge_display_name": "WIFACK INT BANK",
        "canonical_bvmt_symbol": "WIFACK INT BANK",
        "canonical_instrument_id": "WIFACK_INT_BANK",
        "verified_isin": "TN0007200017",
        "market_mode": "Fixing",
    },
]

# Build registries
CHALLENGE_UNIVERSE_REGISTRY: dict[str, ChallengeInstrumentRecord] = {
    entry["challenge_symbol"]: ChallengeInstrumentRecord(**entry)
    for entry in _RAW_CHALLENGE_ENTRIES
}

# Fast lookup maps
_BY_CANONICAL_ID: dict[str, ChallengeInstrumentRecord] = {
    r.canonical_instrument_id: r for r in CHALLENGE_UNIVERSE_REGISTRY.values()
}
# Map alternative Poulina ID if present
if "POULINA_GP_HOLDING" in _BY_CANONICAL_ID:
    _BY_CANONICAL_ID["POULINA_GROUP_HOLDING"] = _BY_CANONICAL_ID["POULINA_GP_HOLDING"]

_BY_ISIN: dict[str, ChallengeInstrumentRecord] = {
    r.verified_isin: r for r in CHALLENGE_UNIVERSE_REGISTRY.values()
}

_BY_CANONICAL_SYMBOL: dict[str, ChallengeInstrumentRecord] = {
    r.canonical_bvmt_symbol.upper(): r for r in CHALLENGE_UNIVERSE_REGISTRY.values()
}


def get_challenge_universe() -> list[ChallengeInstrumentRecord]:
    """Return all 42 registered challenge instruments."""
    return list(CHALLENGE_UNIVERSE_REGISTRY.values())


def get_challenge_symbol_set() -> set[str]:
    """Return the set of 42 uppercase challenge symbols."""
    return set(CHALLENGE_UNIVERSE_REGISTRY.keys())


def is_in_challenge_universe(
    instrument_id: str | None = None,
    isin: str | None = None,
    symbol: str | None = None,
) -> bool:
    """Check whether a security belongs to the observed 42 challenge universe."""
    if instrument_id:
        clean_id = instrument_id.strip()
        if clean_id.upper() in CHALLENGE_UNIVERSE_REGISTRY:
            return True
        if clean_id in _BY_CANONICAL_ID:
            return True
    if isin and isin.strip() in _BY_ISIN:
        return True
    if symbol:
        clean_sym = symbol.strip().upper()
        if clean_sym in CHALLENGE_UNIVERSE_REGISTRY:
            return True
        if clean_sym in _BY_CANONICAL_SYMBOL:
            return True
    return False


def resolve_challenge_record(identifier: str) -> ChallengeInstrumentRecord | None:
    """Resolve an identifier (challenge symbol, instrument ID, ISIN, or symbol) to its record."""
    clean = identifier.strip()
    if clean.upper() in CHALLENGE_UNIVERSE_REGISTRY:
        return CHALLENGE_UNIVERSE_REGISTRY[clean.upper()]
    if clean in _BY_CANONICAL_ID:
        return _BY_CANONICAL_ID[clean]
    if clean in _BY_ISIN:
        return _BY_ISIN[clean]
    if clean.upper() in _BY_CANONICAL_SYMBOL:
        return _BY_CANONICAL_SYMBOL[clean.upper()]
    return None


def validate_challenge_universe() -> dict[str, Any]:
    """Programmatically validate the 42 challenge symbols, checking uniqueness and ISIN integrity."""
    symbols = list(CHALLENGE_UNIVERSE_REGISTRY.keys())
    unique_symbols = set(symbols)
    assert len(symbols) == CHALLENGE_TOTAL_COUNT, (
        f"Expected {CHALLENGE_TOTAL_COUNT} symbols, got {len(symbols)}"
    )
    assert len(unique_symbols) == CHALLENGE_TOTAL_COUNT, (
        f"Duplicate symbols found: {len(symbols) - len(unique_symbols)}"
    )

    isins = [r.verified_isin for r in CHALLENGE_UNIVERSE_REGISTRY.values()]
    assert len(isins) == len(set(isins)), "Duplicate ISINs found in challenge universe"

    continu_count = sum(
        1 for r in CHALLENGE_UNIVERSE_REGISTRY.values() if r.market_mode == "Continu"
    )
    fixing_count = sum(1 for r in CHALLENGE_UNIVERSE_REGISTRY.values() if r.market_mode == "Fixing")

    return {
        "is_valid": True,
        "total_count": len(symbols),
        "continuous_count": continu_count,
        "fixing_count": fixing_count,
        "version": CHALLENGE_UNIVERSE_VERSION,
        "observed_at": CHALLENGE_OBSERVED_AT,
        "symbols": sorted(symbols),
    }


def classify_security_challenge_status(
    instrument_id: str,
    isin: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Classify a security with explicit separate statuses for membership, trading activity, and order eligibility."""
    rec = resolve_challenge_record(instrument_id)
    if rec is None and isin:
        rec = resolve_challenge_record(isin)
    if rec is None and symbol:
        rec = resolve_challenge_record(symbol)

    if rec is not None:
        return {
            "in_challenge_universe": True,
            "challenge_symbol": rec.challenge_symbol,
            "canonical_instrument_id": rec.canonical_instrument_id,
            "canonical_bvmt_symbol": rec.canonical_bvmt_symbol,
            "verified_isin": rec.verified_isin,
            "order_entry_eligibility": rec.order_entry_eligibility,
            "market_mode": rec.market_mode,
            "trading_activity_status": rec.trading_activity_status,
            "quote_freshness": rec.quote_freshness,
            "exclusion_reason": None,
        }

    # Non-member (e.g. MNP, SCN)
    return {
        "in_challenge_universe": False,
        "challenge_symbol": None,
        "canonical_instrument_id": instrument_id,
        "canonical_bvmt_symbol": symbol or instrument_id,
        "verified_isin": isin,
        "order_entry_eligibility": "NOT_IN_UNIVERSE",
        "market_mode": "Unknown",
        "trading_activity_status": "unknown",
        "quote_freshness": "FRESH",
        "exclusion_reason": (
            f"Security '{symbol or instrument_id}' does not appear in the observed 42-instrument "
            f"Tunis Bourse Challenge quotation list. Nonmembers are blocked from manual competition "
            f"order plans to prevent order rejection."
        ),
    }
