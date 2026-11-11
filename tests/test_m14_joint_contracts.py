"""Cross-route and mutation contracts; writes use disposable fixtures only."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bvmt import api
from bvmt.api import create_app
from bvmt.calendar import read_exchange_calendar
from bvmt.challenge_universe import is_in_challenge_universe
from bvmt.data import read_bars_csv
from bvmt.holding_period import evaluate_holding_periods
from bvmt.perf_cache import file_fingerprint, processed_datasets_fingerprint
from bvmt.sparse_generalization import prepare_pit_calendar_and_bars
from bvmt.sparse_research import _compute_event_evidence

pytest_plugins = ["test_api"]


def test_replay_never_moves_known_ingestion_before_publication():
    fixture = Path(__file__).resolve().parent / "fixtures"
    raw = read_bars_csv(fixture / "daily_bars.csv")
    _, replay = prepare_pit_calendar_and_bars(
        read_exchange_calendar(fixture / "exchange_calendar.csv"), raw
    )
    assert all(b.ingested_at >= b.published_at for b in replay if b.published_at is not None)
    assert [(b.published_at, b.ingested_at) for b in replay] == [
        (b.published_at, b.ingested_at) for b in raw
    ]


def test_unknown_catalog_never_becomes_scored_catalyst():
    evidence = _compute_event_evidence(
        "DELICE_HOLDING",
        frozenset({"DH", "DELICE_HOLDING"}),
        [],
        datetime(2026, 11, 10, 17, tzinfo=UTC),
    )
    assert evidence.events_count == 0
    assert evidence.positive_count == 0


def test_empty_challenge_observations_return_explicit_insufficient_evidence():
    fixture = Path(__file__).resolve().parent / "fixtures"
    result = evaluate_holding_periods(
        fixture / "daily_bars.csv",
        fixture / "exchange_calendar.csv",
        fixture / "instrument_master.csv",
        universe="TUNIS_BOURSE_CHALLENGE",
    )
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.horizons == []
    assert result.usable_research_count == 0
    assert len(result.membership_accounting) == 42


def test_explanation_cache_includes_equity_and_frozen_config(service, monkeypatch):
    state = service.load_state()
    api.invalidate_all_caches()
    with patch.object(
        api, "evaluate_sparse_market_research", wraps=api.evaluate_sparse_market_research
    ) as evaluate:
        api._sparse_research_explanations(service, state)
        api._sparse_research_explanations(service, state)
        assert evaluate.call_count == 1
        state.ledger.settled_cash_tnd += Decimal("100")
        api._sparse_research_explanations(service, state)
        assert evaluate.call_count == 2
        original = api.file_fingerprint
        monkeypatch.setattr(
            api,
            "file_fingerprint",
            lambda p: (
                ("changed-config",) if p == Path("configs/sparse_research_v1.json") else original(p)
            ),
        )
        api._sparse_research_explanations(service, state)
        assert evaluate.call_count == 3


def test_explicit_challenge_scope_in_synthetic_mode(service):
    with TestClient(create_app(service)) as client:
        result = client.get("/api/rankings?mode=SYNTHETIC_DEMO&universe=TUNIS_BOURSE_CHALLENGE")
    assert result.status_code == 200
    assert all(
        is_in_challenge_universe(r["instrument_id"], symbol=r["symbol"])
        for r in result.json()["rankings"]
        if r["rank"] is not None
    )


def test_same_metadata_source_mutation_invalidates_all_fingerprints(tmp_path):
    directory = tmp_path / "dataset"
    directory.mkdir()
    source = directory / "daily_bars.canonical.csv"
    source.write_bytes(b"a" * 600000)
    stat = source.stat()
    first = file_fingerprint(source)
    discovery = processed_datasets_fingerprint(tmp_path)
    source.write_bytes(b"b" * 600000)
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert file_fingerprint(source) != first
    assert processed_datasets_fingerprint(tmp_path) != discovery


@pytest.mark.parametrize(
    "route",
    [
        "/api/rankings",
        "/api/trade-plans",
        "/api/trading-intelligence",
        "/api/research?include_strategy_comparison=false",
    ],
)
def test_real_account_routes_cannot_allocate_nonmembers(service, route):
    with TestClient(create_app(service)) as client:
        response = client.get(route)
    assert response.status_code == 200
    payload = response.json()
    for row in payload.get("rankings", []):
        if row["rank"] is not None:
            assert is_in_challenge_universe(row["instrument_id"], symbol=row["symbol"])
    for row in payload.get("plans", []):
        if not is_in_challenge_universe(row["instrument_id"], symbol=row["symbol"]):
            assert row["suggested_max_shares"] == 0
    for group in ("swing_candidates", "position_candidates"):
        for row in payload.get(group, []):
            if not is_in_challenge_universe(row["instrument_id"], symbol=row["symbol"]):
                assert row["quantity_limit"] == 0
