"""Secure, local-first, read-only Playwright browser collector and DOM parser for Tunis Bourse Challenge.

No remote browser service, no cloud credential storage, no automated login or password extraction.
Strictly read-only: only accesses displayp.aspx (portfolio) and display_histo.aspx (movements).
Never accesses bysell.aspx or submits orders.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_CHALLENGE_URL = "https://www.tunisbourse-challenge.com/displayp.aspx"
DEFAULT_MOVEMENTS_URL = "https://www.tunisbourse-challenge.com/display_histo.aspx"
DEFAULT_LOGIN_URL = "https://www.tunisbourse-challenge.com/"
DEFAULT_ROUNDING_TOLERANCE_TND = Decimal("0.05")
STANDARD_FEE_RATE = Decimal("0.005")

ALLOWED_CHALLENGE_HOSTS = {"www.tunisbourse-challenge.com", "tunisbourse-challenge.com"}
FORBIDDEN_TRADING_PATHS = ("bysell.aspx", "acheter", "vendre")


class BrowserCollectorError(Exception):
    """Base exception for browser collection and DOM parsing errors."""


class AuthenticationExpiredError(BrowserCollectorError):
    """Raised when the session is expired or the page redirects to login."""


class LayoutChangedError(BrowserCollectorError):
    """Raised when the expected HTML table structure or fields cannot be found."""


class BalanceMismatchError(BrowserCollectorError):
    """Raised when cash + holdings market value does not match reported total."""


def validate_readonly_challenge_url(url: str) -> str:
    """Ensure browser collector never navigates to order-entry or external URLs."""
    parsed = urlparse(url.strip())
    if (
        parsed.scheme not in {"https", "http"}
        or parsed.netloc.lower() not in ALLOWED_CHALLENGE_HOSTS
    ):
        raise BrowserCollectorError(
            f"Untrusted or non-competition URL rejected: '{url}'. Only {sorted(ALLOWED_CHALLENGE_HOSTS)} allowed."
        )
    path_lower = parsed.path.lower()
    for forbidden in FORBIDDEN_TRADING_PATHS:
        if forbidden in path_lower:
            raise BrowserCollectorError(
                f"Forbidden trading endpoint rejected: '{url}'. Browser collector is strictly read-only."
            )
    return url.strip()


def _normalize_instrument_id(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9._-]+", "_", symbol.strip().upper()).strip("_")


@dataclass(frozen=True)
class BrowserHoldingItem:
    symbol: str
    quantity: int
    acquisition_price_tnd: Decimal
    acquisition_amount_tnd: Decimal
    latest_price_tnd: Decimal
    market_value_tnd: Decimal
    gain_tnd: Decimal
    gain_pct: Decimal


@dataclass(frozen=True)
class BrowserTransactionItem:
    transaction_id: str
    order_id: str
    symbol: str
    instrument_id: str
    side: str  # "BUY" | "SELL"
    filled_shares: int
    execution_price_tnd: Decimal
    fee_tnd: Decimal
    executed_at: str

    def to_dict(self) -> dict[str, object]:
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
    def from_dict(cls, data: dict[str, object]) -> BrowserTransactionItem:
        return cls(
            transaction_id=str(data["transaction_id"]),
            order_id=str(data["order_id"]),
            symbol=str(data["symbol"]),
            instrument_id=str(data["instrument_id"]),
            side=str(data["side"]),
            filled_shares=int(str(data["filled_shares"])),
            execution_price_tnd=Decimal(str(data["execution_price_tnd"])),
            fee_tnd=Decimal(str(data["fee_tnd"])),
            executed_at=str(data["executed_at"]),
        )


@dataclass(frozen=True)
class BrowserPendingOrderItem:
    order_id: str
    symbol: str
    instrument_id: str
    side: str  # "BUY" | "SELL"
    requested_shares: int
    filled_shares: int
    remaining_shares: int
    limit_price_tnd: Decimal
    status: str  # "PENDING" | "PARTIALLY_FILLED"
    submitted_at: str

    def to_dict(self) -> dict[str, object]:
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
    def from_dict(cls, data: dict[str, object]) -> BrowserPendingOrderItem:
        return cls(
            order_id=str(data["order_id"]),
            symbol=str(data["symbol"]),
            instrument_id=str(data["instrument_id"]),
            side=str(data["side"]),
            requested_shares=int(str(data["requested_shares"])),
            filled_shares=int(str(data["filled_shares"])),
            remaining_shares=int(str(data["remaining_shares"])),
            limit_price_tnd=Decimal(str(data["limit_price_tnd"])),
            status=str(data["status"]),
            submitted_at=str(data["submitted_at"]),
        )


@dataclass(frozen=True)
class CompetitionPortfolioDOMSnapshot:
    source_url: str
    retrieved_at: datetime
    portfolio_total_tnd: Decimal
    available_cash_tnd: Decimal
    holdings_market_value_tnd: Decimal
    holdings: tuple[BrowserHoldingItem, ...]
    competition_rank: int | None
    total_participants: int | None
    displayed_overall_performance_pct: Decimal | None
    is_reconciled: bool
    reconciliation_gap_tnd: Decimal
    challenge_period_text: str = ""
    movements_page_captured: bool = False
    movements_source_url: str | None = None
    transactions: tuple[BrowserTransactionItem, ...] = ()
    pending_orders: tuple[BrowserPendingOrderItem, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at.isoformat(),
            "portfolio_total_tnd": str(self.portfolio_total_tnd),
            "available_cash_tnd": str(self.available_cash_tnd),
            "holdings_market_value_tnd": str(self.holdings_market_value_tnd),
            "holdings": [
                {
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "acquisition_price_tnd": str(h.acquisition_price_tnd),
                    "acquisition_amount_tnd": str(h.acquisition_amount_tnd),
                    "latest_price_tnd": str(h.latest_price_tnd),
                    "market_value_tnd": str(h.market_value_tnd),
                    "gain_tnd": str(h.gain_tnd),
                    "gain_pct": str(h.gain_pct),
                }
                for h in self.holdings
            ],
            "competition_rank": self.competition_rank,
            "total_participants": self.total_participants,
            "displayed_overall_performance_pct": (
                str(self.displayed_overall_performance_pct)
                if self.displayed_overall_performance_pct is not None
                else None
            ),
            "is_reconciled": self.is_reconciled,
            "reconciliation_gap_tnd": str(self.reconciliation_gap_tnd),
            "challenge_period_text": self.challenge_period_text,
            "movements_page_captured": self.movements_page_captured,
            "movements_source_url": self.movements_source_url,
            "transactions": [t.to_dict() for t in self.transactions],
            "pending_orders": [p.to_dict() for p in self.pending_orders],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CompetitionPortfolioDOMSnapshot:
        raw_holdings = data.get("holdings", [])
        holdings_list = raw_holdings if isinstance(raw_holdings, list) else []
        holdings = tuple(
            BrowserHoldingItem(
                symbol=str(h["symbol"]),
                quantity=int(str(h["quantity"])),
                acquisition_price_tnd=Decimal(str(h["acquisition_price_tnd"])),
                acquisition_amount_tnd=Decimal(str(h["acquisition_amount_tnd"])),
                latest_price_tnd=Decimal(str(h["latest_price_tnd"])),
                market_value_tnd=Decimal(str(h["market_value_tnd"])),
                gain_tnd=Decimal(str(h["gain_tnd"])),
                gain_pct=Decimal(str(h["gain_pct"])),
            )
            for h in holdings_list
            if isinstance(h, dict)
        )
        raw_txs = data.get("transactions", [])
        tx_list = raw_txs if isinstance(raw_txs, list) else []
        transactions = tuple(
            BrowserTransactionItem.from_dict(t) for t in tx_list if isinstance(t, dict)
        )
        raw_pends = data.get("pending_orders", [])
        pend_list = raw_pends if isinstance(raw_pends, list) else []
        pending_orders = tuple(
            BrowserPendingOrderItem.from_dict(p) for p in pend_list if isinstance(p, dict)
        )
        perf = data.get("displayed_overall_performance_pct")
        rank = data.get("competition_rank")
        participants = data.get("total_participants")
        mov_url = data.get("movements_source_url")
        return cls(
            source_url=str(data["source_url"]),
            retrieved_at=datetime.fromisoformat(str(data["retrieved_at"])),
            portfolio_total_tnd=Decimal(str(data["portfolio_total_tnd"])),
            available_cash_tnd=Decimal(str(data["available_cash_tnd"])),
            holdings_market_value_tnd=Decimal(str(data["holdings_market_value_tnd"])),
            holdings=holdings,
            competition_rank=int(str(rank)) if rank is not None else None,
            total_participants=int(str(participants)) if participants is not None else None,
            displayed_overall_performance_pct=Decimal(str(perf)) if perf is not None else None,
            is_reconciled=bool(data["is_reconciled"]),
            reconciliation_gap_tnd=Decimal(str(data["reconciliation_gap_tnd"])),
            challenge_period_text=str(data.get("challenge_period_text", "")),
            movements_page_captured=bool(data.get("movements_page_captured", False)),
            movements_source_url=str(mov_url) if mov_url is not None else None,
            transactions=transactions,
            pending_orders=pending_orders,
        )


def parse_french_number(raw: str) -> Decimal:
    """Parse French numbers with comma decimals, space thousand separators, and currency/percent suffixes."""
    cleaned = raw.strip()
    for token in ("DT", "dt", "TND", "tnd", "%", "+", "\xa0", "\u202f"):
        cleaned = cleaned.replace(token, "")
    # Remove interior spaces used as thousand separators, then normalize comma to period
    cleaned = cleaned.replace(" ", "").replace(",", ".").strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Cannot parse numeric value from '{raw}': {exc}") from exc


class _SimpleDOMTableParser(HTMLParser):
    """Lightweight pure-Python DOM table and text extractor for displayp.aspx and display_histo.aspx."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self.all_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            self._current_table = []
            self.tables.append(self._current_table)
        elif tag_lower in {"tr"} and self._current_table is not None:
            self._current_row = []
            self._current_table.append(self._current_row)
        elif tag_lower in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if (
            tag_lower in {"td", "th"}
            and self._current_row is not None
            and self._current_cell is not None
        ):
            cell_text = "".join(self._current_cell).strip()
            self._current_row.append(cell_text)
            self._current_cell = None
        elif tag_lower == "tr":
            self._current_row = None
        elif tag_lower == "table":
            self._current_table = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.all_text.append(text)
        if self._current_cell is not None:
            self._current_cell.append(data)


def parse_competition_movements_html(
    html_content: str,
    *,
    retrieved_at: datetime | None = None,
) -> tuple[tuple[BrowserTransactionItem, ...], tuple[BrowserPendingOrderItem, ...]]:
    """Parse read-only display_histo.aspx ('Mouvements') HTML into executed transactions and pending orders.

    Supports French movement labels ('Achat'/'Vente', 'Exécuté'/'En cours'/'En attente')
    as well as English equivalents ('BUY'/'SELL', 'EXECUTED'/'PENDING').
    """
    timestamp = retrieved_at or datetime.now(UTC)
    lower_html = html_content.lower()
    if "connectez-vous" in lower_html or (
        "mot de passe" in lower_html and "mouvement" not in lower_html
    ):
        raise AuthenticationExpiredError(
            "Session expired on display_histo.aspx. Please log in to Tunis Bourse Challenge."
        )

    parser = _SimpleDOMTableParser()
    parser.feed(html_content)

    transactions: list[BrowserTransactionItem] = []
    pending_orders: list[BrowserPendingOrderItem] = []

    seq = 0
    for table in parser.tables:
        header_map: dict[str, int] = {}
        for row in table:
            if not row:
                continue
            row_lower = [c.strip().lower() for c in row]
            joined = " ".join(row_lower)

            # Detect header row
            if any(k in joined for k in ("valeur", "titre", "instrument", "symbole")) and any(
                k in joined for k in ("quantit", "qté", "qte", "shares")
            ):
                header_map = {}
                for idx, col in enumerate(row_lower):
                    if any(k in col for k in ("date", "séance", "seance", "heure")):
                        header_map.setdefault("date", idx)
                    elif any(k in col for k in ("valeur", "titre", "nom", "instrument", "symbole")):
                        header_map.setdefault("symbol", idx)
                    elif any(
                        k in col for k in ("sens", "opérat", "operat", "type", "side", "nature")
                    ):
                        header_map.setdefault("side", idx)
                    elif any(k in col for k in ("quantit", "qté", "qte", "shares")):
                        header_map.setdefault("quantity", idx)
                    elif any(k in col for k in ("cours", "prix", "limite", "price")):
                        header_map.setdefault("price", idx)
                    elif any(k in col for k in ("frais", "commission", "fee")):
                        header_map.setdefault("fee", idx)
                    elif any(k in col for k in ("statut", "état", "etat", "status", "situation")):
                        header_map.setdefault("status", idx)
                    elif any(k in col for k in ("réf", "ref", "ordre", "id", "n°", "num")):
                        header_map.setdefault("id", idx)
                continue

            if not header_map or len(row) < 4:
                continue
            if any(k in joined for k in ("aucun mouvement", "aucun ordre", "totaux", "liquidit")):
                continue

            try:
                sym_idx = header_map.get("symbol", 1)
                qty_idx = header_map.get("quantity", 2)
                px_idx = header_map.get("price", 3)
                if max(sym_idx, qty_idx, px_idx) >= len(row):
                    continue

                symbol = row[sym_idx].strip()
                if not symbol or symbol.lower() in {"valeur", "nom de valeur", "titre"}:
                    continue

                qty_raw = row[qty_idx].replace(" ", "").strip()
                quantity = int(qty_raw)
                if quantity <= 0:
                    continue
                price = parse_french_number(row[px_idx])

                # Determine side (BUY / SELL)
                side_raw = (
                    row[header_map["side"]].strip().lower()
                    if "side" in header_map and header_map["side"] < len(row)
                    else joined
                )
                if any(k in side_raw for k in ("vente", "vendre", "sell", "v")):
                    side = "SELL"
                else:
                    side = "BUY"

                # Determine status (EXECUTED vs PENDING vs CANCELLED)
                status_raw = (
                    row[header_map["status"]].strip().lower()
                    if "status" in header_map and header_map["status"] < len(row)
                    else "exécuté"
                )
                if any(k in status_raw for k in ("annul", "cancel", "rejet", "expir")):
                    continue

                # Determine date/timestamp
                date_raw = (
                    row[header_map["date"]].strip()
                    if "date" in header_map and header_map["date"] < len(row)
                    else ""
                )
                iso_ts = _parse_movement_timestamp(date_raw, fallback=timestamp)

                seq += 1
                raw_id = (
                    row[header_map["id"]].strip()
                    if "id" in header_map
                    and header_map["id"] < len(row)
                    and row[header_map["id"]].strip()
                    else f"MOV-{seq:04d}"
                )
                inst_id = _normalize_instrument_id(symbol)

                if any(
                    k in status_raw
                    for k in ("en cours", "attente", "pending", "valide", "ouvert", "partiel")
                ):
                    pending_orders.append(
                        BrowserPendingOrderItem(
                            order_id=f"ORD-{raw_id}",
                            symbol=symbol,
                            instrument_id=inst_id,
                            side=side,
                            requested_shares=quantity,
                            filled_shares=0,
                            remaining_shares=quantity,
                            limit_price_tnd=price,
                            status="PARTIALLY_FILLED" if "partiel" in status_raw else "PENDING",
                            submitted_at=iso_ts,
                        )
                    )
                else:
                    gross = (Decimal(quantity) * price).quantize(Decimal("0.001"))
                    if (
                        "fee" in header_map
                        and header_map["fee"] < len(row)
                        and row[header_map["fee"]].strip()
                    ):
                        fee = parse_french_number(row[header_map["fee"]])
                    else:
                        fee = (gross * STANDARD_FEE_RATE).quantize(Decimal("0.001"))
                    transactions.append(
                        BrowserTransactionItem(
                            transaction_id=f"TX-{raw_id}",
                            order_id=f"ORD-{raw_id}",
                            symbol=symbol,
                            instrument_id=inst_id,
                            side=side,
                            filled_shares=quantity,
                            execution_price_tnd=price,
                            fee_tnd=fee,
                            executed_at=iso_ts,
                        )
                    )
            except (ValueError, IndexError):
                continue

    return tuple(transactions), tuple(pending_orders)


def _parse_movement_timestamp(raw: str, *, fallback: datetime) -> str:
    cleaned = raw.strip()
    if not cleaned:
        return fallback.isoformat()
    # Match DD/MM/YYYY or DD-MM-YYYY
    m_dmy = re.search(r"(\d{2})[/\-](\d{2})[/\-](\d{4})(?:\s+(\d{2}):(\d{2}))?", cleaned)
    if m_dmy:
        day, month, year, hh, mm = m_dmy.groups()
        hour = hh or "10"
        minute = mm or "00"
        return f"{year}-{month}-{day}T{hour}:{minute}:00+01:00"
    # Match YYYY-MM-DD
    m_ymd = re.search(r"(\d{4})-(\d{2})-(\d{2})", cleaned)
    if m_ymd:
        return f"{m_ymd.group(0)}T10:00:00+01:00"
    return fallback.isoformat()


def parse_competition_portfolio_html(
    html_content: str,
    *,
    source_url: str = DEFAULT_CHALLENGE_URL,
    retrieved_at: datetime | None = None,
    tolerance_tnd: Decimal = DEFAULT_ROUNDING_TOLERANCE_TND,
    movements_html: str | None = None,
    movements_source_url: str | None = None,
) -> CompetitionPortfolioDOMSnapshot:
    """Parse authenticated displayp.aspx HTML into structured snapshot.

    Validates balance: cash + holdings market value == reported total within tolerance.
    Optionally parses display_histo.aspx ('Mouvements') HTML if provided.
    Raises AuthenticationExpiredError if session expired, or LayoutChangedError if missing elements.
    """
    timestamp = retrieved_at or datetime.now(UTC)

    # 1. Detect unauthenticated / login pages
    lower_html = html_content.lower()
    if (
        "connectez-vous" in lower_html
        or "mot de passe" in lower_html
        and "votre portefeuille" not in lower_html
    ):
        raise AuthenticationExpiredError(
            "Session expired or page redirected to login. Please log in to Tunis Bourse Challenge."
        )

    parser = _SimpleDOMTableParser()
    parser.feed(html_content)

    full_text = " ".join(parser.all_text)

    # 2. Extract Portfolio Total
    total_match = re.search(
        r"Votre\s+portefeuille\s*:\s*([0-9\s,\.]+)\s*(?:DT|dt)?",
        full_text,
        re.IGNORECASE,
    )
    if not total_match:
        raise LayoutChangedError("Could not locate 'Votre portefeuille' total amount in page HTML.")
    portfolio_total = parse_french_number(total_match.group(1))

    # 3. Extract Ranking
    rank_match = re.search(
        r"Votre\s+classement\s*:\s*(\d+)\s*/\s*(\d+)",
        full_text,
        re.IGNORECASE,
    )
    rank = int(rank_match.group(1)) if rank_match else None
    participants = int(rank_match.group(2)) if rank_match else None

    # 4. Extract Overall Performance
    perf_match = re.search(
        r"Performance\s+g[ée]n[ée]rale\s*:\s*([+-]?[0-9\s,\.]+)\s*%",
        full_text,
        re.IGNORECASE,
    )
    displayed_perf = parse_french_number(perf_match.group(1)) if perf_match else None

    # 5. Extract Challenge Period Text
    period_match = re.search(
        r"(Tunisbourse\s+Challenge\s+est\s+ouvert[^\.]*\.)",
        full_text,
        re.IGNORECASE,
    )
    period_text = period_match.group(1).strip() if period_match else ""

    # 6. Extract Holdings Table ("Mes valeurs")
    holdings: list[BrowserHoldingItem] = []
    cash_tnd: Decimal | None = None

    for table in parser.tables:
        for _row_idx, row in enumerate(table):
            row_joined = " ".join(row).lower()

            # Detect Cash row (Liquidités)
            if "liquidit" in row_joined:
                for cell in reversed(row):
                    if cell.strip():
                        try:
                            cash_tnd = parse_french_number(cell)
                            break
                        except ValueError:
                            continue

            # Check if this row is a holding row
            # Expected cols: [Vendre, Nom de valeur, Quantité, Prix, Montant, Dernier, Capital, Gain (dt), Gain(%)]
            if len(row) >= 7:
                name_cand = row[1] if len(row) > 7 else row[0]
                if "nom de valeur" in name_cand.lower() or "quantit" in name_cand.lower():
                    continue
                if "totaux" in name_cand.lower() or "liquidit" in name_cand.lower():
                    continue

                try:
                    qty_cand = int(row[2].replace(" ", ""))
                    prix_cand = parse_french_number(row[3])
                    montant_cand = parse_french_number(row[4])
                    dernier_cand = parse_french_number(row[5])
                    capital_cand = parse_french_number(row[6])
                    gain_dt_cand = (
                        parse_french_number(row[7])
                        if len(row) > 7
                        else (capital_cand - montant_cand)
                    )
                    gain_pct_cand = parse_french_number(row[8]) if len(row) > 8 else Decimal("0.00")

                    symbol_clean = name_cand.strip()
                    if symbol_clean:
                        holdings.append(
                            BrowserHoldingItem(
                                symbol=symbol_clean,
                                quantity=qty_cand,
                                acquisition_price_tnd=prix_cand,
                                acquisition_amount_tnd=montant_cand,
                                latest_price_tnd=dernier_cand,
                                market_value_tnd=capital_cand,
                                gain_tnd=gain_dt_cand,
                                gain_pct=gain_pct_cand,
                            )
                        )
                except (ValueError, IndexError):
                    continue

    # Fallback search for Cash if not found in table cells
    if cash_tnd is None:
        cash_match = re.search(
            r"Liquidit[ée]s\s*:\s*([0-9\s,\.]+)\s*(?:DT|dt)?",
            full_text,
            re.IGNORECASE,
        )
        if cash_match:
            cash_tnd = parse_french_number(cash_match.group(1))

    if cash_tnd is None:
        raise LayoutChangedError("Could not locate 'Liquidités' cash balance in page HTML.")

    holdings_value = sum((h.market_value_tnd for h in holdings), Decimal("0.000"))
    calculated_total = cash_tnd + holdings_value
    gap = (calculated_total - portfolio_total).copy_abs()
    is_reconciled = gap <= tolerance_tnd

    if not is_reconciled:
        raise BalanceMismatchError(
            f"Balance mismatch: Cash ({cash_tnd} TND) + Holdings ({holdings_value} TND) = "
            f"{calculated_total} TND, which differs from reported total {portfolio_total} TND "
            f"by {gap} TND (tolerance: {tolerance_tnd} TND)."
        )

    movements_captured = False
    tx_items: tuple[BrowserTransactionItem, ...] = ()
    pend_items: tuple[BrowserPendingOrderItem, ...] = ()
    if movements_html and movements_html.strip():
        try:
            tx_items, pend_items = parse_competition_movements_html(
                movements_html, retrieved_at=timestamp
            )
            movements_captured = True
        except AuthenticationExpiredError:
            movements_captured = False

    return CompetitionPortfolioDOMSnapshot(
        source_url=source_url,
        retrieved_at=timestamp,
        portfolio_total_tnd=portfolio_total,
        available_cash_tnd=cash_tnd,
        holdings_market_value_tnd=holdings_value,
        holdings=tuple(holdings),
        competition_rank=rank,
        total_participants=participants,
        displayed_overall_performance_pct=displayed_perf,
        is_reconciled=is_reconciled,
        reconciliation_gap_tnd=gap,
        challenge_period_text=period_text,
        movements_page_captured=movements_captured,
        movements_source_url=movements_source_url if movements_captured else None,
        transactions=tx_items,
        pending_orders=pend_items,
    )


def save_browser_snapshot(
    snapshot: CompetitionPortfolioDOMSnapshot,
    snapshots_dir: Path,
) -> Path:
    """Save structured DOM snapshot locally outside Git."""
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    stamp = snapshot.retrieved_at.strftime("%Y%m%d_%H%M%S")
    out_path = snapshots_dir / f"sync_{stamp}.json"
    out_path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    return out_path


def load_latest_browser_snapshot(snapshots_dir: Path) -> CompetitionPortfolioDOMSnapshot | None:
    """Load most recent local DOM snapshot if available."""
    if not snapshots_dir.exists():
        return None
    files = sorted(snapshots_dir.glob("sync_*.json"))
    if not files:
        return None
    latest_file = files[-1]
    data = json.loads(latest_file.read_text(encoding="utf-8"))
    return CompetitionPortfolioDOMSnapshot.from_dict(data)


def run_interactive_browser_sync(
    *,
    user_data_dir: Path,
    target_url: str = DEFAULT_CHALLENGE_URL,
    timeout_seconds: int = 180,
) -> str:
    """Launch dedicated browser profile, wait for user to authenticate and navigate to displayp.aspx.

    Local-first, read-only:
    - Launches isolated Chromium user_data_dir (separate from user's Chrome profile).
    - Visible non-headless window allowing user to log in manually.
    - Waits for authenticated portfolio page content.
    - Returns raw HTML string for parsing.
    - Never automates login, never captures credentials, never clicks trade buttons.
    """
    html_content, _ = _run_interactive_browser_pages(
        user_data_dir=user_data_dir,
        target_url=target_url,
        movements_url=None,
        timeout_seconds=timeout_seconds,
    )
    return html_content


def _run_interactive_browser_pages(
    *,
    user_data_dir: Path,
    target_url: str = DEFAULT_CHALLENGE_URL,
    movements_url: str | None = DEFAULT_MOVEMENTS_URL,
    timeout_seconds: int = 180,
) -> tuple[str, str | None]:
    """Launch isolated persistent browser context, capture displayp.aspx and optional display_histo.aspx."""
    validate_readonly_challenge_url(target_url)
    if movements_url is not None:
        validate_readonly_challenge_url(movements_url)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserCollectorError(
            "Playwright is not installed in .venv. Install with: uv pip install playwright"
        ) from exc

    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,
                channel="chrome",
                viewport={"width": 1280, "height": 840},
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,
                viewport={"width": 1280, "height": 840},
            )
        try:
            page = context.new_page() if not context.pages else context.pages[0]
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

            deadline = time.monotonic() + max(5, timeout_seconds)
            portfolio_html: str | None = None
            last_url = ""
            last_title = ""

            while time.monotonic() < deadline:
                if not context.pages or page.is_closed():
                    raise BrowserCollectorError(
                        "Browser window was closed by user before authenticated portfolio DOM was captured."
                    )
                try:
                    current_html = page.content()
                    last_url = page.url
                    last_title = page.title()
                except Exception:
                    time.sleep(0.5)
                    continue

                lower = current_html.lower()
                # Check if authenticated portfolio table is present
                if "votre portefeuille" in lower and "liquidit" in lower:
                    portfolio_html = current_html
                    break

                # If user finished logging in and landed on default.aspx / home page where logout or navbar is shown
                if (
                    ("déconnexion" in lower or "deconnexion" in lower or "mon compte" in lower)
                    and "mot de passe" not in lower
                    and "displayp.aspx" not in last_url.lower()
                ):
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass

                time.sleep(0.75)

            if portfolio_html is None:
                raise AuthenticationExpiredError(
                    f"Timed out after {timeout_seconds}s waiting for authenticated 'Mon portefeuille' "
                    f"(displayp.aspx) DOM. Last observed URL: '{last_url}' (title: '{last_title}'). "
                    f"Please log in manually in the opened browser window and navigate to Portefeuille (displayp.aspx)."
                )

            movements_html: str | None = None
            if movements_url is not None:
                try:
                    page.goto(movements_url, wait_until="domcontentloaded", timeout=15000)
                    time.sleep(0.5)
                    cand_html = page.content()
                    if "mot de passe" not in cand_html.lower():
                        movements_html = cand_html
                except Exception:
                    movements_html = None

            return portfolio_html, movements_html
        finally:
            try:
                context.close()
            except Exception:
                pass


def collect_authenticated_portfolio_snapshot(
    *,
    user_data_dir: Path,
    snapshots_dir: Path,
    target_url: str = DEFAULT_CHALLENGE_URL,
    movements_url: str | None = DEFAULT_MOVEMENTS_URL,
    timeout_seconds: int = 180,
) -> tuple[CompetitionPortfolioDOMSnapshot, Path]:
    """Run interactive read-only browser sync, parse displayp.aspx and display_histo.aspx, and save snapshot."""
    portfolio_html, movements_html = _run_interactive_browser_pages(
        user_data_dir=user_data_dir,
        target_url=target_url,
        movements_url=movements_url,
        timeout_seconds=timeout_seconds,
    )
    snapshot = parse_competition_portfolio_html(
        portfolio_html,
        source_url=target_url,
        movements_html=movements_html,
        movements_source_url=movements_url if movements_html else None,
    )
    saved_path = save_browser_snapshot(snapshot, snapshots_dir)
    return snapshot, saved_path


def run_browser_sync_subprocess(
    *,
    user_data_dir: Path,
    snapshots_dir: Path,
    timeout_seconds: int = 180,
) -> tuple[CompetitionPortfolioDOMSnapshot, Path]:
    """Run the Playwright browser collector in a clean child Python process (Windows/Streamlit safe)."""
    cmd = [
        sys.executable,
        "-m",
        "bvmt.browser",
        "--user-data-dir",
        str(user_data_dir),
        "--snapshots-dir",
        str(snapshots_dir),
        "--timeout",
        str(timeout_seconds),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        err_msg = (proc.stderr or proc.stdout or "Unknown browser sync subprocess error").strip()
        if "AuthenticationExpiredError:" in err_msg:
            raise AuthenticationExpiredError(
                err_msg.split("AuthenticationExpiredError:", 1)[-1].strip()
            )
        if "BalanceMismatchError:" in err_msg:
            raise BalanceMismatchError(err_msg.split("BalanceMismatchError:", 1)[-1].strip())
        if "LayoutChangedError:" in err_msg:
            raise LayoutChangedError(err_msg.split("LayoutChangedError:", 1)[-1].strip())
        raise BrowserCollectorError(err_msg)

    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    snap_path = Path(str(payload["saved_path"]))
    snap_data = json.loads(snap_path.read_text(encoding="utf-8"))
    return CompetitionPortfolioDOMSnapshot.from_dict(snap_data), snap_path


def _cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch local read-only Playwright browser collector for Tunis Bourse Challenge."
    )
    parser.add_argument("--user-data-dir", default="data/browser_profile")
    parser.add_argument("--snapshots-dir", default="data/portfolio/snapshots")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-movements", action="store_true")
    args = parser.parse_args(argv)
    try:
        snapshot, saved_path = collect_authenticated_portfolio_snapshot(
            user_data_dir=Path(args.user_data_dir),
            snapshots_dir=Path(args.snapshots_dir),
            movements_url=None if args.no_movements else DEFAULT_MOVEMENTS_URL,
            timeout_seconds=args.timeout,
        )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "saved_path": saved_path.as_posix(),
                    "snapshot": snapshot.to_dict(),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except AuthenticationExpiredError as exc:
        print(f"AuthenticationExpiredError: {exc}", file=sys.stderr)
        return 2
    except BalanceMismatchError as exc:
        print(f"BalanceMismatchError: {exc}", file=sys.stderr)
        return 3
    except LayoutChangedError as exc:
        print(f"LayoutChangedError: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"BrowserCollectorError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli_main())
