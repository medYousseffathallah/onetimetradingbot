"""Local Streamlit trading decision-support dashboard (Milestone 1C).

Provides a 6-page financial terminal UI over localhost:
1. Overview
2. Stock Opportunities
3. Portfolio
4. Manual Order Journal
5. Research and Documents
6. System Health

Never submits orders automatically, never assumes a recommendation has been executed,
and prominently distinguishes SYNTHETIC DEMO DATA from real market data.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from bvmt import __version__
from bvmt.calendar import (
    evaluate_coverage,
    read_exchange_calendar,
    read_instrument_master,
)
from bvmt.data import aware_timestamp, read_bars_csv
from bvmt.features import rank_session_baseline
from bvmt.ledger import (
    OPEN_ORDER_STATUSES,
    PortfolioLedger,
    quantize_tnd,
)
from bvmt.llm import (
    DocumentChunk,
    chunk_financial_document,
    load_document_index,
    load_llm_budget_config,
    load_usage_ledger,
    search_document_index,
)
from bvmt.notifications import NotificationCenter
from bvmt.recommendations import (
    RecommendationReport,
    VerifiedEventSignal,
    generate_recommendations,
)
from bvmt.rules import competition_blockers

DEFAULT_LEDGER_PATH = Path("data/portfolio/ledger.json")
DEFAULT_ALERTS_PATH = Path("artifacts/alerts/state.json")
DEFAULT_BARS_PATH = Path("tests/fixtures/daily_bars.csv")
DEFAULT_CALENDAR_PATH = Path("tests/fixtures/exchange_calendar.csv")
DEFAULT_INSTRUMENTS_PATH = Path("tests/fixtures/instrument_master.csv")
DEFAULT_COMPETITION_CONFIG = Path("configs/competition.json")
DEFAULT_LLM_CONFIG = Path("configs/llm_budget.example.json")
DEFAULT_DOC_INDEX_PATH = Path("data/processed/document_index/document_chunks.json")


def default_demo_events() -> list[VerifiedEventSignal]:
    return [
        VerifiedEventSignal(
            event_id="EVT-DEMO-A-2026Q1",
            instrument_id="DEMO_A",
            published_at="2026-01-08T15:00:00+00:00",
            event_type="dividend_and_pnb_growth",
            polarity="positive",
            summary="Synthetic Q1 disclosure: PNB up +8.4% and proposed dividend of 1.200 TND/share.",
            verbatim_quote="Le Conseil d'Administration propose la distribution d'un dividende de 1,200 TND par action.",
            source_document_id="synthetic_cmf_demo_a_2026q1",
            quote_verified=True,
        ),
        VerifiedEventSignal(
            event_id="EVT-DEMO-B-2026Q1",
            instrument_id="DEMO_B",
            published_at="2026-01-08T15:30:00+00:00",
            event_type="margin_contraction_notice",
            polarity="neutral",
            summary="Synthetic Q1 disclosure: Operating costs rose due to branch modernization.",
            verbatim_quote="Les charges opératoires enregistrent une hausse liée au programme de modernisation.",
            source_document_id="synthetic_cmf_demo_b_2026q1",
            quote_verified=True,
        ),
    ]


def default_demo_chunks() -> list[DocumentChunk]:
    c1 = chunk_financial_document(
        source_document_id="synthetic_cmf_demo_a_2026q1",
        instrument_ids=["DEMO_A"],
        published_at=aware_timestamp("2026-01-08T15:00:00+00:00"),
        ingested_at=aware_timestamp("2026-01-08T15:10:00+00:00"),
        language="fr",
        text=(
            "Communiqué Financier Synthétique (DEMO_A): Le Conseil d'Administration propose "
            "la distribution d'un dividende de 1,200 TND par action au titre de l'exercice.\n\n"
            "Le produit net bancaire (PNB) progresse de 8,4% par rapport à la même période."
        ),
    )
    c2 = chunk_financial_document(
        source_document_id="synthetic_cmf_demo_b_2026q1",
        instrument_ids=["DEMO_B"],
        published_at=aware_timestamp("2026-01-08T15:30:00+00:00"),
        ingested_at=aware_timestamp("2026-01-08T15:40:00+00:00"),
        language="fr",
        text=(
            "Indicateurs d'Activité Synthétiques (DEMO_B): Les charges opératoires enregistrent "
            "une hausse liée au programme de modernisation du réseau."
        ),
    )
    return c1 + c2


@dataclass
class DashboardAppState:
    ledger: PortfolioLedger
    ledger_path: Path
    notifications: NotificationCenter
    alerts_path: Path
    recommendations: RecommendationReport
    data_is_synthetic: bool
    rule_blockers: list[str]
    latest_bar_session_str: str | None
    price_map: dict[str, Decimal]
    coverage_summary: dict[str, object]
    verified_events: list[VerifiedEventSignal]
    document_chunks: list[DocumentChunk]
    llm_status: dict[str, object]


def build_dashboard_state(
    *,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    alerts_path: Path = DEFAULT_ALERTS_PATH,
    bars_path: Path = DEFAULT_BARS_PATH,
    calendar_path: Path = DEFAULT_CALENDAR_PATH,
    instruments_path: Path = DEFAULT_INSTRUMENTS_PATH,
    competition_config_path: Path = DEFAULT_COMPETITION_CONFIG,
    llm_config_path: Path = DEFAULT_LLM_CONFIG,
    doc_index_path: Path = DEFAULT_DOC_INDEX_PATH,
    cutoff_str: str = "2026-01-09T17:00:00+00:00",
    short_lookback: int = 2,
    long_lookback: int = 3,
    min_turnover_tnd: Decimal = Decimal("5000"),
) -> DashboardAppState:
    """Load or initialize persistent ledger, notifications, recommendations, and system health state."""
    cutoff = aware_timestamp(cutoff_str)
    if ledger_path.is_file():
        ledger = PortfolioLedger.load(ledger_path)
    else:
        ledger = PortfolioLedger(
            initial_cash_tnd=Decimal("100000.000"),
            created_at=cutoff,
        )
        ledger.save(ledger_path)

    notifications = NotificationCenter.load(alerts_path)

    comp_doc = json.loads(competition_config_path.read_text(encoding="utf-8"))
    rule_blockers = competition_blockers(comp_doc)

    instruments = read_instrument_master(instruments_path)
    calendar = read_exchange_calendar(calendar_path)
    bars = read_bars_csv(bars_path)

    data_is_synthetic = any("synthetic" in b.source_id.lower() for b in bars)
    sim_profile = "SYNTHETIC_DEMO" if data_is_synthetic else "RESEARCH_CONSERVATIVE"

    cov_report = evaluate_coverage(instruments, calendar, bars)
    baseline = rank_session_baseline(
        instruments,
        calendar,
        bars,
        cutoff,
        short_lookback=short_lookback,
        long_lookback=long_lookback,
        min_trade_frequency=0.60,
        min_median_turnover_tnd=min_turnover_tnd,
    )

    events = default_demo_events() if data_is_synthetic else []
    chunks = (
        load_document_index(doc_index_path)
        if doc_index_path.is_file()
        else (default_demo_chunks() if data_is_synthetic else [])
    )

    price_map: dict[str, Decimal] = {}
    for b in sorted(bars, key=lambda x: x.session_date):
        if b.session_date <= cutoff.date() and b.status == "traded":
            price_map[b.instrument_id] = quantize_tnd(b.close)

    recs = generate_recommendations(
        baseline,
        ledger,
        generated_at=cutoff,
        simulation_profile=sim_profile,
        data_is_synthetic=data_is_synthetic,
        rule_blocker_count=len(rule_blockers),
        verified_events=events,
    )

    latest_bar_date = max(
        (b.session_date for b in bars if b.session_date <= cutoff.date()), default=None
    )
    notifications.evaluate(
        now=cutoff,
        calendar=calendar,
        latest_bar_session=latest_bar_date,
        ledger=ledger,
        recommendations=recs,
        verified_events=events,
        current_prices=price_map,
    )
    notifications.save(alerts_path)

    llm_cfg = load_llm_budget_config(llm_config_path)
    usage_map = load_usage_ledger(Path(llm_cfg.ledger_path))
    enabled_models = [m for m in llm_cfg.models.values() if m.enabled]
    llm_status: dict[str, object] = {
        "api_key_present": bool(os.environ.get(llm_cfg.api_key_env_var, "").strip()),
        "base_url": llm_cfg.base_url,
        "console_free_quota_only_verified": llm_cfg.console_free_quota_only_verified,
        "enabled_models_count": len(enabled_models),
        "live_opt_in_env_set": os.environ.get(llm_cfg.live_opt_in_env_var) == "1",
        "models": [
            {
                "assigned_roles": list(m.assigned_roles),
                "console_label": m.console_label,
                "effective_cutoff_utc": m.effective_cutoff_utc.isoformat(),
                "enabled": m.enabled,
                "expires_at": m.expires_at.isoformat(),
                "hard_limit": m.hard_limit,
                "modality": m.modality,
                "priority_tier": m.priority_tier,
                "remaining_tokens": max(0, m.hard_limit - usage_map.get(m.console_label, 0)),
                "used_tokens": usage_map.get(m.console_label, 0),
            }
            for m in sorted(
                llm_cfg.models.values(), key=lambda x: (x.priority_tier, x.console_label)
            )
        ],
        "network_enabled": llm_cfg.network_enabled,
        "total_models_count": len(llm_cfg.models),
    }

    return DashboardAppState(
        ledger=ledger,
        ledger_path=ledger_path,
        notifications=notifications,
        alerts_path=alerts_path,
        recommendations=recs,
        data_is_synthetic=data_is_synthetic,
        rule_blockers=rule_blockers,
        latest_bar_session_str=latest_bar_date.isoformat() if latest_bar_date else None,
        price_map=price_map,
        # pyrefly: ignore[bad-argument-type]
        coverage_summary=asdict(cov_report),
        verified_events=events,
        document_chunks=chunks,
        llm_status=llm_status,
    )


def _inject_terminal_css(st: Any) -> None:
    st.markdown(
        """
        <style>
        .bvmt-banner-synthetic {
            background-color: #2b1d00;
            border-left: 6px solid #f59e0b;
            color: #fef3c7;
            padding: 12px 16px;
            border-radius: 4px;
            margin-bottom: 12px;
            font-family: monospace;
        }
        .bvmt-banner-rules {
            background-color: #2d0a0a;
            border-left: 6px solid #ef4444;
            color: #fee2e2;
            padding: 10px 16px;
            border-radius: 4px;
            margin-bottom: 16px;
            font-family: monospace;
        }
        .bvmt-card {
            background-color: #111827;
            border: 1px solid #374151;
            color: #f9fafb;
            padding: 14px;
            border-radius: 6px;
            margin-bottom: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_top_banners(st: Any, state: DashboardAppState) -> None:
    if state.data_is_synthetic:
        st.markdown(
            "<div class='bvmt-banner-synthetic'>"
            "<strong>[SYNTHETIC DEMO MODE]</strong> Currently displaying labeled synthetic fixture bars "
            "(<code>tests/fixtures/daily_bars.csv</code>). Do NOT use synthetic scores for real competition trading. "
            "Import official BVMT daily CSVs into <code>data/processed/</code> for real research."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.success(
            f"[VERIFIED LOCAL MARKET DATA] Latest bar session: {state.latest_bar_session_str} | "
            f"Profile: {state.recommendations.simulation_profile}"
        )

    if state.rule_blockers:
        st.markdown(
            f"<div class='bvmt-banner-rules'>"
            f"<strong>[COMPETITION RULES STATUS: BLOCKED ({len(state.rule_blockers)} UNVERIFIED ATTRIBUTES)]</strong> "
            f"Automatic execution is permanently disabled (<code>execution_enabled: false</code>). "
            f"All orders must be placed manually by the human user on <code>tunisbourse-challenge.com</code> (09:00–14:15 Africa/Tunis)."
            f"</div>",
            unsafe_allow_html=True,
        )

    if state.notifications.missed_open_sessions_on_last_startup:
        missed_str = ", ".join(state.notifications.missed_open_sessions_on_last_startup)
        st.warning(
            f"**Power-Off Catch-Up Notice**: Your PC was off during {len(state.notifications.missed_open_sessions_on_last_startup)} "
            f"open exchange session(s) ({missed_str}). Pending order expirations and data freshness have been re-evaluated."
        )


def _render_overview_page(st: Any, state: DashboardAppState) -> None:
    st.subheader("1. Portfolio & Market Overview")
    snap = state.ledger.valuate(state.price_map)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Total Portfolio Equity (TND)",
        f"{snap.total_equity_tnd:,.3f}",
        f"{snap.total_return_pct:+.3f}%",
    )
    c2.metric("Available Cash (TND)", f"{snap.available_cash_tnd:,.3f}")
    c3.metric("Reserved Cash (Pending BUY)", f"{snap.reserved_cash_tnd:,.3f}")
    c4.metric("Holdings Market Value (TND)", f"{snap.holdings_market_value_tnd:,.3f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Settled Cash (TND)", f"{snap.settled_cash_tnd:,.3f}")
    c6.metric("Unrealized P&L (TND)", f"{snap.total_unrealized_pnl_tnd:+,.3f}")
    c7.metric("Realized P&L (TND)", f"{snap.total_realized_pnl_tnd:+,.3f}")
    c8.metric("Total Fees Paid (0.50%)", f"{snap.total_fees_paid_tnd:,.3f}")

    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### Active Holdings Summary")
        if snap.holdings:
            st.dataframe([h.to_dict() for h in snap.holdings], use_container_width=True)
        else:
            st.info("No active share holdings. Portfolio is 100% in cash.")

        st.markdown("#### Open / Pending Orders")
        open_orders = [
            o.to_dict() for o in state.ledger.orders.values() if o.status in OPEN_ORDER_STATUSES
        ]
        if open_orders:
            st.dataframe(open_orders, use_container_width=True)
        else:
            st.info("No open PENDING or PARTIALLY_FILLED orders.")

    with col_right:
        st.markdown("#### Local Alert Center (Active Alerts)")
        active = state.notifications.active_alerts()
        if not active:
            st.success("No unacknowledged alerts.")
        for alert in active:
            with st.expander(
                f"[{alert.severity}] {alert.title} ({alert.session_date})", expanded=True
            ):
                st.write(alert.message)
                st.caption(
                    f"Alert ID: `{alert.alert_id}` | Category: `{alert.category}` | "
                    f"Catch-Up After Power-Off: `{alert.caught_up_after_power_off}`"
                )
                if st.button(f"Acknowledge {alert.alert_id}", key=f"ack_{alert.alert_id}"):
                    state.notifications.acknowledge(
                        alert.alert_id,
                        acknowledged_at=aware_timestamp(state.recommendations.decision_cutoff),
                    )
                    state.notifications.save(state.alerts_path)
                    st.rerun()


def _render_opportunities_page(st: Any, state: DashboardAppState) -> None:
    st.subheader("2. Stock Opportunities & 5-State Recommendations")
    st.caption(
        f"Decision Cutoff: `{state.recommendations.decision_cutoff}` | "
        f"Latest Open Exchange Session: `{state.recommendations.latest_open_session}` | "
        f"Simulation Profile: `{state.recommendations.simulation_profile}`"
    )

    table_rows = [
        {
            "Rec ID": r.recommendation_id,
            "Symbol": r.symbol,
            "Instrument ID": r.instrument_id,
            "Category": r.category,
            "Rank": r.rank if r.rank is not None else "-",
            "Score": f"{r.composite_score:+.4f}" if r.composite_score is not None else "EXCLUDED",
            "Mom (Short)": f"{r.momentum_20s * 100:+.2f}%" if r.momentum_20s is not None else "-",
            "Mom (Long)": f"{r.momentum_60s * 100:+.2f}%" if r.momentum_60s is not None else "-",
            "RS vs Bench": f"{r.relative_strength_20s * 100:+.2f}%"
            if r.relative_strength_20s is not None
            else "-",
            "Ref Price (TND)": r.reference_price_tnd or "-",
            "Suggested Action": (
                f"{r.suggested_side} {r.suggested_shares} @ {r.suggested_limit_price_tnd} TND"
                if r.suggested_side and r.suggested_shares > 0
                else "NONE"
            ),
            "Est. 0.50% Fee (TND)": r.estimated_fee_tnd,
            "Proj. Weight (%)": f"{r.projected_weight_pct}%",
        }
        for r in state.recommendations.recommendations
    ]
    st.dataframe(table_rows, use_container_width=True)

    st.markdown("#### Detailed Recommendation Cards & Evidence Citations")
    for card in state.recommendations.recommendations:
        header = (
            f"[{card.category}] {card.symbol} ({card.instrument_id}) — "
            f"ID: {card.recommendation_id} | Session: {card.latest_market_data_session}"
        )
        with st.expander(header, expanded=(card.category != "NO TRADE")):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Action State", card.category)
            c2.metric(
                "Suggested Order",
                f"{card.suggested_side} {card.suggested_shares}"
                if card.suggested_side
                else "NO ORDER",
            )
            c3.metric("Gross Amount (TND)", f"{card.suggested_gross_amount_tnd} TND")
            c4.metric(
                "Weight Impact",
                f"{card.current_weight_pct}% -> {card.projected_weight_pct}% (Cap: 10.0%)",
            )

            st.markdown("**Supporting Evidence & Citations:**")
            for ev in card.supporting_evidence:
                st.markdown(f"- {ev}")

            if card.blocked_reasons:
                st.error(
                    "**Trading Blocked / Withheld Reasons:**\n"
                    + "\n".join(f"- {b}" for b in card.blocked_reasons)
                )
            if card.pending_order_warnings:
                st.warning(
                    "**Pending Order Conflicts:**\n"
                    + "\n".join(f"- {w}" for w in card.pending_order_warnings)
                )
            if card.liquidity_warnings:
                st.warning(
                    "**Liquidity & Queue Warnings:**\n"
                    + "\n".join(f"- {w}" for w in card.liquidity_warnings)
                )

            st.markdown("**Main Risks & Competition Disclosures:**")
            for rk in card.main_risks:
                st.markdown(f"- {rk}")


def _render_portfolio_page(st: Any, state: DashboardAppState) -> None:
    st.subheader("3. Portfolio Holdings, Weights, P&L & Concentration Compliance")
    snap = state.ledger.valuate(state.price_map)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Initial Cash (TND)", f"{snap.initial_cash_tnd:,.3f}")
    c2.metric(
        "Total Equity (TND)", f"{snap.total_equity_tnd:,.3f}", f"{snap.total_return_pct:+.3f}%"
    )
    c3.metric("Total Unrealized P&L (TND)", f"{snap.total_unrealized_pnl_tnd:+,.3f}")
    c4.metric("Total Realized P&L (TND)", f"{snap.total_realized_pnl_tnd:+,.3f}")

    if not snap.holdings:
        st.info("No shares currently held in the portfolio.")
    else:
        for h in snap.holdings:
            if h.concentration_warning:
                st.warning(f"**{h.symbol}**: {h.concentration_warning}")
        st.dataframe([h.to_dict() for h in snap.holdings], use_container_width=True)

    st.markdown("#### Historical Realized P&L & Fee Summary by Instrument")
    all_positions = [pos.to_dict() for pos in state.ledger.holdings.values()]
    if all_positions:
        st.dataframe(all_positions, use_container_width=True)
    else:
        st.caption("No historical positions recorded yet.")


def _render_order_journal_page(st: Any, state: DashboardAppState) -> None:
    st.subheader("4. Manual Order Journal & Execution Reconciliation")
    st.info(
        "**Manual Execution Rule**: This system never submits orders to `tunisbourse-challenge.com`. "
        "Place your order manually on the competition website first, then record it here as `PENDING` "
        "and update fills, partial executions, cancellations, or 1-week expirations."
    )

    tab_new, tab_fill, tab_close, tab_history = st.tabs(
        [
            "1. Record New Pending Order",
            "2. Record Execution / Partial Fill",
            "3. Cancel / Reject / Expire Order",
            "4. Full Order & Audit History",
        ]
    )

    now_dt = aware_timestamp(state.recommendations.decision_cutoff)

    with tab_new:
        with st.form("form_record_pending_order"):
            st.markdown("##### Record Manually Submitted Order (`PENDING`)")
            col1, col2, col3 = st.columns(3)
            next_num = len(state.ledger.orders) + 1
            order_id = col1.text_input("Order ID", value=f"ORD-20260109-{next_num:03d}")
            inst_id = col2.text_input("Instrument ID", value="DEMO_A")
            symbol = col3.text_input("Ticker Symbol", value="DEMO_A")

            col4, col5, col6 = st.columns(3)
            side = col4.selectbox("Side", ["BUY", "SELL"])
            qty = int(col5.number_input("Quantity (Shares)", min_value=1, value=100, step=1))
            limit_px = col6.text_input("Limit Price (TND)", value="10.800")

            rec_id = st.text_input("Linked Recommendation ID (optional)", value="")
            notes = st.text_input(
                "Operator Notes", value="Placed manually on tunisbourse-challenge.com"
            )
            submitted = st.form_submit_button("Record Pending Order in Local Ledger")

            if submitted:
                try:
                    state.ledger.record_pending_order(
                        order_id=order_id.strip(),
                        instrument_id=inst_id.strip(),
                        symbol=symbol.strip(),
                        side=side,
                        quantity=qty,
                        limit_price_tnd=limit_px.strip(),
                        submitted_at=now_dt,
                        recommendation_id=rec_id.strip() or None,
                        notes=notes,
                        current_prices=state.price_map,
                    )
                    state.ledger.save(state.ledger_path)
                    st.success(
                        f"Recorded PENDING order `{order_id}` and updated cash/share reservations."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(f"Order rejected by local ledger guard: {exc}")

    with tab_fill:
        open_ids = [
            o.order_id for o in state.ledger.orders.values() if o.status in OPEN_ORDER_STATUSES
        ]
        if not open_ids:
            st.info("No open orders (`PENDING` or `PARTIALLY_FILLED`) available to fill.")
        else:
            with st.form("form_record_fill"):
                st.markdown("##### Record Full or Partial Fill (0.50% Fee Automatically Applied)")
                sel_order_id = st.selectbox("Select Open Order", open_ids)
                sel_order = state.ledger.orders[sel_order_id]
                st.caption(
                    f"Selected: `{sel_order.side}` {sel_order.symbol} | "
                    f"Remaining: `{sel_order.remaining_shares}` of `{sel_order.requested_shares}` shares | "
                    f"Limit Price: `{sel_order.limit_price_tnd} TND`"
                )
                c1, c2 = st.columns(2)
                fill_qty = int(
                    c1.number_input(
                        "Executed Shares in This Fill",
                        min_value=1,
                        max_value=max(1, sel_order.remaining_shares),
                        value=sel_order.remaining_shares,
                        step=1,
                    )
                )
                exec_px = c2.text_input(
                    "Actual Execution Price (TND)", value=str(sel_order.limit_price_tnd)
                )
                fill_notes = st.text_input(
                    "Fill Notes", value="Filled during 09:00-14:15 BVMT session"
                )
                fill_sub = st.form_submit_button("Record Execution Fill")
                if fill_sub:
                    try:
                        state.ledger.record_execution_fill(
                            order_id=sel_order_id,
                            filled_shares=fill_qty,
                            execution_price_tnd=exec_px.strip(),
                            executed_at=now_dt,
                            notes=fill_notes,
                        )
                        state.ledger.save(state.ledger_path)
                        st.success(f"Recorded fill of {fill_qty} shares on `{sel_order_id}`.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(f"Fill rejected: {exc}")

    with tab_close:
        open_ids_close = [
            o.order_id for o in state.ledger.orders.values() if o.status in OPEN_ORDER_STATUSES
        ]
        if not open_ids_close:
            st.info("No open orders available to cancel, reject, or expire.")
        else:
            with st.form("form_close_order"):
                st.markdown("##### Close Open Order (`CANCELLED`, `REJECTED`, or `EXPIRED`)")
                close_oid = st.selectbox("Select Open Order to Close", open_ids_close)
                term_status = st.selectbox("Terminal Status", ["CANCELLED", "EXPIRED", "REJECTED"])
                reason = st.text_input(
                    "Reason", value="Cancelled remaining shares / 1-week simulator expiry"
                )
                close_sub = st.form_submit_button("Close Order & Release Reserved Cash/Shares")
                if close_sub:
                    try:
                        state.ledger.close_open_order(
                            order_id=close_oid,
                            terminal_status=term_status,
                            closed_at=now_dt,
                            reason=reason,
                        )
                        state.ledger.save(state.ledger_path)
                        st.success(
                            f"Order `{close_oid}` marked `{term_status}` and reservations released."
                        )
                        st.rerun()
                    except ValueError as exc:
                        st.error(f"Could not close order: {exc}")

    with tab_history:
        st.markdown("##### All Recorded Manual Orders")
        if state.ledger.orders:
            st.dataframe(
                [o.to_dict() for o in state.ledger.orders.values()],
                use_container_width=True,
            )
        else:
            st.info("No orders recorded yet.")

        st.markdown("##### Immutable Append-Only Audit Log")
        st.dataframe(
            [asdict(e) for e in reversed(state.ledger.audit_log)],
            use_container_width=True,
        )


def _render_research_page(st: Any, state: DashboardAppState) -> None:
    st.subheader("5. Research, Corporate Events & Local Document Search")

    st.markdown("#### Extracted & Quote-Verified Corporate Events")
    if state.verified_events:
        st.dataframe([asdict(e) for e in state.verified_events], use_container_width=True)
    else:
        st.info("No verified corporate events loaded for current dataset.")

    st.markdown("#### Point-in-Time Local Document Index Search (BM25 + Embedding Sidecar)")
    query = st.text_input(
        "Search French/Arabic Financial Disclosures (Point-in-Time Filtered)",
        value="dividende PNB hausse",
    )
    if query.strip() and state.document_chunks:
        hits = search_document_index(
            state.document_chunks,
            cutoff=aware_timestamp(state.recommendations.decision_cutoff),
            query_text=query.strip(),
            top_k=5,
        )
        st.caption(
            f"Found {len(hits)} point-in-time chunk hit(s) on or before `{state.recommendations.decision_cutoff}`:"
        )
        for hit in hits:
            with st.expander(
                f"[{hit.method}] Doc: {hit.source_document_id} ({hit.section_locator}) — Score: {hit.score:.4f}",
                expanded=True,
            ):
                st.write(hit.chunk_text)
                st.caption(
                    f"Chunk ID: `{hit.chunk_id}` | Instruments: `{', '.join(hit.instrument_ids)}` | "
                    f"Published At: `{hit.published_at}`"
                )

    st.markdown("#### Indexed Document Chunks")
    st.dataframe([asdict(c) for c in state.document_chunks], use_container_width=True)


def _render_system_health_page(st: Any, state: DashboardAppState) -> None:
    st.subheader("6. System Health, Competition Rules & Alibaba Allowance Status")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Application Version", __version__)
    c2.metric("Data Mode", "SYNTHETIC_DEMO" if state.data_is_synthetic else "VERIFIED_LOCAL")
    c3.metric("Rule Blockers", str(len(state.rule_blockers)))
    c4.metric(
        "Alibaba Network Mode",
        "LIVE ENABLED" if state.llm_status["network_enabled"] else "OFFLINE (DEFAULT)",
    )

    st.markdown("#### Exchange Calendar & Observation Coverage Summary (`T03`)")
    st.json(state.coverage_summary)

    st.markdown("#### Alibaba Cloud Model Studio 25-Model Allowance & Expiration Status")
    st.caption(
        f"Console Stop-on-Exhaustion / Free Quota Only Verified: `{state.llm_status['console_free_quota_only_verified']}` | "
        f"API Key Env Present: `{state.llm_status['api_key_present']}` | "
        f"Live Opt-In Env (`BVMT_ALLOW_LIVE_LLM=1`): `{state.llm_status['live_opt_in_env_set']}`"
    )
    models_list = state.llm_status.get("models", [])
    if isinstance(models_list, list):
        st.dataframe(models_list, use_container_width=True)

    st.markdown("#### Competition Rule Blockers (`configs/competition.json`)")
    with st.expander(f"View {len(state.rule_blockers)} Unverified Rule Attributes"):
        for b in state.rule_blockers:
            st.markdown(f"- `{b}`")


def render_streamlit_app(state: DashboardAppState | None = None) -> DashboardAppState:
    """Entrypoint called by `streamlit run src/bvmt/dashboard.py` or headless UI tests."""
    import importlib

    st: Any = importlib.import_module("streamlit")

    st.set_page_config(
        page_title="BVMT Trading Intelligence — Local Decision Support",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_terminal_css(st)

    app_state = state or build_dashboard_state()

    st.sidebar.title("BVMT Trading Terminal")
    st.sidebar.caption(f"v{__version__} | Local Decision-Support Only")
    st.sidebar.markdown(
        f"**Mode:** `{'SYNTHETIC DEMO' if app_state.data_is_synthetic else 'VERIFIED LOCAL'}`\n\n"
        f"**Latest Session:** `{app_state.latest_bar_session_str}`\n\n"
        f"**Active Alerts:** `{len(app_state.notifications.active_alerts())}`"
    )

    page = st.sidebar.radio(
        "Navigation",
        [
            "Overview",
            "Stock Opportunities",
            "Portfolio",
            "Manual Order Journal",
            "Research and Documents",
            "System Health",
        ],
    )

    _render_top_banners(st, app_state)

    if page == "Overview":
        _render_overview_page(st, app_state)
    elif page == "Stock Opportunities":
        _render_opportunities_page(st, app_state)
    elif page == "Portfolio":
        _render_portfolio_page(st, app_state)
    elif page == "Manual Order Journal":
        _render_order_journal_page(st, app_state)
    elif page == "Research and Documents":
        _render_research_page(st, app_state)
    elif page == "System Health":
        _render_system_health_page(st, app_state)

    return app_state


if __name__ == "__main__":
    render_streamlit_app()
