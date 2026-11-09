"""Manual portfolio import fallback parser (Milestone 10, Phase 2).

Supports:
1. Copied HTML table or plain text from Tunis Bourse Challenge (`displayp.aspx`).
2. Tab-separated or comma-separated CSV uploads.
3. Explicit detection of extracted fields vs missing fields.
4. Flexible French number parsing (comma separators, space thousand separators).
5. Exact Decimal financial precision (quantized to 0.001 TND).
"""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Literal

from bvmt.sync_service import (
    NormalizedAccountObservation,
    NormalizedHoldingObservation,
    NormalizedTransactionObservation,
    normalize_instrument_id,
    quantize_tnd,
)


def parse_french_number(raw: str) -> Decimal:
    """Parse French-formatted numbers: '19 095,000' -> 19095.000 or '19,095' -> 19.095."""
    clean = raw.strip().replace("\xa0", "").replace(" ", "").replace("DT", "").replace("dt", "")
    if not clean:
        raise ValueError("Empty number string")
    clean = clean.replace(",", ".")
    try:
        return Decimal(clean)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid monetary number string: '{raw}'") from exc


class SimpleHTMLTableExtractor(HTMLParser):
    """Extract rows and cells from HTML table fragment."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell = []
        elif tag == "tr":
            self._current_row = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            self._in_cell = False
            cell_text = "".join(self._current_cell).strip()
            self._current_row.append(cell_text)
        elif tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
                self._current_row = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)


def parse_manual_portfolio_paste(
    raw_text: str,
    *,
    cash_override: Decimal | None = None,
    equity_override: Decimal | None = None,
    rank_override: int | None = None,
) -> NormalizedAccountObservation:
    """Parse pasted text or HTML fragment from Tunis Bourse Challenge displayp.aspx."""
    text = raw_text.strip()
    if not text:
        raise ValueError("Pasted portfolio text is empty.")

    extracted_cash: Decimal | None = cash_override
    extracted_equity: Decimal | None = equity_override
    extracted_rank: int | None = rank_override
    extracted_participants: int | None = None

    # Check for cash in text: "Liquidités : 44 586,070" or "Liquidites 44586.070"
    if extracted_cash is None:
        cash_match = re.search(r"Liquidit[ée]s?\s*:?\s*([0-9\s,\.]+)", text, re.IGNORECASE)
        if cash_match:
            try:
                extracted_cash = quantize_tnd(parse_french_number(cash_match.group(1)))
            except Exception:
                pass

    # Check for total equity: "Total Portefeuille : 49 979,070" or "Total du portefeuille"
    if extracted_equity is None:
        eq_match = re.search(
            r"Total\s*(?:du)?\s*portefeuille\s*:?\s*([0-9\s,\.]+)", text, re.IGNORECASE
        )
        if eq_match:
            try:
                extracted_equity = quantize_tnd(parse_french_number(eq_match.group(1)))
            except Exception:
                pass

    # Check for rank: "Rang : 133 / 14 547" or "Classement : 133"
    if extracted_rank is None:
        rank_match = re.search(
            r"(?:Rang|Classement)\s*:?\s*#?([0-9\s]+)(?:\s*/\s*([0-9\s]+))?", text, re.IGNORECASE
        )
        if rank_match:
            try:
                extracted_rank = int(rank_match.group(1).replace(" ", ""))
                if rank_match.group(2):
                    extracted_participants = int(rank_match.group(2).replace(" ", ""))
            except Exception:
                pass

    holdings: list[NormalizedHoldingObservation] = []

    # If text contains HTML tags, use table extractor
    if "<table" in text.lower() or "<tr" in text.lower():
        parser = SimpleHTMLTableExtractor()
        parser.feed(text)
        rows = parser.rows
    else:
        # Split by lines and tabs/multiple spaces
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        rows = []
        for line in lines:
            if "\t" in line:
                rows.append([c.strip() for c in line.split("\t") if c.strip()])
            elif ";" in line:
                rows.append([c.strip() for c in line.split(";") if c.strip()])
            else:
                # whitespace split if contains numbers
                parts = re.split(r"\s{2,}", line)
                rows.append([p.strip() for p in parts if p.strip()])

    for row in rows:
        if len(row) < 3:
            continue
        first_cell = row[0].upper()
        if any(
            h in first_cell for h in ["VALEUR", "SYMBOLE", "ACTION", "TITRE", "TOTAL", "LIQUIDIT"]
        ):
            continue

        # Look for symbol and numeric values in the row
        sym = row[0].strip().upper()
        # Filter out rows that are clearly not stocks
        if not re.match(r"^[A-Z0-9._\s-]+$", sym) or len(sym) > 40:
            continue

        numbers: list[Decimal] = []
        for cell in row[1:]:
            try:
                val = parse_french_number(cell)
                numbers.append(val)
            except ValueError:
                continue

        if len(numbers) >= 2:
            # Typically: Quantity (int), Acquisition Price, [Latest Price], [Market Value]
            # e.g.: [263, 19.095, 19.000, 4997.000]
            try:
                qty = int(numbers[0])
                acq_px = quantize_tnd(numbers[1])
                lat_px = quantize_tnd(numbers[2]) if len(numbers) >= 3 else acq_px
                mkt_val = (
                    quantize_tnd(numbers[3])
                    if len(numbers) >= 4
                    else quantize_tnd(Decimal(qty) * lat_px)
                )

                holdings.append(
                    NormalizedHoldingObservation(
                        symbol=sym,
                        instrument_id=normalize_instrument_id(sym),
                        quantity=qty,
                        acquisition_price_tnd=acq_px,
                        latest_price_tnd=lat_px,
                        market_value_tnd=mkt_val,
                        displayed_name=sym,
                    )
                )
            except (ValueError, InvalidOperation):
                continue

    # Compute default cash or equity if only one was provided
    holdings_sum = sum((h.market_value_tnd for h in holdings), Decimal("0.000"))
    if extracted_cash is None and extracted_equity is not None:
        extracted_cash = max(Decimal("0.000"), extracted_equity - holdings_sum)
    elif extracted_cash is not None and extracted_equity is None:
        extracted_equity = extracted_cash + holdings_sum
    elif extracted_cash is None and extracted_equity is None:
        extracted_cash = Decimal("50000.000") - holdings_sum
        extracted_equity = Decimal("50000.000")

    assert extracted_cash is not None and extracted_equity is not None
    now_iso = datetime.now(UTC).isoformat()
    snap_id = f"manual_{int(datetime.now(UTC).timestamp())}"

    return NormalizedAccountObservation(
        source="MANUAL_PASTE",
        capture_timestamp=now_iso,
        snapshot_id=snap_id,
        account_equity=quantize_tnd(extracted_equity),
        available_cash=quantize_tnd(extracted_cash),
        holdings=holdings,
        competition_ranking=extracted_rank,
        total_participants=extracted_participants,
        source_page_type="manual_text_paste",
        challenge_period_text="Manual Table Import",
    )


def parse_manual_portfolio_csv(
    csv_content: str,
    *,
    cash: Decimal | None = None,
    equity: Decimal | None = None,
    rank: int | None = None,
) -> NormalizedAccountObservation:
    """Parse structured CSV file containing holdings."""
    stream = io.StringIO(csv_content.strip())
    # Detect delimiter
    sample = csv_content[:1024]
    delimiter = ";" if ";" in sample else ","
    reader = csv.reader(stream, delimiter=delimiter)

    holdings: list[NormalizedHoldingObservation] = []
    meta_cash = cash
    meta_equity = equity

    for row in reader:
        if not row or not any(row):
            continue
        first = row[0].strip().upper()

        # Check metadata headers
        if "CASH" in first or "LIQUIDIT" in first:
            if len(row) >= 2:
                try:
                    meta_cash = quantize_tnd(parse_french_number(row[1]))
                except Exception:
                    pass
            continue
        if "TOTAL" in first or "EQUITY" in first:
            if len(row) >= 2:
                try:
                    meta_equity = quantize_tnd(parse_french_number(row[1]))
                except Exception:
                    pass
            continue
        if any(h in first for h in ["SYMBOL", "VALEUR", "TITRE", "ACTION"]):
            continue

        sym = first
        if not sym:
            continue

        try:
            qty = int(row[1].strip().replace(" ", ""))
            acq_px = quantize_tnd(parse_french_number(row[2]))
            lat_px = (
                quantize_tnd(parse_french_number(row[3]))
                if len(row) >= 4 and row[3].strip()
                else acq_px
            )
            mkt_val = (
                quantize_tnd(parse_french_number(row[4]))
                if len(row) >= 5 and row[4].strip()
                else quantize_tnd(Decimal(qty) * lat_px)
            )

            holdings.append(
                NormalizedHoldingObservation(
                    symbol=sym,
                    instrument_id=normalize_instrument_id(sym),
                    quantity=qty,
                    acquisition_price_tnd=acq_px,
                    latest_price_tnd=lat_px,
                    market_value_tnd=mkt_val,
                    displayed_name=sym,
                )
            )
        except Exception:
            continue

    holdings_sum = sum((h.market_value_tnd for h in holdings), Decimal("0.000"))
    if meta_cash is None and meta_equity is not None:
        meta_cash = max(Decimal("0.000"), meta_equity - holdings_sum)
    elif meta_cash is not None and meta_equity is None:
        meta_equity = meta_cash + holdings_sum
    elif meta_cash is None and meta_equity is None:
        meta_cash = Decimal("50000.000") - holdings_sum
        meta_equity = Decimal("50000.000")

    assert meta_cash is not None and meta_equity is not None
    now_iso = datetime.now(UTC).isoformat()
    snap_id = f"csv_{int(datetime.now(UTC).timestamp())}"

    return NormalizedAccountObservation(
        source="CSV_IMPORT",
        capture_timestamp=now_iso,
        snapshot_id=snap_id,
        account_equity=quantize_tnd(meta_equity),
        available_cash=quantize_tnd(meta_cash),
        holdings=holdings,
        competition_ranking=rank,
        source_page_type="csv_upload",
        challenge_period_text="Manual CSV Upload",
    )


def parse_manual_transactions_csv(csv_content: str) -> list[NormalizedTransactionObservation]:
    """Parse CSV containing transaction history from display_histo.aspx."""
    stream = io.StringIO(csv_content.strip())
    sample = csv_content[:1024]
    delimiter = ";" if ";" in sample else ","
    reader = csv.reader(stream, delimiter=delimiter)

    transactions: list[NormalizedTransactionObservation] = []
    col_map: dict[str, int] = {}

    for row in reader:
        if not row:
            continue
        row_upper = [c.strip().upper() for c in row]

        # Check for header row
        if any(h in row_upper[0] for h in ["DATE", "ID", "TRANSACTION", "SYMBOLE", "ORDER"]):
            for idx, col in enumerate(row_upper):
                if col in {"ID", "N°"} or any(
                    k in col for k in ["ORDER_ID", "TRANSACTION_ID", "REF"]
                ):
                    col_map.setdefault("id", idx)
                elif any(k in col for k in ["DATE", "HEURE", "EXECUTED_AT"]):
                    col_map.setdefault("date", idx)
                elif any(k in col for k in ["SYMBOLE", "SYMBOL", "VALEUR", "TITRE"]):
                    col_map.setdefault("sym", idx)
                elif any(k in col for k in ["SIDE", "SENS", "TYPE"]):
                    col_map.setdefault("side", idx)
                elif any(k in col for k in ["QUANT", "SHARES", "TITRES"]):
                    col_map.setdefault("qty", idx)
                elif any(k in col for k in ["COURS", "PRICE", "PRIX"]):
                    col_map.setdefault("px", idx)
                elif any(k in col for k in ["FRAIS", "FEE", "COMMISSION"]):
                    col_map.setdefault("fee", idx)
            continue

        if len(row) < 5:
            continue

        try:
            tx_id = row[col_map.get("id", 0)].strip()
            sym = row[col_map.get("sym", 1 if "sym" in col_map else 2)].strip().upper()
            date_str = (
                row[col_map["date"]].strip()
                if "date" in col_map and col_map["date"] < len(row)
                else (row[1].strip() if len(row) > 6 else datetime.now(UTC).isoformat())
            )
            side_raw = row[col_map.get("side", 2 if "side" in col_map else 3)].upper()
            side: Literal["BUY", "SELL"] = (
                "BUY" if any(w in side_raw for w in ["ACHAT", "BUY", "A"]) else "SELL"
            )
            qty = int(
                row[col_map.get("qty", 3 if "qty" in col_map else 4)].strip().replace(" ", "")
            )
            px = quantize_tnd(
                parse_french_number(row[col_map.get("px", 4 if "px" in col_map else 5)])
            )
            fee_idx = col_map.get("fee", 5 if "fee" in col_map else (6 if len(row) >= 7 else None))
            fees = (
                quantize_tnd(parse_french_number(row[fee_idx]))
                if fee_idx is not None and fee_idx < len(row) and row[fee_idx].strip()
                else quantize_tnd(Decimal(qty) * px * Decimal("0.005"))
            )

            transactions.append(
                NormalizedTransactionObservation(
                    transaction_id=tx_id,
                    order_id=tx_id,
                    symbol=sym,
                    instrument_id=normalize_instrument_id(sym),
                    side=side,
                    filled_shares=qty,
                    execution_price_tnd=px,
                    fee_tnd=fees,
                    executed_at=date_str,
                )
            )
        except Exception:
            continue

    return transactions
