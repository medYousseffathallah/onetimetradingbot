from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from bvmt.calendar import read_exchange_calendar, read_instrument_master
from bvmt.cli import main
from bvmt.dashboard import build_dashboard_state, discover_available_bar_datasets
from bvmt.data import aware_timestamp, read_bars_csv
from bvmt.features import rank_session_baseline
from bvmt.ledger import (
    CompetitionAccountSnapshot,
    PortfolioLedger,
    compute_commission,
    export_ledger_holdings_csv,
    export_ledger_transactions_csv,
    parse_account_holdings_csv,
    parse_account_pending_orders_csv,
    parse_account_transactions_csv,
    quantize_tnd,
)
from bvmt.llm import evaluate_dry_run, load_llm_budget_config
from bvmt.notifications import NotificationCenter
from bvmt.recommendations import (
    generate_recommendations,
)
from bvmt.rules import competition_blockers

ROOT = Path(__file__).resolve().parents[1]
BARS_PATH = ROOT / "tests/fixtures/daily_bars.csv"
CALENDAR_PATH = ROOT / "tests/fixtures/exchange_calendar.csv"
INSTRUMENTS_PATH = ROOT / "tests/fixtures/instrument_master.csv"
COMP_CONFIG_PATH = ROOT / "configs/competition.json"
LLM_CONFIG_PATH = ROOT / "configs/llm_budget.example.json"


def test_end_to_end_manual_trading_simulation_and_persistence(tmp_path):
    """Phase 6C: Complete 12-step manual trading simulation with Decimal reconciliation and restart persistence."""
    ledger_path = tmp_path / "portfolio" / "ledger.json"
    t0 = aware_timestamp("2026-01-09T09:30:00+00:00")

    # 1. Initialize a virtual portfolio (100,000.000 TND)
    ledger = PortfolioLedger(initial_cash_tnd=Decimal("100000.000"), created_at=t0)
    assert ledger.settled_cash_tnd == Decimal("100000.000")
    assert ledger.available_cash_tnd == Decimal("100000.000")
    assert ledger.reserved_cash_tnd == Decimal("0.000")

    # 2. Generate a stock recommendation from session-aware baseline
    instruments = read_instrument_master(INSTRUMENTS_PATH)
    calendar = read_exchange_calendar(CALENDAR_PATH)
    bars = read_bars_csv(BARS_PATH)
    cutoff = aware_timestamp("2026-01-09T17:00:00+00:00")

    baseline = rank_session_baseline(
        instruments,
        calendar,
        bars,
        cutoff,
        short_lookback=2,
        long_lookback=3,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )
    comp_doc = json.loads(COMP_CONFIG_PATH.read_text(encoding="utf-8"))
    blockers = competition_blockers(comp_doc)

    rec_report = generate_recommendations(
        baseline,
        ledger,
        generated_at=cutoff,
        simulation_profile="SYNTHETIC_DEMO",
        data_is_synthetic=True,
        rule_blocker_count=len(blockers),
    )
    cards_by_id = {c.instrument_id: c for c in rec_report.recommendations}
    assert cards_by_id["DEMO_A"].category == "BUY CANDIDATE"
    assert cards_by_id["DEMO_A"].suggested_side == "BUY"
    assert cards_by_id["DEMO_A"].suggested_shares > 0
    assert cards_by_id["DEMO_B"].category == "NO TRADE"
    assert cards_by_id["DEMO_C"].category == "NO TRADE"

    buy_card = cards_by_id["DEMO_A"]

    # 3. Record a pending buy order (100 shares of DEMO_A @ 10.800 TND)
    t1 = aware_timestamp("2026-01-09T10:00:00+00:00")
    order_buy = ledger.record_pending_order(
        order_id="ORD-SIM-001",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="BUY",
        quantity=100,
        limit_price_tnd=Decimal("10.800"),
        submitted_at=t1,
        recommendation_id=buy_card.recommendation_id,
        notes="Manual entry on competition portal",
    )
    assert order_buy.status == "PENDING"

    # 4. Verify cash reservation: gross = 100 * 10.800 = 1080.000; 0.50% fee = 5.400; reserved = 1085.400
    assert order_buy.reserved_cash_tnd == Decimal("1085.400")
    assert ledger.reserved_cash_tnd == Decimal("1085.400")
    assert ledger.settled_cash_tnd == Decimal("100000.000")
    assert ledger.available_cash_tnd == Decimal("98914.600")

    # Verify recommendation engine now flags pending-order conflict if re-run while order is open
    rec_while_pending = generate_recommendations(
        baseline,
        ledger,
        generated_at=cutoff,
        simulation_profile="SYNTHETIC_DEMO",
        data_is_synthetic=True,
    )
    demo_a_pending_card = {c.instrument_id: c for c in rec_while_pending.recommendations}["DEMO_A"]
    assert demo_a_pending_card.category == "NO TRADE"
    assert any("pending_order_conflict" in r for r in demo_a_pending_card.blocked_reasons)

    # 5. Record a partial execution (60 of 100 shares filled @ 10.800 TND)
    t2 = aware_timestamp("2026-01-09T11:15:00+00:00")
    partial_order = ledger.record_execution_fill(
        order_id="ORD-SIM-001",
        filled_shares=60,
        execution_price_tnd=Decimal("10.800"),
        executed_at=t2,
        notes="Partial fill of 60 shares",
    )
    assert partial_order.status == "PARTIALLY_FILLED"
    assert partial_order.filled_shares == 60
    assert partial_order.remaining_shares == 40

    # 6. Verify updated holdings and remaining reserved cash
    # 60 shares @ 10.800 = 648.000 gross + 3.240 fee = 651.240 cost basis (avg cost = 10.854 TND/sh)
    # Remaining 40 shares @ 10.800 = 432.000 gross + 2.160 fee = 434.160 still reserved
    pos_a = ledger.holdings["DEMO_A"]
    assert pos_a.total_shares == 60
    assert pos_a.cost_basis_tnd == Decimal("651.240")
    assert pos_a.average_cost_tnd == Decimal("10.854")
    assert pos_a.total_fees_paid_tnd == Decimal("3.240")
    assert ledger.settled_cash_tnd == Decimal("99348.760")
    assert ledger.reserved_cash_tnd == Decimal("434.160")
    assert ledger.available_cash_tnd == Decimal("98914.600")

    # 7. Cancel the remaining 40 shares
    t3 = aware_timestamp("2026-01-09T13:30:00+00:00")
    cancelled_order = ledger.close_open_order(
        order_id="ORD-SIM-001",
        terminal_status="CANCELLED",
        closed_at=t3,
        reason="Cancelled unfilled balance before session close",
    )
    assert cancelled_order.status == "CANCELLED"
    assert cancelled_order.remaining_shares == 0

    # 8. Verify released cash
    assert ledger.reserved_cash_tnd == Decimal("0.000")
    assert ledger.available_cash_tnd == Decimal("99348.760")

    # 9. Record a sell execution (sell 20 of 60 shares @ 12.000 TND)
    t4 = aware_timestamp("2026-01-12T10:00:00+00:00")
    ledger.record_pending_order(
        order_id="ORD-SIM-002",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="SELL",
        quantity=20,
        limit_price_tnd=Decimal("12.000"),
        submitted_at=t4,
    )
    assert ledger.holdings["DEMO_A"].reserved_sell_shares == 20
    assert ledger.holdings["DEMO_A"].available_shares == 40

    t5 = aware_timestamp("2026-01-12T11:00:00+00:00")
    sell_order = ledger.record_execution_fill(
        order_id="ORD-SIM-002",
        filled_shares=20,
        execution_price_tnd=Decimal("12.000"),
        executed_at=t5,
    )
    assert sell_order.status == "EXECUTED"

    # 10. Verify realized P&L and transaction fees
    # Sell 20 @ 12.000: gross = 240.000, fee (0.50%) = 1.200, net proceeds = 238.800
    # Removed cost basis for 20 of 60 shares = 651.240 * (20/60) = 217.080
    # Realized P&L = 238.800 - 217.080 = +21.720 TND
    # Total fees paid = 3.240 + 1.200 = 4.440 TND
    # Remaining shares = 40, remaining cost basis = 434.160 TND
    pos_after_sell = ledger.holdings["DEMO_A"]
    assert pos_after_sell.total_shares == 40
    assert pos_after_sell.reserved_sell_shares == 0
    assert pos_after_sell.cost_basis_tnd == Decimal("434.160")
    assert pos_after_sell.realized_pnl_tnd == Decimal("21.720")
    assert pos_after_sell.total_fees_paid_tnd == Decimal("4.440")
    assert ledger.settled_cash_tnd == Decimal("99587.560")

    # 11. Save & restart the application (reload from disk)
    ledger.save(ledger_path)
    reloaded = PortfolioLedger.load(ledger_path)

    # 12. Confirm all portfolio and order data persists identically
    assert reloaded.settled_cash_tnd == Decimal("99587.560")
    assert reloaded.available_cash_tnd == Decimal("99587.560")
    assert reloaded.reserved_cash_tnd == Decimal("0.000")
    assert reloaded.holdings["DEMO_A"].total_shares == 40
    assert reloaded.holdings["DEMO_A"].realized_pnl_tnd == Decimal("21.720")
    assert reloaded.holdings["DEMO_A"].total_fees_paid_tnd == Decimal("4.440")
    assert len(reloaded.orders) == 2
    assert len(reloaded.audit_log) == len(ledger.audit_log)


def test_failure_scenarios_fail_safely(tmp_path):
    """Phase 6D: Verify all 11 failure scenarios fail closed and safely."""
    t0 = aware_timestamp("2026-01-05T09:00:00+00:00")
    ledger = PortfolioLedger(initial_cash_tnd=Decimal("100000.000"), created_at=t0)

    # 1. Insufficient cash
    with pytest.raises(ValueError, match="Insufficient available cash"):
        ledger.record_pending_order(
            order_id="ORD-FAIL-CASH",
            instrument_id="DEMO_A",
            symbol="DEMO_A",
            side="BUY",
            quantity=20000,
            limit_price_tnd=Decimal("10.000"),
            submitted_at=t0,
            enforce_concentration_cap=False,
        )

    # 2. Attempted sale of unowned shares (short selling prohibited)
    with pytest.raises(ValueError, match="short selling prohibited"):
        ledger.record_pending_order(
            order_id="ORD-FAIL-SHORT",
            instrument_id="DEMO_A",
            symbol="DEMO_A",
            side="SELL",
            quantity=10,
            limit_price_tnd=Decimal("10.000"),
            submitted_at=t0,
        )

    # 3. Concentration-limit violation (> 10% of 100,000 TND equity = 10,000 TND)
    with pytest.raises(ValueError, match="10% concentration limit exceeded"):
        ledger.record_pending_order(
            order_id="ORD-FAIL-CAP",
            instrument_id="DEMO_A",
            symbol="DEMO_A",
            side="BUY",
            quantity=1100,
            limit_price_tnd=Decimal("10.000"),  # 11,000 TND > 10,000 TND cap
            submitted_at=t0,
        )

    # 4. Duplicate orders (same order_id, same recommendation_id, or second open order on same stock)
    ledger.record_pending_order(
        order_id="ORD-OK-1",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="BUY",
        quantity=50,
        limit_price_tnd=Decimal("10.000"),
        submitted_at=t0,
        recommendation_id="REC-20260105-DEMOA-01",
    )
    with pytest.raises(ValueError, match="Duplicate order_id"):
        ledger.record_pending_order(
            order_id="ORD-OK-1",
            instrument_id="DEMO_B",
            symbol="DEMO_B",
            side="BUY",
            quantity=10,
            limit_price_tnd=Decimal("20.000"),
            submitted_at=t0,
        )
    with pytest.raises(ValueError, match="Duplicate order submission"):
        ledger.record_pending_order(
            order_id="ORD-DUP-REC",
            instrument_id="DEMO_B",
            symbol="DEMO_B",
            side="BUY",
            quantity=10,
            limit_price_tnd=Decimal("20.000"),
            submitted_at=t0,
            recommendation_id="REC-20260105-DEMOA-01",
        )
    with pytest.raises(ValueError, match="Duplicate open order prevented"):
        ledger.record_pending_order(
            order_id="ORD-DUP-INST",
            instrument_id="DEMO_A",
            symbol="DEMO_A",
            side="BUY",
            quantity=10,
            limit_price_tnd=Decimal("10.000"),
            submitted_at=t0,
        )

    # 5. Missing market data & 6. Stale prices & 7. Expired pending orders & 8. Computer restart catch-up
    calendar = read_exchange_calendar(CALENDAR_PATH)
    alerts_path = tmp_path / "alerts.json"
    nc = NotificationCenter(last_evaluated_at_utc="2026-01-05T15:00:00+00:00")

    # Evaluate 8 days later (2026-01-13) with no market data -> triggers catch-up + missing data + 7-day order expiry
    now_restart = aware_timestamp("2026-01-13T10:00:00+00:00")
    created_alerts = nc.evaluate(
        now=now_restart,
        calendar=calendar,
        latest_bar_session=None,
        ledger=ledger,
    )
    assert len(nc.missed_open_sessions_on_last_startup) == 4  # Jan 6, 7, 8, 9
    categories = {a.category for a in created_alerts}
    assert "ALERT_DATA_STALE" in categories
    assert "ALERT_ORDER_EXPIRY" in categories
    assert all(a.caught_up_after_power_off is True for a in created_alerts)

    # Save & reload NotificationCenter; re-evaluating same state produces 0 duplicate alerts
    nc.save(alerts_path)
    nc_reloaded = NotificationCenter.load(alerts_path)
    dup_alerts = nc_reloaded.evaluate(
        now=now_restart,
        calendar=calendar,
        latest_bar_session=None,
        ledger=ledger,
    )
    assert len(dup_alerts) == 0
    assert len(nc_reloaded.active_alerts()) == len(created_alerts)

    # 9. Invalid imported CSV quarantine check via CLI
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(
        "instrument_id,symbol,session_date,open,high,low,close,volume_shares,turnover_tnd,status,source_id,published_at,ingested_at\n"
        "BAD,BAD,2026-01-05,10.000,9.000,11.000,10.000,-5,100.000,traded,test,2026-01-05T16:00:00+00:00,2026-01-05T16:05:00+00:00\n",
        encoding="utf-8",
    )
    rc = main(
        [
            "import-csv",
            str(bad_csv),
            "--source-id",
            "bad_test",
            "--retrieved-at",
            "2026-01-05T17:00:00+00:00",
            "--raw-dir",
            str(tmp_path / "raw"),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert rc == 1  # Fails safely because 0 accepted rows

    # 10. Missing Alibaba credentials & 11. Expired Alibaba allowance
    llm_cfg = load_llm_budget_config(LLM_CONFIG_PATH)
    expired_dt = aware_timestamp("2026-11-08T01:00:00+00:00")
    dry_exp = evaluate_dry_run(
        llm_cfg,
        model_label="qwen3.7-text-embedding",
        role="document_chunk_embedding_pilot",
        prompt_version="v1",
        text_payload="Test payload",
        now=expired_dt,
        ledger_override_path=tmp_path / "llm_ledger.json",
    )
    assert dry_exp.permitted_for_local_budget_and_expiry is False
    assert dry_exp.permitted_for_live_network_call is False
    assert any("model_allowance_expired" in b for b in dry_exp.blockers)
    assert any("env_DASHSCOPE_API_KEY_missing" in b for b in dry_exp.blockers)


def test_recommendation_hold_reduce_and_sell_candidate_states(tmp_path):
    """Verify HOLD, REDUCE, and SELL CANDIDATE states when portfolio already holds positions."""
    t0 = aware_timestamp("2026-01-05T09:00:00+00:00")
    ledger = PortfolioLedger(initial_cash_tnd=Decimal("100000.000"), created_at=t0)

    # Buy 500 shares of DEMO_A @ 10.000 (~5.4% weight -> HOLD)
    ledger.record_pending_order(
        order_id="ORD-HOLD-1",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="BUY",
        quantity=500,
        limit_price_tnd=Decimal("10.000"),
        submitted_at=t0,
    )
    ledger.record_execution_fill(
        order_id="ORD-HOLD-1",
        filled_shares=500,
        execution_price_tnd=Decimal("10.000"),
        executed_at=t0,
    )

    # Buy 200 shares of DEMO_B @ 20.000 (DEMO_B has negative momentum -> SELL CANDIDATE)
    ledger.record_pending_order(
        order_id="ORD-SELL-1",
        instrument_id="DEMO_B",
        symbol="DEMO_B",
        side="BUY",
        quantity=200,
        limit_price_tnd=Decimal("20.000"),
        submitted_at=t0,
    )
    ledger.record_execution_fill(
        order_id="ORD-SELL-1",
        filled_shares=200,
        execution_price_tnd=Decimal("20.000"),
        executed_at=t0,
    )

    instruments = read_instrument_master(INSTRUMENTS_PATH)
    calendar = read_exchange_calendar(CALENDAR_PATH)
    bars = read_bars_csv(BARS_PATH)
    cutoff = aware_timestamp("2026-01-09T17:00:00+00:00")
    baseline = rank_session_baseline(
        instruments,
        calendar,
        bars,
        cutoff,
        short_lookback=2,
        long_lookback=3,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=Decimal("5000"),
    )

    rec1 = generate_recommendations(baseline, ledger, generated_at=cutoff)
    by_id1 = {c.instrument_id: c for c in rec1.recommendations}
    assert by_id1["DEMO_A"].category == "HOLD"
    assert by_id1["DEMO_B"].category == "SELL CANDIDATE"
    assert by_id1["DEMO_B"].suggested_side == "SELL"
    assert by_id1["DEMO_B"].suggested_shares == 200

    # Now add 450 more shares of DEMO_A @ 10.000 (total 950 shares @ 10.800 = 10,260 TND > 9.5% trigger -> REDUCE)
    ledger.record_pending_order(
        order_id="ORD-REDUCE-1",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="BUY",
        quantity=450,
        limit_price_tnd=Decimal("10.000"),
        submitted_at=t0,
        enforce_concentration_cap=False,
    )
    ledger.record_execution_fill(
        order_id="ORD-REDUCE-1",
        filled_shares=450,
        execution_price_tnd=Decimal("10.000"),
        executed_at=t0,
    )
    rec2 = generate_recommendations(baseline, ledger, generated_at=cutoff)
    by_id2 = {c.instrument_id: c for c in rec2.recommendations}
    assert by_id2["DEMO_A"].category == "REDUCE"
    assert by_id2["DEMO_A"].suggested_side == "SELL"
    assert by_id2["DEMO_A"].suggested_shares > 0


def test_cli_portfolio_and_recommend_commands(tmp_path, capsys):
    ledger_file = tmp_path / "cli_ledger.json"
    assert main(["portfolio-init", "--ledger", str(ledger_file)]) == 0
    capsys.readouterr()

    assert (
        main(
            [
                "order-submit",
                "--ledger",
                str(ledger_file),
                "--order-id",
                "ORD-CLI-1",
                "--instrument-id",
                "DEMO_A",
                "--symbol",
                "DEMO_A",
                "--side",
                "BUY",
                "--quantity",
                "50",
                "--limit-price",
                "10.800",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "order-fill",
                "--ledger",
                str(ledger_file),
                "--order-id",
                "ORD-CLI-1",
                "--filled-shares",
                "50",
                "--execution-price",
                "10.800",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["recommend", "--ledger", str(ledger_file)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["simulation_profile"] == "SYNTHETIC_DEMO"
    assert len(out["recommendations"]) >= 3


def test_dashboard_state_builder(tmp_path):
    state = build_dashboard_state(
        ledger_path=tmp_path / "ledger.json",
        alerts_path=tmp_path / "alerts.json",
    )
    assert state.data_is_synthetic is True
    assert len(state.rule_blockers) > 0
    assert len(state.recommendations.recommendations) >= 3
    assert len(state.notifications.active_alerts()) >= 1
    assert quantize_tnd(compute_commission(Decimal("1000.000"))) == Decimal("5.000")


def test_dashboard_all_six_pages_render_without_exception(tmp_path):
    """Phase 6B: Verify all 6 dashboard pages (Overview, Stock Opportunities, Portfolio, Manual Order Journal, Research and Documents, System Health) render cleanly."""
    from bvmt.dashboard import (
        _render_opportunities_page,
        _render_order_journal_page,
        _render_overview_page,
        _render_portfolio_page,
        _render_research_page,
        _render_system_health_page,
        _render_top_banners,
    )

    class _FakeColumn:
        def metric(self, *args, **kwargs):
            return None

        def text_input(self, label, value="", **kwargs):
            return value

        def selectbox(self, label, options, **kwargs):
            return options[0] if options else ""

        def number_input(self, label, min_value=1, value=1, **kwargs):
            return value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _FakeStreamlit:
        def __init__(self) -> None:
            self.markdowns: list[str] = []
            self.subheaders: list[str] = []
            self.dataframes: list[object] = []
            self.session_state: dict[str, object] = {}

        def markdown(self, text: str, **kwargs) -> None:
            self.markdowns.append(text)

        def subheader(self, text: str) -> None:
            self.subheaders.append(text)

        def caption(self, text: str) -> None:
            return None

        def write(self, obj: object) -> None:
            return None

        def code(self, text: str, **kwargs) -> None:
            return None

        def info(self, text: str) -> None:
            self.markdowns.append(text)

        def success(self, text: str) -> None:
            self.markdowns.append(text)

        def warning(self, text: str) -> None:
            self.markdowns.append(text)

        def error(self, text: str) -> None:
            self.markdowns.append(text)

        def json(self, obj: object) -> None:
            return None

        def dataframe(self, data: object, **kwargs) -> None:
            self.dataframes.append(data)

        def columns(self, count: int):
            return [_FakeColumn() for _ in range(count)]

        def tabs(self, labels: list[str]):
            return [_FakeColumn() for _ in labels]

        def expander(self, label: str, **kwargs):
            return _FakeColumn()

        def form(self, key: str):
            return _FakeColumn()

        def button(self, label: str, **kwargs) -> bool:
            return False

        def checkbox(self, label: str, value: bool = False, **kwargs) -> bool:
            return value

        def form_submit_button(self, label: str) -> bool:
            return False

        def text_input(self, label: str, value: str = "", **kwargs) -> str:
            return value

        def text_area(self, label: str, value: str = "", **kwargs) -> str:
            return value

        def selectbox(self, label: str, options: list[str], **kwargs) -> str:
            return options[0] if options else ""

        def rerun(self) -> None:
            return None

    state = build_dashboard_state(
        ledger_path=tmp_path / "ledger.json",
        alerts_path=tmp_path / "alerts.json",
    )
    fake_st = _FakeStreamlit()

    _render_top_banners(fake_st, state)
    assert any("SYNTHETIC DEMO MODE" in m for m in fake_st.markdowns)
    assert any("COMPETITION RULES STATUS: BLOCKED" in m for m in fake_st.markdowns)

    _render_overview_page(fake_st, state)
    _render_opportunities_page(fake_st, state)
    _render_portfolio_page(fake_st, state)
    _render_order_journal_page(fake_st, state)
    _render_research_page(fake_st, state)
    _render_system_health_page(fake_st, state)

    assert len(fake_st.subheaders) == 6
    assert len(fake_st.dataframes) >= 5


def test_streamlit_apptest_full_navigation_and_order_forms():
    """Phase 6B: Run real Streamlit AppTest engine across all 6 navigation pages with zero exceptions."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "src/bvmt/dashboard.py"), default_timeout=30)
    at.run()
    assert not at.exception

    # Verify default Overview page rendered metrics and banners
    assert any("1. Portfolio & Market Overview" in s.value for s in at.subheader)
    assert any("SYNTHETIC DEMO MODE" in m.value for m in at.markdown)
    assert any("COMPETITION RULES STATUS: BLOCKED" in m.value for m in at.markdown)

    # Navigate through every required page via sidebar radio and confirm zero exceptions
    pages = [
        ("Stock Opportunities", "2. Stock Opportunities"),
        ("Portfolio", "3. Portfolio Holdings"),
        ("Manual Order Journal", "4. Manual Order Journal"),
        ("Research and Documents", "5. Research, Corporate Events"),
        ("System Health", "6. System Health"),
        ("Overview", "1. Portfolio & Market Overview"),
    ]
    for page_label, expected_subheader in pages:
        at.sidebar.radio[0].set_value(page_label).run()
        assert not at.exception, f"Exception on page {page_label}: {at.exception}"
        assert any(expected_subheader in s.value for s in at.subheader), (
            f"Missing subheader '{expected_subheader}' on page '{page_label}'"
        )


def test_g1_competition_csv_import_export_and_valuation_history():
    """Task G1: Verify CSV import/export (English & French conventions) and historical portfolio valuation series."""
    t0 = aware_timestamp("2026-01-05T09:00:00+00:00")
    ledger = PortfolioLedger(initial_cash_tnd=Decimal("100000.000"), created_at=t0)

    # Parse French semicolon holdings CSV with comma decimals
    french_holdings_csv = (
        "valeur;libelle;quantite;cmp;plus_value_realisee;frais_totaux\n"
        "DEMO_A;DEMO_A;100;10,854;0,000;5,400\n"
    )
    holdings = parse_account_holdings_csv(french_holdings_csv)
    assert len(holdings) == 1
    assert holdings[0].instrument_id == "DEMO_A"
    assert holdings[0].total_shares == 100
    assert holdings[0].average_cost_tnd == Decimal("10.854")
    assert holdings[0].total_fees_paid_tnd == Decimal("5.400")

    # Parse executed transactions CSV (with automatic 0.50% fee when fee column is empty)
    tx_csv = (
        "transaction_id,order_id,instrument_id,symbol,side,filled_shares,execution_price_tnd,fee_tnd,executed_at\n"
        "TX-101,ORD-101,DEMO_A,DEMO_A,BUY,100,10.800,,2026-01-06T10:30:00+00:00\n"
    )
    txs = parse_account_transactions_csv(tx_csv)
    assert len(txs) == 1
    assert txs[0].fee_tnd == Decimal("5.400")

    # Parse pending orders CSV (including partial fill status inference)
    pend_csv = (
        "order_id,instrument_id,symbol,side,requested_shares,filled_shares,remaining_shares,limit_price_tnd,submitted_at\n"
        "ORD-102,DEMO_B,DEMO_B,BUY,80,30,50,20.000,2026-01-08T11:00:00+00:00\n"
    )
    pends = parse_account_pending_orders_csv(pend_csv)
    assert len(pends) == 1
    assert pends[0].status == "PARTIALLY_FILLED"
    assert pends[0].remaining_shares == 50

    # Record a dated trade and verify historical portfolio valuation across fixture bars
    ledger.record_pending_order(
        order_id="ORD-HIST-1",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="BUY",
        quantity=100,
        limit_price_tnd=Decimal("10.000"),
        submitted_at=aware_timestamp("2026-01-05T10:00:00+00:00"),
    )
    ledger.record_execution_fill(
        order_id="ORD-HIST-1",
        filled_shares=100,
        execution_price_tnd=Decimal("10.000"),
        executed_at=aware_timestamp("2026-01-05T11:00:00+00:00"),
    )

    bars = read_bars_csv(BARS_PATH)
    history = ledger.compute_valuation_history(bars)
    assert len(history) >= 3
    assert history[0].session_date == "2026-01-05"
    assert history[-1].session_date == "2026-01-09"
    # On 2026-01-09 DEMO_A closes at 10.800 -> 100 shares = 1080.000 MV; cost basis = 1005.000 -> unrealized = +75.000
    assert history[-1].holdings_market_value_tnd == Decimal("1080.000")
    assert history[-1].unrealized_pnl_tnd == Decimal("75.000")
    assert history[-1].cumulative_fees_tnd == Decimal("5.000")

    holdings_export = export_ledger_holdings_csv(ledger, {"DEMO_A": Decimal("10.800")})
    tx_export = export_ledger_transactions_csv(ledger)
    assert "DEMO_A,DEMO_A,100" in holdings_export
    assert "ORD-HIST-1-F01,ORD-HIST-1,DEMO_A" in tx_export


def test_g2_reconciliation_detects_all_six_discrepancy_types_and_requires_confirmation():
    """Task G2: Verify detection of all 6 discrepancy categories and enforce explicit user confirmation before mutating ledger."""
    t0 = aware_timestamp("2026-01-05T09:00:00+00:00")
    ledger = PortfolioLedger(initial_cash_tnd=Decimal("100000.000"), created_at=t0)

    # Local state: 1 open order on DEMO_B (ORD-LOCAL-ONLY) and 50 shares of DEMO_A
    ledger.record_pending_order(
        order_id="ORD-LOCAL-A",
        instrument_id="DEMO_A",
        symbol="DEMO_A",
        side="BUY",
        quantity=50,
        limit_price_tnd=Decimal("10.000"),
        submitted_at=t0,
    )
    ledger.record_execution_fill(
        order_id="ORD-LOCAL-A",
        filled_shares=50,
        execution_price_tnd=Decimal("10.000"),
        executed_at=t0,
    )
    ledger.record_pending_order(
        order_id="ORD-LOCAL-ONLY",
        instrument_id="DEMO_B",
        symbol="DEMO_B",
        side="BUY",
        quantity=10,
        limit_price_tnd=Decimal("20.000"),
        submitted_at=t0,
    )

    cash_before = ledger.settled_cash_tnd
    audit_len_before = len(ledger.audit_log)

    # Construct a competition snapshot containing all 6 discrepancy types:
    # 1. cash_mismatch: settled cash is 98900.000 instead of 99497.500
    # 2. missing_transaction: TX-NEW-1 (50 more shares of DEMO_A)
    # 3. duplicate_transaction: TX-DUP-1 appears twice in snapshot.transactions
    # 4. share_quantity_mismatch: DEMO_A has 100 shares in snapshot vs 50 locally
    # 5. unmatched_pending_order: ORD-LOCAL-ONLY is missing in snapshot, and ORD-ACCT-PEND is new in snapshot
    # 6. fee_mismatch: TX-NEW-1 reports 3.500 TND fee instead of 0.50% (2.500 TND)
    snapshot = CompetitionAccountSnapshot(
        as_of="2026-01-09T16:00:00+00:00",
        settled_cash_tnd=Decimal("98900.000"),
        available_cash_tnd=Decimal("98400.000"),
        holdings=parse_account_holdings_csv(
            "instrument_id,symbol,total_shares,average_cost_tnd,realized_pnl_tnd,total_fees_paid_tnd\n"
            "DEMO_A,DEMO_A,100,10.060,0.000,6.000\n"
        ),
        transactions=parse_account_transactions_csv(
            "transaction_id,order_id,instrument_id,symbol,side,filled_shares,execution_price_tnd,fee_tnd,executed_at\n"
            "ORD-LOCAL-A-F01,ORD-LOCAL-A,DEMO_A,DEMO_A,BUY,50,10.000,2.500,2026-01-05T09:00:00+00:00\n"
            "TX-NEW-1,ORD-ACCT-2,DEMO_A,DEMO_A,BUY,50,10.000,3.500,2026-01-06T10:00:00+00:00\n"
            "TX-NEW-1,ORD-ACCT-2,DEMO_A,DEMO_A,BUY,50,10.000,3.500,2026-01-06T10:00:00+00:00\n"
        ),
        pending_orders=parse_account_pending_orders_csv(
            "order_id,instrument_id,symbol,side,requested_shares,filled_shares,remaining_shares,limit_price_tnd,status,submitted_at\n"
            "ORD-ACCT-PEND,DEMO_C,DEMO_C,BUY,25,0,25,19.000,PENDING,2026-01-09T11:00:00+00:00\n"
        ),
    )

    eval_dt = aware_timestamp("2026-01-09T17:00:00+00:00")
    report = ledger.reconcile_with_snapshot(snapshot, evaluated_at=eval_dt)
    assert report.is_reconciled is False
    assert report.requires_user_confirmation is True

    found_types = {d.discrepancy_type for d in report.discrepancies}
    assert "cash_mismatch" in found_types
    assert "missing_transaction" in found_types
    assert "duplicate_transaction" in found_types
    assert "share_quantity_mismatch" in found_types
    assert "unmatched_pending_order" in found_types
    assert "fee_mismatch" in found_types

    # Verify read-only guarantee: ledger was NOT mutated by reconcile_with_snapshot
    assert ledger.settled_cash_tnd == cash_before
    assert ledger.holdings["DEMO_A"].total_shares == 50
    assert len(ledger.audit_log) == audit_len_before

    # Verify applying without explicit confirmation raises ValueError and does NOT mutate ledger
    with pytest.raises(ValueError, match="Explicit user confirmation"):
        ledger.apply_reconciliation_snapshot(
            snapshot,
            confirmed_by_user=False,
            applied_at=eval_dt,
        )
    assert ledger.settled_cash_tnd == cash_before
    assert ledger.holdings["DEMO_A"].total_shares == 50

    # Verify applying WITH explicit user confirmation updates ledger and logs audit entry
    applied = ledger.apply_reconciliation_snapshot(
        snapshot,
        confirmed_by_user=True,
        applied_at=eval_dt,
        notes="Confirmed sync with competition portal",
    )
    assert len(applied.discrepancies) >= 6
    assert ledger.settled_cash_tnd == Decimal("98900.000")
    assert ledger.holdings["DEMO_A"].total_shares == 100
    assert ledger.orders["ORD-ACCT-PEND"].status == "PENDING"
    assert ledger.orders["ORD-LOCAL-ONLY"].status == "CANCELLED"
    assert ledger.audit_log[-1].event_type == "RECONCILIATION_ADJUSTMENT_APPLIED"


def test_g3_dataset_discovery_and_dashboard_freshness(tmp_path):
    """Task G3: Verify dataset discovery for imported canonical CSVs and dashboard freshness/valuation state."""
    proc_dir = tmp_path / "processed" / "bvmt_official_2026"
    proc_dir.mkdir(parents=True)
    imported_csv = proc_dir / "daily_bars.canonical.csv"
    imported_csv.write_text(BARS_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    discovered = discover_available_bar_datasets(
        processed_root=tmp_path / "processed",
        default_bars_path=BARS_PATH,
    )
    assert len(discovered) == 2
    assert any("VERIFIED IMPORT: bvmt_official_2026" in k for k in discovered)
    assert any("SYNTHETIC DEMO:" in k for k in discovered)

    state = build_dashboard_state(
        ledger_path=tmp_path / "ledger.json",
        alerts_path=tmp_path / "alerts.json",
        bars_path=imported_csv,
    )
    assert state.data_freshness_sessions_behind == 0
    assert len(state.valuation_history) >= 3

