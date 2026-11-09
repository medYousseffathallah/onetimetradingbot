"""Unit tests for the canonical Challenge Universe Registry (Milestone 8)."""

from __future__ import annotations

from bvmt.challenge_universe import (
    CHALLENGE_TOTAL_COUNT,
    CHALLENGE_UNIVERSE_VERSION,
    classify_security_challenge_status,
    get_challenge_symbol_set,
    is_in_challenge_universe,
    resolve_challenge_record,
    validate_challenge_universe,
)

SUPPLIED_42_SYMBOLS = [
    "AB",
    "ATB",
    "ATL",
    "ARTES",
    "TJARI",
    "TJL",
    "BT",
    "BNA",
    "BH",
    "BIAT",
    "CC",
    "CITY",
    "DH",
    "NAKL",
    "ECYCL",
    "ICF",
    "LNDOR",
    "AMV",
    "SAM",
    "MPBS",
    "NBL",
    "OTH",
    "PGH",
    "SAH",
    "SFBT",
    "SIAME",
    "SMART",
    "SOTET",
    "STPAP",
    "STPIL",
    "MGR",
    "SOTUV",
    "SPDIT",
    "STA",
    "STB",
    "TLNET",
    "TPR",
    "TRE",
    "TLS",
    "UIB",
    "UMED",
    "WIFAK",
]


def test_challenge_universe_count_and_uniqueness():
    """Verify exactly 42 unique challenge symbols are registered."""
    val = validate_challenge_universe()
    assert val["is_valid"] is True
    assert val["total_count"] == 42
    assert val["total_count"] == CHALLENGE_TOTAL_COUNT
    assert val["continuous_count"] == 40
    assert val["fixing_count"] == 2
    assert val["version"] == CHALLENGE_UNIVERSE_VERSION


def test_all_supplied_symbols_preserved():
    """Verify every single one of the 42 user-supplied symbols is present in the registry."""
    registered = get_challenge_symbol_set()
    assert len(registered) == 42
    for sym in SUPPLIED_42_SYMBOLS:
        assert sym in registered, f"Missing supplied symbol: {sym}"


def test_non_members_blocked():
    """Verify non-challenge stocks (e.g. MNP, SCN) are strictly recognized as non-members."""
    assert not is_in_challenge_universe(instrument_id="MONOPRIX")
    assert not is_in_challenge_universe(symbol="MNP")
    assert not is_in_challenge_universe(isin="TN0001000108")

    assert not is_in_challenge_universe(instrument_id="ESSOUKNA")
    assert not is_in_challenge_universe(symbol="SCN")
    assert not is_in_challenge_universe(isin="TN0007210016")

    # Other non-members
    assert not is_in_challenge_universe(instrument_id="AIR_LIQUIDE_TSIE")
    assert not is_in_challenge_universe(symbol="ALKIMIA")


def test_classify_security_challenge_status():
    """Verify classification output separates universe membership, order-entry permission, and reasons."""
    # Member: STA
    sta_status = classify_security_challenge_status("STA", isin="TNNGTFLC2986")
    assert sta_status["in_challenge_universe"] is True
    assert sta_status["challenge_symbol"] == "STA"
    assert sta_status["order_entry_eligibility"] == "CONFIRMED"
    assert sta_status["exclusion_reason"] is None

    # Member: BH BANK
    bh_status = classify_security_challenge_status("BH_BANK", isin="TN0001900604")
    assert bh_status["in_challenge_universe"] is True
    assert bh_status["challenge_symbol"] == "BH"
    assert bh_status["canonical_bvmt_symbol"] == "BH BANK"

    # Non-member: MONOPRIX
    mnp_status = classify_security_challenge_status("MONOPRIX", isin="TN0001000108", symbol="MNP")
    assert mnp_status["in_challenge_universe"] is False
    assert mnp_status["order_entry_eligibility"] == "NOT_IN_UNIVERSE"
    assert "does not appear in the observed 42-instrument" in mnp_status["exclusion_reason"]

    # Non-member: SCN
    scn_status = classify_security_challenge_status("ESSOUKNA", symbol="SCN")
    assert scn_status["in_challenge_universe"] is False
    assert scn_status["order_entry_eligibility"] == "NOT_IN_UNIVERSE"


def test_symbol_resolution_mappings():
    """Test resolution by challenge symbol, canonical instrument ID, and ISIN."""
    # MGR -> SOTUMAG (TN0006580013)
    rec_mgr = resolve_challenge_record("MGR")
    assert rec_mgr is not None
    assert rec_mgr.canonical_instrument_id == "SOTUMAG"
    assert rec_mgr.verified_isin == "TN0006580013"

    # SAM -> ATELIER MEUBLE INT (TN0007740012)
    rec_sam = resolve_challenge_record("SAM")
    assert rec_sam is not None
    assert rec_sam.canonical_instrument_id == "ATELIER_MEUBLE_INT"

    # AMV -> ASSU MAGHREBIA VIE (TNDKJ8O68X14)
    rec_amv = resolve_challenge_record("AMV")
    assert rec_amv is not None
    assert rec_amv.canonical_instrument_id == "ASSU_MAGHREBIA_VIE"

    # PGH -> POULINA GP HOLDING
    rec_pgh = resolve_challenge_record("PGH")
    assert rec_pgh is not None
    assert rec_pgh.canonical_instrument_id == "POULINA_GP_HOLDING"

    # Unknown symbol
    assert resolve_challenge_record("UNKNOWN_TICKER") is None


def test_pre_opening_non_cote_semantics():
    """Verify pre-opening non-cote is treated as an activity state, not permanent disqualification."""
    rec = resolve_challenge_record("STA")
    assert rec is not None
    # A challenge member remains in the universe and has order entry eligibility
    assert rec.observed_challenge_membership is True
    assert rec.order_entry_eligibility == "CONFIRMED"
