"""5-state trading decision-support recommendation engine (Milestone 1C).

Connects session-aware quantitative rankings (T04) and verified corporate event citations
to the manual portfolio ledger (`PortfolioLedger`). Never invents target prices or expected
returns, and never submits orders automatically.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal

from bvmt.features import ExcludedInstrument, SessionBaselineReport, SessionCandidate
from bvmt.ledger import (
    DEFAULT_FEE_RATE,
    PortfolioLedger,
    compute_commission,
    quantize_tnd,
)

RECOMMENDATION_CATEGORIES = frozenset(
    {
        "BUY CANDIDATE",
        "HOLD",
        "REDUCE",
        "SELL CANDIDATE",
        "NO TRADE",
    }
)

TARGET_BUY_WEIGHT_RATIO = Decimal("0.085")  # 8.5% target allocation (safety buffer below 10.0% cap)
REDUCE_TRIGGER_WEIGHT_RATIO = Decimal("0.095")  # 9.5% trigger to trim back toward 8.5%
MAX_TURNOVER_PARTICIPATION_RATIO = Decimal(
    "0.10"
)  # Cap proposed order at 10% of 20s median turnover
FEE_HURDLE_MOMENTUM_20S = 0.015  # 1.5% minimum 20-session momentum (> 1.00% round-trip fee drag)


@dataclass(frozen=True)
class VerifiedEventSignal:
    event_id: str
    instrument_id: str
    published_at: str
    event_type: str
    polarity: str  # "positive" | "neutral" | "adverse_risk"
    summary: str
    verbatim_quote: str
    source_document_id: str
    quote_verified: bool


@dataclass(frozen=True)
class RecommendationCard:
    recommendation_id: str
    instrument_id: str
    symbol: str
    category: str  # BUY CANDIDATE, HOLD, REDUCE, SELL CANDIDATE, NO TRADE
    signal_generated_at: str
    latest_market_data_session: str
    simulation_profile: str
    rank: int | None
    composite_score: float | None
    momentum_20s: float | None
    momentum_60s: float | None
    relative_strength_20s: float | None
    volatility_20s: float | None
    median_turnover_20s_tnd: str | None
    trade_frequency_20s: float | None
    reference_price_tnd: str | None
    current_shares: int
    current_weight_pct: str
    suggested_side: str | None  # "BUY" | "SELL" | None
    suggested_shares: int
    suggested_limit_price_tnd: str | None
    suggested_gross_amount_tnd: str
    estimated_fee_tnd: str
    projected_weight_pct: str
    supporting_evidence: list[str]
    main_risks: list[str]
    liquidity_warnings: list[str]
    pending_order_warnings: list[str]
    blocked_reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RecommendationReport:
    generated_at: str
    decision_cutoff: str
    latest_open_session: str
    simulation_profile: str
    data_is_synthetic: bool
    rule_blocker_count: int
    recommendations: list[RecommendationCard]

    def to_dict(self) -> dict[str, object]:
        return {
            "data_is_synthetic": self.data_is_synthetic,
            "decision_cutoff": self.decision_cutoff,
            "generated_at": self.generated_at,
            "latest_open_session": self.latest_open_session,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "rule_blocker_count": self.rule_blocker_count,
            "simulation_profile": self.simulation_profile,
        }


def _make_rec_id(session_str: str, symbol: str, seq: int) -> str:
    clean_date = session_str.replace("-", "")
    clean_sym = "".join(ch for ch in symbol.upper() if ch.isalnum()) or "INST"
    return f"REC-{clean_date}-{clean_sym}-{seq:02d}"


def generate_recommendations(
    baseline: SessionBaselineReport,
    ledger: PortfolioLedger,
    *,
    generated_at: datetime,
    simulation_profile: str = "SYNTHETIC_DEMO",
    data_is_synthetic: bool = True,
    rule_blocker_count: int = 0,
    verified_events: Sequence[VerifiedEventSignal] = (),
    top_buy_count: int = 3,
    target_buy_weight_ratio: Decimal = TARGET_BUY_WEIGHT_RATIO,
    reduce_trigger_weight_ratio: Decimal = REDUCE_TRIGGER_WEIGHT_RATIO,
) -> RecommendationReport:
    """Combine session-aware rankings, verified event signals, and portfolio ledger into 5-state recommendations."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    if top_buy_count < 1:
        raise ValueError("top_buy_count must be >= 1")

    # Build current price map from baseline candidates
    price_map: dict[str, Decimal] = {}
    candidate_by_inst: dict[str, tuple[int, SessionCandidate]] = {}
    for idx, cand in enumerate(baseline.candidates, start=1):
        px = quantize_tnd(cand.close)
        price_map[cand.instrument_id] = px
        candidate_by_inst[cand.instrument_id] = (idx, cand)

    exclusion_by_inst: dict[str, list[ExcludedInstrument]] = {}
    for excl in baseline.exclusions:
        exclusion_by_inst.setdefault(excl.instrument_id, []).append(excl)

    # Filter events to point-in-time verified events only
    events_by_inst: dict[str, list[VerifiedEventSignal]] = {}
    for ev in verified_events:
        if ev.quote_verified:
            events_by_inst.setdefault(ev.instrument_id, []).append(ev)

    valuation = ledger.valuate(price_map)
    total_equity = valuation.total_equity_tnd
    holding_val_map = {h.instrument_id: h for h in valuation.holdings}

    # Track running available cash across proposed BUY candidates so total proposals never exceed cash
    running_available_cash = ledger.available_cash_tnd

    all_inst_ids = sorted(
        set(candidate_by_inst.keys())
        | set(exclusion_by_inst.keys())
        | {inst_id for inst_id, pos in ledger.holdings.items() if pos.total_shares > 0}
    )

    # Order evaluation so ranked candidates come first in rank order, followed by excluded/held instruments
    ordered_inst_ids = [c.instrument_id for c in baseline.candidates] + [
        i for i in all_inst_ids if i not in candidate_by_inst
    ]

    cards: list[RecommendationCard] = []
    for seq, inst_id in enumerate(ordered_inst_ids, start=1):
        rank_tuple = candidate_by_inst.get(inst_id)
        excls = exclusion_by_inst.get(inst_id, [])
        pos = ledger.holdings.get(inst_id)
        held_shares = pos.total_shares if pos is not None else 0
        avail_sell_shares = pos.available_shares if pos is not None else 0
        h_val = holding_val_map.get(inst_id)
        current_weight_pct = h_val.portfolio_weight_pct if h_val is not None else Decimal("0.000")
        current_mv = h_val.market_value_tnd if h_val is not None else Decimal("0.000")

        open_orders = ledger.open_orders_for_instrument(inst_id)
        inst_events = events_by_inst.get(inst_id, [])
        adverse_events = [e for e in inst_events if e.polarity == "adverse_risk"]
        positive_events = [e for e in inst_events if e.polarity == "positive"]

        pending_warnings = [
            f"Open order {o.order_id}: {o.side} {o.remaining_shares}/{o.requested_shares} {o.symbol} @ {o.limit_price_tnd} TND ({o.status})"
            for o in open_orders
        ]
        risk_notes: list[str] = []
        if data_is_synthetic:
            risk_notes.append(
                "SYNTHETIC DEMO DATA: Rankings use labeled synthetic fixture bars, not live BVMT prices."
            )
        if rule_blocker_count > 0:
            risk_notes.append(
                f"COMPETITION RULES PARTIALLY UNVERIFIED: {rule_blocker_count} attribute blocker(s) remain in configs/competition.json."
            )
        risk_notes.append(
            "EXECUTION WINDOW & QUEUE RISK: Orders on tunisbourse-challenge.com execute only 09:00-14:15 Africa/Tunis and stay PENDING on zero-volume stocks (1-week expiry)."
        )

        # Case 1: Instrument was excluded by point-in-time eligibility, staleness, suspension, or liquidity gates
        if rank_tuple is None:
            sym = (
                pos.symbol
                if pos is not None
                else (excls[0].symbol if excls and excls[0].symbol else inst_id)
            )
            blocked = [f"{e.reason}: {e.detail}" for e in excls] or [
                "unranked_instrument: No valid point-in-time session baseline observation"
            ]
            liq_warn = [
                f"{e.reason}: {e.detail}"
                for e in excls
                if e.reason in {"insufficient_liquidity", "stale_quote", "untraded_lookback_anchor"}
            ]
            evidence = [
                f"Session baseline cutoff {baseline.decision_cutoff} excluded {sym} ({', '.join(e.reason for e in excls)})."
            ]
            cards.append(
                RecommendationCard(
                    recommendation_id=_make_rec_id(baseline.latest_open_session, sym, seq),
                    instrument_id=inst_id,
                    symbol=sym,
                    category="NO TRADE",
                    signal_generated_at=generated_at.isoformat(),
                    latest_market_data_session=baseline.latest_open_session,
                    simulation_profile=simulation_profile,
                    rank=None,
                    composite_score=None,
                    momentum_20s=None,
                    momentum_60s=None,
                    relative_strength_20s=None,
                    volatility_20s=None,
                    median_turnover_20s_tnd=None,
                    trade_frequency_20s=None,
                    reference_price_tnd=str(pos.average_cost_tnd) if pos else None,
                    current_shares=held_shares,
                    current_weight_pct=str(current_weight_pct),
                    suggested_side=None,
                    suggested_shares=0,
                    suggested_limit_price_tnd=None,
                    suggested_gross_amount_tnd="0.000",
                    estimated_fee_tnd="0.000",
                    projected_weight_pct=str(current_weight_pct),
                    supporting_evidence=evidence,
                    main_risks=risk_notes,
                    liquidity_warnings=liq_warn,
                    pending_order_warnings=pending_warnings,
                    blocked_reasons=blocked,
                )
            )
            continue

        rank, cand = rank_tuple
        ref_price = quantize_tnd(cand.close)
        med_turnover = quantize_tnd(cand.median_turnover_20s)
        liq_warnings: list[str] = []
        if cand.trade_frequency_20s < 0.85:
            liq_warnings.append(
                f"Moderate trading frequency: traded in {cand.trade_frequency_20s * 100:.0f}% of last {baseline.short_lookback_sessions} open sessions."
            )
        if med_turnover < Decimal("25000.000"):
            liq_warnings.append(
                f"Low median daily turnover ({med_turnover} TND); large orders risk partial fill or 1-week queue expiry."
            )

        evidence_list = [
            f"Rank #{rank} of {len(baseline.candidates)} eligible {cand.market_segment} stocks (composite score: {cand.composite_score:+.4f}).",
            f"Session momentum: {baseline.short_lookback_sessions}s = {cand.momentum_20s * 100:+.2f}%, "
            f"{baseline.long_lookback_sessions}s = {cand.momentum_60s * 100:+.2f}%, "
            f"RS vs universe ({baseline.benchmark_return_20s * 100:+.2f}%) = {cand.relative_strength_20s * 100:+.2f}%.",
            f"Liquidity ({baseline.short_lookback_sessions}s): median turnover {med_turnover} TND, trade frequency {cand.trade_frequency_20s * 100:.0f}%, volatility {cand.volatility_20s * 100:.2f}%.",
        ]
        for pev in positive_events:
            evidence_list.append(
                f'Verified Event [{pev.event_id} / {pev.source_document_id}]: {pev.summary} ("{pev.verbatim_quote}")'
            )
        for aev in adverse_events:
            risk_notes.append(
                f'ADVERSE EVENT [{aev.event_id} / {aev.source_document_id}]: {aev.summary} ("{aev.verbatim_quote}")'
            )

        # If an open order already exists for this instrument, block duplicate sizing -> NO TRADE
        if open_orders:
            cards.append(
                RecommendationCard(
                    recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                    instrument_id=inst_id,
                    symbol=cand.symbol,
                    category="NO TRADE",
                    signal_generated_at=generated_at.isoformat(),
                    latest_market_data_session=cand.last_session,
                    simulation_profile=simulation_profile,
                    rank=rank,
                    composite_score=cand.composite_score,
                    momentum_20s=cand.momentum_20s,
                    momentum_60s=cand.momentum_60s,
                    relative_strength_20s=cand.relative_strength_20s,
                    volatility_20s=cand.volatility_20s,
                    median_turnover_20s_tnd=str(med_turnover),
                    trade_frequency_20s=cand.trade_frequency_20s,
                    reference_price_tnd=str(ref_price),
                    current_shares=held_shares,
                    current_weight_pct=str(current_weight_pct),
                    suggested_side=None,
                    suggested_shares=0,
                    suggested_limit_price_tnd=None,
                    suggested_gross_amount_tnd="0.000",
                    estimated_fee_tnd="0.000",
                    projected_weight_pct=str(current_weight_pct),
                    supporting_evidence=evidence_list,
                    main_risks=risk_notes,
                    liquidity_warnings=liq_warnings,
                    pending_order_warnings=pending_warnings,
                    blocked_reasons=[
                        "pending_order_conflict: Active PENDING/PARTIALLY_FILLED order exists for this stock; reconcile before placing another order."
                    ],
                )
            )
            continue

        # Case 2: Currently held position (held_shares > 0)
        if held_shares > 0:
            current_weight_ratio = (
                (current_mv / total_equity) if total_equity > Decimal("0") else Decimal("0")
            )
            # 2a. Concentration breach / approach -> REDUCE
            if current_weight_ratio > reduce_trigger_weight_ratio:
                target_mv = quantize_tnd(total_equity * target_buy_weight_ratio)
                excess_mv = max(Decimal("0.000"), current_mv - target_mv)
                trim_shares = min(
                    avail_sell_shares,
                    max(1, int((excess_mv / ref_price).to_integral_value())),
                )
                gross = quantize_tnd(Decimal(trim_shares) * ref_price)
                fee = compute_commission(gross, ledger.fee_rate)
                proj_mv = max(Decimal("0.000"), current_mv - gross)
                proj_wt = (
                    quantize_tnd((proj_mv / total_equity) * Decimal("100"))
                    if total_equity > Decimal("0")
                    else Decimal("0.000")
                )
                evidence_list.append(
                    f"Current position weight ({current_weight_pct}%) exceeds {reduce_trigger_weight_ratio * 100:.1f}% safety threshold against the 10.0% competition cap."
                )
                cards.append(
                    RecommendationCard(
                        recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                        instrument_id=inst_id,
                        symbol=cand.symbol,
                        category="REDUCE",
                        signal_generated_at=generated_at.isoformat(),
                        latest_market_data_session=cand.last_session,
                        simulation_profile=simulation_profile,
                        rank=rank,
                        composite_score=cand.composite_score,
                        momentum_20s=cand.momentum_20s,
                        momentum_60s=cand.momentum_60s,
                        relative_strength_20s=cand.relative_strength_20s,
                        volatility_20s=cand.volatility_20s,
                        median_turnover_20s_tnd=str(med_turnover),
                        trade_frequency_20s=cand.trade_frequency_20s,
                        reference_price_tnd=str(ref_price),
                        current_shares=held_shares,
                        current_weight_pct=str(current_weight_pct),
                        suggested_side="SELL",
                        suggested_shares=trim_shares,
                        suggested_limit_price_tnd=str(ref_price),
                        suggested_gross_amount_tnd=str(gross),
                        estimated_fee_tnd=str(fee),
                        projected_weight_pct=str(proj_wt),
                        supporting_evidence=evidence_list,
                        main_risks=risk_notes,
                        liquidity_warnings=liq_warnings,
                        pending_order_warnings=pending_warnings,
                        blocked_reasons=[],
                    )
                )
                continue

            # 2b. Negative momentum breakdown or adverse verified event -> SELL CANDIDATE
            if (cand.momentum_20s < 0.0 and cand.momentum_60s < 0.0) or bool(adverse_events):
                sell_sh = avail_sell_shares
                gross = quantize_tnd(Decimal(sell_sh) * ref_price)
                fee = compute_commission(gross, ledger.fee_rate)
                reason_txt = (
                    "Adverse verified corporate event"
                    if adverse_events
                    else "Negative short- and long-session momentum breakdown"
                )
                evidence_list.append(f"Exit trigger: {reason_txt}.")
                cards.append(
                    RecommendationCard(
                        recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                        instrument_id=inst_id,
                        symbol=cand.symbol,
                        category="SELL CANDIDATE",
                        signal_generated_at=generated_at.isoformat(),
                        latest_market_data_session=cand.last_session,
                        simulation_profile=simulation_profile,
                        rank=rank,
                        composite_score=cand.composite_score,
                        momentum_20s=cand.momentum_20s,
                        momentum_60s=cand.momentum_60s,
                        relative_strength_20s=cand.relative_strength_20s,
                        volatility_20s=cand.volatility_20s,
                        median_turnover_20s_tnd=str(med_turnover),
                        trade_frequency_20s=cand.trade_frequency_20s,
                        reference_price_tnd=str(ref_price),
                        current_shares=held_shares,
                        current_weight_pct=str(current_weight_pct),
                        suggested_side="SELL" if sell_sh > 0 else None,
                        suggested_shares=sell_sh,
                        suggested_limit_price_tnd=str(ref_price) if sell_sh > 0 else None,
                        suggested_gross_amount_tnd=str(gross),
                        estimated_fee_tnd=str(fee),
                        projected_weight_pct="0.000",
                        supporting_evidence=evidence_list,
                        main_risks=risk_notes,
                        liquidity_warnings=liq_warnings,
                        pending_order_warnings=pending_warnings,
                        blocked_reasons=[],
                    )
                )
                continue

            # 2c. Otherwise keep holding -> HOLD
            evidence_list.append(
                f"Existing position ({held_shares} shares, {current_weight_pct}% weight) remains within 10% cap with intact trend; holding avoids 1.00% round-trip fee churn."
            )
            cards.append(
                RecommendationCard(
                    recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                    instrument_id=inst_id,
                    symbol=cand.symbol,
                    category="HOLD",
                    signal_generated_at=generated_at.isoformat(),
                    latest_market_data_session=cand.last_session,
                    simulation_profile=simulation_profile,
                    rank=rank,
                    composite_score=cand.composite_score,
                    momentum_20s=cand.momentum_20s,
                    momentum_60s=cand.momentum_60s,
                    relative_strength_20s=cand.relative_strength_20s,
                    volatility_20s=cand.volatility_20s,
                    median_turnover_20s_tnd=str(med_turnover),
                    trade_frequency_20s=cand.trade_frequency_20s,
                    reference_price_tnd=str(ref_price),
                    current_shares=held_shares,
                    current_weight_pct=str(current_weight_pct),
                    suggested_side=None,
                    suggested_shares=0,
                    suggested_limit_price_tnd=None,
                    suggested_gross_amount_tnd="0.000",
                    estimated_fee_tnd="0.000",
                    projected_weight_pct=str(current_weight_pct),
                    supporting_evidence=evidence_list,
                    main_risks=risk_notes,
                    liquidity_warnings=liq_warnings,
                    pending_order_warnings=pending_warnings,
                    blocked_reasons=[],
                )
            )
            continue

        # Case 3: Unheld eligible candidate (held_shares == 0)
        if adverse_events:
            cards.append(
                RecommendationCard(
                    recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                    instrument_id=inst_id,
                    symbol=cand.symbol,
                    category="NO TRADE",
                    signal_generated_at=generated_at.isoformat(),
                    latest_market_data_session=cand.last_session,
                    simulation_profile=simulation_profile,
                    rank=rank,
                    composite_score=cand.composite_score,
                    momentum_20s=cand.momentum_20s,
                    momentum_60s=cand.momentum_60s,
                    relative_strength_20s=cand.relative_strength_20s,
                    volatility_20s=cand.volatility_20s,
                    median_turnover_20s_tnd=str(med_turnover),
                    trade_frequency_20s=cand.trade_frequency_20s,
                    reference_price_tnd=str(ref_price),
                    current_shares=0,
                    current_weight_pct="0.000",
                    suggested_side=None,
                    suggested_shares=0,
                    suggested_limit_price_tnd=None,
                    suggested_gross_amount_tnd="0.000",
                    estimated_fee_tnd="0.000",
                    projected_weight_pct="0.000",
                    supporting_evidence=evidence_list,
                    main_risks=risk_notes,
                    liquidity_warnings=liq_warnings,
                    pending_order_warnings=pending_warnings,
                    blocked_reasons=["adverse_verified_event: Blocked by verified risk disclosure"],
                )
            )
            continue

        if (
            rank <= top_buy_count
            and cand.momentum_20s >= FEE_HURDLE_MOMENTUM_20S
            and cand.momentum_60s > 0.0
            and cand.relative_strength_20s >= 0.0
        ):
            # Size position up to min(8.5% of total equity, 10% of 20s median turnover, available cash)
            target_notional_cap = quantize_tnd(total_equity * target_buy_weight_ratio)
            liquidity_notional_cap = quantize_tnd(med_turnover * MAX_TURNOVER_PARTICIPATION_RATIO)
            cash_notional_cap = quantize_tnd(
                running_available_cash / (Decimal("1") + (ledger.fee_rate or DEFAULT_FEE_RATE))
            )

            effective_notional = min(target_notional_cap, cash_notional_cap)
            if (
                liquidity_notional_cap > Decimal("0")
                and liquidity_notional_cap < effective_notional
            ):
                liq_warnings.append(
                    f"Order size capped at 10% of 20-session median turnover ({liquidity_notional_cap} TND) to limit market impact and queue risk."
                )
                effective_notional = liquidity_notional_cap

            buy_shares = int(effective_notional // ref_price)
            # Ensure gross + fee fits strictly within running_available_cash and 10% hard cap
            while buy_shares > 0:
                gross = quantize_tnd(Decimal(buy_shares) * ref_price)
                fee = compute_commission(gross, ledger.fee_rate)
                if gross + fee <= running_available_cash and gross <= quantize_tnd(
                    total_equity * ledger.max_concentration_ratio
                ):
                    break
                buy_shares -= 1

            if buy_shares > 0:
                gross = quantize_tnd(Decimal(buy_shares) * ref_price)
                fee = compute_commission(gross, ledger.fee_rate)
                running_available_cash = quantize_tnd(running_available_cash - (gross + fee))
                proj_wt = (
                    quantize_tnd((gross / total_equity) * Decimal("100"))
                    if total_equity > Decimal("0")
                    else Decimal("0.000")
                )
                cards.append(
                    RecommendationCard(
                        recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                        instrument_id=inst_id,
                        symbol=cand.symbol,
                        category="BUY CANDIDATE",
                        signal_generated_at=generated_at.isoformat(),
                        latest_market_data_session=cand.last_session,
                        simulation_profile=simulation_profile,
                        rank=rank,
                        composite_score=cand.composite_score,
                        momentum_20s=cand.momentum_20s,
                        momentum_60s=cand.momentum_60s,
                        relative_strength_20s=cand.relative_strength_20s,
                        volatility_20s=cand.volatility_20s,
                        median_turnover_20s_tnd=str(med_turnover),
                        trade_frequency_20s=cand.trade_frequency_20s,
                        reference_price_tnd=str(ref_price),
                        current_shares=0,
                        current_weight_pct="0.000",
                        suggested_side="BUY",
                        suggested_shares=buy_shares,
                        suggested_limit_price_tnd=str(ref_price),
                        suggested_gross_amount_tnd=str(gross),
                        estimated_fee_tnd=str(fee),
                        projected_weight_pct=str(proj_wt),
                        supporting_evidence=evidence_list,
                        main_risks=risk_notes,
                        liquidity_warnings=liq_warnings,
                        pending_order_warnings=pending_warnings,
                        blocked_reasons=[],
                    )
                )
                continue
            else:
                cards.append(
                    RecommendationCard(
                        recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                        instrument_id=inst_id,
                        symbol=cand.symbol,
                        category="NO TRADE",
                        signal_generated_at=generated_at.isoformat(),
                        latest_market_data_session=cand.last_session,
                        simulation_profile=simulation_profile,
                        rank=rank,
                        composite_score=cand.composite_score,
                        momentum_20s=cand.momentum_20s,
                        momentum_60s=cand.momentum_60s,
                        relative_strength_20s=cand.relative_strength_20s,
                        volatility_20s=cand.volatility_20s,
                        median_turnover_20s_tnd=str(med_turnover),
                        trade_frequency_20s=cand.trade_frequency_20s,
                        reference_price_tnd=str(ref_price),
                        current_shares=0,
                        current_weight_pct="0.000",
                        suggested_side=None,
                        suggested_shares=0,
                        suggested_limit_price_tnd=None,
                        suggested_gross_amount_tnd="0.000",
                        estimated_fee_tnd="0.000",
                        projected_weight_pct="0.000",
                        supporting_evidence=evidence_list,
                        main_risks=risk_notes,
                        liquidity_warnings=liq_warnings,
                        pending_order_warnings=pending_warnings,
                        blocked_reasons=[
                            f"insufficient_available_cash: Available cash ({running_available_cash} TND) cannot fund 1 share @ {ref_price} TND + 0.50% fee"
                        ],
                    )
                )
                continue

        # Lower-ranked or negative-momentum unheld stock -> NO TRADE
        reasons: list[str] = []
        if rank > top_buy_count:
            reasons.append(f"below_rank_cutoff: Rank #{rank} exceeds top-{top_buy_count} shortlist")
        if cand.momentum_20s < FEE_HURDLE_MOMENTUM_20S:
            reasons.append(
                f"below_fee_hurdle: 20s momentum ({cand.momentum_20s * 100:+.2f}%) is below +{FEE_HURDLE_MOMENTUM_20S * 100:.2f}% fee-adjusted threshold"
            )
        if cand.momentum_60s <= 0.0:
            reasons.append(
                f"non_positive_long_momentum: 60s momentum ({cand.momentum_60s * 100:+.2f}%) <= 0%"
            )
        if cand.relative_strength_20s < 0.0:
            reasons.append(
                f"negative_relative_strength: RS ({cand.relative_strength_20s * 100:+.2f}%) underperforms universe benchmark"
            )

        cards.append(
            RecommendationCard(
                recommendation_id=_make_rec_id(cand.last_session, cand.symbol, seq),
                instrument_id=inst_id,
                symbol=cand.symbol,
                category="NO TRADE",
                signal_generated_at=generated_at.isoformat(),
                latest_market_data_session=cand.last_session,
                simulation_profile=simulation_profile,
                rank=rank,
                composite_score=cand.composite_score,
                momentum_20s=cand.momentum_20s,
                momentum_60s=cand.momentum_60s,
                relative_strength_20s=cand.relative_strength_20s,
                volatility_20s=cand.volatility_20s,
                median_turnover_20s_tnd=str(med_turnover),
                trade_frequency_20s=cand.trade_frequency_20s,
                reference_price_tnd=str(ref_price),
                current_shares=0,
                current_weight_pct="0.000",
                suggested_side=None,
                suggested_shares=0,
                suggested_limit_price_tnd=None,
                suggested_gross_amount_tnd="0.000",
                estimated_fee_tnd="0.000",
                projected_weight_pct="0.000",
                supporting_evidence=evidence_list,
                main_risks=risk_notes,
                liquidity_warnings=liq_warnings,
                pending_order_warnings=pending_warnings,
                blocked_reasons=reasons or ["not_actionable"],
            )
        )

    return RecommendationReport(
        generated_at=generated_at.isoformat(),
        decision_cutoff=baseline.decision_cutoff,
        latest_open_session=baseline.latest_open_session,
        simulation_profile=simulation_profile,
        data_is_synthetic=data_is_synthetic,
        rule_blocker_count=rule_blocker_count,
        recommendations=cards,
    )
