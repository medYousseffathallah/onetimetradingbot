"""Unit test suite for the Manual Import Fallback Parser (Milestone 10, Phase 2).

Covers:
- French number parsing (spaces, DT, commas, invalid strings).
- HTML table parsing from Tunis Bourse Challenge displayp.aspx.
- Plain text table parsing (tab-separated, semicolon-separated).
- Holdings CSV import with header detection.
- Transaction history CSV import from display_histo.aspx.
- Cash, equity, and rank override handling.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bvmt.manual_import import (
    parse_french_number,
    parse_manual_portfolio_csv,
    parse_manual_portfolio_paste,
    parse_manual_transactions_csv,
)


def test_parse_french_number() -> None:
    assert parse_french_number("19 095,000") == Decimal("19095.000")
    assert parse_french_number("19,095") == Decimal("19.095")
    assert parse_french_number(" 44 586,070 DT ") == Decimal("44586.070")
    assert parse_french_number("0,000") == Decimal("0.000")
    assert parse_french_number("12.500") == Decimal("12.500")

    with pytest.raises(ValueError):
        parse_french_number("")

    with pytest.raises(ValueError):
        parse_french_number("abc")


def test_parse_manual_portfolio_paste_plain_text() -> None:
    raw = """
    Total du portefeuille : 49 979,070 DT
    Liquidités : 44 586,070 DT
    Rang : #133 / 14 547

    Valeur	Quantité	Prix d'achat	Dernier cours	Total
    BH BANK	30	13,067	13,090	392,700
    DELICE HOLDING	263	19,011	19,000	4 997,000
    """

    obs = parse_manual_portfolio_paste(raw)
    assert obs.source == "MANUAL_PASTE"
    assert obs.account_equity == Decimal("49979.070")
    assert obs.available_cash == Decimal("44586.070")
    assert obs.competition_ranking == 133
    assert obs.total_participants == 14547
    assert len(obs.holdings) == 2

    bh = obs.holdings[0]
    assert bh.symbol == "BH_BANK" or "BH" in bh.symbol
    assert bh.quantity == 30
    assert bh.acquisition_price_tnd == Decimal("13.067")
    assert bh.market_value_tnd == Decimal("392.700")

    dh = obs.holdings[1]
    assert "DELICE" in dh.symbol
    assert dh.quantity == 263
    assert dh.acquisition_price_tnd == Decimal("19.011")
    assert dh.latest_price_tnd == Decimal("19.000")
    assert dh.market_value_tnd == Decimal("4997.000")


def test_parse_manual_portfolio_paste_html() -> None:
    html = """
    <div>
        <p>Liquidités : 49 608,050 DT</p>
        <p>Total portefeuille : 50 000,750 DT</p>
        <p>Classement : #118 / 14 500</p>
        <table id="tab_portefeuille">
            <thead>
                <tr><th>Symbole</th><th>Quantité</th><th>Prix Achat</th><th>Dernier</th><th>Total</th></tr>
            </thead>
            <tbody>
                <tr><td>BH</td><td>30</td><td>13,067</td><td>13,090</td><td>392,700</td></tr>
            </tbody>
        </table>
    </div>
    """

    obs = parse_manual_portfolio_paste(html)
    assert obs.account_equity == Decimal("50000.750")
    assert obs.available_cash == Decimal("49608.050")
    assert obs.competition_ranking == 118
    assert len(obs.holdings) == 1
    assert obs.holdings[0].symbol == "BH"
    assert obs.holdings[0].quantity == 30
    assert obs.holdings[0].market_value_tnd == Decimal("392.700")


def test_parse_manual_portfolio_csv() -> None:
    csv_content = """
    # Metadonnées
    CASH;44586.070
    TOTAL_EQUITY;49979.070
    # Portefeuille
    SYMBOL;QUANTITY;ACQUISITION_PRICE;LATEST_PRICE;MARKET_VALUE
    BH;30;13.067;13.090;392.700
    DH;263;19.011;19.000;4997.000
    """

    obs = parse_manual_portfolio_csv(csv_content)
    assert obs.source == "CSV_IMPORT"
    assert obs.available_cash == Decimal("44586.070")
    assert obs.account_equity == Decimal("49979.070")
    assert len(obs.holdings) == 2
    assert obs.holdings[0].symbol == "BH"
    assert obs.holdings[1].symbol == "DH"


def test_parse_manual_transactions_csv() -> None:
    csv_content = """
    ORDER_ID;SYMBOL;SIDE;SHARES;PRICE;FEE;EXECUTED_AT
    1001;BH;ACHAT;30;13.067;0.700;2026-11-06 10:30:00
    1002;DH;ACHAT;263;19.011;1.200;2026-11-06 11:15:00
    """

    txs = parse_manual_transactions_csv(csv_content)
    assert len(txs) == 2
    assert txs[0].symbol == "BH"
    assert txs[0].side == "BUY"
    assert txs[0].filled_shares == 30
    assert txs[0].execution_price_tnd == Decimal("13.067")
    assert txs[0].fee_tnd == Decimal("0.700")

    assert txs[1].symbol == "DH"
    assert txs[1].side == "BUY"
    assert txs[1].filled_shares == 263
    assert txs[1].execution_price_tnd == Decimal("19.011")


def test_parse_manual_paste_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_manual_portfolio_paste("   ")
