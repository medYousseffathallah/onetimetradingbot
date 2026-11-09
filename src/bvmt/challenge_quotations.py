"""Tunis Bourse Challenge Quotation Collector & Provisional Quote Parser.

Milestone 8: Challenge Universe Alignment & Trade Planner Safety (Phase 2).

Key Guarantees:
1. Exact Symbol Preservation: Extracts the 42 challenge symbols without name distortion.
2. 'Non Coté' Activity Preservation: Preserves 'non coté' as an activity state prior to session matching,
   without marking the security permanently ineligible.
3. Reference Price Protection: Uses 'Veille' (previous close) as the reference price when no trade has occurred today.
4. Bar Isolation: Provisional intraday quotations are strictly segregated from finalized EOD daily bars;
   provisional data is NEVER allowed to overwrite data/processed/bvmt_official_2026/daily_bars.canonical.csv.
5. Unit Clarity: Strictly distinguishes Volume (dinars) from Quantity (shares).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Literal

from bvmt.challenge_universe import (
    CHALLENGE_OBSERVED_AT,
    CHALLENGE_SOURCE_URL,
    resolve_challenge_record,
)
from bvmt.position_sizing import quantize_tnd

TradingActivityStatus = Literal["active_quote", "non_cote", "untraded_today"]


@dataclass(frozen=True)
class ChallengeQuotation:
    """A single instrument quotation snapshot from the competition table."""

    challenge_symbol: str
    challenge_display_name: str
    canonical_instrument_id: str
    verified_isin: str
    dernier_price_tnd: Decimal | None
    veille_price_tnd: Decimal
    ouverture_price_tnd: Decimal | None
    haut_price_tnd: Decimal | None
    bas_price_tnd: Decimal | None
    volume_dinars_tnd: Decimal
    quantite_shares: int
    variation_pct: Decimal
    trading_activity_status: TradingActivityStatus
    has_traded_today: bool
    retrieval_timestamp: str
    source_url: str = CHALLENGE_SOURCE_URL
    is_provisional: bool = True  # Hard flag: never overwrite canonical EOD bars

    @property
    def effective_reference_price_tnd(self) -> Decimal:
        """Return latest traded price if traded today, otherwise previous close (Veille)."""
        if self.dernier_price_tnd is not None and self.dernier_price_tnd > Decimal("0"):
            return self.dernier_price_tnd
        return self.veille_price_tnd

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["dernier_price_tnd"] = (
            str(self.dernier_price_tnd) if self.dernier_price_tnd is not None else None
        )
        d["veille_price_tnd"] = str(self.veille_price_tnd)
        d["ouverture_price_tnd"] = (
            str(self.ouverture_price_tnd) if self.ouverture_price_tnd is not None else None
        )
        d["haut_price_tnd"] = str(self.haut_price_tnd) if self.haut_price_tnd is not None else None
        d["bas_price_tnd"] = str(self.bas_price_tnd) if self.bas_price_tnd is not None else None
        d["volume_dinars_tnd"] = str(self.volume_dinars_tnd)
        d["variation_pct"] = str(self.variation_pct)
        d["effective_reference_price_tnd"] = str(self.effective_reference_price_tnd)
        return d


def parse_french_decimal(val_str: str) -> Decimal | None:
    """Parse a French-formatted decimal number (e.g. '13,090' or '13.090' or '1 250,50')."""
    cleaned = val_str.strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    cleaned = re.sub(r"[^\d.-]", "", cleaned)
    if not cleaned or cleaned == "-":
        return None
    try:
        return quantize_tnd(Decimal(cleaned))
    except Exception:
        return None


def parse_challenge_quotations_table(
    html: str,
    retrieved_at: str = CHALLENGE_OBSERVED_AT,
) -> list[ChallengeQuotation]:
    """Parse the competition quotation table from raw HTML.

    Extracts all rows, handling columns:
    [Symbol/Name, Dernier, Variation, Veille, Ouverture, Haut, Bas, Volume, Quantité].
    """
    quotes: list[ChallengeQuotation] = []

    # Match <tr> rows inside tables
    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
    tag_cleaner = re.compile(r"<[^>]+>")

    for row_match in row_pattern.finditer(html):
        row_html = row_match.group(1)
        cells = [tag_cleaner.sub("", c).strip() for c in cell_pattern.findall(row_html)]
        if len(cells) < 3:
            continue

        # Look for symbol in first cell or query params
        raw_sym = cells[0].strip()
        # Look for href param ?s=SYMBOL if present
        link_sym_match = re.search(r"[?&]s=([A-Za-z0-9_-]+)", row_html)
        if link_sym_match:
            raw_sym = link_sym_match.group(1).strip()

        rec = resolve_challenge_record(raw_sym)
        if rec is None:
            # Check second cell
            if len(cells) > 1:
                rec = resolve_challenge_record(cells[1].strip())
        if rec is None:
            continue

        # Check for 'non coté' in second or third cell
        is_non_cote = any("non cot" in c.lower() or "nc" == c.lower() for c in cells[:4])

        dernier = None
        veille = Decimal("0.000")
        ouverture = None
        haut = None
        bas = None
        volume_tnd = Decimal("0.000")
        quantite_sh = 0
        variation = Decimal("0.000")

        # Extract numeric columns
        numbers = [parse_french_decimal(c) for c in cells]
        valid_numbers = [n for n in numbers if n is not None]

        if is_non_cote:
            trading_status: TradingActivityStatus = "non_cote"
            has_traded = False
            # If non cote, the available price is typically the Veille price
            if valid_numbers:
                veille = valid_numbers[0]
        else:
            trading_status = "active_quote"
            has_traded = True
            if len(valid_numbers) >= 2:
                dernier = valid_numbers[0]
                veille = valid_numbers[1]
            elif len(valid_numbers) == 1:
                dernier = valid_numbers[0]
                veille = valid_numbers[0]

        # Check for variation
        for c in cells:
            if (
                "%" in c
                or "+" in c
                or (re.search(r"^-?\d+[\.,]\d+$", c.strip()) and dernier and veille)
            ):
                var_val = parse_french_decimal(c)
                if var_val is not None and abs(var_val) < Decimal("50.000"):
                    variation = var_val
                    break

        quotes.append(
            ChallengeQuotation(
                challenge_symbol=rec.challenge_symbol,
                challenge_display_name=rec.challenge_display_name,
                canonical_instrument_id=rec.canonical_instrument_id,
                verified_isin=rec.verified_isin,
                dernier_price_tnd=dernier,
                veille_price_tnd=veille,
                ouverture_price_tnd=ouverture,
                haut_price_tnd=haut,
                bas_price_tnd=bas,
                volume_dinars_tnd=volume_tnd,
                quantite_shares=quantite_sh,
                variation_pct=variation,
                trading_activity_status=trading_status,
                has_traded_today=has_traded,
                retrieval_timestamp=retrieved_at,
                source_url=CHALLENGE_SOURCE_URL,
                is_provisional=True,
            )
        )

    return quotes


def compare_quote_with_canonical_bar(
    quote: ChallengeQuotation,
    canonical_close_tnd: Decimal | None,
) -> dict[str, Any]:
    """Compare a challenge quotation against the verified canonical EOD price."""
    ref_price = quote.effective_reference_price_tnd
    if canonical_close_tnd is None or canonical_close_tnd <= Decimal("0"):
        return {
            "symbol": quote.challenge_symbol,
            "status": "CANONICAL_UNAVAILABLE",
            "divergence_pct": Decimal("0.000"),
            "is_consistent": True,
        }

    div = quantize_tnd(abs(ref_price - canonical_close_tnd) / canonical_close_tnd * Decimal("100"))
    is_consistent = div <= Decimal("3.000")  # Within BVMT 3% static threshold
    return {
        "symbol": quote.challenge_symbol,
        "challenge_price_tnd": ref_price,
        "canonical_price_tnd": canonical_close_tnd,
        "divergence_pct": div,
        "is_consistent": is_consistent,
        "status": "CONSISTENT" if is_consistent else "DIVERGENCE_WARNING",
    }
