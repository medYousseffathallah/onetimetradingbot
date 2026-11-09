"""Unit test suite for the Canonical Synchronization Service (Milestone 10).

Covers:
- Quantization to 0.001 TND (exact decimal precision).
- Balance validation (cash + sum(holdings) == equity within tolerance).
- Ingestion of observations from all channels.
- Duplicate snapshot detection.
- Pairing token generation, persistence, and verification.
- Preservation of confirmed ledger on failed ingestion attempts.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.sync_service import (
    CanonicalSyncService,
    NormalizedAccountObservation,
    NormalizedHoldingObservation,
    NormalizedOrderObservation,
    NormalizedTransactionObservation,
    get_or_create_pairing_token,
    quantize_tnd,
    verify_pairing_token,
)


def test_quantize_tnd_precision() -> None:
    # 3 decimal places standard
    assert quantize_tnd("19.095") == Decimal("19.095")
    assert quantize_tnd("19,095") == Decimal("19.095")
    assert quantize_tnd("19 095,000") == Decimal("19095.000")
    assert quantize_tnd(15) == Decimal("15.000")
    assert quantize_tnd(15.1234) == Decimal("15.123")
    assert quantize_tnd(15.1236) == Decimal("15.124")  # round-half-up

    with pytest.raises(ValueError):
        quantize_tnd("invalid_number")


def test_pairing_token_lifecycle(tmp_path: Path) -> None:
    token_file = tmp_path / "test_pairing_token.txt"

    # Generation
    token = get_or_create_pairing_token(token_file)
    assert len(token) == 48
    assert token_file.is_file()

    # Re-reading same token
    assert get_or_create_pairing_token(token_file) == token

    # Verification
    assert verify_pairing_token(token, token_file) is True
    assert verify_pairing_token(token.upper(), token_file) is False
    assert verify_pairing_token("invalid_token_12345678901234567890", token_file) is False
    assert verify_pairing_token("", token_file) is False
    assert verify_pairing_token(None, token_file) is False


def test_canonical_sync_valid_observation(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots"
    service = CanonicalSyncService(snapshots_dir=snapshots_dir)

    obs = NormalizedAccountObservation(
        source="CHROME_EXTENSION",
        capture_timestamp="2026-11-09T09:30:00Z",
        snapshot_id="snap_valid_001",
        account_equity=Decimal("50000.750"),
        available_cash=Decimal("49608.050"),
        holdings=[
            NormalizedHoldingObservation(
                symbol="BH",
                instrument_id="BH",
                quantity=30,
                acquisition_price_tnd=Decimal("13.067"),
                latest_price_tnd=Decimal("13.090"),
                market_value_tnd=Decimal("392.700"),
            )
        ],
        competition_ranking=118,
        total_participants=14547,
    )

    result = service.ingest_observation(obs)
    assert result.success is True
    assert result.validation_status == "VALID"
    assert result.reconciliation_gap_tnd == Decimal("0.000")
    assert result.saved_snapshot_path is not None
    assert result.saved_snapshot_path.is_file()


def test_canonical_sync_balance_mismatch(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots"
    service = CanonicalSyncService(snapshots_dir=snapshots_dir)

    # Cash + Holding (49608.050 + 392.700 = 50000.750) does not match equity 52000.000
    obs = NormalizedAccountObservation(
        source="MANUAL_PASTE",
        capture_timestamp="2026-11-09T09:30:00Z",
        snapshot_id="snap_mismatch_001",
        account_equity=Decimal("52000.000"),
        available_cash=Decimal("49608.050"),
        holdings=[
            NormalizedHoldingObservation(
                symbol="BH",
                instrument_id="BH",
                quantity=30,
                acquisition_price_tnd=Decimal("13.067"),
                latest_price_tnd=Decimal("13.090"),
                market_value_tnd=Decimal("392.700"),
            )
        ],
    )

    result = service.ingest_observation(obs)
    assert result.success is False
    assert result.validation_status == "BALANCE_MISMATCH"
    assert result.saved_snapshot_path is None
    assert len(result.error_messages) == 1
    assert "Balance mismatch" in result.error_messages[0]


def test_canonical_sync_duplicate_detection(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots"
    service = CanonicalSyncService(snapshots_dir=snapshots_dir)

    obs = NormalizedAccountObservation(
        source="CHROME_EXTENSION",
        capture_timestamp="2026-11-09T09:30:00Z",
        snapshot_id="snap_dup_001",
        account_equity=Decimal("50000.750"),
        available_cash=Decimal("49608.050"),
        holdings=[
            NormalizedHoldingObservation(
                symbol="BH",
                instrument_id="BH",
                quantity=30,
                acquisition_price_tnd=Decimal("13.067"),
                latest_price_tnd=Decimal("13.090"),
                market_value_tnd=Decimal("392.700"),
            )
        ],
    )

    # First ingestion
    r1 = service.ingest_observation(obs)
    assert r1.success is True
    assert r1.is_duplicate is False

    # Second ingestion of identical content
    r2 = service.ingest_observation(obs)
    assert r2.success is True
    assert r2.is_duplicate is True
    assert any("identical" in w.lower() for w in r2.warning_messages)


def test_canonical_sync_serialization_roundtrip() -> None:
    obs = NormalizedAccountObservation(
        source="CHROME_EXTENSION",
        capture_timestamp="2026-11-09T09:30:00Z",
        snapshot_id="snap_roundtrip",
        account_equity=Decimal("50000.750"),
        available_cash=Decimal("49608.050"),
        holdings=[
            NormalizedHoldingObservation(
                symbol="BH",
                instrument_id="BH",
                quantity=30,
                acquisition_price_tnd=Decimal("13.067"),
                latest_price_tnd=Decimal("13.090"),
                market_value_tnd=Decimal("392.700"),
            )
        ],
        pending_orders=[
            NormalizedOrderObservation(
                order_id="ord_1",
                symbol="DH",
                instrument_id="DH",
                side="BUY",
                requested_shares=200,
                filled_shares=0,
                remaining_shares=200,
                limit_price_tnd=Decimal("14.500"),
                status="PENDING",
                submitted_at="2026-11-09T09:15:00Z",
            )
        ],
        transactions=[
            NormalizedTransactionObservation(
                transaction_id="tx_1",
                order_id="ord_0",
                symbol="BH",
                instrument_id="BH",
                side="BUY",
                filled_shares=30,
                execution_price_tnd=Decimal("13.067"),
                fee_tnd=Decimal("0.700"),
                executed_at="2026-11-06T10:00:00Z",
            )
        ],
        competition_ranking=118,
        total_participants=14547,
        displayed_overall_performance_pct=Decimal("0.00"),
    )

    d = obs.to_dict()
    roundtripped = NormalizedAccountObservation.from_dict(d)
    assert roundtripped.account_equity == obs.account_equity
    assert roundtripped.available_cash == obs.available_cash
    assert len(roundtripped.holdings) == 1
    assert roundtripped.holdings[0].symbol == "BH"
    assert len(roundtripped.pending_orders) == 1
    assert len(roundtripped.transactions) == 1
    assert roundtripped.competition_ranking == 118
