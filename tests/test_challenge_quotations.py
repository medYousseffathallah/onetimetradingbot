"""Unit tests for Tunis Bourse Challenge Quotation Parser (Milestone 8 Phase 2)."""

from __future__ import annotations

from decimal import Decimal

from bvmt.challenge_quotations import (
    ChallengeQuotation,
    compare_quote_with_canonical_bar,
    parse_challenge_quotations_table,
    parse_french_decimal,
)


def test_parse_french_decimal():
    """Verify parsing of various French numeric formats."""
    assert parse_french_decimal("13,090") == Decimal("13.090")
    assert parse_french_decimal("115.900") == Decimal("115.900")
    assert parse_french_decimal("1 250,50") == Decimal("1250.500")
    assert parse_french_decimal(" - ") is None
    assert parse_french_decimal("non coté") is None


def test_parse_quotations_table_with_active_and_non_cote():
    """Verify parsing of HTML table containing both active traded rows and pre-market 'non coté' rows."""
    html_sample = """
    <table class="table-cotations">
        <thead>
            <tr><th>Valeur</th><th>Dernier</th><th>Veille</th><th>Variation</th></tr>
        </thead>
        <tbody>
            <tr>
                <td><a href="cotation.aspx?s=STA">STA</a></td>
                <td>115,900</td>
                <td>114,500</td>
                <td>+1.22%</td>
            </tr>
            <tr>
                <td><a href="cotation.aspx?s=BH">BH</a></td>
                <td>13,090</td>
                <td>13,065</td>
                <td>+0.19%</td>
            </tr>
            <tr>
                <td><a href="cotation.aspx?s=SMART">SMART</a></td>
                <td>non coté</td>
                <td>37,890</td>
                <td>0.00%</td>
            </tr>
        </tbody>
    </table>
    """
    quotes = parse_challenge_quotations_table(html_sample, retrieved_at="2026-11-09T09:15:00+01:00")
    assert len(quotes) == 3

    # STA: Traded quote
    sta_q = next(q for q in quotes if q.challenge_symbol == "STA")
    assert sta_q.dernier_price_tnd == Decimal("115.900")
    assert sta_q.veille_price_tnd == Decimal("114.500")
    assert sta_q.trading_activity_status == "active_quote"
    assert sta_q.has_traded_today is True
    assert sta_q.effective_reference_price_tnd == Decimal("115.900")
    assert sta_q.is_provisional is True

    # BH: Traded quote
    bh_q = next(q for q in quotes if q.challenge_symbol == "BH")
    assert bh_q.dernier_price_tnd == Decimal("13.090")
    assert bh_q.canonical_instrument_id == "BH_BANK"

    # SMART: Non coté (pre-market unexecuted)
    smart_q = next(q for q in quotes if q.challenge_symbol == "SMART")
    assert smart_q.dernier_price_tnd is None
    assert smart_q.trading_activity_status == "non_cote"
    assert smart_q.has_traded_today is False
    # Preserves Veille price as effective reference price
    assert smart_q.effective_reference_price_tnd == Decimal("37.890")
    assert smart_q.is_provisional is True


def test_quote_comparison_with_canonical_bars():
    """Verify comparison between provisional challenge quote and canonical EOD bars."""
    quote = ChallengeQuotation(
        challenge_symbol="STA",
        challenge_display_name="STA",
        canonical_instrument_id="STA",
        verified_isin="TNNGTFLC2986",
        dernier_price_tnd=Decimal("115.900"),
        veille_price_tnd=Decimal("115.900"),
        ouverture_price_tnd=Decimal("115.900"),
        haut_price_tnd=Decimal("116.000"),
        bas_price_tnd=Decimal("115.500"),
        volume_dinars_tnd=Decimal("25500.000"),
        quantite_shares=220,
        variation_pct=Decimal("0.000"),
        trading_activity_status="active_quote",
        has_traded_today=True,
        retrieval_timestamp="2026-11-09T09:30:00+01:00",
    )

    # Identical price -> consistent
    cmp_res = compare_quote_with_canonical_bar(quote, Decimal("115.900"))
    assert cmp_res["is_consistent"] is True
    assert cmp_res["divergence_pct"] == Decimal("0.000")
    assert cmp_res["status"] == "CONSISTENT"

    # Divergent price (e.g. 5% move beyond 3% threshold)
    cmp_div = compare_quote_with_canonical_bar(quote, Decimal("122.000"))
    assert cmp_div["is_consistent"] is False
    assert cmp_div["status"] == "DIVERGENCE_WARNING"

