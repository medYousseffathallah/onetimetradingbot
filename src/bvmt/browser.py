"""Secure, local-first, read-only Playwright browser collector and DOM parser for Tunis Bourse Challenge.

No remote browser service, no cloud credential storage, no automated login or password extraction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_CHALLENGE_URL = "https://www.tunisbourse-challenge.com/displayp.aspx"
DEFAULT_LOGIN_URL = "https://www.tunisbourse-challenge.com/"
DEFAULT_ROUNDING_TOLERANCE_TND = Decimal("0.05")


class BrowserCollectorError(Exception):
    """Base exception for browser collection and DOM parsing errors."""


class AuthenticationExpiredError(BrowserCollectorError):
    """Raised when the session is expired or the page redirects to login."""


class LayoutChangedError(BrowserCollectorError):
    """Raised when the expected HTML table structure or fields cannot be found."""


class BalanceMismatchError(BrowserCollectorError):
    """Raised when cash + holdings market value does not match reported total."""


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
        perf = data.get("displayed_overall_performance_pct")
        rank = data.get("competition_rank")
        participants = data.get("total_participants")
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
        )


def parse_french_number(raw: str) -> Decimal:
    """Parse French numbers with comma decimals, space thousand separators, and currency/percent suffixes."""
    cleaned = raw.strip()
    for token in ("DT", "dt", "%", "+", "\xa0"):
        cleaned = cleaned.replace(token, "")
    # Remove interior spaces used as thousand separators, then normalize comma to period
    cleaned = cleaned.replace(" ", "").replace(",", ".").strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Cannot parse numeric value from '{raw}': {exc}") from exc


class _SimpleDOMTableParser(HTMLParser):
    """Lightweight pure-Python DOM table and text extractor for displayp.aspx."""

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


def parse_competition_portfolio_html(
    html_content: str,
    *,
    source_url: str = DEFAULT_CHALLENGE_URL,
    retrieved_at: datetime | None = None,
    tolerance_tnd: Decimal = DEFAULT_ROUNDING_TOLERANCE_TND,
) -> CompetitionPortfolioDOMSnapshot:
    """Parse authenticated displayp.aspx HTML into structured snapshot.

    Validates balance: cash + holdings market value == reported total within tolerance.
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
    # Search tables for column headers: Nom de valeur, Quantité, Prix, Montant, Dernier, Capital
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
                # Check if 2nd cell or 1st cell looks like an instrument name
                # and 3rd/4th has integer quantity and decimal prices
                name_cand = row[1] if len(row) > 7 else row[0]
                # Filter out header rows
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
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserCollectorError(
            "Playwright is not installed in .venv. Install with: uv pip install playwright"
        ) from exc

    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            channel="chrome",  # Uses local Chrome installation if available, falls back to chromium
            viewport={"width": 1280, "height": 800},
        )
        try:
            page = context.new_page() if not context.pages else context.pages[0]
            page.goto(target_url)

            # Wait for user to log in and navigate to displayp.aspx (looking for portfolio table or text)
            # Timeout in milliseconds
            page.wait_for_selector(
                "text=Votre portefeuille",
                timeout=timeout_seconds * 1000,
            )
            html_content = page.content()
            return html_content
        finally:
            context.close()
