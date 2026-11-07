"""Tests for Playwright browser collector and DOM parser for Tunis Bourse Challenge."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.browser import (
    AuthenticationExpiredError,
    BalanceMismatchError,
    BrowserCollectorError,
    LayoutChangedError,
    load_latest_browser_snapshot,
    parse_competition_movements_html,
    parse_competition_portfolio_html,
    parse_french_number,
    save_browser_snapshot,
    validate_readonly_challenge_url,
)
from bvmt.dashboard import (
    apply_confirmed_browser_sync_to_state,
    build_dashboard_state,
    evaluate_account_sync_freshness,
)
from bvmt.ledger import load_screenshot_snapshot

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
    <tbody class="alri">
        <tr>
            <td><button>vendre</button></td>
            <td>BH BANK</td>
            <td>30</td>
            <td>13.065</td>
            <td>391.95</td>
            <td>13.00</td>
            <td>390.00</td><td>-1.95</td><td>-0.50%</td>
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


MOVEMENTS_HTML_FIXTURE = """
<!DOCTYPE html>
<html>
<head><title>Tunisbourse Challenge - Mouvements</title></head>
<body>
<div class="movements-section">
    <h3>Mouvements</h3>
    <table id="table-mouvements">
        <thead>
            <tr>
                <th>Réf</th>
                <th>Date</th>
                <th>Nom de valeur</th>
                <th>Opération</th>
                <th>Quantité</th>
                <th>Cours</th>
                <th>Frais</th>
                <th>Statut</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>1001</td>
                <td>03/11/2026 10:15</td>
                <td>BH BANK</td>
                <td>Achat</td>
                <td>30</td>
                <td>13,000</td>
                <td>1,950</td>
                <td>Exécuté</td>
            </tr>
            <tr>
                <td>1002</td>
                <td>06/11/2026 11:30</td>
                <td>SFBT</td>
                <td>Achat</td>
                <td>50</td>
                <td>12,400</td>
                <td>3,100</td>
                <td>En cours</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""


def test_validate_readonly_challenge_url():
    assert (
        validate_readonly_challenge_url("https://www.tunisbourse-challenge.com/displayp.aspx")
        == "https://www.tunisbourse-challenge.com/displayp.aspx"
    )
    assert (
        validate_readonly_challenge_url("https://www.tunisbourse-challenge.com/display_histo.aspx")
        == "https://www.tunisbourse-challenge.com/display_histo.aspx"
    )
    with pytest.raises(BrowserCollectorError, match="Forbidden trading endpoint"):
        validate_readonly_challenge_url("https://www.tunisbourse-challenge.com/bysell.aspx")
    with pytest.raises(BrowserCollectorError, match="Untrusted or non-competition URL"):
        validate_readonly_challenge_url("https://evil.example.com/displayp.aspx")


def test_parse_competition_movements_html():
    t0 = datetime(2026, 11, 6, 15, 0, 0, tzinfo=UTC)
    txs, pends = parse_competition_movements_html(MOVEMENTS_HTML_FIXTURE, retrieved_at=t0)
    assert len(txs) == 1
    assert txs[0].symbol == "BH BANK"
    assert txs[0].instrument_id == "BH_BANK"
    assert txs[0].side == "BUY"
    assert txs[0].filled_shares == 30
    assert txs[0].execution_price_tnd == Decimal("13.000")
    assert txs[0].fee_tnd == Decimal("1.950")
    assert txs[0].executed_at == "2026-11-03T10:15:00+01:00"

    assert len(pends) == 1
    assert pends[0].symbol == "SFBT"
    assert pends[0].instrument_id == "SFBT"
    assert pends[0].side == "BUY"
    assert pends[0].requested_shares == 50
    assert pends[0].remaining_shares == 50
    assert pends[0].limit_price_tnd == Decimal("12.400")
    assert pends[0].status == "PENDING"


def test_browser_sync_confirmation_reconciliation_and_restart_persistence(tmp_path: Path):
    ledger_p = tmp_path / "real_competition_ledger.json"
    baseline_snap_p = tmp_path / "real_account_snapshot.json"
    alerts_p = tmp_path / "alerts.json"

    # 1. Initialize dashboard state in REAL_COMPETITION mode (creates baseline_snap_p)
    state = build_dashboard_state(
        ledger_path=ledger_p,
        alerts_path=alerts_p,
        portfolio_mode="REAL_COMPETITION",
        real_snapshot_path=baseline_snap_p,
    )
    assert baseline_snap_p.exists()
    original_baseline = load_screenshot_snapshot(baseline_snap_p)
    assert original_baseline.snapshot_id == "SNAP-TBC-USER-001"

    # Verify undated baseline triggers stale account warning
    freshness_before = evaluate_account_sync_freshness(state.account_snapshot, "2026-11-06")
    assert freshness_before["is_stale"] is True
    assert "Stale Account Warning" in str(freshness_before["warning_message"])

    # 2. Parse a new browser sync snapshot with movements (e.g. updated price/holdings + movements)
    sync_time = datetime(2026, 11, 6, 16, 30, 0, tzinfo=UTC)
    dom_snap = parse_competition_portfolio_html(
        MULTIPLE_HOLDINGS_HTML_FIXTURE,
        retrieved_at=sync_time,
        movements_html=MOVEMENTS_HTML_FIXTURE,
        movements_source_url="https://www.tunisbourse-challenge.com/display_histo.aspx",
    )
    assert dom_snap.movements_page_captured is True
    assert len(dom_snap.transactions) == 1
    assert len(dom_snap.pending_orders) == 1

    # 3. Unconfirmed apply must be rejected without mutating state
    with pytest.raises(ValueError, match="Explicit user confirmation"):
        apply_confirmed_browser_sync_to_state(state, dom_snap, confirmed_by_user=False)
    assert state.ledger.settled_cash_tnd == Decimal("49608.050")

    # 4. Confirmed apply reconciles cash, holdings, transactions, pending orders, and persists to disk
    recon_rep = apply_confirmed_browser_sync_to_state(state, dom_snap, confirmed_by_user=True)
    assert recon_rep.account_settled_cash_tnd == Decimal("50695.500")
    assert ledger_p.exists()

    # Original baseline screenshot file MUST remain untouched
    baseline_after = load_screenshot_snapshot(baseline_snap_p)
    assert baseline_after.snapshot_id == "SNAP-TBC-USER-001"
    assert baseline_after.available_cash_tnd == Decimal("49608.050")

    # 5. Simulate full dashboard restart by calling build_dashboard_state from disk
    restarted_state = build_dashboard_state(
        ledger_path=ledger_p,
        alerts_path=alerts_p,
        portfolio_mode="REAL_COMPETITION",
        real_snapshot_path=baseline_snap_p,
    )
    assert restarted_state.ledger.settled_cash_tnd == Decimal("50695.500")
    assert set(restarted_state.ledger.holdings.keys()) == {"BH_BANK", "SFBT"}
    assert restarted_state.ledger.holdings["SFBT"].total_shares == 100
    assert restarted_state.ledger.opening_snapshot is not None
    assert restarted_state.ledger.opening_snapshot.snapshot_id == "SNAP-TBC-USER-001"
    assert len(restarted_state.ledger.snapshot_history) == 2
    assert restarted_state.account_snapshot is not None
    assert restarted_state.account_snapshot.live_synchronized is True
    assert restarted_state.account_snapshot.transactions_imported is True
    assert restarted_state.account_snapshot.pending_orders_verified is True
    assert "ORD-1001" in restarted_state.ledger.orders
    assert "ORD-1002" in restarted_state.ledger.orders
    assert restarted_state.ledger.orders["ORD-1002"].status == "PENDING"

    # Freshness check after 2026-11-06 sync is now fresh
    freshness_after = evaluate_account_sync_freshness(
        restarted_state.account_snapshot, "2026-11-06"
    )
    assert freshness_after["is_stale"] is False
    assert freshness_after["warning_message"] is None


VERIFIED_ALRI_ROW = """
<tr data-sect="8300">
  <td class="alct"><button>vendre</button></td>
  <td class="no">BH</td><td class="no">223375</td>
  <td class="allf"><a href="display.aspx?s=BH">BH BANK</a></td>
  <td>30</td><td class="no">A</td><td>13.065</td><td>391.95</td>
  <td>...</td><td>392.70</td>
  <td class="quote_upb">0.75</td><td class="quote_upb">0.19%</td>
</tr>
"""


def alri_portfolio(rows: str, total: str = "50000,75", cash: str = "49608.05") -> str:
    return f"""<div>Votre portefeuille : {total} DT</div>
    <table><tbody class="alri">{rows}
    <tr><td colspan="9">Liquidités</td><td>{cash}</td></tr>
    <tr><td colspan="9">Totaux</td><td>{total}</td></tr>
    </tbody></table>"""


@pytest.mark.parametrize("latest", ["...", "\u2026", "13.090"])
def test_verified_alri_holdings(latest: str):
    snap = parse_competition_portfolio_html(
        alri_portfolio(VERIFIED_ALRI_ROW.replace("...", latest))
    )
    assert len(snap.holdings) == 1
    bh = snap.holdings[0]
    assert bh.symbol == "BH BANK"
    assert bh.displayed_symbol == "BH"
    assert bh.displayed_identifier == "223375"
    assert bh.quantity == 30
    assert bh.acquisition_price_tnd == Decimal("13.065")
    assert bh.acquisition_amount_tnd == Decimal("391.95")
    assert bh.latest_price_tnd == Decimal("13.090")
    assert bh.market_value_tnd == Decimal("392.70")
    assert bh.gain_tnd == Decimal("0.75")
    assert bh.gain_pct == Decimal("0.19")
    assert snap.available_cash_tnd == Decimal("49608.05")
    assert snap.available_cash_tnd + bh.market_value_tnd == snap.portfolio_total_tnd
    assert snap.portfolio_total_tnd == Decimal("50000.75")
    assert type(snap).from_dict(snap.to_dict()) == snap


def test_alri_multiple_holdings_and_link_symbol_fallback():
    second = (
        VERIFIED_ALRI_ROW.replace(">BH</td>", "></td>")
        .replace(">BH BANK</a>", ">SECOND BANK</a>")
        .replace("s=BH", "s=SECOND")
        .replace("223375", "999999")
        .replace("13.065", "13,065")
        .replace("...", "13,00")
        .replace("392.70", "390,00")
        .replace("quote_upb", "quote_downb")
        .replace(">0.75<", ">-1,95<")
        .replace(">0.19%<", ">-0,50%<")
    )
    snap = parse_competition_portfolio_html(
        alri_portfolio(VERIFIED_ALRI_ROW + second, total="50390,75", cash="49 608,05")
    )
    assert len(snap.holdings) == 2
    assert snap.holdings[0].gain_tnd == Decimal("0.75")
    assert snap.holdings[1].displayed_symbol == "SECOND"
    assert snap.holdings[1].displayed_identifier == "999999"
    assert snap.holdings[1].acquisition_price_tnd == Decimal("13.065")
    assert snap.holdings[1].gain_tnd == Decimal("-1.95")
    assert snap.holdings[1].gain_pct == Decimal("-0.50")


@pytest.mark.parametrize(
    "row",
    [
        VERIFIED_ALRI_ROW.replace("<td>...</td>", "<td>unavailable</td>"),
        VERIFIED_ALRI_ROW.replace("<td>30</td>", "<td>invalid</td>"),
        VERIFIED_ALRI_ROW.replace("<td>30</td>", "<td>0</td>"),
        VERIFIED_ALRI_ROW.replace("<td>391.95</td>", ""),
        VERIFIED_ALRI_ROW.replace("BH BANK</a>", "</a>"),
        VERIFIED_ALRI_ROW.replace("<td>392.70</td>", "<td>NaN</td>"),
        "<tr><td>Unrecognized holding</td></tr>",
    ],
)
def test_alri_malformed_rows_fail_even_when_totals_are_all_cash(row: str):
    with pytest.raises(LayoutChangedError):
        parse_competition_portfolio_html(alri_portfolio(row, total="49608,05"))


@pytest.mark.parametrize("rows", ["", '<tr><td colspan="12">Aucune valeur</td></tr>'])
def test_alri_empty_portfolio(rows: str):
    snap = parse_competition_portfolio_html(alri_portfolio(rows, total="49608,05"))
    assert snap.holdings == ()
    assert snap.available_cash_tnd == snap.portfolio_total_tnd


def test_totals_without_holdings_table_fail():
    with pytest.raises(LayoutChangedError, match="holdings table"):
        parse_competition_portfolio_html(
            "<div>Votre portefeuille : 50000 DT</div>"
            "<table><tr><td>Liquidités</td><td>50000</td></tr></table>"
        )


def test_legacy_snapshot_without_displayed_identifiers():
    snap = parse_competition_portfolio_html(VERIFIED_SCREENSHOT_HTML_FIXTURE)
    data = snap.to_dict()
    for holding in data["holdings"]:
        holding.pop("displayed_symbol", None)
        holding.pop("displayed_identifier", None)
    loaded = type(snap).from_dict(data)
    assert loaded.holdings[0].displayed_symbol is None
    assert loaded.holdings[0].displayed_identifier is None


def test_alri_separate_summary_table_and_identifier_first_column():
    row = VERIFIED_ALRI_ROW.replace(
        '<td class="no">BH</td><td class="no">223375</td>',
        '<td class="no">223375</td><td class="no">BH</td>',
    ).replace("...", "13.09")
    html = f"""
    <div>Votre portefeuille : 50000,75 DT</div>
    <div>Votre classement : 118 / 14530</div>
    <table><tbody class="alri">{row}</tbody></table>
    <table>
      <tr><td>Liquidités</td><td>49608.05</td></tr>
      <tr><td>Totaux</td><td>50000.75</td><td>0.75</td><td>0.00%</td></tr>
    </table>
    """
    snap = parse_competition_portfolio_html(html)
    assert len(snap.holdings) == 1
    bh = snap.holdings[0]
    assert bh.symbol == "BH BANK"
    assert bh.displayed_symbol == "BH"
    assert bh.displayed_identifier == "223375"
    assert bh.quantity == 30
    assert bh.market_value_tnd == Decimal("392.70")
    assert snap.available_cash_tnd == Decimal("49608.05")
    assert snap.portfolio_total_tnd == Decimal("50000.75")
    assert snap.competition_rank == 118
    assert snap.total_participants == 14530
    assert snap.is_reconciled is True
