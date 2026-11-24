from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from bvmt_v2.contracts import pv
from bvmt_v2.market_data import synthetic_market
from bvmt_v2.research_engine import (
    SUPPORT,
    Disclosure,
    ResearchContext,
    ResearchEngine,
    bounded_risk_ratio_v2,
)


@pytest.fixture(scope="module")
def market():
    return synthetic_market()


def test_future_prices_publications_and_ingestion_cannot_move_cutoff(market):
    key = "AMEN_BANK"
    series = market.bars[key]
    at = series[80].provenance.ingested_at
    event = Disclosure(key, "Known before cutoff", at, at, "test_filing")
    future = Disclosure(key, "Not yet available", at, at + timedelta(seconds=1), "future_filing")
    ctx = ResearchContext(events=(event, future))
    early = replace(
        market, sessions=market.sessions[:81], bars={k: s[:81] for k, s in market.bars.items()}
    )
    expected = ResearchEngine(early, at, ctx).candidate(key)
    assert expected == ResearchEngine(market, at, ctx).candidate(key)
    assert expected.assessment.event_context == (event.summary,)
    late = series[80].model_copy(
        update={
            "provenance": series[80].provenance.model_copy(
                update={"ingested_at": at + timedelta(seconds=1)}
            )
        }
    )
    edited = replace(market, bars={**market.bars, key: (*series[:80], late, *series[81:])})
    missing = ResearchEngine(edited, at, ctx).candidate(key)
    assert missing.assessment.state == "INSUFFICIENT_EVIDENCE"
    assert missing.assessment.technical_state["ret_20s"].value is None


def test_future_bar_in_peer_cannot_influence_breadth_or_relative_strength(market):
    series = market.bars["ATB"]
    at = series[80].provenance.ingested_at
    altered = series[81].model_copy(
        update={
            "close_tnd": pv("9000", "TND", "SIMULATED", "shock", series[81].provenance.ingested_at)
        }
    )
    changed = replace(market, bars={**market.bars, "ATB": (*series[:81], altered, *series[82:])})
    assert ResearchEngine(market, at).candidate("AMEN_BANK") == ResearchEngine(
        changed, at
    ).candidate("AMEN_BANK")


@pytest.mark.parametrize(("horizon", "support"), SUPPORT.items())
def test_layers_and_horizons(market, horizon, support):
    bar = market.bars["AMEN_BANK"][-1]
    e = ResearchEngine(market, bar.provenance.ingested_at)
    c = e.candidate("AMEN_BANK", horizon)
    a = c.assessment
    assert set(a.layers) == {f"L{i}" for i in range(1, 11)} and all(a.layers.values())
    assert a.horizon_support_status == support
    assert a.fundamental_state.status == "UNAVAILABLE" and a.event_context == ("UNAVAILABLE",)
    assert any(e.summary == "TUNINDEX" for e in a.missing_evidence)
    assert a.model_version == "v2.0.0-layers" and c.challenge_eligible
    assert (
        a.technical_state["ret_20s"].value
        == bar.close_tnd.value / market.bars["AMEN_BANK"][-21].close_tnd.value - 1
    )
    assert c.ten_pct_adv_shares.value == D(1200) and a.liquidity_status == "ONE_DAY"
    assert a.technical_state["challenge_breadth_pct"].value is not None
    assert a.execution_feasibility.automatic_submission_enabled is False
    if support.startswith("BLOCKED"):
        assert a.state == "INSUFFICIENT_EVIDENCE"


def test_held_and_nonchallenge(market):
    e = ResearchEngine(
        market,
        market.bars["ATB"][-1].provenance.ingested_at,
        ResearchContext(("ATB",), {"ATB": D(".12")}),
    )
    assert e.candidate("ATB").assessment.state == "HELD_POSITION_REVIEW"
    assert e.candidate("ATB").assessment.portfolio_suitability["issuer"] == "AT_OR_ABOVE_CAP"
    non = e.candidate("MNP")
    assert not non.challenge_eligible and non.assessment.state == "RESTRICTED"
    full = e.discover("FULL_BVMT_RESEARCH", "5_10")
    assert {c.assessment.instrument.instrument_id for c in full} == set(market.instruments)
    assert all(c.challenge_eligible for c in e.discover("TUNIS_BOURSE_CHALLENGE", "5_10"))
    assert bounded_risk_ratio_v2(D(3), D(4)) == D(".6")
