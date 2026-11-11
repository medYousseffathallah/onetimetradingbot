"""Comprehensive Phase 1 synchronization reliability regression suite.

Covers all 24 audit findings across Chrome extension DOM extraction,
CORS/localhost API routes, French numeric/date parsing, manual import,
Playwright collector/worker resilience, atomic ledger persistence,
transaction-history reconciliation, and TOCTOU confirm/reject gating.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bvmt.api import create_app
from bvmt.browser import (
    BrowserCollectorError,
    BrowserHoldingItem,
    BrowserPendingOrderItem,
    BrowserTransactionItem,
    CompetitionPortfolioDOMSnapshot,
    load_latest_browser_snapshot,
    parse_competition_movements_html,
    save_browser_snapshot,
)
from bvmt.dashboard import apply_confirmed_browser_sync_to_state, build_dashboard_state
from bvmt.ledger import (
    PortfolioLedger,
    build_snapshot_from_dom,
)
from bvmt.manual_import import (
    parse_manual_portfolio_csv,
    parse_manual_portfolio_paste,
    parse_manual_transactions_csv,
)
from bvmt.playwright_worker import PlaywrightJobManager
from bvmt.portfolio_service import PortfolioStateService
from bvmt.sync_service import (
    CanonicalSyncService,
    NormalizedAccountObservation,
    NormalizedHoldingObservation,
    quantize_tnd,
)

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "extension"


@pytest.fixture
def service(tmp_path: Path) -> PortfolioStateService:
    active = PortfolioStateService(
        bars_path=ROOT / "tests/fixtures/daily_bars.csv",
        ledger_path=tmp_path / "ledger.json",
        real_snapshot_path=tmp_path / "opening.json",
        snapshots_dir=tmp_path / "snapshots",
        alerts_path=tmp_path / "alerts.json",
        calendar_path=ROOT / "tests/fixtures/exchange_calendar.csv",
        instruments_path=ROOT / "tests/fixtures/instrument_master.csv",
        competition_config_path=ROOT / "configs/competition.json",
        llm_config_path=ROOT / "configs/llm_budget.example.json",
        doc_index_path=tmp_path / "index.json",
        processed_root=tmp_path / "processed",
    )
    state = active.load_state()
    state.ledger.save(state.ledger_path)
    return active


def _run_node(script: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js runtime not available for extension JS regression tests")
    proc = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, f"Node failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    return json.loads(proc.stdout)


def _run_content_js(*, body_text: str, tables: list[dict[str, object]], href: str) -> dict[str, object]:
    content_path = str(EXTENSION_DIR / "content.js").replace("\\", "\\\\")
    script = f"""
const fs = require("fs");
const contentCode = fs.readFileSync("{content_path}", "utf-8");
const tablesInput = {json.dumps(tables)};
const mockTables = tablesInput.map((t) => {{
  const makeCell = (c) => {{
    if (c && typeof c === "object") {{
      return {{
        tagName: c.tag || "TD",
        innerText: c.text || "",
        textContent: c.text || "",
        className: c.className || "",
        classList: {{ contains: (cls) => String(c.className || "").split(/\\s+/).includes(cls) }},
        querySelector: (sel) => (sel === "a" && c.linkText ? {{ innerText: c.linkText, textContent: c.linkText }} : null),
      }};
    }}
    const tag = t.hasThHeader && t.rows[0] && t.rows[0].includes(c) ? "TH" : "TD";
    return {{
      tagName: tag,
      innerText: String(c),
      textContent: String(c),
      className: "",
      classList: {{ contains: () => false }},
      querySelector: () => null,
    }};
  }};
  const rowObjs = t.rows.map((cells, rIdx) => ({{
    className: t.tbodyClass || "",
    closest: (sel) => (sel === "tbody" && t.tbodyClass ? {{ className: t.tbodyClass }} : null),
    querySelectorAll: (sel) => {{
      if (sel.includes("th") && !sel.includes("td")) {{
        return rIdx === 0 && t.hasThHeader ? cells.map((c) => makeCell(c)) : [];
      }}
      if (sel.includes("td") || sel.includes("th")) {{
        return cells.map((c) => makeCell(c));
      }}
      return [];
    }},
  }}));
  return {{
    innerText: t.rows.map((r) => r.map((c) => (typeof c === "object" ? c.text : c)).join("\\t")).join("\\n"),
    className: t.className || "",
    querySelectorAll: (sel) => (sel.includes("tr") ? rowObjs : []),
  }};
}});
const document = {{
  body: {{ innerText: {json.dumps(body_text)} }},
  querySelectorAll: (sel) => (sel === "table" ? mockTables : []),
  querySelector: (sel) => {{
    if (sel === "#tab_portefeuille" && tablesInput[0]?.id === "tab_portefeuille") return mockTables[0];
    return null;
  }},
}};
const window = {{ location: {{ href: {json.dumps(href)} }} }};
const fn = new Function("document", "window", "return " + contentCode);
const result = fn(document, window);
console.log(JSON.stringify(result));
"""
    return _run_node(script)


# ---------------------------------------------------------------------------
# A. Extension & DOM Extraction + CORS (EXT-01..EXT-06)
# ---------------------------------------------------------------------------


def test_ext01_cors_preflight_allows_extension_origin_and_pairing_header(
    service: PortfolioStateService,
) -> None:
    with TestClient(create_app(service)) as client:
        ok = client.options(
            "/api/sync/extension",
            headers={
                "Origin": "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-bvmt-pairing-token",
            },
        )
        assert ok.status_code == 200, ok.text
        allow_headers = ok.headers.get("access-control-allow-headers", "").lower()
        assert "x-bvmt-pairing-token" in allow_headers
        assert (
            ok.headers.get("access-control-allow-origin")
            == "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef"
        )

        evil = client.options(
            "/api/sync/extension",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-bvmt-pairing-token",
            },
        )
        assert evil.status_code == 400


def test_ext01_background_relay_forwards_upload_with_pairing_header() -> None:
    bg_path = str(EXTENSION_DIR / "background.js").replace("\\", "\\\\")
    script = f"""
const fs = require("fs");
const listeners = [];
const chrome = {{
  runtime: {{
    onInstalled: {{ addListener: () => {{}} }},
    onMessage: {{ addListener: (fn) => listeners.push(fn) }},
  }},
}};
let fetched = null;
const fetch = async (url, init) => {{
  fetched = {{ url, init }};
  return {{
    ok: true,
    status: 200,
    json: async () => ({{ success: true, snapshot_id: "snap_bg_1" }}),
  }};
}};
const fn = new Function("chrome", "fetch", fs.readFileSync("{bg_path}", "utf-8"));
fn(chrome, fetch);
if (listeners.length === 0) throw new Error("No onMessage listener registered in background.js");
let keepAlive = false;
const done = new Promise((resolve) => {{
  keepAlive = listeners[0](
    {{
      type: "BVMT_SYNC_UPLOAD",
      endpointUrl: "http://127.0.0.1:8000/api/sync/extension",
      pairingToken: "tok_test_123",
      payload: {{ snapshot_id: "snap_bg_1", source_schema_version: "2026.11-v2" }},
    }},
    {{}},
    (resp) => resolve(resp)
  );
}});
done.then((resp) => {{
  console.log(JSON.stringify({{ keepAlive, fetched, resp }}));
}});
"""
    out = _run_node(script)
    assert out["keepAlive"] is True
    assert out["resp"]["ok"] is True  # type: ignore[index]
    assert out["fetched"]["init"]["headers"]["X-BVMT-Pairing-Token"] == "tok_test_123"  # type: ignore[index]


def test_ext02_content_script_avoids_nom_de_valeur_collision_and_header_validation_error() -> None:
    res = _run_content_js(
        href="https://www.tunisbourse-challenge.com/displayp.aspx",
        body_text="Votre portefeuille : 50 050,000 DT\nLiquidités : 49 000,000 DT",
        tables=[
            {
                "id": "tab_portefeuille",
                "hasThHeader": True,
                "rows": [
                    [
                        "Vendre",
                        "Nom de valeur",
                        "Quantité",
                        "Prix",
                        "Montant",
                        "Dernier",
                        "Capital",
                        "Gain (dt)",
                        "Gain(%)",
                    ],
                    [
                        "vendre",
                        "2L",
                        "100",
                        "10,000",
                        "1 000,000",
                        "...",
                        "1 050,000",
                        "50,000",
                        "5,00%",
                    ],
                ],
            }
        ],
    )
    assert res["success"] is True
    assert res["source_schema_version"] == "2026.11-v2"
    assert res["validation_errors"] == []
    holdings = res["holdings"]
    assert isinstance(holdings, list) and len(holdings) == 1
    assert holdings[0]["symbol"] == "2L"
    assert holdings[0]["market_value_tnd"] == "1050.000"
    assert holdings[0]["latest_price_tnd"] == "10.500"


def test_ext03_content_script_12_cell_alri_extracts_qty_30_not_id_223375() -> None:
    res = _run_content_js(
        href="https://www.tunisbourse-challenge.com/displayp.aspx",
        body_text="Votre portefeuille : 50 000,750 DT\nLiquidités : 49 608,050 DT",
        tables=[
            {
                "id": "tab_portefeuille",
                "tbodyClass": "alri",
                "rows": [
                    [
                        {"text": "vendre"},
                        {"text": "BH", "className": "no"},
                        {"text": "223375", "className": "no"},
                        {"text": "BH BANK", "linkText": "BH BANK"},
                        {"text": "30"},
                        {"text": "A"},
                        {"text": "13.065"},
                        {"text": "391.95"},
                        {"text": "..."},
                        {"text": "392.70"},
                        {"text": "0.75"},
                        {"text": "0.19%"},
                    ]
                ],
            }
        ],
    )
    assert res["success"] is True
    holdings = res["holdings"]
    assert len(holdings) == 1  # type: ignore[arg-type]
    assert holdings[0]["symbol"] == "BH BANK"  # type: ignore[index]
    assert holdings[0]["quantity"] == 30  # type: ignore[index]
    assert holdings[0]["acquisition_price_tnd"] == "13.065"  # type: ignore[index]
    assert holdings[0]["market_value_tnd"] == "392.700"  # type: ignore[index]
    assert holdings[0]["displayed_identifier"] == "223375"  # type: ignore[index]


def test_ext04_ext05_no_50000_fallback_strict_french_thousands_and_reject_2l() -> None:
    # Missing cash/equity -> MUST fail cleanly without "50000.000"
    missing_bal = _run_content_js(
        href="https://www.tunisbourse-challenge.com/displayp.aspx",
        body_text="Portefeuille en cours",
        tables=[
            {
                "id": "tab_portefeuille",
                "rows": [
                    [
                        "Vendre",
                        "Nom de valeur",
                        "Quantité",
                        "Prix",
                        "Montant",
                        "Dernier",
                        "Capital",
                        "Gain (dt)",
                        "Gain(%)",
                    ],
                    [
                        "vendre",
                        "BH BANK",
                        "30",
                        "13,065",
                        "391,950",
                        "13,090",
                        "392,700",
                        "0,750",
                        "0,19%",
                    ],
                ],
            }
        ],
    )
    assert missing_bal["success"] is False
    assert missing_bal.get("account_equity") != "50000.000"

    # Dot thousand separators & negative performance
    french = _run_content_js(
        href="https://www.tunisbourse-challenge.com/displayp.aspx",
        body_text=(
            "Votre portefeuille : 50.000,000 DT\n"
            "Liquidités : 48.765,440 DT\n"
            "Performance générale : -1,25 %"
        ),
        tables=[
            {
                "id": "tab_portefeuille",
                "rows": [
                    [
                        "Vendre",
                        "Nom de valeur",
                        "Quantité",
                        "Prix",
                        "Montant",
                        "Dernier",
                        "Capital",
                        "Gain (dt)",
                        "Gain(%)",
                    ],
                    [
                        "vendre",
                        "2L",
                        "100",
                        "12,000",
                        "1.200,000",
                        "12,345",
                        "1.234,560",
                        "34,560",
                        "2,88%",
                    ],
                ],
            }
        ],
    )
    assert french["success"] is True
    assert french["account_equity"] == "50000.000"
    assert french["available_cash"] == "48765.440"
    assert french["displayed_overall_performance_pct"] == "-1.250"
    assert french["holdings"][0]["acquisition_amount_tnd"] == "1200.000"  # type: ignore[index]
    assert french["holdings"][0]["market_value_tnd"] == "1234.560"  # type: ignore[index]


def test_ext06_content_script_display_histo_and_popup_gating() -> None:
    histo = _run_content_js(
        href="https://www.tunisbourse-challenge.com/display_histo.aspx",
        body_text="Historique des opérations",
        tables=[
            {
                "id": "tab_histo",
                "hasThHeader": True,
                "rows": [
                    [
                        "Réf",
                        "Date",
                        "Nom de valeur",
                        "Sens",
                        "Quantité",
                        "Cours",
                        "Montant",
                        "Statut",
                    ],
                    [
                        "TX-501",
                        "09/11/2026 10:15",
                        "BH BANK",
                        "Achat validé",
                        "30",
                        "13,065",
                        "391,950",
                        "Exécuté",
                    ],
                    [
                        "ORD-999",
                        "10/11/2026 09:40",
                        "SFBT",
                        "Vente",
                        "20",
                        "12,500",
                        "250,000",
                        "En cours",
                    ],
                ],
            }
        ],
    )
    assert histo["success"] is True
    assert histo["source_page_type"] == "display_histo.aspx"
    assert histo["source_schema_version"] == "2026.11-v2"
    assert len(histo["transactions"]) == 1  # type: ignore[arg-type]
    assert histo["transactions"][0]["side"] == "BUY"  # type: ignore[index]
    assert len(histo["pending_orders"]) == 1  # type: ignore[arg-type]
    assert histo["pending_orders"][0]["order_id"] == "ORD-999"  # type: ignore[index]

    # Popup blocks transmit when res.success === false or validation_errors non-empty
    popup_js = (EXTENSION_DIR / "popup.js").read_text(encoding="utf-8")
    assert "source_schema_version" in popup_js
    assert "res.success === false" in popup_js or "res?.success === false" in popup_js
    assert "BVMT_SYNC_UPLOAD" in popup_js


def test_ext06_manifest_includes_non_www_challenge_domains() -> None:
    manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))
    hosts = set(manifest["host_permissions"])
    assert "http://tunisbourse.com.tn/*" in hosts
    assert "https://tunisbourse.com.tn/*" in hosts


# ---------------------------------------------------------------------------
# B. Localhost API & Sync Service (API-01..API-03, SVC-01..SVC-03)
# ---------------------------------------------------------------------------


def test_api01_browser_sync_error_does_not_return_200_with_stale_confirmed_snapshot(
    service: PortfolioStateService,
) -> None:
    snap = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-07T12:20:06+00:00"),
        portfolio_total_tnd=Decimal("50000.750"),
        available_cash_tnd=Decimal("49608.050"),
        holdings_market_value_tnd=Decimal("392.700"),
        holdings=(
            BrowserHoldingItem(
                symbol="BH BANK",
                quantity=30,
                acquisition_price_tnd=Decimal("13.065"),
                acquisition_amount_tnd=Decimal("391.950"),
                latest_price_tnd=Decimal("13.090"),
                market_value_tnd=Decimal("392.700"),
                gain_tnd=Decimal("0.750"),
                gain_pct=Decimal("0.19"),
            ),
        ),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
    )
    save_browser_snapshot(snap, service.snapshots_dir)
    service.confirm_snapshot(confirmed_by_user=True, dom_snap=snap)

    with patch(
        "bvmt.api.run_browser_sync_subprocess",
        side_effect=BrowserCollectorError("Simulated Playwright failure"),
    ):
        with TestClient(create_app(service)) as client:
            resp = client.post("/api/sync/browser", json={"timeout_seconds": 30})
    assert resp.status_code == 422


def test_api02_french_overrides_and_invalid_decimal_never_return_500(
    service: PortfolioStateService,
) -> None:
    with TestClient(create_app(service)) as client:
        tok = client.get("/api/sync/pairing-token").json()["pairing_token"]

        # Valid French formatted cash/equity overrides in manual CSV
        ok_csv = client.post(
            "/api/sync/manual/csv",
            json={
                "csv_content": "SYMBOL;QUANTITY;ACQUISITION_PRICE;LATEST_PRICE;MARKET_VALUE\nBH;30;13,065;13,090;392,700\n",
                "cash_override": "49 608,050 DT",
                "equity_override": "50.000,750",
            },
        )
        assert ok_csv.status_code == 200, ok_csv.text

        # Garbage overrides -> 422 (NOT 500)
        bad_paste = client.post(
            "/api/sync/manual/paste",
            json={
                "raw_text": "BH BANK\t30\t13,065\t13,090\t392,700",
                "cash_override": "NOT_A_NUMBER",
                "equity_override": "50000.750",
            },
        )
        assert bad_paste.status_code == 422

        bad_csv = client.post(
            "/api/sync/manual/csv",
            json={
                "csv_content": "SYMBOL;QUANTITY;ACQUISITION_PRICE;LATEST_PRICE;MARKET_VALUE\nBH;30;13.065;13.090;392.700\n",
                "cash_override": "bad_override",
                "equity_override": "50000.750",
            },
        )
        assert bad_csv.status_code == 422

        # French gain_pct in extension sync -> 200, garbage decimal -> 422
        ext_french = client.post(
            "/api/sync/extension",
            headers={"X-BVMT-Pairing-Token": tok},
            json={
                "source": "CHROME_EXTENSION",
                "capture_timestamp": "2026-11-09T10:00:00Z",
                "snapshot_id": "snap_ext_fr_01",
                "account_equity": "50.000,750 DT",
                "available_cash": "49\xa0608,050 DT",
                "holdings": [
                    {
                        "symbol": "BH BANK",
                        "quantity": 30,
                        "acquisition_price_tnd": "13,065",
                        "latest_price_tnd": None,
                        "market_value_tnd": "392,700",
                        "gain_tnd": "0,750",
                        "gain_pct": "0,19%",
                    }
                ],
            },
        )
        assert ext_french.status_code == 200, ext_french.text


def test_api03_pairing_token_persists_inside_snapshots_parent(tmp_path: Path) -> None:
    svc = PortfolioStateService(
        bars_path=ROOT / "tests/fixtures/daily_bars.csv",
        ledger_path=tmp_path / "isolated/ledger.json",
        real_snapshot_path=tmp_path / "isolated/opening.json",
        snapshots_dir=tmp_path / "isolated/snapshots",
        alerts_path=tmp_path / "isolated/alerts.json",
        calendar_path=ROOT / "tests/fixtures/exchange_calendar.csv",
        instruments_path=ROOT / "tests/fixtures/instrument_master.csv",
        competition_config_path=ROOT / "configs/competition.json",
        llm_config_path=ROOT / "configs/llm_budget.example.json",
        doc_index_path=tmp_path / "isolated/index.json",
        processed_root=tmp_path / "isolated/processed",
    )
    svc.load_state().ledger.save(tmp_path / "isolated/ledger.json")
    expected_token_path = tmp_path / "isolated/pairing_token.txt"
    assert not expected_token_path.exists()
    with TestClient(create_app(svc)) as client:
        tok = client.get("/api/sync/pairing-token").json()["pairing_token"]
    assert expected_token_path.exists()
    assert expected_token_path.read_text(encoding="utf-8").strip() == tok


def test_svc01_svc02_quantize_tnd_and_falsy_zero_preservation() -> None:
    assert quantize_tnd("19\xa0095,000") == Decimal("19095.000")
    assert quantize_tnd("19\u202f095,000") == Decimal("19095.000")
    assert quantize_tnd("44 586,070 DT") == Decimal("44586.070")
    assert quantize_tnd("1.234,567") == Decimal("1234.567")
    assert quantize_tnd("-450,000") == Decimal("-450.000")
    assert quantize_tnd("0,19%") == Decimal("0.190")
    for bad in ("...", "—", "2L", "N/A", ""):
        with pytest.raises(ValueError):
            quantize_tnd(bad)

    holding = NormalizedHoldingObservation.from_dict(
        {
            "symbol": "BH BANK",
            "quantity": 10,
            "acquisition_price_tnd": "10.000",
            "acquisition_amount_tnd": "100.000",
            "latest_price_tnd": "10.500",
            "market_value_tnd": "105.000",
            "gain_tnd": 0,
            "gain_pct": 0,
        }
    )
    assert holding.gain_tnd == Decimal("0.000")
    assert holding.gain_pct == Decimal("0.000")

    obs_none = NormalizedAccountObservation(
        source="CHROME_EXTENSION",
        capture_timestamp="2026-11-09T10:00:00Z",
        snapshot_id="snap_zero_test",
        account_equity=Decimal("1050.000"),
        available_cash=Decimal("0.000"),
        holdings=(
            NormalizedHoldingObservation(
                symbol="BH BANK",
                instrument_id="BH_BANK",
                quantity=100,
                acquisition_price_tnd=Decimal("10.000"),
                acquisition_amount_tnd=None,
                latest_price_tnd=Decimal("10.500"),
                market_value_tnd=Decimal("1050.000"),
                gain_tnd=None,
                gain_pct=None,
            ),
        ),
    )
    dom = obs_none.to_dom_snapshot()
    assert dom.holdings[0].gain_tnd == Decimal("50.000")


def test_svc03_dedup_distinguishes_symbol_swap_scans_all_files_and_does_not_bloat_disk(
    service: PortfolioStateService,
) -> None:
    sync_svc = CanonicalSyncService(
        portfolio_service=service,
        snapshots_dir=service.snapshots_dir,
        pairing_token_path=service.snapshots_dir.parent / "pairing_token.txt",
    )
    obs_bh = NormalizedAccountObservation(
        source="CHROME_EXTENSION",
        capture_timestamp="2026-11-09T09:00:00Z",
        snapshot_id="snap_bh",
        account_equity=Decimal("50000.750"),
        available_cash=Decimal("49608.050"),
        holdings=(
            NormalizedHoldingObservation(
                symbol="BH BANK",
                instrument_id="BH_BANK",
                quantity=30,
                acquisition_price_tnd=Decimal("13.065"),
                acquisition_amount_tnd=Decimal("391.950"),
                latest_price_tnd=Decimal("13.090"),
                market_value_tnd=Decimal("392.700"),
            ),
        ),
    )
    r1 = sync_svc.ingest_observation(obs_bh, allow_duplicate=False)
    assert r1.success is True and r1.is_duplicate is False
    assert len(list(service.snapshots_dir.glob("sync_*.json"))) == 1

    # Duplicate at different timestamp with allow_duplicate=False MUST NOT write a 2nd file
    r1_dup = sync_svc.ingest_observation(
        replace(obs_bh, snapshot_id="snap_bh_dup", capture_timestamp="2026-11-09T09:03:00Z"),
        allow_duplicate=False,
    )
    assert r1_dup.success is True and r1_dup.is_duplicate is True
    assert len(list(service.snapshots_dir.glob("sync_*.json"))) == 1

    # Symbol swap (UIB at exact same total value & cash) MUST NOT be duplicate
    obs_uib = NormalizedAccountObservation(
        source="CHROME_EXTENSION",
        capture_timestamp="2026-11-09T09:05:00Z",
        snapshot_id="snap_uib",
        account_equity=Decimal("50000.750"),
        available_cash=Decimal("49608.050"),
        holdings=(
            NormalizedHoldingObservation(
                symbol="UIB",
                instrument_id="UIB",
                quantity=20,
                acquisition_price_tnd=Decimal("19.598"),
                acquisition_amount_tnd=Decimal("391.950"),
                latest_price_tnd=Decimal("19.635"),
                market_value_tnd=Decimal("392.700"),
            ),
        ),
    )
    r_uib = sync_svc.ingest_observation(obs_uib, allow_duplicate=False)
    assert r_uib.is_duplicate is False
    assert len(list(service.snapshots_dir.glob("sync_*.json"))) == 2

    # Save 6 newer distinct snapshots; matching obs_bh (>5 files back) must STILL detect duplicate!
    for i in range(6):
        obs_other = NormalizedAccountObservation(
            source="CHROME_EXTENSION",
            capture_timestamp=f"2026-11-09T10:{i:02d}:00Z",
            snapshot_id=f"snap_other_{i}",
            account_equity=Decimal(f"{50010 + i}.000"),
            available_cash=Decimal(f"{50010 + i}.000"),
            holdings=(),
        )
        assert sync_svc.ingest_observation(obs_other, allow_duplicate=False).is_duplicate is False

    is_dup_old = sync_svc.check_duplicate(
        replace(obs_bh, snapshot_id="snap_bh_again", capture_timestamp="2026-11-09T11:00:00Z")
    )
    assert is_dup_old is True


# ---------------------------------------------------------------------------
# C. Manual Import (MAN-01..MAN-03)
# ---------------------------------------------------------------------------


def test_man01_man02_garbage_rejected_total_tunisie_preserved_and_ellipsis_columns() -> None:
    with pytest.raises(ValueError):
        parse_manual_portfolio_paste("Hello unrelated text without any balances or rows")

    with pytest.raises(ValueError):
        parse_manual_portfolio_csv("SYMBOL;QUANTITY;ACQ;LAT;VAL\nBH;BAD_QTY;10;11;120\n")

    # Stock named "TOTAL TUNISIE" must NOT be discarded by TOTAL filter
    paste_total = (
        "Votre portefeuille : 50 000,000 DT\n"
        "Liquidités : 48 000,000 DT\n"
        "TOTAL TUNISIE\t100\t19,500\t...\t2 000,000\t50,000\t2,56%\n"
    )
    obs = parse_manual_portfolio_paste(paste_total)
    assert len(obs.holdings) == 1
    assert obs.holdings[0].symbol == "TOTAL TUNISIE"
    assert obs.holdings[0].market_value_tnd == Decimal("2000.000")
    assert obs.holdings[0].latest_price_tnd == Decimal("20.000")


def test_man03_transactions_csv_endpoint_side_and_iso_timestamp(
    service: PortfolioStateService,
) -> None:
    csv_tx = (
        "Réf;Date;Nom de valeur;Sens;Quantité;Cours;Frais;Montant net\n"
        "TX-101;09/11/2026 10:15;BH BANK;VENTE PARTIELLE;10;13,200;0,660;131,340\n"
    )
    txs = parse_manual_transactions_csv(csv_tx)
    assert len(txs) == 1
    assert txs[0].side == "SELL"
    parsed_dt = datetime.fromisoformat(txs[0].executed_at)
    assert parsed_dt.year == 2026 and parsed_dt.month == 11 and parsed_dt.day == 9

    with TestClient(create_app(service)) as client:
        res = client.post("/api/sync/manual/transactions", json={"csv_content": csv_tx})
        assert res.status_code == 200, res.text
        assert res.json()["success"] is True

        # Reject invalid CSV cleanly with HTTP 422
        bad = client.post(
            "/api/sync/manual/transactions",
            json={"csv_content": "Réf;Date;Valeur;Sens;Qté\nTX-BAD;bad;BH;BUY;not_a_num\n"},
        )
        assert bad.status_code == 422

        # Confirm staged movements snapshot -> GET /api/transactions must return 200 (never 503!)
        conf = client.post("/api/sync/confirm", json={"confirmed_by_user": True})
        assert conf.status_code == 200, conf.text
        tx_resp = client.get("/api/transactions")
        assert tx_resp.status_code == 200, tx_resp.text


# ---------------------------------------------------------------------------
# D. Browser Collector & Playwright Worker (BRW-01..BRW-05)
# ---------------------------------------------------------------------------


def test_brw01_brw02_movements_side_sotuver_and_unrecognized_headers() -> None:
    html_sotuver = """
    <html><body>
      <table>
        <tr><th>Réf</th><th>Date</th><th>Valeur</th><th>Sens</th><th>Quantité</th><th>Cours</th><th>Statut</th></tr>
        <tr><td>TX-1</td><td>09/11/2026 10:15</td><td>SOTUVER</td><td>Achat validé</td><td>20</td><td>12,500</td><td>Exécuté</td></tr>
      </table>
    </body></html>
    """
    txs, pends = parse_competition_movements_html(html_sotuver)
    assert len(txs) == 1
    assert txs[0].symbol == "SOTUVER"
    assert txs[0].side == "BUY"
    assert len(pends) == 0

    # Row without side column containing 'v' in SOTUVER must NOT classify as SELL
    html_no_side = """
    <html><body>
      <table>
        <tr><th>Date</th><th>Valeur</th><th>Quantité</th><th>Cours</th></tr>
        <tr><td>09/11/2026</td><td>SOTUVER</td><td>20</td><td>12,500</td></tr>
      </table>
    </body></html>
    """
    txs_no_side, _ = parse_competition_movements_html(html_no_side)
    assert all(tx.side != "SELL" for tx in txs_no_side)

    # Unrecognized movements headers on display_histo.aspx MUST NOT falsely report movements_page_captured=True
    from bvmt.browser import parse_competition_portfolio_html

    port_html = """
    <html><body>
      Votre portefeuille : 50 000,000 DT
      <table>
        <thead><tr><th>Vendre</th><th>Nom de valeur</th><th>Quantité</th><th>Prix</th><th>Montant</th><th>Dernier</th><th>Capital</th><th>Gain</th><th>%</th></tr></thead>
        <tbody><tr><td>Liquidités</td><td>50 000,000</td></tr></tbody>
      </table>
    </body></html>
    """
    unknown_mov_html = """
    <html><body>
      <table>
        <tr><th>Horodatage</th><th>Code</th><th>Opération inconnue</th><th>Volume</th></tr>
        <tr><td>09/11/2026</td><td>BH</td><td>?</td><td>30</td></tr>
      </table>
    </body></html>
    """
    snap = parse_competition_portfolio_html(
        port_html,
        retrieved_at=datetime.fromisoformat("2026-11-09T11:00:00+00:00"),
        movements_html=unknown_mov_html,
    )
    assert snap.movements_page_captured is False
    assert len(snap.movements_parse_warnings) >= 1


def test_brw03_brw04_same_second_snapshots_not_overwritten_and_corrupt_snapshot_resilient(
    service: PortfolioStateService,
) -> None:
    snap1 = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-11T10:00:00.100000+00:00"),
        portfolio_total_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49000.000"),
        holdings_market_value_tnd=Decimal("1000.000"),
        holdings=(
            BrowserHoldingItem(
                symbol="BH BANK",
                quantity=50,
                acquisition_price_tnd=Decimal("20.000"),
                acquisition_amount_tnd=Decimal("1000.000"),
                latest_price_tnd=Decimal("20.000"),
                market_value_tnd=Decimal("1000.000"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
        ),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
    )
    snap2 = replace(
        snap1,
        retrieved_at=datetime.fromisoformat("2026-11-11T10:00:00.900000+00:00"),
        holdings=(
            replace(snap1.holdings[0], symbol="STA"),
        ),
    )
    p1 = save_browser_snapshot(snap1, service.snapshots_dir)
    p2 = save_browser_snapshot(snap2, service.snapshots_dir)
    assert p1 != p2
    assert len(list(service.snapshots_dir.glob("sync_*.json"))) == 2

    # Write a corrupt newest file -> load_latest_browser_snapshot and GET /api/overview must survive!
    (service.snapshots_dir / "sync_20991231_235959.json").write_text(
        "{corrupt json", encoding="utf-8"
    )
    latest = load_latest_browser_snapshot(service.snapshots_dir)
    assert latest is not None
    assert latest.holdings[0].symbol == "STA"

    with TestClient(create_app(service)) as client:
        ov = client.get("/api/overview")
        assert ov.status_code == 200, ov.text


def test_brw05_playwright_msedge_fallback_pid_lock_protection_and_job_persistence(
    tmp_path: Path,
) -> None:
    # 1. Profile lock must NOT delete active lock when owning PID is live
    profile = tmp_path / "profile"
    profile.mkdir()
    for name in ("lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie"):
        (profile / name).write_text("locked", encoding="utf-8")

    with patch.object(PlaywrightJobManager, "_is_profile_in_use", return_value=True):
        assert PlaywrightJobManager.clean_stale_profile_lock(profile) is False
        assert (profile / "SingletonLock").exists()

    with patch.object(PlaywrightJobManager, "_is_profile_in_use", return_value=False):
        assert PlaywrightJobManager.clean_stale_profile_lock(profile) is True
        for name in ("lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie"):
            assert not (profile / name).exists()

    # 2. Persisted job registry survives manager restart
    snaps_dir = tmp_path / "snaps"
    dummy_snap = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-11T10:00:00+00:00"),
        portfolio_total_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("50000.000"),
        holdings_market_value_tnd=Decimal("0.000"),
        holdings=(),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
    )
    saved_dummy = save_browser_snapshot(dummy_snap, snaps_dir)

    jobs_file = tmp_path / "sync_jobs.json"
    mgr1 = PlaywrightJobManager(jobs_path=jobs_file)
    with patch("bvmt.playwright_worker.subprocess.Popen") as popen_mock:
        proc = popen_mock.return_value
        proc.pid = 999999
        proc.poll.return_value = 0
        proc.returncode = 0
        proc.communicate.return_value = (json.dumps({"saved_path": str(saved_dummy)}), "")
        job = mgr1.start_job(
            user_data_dir=profile,
            snapshots_dir=snaps_dir,
            timeout_seconds=10,
        )
        # Allow monitor thread to observe poll=0 & write completed state
        import time

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            cur = mgr1.get_job(job.job_id)
            if cur is not None and cur.status != "RUNNING":
                break
            time.sleep(0.02)

    mgr2 = PlaywrightJobManager(jobs_path=jobs_file)
    restored = mgr2.get_job(job.job_id)
    assert restored is not None
    assert restored.job_id == job.job_id

    # 3. Chrome -> msedge fallback chain in _run_interactive_browser_pages
    from bvmt import browser as browser_mod

    launch_calls: list[dict[str, object]] = []

    class FakePage:
        def __init__(self) -> None:
            self.url = "https://www.tunisbourse-challenge.com/displayp.aspx"

        def set_default_timeout(self, _ms: int) -> None:
            return

        def goto(self, url: str, **_kwargs: object) -> None:
            self.url = url

        def title(self) -> str:
            return "Mon portefeuille"

        def is_closed(self) -> bool:
            return False

        def content(self) -> str:
            return (
                "<p>Votre portefeuille : 50 000,000 DT</p>"
                "<table class='table_portefeuille'>"
                "<tr><th>Nom de valeur</th><th>Quantité</th><th>Prix</th><th>Montant</th><th>Dernier</th><th>Capital</th></tr>"
                "<tr><td>Liquidités</td><td>50 000,000</td></tr>"
                "</table>"
            )

        def inner_text(self, _sel: str) -> str:
            return "Votre portefeuille : 50 000,000 DT\nLiquidités : 50 000,000 DT"

    class FakeContext:
        def __init__(self) -> None:
            self.pages = [FakePage()]

        def new_page(self) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return

    class FakeChromium:
        def launch_persistent_context(self, **kwargs: object) -> FakeContext:
            launch_calls.append(kwargs)
            if kwargs.get("channel") == "chrome":
                raise RuntimeError("chrome binary not available")
            if kwargs.get("channel") == "msedge":
                return FakeContext()
            raise RuntimeError("bundled chromium absent")

    class FakePlaywrightCM:
        def __enter__(self) -> object:
            return type("PW", (), {"chromium": FakeChromium()})()

        def __exit__(self, *_args: object) -> None:
            return

    monkeypatch_sync = patch("playwright.sync_api.sync_playwright", return_value=FakePlaywrightCM())
    with monkeypatch_sync:
        out_snap, _saved_path = browser_mod.collect_authenticated_portfolio_snapshot(
            user_data_dir=tmp_path / "pw_profile",
            snapshots_dir=tmp_path / "pw_snaps",
            movements_url=None,
            timeout_seconds=10,
        )
    assert out_snap.portfolio_total_tnd == Decimal("50000.000")
    assert [c.get("channel") for c in launch_calls] == ["chrome", "msedge"]


# ---------------------------------------------------------------------------
# E. Ledger Reconciliation, Atomic Save, Confirm TOCTOU & Reject (LED-01..LED-04)
# ---------------------------------------------------------------------------


def test_led01_displayp_only_confirm_preserves_open_orders_and_transactions_flag(
    service: PortfolioStateService,
) -> None:
    snap_mov = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-08T10:00:00+00:00"),
        portfolio_total_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49608.050"),
        holdings_market_value_tnd=Decimal("391.950"),
        holdings=(
            BrowserHoldingItem(
                symbol="BH BANK",
                quantity=30,
                acquisition_price_tnd=Decimal("13.065"),
                acquisition_amount_tnd=Decimal("391.950"),
                latest_price_tnd=Decimal("13.065"),
                market_value_tnd=Decimal("391.950"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
        ),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
        movements_page_captured=True,
        transactions=(
            BrowserTransactionItem(
                transaction_id="TX-BH-1",
                order_id="ORD-BH-1",
                instrument_id="BH_BANK",
                symbol="BH BANK",
                side="BUY",
                filled_shares=30,
                execution_price_tnd=Decimal("13.065"),
                fee_tnd=Decimal("1.960"),
                executed_at="2026-11-08T09:50:00+00:00",
            ),
        ),
        pending_orders=(
            BrowserPendingOrderItem(
                order_id="ORD-999",
                instrument_id="SFBT",
                symbol="SFBT",
                side="BUY",
                requested_shares=10,
                filled_shares=0,
                remaining_shares=10,
                limit_price_tnd=Decimal("12.000"),
                submitted_at="2026-11-08T09:55:00+00:00",
                status="PENDING",
            ),
        ),
    )
    state = service.load_state()
    apply_confirmed_browser_sync_to_state(state, snap_mov, confirmed_by_user=True)
    assert state.ledger.orders["ORD-999"].status == "PENDING"
    assert state.account_snapshot.transactions_imported is True

    # Subsequent displayp.aspx-only snapshot MUST NOT cancel ORD-999 or reset transactions_imported
    snap_ext = CompetitionPortfolioDOMSnapshot(
        source_url="bvmt-sync://chrome_extension/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-09T10:00:00+00:00"),
        portfolio_total_tnd=Decimal("50000.750"),
        available_cash_tnd=Decimal("49608.050"),
        holdings_market_value_tnd=Decimal("392.700"),
        holdings=(replace(snap_mov.holdings[0], latest_price_tnd=Decimal("13.090"), market_value_tnd=Decimal("392.700")),),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
        movements_page_captured=False,
    )
    apply_confirmed_browser_sync_to_state(state, snap_ext, confirmed_by_user=True)
    assert state.ledger.orders["ORD-999"].status == "PENDING"
    assert state.account_snapshot.transactions_imported is True
    assert state.account_snapshot.pending_orders_verified is True


def test_led02_bh_assurance_isin_alias_mapping_and_idempotent_confirm(
    service: PortfolioStateService,
) -> None:
    dom_aliases = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-09T14:40:00+00:00"),
        portfolio_total_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("47000.000"),
        holdings_market_value_tnd=Decimal("3000.000"),
        holdings=(
            BrowserHoldingItem(
                symbol="BH ASSURANCE",
                quantity=10,
                acquisition_price_tnd=Decimal("50.000"),
                acquisition_amount_tnd=Decimal("500.000"),
                latest_price_tnd=Decimal("50.000"),
                market_value_tnd=Decimal("500.000"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
            BrowserHoldingItem(
                symbol="BH",
                quantity=50,
                acquisition_price_tnd=Decimal("13.000"),
                acquisition_amount_tnd=Decimal("650.000"),
                latest_price_tnd=Decimal("13.000"),
                market_value_tnd=Decimal("650.000"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
            BrowserHoldingItem(
                symbol="DH",
                quantity=100,
                acquisition_price_tnd=Decimal("13.500"),
                acquisition_amount_tnd=Decimal("1350.000"),
                latest_price_tnd=Decimal("13.500"),
                market_value_tnd=Decimal("1350.000"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
            BrowserHoldingItem(
                symbol="NBL",
                quantity=100,
                acquisition_price_tnd=Decimal("5.000"),
                acquisition_amount_tnd=Decimal("500.000"),
                latest_price_tnd=Decimal("5.000"),
                market_value_tnd=Decimal("500.000"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
        ),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
    )
    acct = build_snapshot_from_dom(dom_aliases)
    by_id = {h.instrument_id: h for h in acct.holdings}
    assert "BH_BANK" in by_id
    assert by_id["BH_BANK"].isin == "TN0001900604"
    assert "DELICE_HOLDING" in by_id
    assert "NEW_BODY_LINE" in by_id
    bh_assur = [h for h in acct.holdings if "ASSURANCE" in h.symbol.upper()][0]
    assert bh_assur.instrument_id == "BH_ASSURANCE"
    assert bh_assur.isin == "TN0006550016"

    # Repeated confirmation of identical snapshot MUST NOT duplicate snapshot_history or audit_log
    state = service.load_state()
    apply_confirmed_browser_sync_to_state(state, dom_aliases, confirmed_by_user=True)
    hist_len = len(state.ledger.snapshot_history)
    audit_len = len(state.ledger.audit_log)
    apply_confirmed_browser_sync_to_state(state, dom_aliases, confirmed_by_user=True)
    assert len(state.ledger.snapshot_history) == hist_len
    assert len(state.ledger.audit_log) == audit_len


def test_led03_ledger_save_does_not_unlink_before_atomic_replace(
    service: PortfolioStateService,
) -> None:
    state = service.load_state()
    ledger_path = state.ledger_path
    assert ledger_path.exists()
    original_bytes = ledger_path.read_bytes()
    original_settled = state.ledger.settled_cash_tnd

    # Mutate in-memory state so atomic_write_text does not short-circuit as byte-identical
    state.ledger.settled_cash_tnd = original_settled + Decimal("1.000")
    with patch("bvmt.snapshots.os.replace", side_effect=OSError("disk full simulated")):
        with pytest.raises(OSError):
            state.ledger.save(ledger_path)

    # Prior confirmed ledger MUST STILL exist intact on disk!
    assert ledger_path.exists()
    assert ledger_path.read_bytes() == original_bytes
    reloaded = PortfolioLedger.load(ledger_path)
    assert reloaded.settled_cash_tnd == original_settled


def test_led04_toctou_confirm_409_and_reject_persists_across_restart(
    service: PortfolioStateService,
) -> None:
    snap_a = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-10T09:00:00+00:00"),
        portfolio_total_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49500.000"),
        holdings_market_value_tnd=Decimal("500.000"),
        holdings=(
            BrowserHoldingItem(
                symbol="BH BANK",
                quantity=25,
                acquisition_price_tnd=Decimal("20.000"),
                acquisition_amount_tnd=Decimal("500.000"),
                latest_price_tnd=Decimal("20.000"),
                market_value_tnd=Decimal("500.000"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
        ),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
        snapshot_id="snap_toctou_a",
    )
    snap_b = replace(
        snap_a,
        retrieved_at=datetime.fromisoformat("2026-11-10T09:05:00+00:00"),
        portfolio_total_tnd=Decimal("50100.000"),
        available_cash_tnd=Decimal("49600.000"),
        snapshot_id="snap_toctou_b",
    )
    save_browser_snapshot(snap_a, service.snapshots_dir)
    save_browser_snapshot(snap_b, service.snapshots_dir)

    with TestClient(create_app(service)) as client:
        prev = client.get("/api/sync/preview").json()
        assert prev["candidate_snapshot"]["snapshot_id"] == "snap_toctou_b"

        # Mismatched expected_snapshot_id -> 409 Conflict
        conflict = client.post(
            "/api/sync/confirm",
            json={"confirmed_by_user": True, "expected_snapshot_id": "snap_toctou_a"},
        )
        assert conflict.status_code == 409, conflict.text

        # Reject snap_toctou_b -> cleared from pending across fresh dashboard state reload!
        rej = client.post(
            "/api/sync/reject",
            json={"snapshot_id": "snap_toctou_b", "reason": "Wrong test capture"},
        )
        assert rej.status_code == 200, rej.text

    restarted_state = build_dashboard_state(
        bars_path=service.requested_bars_path,
        ledger_path=service.requested_ledger_path,
        real_snapshot_path=service.real_snapshot_path,
        snapshots_dir=service.snapshots_dir,
        alerts_path=service.alerts_path,
        calendar_path=service.calendar_path,
        instruments_path=service.instruments_path,
        competition_config_path=service.competition_config_path,
        llm_config_path=service.llm_config_path,
        doc_index_path=service.doc_index_path,
        portfolio_mode=service.portfolio_mode,
    )
    # After rejecting snap_b, pending falls back to older unconfirmed snap_a (or None if rejected too)
    assert restarted_state.pending_browser_snapshot is not None
    assert restarted_state.pending_browser_snapshot.snapshot_id == "snap_toctou_a"
    assert (
        restarted_state.latest_browser_snapshot is None
        or restarted_state.latest_browser_snapshot.snapshot_id != "snap_toctou_b"
    )


def test_ext06_popup_ui_gating_and_background_relay_runtime() -> None:
    popup_path = str(EXTENSION_DIR / "popup.js").replace("\\", "\\\\")
    script = f"""
const fs = require("fs");
const popupCode = fs.readFileSync("{popup_path}", "utf-8");
const domHandlers = {{}};
const makeEl = (id, initVal = "") => ({{
  id,
  value: initVal,
  innerText: "",
  innerHTML: "",
  className: "",
  disabled: false,
  style: {{ display: "none" }},
  _handlers: {{}},
  addEventListener(ev, fn) {{ this._handlers[ev] = fn; }},
}});
const els = {{
  tokenInput: makeEl("tokenInput", "tok_popup_1"),
  saveTokenBtn: makeEl("saveTokenBtn"),
  connectionStatus: makeEl("connectionStatus"),
  tabNotice: makeEl("tabNotice"),
  extractBtn: makeEl("extractBtn"),
  previewCard: makeEl("previewCard"),
  prevEquity: makeEl("prevEquity"),
  prevCash: makeEl("prevCash"),
  prevHoldings: makeEl("prevHoldings"),
  prevRank: makeEl("prevRank"),
  sendBtn: makeEl("sendBtn"),
  msgBox: makeEl("msgBox"),
}};
const document = {{
  addEventListener: (ev, fn) => {{ domHandlers[ev] = fn; }},
  getElementById: (id) => els[id],
}};
let extractPayload = {{
  success: false,
  error: "MISSING_BALANCES",
  validation_errors: ["Missing account balances"],
  account_equity: null,
  available_cash: null,
}};
const relayed = [];
const chrome = {{
  storage: {{ local: {{ get: async () => ({{ pairingToken: "tok_popup_1" }}), set: async () => {{}} }} }},
  tabs: {{ query: async () => [{{ id: 7, url: "https://www.tunisbourse-challenge.com/displayp.aspx", title: "Portefeuille" }}] }},
  scripting: {{ executeScript: async () => [{{ result: extractPayload }}] }},
  runtime: {{
    lastError: null,
    sendMessage: (msg, cb) => {{
      relayed.push(msg);
      cb({{ ok: true, status: 200, data: {{ success: true }} }});
    }},
  }},
}};
const fetch = async () => ({{ ok: true, status: 200, json: async () => ({{ status: "ok" }}) }});
const fn = new Function("document", "chrome", "fetch", "URL", popupCode);
fn(document, chrome, fetch, URL);
(async () => {{
  await domHandlers["DOMContentLoaded"]();
  await els.extractBtn._handlers["click"]();
  const invalidSendDisabled = els.sendBtn.disabled;
  const invalidMsg = els.msgBox.innerText;
  await els.sendBtn._handlers["click"]();
  const relayedAfterInvalid = relayed.length;

  extractPayload = {{
    success: true,
    extracted_at: "2026-11-11T10:00:00Z",
    source_schema_version: "2026.11-v2",
    source_page_type: "displayp.aspx",
    account_equity: "50000.000",
    available_cash: "49608.050",
    holdings: [{{ symbol: "BH BANK", quantity: 30 }}],
    transactions: [],
    pending_orders: [],
    competition_ranking: 5,
    total_participants: 100,
    displayed_overall_performance_pct: "0.000",
    is_reconciled: true,
    reconciliation_gap_tnd: "0.000",
    validation_errors: [],
  }};
  await els.extractBtn._handlers["click"]();
  const validSendDisabled = els.sendBtn.disabled;
  await els.sendBtn._handlers["click"]();
  console.log(JSON.stringify({{
    invalidSendDisabled,
    invalidMsg,
    relayedAfterInvalid,
    validSendDisabled,
    relayed,
  }}));
}})();
"""
    out = _run_node(script)
    assert out["invalidSendDisabled"] is True
    assert "Missing account balances" in str(out["invalidMsg"])
    assert out["relayedAfterInvalid"] == 0
    assert out["validSendDisabled"] is False
    relayed = out["relayed"]
    assert isinstance(relayed, list) and len(relayed) == 1
    assert relayed[0]["type"] == "BVMT_SYNC_UPLOAD"
    assert relayed[0]["pairingToken"] == "tok_popup_1"
    assert relayed[0]["payload"]["source_schema_version"] == "2026.11-v2"


def test_led05_incremental_partial_fills_and_sell_realized_pnl(
    service: PortfolioStateService,
) -> None:
    snap1 = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/displayp.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-08T10:00:00+00:00"),
        portfolio_total_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49350.000"),
        holdings_market_value_tnd=Decimal("650.000"),
        holdings=(
            BrowserHoldingItem(
                symbol="BH BANK",
                quantity=50,
                acquisition_price_tnd=Decimal("13.000"),
                acquisition_amount_tnd=Decimal("650.000"),
                latest_price_tnd=Decimal("13.000"),
                market_value_tnd=Decimal("650.000"),
                gain_tnd=Decimal("0.000"),
                gain_pct=Decimal("0.00"),
            ),
        ),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
        movements_page_captured=True,
        transactions=(
            BrowserTransactionItem(
                transaction_id="TX-BUY-1",
                order_id="ORD-PARTIAL",
                instrument_id="BH_BANK",
                symbol="BH BANK",
                side="BUY",
                filled_shares=20,
                execution_price_tnd=Decimal("13.000"),
                fee_tnd=Decimal("1.300"),
                executed_at="2026-11-08T09:50:00+00:00",
            ),
        ),
        pending_orders=(
            BrowserPendingOrderItem(
                order_id="ORD-PARTIAL",
                instrument_id="BH_BANK",
                symbol="BH BANK",
                side="BUY",
                requested_shares=50,
                filled_shares=20,
                remaining_shares=30,
                limit_price_tnd=Decimal("13.000"),
                submitted_at="2026-11-08T09:45:00+00:00",
                status="PARTIALLY_FILLED",
            ),
        ),
    )
    state = service.load_state()
    apply_confirmed_browser_sync_to_state(state, snap1, confirmed_by_user=True)
    assert len(state.ledger.orders["ORD-PARTIAL"].fills) == 1

    # Incremental second capture finishes ORD-PARTIAL and executes SELL 20 @ 14.000
    snap2 = CompetitionPortfolioDOMSnapshot(
        source_url="https://www.tunisbourse-challenge.com/display_histo.aspx",
        retrieved_at=datetime.fromisoformat("2026-11-09T11:00:00+00:00"),
        portfolio_total_tnd=Decimal("50000.000"),
        available_cash_tnd=Decimal("49350.000"),
        holdings_market_value_tnd=Decimal("0.000"),
        holdings=(),
        competition_rank=None,
        total_participants=None,
        displayed_overall_performance_pct=None,
        is_reconciled=True,
        reconciliation_gap_tnd=Decimal("0.000"),
        movements_page_captured=True,
        transactions=(
            BrowserTransactionItem(
                transaction_id="TX-BUY-2",
                order_id="ORD-PARTIAL",
                instrument_id="BH_BANK",
                symbol="BH BANK",
                side="BUY",
                filled_shares=30,
                execution_price_tnd=Decimal("13.000"),
                fee_tnd=Decimal("1.950"),
                executed_at="2026-11-09T10:15:00+00:00",
            ),
            BrowserTransactionItem(
                transaction_id="TX-SELL-1",
                order_id="ORD-SELL-1",
                instrument_id="BH_BANK",
                symbol="BH BANK",
                side="SELL",
                filled_shares=20,
                execution_price_tnd=Decimal("14.000"),
                fee_tnd=Decimal("1.400"),
                executed_at="2026-11-09T10:45:00+00:00",
            ),
        ),
        pending_orders=(),
    )
    apply_confirmed_browser_sync_to_state(state, snap2, confirmed_by_user=True)
    ord_partial = state.ledger.orders["ORD-PARTIAL"]
    assert [f.fill_id for f in ord_partial.fills] == ["TX-BUY-1", "TX-BUY-2"]
    assert ord_partial.filled_shares == 50
    assert ord_partial.remaining_shares == 0
    assert ord_partial.status == "EXECUTED"

    sell_ord = state.ledger.orders["ORD-SELL-1"]
    assert sell_ord.fills[0].realized_pnl_delta_tnd == Decimal("18.600")
    assert state.ledger.holdings["BH_BANK"].realized_pnl_tnd == Decimal("18.600")
    assert state.ledger.holdings["BH_BANK"].total_fees_paid_tnd == Decimal("4.650")
