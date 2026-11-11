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

from bvmt.browser import (
    _classify_movement_side,
    _parse_movement_timestamp,
)
from bvmt.browser import (
    parse_french_number as _strict_parse_french_number,
)
from bvmt.sync_service import (
    NormalizedAccountObservation,
    NormalizedHoldingObservation,
    NormalizedTransactionObservation,
    normalize_instrument_id,
    quantize_tnd,
)


def parse_french_number(raw: str) -> Decimal:
    """Parse locale-aware French numbers strictly using canonical browser parser."""
    return _strict_parse_french_number(raw)


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
        cash_match = re.search(
            r"Liquidit[ée]s?\s*:?\s*(-?[0-9][0-9\s\xa0\u202f,\.]*)", text, re.IGNORECASE
        )
        if cash_match:
            try:
                extracted_cash = quantize_tnd(parse_french_number(cash_match.group(1)))
            except ValueError:
                pass

    # Check for total equity: "Total Portefeuille : 49 979,070", "Votre portefeuille : 50061,96 DT", or "Totaux 50061.96"
    if extracted_equity is None:
        eq_match = re.search(
            r"(?:Votre\s+portefeuille|Total\s*(?:du)?\s*portefeuille)\s*:?\s*(-?[0-9][0-9\s\xa0\u202f,\.]*)",
            text,
            re.IGNORECASE,
        ) or re.search(r"\bTotaux\b\s*:?\s*(-?[0-9][0-9\s\xa0\u202f,\.]*)", text, re.IGNORECASE)
        if eq_match:
            try:
                extracted_equity = quantize_tnd(parse_french_number(eq_match.group(1)))
            except ValueError:
                pass

    # Check for rank: "Rang : 133 / 14 547", "Classement : 133", or "Votre classement : 112 / 14573"
    if extracted_rank is None:
        rank_match = re.search(
            r"(?:Votre\s+classement|Rang|Classement)\s*:?\s*#?([0-9\s\xa0\u202f]+)(?:\s*/\s*([0-9\s\xa0\u202f]+))?",
            text,
            re.IGNORECASE,
        )
        if rank_match:
            try:
                extracted_rank = int(
                    rank_match.group(1).replace("\xa0", "").replace("\u202f", "").replace(" ", "")
                )
                if rank_match.group(2):
                    extracted_participants = int(
                        rank_match.group(2)
                        .replace("\xa0", "")
                        .replace("\u202f", "")
                        .replace(" ", "")
                    )
            except ValueError:
                pass

    holdings: list[NormalizedHoldingObservation] = []

    # If text contains HTML tags, use table extractor
    if "<table" in text.lower() or "<tr" in text.lower():
        parser = SimpleHTMLTableExtractor()
        parser.feed(text)
        rows = parser.rows
    else:
        # Split by lines preserving empty/placeholder cells for column alignment
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        rows = []
        for line in lines:
            if "\t" in line:
                rows.append([c.strip() for c in line.split("\t")])
            elif ";" in line:
                rows.append([c.strip() for c in line.split(";")])
            else:
                parts = re.split(r"\s{2,}", line)
                rows.append([p.strip() for p in parts if p.strip()])

    seen_symbols: set[str] = set()

    for row in rows:
        if len(row) < 2:
            continue
        first_cell = " ".join(row[0].upper().split())
        if first_cell in {
            "VALEUR",
            "NOM DE VALEUR",
            "SYMBOLE",
            "SYMBOL",
            "TITRE",
            "TOTAUX",
            "TOTAL",
            "TOTAL PORTEFEUILLE",
            "TOTAL DU PORTEFEUILLE",
            "LIQUIDITES",
            "LIQUIDITÉS",
        } or re.match(
            r"^(?:NOM\s+DE\s+VALEUR|TOTAL\s+(?:DU\s+)?PORTEFEUILLE|TOTAL\s+GENERAL|TOTAL\s*:|TOTAUX\b|LIQUIDIT[ÉE]S?\b)",
            first_cell,
        ):
            if first_cell.startswith("LIQUIDIT") and extracted_cash is None and len(row) >= 2:
                try:
                    extracted_cash = quantize_tnd(parse_french_number(row[1]))
                except ValueError:
                    pass
            if (
                first_cell.startswith(("TOTAUX", "TOTAL"))
                and extracted_equity is None
                and len(row) >= 2
            ):
                try:
                    extracted_equity = quantize_tnd(parse_french_number(row[1]))
                except ValueError:
                    pass
            continue

        # Handle 12-cell tbody.alri layout:
        # [vendre, ticker, numeric_id, full_name, qty, A, acq_px, acq_amt, lat_px, mkt_val, gain_dt, gain_pct]
        sym = ""
        displayed_name: str | None = None
        candidate_num_cells: list[str] = []

        if (
            len(row) >= 10
            and row[2].strip().isdigit()
            and row[5].strip().upper() in {"A", "S", "V"}
        ):
            sym = row[3].strip().upper()
            displayed_name = row[1].strip().upper() or sym
            candidate_num_cells = [row[4], *row[6:]]
        elif first_cell == "VENDRE" or "ACTION" in first_cell or not first_cell:
            if len(row) >= 3:
                sym = row[1].strip().upper()
                candidate_num_cells = row[2:]
        else:
            sym = row[0].strip().upper()
            candidate_num_cells = row[1:]

        # Filter out rows that are clearly header/summary text (never drop e.g. 'TOTAL TUNISIE')
        if (
            not sym
            or sym in {"VENDRE", "VALEUR", "NOM DE VALEUR", "TOTAUX", "TOTAL"}
            or len(sym) > 50
            or "LIQUIDIT" in sym
            or "TOTAUX" in sym
            or re.match(r"^TOTAL\s+(?:DU\s+)?PORTEFEUILLE$", sym)
        ):
            continue

        if sym in seen_symbols:
            continue

        # Preserve column slots for "..." / empty cells so later columns never shift left!
        slots: list[Decimal | None] = []
        for cell in candidate_num_cells:
            stripped = cell.strip()
            if not stripped or stripped in {"...", "…", "—", "–", "-", "N/A", "na"}:
                slots.append(None)
                continue
            try:
                slots.append(parse_french_number(stripped))
            except ValueError:
                slots.append(None)

        if len(slots) >= 2 and slots[0] is not None and slots[1] is not None:
            try:
                qty = int(slots[0])
                if qty <= 0 or Decimal(qty) != slots[0]:
                    continue
                acq_px = quantize_tnd(slots[1])
                if acq_px <= Decimal("0.000"):
                    continue

                lat_px: Decimal | None = None
                mkt_val: Decimal | None = None
                acq_amt: Decimal | None = None
                gain_tnd: Decimal | None = None
                gain_pct: Decimal | None = None

                # Check if row contains Montant column:
                # [qty, acq_px, montant, dernier, capital, gain, gain%]
                if (
                    len(slots) >= 4
                    and slots[2] is not None
                    and abs(Decimal(qty) * acq_px - slots[2])
                    < max(Decimal("0.05") * abs(slots[2]), Decimal("1.000"))
                ):
                    acq_amt = quantize_tnd(slots[2])
                    if len(slots) >= 5 and slots[4] is not None:
                        mkt_val = quantize_tnd(slots[4])
                    if slots[3] is not None:
                        lat_px = quantize_tnd(slots[3])
                    elif mkt_val is not None:
                        lat_px = quantize_tnd(mkt_val / Decimal(qty))
                    else:
                        lat_px = acq_px
                    if mkt_val is None:
                        mkt_val = quantize_tnd(Decimal(qty) * lat_px)
                    if len(slots) >= 6 and slots[5] is not None:
                        gain_tnd = quantize_tnd(slots[5])
                    if len(slots) >= 7 and slots[6] is not None:
                        gain_pct = quantize_tnd(slots[6])
                else:
                    # Short layout: [qty, acq_px, dernier, capital, gain, gain%]
                    if len(slots) >= 4 and slots[3] is not None:
                        mkt_val = quantize_tnd(slots[3])
                    if len(slots) >= 3 and slots[2] is not None:
                        lat_px = quantize_tnd(slots[2])
                    elif mkt_val is not None:
                        lat_px = quantize_tnd(mkt_val / Decimal(qty))
                    else:
                        lat_px = acq_px
                    if mkt_val is None:
                        mkt_val = quantize_tnd(Decimal(qty) * lat_px)
                    if len(slots) >= 5 and slots[4] is not None:
                        gain_tnd = quantize_tnd(slots[4])
                    if len(slots) >= 6 and slots[5] is not None:
                        gain_pct = quantize_tnd(slots[5])

                if acq_amt is None:
                    acq_amt = quantize_tnd(Decimal(qty) * acq_px)
                if gain_tnd is None:
                    gain_tnd = quantize_tnd(mkt_val - acq_amt)
                if gain_pct is None and acq_amt > Decimal("0.000"):
                    gain_pct = quantize_tnd((gain_tnd / acq_amt) * Decimal("100"))

                seen_symbols.add(sym)
                holdings.append(
                    NormalizedHoldingObservation(
                        symbol=sym,
                        instrument_id=normalize_instrument_id(sym),
                        quantity=qty,
                        acquisition_price_tnd=acq_px,
                        latest_price_tnd=lat_px,
                        market_value_tnd=mkt_val,
                        acquisition_amount_tnd=acq_amt,
                        gain_tnd=gain_tnd,
                        gain_pct=gain_pct,
                        displayed_name=displayed_name or sym,
                    )
                )
            except (ValueError, InvalidOperation):
                continue

    # Compute default cash or equity ONLY when at least one explicit balance was provided
    holdings_sum = sum((h.market_value_tnd for h in holdings), Decimal("0.000"))
    if extracted_cash is None and extracted_equity is not None:
        extracted_cash = max(Decimal("0.000"), extracted_equity - holdings_sum)
    elif extracted_cash is not None and extracted_equity is None:
        extracted_equity = extracted_cash + holdings_sum
    elif extracted_cash is None and extracted_equity is None:
        raise ValueError(
            "Could not extract account cash or portfolio equity from pasted text. "
            "Include 'Liquidités' / 'Votre portefeuille' balances or supply cash/equity overrides."
        )

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
    row_errors: list[str] = []
    meta_cash = cash
    meta_equity = equity

    for row_num, row in enumerate(reader, start=1):
        if not row or not any(c.strip() for c in row):
            continue
        first = " ".join(row[0].strip().upper().split())

        # Check metadata headers strictly without matching stock names like "TOTAL TUNISIE"
        if first in {"CASH", "AVAILABLE_CASH", "LIQUIDITES", "LIQUIDITÉS"} and len(row) <= 3:
            if len(row) >= 2 and row[1].strip():
                meta_cash = quantize_tnd(parse_french_number(row[1]))
            continue
        if (
            first in {"TOTAL", "TOTAUX", "EQUITY", "TOTAL_EQUITY", "TOTAL PORTEFEUILLE"}
            and len(row) <= 3
        ):
            if len(row) >= 2 and row[1].strip():
                meta_equity = quantize_tnd(parse_french_number(row[1]))
            continue
        if (
            any(
                first == h or first.startswith(h + " ")
                for h in ("SYMBOL", "SYMBOLE", "VALEUR", "NOM DE VALEUR", "TITRE", "ACTION")
            )
            or first == "VALEUR"
        ):
            continue

        sym = first
        if not sym:
            continue

        try:
            qty_raw = row[1].replace("\xa0", "").replace("\u202f", "").replace(" ", "").strip()
            qty = int(qty_raw)
            if qty <= 0:
                raise ValueError(f"Quantity must be positive, got '{row[1]}'")
            acq_px = quantize_tnd(parse_french_number(row[2]))
            lat_px = (
                quantize_tnd(parse_french_number(row[3]))
                if len(row) >= 4
                and row[3].strip()
                and row[3].strip() not in {"...", "…", "—", "N/A"}
                else acq_px
            )
            mkt_val = (
                quantize_tnd(parse_french_number(row[4]))
                if len(row) >= 5
                and row[4].strip()
                and row[4].strip() not in {"...", "…", "—", "N/A"}
                else quantize_tnd(Decimal(qty) * lat_px)
            )
            if (
                len(row) >= 4
                and row[3].strip() in {"...", "…"}
                and len(row) >= 5
                and row[4].strip()
            ):
                lat_px = quantize_tnd(mkt_val / Decimal(qty))

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
        except (ValueError, IndexError, InvalidOperation) as exc:
            row_errors.append(f"Row {row_num} ('{sym}'): {exc}")

    if row_errors and not holdings:
        raise ValueError(f"Failed to parse portfolio CSV rows: {'; '.join(row_errors)}")

    holdings_sum = sum((h.market_value_tnd for h in holdings), Decimal("0.000"))
    if meta_cash is None and meta_equity is not None:
        meta_cash = max(Decimal("0.000"), meta_equity - holdings_sum)
    elif meta_cash is not None and meta_equity is None:
        meta_equity = meta_cash + holdings_sum
    elif meta_cash is None and meta_equity is None:
        raise ValueError(
            "CSV portfolio import is missing both cash and equity balances. "
            "Provide CASH/TOTAL metadata rows or cash_override/equity_override."
        )

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
    """Parse CSV containing transaction history from display_histo.aspx with strict validation."""
    text = csv_content.strip()
    if not text:
        raise ValueError("Transactions CSV content is empty.")

    stream = io.StringIO(text)
    sample = text[:1024]
    delimiter = ";" if ";" in sample else ","
    reader = csv.reader(stream, delimiter=delimiter)

    transactions: list[NormalizedTransactionObservation] = []
    row_errors: list[str] = []
    col_map: dict[str, int] = {}
    fallback_dt = datetime.now(UTC)

    for row_num, row in enumerate(reader, start=1):
        if not row or not any(c.strip() for c in row):
            continue
        row_upper = [c.strip().upper() for c in row]
        joined = " ".join(row_upper)

        # Scan full header row for French/English column labels (including RÉF, VALEUR, QUANTITÉ, COURS)
        if any(
            k in joined
            for k in (
                "SYMBOLE",
                "SYMBOL",
                "VALEUR",
                "TITRE",
                "LIBELL",
                "ORDER_ID",
                "TRANSACTION_ID",
            )
        ) and any(
            k in joined for k in ("QUANT", "SHARES", "TITRES", "QTÉ", "QTE", "NOMBRE", "DATE")
        ):
            col_map = {}
            for idx, col in enumerate(row_upper):
                if col in {"ID", "N°", "REF", "RÉF"} or any(
                    k in col for k in ["ORDER_ID", "TRANSACTION_ID", "REF", "RÉF"]
                ):
                    col_map.setdefault("id", idx)
                elif any(k in col for k in ["DATE", "HEURE", "EXECUTED_AT", "SÉANCE", "SEANCE"]):
                    col_map.setdefault("date", idx)
                elif any(k in col for k in ["SYMBOLE", "SYMBOL", "VALEUR", "TITRE", "LIBELL"]):
                    col_map.setdefault("sym", idx)
                elif any(k in col for k in ["SIDE", "SENS", "TYPE", "OPÉRAT", "OPERAT"]):
                    col_map.setdefault("side", idx)
                elif any(k in col for k in ["QUANT", "SHARES", "TITRES", "QTÉ", "QTE", "NOMBRE"]):
                    col_map.setdefault("qty", idx)
                elif any(k in col for k in ["COURS", "PRICE", "PRIX"]):
                    col_map.setdefault("px", idx)
                elif any(k in col for k in ["FRAIS", "FEE", "COMMISSION"]):
                    col_map.setdefault("fee", idx)
            continue

        if len(row) < 5:
            row_errors.append(f"Row {row_num} has fewer than 5 columns.")
            continue

        try:
            id_idx = col_map.get("id", 0)
            tx_id = (
                row[id_idx].strip()
                if id_idx < len(row) and row[id_idx].strip()
                else f"CSV-TX-{row_num}"
            )
            sym_idx = col_map.get("sym", 1 if "date" not in col_map else 2)
            sym = row[sym_idx].strip().upper()
            if not sym:
                raise ValueError("Missing security symbol.")

            date_raw = (
                row[col_map["date"]].strip()
                if "date" in col_map and col_map["date"] < len(row)
                else (row[1].strip() if len(row) > 6 else fallback_dt.isoformat())
            )
            executed_at_iso = _parse_movement_timestamp(date_raw, fallback=fallback_dt)

            side_idx = col_map.get("side", 2 if "date" not in col_map else 3)
            side_raw = row[side_idx] if side_idx < len(row) else ""
            classified_side = _classify_movement_side(side_raw)
            if classified_side not in {"BUY", "SELL"}:
                raise ValueError(f"Unrecognized transaction side '{side_raw}'.")
            side: Literal["BUY", "SELL"] = classified_side  # type: ignore[assignment]

            qty_idx = col_map.get("qty", 3 if "date" not in col_map else 4)
            qty_raw = (
                row[qty_idx].replace("\xa0", "").replace("\u202f", "").replace(" ", "").strip()
            )
            qty = int(qty_raw)
            if qty <= 0:
                raise ValueError(f"Quantity must be positive, got '{qty_raw}'.")

            px_idx = col_map.get("px", 4 if "date" not in col_map else 5)
            px = quantize_tnd(parse_french_number(row[px_idx]))

            fee_idx = col_map.get("fee")
            if fee_idx is None:
                # Positional fee only when header absent and column exists cleanly
                cand_idx = 5 if "date" not in col_map else (6 if len(row) >= 7 else None)
                fee_idx = cand_idx
            fees = (
                quantize_tnd(parse_french_number(row[fee_idx]))
                if fee_idx is not None and fee_idx < len(row) and row[fee_idx].strip()
                else Decimal("0.000")
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
                    executed_at=executed_at_iso,
                )
            )
        except (ValueError, IndexError, InvalidOperation) as exc:
            row_errors.append(f"Row {row_num}: {exc}")

    if row_errors and not transactions:
        raise ValueError(f"Failed to parse transactions CSV: {'; '.join(row_errors)}")
    if not transactions:
        raise ValueError("No valid transaction rows found in CSV content.")
    if row_errors:
        raise ValueError(f"Malformed transaction CSV row(s): {'; '.join(row_errors)}")

    return transactions
