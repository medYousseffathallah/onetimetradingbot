"""Research projections preserve source identity while joining verified aliases."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from bvmt.calendar import read_instrument_master
from bvmt.data import read_bars_csv
from bvmt.research_identity import (
    canonicalize_research_identity,
    challenge_membership_accounting,
)

DATA = Path("data/processed/bvmt_official_2026")
requires_official_data = pytest.mark.skipif(
    not (DATA / "daily_bars.canonical.csv").is_file(),
    reason="Local official historical snapshot is unavailable",
)


@requires_official_data
def test_poulina_projection_preserves_source_rows_and_joins_196_sessions():
    master = read_instrument_master(DATA / "instrument_master.csv")
    bars = read_bars_csv(DATA / "daily_bars.canonical.csv")
    original = tuple(bars)
    projected = canonicalize_research_identity(master, bars)
    pgh = [b for b in projected.bars if b.instrument_id == "POULINA_GP_HOLDING"]
    assert len(pgh) == 196
    assert len({b.session_date for b in pgh}) == 196
    assert {b.symbol for b in pgh} == {"POULINA GP HOLDING", "POULINA GROUP HOLDING"}
    assert tuple(bars) == original
    before = next(b for b in bars if b.instrument_id == "POULINA_GROUP_HOLDING")
    after = next(b for b in pgh if b.session_date == before.session_date)
    assert replace(after, instrument_id=before.instrument_id) == before
    aliases = [a for a in projected.aliases if a.canonical_instrument_id == "POULINA_GP_HOLDING"]
    assert {a.source_instrument_id for a in aliases} == {
        "POULINA_GP_HOLDING",
        "POULINA_GROUP_HOLDING",
    }
    assert len([r for r in projected.instruments if r.isin == "TN0005700018"]) == 1


@requires_official_data
def test_all_42_members_accounted_separately_from_evaluability():
    master = read_instrument_master(DATA / "instrument_master.csv")
    projected = canonicalize_research_identity(master, [])
    rows = challenge_membership_accounting(projected.instruments)
    assert len(rows) == 42
    assert all(r["membership_accounted"] for r in rows)
    assert sum(bool(r["has_usable_metrics"]) for r in rows) == 0


@requires_official_data
def test_alias_overlap_is_rejected_even_when_prices_match():
    master = read_instrument_master(DATA / "instrument_master.csv")
    bar = next(
        b
        for b in read_bars_csv(DATA / "daily_bars.canonical.csv")
        if b.instrument_id == "POULINA_GP_HOLDING"
    )
    with pytest.raises(ValueError, match="overlap"):
        canonicalize_research_identity(
            master, [bar, replace(bar, instrument_id="POULINA_GROUP_HOLDING")]
        )


@requires_official_data
def test_known_alias_with_conflicting_isin_is_rejected():
    master = read_instrument_master(DATA / "instrument_master.csv")
    bar = next(
        b
        for b in read_bars_csv(DATA / "daily_bars.canonical.csv")
        if b.instrument_id == "POULINA_GP_HOLDING"
    )
    with pytest.raises(ValueError, match="ISIN"):
        canonicalize_research_identity(master, [replace(bar, isin="TN0003200755")])


@requires_official_data
def test_name_similarity_is_not_identity_evidence():
    master = read_instrument_master(DATA / "instrument_master.csv")
    base = next(r for r in master if r.instrument_id == "POULINA_GP_HOLDING")
    unrelated = replace(
        base, instrument_id="POULINA_SIMILAR", symbol="POULINA SIMILAR", isin="TN0000000001"
    )
    projection = canonicalize_research_identity([base, unrelated], [])
    assert {r.instrument_id for r in projection.instruments} == {
        "POULINA_GP_HOLDING",
        "POULINA_SIMILAR",
    }


@requires_official_data
def test_holding_report_membership_and_dynamic_narrative():
    from bvmt.holding_period import evaluate_holding_periods

    report = evaluate_holding_periods(horizons=[19], universe="TUNIS_BOURSE_CHALLENGE")
    assert report.membership_accounted_count == 42
    assert len(report.membership_accounting) == 42
    assert report.usable_research_count <= 42
    assert report.dataset_session_count == 196
    assert not any("194 trading sessions" in line for line in report.reasoning)
    assert report.research_version == "holding_period_identity_v2"
    assert report.availability_policy == "EOD_REPLAY_ASSUMPTION_NOT_VERIFIED_PUBLICATION"


def test_unsupported_holding_scope_rejected():
    from bvmt.holding_period import evaluate_holding_periods

    with pytest.raises(ValueError, match="universe"):
        evaluate_holding_periods(horizons=[19], universe="unknown")


@requires_official_data
def test_disjoint_alias_validity_does_not_become_continuous_history():
    master = read_instrument_master(DATA / "instrument_master.csv")
    older = next(r for r in master if r.instrument_id == "POULINA_GROUP_HOLDING")
    newer = next(r for r in master if r.instrument_id == "POULINA_GP_HOLDING")
    with pytest.raises(ValueError, match="disjoint"):
        canonicalize_research_identity([replace(older, valid_to=date(2026, 3, 31)), newer], [])
    with pytest.raises(ValueError, match="disjoint"):
        canonicalize_research_identity([replace(older, listed_to=date(2026, 3, 31)), newer], [])


@requires_official_data
def test_alias_fallback_requires_record_valid_on_bar_date():
    master = read_instrument_master(DATA / "instrument_master.csv")
    bar = next(
        b
        for b in read_bars_csv(DATA / "daily_bars.canonical.csv")
        if b.instrument_id == "POULINA_GROUP_HOLDING"
    )
    with pytest.raises(ValueError, match="dated alias"):
        canonicalize_research_identity(
            master, [replace(bar, instrument_id="POULINA_GP_HOLDING", isin=None)]
        )
    with pytest.raises(ValueError, match="dated alias"):
        canonicalize_research_identity(master, [replace(bar, instrument_id="POULINA_GP_HOLDING")])
