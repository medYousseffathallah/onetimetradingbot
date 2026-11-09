"""Canonical account synchronization service for Tunis Bourse Challenge (Milestone 10).

Unifies all ingestion channels:
1. PRIMARY: Chrome Browser Companion extension (Manifest V3, activeTab).
2. SECONDARY: Manual paste & CSV import.
3. FALLBACK: Playwright automated browser collector.

Enforces:
- Exact Decimal financial values (quantized to 0.001 TND).
- No phantom zeros: missing values remain None.
- Complete balance validation: cash + sum(holdings.market_value) == total_equity.
- Duplicate detection: identical snapshots do not duplicate trades.
- Immutable snapshot persistence outside Git (`data/portfolio/snapshots/`).
- Separation of capture, reconciliation preview, and explicit confirmation.
- Preservation of confirmed ledger on failed ingestion attempts.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from bvmt.browser import (
    BrowserHoldingItem,
    BrowserPendingOrderItem,
    BrowserTransactionItem,
    CompetitionPortfolioDOMSnapshot,
    save_browser_snapshot,
)
from bvmt.portfolio_service import PortfolioStateService

MILLIME = Decimal("0.001")
DEFAULT_BALANCE_TOLERANCE_TND = Decimal("0.050")
DEFAULT_PAIRING_TOKEN_PATH = Path("data/portfolio/pairing_token.txt")
DEFAULT_SNAPSHOTS_DIR = Path("data/portfolio/snapshots")

SyncSource = Literal[
    "CHROME_EXTENSION",
    "MANUAL_PASTE",
    "CSV_IMPORT",
    "PLAYWRIGHT_WORKER",
    "SNAPSHOT_FILE",
]

ValidationStatus = Literal[
    "VALID",
    "BALANCE_MISMATCH",
    "DUPLICATE_SNAPSHOT",
    "MALFORMED_ROW",
    "AUTHENTICATION_REQUIRED",
    "EMPTY_OBSERVATION",
]

ConfirmationStatus = Literal["PENDING", "CONFIRMED", "REJECTED"]


def quantize_tnd(value: Decimal | str | int | float) -> Decimal:
    """Quantize to 0.001 TND with round-half-up."""
    try:
        dec = (
            value
            if isinstance(value, Decimal)
            else Decimal(str(value).strip().replace(" ", "").replace(",", "."))
        )
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid TND monetary value: '{value}'") from exc
    if not dec.is_finite():
        raise ValueError(f"Non-finite monetary value: '{value}'")
    return dec.quantize(MILLIME, rounding=ROUND_HALF_UP)


def normalize_instrument_id(symbol: str) -> str:
    """Normalize raw ticker or French name into safe uppercase ID."""
    return re.sub(r"[^A-Z0-9._-]+", "_", symbol.strip().upper()).strip("_")


@dataclass(frozen=True)
class NormalizedHoldingObservation:
    """Normalized holding extracted from competition table."""

    symbol: str
    instrument_id: str
    quantity: int
    acquisition_price_tnd: Decimal
    latest_price_tnd: Decimal
    market_value_tnd: Decimal
    acquisition_amount_tnd: Decimal | None = None
    gain_tnd: Decimal | None = None
    gain_pct: Decimal | None = None
    displayed_name: str | None = None
    isin: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "instrument_id": self.instrument_id,
            "quantity": self.quantity,
            "acquisition_price_tnd": str(self.acquisition_price_tnd),
            "latest_price_tnd": str(self.latest_price_tnd),
            "market_value_tnd": str(self.market_value_tnd),
            "acquisition_amount_tnd": (
                str(self.acquisition_amount_tnd)
                if self.acquisition_amount_tnd is not None
                else None
            ),
            "gain_tnd": str(self.gain_tnd) if self.gain_tnd is not None else None,
            "gain_pct": str(self.gain_pct) if self.gain_pct is not None else None,
            "displayed_name": self.displayed_name,
            "isin": self.isin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedHoldingObservation:
        sym = str(data["symbol"]).strip().upper()
        inst_id = str(data.get("instrument_id") or normalize_instrument_id(sym))
        qty = int(str(data["quantity"]))
        acq_px = quantize_tnd(data["acquisition_price_tnd"])
        lat_px = quantize_tnd(data.get("latest_price_tnd", acq_px))
        mkt_val = (
            quantize_tnd(data["market_value_tnd"])
            if "market_value_tnd" in data and data["market_value_tnd"] is not None
            else quantize_tnd(Decimal(qty) * lat_px)
        )
        acq_amt = (
            quantize_tnd(data["acquisition_amount_tnd"])
            if data.get("acquisition_amount_tnd")
            else quantize_tnd(Decimal(qty) * acq_px)
        )
        gain_val = (
            quantize_tnd(data["gain_tnd"])
            if data.get("gain_tnd")
            else quantize_tnd(mkt_val - acq_amt)
        )
        gain_pc = (
            Decimal(str(data["gain_pct"]))
            if data.get("gain_pct") is not None
            else (
                quantize_tnd((gain_val / acq_amt) * Decimal("100"))
                if acq_amt > 0
                else Decimal("0.00")
            )
        )

        return cls(
            symbol=sym,
            instrument_id=inst_id,
            quantity=qty,
            acquisition_price_tnd=acq_px,
            latest_price_tnd=lat_px,
            market_value_tnd=mkt_val,
            acquisition_amount_tnd=acq_amt,
            gain_tnd=gain_val,
            gain_pct=gain_pc,
            displayed_name=str(data.get("displayed_name") or data.get("displayed_symbol") or sym),
            isin=str(data.get("isin")) if data.get("isin") else None,
        )


@dataclass(frozen=True)
class NormalizedTransactionObservation:
    """Historical transaction record extracted from competition display_histo.aspx."""

    transaction_id: str
    order_id: str
    symbol: str
    instrument_id: str
    side: Literal["BUY", "SELL"]
    filled_shares: int
    execution_price_tnd: Decimal
    fee_tnd: Decimal
    executed_at: str  # ISO 8601 UTC

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "filled_shares": self.filled_shares,
            "execution_price_tnd": str(self.execution_price_tnd),
            "fee_tnd": str(self.fee_tnd),
            "executed_at": self.executed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedTransactionObservation:
        side_val = str(data["side"]).upper()
        if side_val not in {"BUY", "SELL"}:
            raise ValueError(f"Transaction side must be BUY or SELL, got: {side_val}")
        return cls(
            transaction_id=str(data["transaction_id"]),
            order_id=str(data.get("order_id", data["transaction_id"])),
            symbol=str(data["symbol"]).strip().upper(),
            instrument_id=str(
                data.get("instrument_id") or normalize_instrument_id(str(data["symbol"]))
            ),
            side=side_val,  # type: ignore[arg-type]
            filled_shares=int(str(data["filled_shares"])),
            execution_price_tnd=quantize_tnd(data["execution_price_tnd"]),
            fee_tnd=quantize_tnd(data.get("fee_tnd", "0.000")),
            executed_at=str(data["executed_at"]),
        )


@dataclass(frozen=True)
class NormalizedOrderObservation:
    """Pending order observation extracted from competition order book."""

    order_id: str
    symbol: str
    instrument_id: str
    side: Literal["BUY", "SELL"]
    requested_shares: int
    filled_shares: int
    remaining_shares: int
    limit_price_tnd: Decimal
    status: str
    submitted_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "requested_shares": self.requested_shares,
            "filled_shares": self.filled_shares,
            "remaining_shares": self.remaining_shares,
            "limit_price_tnd": str(self.limit_price_tnd),
            "status": self.status,
            "submitted_at": self.submitted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedOrderObservation:
        return cls(
            order_id=str(data["order_id"]),
            symbol=str(data["symbol"]).strip().upper(),
            instrument_id=str(
                data.get("instrument_id") or normalize_instrument_id(str(data["symbol"]))
            ),
            side=str(data["side"]).upper(),  # type: ignore[arg-type]
            requested_shares=int(str(data["requested_shares"])),
            filled_shares=int(str(data.get("filled_shares", 0))),
            remaining_shares=int(str(data.get("remaining_shares", data["requested_shares"]))),
            limit_price_tnd=quantize_tnd(data["limit_price_tnd"]),
            status=str(data.get("status", "PENDING")),
            submitted_at=str(data["submitted_at"]),
        )


@dataclass(frozen=True)
class NormalizedAccountObservation:
    """Canonical normalized account observation across all capture channels."""

    source: SyncSource
    capture_timestamp: str  # ISO 8601 UTC
    snapshot_id: str
    account_equity: Decimal
    available_cash: Decimal
    holdings: list[NormalizedHoldingObservation] = field(default_factory=list)
    pending_orders: list[NormalizedOrderObservation] = field(default_factory=list)
    transactions: list[NormalizedTransactionObservation] = field(default_factory=list)
    competition_ranking: int | None = None
    total_participants: int | None = None
    displayed_overall_performance_pct: Decimal | None = None
    source_page_type: str = "displayp.aspx"
    challenge_period_text: str = ""
    raw_payload_hash: str | None = None

    def compute_content_hash(self) -> str:
        """Deterministic fingerprint of balance and holdings to detect duplicates."""
        h = hashlib.sha256()
        h.update(str(self.account_equity).encode("utf-8"))
        h.update(b"|")
        h.update(str(self.available_cash).encode("utf-8"))
        for hold in sorted(self.holdings, key=lambda x: x.symbol):
            h.update(
                f"|{hold.symbol}:{hold.quantity}:{hold.acquisition_price_tnd}:{hold.latest_price_tnd}".encode()
            )
        return h.hexdigest()

    def to_dom_snapshot(self) -> CompetitionPortfolioDOMSnapshot:
        """Convert normalized observation into canonical DOM snapshot."""
        dt = datetime.fromisoformat(self.capture_timestamp.replace("Z", "+00:00"))
        holdings_tuples = tuple(
            BrowserHoldingItem(
                symbol=h.symbol,
                quantity=h.quantity,
                acquisition_price_tnd=h.acquisition_price_tnd,
                acquisition_amount_tnd=h.acquisition_amount_tnd
                or quantize_tnd(Decimal(h.quantity) * h.acquisition_price_tnd),
                latest_price_tnd=h.latest_price_tnd,
                market_value_tnd=h.market_value_tnd,
                gain_tnd=h.gain_tnd
                or quantize_tnd(h.market_value_tnd - (h.acquisition_amount_tnd or Decimal(0))),
                gain_pct=h.gain_pct or Decimal("0.00"),
                displayed_symbol=h.symbol,
                displayed_identifier=h.displayed_name,
            )
            for h in self.holdings
        )
        tx_tuples = tuple(
            BrowserTransactionItem(
                transaction_id=t.transaction_id,
                order_id=t.order_id,
                symbol=t.symbol,
                instrument_id=t.instrument_id,
                side=t.side,
                filled_shares=t.filled_shares,
                execution_price_tnd=t.execution_price_tnd,
                fee_tnd=t.fee_tnd,
                executed_at=t.executed_at,
            )
            for t in self.transactions
        )
        po_tuples = tuple(
            BrowserPendingOrderItem(
                order_id=p.order_id,
                symbol=p.symbol,
                instrument_id=p.instrument_id,
                side=p.side,
                requested_shares=p.requested_shares,
                filled_shares=p.filled_shares,
                remaining_shares=p.remaining_shares,
                limit_price_tnd=p.limit_price_tnd,
                status=p.status,
                submitted_at=p.submitted_at,
            )
            for p in self.pending_orders
        )
        holdings_val = sum((h.market_value_tnd for h in self.holdings), Decimal("0.000"))
        gap = (self.available_cash + holdings_val - self.account_equity).copy_abs()
        is_rec = gap <= DEFAULT_BALANCE_TOLERANCE_TND

        return CompetitionPortfolioDOMSnapshot(
            source_url=f"bvmt-sync://{self.source.lower()}/{self.source_page_type}",
            retrieved_at=dt,
            portfolio_total_tnd=self.account_equity,
            available_cash_tnd=self.available_cash,
            holdings_market_value_tnd=holdings_val,
            holdings=holdings_tuples,
            competition_rank=self.competition_ranking,
            total_participants=self.total_participants,
            displayed_overall_performance_pct=self.displayed_overall_performance_pct,
            is_reconciled=is_rec,
            reconciliation_gap_tnd=gap,
            challenge_period_text=self.challenge_period_text,
            movements_page_captured=bool(self.transactions or self.pending_orders),
            movements_source_url=f"bvmt-sync://{self.source.lower()}/movements"
            if self.transactions
            else None,
            transactions=tx_tuples,
            pending_orders=po_tuples,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "capture_timestamp": self.capture_timestamp,
            "snapshot_id": self.snapshot_id,
            "account_equity": str(self.account_equity),
            "available_cash": str(self.available_cash),
            "holdings": [h.to_dict() for h in self.holdings],
            "pending_orders": [p.to_dict() for p in self.pending_orders],
            "transactions": [t.to_dict() for t in self.transactions],
            "competition_ranking": self.competition_ranking,
            "total_participants": self.total_participants,
            "displayed_overall_performance_pct": (
                str(self.displayed_overall_performance_pct)
                if self.displayed_overall_performance_pct is not None
                else None
            ),
            "source_page_type": self.source_page_type,
            "challenge_period_text": self.challenge_period_text,
            "raw_payload_hash": self.raw_payload_hash or self.compute_content_hash(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedAccountObservation:
        return cls(
            source=data.get("source", "MANUAL_PASTE"),
            capture_timestamp=str(data.get("capture_timestamp") or datetime.now(UTC).isoformat()),
            snapshot_id=str(
                data.get("snapshot_id") or f"snap_{int(datetime.now(UTC).timestamp())}"
            ),
            account_equity=quantize_tnd(data["account_equity"]),
            available_cash=quantize_tnd(data["available_cash"]),
            holdings=[
                NormalizedHoldingObservation.from_dict(h)
                for h in data.get("holdings", [])
                if isinstance(h, dict)
            ],
            pending_orders=[
                NormalizedOrderObservation.from_dict(p)
                for p in data.get("pending_orders", [])
                if isinstance(p, dict)
            ],
            transactions=[
                NormalizedTransactionObservation.from_dict(t)
                for t in data.get("transactions", [])
                if isinstance(t, dict)
            ],
            competition_ranking=int(data["competition_ranking"])
            if data.get("competition_ranking") is not None
            else None,
            total_participants=int(data["total_participants"])
            if data.get("total_participants") is not None
            else None,
            displayed_overall_performance_pct=(
                Decimal(str(data["displayed_overall_performance_pct"]))
                if data.get("displayed_overall_performance_pct") is not None
                else None
            ),
            source_page_type=str(data.get("source_page_type", "displayp.aspx")),
            challenge_period_text=str(data.get("challenge_period_text", "")),
            raw_payload_hash=str(data["raw_payload_hash"])
            if data.get("raw_payload_hash")
            else None,
        )


@dataclass(frozen=True)
class IngestionResult:
    """Result of canonical observation ingestion."""

    success: bool
    validation_status: ValidationStatus
    snapshot_id: str
    saved_snapshot_path: Path | None
    observation: NormalizedAccountObservation
    reconciliation_gap_tnd: Decimal
    is_duplicate: bool
    error_messages: list[str] = field(default_factory=list)
    warning_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "validation_status": self.validation_status,
            "snapshot_id": self.snapshot_id,
            "saved_snapshot_path": self.saved_snapshot_path.as_posix()
            if self.saved_snapshot_path
            else None,
            "reconciliation_gap_tnd": str(self.reconciliation_gap_tnd),
            "is_duplicate": self.is_duplicate,
            "error_messages": self.error_messages,
            "warning_messages": self.warning_messages,
            "observation": self.observation.to_dict(),
        }


def get_or_create_pairing_token(token_file: Path = DEFAULT_PAIRING_TOKEN_PATH) -> str:
    """Retrieve or generate local pairing token for Chrome extension authentication."""
    token_file.parent.mkdir(parents=True, exist_ok=True)
    if token_file.is_file():
        token = token_file.read_text(encoding="utf-8").strip()
        if token and len(token) >= 32:
            return token
    new_token = secrets.token_hex(24)  # 48 chars hex
    token_file.write_text(new_token, encoding="utf-8")
    return new_token


def verify_pairing_token(token: str | None, token_file: Path = DEFAULT_PAIRING_TOKEN_PATH) -> bool:
    """Verify incoming extension request against stored pairing token."""
    if not token or not token.strip():
        return False
    expected = get_or_create_pairing_token(token_file)
    return secrets.compare_digest(token.strip(), expected)


class CanonicalSyncService:
    """Single central authority for account observation ingestion, validation, and persistence."""

    def __init__(
        self,
        *,
        portfolio_service: PortfolioStateService | None = None,
        snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
        pairing_token_path: Path = DEFAULT_PAIRING_TOKEN_PATH,
        balance_tolerance_tnd: Decimal = DEFAULT_BALANCE_TOLERANCE_TND,
    ) -> None:
        self.portfolio_service = portfolio_service or PortfolioStateService(
            portfolio_mode="REAL_COMPETITION"
        )
        self.snapshots_dir = snapshots_dir
        self.pairing_token_path = pairing_token_path
        self.balance_tolerance_tnd = balance_tolerance_tnd

    def get_pairing_token(self) -> str:
        return get_or_create_pairing_token(self.pairing_token_path)

    def verify_pairing(self, token: str | None) -> bool:
        return verify_pairing_token(token, self.pairing_token_path)

    def check_duplicate(self, observation: NormalizedAccountObservation) -> bool:
        """Check if an identical snapshot was already confirmed or captured recently."""
        state = self.portfolio_service.load_state()
        if (
            state.account_snapshot is not None
            and state.account_snapshot.portfolio_total_tnd == observation.account_equity
            and state.account_snapshot.available_cash_tnd == observation.available_cash
            and len(state.account_snapshot.holdings) == len(observation.holdings)
        ):
            return True

        content_hash = observation.compute_content_hash()

        # Check existing snapshot files
        if self.snapshots_dir.is_dir():
            for snap_file in sorted(self.snapshots_dir.glob("sync_*.json"), reverse=True)[:5]:
                try:
                    data = json.loads(snap_file.read_text(encoding="utf-8"))
                    cand = CompetitionPortfolioDOMSnapshot.from_dict(data)
                    # Compare cash, equity, holdings count, and symbols
                    cand_hash = hashlib.sha256()
                    cand_hash.update(str(cand.portfolio_total_tnd).encode())
                    cand_hash.update(b"|")
                    cand_hash.update(str(cand.available_cash_tnd).encode())
                    for hold in sorted(cand.holdings, key=lambda x: x.symbol):
                        cand_hash.update(
                            f"|{hold.symbol}:{hold.quantity}:{hold.acquisition_price_tnd}:{hold.latest_price_tnd}".encode()
                        )
                    if cand_hash.hexdigest() == content_hash:
                        return True
                except Exception:
                    continue
        return False

    def ingest_observation(
        self,
        observation: NormalizedAccountObservation,
        *,
        allow_duplicate: bool = False,
    ) -> IngestionResult:
        """Validate, persist immutable snapshot, and prepare reconciliation preview."""
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Basic sanity checks
        if observation.account_equity <= Decimal("0.000"):
            errors.append(
                f"Account equity must be strictly positive, got: {observation.account_equity} TND"
            )
        if observation.available_cash < Decimal("0.000"):
            errors.append(
                f"Available cash cannot be negative, got: {observation.available_cash} TND"
            )

        # 2. Balance Validation: Cash + Sum(holdings market value) == Equity
        holdings_value = sum((h.market_value_tnd for h in observation.holdings), Decimal("0.000"))
        computed_total = observation.available_cash + holdings_value
        reconciliation_gap = (computed_total - observation.account_equity).copy_abs()

        if reconciliation_gap > self.balance_tolerance_tnd:
            errors.append(
                f"Balance mismatch: Cash ({observation.available_cash} TND) + Holdings ({holdings_value} TND) = "
                f"{computed_total} TND, which differs from reported total {observation.account_equity} TND "
                f"by {reconciliation_gap} TND (tolerance: {self.balance_tolerance_tnd} TND)."
            )

        # 3. Duplicate check
        is_dup = self.check_duplicate(observation)
        if is_dup and not allow_duplicate:
            warnings.append("An identical portfolio snapshot is already captured on disk.")

        if errors:
            status: ValidationStatus = (
                "BALANCE_MISMATCH" if "Balance mismatch" in errors[0] else "MALFORMED_ROW"
            )
            return IngestionResult(
                success=False,
                validation_status=status,
                snapshot_id=observation.snapshot_id,
                saved_snapshot_path=None,
                observation=observation,
                reconciliation_gap_tnd=reconciliation_gap,
                is_duplicate=is_dup,
                error_messages=errors,
                warning_messages=warnings,
            )

        # 4. Transform to canonical DOM snapshot and save immutably
        dom_snap = observation.to_dom_snapshot()
        saved_path = save_browser_snapshot(dom_snap, self.snapshots_dir)

        return IngestionResult(
            success=True,
            validation_status="VALID",
            snapshot_id=observation.snapshot_id,
            saved_snapshot_path=saved_path,
            observation=observation,
            reconciliation_gap_tnd=reconciliation_gap,
            is_duplicate=is_dup,
            error_messages=[],
            warning_messages=warnings,
        )
