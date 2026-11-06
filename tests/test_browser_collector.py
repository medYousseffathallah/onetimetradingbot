"""Tests for Playwright browser collector and DOM parser for Tunis Bourse Challenge."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.browser import (
    AuthenticationExpiredError,
    BalanceMismatchError,
    LayoutChangedError,
    load_latest_browser_snapshot,
    parse_competition_portfolio_html,
    parse_french_number,
    save_browser_snapshot,
)

# Deterministic fixture mirroring the user's verified screenshot
VERIFIED_SCREENSHOT_HTML_FIXTURE = """
<!DOCTYPE html>
<html>
<head><title>Tunisbourse Challenge - Mon Portefeuille</title></head>
<body>
<div class="portefeuille-header">
    <h3>Mon portefeuille</h3>
    <p>Tunisbourse Challenge est ouvert, il se déroule du 1er octobre 2026 au 31 mai 2027.</p>
    <div class="metrics">
        <span>Votre portefeuille : 49998,05 DT</span>
        <span>Votre classement : 4813 / 14530</span>
        <span>Performance générale : +0,00%</span>
    </div>
</div>

<div class="valeurs-section">
    <h3>Mes valeurs</h3>
    <table id="table-valeurs">
        <thead>
            <tr>
                <th>Vendre</th>
                <th>Nom de valeur</th>
                <th>Quantité</th>
                <th>Prix</th>
                <th>Montant</th>
                <th>Dernier</th>
                <th>Capital</th>
                <th>Gain (dt)</th>
                <th>Gain(%)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><button>vendre</button></td>
                <td>BH BANK</td>
                <td>30</td>
                <td>13.065</td>
                <td>391.95</td>
                <td>13.00</td>
                <td>390.00</td>
                <td>-1.95</td>
                <td>-0.50%</td>
            </tr>
            <tr class="liquidites-row">
                <td colspan="6">Liquidités</td>
                <td>49608.05</td>
                <td colspan="2"></td>
            </tr>
            <tr class="totaux-row">
                <td colspan="6">Totaux</td>
                <td>49998.05</td>
                <td>-1.95</td>
                <td>0.00%</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""

# Fixture with multiple holdings
MULTIPLE_HOLDINGS_HTML_FIXTURE = """
<!DOCTYPE html>
<html>
<body>
<div class="header">
    <p>Tunisbourse Challenge est ouvert, il se déroule du 1er octobre 2026 au 31 mai 2027.</p>
    <div>Votre portefeuille : 52 350,50 DT</div>
    <div>Votre classement : 120 / 14530</div>
    <div>Performance générale : +4,70%</div>
</div>
<table>
    <thead>
        <tr>
            <th>Vendre</th><th>Nom de valeur</th><th>Quantité</th><th>Prix</th><th>Montant</th><th>Dernier</th><th>Capital</th><th>Gain (dt)</th><th>Gain(%)</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><button>vendre</button></td>
            <td>BH BANK</td>
            <td>30</td>
            <td>13,065</td>
            <td>391,95</td>
            <td>13,50</td>
            <td>405,00</td>
            <td>13,05</td>
            <td>3,33%</td>
        </tr>
        <tr>
            <td><button>vendre</button></td>
            <td>SFBT</td>
            <td>100</td>
            <td>12,000</td>
            <td>1200,00</td>
            <td>12,50</td>
            <td>1250,00</td>
            <td>50,00</td>
            <td>4,17%</td>
        </tr>
        <tr>
            <td colspan="6">Liquidités</td>
            <td>50 695,50</td>
            <td colspan="2"></td>
        </tr>
        <tr>
            <td colspan="6">Totaux</td>
            <td>52 350,50</td>
            <td>63,05</td>
            <td>4,70%</td>
        </tr>
    </tbody>
</table>
</body>
</html>
"""

# Fixture with 0 holdings (all cash)
EMPTY_HOLDINGS_HTML_FIXTURE = """
<!DOCTYPE html>
<html>
<body>
<div>Votre portefeuille : 50000,00 DT</div>
<div>Votre classement : 5000 / 14530</div>
<div>Performance générale : 0,00%</div>
<table>
    <thead>
        <tr>
            <th>Vendre</th><th>Nom de valeur</th><th>Quantité</th><th>Prix</th><th>Montant</th><th>Dernier</th><th>Capital</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td colspan="6">Liquidités</td>
            <td>50000,00</td>
        </tr>
    </tbody>
</table>
</body>
</html>
"""

# Expired session / login redirect fixture
EXPIRED_SESSION_HTML_FIXTURE = """
<!DOCTYPE html>
<html>
<head><title>Connexion - Tunisbourse Challenge</title></head>
<body>
<div class="login-box">
    <h2>Connectez-vous à votre espace</h2>
    <form action="/login.aspx" method="post">
        <label>Identifiant:</label><input type="text" name="username" />
        <label>Mot de passe:</label><input type="password" name="password" />
        <button type="submit">Connexion</button>
    </form>
</div>
</body>
</html>
"""

# Balance mismatch fixture
BALANCE_MISMATCH_HTML_FIXTURE = """
<!DOCTYPE html>
<html>
<body>
<div>Votre portefeuille : 49998,05 DT</div>
<table>
    <tbody>
        <tr>
            <td><button>vendre</button></td>
            <td>BH BANK</td>
            <td>30</td>
            <td>13.065</td>
            <td>391.95</td>
            <td>13.00</td>
            <td>390.00</td>
        </tr>
        <tr>
            <td colspan="6">Liquidités</td>
            <td>40000.00</td> <!-- Intentionally mismatched cash: 40000 + 390 != 49998.05 -->
        </tr>
    </tbody>
</table>
</body>
</html>
"""


def test_french_number_parser():
    assert parse_french_number("49998,05 DT") == Decimal("49998.05")
    assert parse_french_number("49 608,05 dt") == Decimal("49608.05")
    assert parse_french_number("13.065") == Decimal("13.065")
    assert parse_french_number("-1,95") == Decimal("-1.95")
    assert parse_french_number("+0,00%") == Decimal("0.00")
    assert parse_french_number("12 345,678") == Decimal("12345.678")
    with pytest.raises(ValueError, match="Cannot parse numeric"):
        parse_french_number("invalid_text")


def test_parse_verified_screenshot_fixture():
    t0 = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
    snap = parse_competition_portfolio_html(VERIFIED_SCREENSHOT_HTML_FIXTURE, retrieved_at=t0)

    assert snap.portfolio_total_tnd == Decimal("49998.05")
    assert snap.available_cash_tnd == Decimal("49608.05")
    assert snap.holdings_market_value_tnd == Decimal("390.00")
    assert snap.competition_rank == 4813
    assert snap.total_participants == 14530
    assert snap.displayed_overall_performance_pct == Decimal("0.00")
    assert snap.is_reconciled is True
    assert snap.reconciliation_gap_tnd == Decimal("0.00")
    assert "Tunisbourse Challenge est ouvert" in snap.challenge_period_text

    assert len(snap.holdings) == 1
    bh = snap.holdings[0]
    assert bh.symbol == "BH BANK"
    assert bh.quantity == 30
    assert bh.acquisition_price_tnd == Decimal("13.065")
    assert bh.acquisition_amount_tnd == Decimal("391.95")
    assert bh.latest_price_tnd == Decimal("13.00")
    assert bh.market_value_tnd == Decimal("390.00")
    assert bh.gain_tnd == Decimal("-1.95")
    assert bh.gain_pct == Decimal("-0.50")


def test_parse_multiple_holdings_and_french_formatting():
    snap = parse_competition_portfolio_html(MULTIPLE_HOLDINGS_HTML_FIXTURE)
    assert snap.portfolio_total_tnd == Decimal("52350.50")
    assert snap.available_cash_tnd == Decimal("50695.50")
    assert snap.holdings_market_value_tnd == Decimal("1655.00")  # 405 + 1250
    assert snap.competition_rank == 120
    assert snap.total_participants == 14530
    assert snap.displayed_overall_performance_pct == Decimal("4.70")
    assert snap.is_reconciled is True
    assert len(snap.holdings) == 2

    bh = snap.holdings[0]
    assert bh.symbol == "BH BANK"
    assert bh.quantity == 30
    assert bh.latest_price_tnd == Decimal("13.50")

    sfbt = snap.holdings[1]
    assert sfbt.symbol == "SFBT"
    assert sfbt.quantity == 100
    assert sfbt.market_value_tnd == Decimal("1250.00")


def test_parse_empty_holdings():
    snap = parse_competition_portfolio_html(EMPTY_HOLDINGS_HTML_FIXTURE)
    assert snap.portfolio_total_tnd == Decimal("50000.00")
    assert snap.available_cash_tnd == Decimal("50000.00")
    assert snap.holdings_market_value_tnd == Decimal("0.000")
    assert len(snap.holdings) == 0
    assert snap.is_reconciled is True


def test_authentication_expired_error():
    with pytest.raises(AuthenticationExpiredError, match="Session expired"):
        parse_competition_portfolio_html(EXPIRED_SESSION_HTML_FIXTURE)


def test_balance_mismatch_error():
    with pytest.raises(BalanceMismatchError, match="Balance mismatch"):
        parse_competition_portfolio_html(BALANCE_MISMATCH_HTML_FIXTURE)


def test_layout_changed_error():
    broken_html = "<html><body><div>Some other page without portfolio content</div></body></html>"
    with pytest.raises(LayoutChangedError, match="Could not locate 'Votre portefeuille'"):
        parse_competition_portfolio_html(broken_html)


def test_save_and_load_browser_snapshot(tmp_path: Path):
    t0 = datetime(2026, 11, 6, 13, 0, 0, tzinfo=UTC)
    snap = parse_competition_portfolio_html(VERIFIED_SCREENSHOT_HTML_FIXTURE, retrieved_at=t0)

    saved_path = save_browser_snapshot(snap, tmp_path)
    assert saved_path.exists()
    assert saved_path.name.startswith("sync_20261106_130000.json")

    loaded = load_latest_browser_snapshot(tmp_path)
    assert loaded is not None
    assert loaded.portfolio_total_tnd == snap.portfolio_total_tnd
    assert loaded.available_cash_tnd == snap.available_cash_tnd
    assert len(loaded.holdings) == 1
    assert loaded.holdings[0].symbol == "BH BANK"
    assert loaded.is_reconciled is True
