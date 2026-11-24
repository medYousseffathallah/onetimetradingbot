"""Read-only account reconstruction, position review and manual scenario arithmetic."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median, pstdev
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from .contracts import (
    Holding,
    Horizon,
    InvestmentThesis,
    ManualTradeScenario,
    PerformanceAttribution,
    PortfolioSnapshot,
    PositionDecision,
    ProvenanceValue,
    RiskAssessment,
    SignalJournal,
    ValueStatus,
    money,
    pv,
)
from .market_data import MarketData

ROOT = Path(__file__).resolve().parents[2]
Mode = Literal["REAL_COMPETITION", "SYNTHETIC_DEMO"]
Side = Literal["BUY", "SELL", "PROTECTION"]
Monitoring = Literal["HOLD", "REVIEW", "CONSIDER_TRIM", "CONSIDER_EXIT", "INSUFFICIENT_DATA"]
CAP = Decimal("0.10")
FEE = Decimal("0.005")
ZERO = Decimal(0)


def _read(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        raw = json.load(f, parse_float=Decimal)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object in {path.name}")
    return raw


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Account timestamp requires an offset")
    return result.astimezone(UTC)


def _value(
    value: Decimal | int | str | None,
    unit: str,
    status: ValueStatus,
    source: str,
    at: datetime,
    observed: datetime | None = None,
    reason: str = "Absent from source",
) -> ProvenanceValue:
    return pv(
        value,
        unit,
        "UNAVAILABLE" if value is None else status,
        source,
        at,
        reason if value is None else None,
        observed,
    )


def _holding(
    row: Mapping[str, Any],
    market: MarketData,
    source: str,
    at: datetime,
    observed: datetime | None,
    status: ValueStatus,
) -> Holding:
    iid = str(row.get("instrument_id") or row.get("symbol") or row["displayed_identifier"]).replace(
        " ", "_"
    )
    inst = market.instruments.get(iid)

    def amount(key: str, alt: str = "") -> ProvenanceValue:
        return _value(row.get(key, row.get(alt)), "TND", status, source, at, observed)

    return Holding(
        instrument_id=iid,
        isin=inst.isin if inst else row.get("isin"),
        symbol=str(row.get("symbol", iid)),
        quantity=row["quantity"],
        displayed_avg_cost_tnd=amount("acquisition_price_tnd", "displayed_acquisition_price_tnd"),
        displayed_acquisition_amount_tnd=amount(
            "acquisition_amount_tnd", "displayed_acquisition_amount_tnd"
        ),
        displayed_price_tnd=amount("latest_price_tnd", "displayed_last_price_tnd"),
        displayed_value_tnd=amount("market_value_tnd", "current_market_value_tnd"),
        displayed_unrealized_pnl_tnd=amount("gain_tnd", "displayed_unrealized_pnl_tnd"),
        verified_cost_basis_tnd=amount("verified_cost_basis_tnd")
        if status == "SIMULATED"
        else _value(
            None,
            "TND",
            status,
            source,
            at,
            reason="Verified transaction history and fee inclusion missing",
        ),
        eod_reference_close_tnd=_value(
            None, "TND", status, source, at, reason="Account observation, not an EOD mark"
        ),
    )


def _snapshot(
    raw: Mapping[str, Any], source: str, market: MarketData, at: datetime, status: ValueStatus
) -> PortfolioSnapshot:
    capture = raw.get("retrieved_at") or raw.get("capture_timestamp")
    observed = _time(capture) if capture else None

    def field(key: str, unit: str = "TND") -> ProvenanceValue:
        return _value(raw.get(key), unit, status, source, at, observed)

    holdings = tuple(_holding(h, market, source, at, observed, status) for h in raw["holdings"])
    mv = field("holdings_market_value_tnd")
    if (
        mv.value is None
        and raw.get("portfolio_total_tnd") is not None
        and raw.get("available_cash_tnd") is not None
    ):
        mv = _value(
            Decimal(raw["portfolio_total_tnd"]) - Decimal(raw["available_cash_tnd"]),
            "TND",
            "SIMULATED" if status == "SIMULATED" else "CALCULATED",
            source,
            at,
            observed,
        )
    return PortfolioSnapshot(
        snapshot_id=source,
        captured_at=observed,
        source_id=source,
        equity_tnd=field("portfolio_total_tnd"),
        cash_tnd=field("available_cash_tnd"),
        holdings_value_tnd=mv,
        rank=raw.get("competition_rank"),
        total_participants=raw.get("total_participants", raw.get("competition_participants")),
        reported_holdings_count=raw.get("reported_holdings_count", len(holdings)),
        return_pct=field("displayed_overall_performance_pct", "PCT"),
        verification_status=status,
        holdings=holdings,
    )


def _mark_portfolio(
    current: PortfolioSnapshot, market: MarketData, at: datetime, demo: bool
) -> PortfolioSnapshot:
    session = max((s for s in market.sessions if s <= at.date()), default=None)
    source = f"{current.source_id}+eod_{session}"
    status: ValueStatus = "SIMULATED" if demo else "CALCULATED"
    marked: list[Holding] = []
    values: list[Decimal] = []
    for h in current.holdings:
        bar = next(
            (
                b
                for b in reversed(market.bars.get(h.instrument_id, ()))
                if b.session_date == session and b.provenance.available_at <= at
            ),
            None,
        )
        close = (
            bar.close_tnd
            if bar
            else _value(
                None, "TND", status, source, at, reason="No available mark for this session"
            )
        )
        if close.value is not None:
            values.append(close.value * h.quantity)
        marked.append(h.model_copy(update={"eod_reference_close_tnd": close}))
    complete = len(values) == len(marked)
    mv = sum(values, ZERO) if complete else None
    cash = current.cash_tnd.value
    equity = cash + mv if cash is not None and mv is not None else None
    return PortfolioSnapshot(
        snapshot_id=source,
        captured_at=None,
        source_id=source,
        equity_tnd=_value(equity, "TND", status, source, at),
        cash_tnd=current.cash_tnd,
        holdings_value_tnd=_value(mv, "TND", status, source, at),
        rank=None,
        total_participants=None,
        reported_holdings_count=len(marked),
        verification_status=status,
        holdings=tuple(marked),
    )


def monitoring_state(
    weight: Decimal | None, price: Decimal | None, trend: Decimal | None, trailing_breach: bool
) -> tuple[Monitoring, str]:
    if weight is None or price is None or trend is None:
        return (
            "INSUFFICIENT_DATA",
            "A current position mark, equity or 20-session trend is missing.",
        )
    if trailing_breach:
        return (
            "CONSIDER_EXIT",
            "Closing price crossed the 8% research trailing threshold after a verified entry.",
        )
    if weight > CAP:
        return "CONSIDER_TRIM", "Marked position exceeds the 10% research concentration limit."
    if trend < 0:
        return "REVIEW", "The 20-session price trend is negative."
    return "HOLD", "The marked weight and 20-session trend meet the monitoring assumptions."


@dataclass(frozen=True)
class PortfolioBook:
    market: MarketData
    mode: Mode
    current: PortfolioSnapshot
    eod_mark_portfolio: PortfolioSnapshot
    confirmed_ledger: PortfolioSnapshot | None
    latest_dom_capture: PortfolioSnapshot | None
    unverified_screenshot: PortfolioSnapshot | None
    account_state_conflict: bool
    attribution: PerformanceAttribution
    at: datetime
    verified_entries: Mapping[str, datetime]
    rejected_captures: tuple[str, ...] = ()

    def snapshots(self) -> dict[str, PortfolioSnapshot]:
        if self.mode == "SYNTHETIC_DEMO":
            return {"synthetic_demo": self.current, "eod_mark_portfolio": self.eod_mark_portfolio}
        snapshots = {
            "confirmed_ledger": self.confirmed_ledger,
            "latest_dom_capture": self.latest_dom_capture,
            "unverified_screenshot": self.unverified_screenshot,
            "eod_mark_portfolio": self.eod_mark_portfolio,
        }
        return {key: value for key, value in snapshots.items() if value is not None}

    def _blockers(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.account_state_conflict:
            reasons.append("ACCOUNT_STATE_CONFLICT")
        if self.mode == "REAL_COMPETITION":
            reasons.extend(
                (
                    "UNVERIFIED_COMPETITION_RULES",
                    "CURRENT_EXECUTABLE_QUOTE_UNAVAILABLE",
                    "UNVERIFIED_PENDING_ORDERS",
                )
            )
        return tuple(reasons)

    def position(self, instrument_id: str) -> PositionDecision:
        item = next(
            (h for h in self.eod_mark_portfolio.holdings if h.instrument_id == instrument_id), None
        )
        if item is None:
            raise KeyError(instrument_id)
        source = self.eod_mark_portfolio.source_id
        status: ValueStatus = "SIMULATED" if self.mode == "SYNTHETIC_DEMO" else "CALCULATED"

        def metric(
            n: Decimal | int | None, unit: str, reason: str = "Insufficient marked history"
        ) -> ProvenanceValue:
            return _value(n, unit, status, source, self.at, reason=reason)

        equity = self.eod_mark_portfolio.equity_tnd.value
        price = item.eod_reference_close_tnd.value
        weight = (
            price * item.quantity / equity if price is not None and equity and equity > 0 else None
        )
        known = {
            b.session_date: b
            for b in self.market.bars.get(instrument_id, ())
            if b.session_date <= self.at.date() and b.provenance.available_at <= self.at
        }
        sessions = [d for d in self.market.sessions if d <= self.at.date()][-21:]
        closes = [known[d].close_tnd.value for d in sessions if d in known]
        vols = [Decimal(known[d].volume_shares) for d in sessions[-20:] if d in known]
        capacity = median(vols) * CAP if len(vols) == 20 else None
        days = Decimal(item.quantity) / capacity if capacity and capacity > 0 else None
        prices = [p for p in closes if p is not None and p > 0]
        trend = prices[-1] / prices[0] - 1 if len(prices) == 21 else None
        vol = (
            pstdev([b / a - 1 for a, b in zip(prices, prices[1:], strict=False)])
            if len(prices) == 21
            else None
        )
        entry = self.verified_entries.get(instrument_id)
        highs = [
            b.close_tnd.value
            for d, b in known.items()
            if entry and entry.date() < d and b.close_tnd.value is not None
        ]
        basis = item.verified_cost_basis_tnd.value
        peak = max(highs, default=ZERO)
        breach = bool(
            price is not None
            and basis is not None
            and peak * item.quantity > basis
            and price <= peak * Decimal("0.92")
        )
        state, explanation = monitoring_state(weight, price, trend, breach)
        blockers = self._blockers()
        if not capacity or capacity < 1:
            blockers += ("INSUFFICIENT_EXIT_LIQUIDITY",)
        concentration = weight > CAP if weight is not None else None
        risk = RiskAssessment(
            position_weight=metric(weight, "RATIO"),
            max_single_stock_weight=metric(CAP, "RATIO"),
            concentration_breach=concentration,
            liquidity_days_to_exit=metric(days, "SESSIONS"),
            volatility_20s=metric(vol, "RATIO"),
            downside_stress_tnd=_value(
                price * item.quantity * Decimal("0.05") if price else None,
                "TND",
                "SIMULATED",
                "illustrative_5pct_price_decline",
                self.at,
            ),
            risk_budget_breached=concentration,
        )
        return PositionDecision(
            instrument_id=instrument_id,
            monitoring_state=state,
            execution_state="EXECUTION_BLOCKED" if blockers else "ELIGIBLE_MANUAL_ONLY",
            blockers=blockers,
            explanation=explanation,
            next_review_trigger="Next session close or reconciled holdings and pending orders.",
            exit_scenarios=(
                "partial sale",
                "5% downside stress",
                "8% trailing close after verified entry"
                if entry
                else "Trailing protection unavailable without verified entry timestamp",
            ),
            risk=risk,
            thesis=InvestmentThesis(
                instrument_id=instrument_id,
                thesis="No human thesis recorded",
                horizon_sessions=None,
                invalidation_conditions=(),
                recorded_at=None,
                origin="UNVERIFIED_NONE",
            ),
            realized_pnl_tnd=self.attribution.realized_pnl_tnd
            if self.mode == "SYNTHETIC_DEMO"
            else metric(None, "TND", "Complete verified trade history missing"),
            unrealized_pnl_tnd=self.attribution.position_attributions.get(instrument_id, {}).get(
                "unrealized_pnl_tnd"
            ),
        )

    def scenario(
        self, side: Side, instrument_id: str, quantity: int, limit_price_tnd: Decimal
    ) -> ManualTradeScenario:
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Scenario quantity must be a positive integer")
        if (
            not isinstance(limit_price_tnd, Decimal)
            or not limit_price_tnd.is_finite()
            or money(limit_price_tnd) <= 0
        ):
            raise ValueError("Scenario requires a positive Decimal price in TND")
        price = money(limit_price_tnd)
        if side not in ("BUY", "SELL", "PROTECTION"):
            raise ValueError("Unknown scenario side")
        blockers = list(self._blockers())
        instrument = self.market.instruments.get(instrument_id)
        if side == "BUY" and (
            not instrument
            or not instrument.challenge_member
            or instrument.order_entry_eligibility != "CONFIRMED"
        ):
            blockers.append("RESTRICTED_CHALLENGE")
        item = next(
            (h for h in self.eod_mark_portfolio.holdings if h.instrument_id == instrument_id), None
        )
        held = item.quantity if item else 0
        if side != "BUY" and quantity > held:
            blockers.append("INSUFFICIENT_UNRESERVED_SHARES")
        gross = money(price * quantity)
        fee = money(gross * FEE)
        net = gross - fee
        cash = self.current.cash_tnd.value
        post_cash = (
            (cash - gross - fee if side == "BUY" else cash + net) if cash is not None else None
        )
        if post_cash is None or post_cash < 0:
            blockers.append("INSUFFICIENT_CASH")
        equity = self.eod_mark_portfolio.equity_tnd.value
        mark = item.eod_reference_close_tnd.value if item else price
        # Revalue this issuer at the scenario price before applying the cash/share transfer.
        post_equity = (
            equity + held * (price - mark) - fee
            if equity is not None and mark is not None
            else None
        )
        post_shares = held + quantity if side == "BUY" else held - quantity
        weight = (
            post_shares * price / post_equity
            if post_equity and post_equity > 0 and post_shares >= 0
            else None
        )
        if side == "BUY" and (weight is None or weight > CAP):
            blockers.append("SINGLE_STOCK_CAP")
        bars = self.market.bars.get(instrument_id, ())
        sessions = tuple(s for s in self.market.sessions if s <= self.at.date())[-20:]
        volumes = [
            Decimal(b.volume_shares)
            for b in bars
            if b.session_date in sessions and b.provenance.available_at <= self.at
        ]
        if len(volumes) != 20 or int(median(volumes) * CAP) < quantity:
            blockers.append("ONE_SESSION_LIQUIDITY_CAP")

        def sim(value: Decimal | None, unit: str = "TND") -> ProvenanceValue:
            return _value(value, unit, "SIMULATED", "manual_price_scenario", self.at)

        return ManualTradeScenario(
            side=side,
            instrument_id=instrument_id,
            quantity=quantity,
            limit_price_tnd=sim(price),
            gross_tnd=sim(gross),
            estimated_fee_tnd=sim(fee),
            stress_proceeds_tnd=sim(net if side != "BUY" else None),
            downside_loss_tnd=sim(max(ZERO, quantity * mark - net))
            if side == "PROTECTION" and mark is not None and item is not None
            else None,
            post_trade_weight=sim(weight, "RATIO"),
            post_trade_cash_tnd=sim(post_cash),
            is_valid=not blockers,
            rejection_reasons=tuple(blockers),
            is_executed=False,
        )


def _attribution(
    first: PortfolioSnapshot,
    marked: PortfolioSnapshot,
    end: date,
    at: datetime,
    report: Mapping[str, Any],
    demo: bool,
) -> PerformanceAttribution:
    status: ValueStatus = "SIMULATED" if demo else "CALCULATED"
    source = marked.source_id

    def val(
        n: Decimal | None,
        unit: str = "TND",
        reason: str = "Incomplete verified movement and fee history",
    ) -> ProvenanceValue:
        return _value(n, unit, status, source, at, reason=reason)

    positions: dict[str, dict[str, ProvenanceValue]] = {}
    pnl_values: list[Decimal] = []
    for h in marked.holdings:
        displayed = h.displayed_value_tnd.value
        gain = h.displayed_unrealized_pnl_tnd.value
        close = h.eod_reference_close_tnd.value
        basis = (
            h.displayed_acquisition_amount_tnd.value if h.displayed_acquisition_amount_tnd else None
        )
        if basis is None and gain is not None and displayed is not None:
            basis = displayed - gain
        pnl = close * h.quantity - basis if close is not None and basis is not None else None
        positions[h.instrument_id] = {
            "unrealized_pnl_tnd": val(
                pnl, reason="Missing displayed acquisition basis or EOD mark"
            ),
            "eod_reference_close_tnd": h.eod_reference_close_tnd,
        }
        if pnl is not None:
            pnl_values.append(pnl)
    unrealized = sum(pnl_values, ZERO) if len(pnl_values) == len(marked.holdings) else None
    ending = marked.equity_tnd.value
    starting = first.equity_tnd.value
    change = ending - starting if ending is not None and starting is not None else None
    first_pnls = [h.displayed_unrealized_pnl_tnd.value for h in first.holdings]
    opening_pnl = (
        sum((p for p in first_pnls if p is not None), ZERO) if None not in first_pnls else None
    )
    residual = (
        change - unrealized + opening_pnl
        if change is not None and unrealized is not None and opening_pnl is not None
        else None
    )
    cash = marked.cash_tnd.value
    benchmarks = {
        "TUNINDEX": val(None, "PCT", "No PIT TUNINDEX series in local archive"),
        "BL-CASH": _value(0, "PCT", "SIMULATED", "cash_baseline", at),
    }
    # R1 benchmark entry conventions are encoded in their source labels and dates.
    if (
        first.captured_at
        and first.captured_at.date() == date(2026, 11, 7)
        and end == date(2026, 11, 18)
    ):
        for label, result in (
            report.get("benchmark_comparisons", {}).get("Nov7_to_Nov18", {}).items()
        ):
            if isinstance(result, dict) and label.startswith(
                ("ew_", "buy_and_hold_", "simple_mom20_")
            ):
                fraction = result.get(
                    "return_pct", result.get("return_vs_50k_pct", result.get("return_mtm_pct"))
                )
                benchmarks[label] = _value(
                    fraction, "PCT", "SIMULATED", "r1_autopsy_results/Nov7_to_Nov18", at
                )
    return PerformanceAttribution(
        period_start=first.captured_at.date() if first.captured_at else end,
        period_end=end,
        starting_equity_tnd=first.equity_tnd,
        ending_equity_tnd=marked.equity_tnd,
        total_return_pct=val(
            change / starting * 100 if change is not None and starting else None, "PCT"
        ),
        realized_pnl_tnd=val(ZERO if demo else None),
        unrealized_pnl_tnd=val(unrealized),
        unexplained_residual_tnd=val(residual),
        estimated_fees_tnd=val(ZERO if demo else None),
        cash_drag_pct=val(cash / ending * 100 if cash is not None and ending else None, "PCT"),
        position_attributions=positions,
        benchmarks=benchmarks,
        failure_tags=()
        if demo
        else (
            "UNVERIFIED_COST_BASIS",
            "INCOMPLETE_TRANSACTION_HISTORY",
            "STATIC_HOLDINGS_SINCE_DOM_CAPTURE",
            "EOD_PRICES_ONLY",
        ),
    )


def _conflicts(a: PortfolioSnapshot, b: PortfolioSnapshot) -> bool:
    def quantities(snapshot: PortfolioSnapshot) -> dict[str, int]:
        return {h.instrument_id: h.quantity for h in snapshot.holdings}

    return (
        a.captured_at != b.captured_at
        or a.cash_tnd.value != b.cash_tnd.value
        or a.equity_tnd.value != b.equity_tnd.value
        or quantities(a) != quantities(b)
    )


def load_portfolio(
    market: MarketData,
    mode: Mode = "REAL_COMPETITION",
    portfolio_dir: Path | None = None,
    autopsy_path: Path | None = None,
) -> PortfolioBook:
    at = datetime.now(UTC)
    synthetic_bars = (
        b.provenance.data_quality_status == "SYNTHETIC_FIXTURE"
        for series in market.bars.values()
        for b in series
    )
    if mode == "SYNTHETIC_DEMO":
        iid = "EURO-CYCLES"
        # Ring-fenced simulated ledger. The synthetic account has cash and a single verified lot.
        bars = market.bars.get(iid, ())
        if not bars or not all(synthetic_bars):
            raise ValueError("Synthetic portfolio requires synthetic market observations")
        entry = bars[0]
        cost = entry.close_tnd.value
        if cost is None:
            raise ValueError("Missing synthetic opening basis")
        raw: dict[str, Any] = {
            "retrieved_at": entry.close_tnd.calculation_time.isoformat(),
            "portfolio_total_tnd": "50000",
            "available_cash_tnd": 50000 - 100 * cost,
            "holdings": [
                {
                    "instrument_id": iid,
                    "symbol": iid,
                    "quantity": 100,
                    "acquisition_price_tnd": cost,
                    "acquisition_amount_tnd": 100 * cost,
                    "latest_price_tnd": cost,
                    "market_value_tnd": 100 * cost,
                    "verified_cost_basis_tnd": 100 * cost,
                    "gain_tnd": "0",
                }
            ],
        }
        initial = _snapshot(raw, "synthetic_demo_opening", market, at, "SIMULATED")
        marked = _mark_portfolio(initial, market, at, True)
        attribution = _attribution(initial, marked, market.sessions[-1], at, {}, True)
        return PortfolioBook(
            market,
            mode,
            initial,
            marked,
            None,
            None,
            None,
            False,
            attribution,
            at,
            {iid: entry.close_tnd.calculation_time},
        )
    if mode != "REAL_COMPETITION":
        raise ValueError("Unknown account mode")
    if any(synthetic_bars):
        raise ValueError("Synthetic prices cannot mark a real competition account")
    account_dir = portfolio_dir or ROOT.parent / "bvmt-starter-kit" / "data" / "portfolio"
    ledger = _read(account_dir / "real_competition_ledger.json")
    active = ledger["snapshot_history"][-1]
    confirmed = _snapshot(active, active["snapshot_id"], market, at, "OBSERVED")
    ledger_positions = {key: row["total_shares"] for key, row in ledger["holdings"].items()}
    active_disagrees = (
        ledger_positions != {h.instrument_id: h.quantity for h in confirmed.holdings}
        or Decimal(ledger["available_cash_tnd"]) != confirmed.cash_tnd.value
    )
    captures: list[PortfolioSnapshot] = []
    rejected: list[str] = []
    for path in sorted((account_dir / "snapshots").glob("*.json")):
        raw = _read(path)
        if raw.get("is_reconciled") is not True or any(
            h.get("symbol") == "VENDRE" for h in raw.get("holdings", ())
        ):
            rejected.append(path.name)
            continue
        captures.append(_snapshot(raw, raw.get("snapshot_id") or path.stem, market, at, "OBSERVED"))
    if not captures:
        raise ValueError("No reconciled DOM capture in local archive")
    captures.sort(key=lambda s: s.captured_at or datetime.min.replace(tzinfo=UTC))
    current = captures[-1]
    marked = _mark_portfolio(current, market, at, False)
    report = _read(autopsy_path or ROOT / "research" / "experiments-v2" / "r1_autopsy_results.json")
    screenshot = report["eod_trajectories"]["unverified_user_screenshot"]
    rank, participants = [
        int(v.strip().replace(",", "")) for v in screenshot["reported_rank"].split("/")
    ]
    symbol, quantity, _unit = screenshot["reported_new_holding"].split()
    screenshot_raw = {
        "portfolio_total_tnd": screenshot["reported_equity_tnd"],
        "competition_rank": rank,
        "total_participants": participants,
        "reported_holdings_count": screenshot["reported_holdings_count"],
        "displayed_overall_performance_pct": screenshot["reported_return_pct"].rstrip("%"),
        "holdings": [{"symbol": symbol, "quantity": int(quantity)}],
    }
    unverified = _snapshot(
        screenshot_raw, "unverified_user_screenshot_2026_11", market, at, "UNVERIFIED"
    )
    attribution = _attribution(captures[0], marked, market.sessions[-1], at, report, False)
    return PortfolioBook(
        market,
        mode,
        current,
        marked,
        confirmed,
        current,
        unverified,
        active_disagrees or _conflicts(confirmed, current),
        attribution,
        at,
        {},
        tuple(rejected),
    )


def _journal_path() -> Path:
    research = ROOT / "research"
    path = research / "v2_signal_journal.json"
    if path.resolve() != path or research.resolve() != research:
        raise ValueError("Journal must be a local V2 research file")
    return path


def _digest(record: SignalJournal) -> str:
    payload = record.model_dump(mode="json", exclude={"frozen_hash"})
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_signal_journal() -> tuple[SignalJournal, ...]:
    path = _journal_path()
    if not path.exists():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Expected a frozen signal journal array")
    records = tuple(SignalJournal.model_validate_json(json.dumps(row)) for row in raw)
    if any(_digest(r) != r.frozen_hash for r in records) or len(
        {r.journal_id for r in records}
    ) != len(records):
        raise ValueError("Signal journal hash or identity mismatch")
    return records


def freeze_signal(
    journal_id: str, instrument_id: str, action_state: str, horizon: Horizon, forecast_session: date
) -> SignalJournal:
    """Append atomically. An interrupted writer leaves a visible lock for manual recovery."""
    path = _journal_path()
    lock = path.with_suffix(".lock")
    if not journal_id.strip() or not instrument_id.strip() or not action_state.strip():
        raise ValueError("Missing frozen signal identity or research state")
    # Acquire exclusively before reading; two processes cannot accept the same stale state.
    with lock.open("x", encoding="ascii"):
        pass
    tmp: Path | None = None
    try:
        records = read_signal_journal()
        previous = next((r for r in records if r.journal_id == journal_id), None)
        if previous:
            if (
                previous.instrument_id,
                previous.action_state,
                previous.horizon,
                previous.forecast_session,
            ) == (instrument_id, action_state, horizon, forecast_session):
                return previous
            raise ValueError("Frozen journal ID already contains a different signal")
        recorded = datetime.now(UTC)
        if forecast_session <= (recorded + timedelta(hours=1)).date():
            raise ValueError("Frozen signals require a future Tunis session")
        draft = SignalJournal(
            journal_id=journal_id,
            instrument_id=instrument_id,
            action_state=action_state,
            recorded_at=recorded,
            horizon=horizon,
            forecast_session=forecast_session,
            frozen_hash="",
            outcome_status="PENDING",
        )
        record = draft.model_copy(update={"frozen_hash": _digest(draft)})
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump([r.model_dump(mode="json") for r in (*records, record)], f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return record
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        lock.unlink()
