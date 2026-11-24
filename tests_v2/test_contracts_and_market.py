import csv
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from bvmt_v2 import contracts
from bvmt_v2.contracts import ProvenanceValue, money, pv
from bvmt_v2.market_data import REGISTRY, load_market

AT = datetime(2026, 11, 24, tzinfo=UTC)
DOMAINS = """Instrument PriceProvenance MarketObservation ResearchEvidence StockAssessment InvestmentThesis OpportunityCandidate PortfolioSnapshot Holding Transaction PendingOrder RiskAssessment PositionDecision ExecutionFeasibility ManualTradeScenario ModelExperiment SignalJournal PerformanceAttribution""".split()


@pytest.mark.parametrize("name", DOMAINS)
def test_domain_contract_requires_typed_fields_and_forbids_extras(name):
    model = getattr(contracts, name)
    assert model.model_json_schema()["additionalProperties"] is False
    with pytest.raises(ValidationError):
        model.model_validate({"unknown": 1})


def test_decimal_roundtrip_and_half_up():
    raw = pv("12.3455", "TND", "OBSERVED", "fixture", AT, observed=AT)
    assert raw.value == Decimal("12.346")
    assert raw.model_dump(mode="json")["value"] == "12.346"
    assert money(Decimal("-0.0005")) == Decimal("-0.001")
    assert ProvenanceValue.model_validate_json(raw.model_dump_json()) == raw
    with pytest.raises(ValidationError):
        ProvenanceValue.model_validate_json(raw.model_dump_json().replace('"12.346"', "12.346"))
    with pytest.raises(ValidationError):
        pv(None, "PCT", "UNAVAILABLE", "fixture", AT)
    with pytest.raises(ValidationError):
        pv("0", "PCT", "UNAVAILABLE", "fixture", AT, "Missing")
    with pytest.raises(ValidationError):
        pv(None, "TND", "OBSERVED", "fixture", AT)
    with pytest.raises(ValidationError):
        pv("1", "TND", "OBSERVED", "fixture", AT.replace(tzinfo=None))
    with pytest.raises(ValueError):
        pv(float("inf"), "TND", "SIMULATED", "fixture", AT)
    with pytest.raises(ValidationError):
        contracts.PendingOrder(
            order_id="x",
            instrument_id="x",
            side="BUY",
            remaining_shares=1,
            submitted_at=AT,
            status="pending",
            limit_price_tnd=pv("2", "SHARES", "OBSERVED", "fixture", AT),
        )


def _write(path: Path, rows: list[dict[str, str]]):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def csv_dir() -> Iterator[Path]:
    path = Path(__file__).resolve().parent / f"csv-{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        for f in path.iterdir():
            f.unlink()
        path.rmdir()


def test_equity_whitelist_alias_dates_and_source_provenance(csv_dir):
    tmp_path = csv_dir
    day1, day2 = "2026-01-02", "2026-01-05"
    key, alias = "POULINA_GROUP_HOLDING", "POULINA_GP_HOLDING"
    master = {
        "instrument_id": key,
        "isin": "TN0005700018",
        "symbol": key,
        "listed_from": day1,
        "asset_type": "equity",
    }
    row = {
        "instrument_id": key,
        "session_date": day1,
        "open": "1",
        "high": "2",
        "low": "1",
        "close": "2",
        "turnover_tnd": "200",
        "volume_shares": "100",
        "ingested_at": AT.isoformat(),
        "published_at": "",
        "status": "traded",
        "source_id": "fixture_csv",
    }
    master_path = _write(
        tmp_path / "instruments.csv",
        [
            master,
            dict(master, instrument_id=alias, listed_from=day2),
            dict(master, instrument_id="BOND", asset_type="bond"),
        ],
    )
    bars_path = _write(
        tmp_path / "bars.csv",
        [
            row,
            dict(row, instrument_id=alias),
            dict(row, instrument_id=alias, session_date=day2),
            dict(row, instrument_id="BOND"),
            dict(row, instrument_id="RIGHT"),
        ],
    )
    cal = _write(
        tmp_path / "calendar.csv", [{"session_date": d, "is_open": "true"} for d in (day1, day2)]
    )
    m = load_market(bars_path, master_path, cal, validated_at=AT)
    assert m.rejected_non_equity_count == 2
    assert list(m.instruments) == [key] and m.resolve("PGH") == key
    assert m.instruments[key].challenge_member and str(m.instruments[key].listed_from) == day1
    assert tuple(b.session_date for b in m.bars[key]) == m.sessions
    p = m.bars[key][0].provenance
    assert p.source_publication_time is None and p.retrieved_at is None
    assert p.first_observed_at == p.ingested_at == p.validated_at == AT
    assert p.data_quality_status == "EOD_UNVERIFIED_PUB_TIME"
    assert p.historical_eod_close_tnd.status == "OBSERVED" and len(p.source_hash) == 64
    assert (
        p.current_executable_quote_tnd.status == "UNAVAILABLE"
        and p.current_executable_quote_tnd.value is None
    )


def test_official_archive_registry_and_rows():
    m = load_market()
    assert len(REGISTRY) == sum(i.challenge_member for i in m.instruments.values()) == 42
    assert len(m.instruments) == 75 and len(m.sessions) == 202
    assert sum(map(len, m.bars.values())) == 15080
    assert len(m.bars[m.resolve("TN0005700018")]) == 202
    assert m.instruments[m.resolve("TRE")].market_mode == "Fixing"
    for symbol in ("MNP", "SCN"):
        assert m.instruments[m.resolve(symbol)].order_entry_eligibility == "NOT_IN_UNIVERSE"
    assert all(
        b.provenance.source_publication_time is None for bars in m.bars.values() for b in bars
    )
