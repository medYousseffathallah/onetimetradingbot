"""Multi-layer point-in-time stock research engine & forward-validation ledger (Phases 4 & 7).

Model Version: ``sparse_research_v1``

Core guarantees:
1. Completely decoupled from manual trade planner auto-orders (strictly research-only).
2. Evaluates 7 independent layers at a strict timezone-aware point-in-time (PIT) cutoff:
   - quantitative_trend_evidence
   - fundamental_evidence
   - event_disclosure_evidence
   - liquidity_execution_feasibility
   - data_quality_freshness
   - competition_eligibility
   - portfolio_risk
3. Implements a 5-state Research Status taxonomy separate from trading_eligibility.
4. Missing observations remain explicit ``None`` (JSON ``null``) -- never substituted with ``0``.
5. Stale closes are never forward-filled into ``executable_reference_price_tnd``.
6. Limit-reserved ('H'/'B') bar inspection and sensitivity recovery operate non-destructively
   via separate adapters without modifying ``bvmt.data`` or historical Models A-I.
7. Forward validation records append-only prospective signals and requires multi-stock
   prospective evidence before promotion (explicitly forbidding retrospective ICF-only promotion).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import median
from typing import Any, Literal

from bvmt.calendar import (
    ExchangeSession,
    InstrumentRecord,
    SuspensionRecord,
    resolve_instrument_on_date,
    validate_exchange_calendar,
    validate_instrument_master,
)
from bvmt.challenge_universe import (
    CHALLENGE_UNIVERSE_VERSION,
    ChallengeInstrumentRecord,
    resolve_challenge_record,
)
from bvmt.data import (
    DailyBar,
    aware_timestamp,
    parse_french_decimal,
    parse_french_session_date,
    validate_bars,
)
from bvmt.execution import MarketOrder, estimate_next_bar_fill
from bvmt.features import SessionBaselineReport
from bvmt.llm import DocumentChunk
from bvmt.macro_events import (
    get_verified_macro_intelligence,
    resolve_instrument_aliases,
)
from bvmt.position_sizing import (
    DEFAULT_PURCHASE_FEE_RATE,
    DEFAULT_SALE_FEE_RATE,
    PendingOrderReservation,
    quantize_tnd,
)

SPARSE_OPPORTUNITY_MODEL_VERSION = "sparse_research_v1"

ResearchStatus = Literal[
    "FULL_RESEARCH_AVAILABLE",
    "PARTIAL_RESEARCH_AVAILABLE",
    "EVENT_RESEARCH_AVAILABLE",
    "INSUFFICIENT_EVIDENCE",
    "RESTRICTED_FOR_TRADING",
]

ResearchTier = Literal[
    "FULL_RESEARCH_AVAILABLE",
    "PARTIAL_RESEARCH_AVAILABLE",
    "EVENT_RESEARCH_AVAILABLE",
    "INSUFFICIENT_EVIDENCE",
]

TradingEligibilityCode = Literal[
    "CHALLENGE_ORDER_ELIGIBLE",
    "UNTRADED_OR_STALE_EXECUTION_RISK",
    "RESEARCH_ONLY_NOT_IN_CHALLENGE",
    "SUSPENDED_AT_CUTOFF",
    "MARKET_SEGMENT_RESTRICTED",
]

FundamentalAvailability = Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE"]
EventAvailability = Literal["EVENTS_FOUND", "MACRO_CONTEXT_ONLY", "NO_VERIFIED_EVENTS"]
ExecutionFeasibilityStatus = Literal[
    "FEASIBLE",
    "LIQUIDITY_LIMITED",
    "STALE_OR_UNTRADED",
    "INSUFFICIENT_OBSERVATIONS",
    "MARKET_RESTRICTED",
]
FreshnessTier = Literal[
    "FRESH",
    "RECENT",
    "STALE",
    "NEVER_TRADED",
    "MISSING_RECENT_BAR",
]
ExecutionTrapRisk = Literal["LOW", "MODERATE", "HIGH", "EXTREME"]

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "sparse_research_v1.json"


def _round_float(val: float, digits: int = 4) -> float:
    return round(float(val), digits)


def _money_decimal(val: Any) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _norm_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9._-]+", "_", value.strip().upper()).strip("_")


# ---------------------------------------------------------------------------
# Frozen Configuration & Hashing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromotionGateConfig:
    """Conservative quantitative gates required before model promotion."""

    min_prospective_settled_signals: int = 20
    min_prospective_sessions: int = 20
    min_non_icf_settled_signals: int = 15
    max_false_positive_rate: float = 0.45
    max_false_positive_uplift_vs_baseline: float = 0.05
    min_mean_net_return_after_costs_pct: float = 0.0
    max_drawdown_pct: float = 15.0
    require_non_icf_positive_expectancy: bool = True
    forbid_promotion_solely_on_retrospective_icf: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SparseResearchConfig:
    """Immutable, hashable research model configuration."""

    schema_version: int = 1
    model_version: str = SPARSE_OPPORTUNITY_MODEL_VERSION
    auto_order_submission: bool = False
    micro_lookback_sessions: int = 5
    short_lookback_sessions: int = 20
    long_lookback_sessions: int = 60
    awakening_baseline_sessions: int = 20
    min_awakening_baseline_bars: int = 5
    full_max_quote_age_sessions: int = 2
    partial_max_quote_age_sessions: int = 15
    full_min_trade_freq_20s: float = 0.75
    full_max_missing_in_60s: int = 0
    min_partial_traded_bars: int = 2
    liquidity_feasible_median_turnover_tnd: Decimal = Decimal("5000.000")
    liquidity_marginal_median_turnover_tnd: Decimal = Decimal("1000.000")
    awakening_turnover_ratio_threshold: float = 3.0
    awakening_min_turnover_tnd: Decimal = Decimal("10000.000")
    awakening_min_day_return_pct: float = 0.0
    partial_horizon_score_multiplier: float = 0.65
    awakening_score_bonus: float = 6.0
    event_catalyst_score_bonus: float = 2.5
    sparse_zero_vol_penalty: float = 3.0
    sparse_zero_vol_penalty_threshold: float = 0.40
    candidate_min_quant_score: float = 5.0
    candidate_top_k: int = 8
    candidate_allow_awakening_bypass: bool = True
    candidate_allow_event_catalyst: bool = True
    buy_fee_rate: Decimal = DEFAULT_PURCHASE_FEE_RATE
    sell_fee_rate: Decimal = DEFAULT_SALE_FEE_RATE
    slippage_bps: Decimal = Decimal("20")
    liquidity_participation_cap: Decimal = Decimal("0.1000")
    max_single_stock_weight: Decimal = Decimal("0.1000")
    target_position_weight: Decimal = Decimal("0.0850")
    minimum_order_notional_tnd: Decimal = Decimal("100.000")
    daily_collar_static_pct: Decimal = Decimal("3.00")
    hb_recovery_enabled_by_default: bool = False
    promotion_gates: PromotionGateConfig = field(default_factory=PromotionGateConfig)

    def __post_init__(self) -> None:
        if self.auto_order_submission:
            raise ValueError("Sparse research model must never enable auto_order_submission")
        if self.micro_lookback_sessions < 2 or self.short_lookback_sessions < 5:
            raise ValueError("Lookbacks must satisfy micro >= 2 and short >= 5")
        if self.long_lookback_sessions < self.short_lookback_sessions:
            raise ValueError("long_lookback_sessions must be >= short_lookback_sessions")
        if not (0.0 < self.full_min_trade_freq_20s <= 1.0):
            raise ValueError("full_min_trade_freq_20s must be in (0, 1]")
        if self.awakening_turnover_ratio_threshold <= 1.0:
            raise ValueError("awakening_turnover_ratio_threshold must be > 1.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_version": self.model_version,
            "auto_order_submission": self.auto_order_submission,
            "research_parameters": {
                "micro_lookback_sessions": self.micro_lookback_sessions,
                "short_lookback_sessions": self.short_lookback_sessions,
                "long_lookback_sessions": self.long_lookback_sessions,
                "awakening_baseline_sessions": self.awakening_baseline_sessions,
                "min_awakening_baseline_bars": self.min_awakening_baseline_bars,
                "full_max_quote_age_sessions": self.full_max_quote_age_sessions,
                "partial_max_quote_age_sessions": self.partial_max_quote_age_sessions,
                "full_min_trade_freq_20s": self.full_min_trade_freq_20s,
                "full_max_missing_in_60s": self.full_max_missing_in_60s,
                "min_partial_traded_bars": self.min_partial_traded_bars,
                "liquidity_feasible_median_turnover_tnd": str(
                    self.liquidity_feasible_median_turnover_tnd
                ),
                "liquidity_marginal_median_turnover_tnd": str(
                    self.liquidity_marginal_median_turnover_tnd
                ),
                "awakening_turnover_ratio_threshold": self.awakening_turnover_ratio_threshold,
                "awakening_min_turnover_tnd": str(self.awakening_min_turnover_tnd),
                "awakening_min_day_return_pct": self.awakening_min_day_return_pct,
                "partial_horizon_score_multiplier": self.partial_horizon_score_multiplier,
                "awakening_score_bonus": self.awakening_score_bonus,
                "event_catalyst_score_bonus": self.event_catalyst_score_bonus,
                "sparse_zero_vol_penalty": self.sparse_zero_vol_penalty,
                "sparse_zero_vol_penalty_threshold": self.sparse_zero_vol_penalty_threshold,
                "candidate_min_quant_score": self.candidate_min_quant_score,
                "candidate_top_k": self.candidate_top_k,
                "candidate_allow_awakening_bypass": self.candidate_allow_awakening_bypass,
                "candidate_allow_event_catalyst": self.candidate_allow_event_catalyst,
            },
            "execution_and_risk": {
                "buy_fee_rate": str(self.buy_fee_rate),
                "sell_fee_rate": str(self.sell_fee_rate),
                "slippage_bps": str(self.slippage_bps),
                "liquidity_participation_cap": str(self.liquidity_participation_cap),
                "max_single_stock_weight": str(self.max_single_stock_weight),
                "target_position_weight": str(self.target_position_weight),
                "minimum_order_notional_tnd": str(self.minimum_order_notional_tnd),
                "daily_collar_static_pct": str(self.daily_collar_static_pct),
            },
            "hb_limit_reserved_experiment": {
                "enabled_by_default": self.hb_recovery_enabled_by_default,
            },
            "promotion_gates": self.promotion_gates.to_dict(),
        }

    def config_sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_frozen_sparse_research_config(path: Path | None = None) -> SparseResearchConfig:
    """Load the frozen ``sparse_research_v1`` configuration JSON (or default if absent)."""
    target = path or _DEFAULT_CONFIG_PATH
    if not target.is_file():
        return SparseResearchConfig()
    raw = json.loads(target.read_text(encoding="utf-8"))
    rp = raw.get("research_parameters", {})
    er = raw.get("execution_and_risk", {})
    hb = raw.get("hb_limit_reserved_experiment", {})
    pg = raw.get("promotion_gates", {})
    gates = PromotionGateConfig(
        min_prospective_settled_signals=int(pg.get("min_prospective_settled_signals", 20)),
        min_prospective_sessions=int(pg.get("min_prospective_sessions", 20)),
        min_non_icf_settled_signals=int(pg.get("min_non_icf_settled_signals", 15)),
        max_false_positive_rate=float(pg.get("max_false_positive_rate", 0.45)),
        max_false_positive_uplift_vs_baseline=float(
            pg.get("max_false_positive_uplift_vs_baseline", 0.05)
        ),
        min_mean_net_return_after_costs_pct=float(
            pg.get("min_mean_net_return_after_costs_pct", 0.0)
        ),
        max_drawdown_pct=float(pg.get("max_drawdown_pct", 15.0)),
        require_non_icf_positive_expectancy=bool(
            pg.get("require_non_icf_positive_expectancy", True)
        ),
        forbid_promotion_solely_on_retrospective_icf=bool(
            pg.get("forbid_promotion_solely_on_retrospective_icf", True)
        ),
    )
    return SparseResearchConfig(
        schema_version=int(raw.get("schema_version", 1)),
        model_version=str(raw.get("model_version", SPARSE_OPPORTUNITY_MODEL_VERSION)),
        auto_order_submission=bool(raw.get("auto_order_submission", False)),
        micro_lookback_sessions=int(rp.get("micro_lookback_sessions", 5)),
        short_lookback_sessions=int(rp.get("short_lookback_sessions", 20)),
        long_lookback_sessions=int(rp.get("long_lookback_sessions", 60)),
        awakening_baseline_sessions=int(rp.get("awakening_baseline_sessions", 20)),
        min_awakening_baseline_bars=int(rp.get("min_awakening_baseline_bars", 5)),
        full_max_quote_age_sessions=int(rp.get("full_max_quote_age_sessions", 2)),
        partial_max_quote_age_sessions=int(rp.get("partial_max_quote_age_sessions", 15)),
        full_min_trade_freq_20s=float(rp.get("full_min_trade_freq_20s", 0.75)),
        full_max_missing_in_60s=int(rp.get("full_max_missing_in_60s", 0)),
        min_partial_traded_bars=int(rp.get("min_partial_traded_bars", 2)),
        liquidity_feasible_median_turnover_tnd=Decimal(
            str(rp.get("liquidity_feasible_median_turnover_tnd", "5000.000"))
        ),
        liquidity_marginal_median_turnover_tnd=Decimal(
            str(rp.get("liquidity_marginal_median_turnover_tnd", "1000.000"))
        ),
        awakening_turnover_ratio_threshold=float(rp.get("awakening_turnover_ratio_threshold", 3.0)),
        awakening_min_turnover_tnd=Decimal(str(rp.get("awakening_min_turnover_tnd", "10000.000"))),
        awakening_min_day_return_pct=float(rp.get("awakening_min_day_return_pct", 0.0)),
        partial_horizon_score_multiplier=float(rp.get("partial_horizon_score_multiplier", 0.65)),
        awakening_score_bonus=float(rp.get("awakening_score_bonus", 6.0)),
        event_catalyst_score_bonus=float(rp.get("event_catalyst_score_bonus", 2.5)),
        sparse_zero_vol_penalty=float(rp.get("sparse_zero_vol_penalty", 3.0)),
        sparse_zero_vol_penalty_threshold=float(rp.get("sparse_zero_vol_penalty_threshold", 0.40)),
        candidate_min_quant_score=float(rp.get("candidate_min_quant_score", 5.0)),
        candidate_top_k=int(rp.get("candidate_top_k", 8)),
        candidate_allow_awakening_bypass=bool(rp.get("candidate_allow_awakening_bypass", True)),
        candidate_allow_event_catalyst=bool(rp.get("candidate_allow_event_catalyst", True)),
        buy_fee_rate=Decimal(str(er.get("buy_fee_rate", "0.0050"))),
        sell_fee_rate=Decimal(str(er.get("sell_fee_rate", "0.0050"))),
        slippage_bps=Decimal(str(er.get("slippage_bps", "20"))),
        liquidity_participation_cap=Decimal(str(er.get("liquidity_participation_cap", "0.1000"))),
        max_single_stock_weight=Decimal(str(er.get("max_single_stock_weight", "0.1000"))),
        target_position_weight=Decimal(str(er.get("target_position_weight", "0.0850"))),
        minimum_order_notional_tnd=Decimal(str(er.get("minimum_order_notional_tnd", "100.000"))),
        daily_collar_static_pct=Decimal(str(er.get("daily_collar_static_pct", "3.00"))),
        hb_recovery_enabled_by_default=bool(hb.get("enabled_by_default", False)),
        promotion_gates=gates,
    )


def compute_bars_input_sha256(bars: Sequence[DailyBar]) -> str:
    """Deterministic digest of the PIT DailyBar slice fed into evaluation."""
    hasher = hashlib.sha256()
    for b in sorted(bars, key=lambda x: (x.instrument_id, x.session_date)):
        row = (
            f"{b.instrument_id}|{b.session_date.isoformat()}|{b.open}|{b.high}|{b.low}|"
            f"{b.close}|{b.volume_shares}|{b.turnover_tnd}|{b.status}\n"
        )
        hasher.update(row.encode("utf-8"))
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Non-Destructive 'H'/'B' Limit-Reserved Bar Inspection & Sensitivity Adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LimitReservedBarMeta:
    """Audit metadata for BVMT 'H'/'B' limit-reserved closes quarantined by strict OHLC validation."""

    instrument_id: str
    symbol: str
    session_date: date
    indicateur: str
    raw_open: Decimal
    raw_high: Decimal
    raw_low: Decimal
    raw_close: Decimal
    volume_shares: int
    turnover_tnd: Decimal
    recovered_high: Decimal
    recovered_low: Decimal
    recovered: bool
    source_locator: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "session_date": self.session_date.isoformat(),
            "indicateur": self.indicateur,
            "raw_open": str(self.raw_open),
            "raw_high": str(self.raw_high),
            "raw_low": str(self.raw_low),
            "raw_close": str(self.raw_close),
            "volume_shares": self.volume_shares,
            "turnover_tnd": str(self.turnover_tnd),
            "recovered_high": str(self.recovered_high),
            "recovered_low": str(self.recovered_low),
            "recovered": self.recovered,
            "source_locator": self.source_locator,
        }


def extract_limit_reserved_bars_from_rejections(
    rejections_paths: Sequence[Path],
    *,
    allow_recovery: bool = False,
) -> tuple[list[DailyBar], list[LimitReservedBarMeta]]:
    """Inspect BVMT rejection artifacts (`rejections.json` / `rejected_rows.csv`) for 'H'/'B' bars.

    Strictly read-only and non-destructive:
    - Never modifies files on disk or alters ``bvmt.data.validate_bar``.
    - Only extracts rows rejected with ``OHLC bounds are inconsistent`` where
      ``indicateur in ('H', 'B')``, positive close, and positive traded volume.
    - When ``allow_recovery=True``, creates sensitivity-only ``DailyBar`` objects by widening
      ``high=max(raw_open, raw_high, raw_close)`` and ``low=min(raw_open, raw_low, raw_close)``
      so threshold-reserved closes become inspectable without inventing prices.
    """
    seen_keys: set[tuple[str, date]] = set()
    meta_out: list[LimitReservedBarMeta] = []
    bars_out: list[DailyBar] = []

    raw_items: list[tuple[str, str, str]] = []  # (reason, raw_row_json, locator)
    for path in rejections_paths:
        if not path.is_file():
            continue
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("rejections", []) if isinstance(payload, dict) else []
            for idx, entry in enumerate(rows, 1):
                if isinstance(entry, dict):
                    raw_items.append(
                        (
                            str(entry.get("reason", "")),
                            str(entry.get("raw_row", "")),
                            f"{path.name}#{idx}",
                        )
                    )
        elif path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for idx, entry in enumerate(reader, 1):
                    raw_items.append(
                        (
                            str(entry.get("rejection_reason", "")),
                            str(entry.get("raw_row", "")),
                            f"{path.name}#{idx}",
                        )
                    )

    for reason, raw_json, locator in raw_items:
        if reason != "OHLC bounds are inconsistent" or not raw_json.strip():
            continue
        try:
            obj = json.loads(raw_json, parse_float=Decimal)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        indicateur = str(obj.get("indicateur") or "").strip().upper()
        if indicateur not in {"H", "B"}:
            continue
        symbol = str(obj.get("valeur") or "").strip()
        if not symbol:
            continue
        inst_id = _norm_token(symbol)
        try:
            sess_date = parse_french_session_date(str(obj.get("dateSeance", "")))
            raw_open = parse_french_decimal(str(obj.get("coursOuvert", "")), "coursOuvert")
            raw_high = parse_french_decimal(str(obj.get("plusHaut", "")), "plusHaut")
            raw_low = parse_french_decimal(str(obj.get("plusBas", "")), "plusBas")
            raw_close = parse_french_decimal(str(obj.get("cloture", "")), "cloture")
            qty_dec = parse_french_decimal(str(obj.get("quantites", "0")), "quantites")
            turnover = parse_french_decimal(str(obj.get("capitaux", "0")), "capitaux")
        except ValueError:
            continue
        qty = int(qty_dec)
        if raw_close <= 0 or qty <= 0 or turnover <= 0:
            continue

        key = (inst_id, sess_date)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        rec_high = max(raw_open, raw_high, raw_close)
        rec_low = min(raw_open, raw_low, raw_close)
        meta_out.append(
            LimitReservedBarMeta(
                instrument_id=inst_id,
                symbol=symbol,
                session_date=sess_date,
                indicateur=indicateur,
                raw_open=raw_open,
                raw_high=raw_high,
                raw_low=raw_low,
                raw_close=raw_close,
                volume_shares=qty,
                turnover_tnd=turnover,
                recovered_high=rec_high,
                recovered_low=rec_low,
                recovered=allow_recovery,
                source_locator=locator,
            )
        )
        if allow_recovery:
            ts = datetime.fromisoformat(f"{sess_date.isoformat()}T16:00:00+01:00")
            bars_out.append(
                DailyBar(
                    instrument_id=inst_id,
                    symbol=symbol,
                    session_date=sess_date,
                    open=raw_open,
                    high=rec_high,
                    low=rec_low,
                    close=raw_close,
                    volume_shares=qty,
                    turnover_tnd=turnover,
                    status="traded",
                    source_id="bvmt_hb_threshold_recovery",
                    published_at=ts,
                    ingested_at=ts,
                    isin=str(obj.get("codeISIN") or "").strip() or None,
                )
            )

    meta_out.sort(key=lambda m: (m.session_date, m.instrument_id))
    bars_out.sort(key=lambda b: (b.instrument_id, b.session_date))
    return bars_out, meta_out


def merge_canonical_with_hb_recovery(
    canonical_bars: Sequence[DailyBar],
    hb_bars: Sequence[DailyBar],
) -> tuple[list[DailyBar], frozenset[tuple[str, date]]]:
    """Return a merged bar copy for sensitivity testing without overwriting canonical bars."""
    merged = list(canonical_bars)
    existing = {(b.instrument_id, b.session_date) for b in merged}
    recovered_keys: set[tuple[str, date]] = set()
    for hb in hb_bars:
        key = (hb.instrument_id, hb.session_date)
        if key not in existing:
            merged.append(hb)
            existing.add(key)
            recovered_keys.add(key)
    merged.sort(key=lambda b: (b.instrument_id, b.session_date))
    return merged, frozenset(recovered_keys)


def load_emetteur_sector_map(mapping_path: Path) -> dict[str, str]:
    """Read `mapping_emetteur.json` strictly read-only into `{ISIN_or_mnemo: sector_fr}`."""
    if not mapping_path.is_file():
        return {}
    raw = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for isin, rec in raw.items():
        if not isinstance(rec, dict):
            continue
        sec = str(rec.get("sector_fr") or rec.get("sector_en") or "").strip()
        if sec:
            out[str(isin).strip().upper()] = sec
            mn = str(rec.get("mnemo") or "").strip().upper()
            if mn:
                out[mn] = sec
    return out


# ---------------------------------------------------------------------------
# 7 Independent Component Dataclasses + Research/Trading/Explanation Schemas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FundamentalSnapshotRecord:
    """Optional verified PIT fundamental record supplied from local financial tables."""

    instrument_id: str
    period_label: str
    published_at: datetime
    ingested_at: datetime
    source_label: str
    revenue_yoy_pct: float | None = None
    net_income_yoy_pct: float | None = None
    pe_ratio: float | None = None
    pbv_ratio: float | None = None
    dividend_yield_pct: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class QuantitativeTrendEvidence:
    """Layer 1: Multi-horizon trend & volume awakening (None for missing, never 0)."""

    momentum_5s_pct: float | None
    momentum_20s_pct: float | None
    momentum_60s_pct: float | None
    relative_strength_20s_pct: float | None
    benchmark_return_20s_pct: float | None
    observed_trade_return_pct: float | None
    observed_trade_interval_sessions: int | None
    trailing_traded_5_return_pct: float | None
    latest_day_return_pct: float | None
    volatility_20s_pct: float | None
    latest_turnover_tnd: Decimal | None
    trailing_median_turnover_20s_tnd: Decimal | None
    turnover_awakening_ratio: float | None
    volume_awakening_ratio: float | None
    awakening_detected: bool
    is_partial_horizon: bool
    quantitative_score: float | None
    signal_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "momentum_5s_pct": self.momentum_5s_pct,
            "momentum_20s_pct": self.momentum_20s_pct,
            "momentum_60s_pct": self.momentum_60s_pct,
            "relative_strength_20s_pct": self.relative_strength_20s_pct,
            "benchmark_return_20s_pct": self.benchmark_return_20s_pct,
            "observed_trade_return_pct": self.observed_trade_return_pct,
            "observed_trade_interval_sessions": self.observed_trade_interval_sessions,
            "trailing_traded_5_return_pct": self.trailing_traded_5_return_pct,
            "latest_day_return_pct": self.latest_day_return_pct,
            "volatility_20s_pct": self.volatility_20s_pct,
            "latest_turnover_tnd": str(self.latest_turnover_tnd)
            if self.latest_turnover_tnd is not None
            else None,
            "trailing_median_turnover_20s_tnd": str(self.trailing_median_turnover_20s_tnd)
            if self.trailing_median_turnover_20s_tnd is not None
            else None,
            "turnover_awakening_ratio": self.turnover_awakening_ratio,
            "volume_awakening_ratio": self.volume_awakening_ratio,
            "awakening_detected": self.awakening_detected,
            "is_partial_horizon": self.is_partial_horizon,
            "quantitative_score": self.quantitative_score,
            "signal_notes": self.signal_notes,
        }


@dataclass(frozen=True)
class FundamentalEvidence:
    """Layer 2: Point-in-time verified financial fundamentals (UNAVAILABLE when absent locally)."""

    availability_status: FundamentalAvailability
    gap_reason: str | None
    latest_period: str | None
    published_at: str | None
    revenue_yoy_pct: float | None
    net_income_yoy_pct: float | None
    pe_ratio: float | None
    pbv_ratio: float | None
    dividend_yield_pct: float | None
    source_label: str | None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventDisclosureEvidence:
    """Layer 3: Strict PIT corporate disclosures & macro/fiscal context with alias resolution."""

    availability_status: EventAvailability
    events_count: int
    macro_context_count: int
    company_disclosure_count: int
    synthetic_excluded_count: int
    matched_aliases: list[str]
    positive_count: int
    negative_count: int
    mixed_neutral_count: int
    events: list[dict[str, Any]]
    gap_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiquidityExecutionFeasibility:
    """Layer 4: Execution realism & liquidity capacity (no zero coercion, no stale forward-fill)."""

    median_turnover_20s_tnd: Decimal | None
    median_traded_turnover_20s_tnd: Decimal | None
    median_volume_20s_shares: int | None
    trade_frequency_20s: float | None
    zero_volume_share_ratio_20s: float | None
    latest_session_volume_shares: int | None
    latest_session_turnover_tnd: Decimal | None
    participation_10pct_max_shares: int | None
    participation_10pct_max_tnd: Decimal | None
    executable_reference_price_tnd: Decimal | None
    last_verified_close_tnd: Decimal | None
    tick_size_tnd: Decimal | None
    tick_rule_status: str
    daily_collar_pct: Decimal
    collar_risk_flag: bool
    execution_status: ExecutionFeasibilityStatus
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "median_turnover_20s_tnd": str(self.median_turnover_20s_tnd)
            if self.median_turnover_20s_tnd is not None
            else None,
            "median_traded_turnover_20s_tnd": str(self.median_traded_turnover_20s_tnd)
            if self.median_traded_turnover_20s_tnd is not None
            else None,
            "median_volume_20s_shares": self.median_volume_20s_shares,
            "trade_frequency_20s": self.trade_frequency_20s,
            "zero_volume_share_ratio_20s": self.zero_volume_share_ratio_20s,
            "latest_session_volume_shares": self.latest_session_volume_shares,
            "latest_session_turnover_tnd": str(self.latest_session_turnover_tnd)
            if self.latest_session_turnover_tnd is not None
            else None,
            "participation_10pct_max_shares": self.participation_10pct_max_shares,
            "participation_10pct_max_tnd": str(self.participation_10pct_max_tnd)
            if self.participation_10pct_max_tnd is not None
            else None,
            "executable_reference_price_tnd": str(self.executable_reference_price_tnd)
            if self.executable_reference_price_tnd is not None
            else None,
            "last_verified_close_tnd": str(self.last_verified_close_tnd)
            if self.last_verified_close_tnd is not None
            else None,
            "tick_size_tnd": str(self.tick_size_tnd) if self.tick_size_tnd is not None else None,
            "tick_rule_status": self.tick_rule_status,
            "daily_collar_pct": str(self.daily_collar_pct),
            "collar_risk_flag": self.collar_risk_flag,
            "execution_status": self.execution_status,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class DataQualityFreshness:
    """Layer 5: Observation integrity, missingness, quote age, and 'H'/'B' bar audit."""

    last_verified_traded_date: date | None
    latest_observed_bar_date: date | None
    latest_bar_status: str | None
    total_open_sessions: int
    observed_bars: int
    traded_bars: int
    untraded_bars: int
    observation_coverage_ratio: float
    traded_coverage_ratio: float
    quote_age_open_sessions: int | None
    quote_age_calendar_days: int | None
    missing_open_sessions_60s: int
    missing_open_sessions_20s: int
    missing_open_session_dates_60s: list[str]
    trailing_untraded_sessions: int
    limit_reserved_bars_in_window: int
    limit_reserved_events: list[dict[str, Any]]
    has_unrecovered_limit_reserved_gap: bool
    freshness_tier: FreshnessTier

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_verified_traded_date": self.last_verified_traded_date.isoformat()
            if self.last_verified_traded_date is not None
            else None,
            "latest_observed_bar_date": self.latest_observed_bar_date.isoformat()
            if self.latest_observed_bar_date is not None
            else None,
            "latest_bar_status": self.latest_bar_status,
            "total_open_sessions": self.total_open_sessions,
            "observed_bars": self.observed_bars,
            "traded_bars": self.traded_bars,
            "untraded_bars": self.untraded_bars,
            "observation_coverage_ratio": self.observation_coverage_ratio,
            "traded_coverage_ratio": self.traded_coverage_ratio,
            "quote_age_open_sessions": self.quote_age_open_sessions,
            "quote_age_calendar_days": self.quote_age_calendar_days,
            "missing_open_sessions_60s": self.missing_open_sessions_60s,
            "missing_open_sessions_20s": self.missing_open_sessions_20s,
            "missing_open_session_dates_60s": self.missing_open_session_dates_60s,
            "trailing_untraded_sessions": self.trailing_untraded_sessions,
            "limit_reserved_bars_in_window": self.limit_reserved_bars_in_window,
            "limit_reserved_events": self.limit_reserved_events,
            "has_unrecovered_limit_reserved_gap": self.has_unrecovered_limit_reserved_gap,
            "freshness_tier": self.freshness_tier,
        }


@dataclass(frozen=True)
class CompetitionEligibilityStatus:
    """Layer 6: Competition membership & market segment status, separate from research."""

    in_challenge_universe: bool
    challenge_symbol: str | None
    order_entry_eligibility: str
    market_segment: str
    market_mode: str
    is_competition_permitted: bool
    restriction_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioRiskContext:
    """Layer 7: Held exposure, 10% single-stock cap headroom, sector & slippage trap risk."""

    held_shares: int
    held_value_tnd: Decimal
    held_weight_pct: Decimal
    max_single_stock_cap_pct: Decimal
    cap_headroom_tnd: Decimal
    cap_headroom_shares: int | None
    sector: str | None
    sector_exposure_pct: Decimal
    sector_concentration_warning: str | None
    execution_trap_risk: ExecutionTrapRisk

    def to_dict(self) -> dict[str, Any]:
        return {
            "held_shares": self.held_shares,
            "held_value_tnd": str(self.held_value_tnd),
            "held_weight_pct": str(self.held_weight_pct),
            "max_single_stock_cap_pct": str(self.max_single_stock_cap_pct),
            "cap_headroom_tnd": str(self.cap_headroom_tnd),
            "cap_headroom_shares": self.cap_headroom_shares,
            "sector": self.sector,
            "sector_exposure_pct": str(self.sector_exposure_pct),
            "sector_concentration_warning": self.sector_concentration_warning,
            "execution_trap_risk": self.execution_trap_risk,
        }


@dataclass(frozen=True)
class TradingEligibilityStatus:
    """Structured trading eligibility strictly separate from research_status."""

    status: TradingEligibilityCode
    challenge_order_eligible: bool
    underlying_research_status: ResearchTier
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchDecisionExplanation:
    """Structured plain-language explanation for human decision review."""

    why_interesting: list[str]
    why_uncertain: list[str]
    missing_data: list[str]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    is_tradable: bool
    execution_risk: str
    review_trigger: str
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SparseInstrumentResearchAssessment:
    """Complete 7-layer PIT research assessment for one instrument."""

    instrument_id: str
    symbol: str
    isin: str | None
    as_of_session: str
    model_version: str
    research_status: ResearchStatus
    trading_eligibility: TradingEligibilityStatus
    research_priority_score: float | None
    is_selected_candidate: bool
    candidate_selection_reason: str | None
    baseline_eligible: bool
    baseline_exclusion_reasons: list[str]
    quantitative_trend_evidence: QuantitativeTrendEvidence
    fundamental_evidence: FundamentalEvidence
    event_disclosure_evidence: EventDisclosureEvidence
    liquidity_execution_feasibility: LiquidityExecutionFeasibility
    data_quality_freshness: DataQualityFreshness
    competition_eligibility: CompetitionEligibilityStatus
    portfolio_risk: PortfolioRiskContext
    explanation: ResearchDecisionExplanation

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "isin": self.isin,
            "as_of_session": self.as_of_session,
            "model_version": self.model_version,
            "research_status": self.research_status,
            "trading_eligibility": self.trading_eligibility.to_dict(),
            "research_priority_score": self.research_priority_score,
            "is_selected_candidate": self.is_selected_candidate,
            "candidate_selection_reason": self.candidate_selection_reason,
            "baseline_eligible": self.baseline_eligible,
            "baseline_exclusion_reasons": self.baseline_exclusion_reasons,
            "quantitative_trend_evidence": self.quantitative_trend_evidence.to_dict(),
            "fundamental_evidence": self.fundamental_evidence.to_dict(),
            "event_disclosure_evidence": self.event_disclosure_evidence.to_dict(),
            "liquidity_execution_feasibility": self.liquidity_execution_feasibility.to_dict(),
            "data_quality_freshness": self.data_quality_freshness.to_dict(),
            "competition_eligibility": self.competition_eligibility.to_dict(),
            "portfolio_risk": self.portfolio_risk.to_dict(),
            "explanation": self.explanation.to_dict(),
        }


@dataclass(frozen=True)
class SparseMarketResearchReport:
    """Cross-market multi-layer research report at a fixed PIT cutoff."""

    as_of: str
    latest_open_session: str
    model_version: str
    config_sha256: str
    input_data_sha256: str
    limit_reserved_recovery_applied: bool
    total_instruments: int
    status_counts: dict[str, int]
    selected_candidate_ids: list[str]
    assessments: list[SparseInstrumentResearchAssessment]
    by_instrument: dict[str, SparseInstrumentResearchAssessment] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "latest_open_session": self.latest_open_session,
            "model_version": self.model_version,
            "config_sha256": self.config_sha256,
            "input_data_sha256": self.input_data_sha256,
            "limit_reserved_recovery_applied": self.limit_reserved_recovery_applied,
            "total_instruments": self.total_instruments,
            "status_counts": self.status_counts,
            "selected_candidate_ids": self.selected_candidate_ids,
            "assessments": [a.to_dict() for a in self.assessments],
        }


# ---------------------------------------------------------------------------
# Pure Layer Builders
# ---------------------------------------------------------------------------


def _exact_calendar_return_pct(
    pit_bars: Mapping[tuple[str, date], DailyBar],
    inst_id: str,
    start_date: date | None,
    end_date: date | None,
) -> float | None:
    if start_date is None or end_date is None:
        return None
    b_start = pit_bars.get((inst_id, start_date))
    b_end = pit_bars.get((inst_id, end_date))
    if (
        b_start is None
        or b_end is None
        or b_start.status != "traded"
        or b_end.status != "traded"
        or b_start.close <= 0
    ):
        return None
    return _round_float(float((b_end.close / b_start.close - Decimal(1)) * Decimal(100)), 4)


def _compute_quantitative_trend(
    inst_id: str,
    pit_bars: Mapping[tuple[str, date], DailyBar],
    inst_bars: Sequence[DailyBar],
    traded_bars: Sequence[DailyBar],
    open_sessions: Sequence[ExchangeSession],
    config: SparseResearchConfig,
) -> dict[str, Any]:
    """Compute raw multi-horizon metrics (first pass before cross-sectional benchmark)."""
    latest_date = open_sessions[-1].session_date
    latest_bar = pit_bars.get((inst_id, latest_date))

    w5 = (
        open_sessions[-(config.micro_lookback_sessions + 1) :]
        if len(open_sessions) >= config.micro_lookback_sessions + 1
        else []
    )
    w20 = (
        open_sessions[-(config.short_lookback_sessions + 1) :]
        if len(open_sessions) >= config.short_lookback_sessions + 1
        else []
    )
    w60 = (
        open_sessions[-(config.long_lookback_sessions + 1) :]
        if len(open_sessions) >= config.long_lookback_sessions + 1
        else []
    )

    mom5 = _exact_calendar_return_pct(
        pit_bars, inst_id, w5[0].session_date if w5 else None, latest_date
    )
    mom20 = _exact_calendar_return_pct(
        pit_bars, inst_id, w20[0].session_date if w20 else None, latest_date
    )
    mom60 = _exact_calendar_return_pct(
        pit_bars, inst_id, w60[0].session_date if w60 else None, latest_date
    )

    # Traded-to-traded observation metrics (never forward-fill untraded days)
    obs_ret: float | None = None
    obs_interval: int | None = None
    if len(traded_bars) >= 2:
        prev_t, last_t = traded_bars[-2], traded_bars[-1]
        if prev_t.close > 0:
            obs_ret = _round_float(float((last_t.close / prev_t.close - Decimal(1)) * 100), 4)
            obs_interval = sum(
                1
                for s in open_sessions
                if prev_t.session_date < s.session_date <= last_t.session_date
            )

    quote_age = (
        sum(1 for s in open_sessions if s.session_date > traded_bars[-1].session_date)
        if traded_bars
        else None
    )

    trailing_traded_5_ret: float | None = None
    if (
        len(traded_bars) >= 2
        and quote_age is not None
        and quote_age <= config.partial_max_quote_age_sessions
    ):
        anchor_idx = max(0, len(traded_bars) - 5)
        t_start = traded_bars[anchor_idx]
        t_end = traded_bars[-1]
        if t_start.close > 0 and t_start.session_date != t_end.session_date:
            trailing_traded_5_ret = _round_float(
                float((t_end.close / t_start.close - Decimal(1)) * 100), 4
            )

    latest_day_ret: float | None = None
    if latest_bar is not None and latest_bar.status == "traded":
        prior_traded = [b for b in traded_bars if b.session_date < latest_date]
        if prior_traded:
            prev_close = prior_traded[-1].close
            gap_sessions = sum(
                1
                for s in open_sessions
                if prior_traded[-1].session_date < s.session_date <= latest_date
            )
            if prev_close > 0 and gap_sessions <= config.partial_max_quote_age_sessions:
                latest_day_ret = _round_float(
                    float((latest_bar.close / prev_close - Decimal(1)) * 100), 4
                )

    # Volatility strictly from consecutive traded bars inside the short 21-session window
    vol_window = (
        open_sessions[-(config.short_lookback_sessions + 1) :]
        if len(open_sessions) >= config.short_lookback_sessions + 1
        else open_sessions
    )
    vol_dates = {s.session_date for s in vol_window}
    traded_in_short = [b for b in traded_bars if b.session_date in vol_dates]
    vol20: float | None = None
    if len(traded_in_short) >= 3:
        steps = [
            float((traded_in_short[i].close / traded_in_short[i - 1].close - Decimal(1)) * 100)
            for i in range(1, len(traded_in_short))
            if traded_in_short[i - 1].close > 0
        ]
        if len(steps) >= 2:
            mean_s = sum(steps) / len(steps)
            var_s = sum((r - mean_s) ** 2 for r in steps) / (len(steps) - 1)
            vol20 = _round_float(max(1e-6, var_s**0.5), 4)

    # Volume / turnover awakening against PRIOR baseline [t-20 .. t-1]
    prior_end = len(open_sessions) - 1
    prior_start = max(0, prior_end - config.awakening_baseline_sessions)
    baseline_dates = {s.session_date for s in open_sessions[prior_start:prior_end]}
    baseline_bars = [b for b in inst_bars if b.session_date in baseline_dates]

    latest_turnover = (
        latest_bar.turnover_tnd
        if latest_bar is not None and latest_bar.status == "traded"
        else None
    )
    trailing_med_turnover: Decimal | None = None
    turnover_ratio: float | None = None
    volume_ratio: float | None = None
    awakening_detected = False
    notes: list[str] = []

    if len(baseline_bars) >= config.min_awakening_baseline_bars:
        trailing_med_turnover = _money_decimal(median([b.turnover_tnd for b in baseline_bars]))
        trailing_med_vol = float(median([b.volume_shares for b in baseline_bars]))
        if latest_bar is not None and latest_bar.status == "traded":
            if trailing_med_turnover > 0:
                turnover_ratio = _round_float(
                    float(latest_bar.turnover_tnd / trailing_med_turnover), 2
                )
            if trailing_med_vol > 0:
                volume_ratio = _round_float(latest_bar.volume_shares / trailing_med_vol, 2)

            day_ret_ok = (
                latest_day_ret is None or latest_day_ret >= config.awakening_min_day_return_pct
            )
            notional_ok = latest_bar.turnover_tnd >= config.awakening_min_turnover_tnd
            ratio_ok = (
                turnover_ratio is not None
                and turnover_ratio >= config.awakening_turnover_ratio_threshold
            ) or (trailing_med_turnover == Decimal("0.000"))
            if day_ret_ok and notional_ok and ratio_ok:
                awakening_detected = True
                if turnover_ratio is None:
                    notes.append(
                        f"Awakening from zero-median baseline: traded {latest_bar.turnover_tnd} TND today."
                    )
                else:
                    notes.append(
                        f"Turnover awakening detected: {turnover_ratio:.2f}x trailing 20s median "
                        f"({latest_bar.turnover_tnd} TND vs {trailing_med_turnover} TND)."
                    )

    is_partial = mom20 is None or mom60 is None or vol20 is None
    if mom20 is None:
        notes.append("20-session exact calendar return unavailable (missing or untraded endpoint).")
    if mom60 is None:
        notes.append("60-session exact calendar return unavailable (missing or untraded endpoint).")

    return {
        "momentum_5s_pct": mom5,
        "momentum_20s_pct": mom20,
        "momentum_60s_pct": mom60,
        "observed_trade_return_pct": obs_ret,
        "observed_trade_interval_sessions": obs_interval,
        "trailing_traded_5_return_pct": trailing_traded_5_ret,
        "latest_day_return_pct": latest_day_ret,
        "volatility_20s_pct": vol20,
        "latest_turnover_tnd": latest_turnover,
        "trailing_median_turnover_20s_tnd": trailing_med_turnover,
        "turnover_awakening_ratio": turnover_ratio,
        "volume_awakening_ratio": volume_ratio,
        "awakening_detected": awakening_detected,
        "is_partial_horizon": is_partial,
        "quote_age": quote_age,
        "notes": notes,
    }


def _compute_fundamental_evidence(
    aliases: frozenset[str],
    records: Sequence[FundamentalSnapshotRecord],
    cutoff: datetime,
) -> FundamentalEvidence:
    pit_matches = [
        r
        for r in records
        if _norm_token(r.instrument_id) in aliases
        and r.published_at.tzinfo is not None
        and r.ingested_at.tzinfo is not None
        and r.published_at <= cutoff
        and r.ingested_at <= cutoff
    ]
    if not pit_matches:
        return FundamentalEvidence(
            availability_status="UNAVAILABLE",
            gap_reason=(
                "No verified point-in-time balance sheet, earnings, or corporate-action "
                "fundamental table ingested locally as of cutoff."
            ),
            latest_period=None,
            published_at=None,
            revenue_yoy_pct=None,
            net_income_yoy_pct=None,
            pe_ratio=None,
            pbv_ratio=None,
            dividend_yield_pct=None,
            source_label=None,
            notes=[
                "Snapshot valuation fields without publication timestamps are excluded by PIT policy."
            ],
        )

    latest = max(pit_matches, key=lambda r: (r.published_at, r.period_label))
    populated = sum(
        1
        for v in (
            latest.revenue_yoy_pct,
            latest.net_income_yoy_pct,
            latest.pe_ratio,
            latest.pbv_ratio,
            latest.dividend_yield_pct,
        )
        if v is not None
    )
    status: FundamentalAvailability = "AVAILABLE" if populated >= 3 else "PARTIAL"
    return FundamentalEvidence(
        availability_status=status,
        gap_reason=None if status == "AVAILABLE" else "Only partial fundamental fields present.",
        latest_period=latest.period_label,
        published_at=latest.published_at.isoformat(),
        revenue_yoy_pct=latest.revenue_yoy_pct,
        net_income_yoy_pct=latest.net_income_yoy_pct,
        pe_ratio=latest.pe_ratio,
        pbv_ratio=latest.pbv_ratio,
        dividend_yield_pct=latest.dividend_yield_pct,
        source_label=latest.source_label,
        notes=[latest.notes] if latest.notes else [],
    )


def _compute_event_evidence(
    inst_id: str,
    aliases: frozenset[str],
    document_chunks: Sequence[DocumentChunk],
    cutoff: datetime,
) -> EventDisclosureEvidence:
    macro_items = get_verified_macro_intelligence(
        cutoff=cutoff,
        instrument_id=inst_id,
        include_aliases=True,
        extra_aliases=tuple(sorted(aliases)),
    )
    events_out: list[dict[str, Any]] = []
    matched_aliases_set: set[str] = set()
    macro_cnt = 0
    comp_cnt = 0
    pos_cnt = 0
    neg_cnt = 0
    mix_cnt = 0

    for ev in macro_items:
        ev_tokens = {token.upper() for token in (*ev.affected_instrument_ids, *ev.affected_symbols)}
        ev_tokens |= {_norm_token(token) for token in ev_tokens}
        matched_aliases_set.update(aliases & ev_tokens)
        is_company = ev.category == "CORPORATE_EARNINGS"
        if is_company:
            comp_cnt += 1
        else:
            macro_cnt += 1
        if ev.polarity == "POSITIVE":
            pos_cnt += 1
        elif ev.polarity == "NEGATIVE":
            neg_cnt += 1
        else:
            mix_cnt += 1
        events_out.append(
            {
                "event_id": ev.event_id,
                "source_type": "official_corporate_disclosure"
                if is_company
                else "official_macro_policy",
                "category": ev.category,
                "title": ev.title,
                "published_at": ev.published_at,
                "source_label": ev.source_label,
                "polarity": ev.polarity,
                "uncertainty_rating": ev.uncertainty_rating,
                "impact_pathway": ev.impact_pathway,
                "contradicting_evidence": ev.contradicting_evidence,
            }
        )

    synthetic_excluded = 0
    seen_chunk_ids: set[str] = set()
    for chunk in document_chunks:
        if chunk.chunk_id in seen_chunk_ids:
            continue
        if "synthetic" in chunk.source_document_id.lower():
            synthetic_excluded += 1
            continue
        if chunk.published_at is None:
            continue
        try:
            pub_dt = aware_timestamp(chunk.published_at)
            ing_dt = aware_timestamp(chunk.ingested_at)
        except ValueError:
            continue
        if pub_dt > cutoff or ing_dt > cutoff:
            continue
        chunk_tokens = {t.upper() for t in chunk.instrument_ids} | {
            _norm_token(t) for t in chunk.instrument_ids
        }
        overlap = aliases & chunk_tokens
        if not overlap:
            continue
        seen_chunk_ids.add(chunk.chunk_id)
        matched_aliases_set.update(overlap)
        comp_cnt += 1
        mix_cnt += 1
        events_out.append(
            {
                "event_id": chunk.chunk_id,
                "source_type": "local_document_chunk",
                "category": "COMPANY_DISCLOSURE",
                "title": f"{chunk.source_document_id} ({chunk.section_locator})",
                "published_at": chunk.published_at,
                "source_label": chunk.source_document_id,
                "polarity": "NEUTRAL",
                "uncertainty_rating": "MODERATE",
                "impact_pathway": chunk.chunk_text[:240],
                "contradicting_evidence": None,
            }
        )

    events_out.sort(key=lambda e: str(e["published_at"]), reverse=True)
    total = len(events_out)
    if comp_cnt > 0:
        avail: EventAvailability = "EVENTS_FOUND"
        gap: str | None = None
    elif macro_cnt > 0:
        avail = "MACRO_CONTEXT_ONLY"
        gap = (
            "No company-level CMF/BVMT filing chunks present locally; "
            "only macro/fiscal context matched via canonical aliases."
        )
    else:
        avail = "NO_VERIFIED_EVENTS"
        gap = "No verified local disclosures or matching macro context recorded as of cutoff."

    return EventDisclosureEvidence(
        availability_status=avail,
        events_count=total,
        macro_context_count=macro_cnt,
        company_disclosure_count=comp_cnt,
        synthetic_excluded_count=synthetic_excluded,
        matched_aliases=sorted(matched_aliases_set),
        positive_count=pos_cnt,
        negative_count=neg_cnt,
        mixed_neutral_count=mix_cnt,
        events=events_out,
        gap_reason=gap,
    )


def _compute_liquidity_and_freshness(
    inst_id: str,
    pit_bars: Mapping[tuple[str, date], DailyBar],
    inst_bars: Sequence[DailyBar],
    traded_bars: Sequence[DailyBar],
    untraded_bars: Sequence[DailyBar],
    open_sessions: Sequence[ExchangeSession],
    limit_reserved_events: Sequence[LimitReservedBarMeta],
    hb_bar_keys: frozenset[tuple[str, date]],
    is_comp_permitted: bool,
    config: SparseResearchConfig,
) -> tuple[LiquidityExecutionFeasibility, DataQualityFreshness]:
    latest_session = open_sessions[-1]
    latest_date = latest_session.session_date
    total_sessions = len(open_sessions)

    w20_all = (
        open_sessions[-(config.short_lookback_sessions + 1) :]
        if total_sessions >= config.short_lookback_sessions + 1
        else open_sessions
    )
    recent_w20 = w20_all[1:] if len(w20_all) > 1 else w20_all
    recent_dates_20 = {s.session_date for s in recent_w20}

    w60_all = (
        open_sessions[-(config.long_lookback_sessions + 1) :]
        if total_sessions >= config.long_lookback_sessions + 1
        else open_sessions
    )
    dates_60 = {s.session_date for s in w60_all}

    inst_bar_dates = {b.session_date for b in inst_bars}
    missing_60_dates = sorted(d.isoformat() for d in dates_60 if d not in inst_bar_dates)
    missing_20_count = sum(1 for d in recent_dates_20 if d not in inst_bar_dates)

    latest_bar = pit_bars.get((inst_id, latest_date))
    last_traded = traded_bars[-1] if traded_bars else None
    latest_observed = inst_bars[-1] if inst_bars else None

    trailing_untraded = 0
    for b in reversed(inst_bars):
        if b.status in {"no_trade", "untraded"}:
            trailing_untraded += 1
        else:
            break

    quote_age_sessions = (
        sum(1 for s in open_sessions if s.session_date > last_traded.session_date)
        if last_traded is not None
        else None
    )
    quote_age_days = (
        (latest_date - last_traded.session_date).days if last_traded is not None else None
    )

    pit_hb_events = [e for e in limit_reserved_events if e.session_date <= latest_date]
    has_unrecovered_hb = any(
        (inst_id, e.session_date) not in hb_bar_keys and (inst_id, e.session_date) not in pit_bars
        for e in pit_hb_events
    )

    if last_traded is None:
        freshness_tier: FreshnessTier = "NEVER_TRADED"
    elif latest_bar is None:
        freshness_tier = "MISSING_RECENT_BAR"
    elif (
        quote_age_sessions is not None and quote_age_sessions <= config.full_max_quote_age_sessions
    ):
        freshness_tier = "FRESH"
    elif (
        quote_age_sessions is not None
        and quote_age_sessions <= config.partial_max_quote_age_sessions
    ):
        freshness_tier = "RECENT"
    else:
        freshness_tier = "STALE"

    freshness = DataQualityFreshness(
        last_verified_traded_date=last_traded.session_date if last_traded else None,
        latest_observed_bar_date=latest_observed.session_date if latest_observed else None,
        latest_bar_status=latest_observed.status if latest_observed else None,
        total_open_sessions=total_sessions,
        observed_bars=len(inst_bars),
        traded_bars=len(traded_bars),
        untraded_bars=len(untraded_bars),
        observation_coverage_ratio=_round_float(len(inst_bars) / max(1, total_sessions), 4),
        traded_coverage_ratio=_round_float(len(traded_bars) / max(1, total_sessions), 4),
        quote_age_open_sessions=quote_age_sessions,
        quote_age_calendar_days=quote_age_days,
        missing_open_sessions_60s=len(missing_60_dates),
        missing_open_sessions_20s=missing_20_count,
        missing_open_session_dates_60s=missing_60_dates,
        trailing_untraded_sessions=trailing_untraded,
        limit_reserved_bars_in_window=len(pit_hb_events),
        limit_reserved_events=[e.to_dict() for e in pit_hb_events],
        has_unrecovered_limit_reserved_gap=has_unrecovered_hb,
        freshness_tier=freshness_tier,
    )

    # Liquidity & execution realism -- NEVER coerce missing to 0.000, NEVER forward-fill stale close
    recent_bars_20 = [b for b in inst_bars if b.session_date in recent_dates_20]
    traded_recent_20 = [b for b in recent_bars_20 if b.status == "traded"]

    med_turnover_20: Decimal | None = None
    med_traded_turnover_20: Decimal | None = None
    med_vol_20: int | None = None
    trade_freq_20: float | None = None
    zero_vol_ratio_20: float | None = None

    if recent_bars_20:
        med_turnover_20 = _money_decimal(median([b.turnover_tnd for b in recent_bars_20]))
        med_vol_20 = int(median([b.volume_shares for b in recent_bars_20]))
        trade_freq_20 = _round_float(len(traded_recent_20) / max(1, len(recent_w20)), 4)
        untraded_cnt_20 = sum(1 for b in recent_bars_20 if b.volume_shares == 0)
        zero_vol_ratio_20 = _round_float(untraded_cnt_20 / len(recent_bars_20), 4)
    if traded_recent_20:
        med_traded_turnover_20 = _money_decimal(median([b.turnover_tnd for b in traded_recent_20]))

    executable_ref_price = (
        latest_bar.close
        if latest_bar is not None and latest_bar.status == "traded" and latest_bar.close > 0
        else None
    )
    last_verified_close = last_traded.close if last_traded is not None else None

    part_max_tnd: Decimal | None = None
    part_max_shares: int | None = None
    if med_turnover_20 is not None:
        part_max_tnd = quantize_tnd(med_turnover_20 * config.liquidity_participation_cap)
        price_for_shares = executable_ref_price or last_verified_close
        if price_for_shares is not None and price_for_shares > 0:
            part_max_shares = int(part_max_tnd // price_for_shares)

    indicative_tick = Decimal("0.010")
    collar_flag = (
        latest_bar is not None
        and latest_bar.status == "traded"
        and (latest_bar.open == latest_bar.high or latest_bar.open == latest_bar.low)
        and latest_bar.high == latest_bar.low
    ) or has_unrecovered_hb

    liq_notes: list[str] = []
    if executable_ref_price is None and last_verified_close is not None:
        liq_notes.append(
            f"Stale/untraded on {latest_date.isoformat()}: executable_reference_price_tnd kept None "
            f"(last verified traded close {last_verified_close} TND on {last_traded.session_date if last_traded else 'N/A'})."
        )
    if med_turnover_20 is None:
        liq_notes.append("No observations in trailing 20-session window; median turnover is None.")

    if not is_comp_permitted:
        exec_status: ExecutionFeasibilityStatus = "MARKET_RESTRICTED"
    elif not recent_bars_20 or last_traded is None:
        exec_status = "INSUFFICIENT_OBSERVATIONS"
    elif executable_ref_price is None or (
        quote_age_sessions is not None and quote_age_sessions > config.full_max_quote_age_sessions
    ):
        exec_status = "STALE_OR_UNTRADED"
    elif (
        med_turnover_20 is not None
        and med_turnover_20 >= config.liquidity_feasible_median_turnover_tnd
        and part_max_tnd is not None
        and part_max_tnd >= config.minimum_order_notional_tnd
    ):
        exec_status = "FEASIBLE"
    else:
        exec_status = "LIQUIDITY_LIMITED"

    liquidity = LiquidityExecutionFeasibility(
        median_turnover_20s_tnd=med_turnover_20,
        median_traded_turnover_20s_tnd=med_traded_turnover_20,
        median_volume_20s_shares=med_vol_20,
        trade_frequency_20s=trade_freq_20,
        zero_volume_share_ratio_20s=zero_vol_ratio_20,
        latest_session_volume_shares=latest_bar.volume_shares if latest_bar else None,
        latest_session_turnover_tnd=latest_bar.turnover_tnd if latest_bar else None,
        participation_10pct_max_shares=part_max_shares,
        participation_10pct_max_tnd=part_max_tnd,
        executable_reference_price_tnd=executable_ref_price,
        last_verified_close_tnd=last_verified_close,
        tick_size_tnd=indicative_tick,
        tick_rule_status="UNVERIFIED_IN_COMPETITION_CONFIG_INDICATIVE_0.010_TND",
        daily_collar_pct=config.daily_collar_static_pct,
        collar_risk_flag=collar_flag,
        execution_status=exec_status,
        notes=liq_notes,
    )
    return liquidity, freshness


def _compute_portfolio_risk(
    inst_id: str,
    symbol: str,
    aliases: frozenset[str],
    held_positions: Mapping[str, Any],
    pending_orders: Sequence[PendingOrderReservation],
    portfolio_equity_tnd: Decimal,
    sector: str | None,
    sector_exposures_tnd: Mapping[str, Decimal],
    liquidity: LiquidityExecutionFeasibility,
    freshness: DataQualityFreshness,
    config: SparseResearchConfig,
) -> PortfolioRiskContext:
    matched_pos: Any = None
    for candidate_key in (inst_id, symbol, *sorted(aliases)):
        if candidate_key in held_positions:
            matched_pos = held_positions[candidate_key]
            break

    held_shares = 0
    avg_cost = Decimal("0.000")
    latest_px = liquidity.executable_reference_price_tnd or liquidity.last_verified_close_tnd
    if matched_pos is not None:
        if isinstance(matched_pos, Mapping):
            held_shares = int(matched_pos.get("total_shares", matched_pos.get("quantity", 0)) or 0)
            avg_cost = quantize_tnd(
                matched_pos.get("average_cost_tnd", matched_pos.get("acquisition_price_tnd", "0"))
            )
            if latest_px is None and matched_pos.get("latest_price_tnd") is not None:
                latest_px = quantize_tnd(matched_pos["latest_price_tnd"])
        else:
            held_shares = int(
                getattr(matched_pos, "total_shares", getattr(matched_pos, "quantity", 0)) or 0
            )
            avg_cost = quantize_tnd(
                getattr(
                    matched_pos,
                    "average_cost_tnd",
                    getattr(matched_pos, "acquisition_price_tnd", "0"),
                )
            )
            if latest_px is None and getattr(matched_pos, "latest_price_tnd", None) is not None:
                latest_px = quantize_tnd(matched_pos.latest_price_tnd)

    valuation_px = latest_px if latest_px is not None and latest_px > 0 else avg_cost
    held_value = quantize_tnd(Decimal(held_shares) * valuation_px)
    held_weight_pct = (
        quantize_tnd(held_value / portfolio_equity_tnd * Decimal("100"))
        if portfolio_equity_tnd > 0
        else Decimal("0.000")
    )

    reserved_buy = Decimal("0.000")
    for po in pending_orders:
        if po.side.upper() == "BUY" and (
            _norm_token(po.instrument_id) in aliases or po.instrument_id == inst_id
        ):
            reserved_buy += po.reserved_cash_tnd

    max_cap_tnd = quantize_tnd(portfolio_equity_tnd * config.max_single_stock_weight)
    headroom_tnd = max(Decimal("0.000"), quantize_tnd(max_cap_tnd - held_value - reserved_buy))
    headroom_shares = int(headroom_tnd // valuation_px) if valuation_px > 0 else None

    sec_val = sector_exposures_tnd.get(sector or "", Decimal("0.000"))
    sec_pct = (
        quantize_tnd(sec_val / portfolio_equity_tnd * Decimal("100"))
        if portfolio_equity_tnd > 0
        else Decimal("0.000")
    )
    sec_warn = (
        f"Sector '{sector}' exposure already at {sec_pct}% of equity (>= 25% threshold)."
        if sec_pct >= Decimal("25.000")
        else None
    )

    if freshness.freshness_tier in {"NEVER_TRADED", "STALE"} or (
        liquidity.zero_volume_share_ratio_20s is not None
        and liquidity.zero_volume_share_ratio_20s >= 0.70
    ):
        trap_risk: ExecutionTrapRisk = "EXTREME"
    elif (
        liquidity.collar_risk_flag
        or liquidity.execution_status == "LIQUIDITY_LIMITED"
        or (
            liquidity.participation_10pct_max_tnd is not None
            and liquidity.participation_10pct_max_tnd < config.minimum_order_notional_tnd
        )
    ):
        trap_risk = "HIGH"
    elif (
        liquidity.median_turnover_20s_tnd is not None
        and liquidity.median_turnover_20s_tnd < Decimal("20000.000")
    ) or freshness.missing_open_sessions_60s > 0:
        trap_risk = "MODERATE"
    else:
        trap_risk = "LOW"

    return PortfolioRiskContext(
        held_shares=held_shares,
        held_value_tnd=held_value,
        held_weight_pct=held_weight_pct,
        max_single_stock_cap_pct=quantize_tnd(config.max_single_stock_weight * Decimal("100")),
        cap_headroom_tnd=headroom_tnd,
        cap_headroom_shares=headroom_shares,
        sector=sector,
        sector_exposure_pct=sec_pct,
        sector_concentration_warning=sec_warn,
        execution_trap_risk=trap_risk,
    )


def _compute_quantitative_score(
    raw: Mapping[str, Any],
    rel_strength_20s: float | None,
    liquidity: LiquidityExecutionFeasibility,
    events: EventDisclosureEvidence,
    config: SparseResearchConfig,
) -> float | None:
    """Compute bounded transparent research score (None if insufficient/stale)."""
    quote_age: int | None = raw["quote_age"]
    if quote_age is None or quote_age > config.partial_max_quote_age_sessions:
        return None

    m20: float | None = raw["momentum_20s_pct"]
    m60: float | None = raw["momentum_60s_pct"]
    m5: float | None = raw["momentum_5s_pct"]
    v20: float | None = raw["volatility_20s_pct"]
    t5: float | None = raw["trailing_traded_5_return_pct"]
    obs_ret: float | None = raw["observed_trade_return_pct"]
    awakening: bool = bool(raw["awakening_detected"])

    score = 0.0
    if not raw["is_partial_horizon"] and m20 is not None and m60 is not None and v20 is not None:
        denom = max(v20, 0.5)
        risk_adj = 0.5 * (m20 / denom) + 0.5 * (m60 / denom)
        score += risk_adj * 4.0
        if m5 is not None:
            score += 0.25 * m5
    else:
        proxy = m20 if m20 is not None else (t5 if t5 is not None else obs_ret)
        if proxy is None:
            return None
        denom = max(v20 if v20 is not None else 2.0, 1.0)
        score += (proxy / denom) * 4.0 * config.partial_horizon_score_multiplier

    if rel_strength_20s is not None:
        score += 0.15 * rel_strength_20s
    if awakening:
        score += config.awakening_score_bonus
    if events.positive_count > events.negative_count and events.company_disclosure_count > 0:
        score += config.event_catalyst_score_bonus
    if (
        liquidity.zero_volume_share_ratio_20s is not None
        and liquidity.zero_volume_share_ratio_20s >= config.sparse_zero_vol_penalty_threshold
        and not awakening
    ):
        score -= config.sparse_zero_vol_penalty

    return _round_float(max(-50.0, min(100.0, score)), 4)


def _classify_statuses(
    is_comp_permitted: bool,
    is_suspended: bool,
    chal_rec: ChallengeInstrumentRecord | None,
    active_rec: InstrumentRecord | None,
    freshness: DataQualityFreshness,
    liquidity: LiquidityExecutionFeasibility,
    trend: QuantitativeTrendEvidence,
    fundamental: FundamentalEvidence,
    events: EventDisclosureEvidence,
    config: SparseResearchConfig,
) -> tuple[ResearchStatus, TradingEligibilityStatus]:
    quote_age = freshness.quote_age_open_sessions
    trade_freq = liquidity.trade_frequency_20s

    has_full_history = (
        freshness.missing_open_sessions_60s <= config.full_max_missing_in_60s
        and freshness.missing_open_sessions_20s == 0
        and quote_age is not None
        and quote_age <= config.full_max_quote_age_sessions
        and trade_freq is not None
        and trade_freq >= config.full_min_trade_freq_20s
        and trend.momentum_20s_pct is not None
        and trend.momentum_60s_pct is not None
    )
    has_partial_history = (
        freshness.traded_bars >= config.min_partial_traded_bars
        and quote_age is not None
        and quote_age <= config.partial_max_quote_age_sessions
    )
    has_event_or_fund = events.events_count > 0 or fundamental.availability_status != "UNAVAILABLE"

    if has_full_history:
        underlying: ResearchTier = "FULL_RESEARCH_AVAILABLE"
    elif has_partial_history:
        underlying = "PARTIAL_RESEARCH_AVAILABLE"
    elif has_event_or_fund:
        underlying = "EVENT_RESEARCH_AVAILABLE"
    else:
        underlying = "INSUFFICIENT_EVIDENCE"

    research_status: ResearchStatus = underlying if is_comp_permitted else "RESTRICTED_FOR_TRADING"

    reasons: list[str] = []
    if is_suspended:
        t_code: TradingEligibilityCode = "SUSPENDED_AT_CUTOFF"
        reasons.append("Official suspension active on decision session.")
    elif not is_comp_permitted or active_rec is None:
        t_code = "MARKET_SEGMENT_RESTRICTED"
        seg = active_rec.market_segment if active_rec is not None else "unlisted"
        reasons.append(f"Market segment '{seg}' or eligibility flag restricts competition trading.")
    elif chal_rec is None:
        t_code = "RESEARCH_ONLY_NOT_IN_CHALLENGE"
        reasons.append(
            "Permitted principal security on BVMT, but absent from the 42-instrument Tunis Bourse Challenge list."
        )
    elif liquidity.executable_reference_price_tnd is None:
        t_code = "UNTRADED_OR_STALE_EXECUTION_RISK"
        reasons.append(
            "Latest session was untraded or missing; no current executable reference price."
        )
    else:
        t_code = "CHALLENGE_ORDER_ELIGIBLE"
        reasons.append(
            f"Confirmed 42-Challenge security ({chal_rec.challenge_symbol}) with fresh traded bar."
        )

    return research_status, TradingEligibilityStatus(
        status=t_code,
        challenge_order_eligible=(t_code == "CHALLENGE_ORDER_ELIGIBLE"),
        underlying_research_status=underlying,
        reasons=reasons,
    )


def _evaluate_candidate_selection(
    research_status: ResearchStatus,
    trading_elig: TradingEligibilityStatus,
    trend: QuantitativeTrendEvidence,
    liquidity: LiquidityExecutionFeasibility,
    freshness: DataQualityFreshness,
    events: EventDisclosureEvidence,
    config: SparseResearchConfig,
) -> tuple[bool, str | None, float | None]:
    """Deterministic PIT candidate eligibility rule (strictly research signal, NOT auto-order)."""
    if research_status in {"INSUFFICIENT_EVIDENCE", "RESTRICTED_FOR_TRADING"}:
        return False, None, trend.quantitative_score
    if liquidity.executable_reference_price_tnd is None:
        return False, None, trend.quantitative_score

    q_score = trend.quantitative_score
    priority = q_score
    if priority is not None and not trading_elig.challenge_order_eligible:
        # Still scorable for research, slightly prioritized below direct challenge members in tiebreaks
        priority = _round_float(priority - 0.01, 4)

    # Rule A: Unusual volume/turnover awakening on positive price action
    if (
        config.candidate_allow_awakening_bypass
        and trend.awakening_detected
        and freshness.quote_age_open_sessions == 0
    ):
        return (
            True,
            f"volume_awakening ({trend.turnover_awakening_ratio or 'zero-baseline'}x trailing median turnover)",
            priority if priority is not None else 1.0,
        )

    # Rule B: Positive risk-adjusted multi-horizon trend with tradable liquidity
    if (
        q_score is not None
        and q_score >= config.candidate_min_quant_score
        and liquidity.median_turnover_20s_tnd is not None
        and liquidity.median_turnover_20s_tnd >= config.liquidity_marginal_median_turnover_tnd
    ):
        return True, f"risk_adjusted_trend (quant_score={q_score:.2f})", priority

    # Rule C: Verified company disclosure positive catalyst with active tradable liquidity
    if (
        config.candidate_allow_event_catalyst
        and events.company_disclosure_count > 0
        and events.positive_count > events.negative_count
        and liquidity.median_turnover_20s_tnd is not None
        and liquidity.median_turnover_20s_tnd >= config.liquidity_marginal_median_turnover_tnd
        and (q_score is None or q_score >= 0.0)
    ):
        return (
            True,
            "positive_company_disclosure_catalyst",
            priority if priority is not None else 2.5,
        )

    return False, None, priority


def _build_explanation(
    symbol: str,
    research_status: ResearchStatus,
    trading_elig: TradingEligibilityStatus,
    trend: QuantitativeTrendEvidence,
    fundamental: FundamentalEvidence,
    events: EventDisclosureEvidence,
    liquidity: LiquidityExecutionFeasibility,
    freshness: DataQualityFreshness,
    portfolio_risk: PortfolioRiskContext,
) -> ResearchDecisionExplanation:
    why_interesting: list[str] = []
    why_uncertain: list[str] = []
    missing_data: list[str] = []
    supporting: list[str] = []
    contradicting: list[str] = []

    if trend.awakening_detected:
        ratio_txt = (
            f"{trend.turnover_awakening_ratio:.2f}x"
            if trend.turnover_awakening_ratio is not None
            else "from zero median"
        )
        why_interesting.append(
            f"Unusual volume/turnover awakening ({ratio_txt} trailing median, {trend.latest_turnover_tnd} TND today)."
        )
        supporting.append(why_interesting[-1])
    if trend.momentum_20s_pct is not None:
        if trend.momentum_20s_pct > 0:
            why_interesting.append(f"Positive 20-session return ({trend.momentum_20s_pct:+.2f}%).")
            supporting.append(why_interesting[-1])
        else:
            contradicting.append(f"Negative 20-session return ({trend.momentum_20s_pct:+.2f}%).")
    if trend.momentum_60s_pct is not None:
        if trend.momentum_60s_pct > 0:
            supporting.append(f"Positive 60-session trend ({trend.momentum_60s_pct:+.2f}%).")
        else:
            contradicting.append(f"Negative 60-session trend ({trend.momentum_60s_pct:+.2f}%).")
    if trend.trailing_traded_5_return_pct is not None and trend.is_partial_horizon:
        why_interesting.append(
            f"Trailing 5-traded-bar proxy return is {trend.trailing_traded_5_return_pct:+.2f}%."
        )
    if events.events_count > 0:
        first_ev = events.events[0]
        note = f"{events.events_count} PIT event(s) matched (latest: {first_ev['title']})."
        why_interesting.append(note)
        supporting.append(note)
    if not why_interesting:
        why_interesting.append(
            f"Monitored under '{research_status}' for market completeness without active trend trigger."
        )

    if freshness.missing_open_sessions_60s > 0:
        msg = (
            f"{freshness.missing_open_sessions_60s} missing open session(s) in trailing 60-session window "
            f"({', '.join(freshness.missing_open_session_dates_60s[:5])})."
        )
        why_uncertain.append(msg)
        missing_data.append(msg)
    if freshness.has_unrecovered_limit_reserved_gap:
        msg = f"{freshness.limit_reserved_bars_in_window} limit-reserved ('H'/'B') bar(s) rejected by strict OHLC bounds."
        why_uncertain.append(msg)
        missing_data.append(msg)
    if fundamental.availability_status == "UNAVAILABLE":
        missing_data.append(fundamental.gap_reason or "Local PIT fundamental tables unavailable.")
        why_uncertain.append("No verified PIT earnings or valuation multiples ingested locally.")
    if events.company_disclosure_count == 0:
        missing_data.append("No company-level CMF/BVMT PDF disclosure chunks ingested locally.")
    if liquidity.trade_frequency_20s is not None and liquidity.trade_frequency_20s < 0.75:
        contradicting.append(
            f"Sparse trading regularity: traded on {liquidity.trade_frequency_20s * 100:.0f}% of trailing 20 sessions."
        )
    if (
        liquidity.median_turnover_20s_tnd is not None
        and liquidity.median_turnover_20s_tnd < Decimal("5000.000")
    ):
        contradicting.append(
            f"Low trailing 20s median turnover ({liquidity.median_turnover_20s_tnd} TND < 5,000 TND feasible hurdle)."
        )
    if liquidity.executable_reference_price_tnd is None:
        why_uncertain.append(
            "Latest session was untraded or missing; executable price cannot be verified."
        )
        contradicting.append("Zero current-session executable price.")
    if portfolio_risk.held_weight_pct >= portfolio_risk.max_single_stock_cap_pct:
        contradicting.append(
            f"Held weight ({portfolio_risk.held_weight_pct}%) already at/above 10% single-stock cap."
        )
    if not why_uncertain:
        why_uncertain.append(
            "Past price regularity and macro context remain subject to 1.00% round-trip fee drag and BVMT ±3% collars."
        )

    exec_risk = (
        f"Execution trap risk is {portfolio_risk.execution_trap_risk}: "
        f"10% participation capacity = {liquidity.participation_10pct_max_tnd or 'None'} TND "
        f"({liquidity.participation_10pct_max_shares if liquidity.participation_10pct_max_shares is not None else 'None'} shares); "
        f"tick rule {liquidity.tick_rule_status}."
    )

    if not trading_elig.challenge_order_eligible:
        trigger = f"Research review only ({trading_elig.status}); requires verified Challenge universe admission / active session quote."
    elif trend.awakening_detected:
        trigger = f"Human review warranted for {symbol}: check CMF/BVMT news & order-book depth before any manual limit order."
    else:
        trigger = f"Re-evaluate {symbol} if turnover awakens >= 3.0x trailing median (>10,000 TND) with positive close or verified CMF filing."

    return ResearchDecisionExplanation(
        why_interesting=why_interesting,
        why_uncertain=why_uncertain,
        missing_data=missing_data,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        is_tradable=trading_elig.challenge_order_eligible,
        execution_risk=exec_risk,
        review_trigger=trigger,
        disclaimer=(
            "RESEARCH-ONLY OUTPUT: Research status never equals an automatic BUY signal, "
            "produces NO calibrated probability or profit confidence, and requires explicit human review."
        ),
    )


# ---------------------------------------------------------------------------
# Main PIT Research Evaluator
# ---------------------------------------------------------------------------


def evaluate_sparse_market_research(
    instruments: Iterable[InstrumentRecord],
    calendar: Iterable[ExchangeSession],
    bars: Iterable[DailyBar],
    cutoff: datetime,
    *,
    config: SparseResearchConfig | None = None,
    baseline_report: SessionBaselineReport | None = None,
    suspensions: Iterable[SuspensionRecord] = (),
    document_chunks: Sequence[DocumentChunk] = (),
    fundamental_records: Sequence[FundamentalSnapshotRecord] = (),
    held_positions: Mapping[str, Any] | None = None,
    pending_orders: Sequence[PendingOrderReservation] = (),
    portfolio_equity_tnd: Decimal = Decimal("50000.000"),
    sector_by_instrument: Mapping[str, str] | None = None,
    limit_reserved_meta: Sequence[LimitReservedBarMeta] = (),
    limit_reserved_recovery_applied: bool = False,
    hb_bar_keys: frozenset[tuple[str, date]] = frozenset(),
) -> SparseMarketResearchReport:
    """Evaluate all listed BVMT instruments across 7 independent PIT layers."""
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")

    cfg = config or load_frozen_sparse_research_config()
    inst_list = validate_instrument_master(instruments)
    cal_list = validate_exchange_calendar(calendar)
    bar_list = validate_bars(bars)

    open_sessions = [
        s for s in cal_list if s.is_open and s.closes_at is not None and s.closes_at <= cutoff
    ]
    if not open_sessions:
        raise ValueError("No completed open exchange sessions on or before cutoff")

    latest_session = open_sessions[-1]
    latest_date = latest_session.session_date
    suspended_keys = {(s.instrument_id, s.session_date) for s in suspensions}

    pit_bars_list: list[DailyBar] = []
    pit_bars: dict[tuple[str, date], DailyBar] = {}
    bars_by_inst: dict[str, list[DailyBar]] = defaultdict(list)
    for b in bar_list:
        if (
            b.published_at is not None
            and b.published_at <= cutoff
            and b.ingested_at <= cutoff
            and b.session_date <= latest_date
        ):
            pit_bars[(b.instrument_id, b.session_date)] = b
            bars_by_inst[b.instrument_id].append(b)
            pit_bars_list.append(b)

    for iid in bars_by_inst:
        bars_by_inst[iid].sort(key=lambda x: x.session_date)

    by_inst_master: dict[str, list[InstrumentRecord]] = defaultdict(list)
    for rec in inst_list:
        by_inst_master[rec.instrument_id].append(rec)

    baseline_cands = (
        {c.instrument_id for c in baseline_report.candidates}
        if baseline_report is not None
        else set()
    )
    baseline_excls: dict[str, list[str]] = defaultdict(list)
    if baseline_report is not None:
        for e in baseline_report.exclusions:
            baseline_excls[e.instrument_id].append(e.reason)

    meta_by_inst: dict[str, list[LimitReservedBarMeta]] = defaultdict(list)
    for m in limit_reserved_meta:
        meta_by_inst[m.instrument_id].append(m)

    sector_map = dict(sector_by_instrument or {})
    held_map = held_positions or {}

    # Compute held sector totals for concentration warning
    sector_exposures_tnd: dict[str, Decimal] = defaultdict(lambda: Decimal("0.000"))
    for key, pos in held_map.items():
        pos_sec = sector_map.get(key) or sector_map.get(_norm_token(key))
        if not pos_sec:
            continue
        sh = (
            int(pos.get("total_shares", pos.get("quantity", 0)) or 0)
            if isinstance(pos, Mapping)
            else int(getattr(pos, "total_shares", getattr(pos, "quantity", 0)) or 0)
        )
        px = (
            quantize_tnd(pos.get("latest_price_tnd", pos.get("average_cost_tnd", "0")))
            if isinstance(pos, Mapping)
            else quantize_tnd(
                getattr(pos, "latest_price_tnd", getattr(pos, "average_cost_tnd", "0"))
            )
        )
        sector_exposures_tnd[pos_sec] += quantize_tnd(Decimal(sh) * px)

    # Pass 1: raw trend computation per instrument so market benchmark_20s is strictly cross-sectional PIT
    raw_by_inst: dict[str, dict[str, Any]] = {}
    active_by_inst: dict[str, InstrumentRecord | None] = {}
    mom20_principal_pool: list[float] = []

    for inst_id in sorted(by_inst_master.keys()):
        recs = by_inst_master[inst_id]
        active_rec = resolve_instrument_on_date(recs, inst_id, latest_date)
        active_by_inst[inst_id] = active_rec
        rec_ref = active_rec if active_rec is not None else recs[-1]
        inst_bars = bars_by_inst.get(inst_id, [])
        traded_bars = [b for b in inst_bars if b.status == "traded"]
        raw = _compute_quantitative_trend(
            inst_id, pit_bars, inst_bars, traded_bars, open_sessions, cfg
        )
        raw_by_inst[inst_id] = raw
        if raw["momentum_20s_pct"] is not None and rec_ref.market_segment in {
            "principal",
            "principal_continu",
            "principal_fixing",
        }:
            mom20_principal_pool.append(float(raw["momentum_20s_pct"]))

    bench_20s_pct: float | None = (
        _round_float(sum(mom20_principal_pool) / len(mom20_principal_pool), 4)
        if mom20_principal_pool
        else None
    )

    assessments: list[SparseInstrumentResearchAssessment] = []
    status_counts: dict[str, int] = defaultdict(int)
    selected_ids: list[str] = []

    for inst_id in sorted(by_inst_master.keys()):
        recs = by_inst_master[inst_id]
        active_rec = active_by_inst[inst_id]
        rec_ref = active_rec if active_rec is not None else recs[-1]
        symbol = rec_ref.symbol
        isin = rec_ref.isin
        segment = rec_ref.market_segment

        inst_bars = bars_by_inst.get(inst_id, [])
        traded_bars = [b for b in inst_bars if b.status == "traded"]
        untraded_bars = [b for b in inst_bars if b.status in {"no_trade", "untraded"}]
        latest_bar = pit_bars.get((inst_id, latest_date))

        chal_rec = (
            resolve_challenge_record(inst_id)
            or (resolve_challenge_record(isin) if isin else None)
            or resolve_challenge_record(symbol)
        )
        extra_aliases: list[str] = [symbol]
        if isin:
            extra_aliases.append(isin)
        if chal_rec is not None:
            extra_aliases.extend(
                [
                    chal_rec.challenge_symbol,
                    chal_rec.canonical_instrument_id,
                    chal_rec.verified_isin,
                ]
            )
        aliases = resolve_instrument_aliases(inst_id, extra_aliases=extra_aliases)

        is_restricted_segment = segment not in {
            "principal",
            "principal_continu",
            "principal_fixing",
        }
        is_suspended_now = (inst_id, latest_date) in suspended_keys or (
            latest_bar is not None and latest_bar.status == "suspended"
        )
        is_comp_permitted = (
            active_rec is not None
            and active_rec.is_competition_eligible
            and not is_restricted_segment
            and not is_suspended_now
        )

        # Layer 6: Competition Eligibility
        restriction_reason: str | None = None
        if is_suspended_now:
            restriction_reason = f"Suspended on {latest_date.isoformat()}."
        elif active_rec is None or not active_rec.is_competition_eligible or is_restricted_segment:
            restriction_reason = (
                f"Segment '{segment}' is restricted or unlisted on {latest_date.isoformat()}."
            )
        elif chal_rec is None:
            restriction_reason = "Not in observed 42-security Tunis Bourse Challenge list."

        comp_elig = CompetitionEligibilityStatus(
            in_challenge_universe=chal_rec is not None,
            challenge_symbol=chal_rec.challenge_symbol if chal_rec else None,
            order_entry_eligibility=(
                chal_rec.order_entry_eligibility if chal_rec else "NOT_IN_UNIVERSE"
            ),
            market_segment=segment,
            market_mode=(
                chal_rec.market_mode
                if chal_rec is not None
                else (
                    "Continu"
                    if "continu" in segment
                    else "Fixing"
                    if "fixing" in segment
                    else "Unknown"
                )
            ),
            is_competition_permitted=is_comp_permitted,
            restriction_reason=restriction_reason,
        )

        # Layer 4 & 5: Liquidity & Freshness
        liquidity, freshness = _compute_liquidity_and_freshness(
            inst_id,
            pit_bars,
            inst_bars,
            traded_bars,
            untraded_bars,
            open_sessions,
            meta_by_inst.get(inst_id, []),
            hb_bar_keys,
            is_comp_permitted,
            cfg,
        )

        # Layer 2 & 3: Fundamentals & Event Disclosures
        fundamental = _compute_fundamental_evidence(aliases, fundamental_records, cutoff)
        events = _compute_event_evidence(inst_id, aliases, document_chunks, cutoff)

        # Layer 1: Quantitative Trend Evidence
        raw = raw_by_inst[inst_id]
        m20: float | None = raw["momentum_20s_pct"]
        rel_str: float | None = (
            _round_float(m20 - bench_20s_pct, 4)
            if m20 is not None and bench_20s_pct is not None
            else None
        )
        quant_score = _compute_quantitative_score(raw, rel_str, liquidity, events, cfg)
        trend = QuantitativeTrendEvidence(
            momentum_5s_pct=raw["momentum_5s_pct"],
            momentum_20s_pct=m20,
            momentum_60s_pct=raw["momentum_60s_pct"],
            relative_strength_20s_pct=rel_str,
            benchmark_return_20s_pct=bench_20s_pct,
            observed_trade_return_pct=raw["observed_trade_return_pct"],
            observed_trade_interval_sessions=raw["observed_trade_interval_sessions"],
            trailing_traded_5_return_pct=raw["trailing_traded_5_return_pct"],
            latest_day_return_pct=raw["latest_day_return_pct"],
            volatility_20s_pct=raw["volatility_20s_pct"],
            latest_turnover_tnd=raw["latest_turnover_tnd"],
            trailing_median_turnover_20s_tnd=raw["trailing_median_turnover_20s_tnd"],
            turnover_awakening_ratio=raw["turnover_awakening_ratio"],
            volume_awakening_ratio=raw["volume_awakening_ratio"],
            awakening_detected=bool(raw["awakening_detected"]),
            is_partial_horizon=bool(raw["is_partial_horizon"]),
            quantitative_score=quant_score,
            signal_notes=list(raw["notes"]),
        )

        # Layer 7: Portfolio Risk
        sector = (
            sector_map.get(inst_id)
            or (sector_map.get(isin.upper()) if isin else None)
            or (sector_map.get(chal_rec.challenge_symbol.upper()) if chal_rec else None)
        )
        port_risk = _compute_portfolio_risk(
            inst_id,
            symbol,
            aliases,
            held_map,
            pending_orders,
            portfolio_equity_tnd,
            sector,
            sector_exposures_tnd,
            liquidity,
            freshness,
            cfg,
        )

        research_status, trading_elig = _classify_statuses(
            is_comp_permitted,
            is_suspended_now,
            chal_rec,
            active_rec,
            freshness,
            liquidity,
            trend,
            fundamental,
            events,
            cfg,
        )
        status_counts[research_status] += 1

        is_sel, sel_reason, priority_score = _evaluate_candidate_selection(
            research_status, trading_elig, trend, liquidity, freshness, events, cfg
        )
        if is_sel:
            selected_ids.append(inst_id)

        explanation = _build_explanation(
            symbol,
            research_status,
            trading_elig,
            trend,
            fundamental,
            events,
            liquidity,
            freshness,
            port_risk,
        )

        assessments.append(
            SparseInstrumentResearchAssessment(
                instrument_id=inst_id,
                symbol=symbol,
                isin=isin,
                as_of_session=latest_date.isoformat(),
                model_version=cfg.model_version,
                research_status=research_status,
                trading_eligibility=trading_elig,
                research_priority_score=priority_score,
                is_selected_candidate=is_sel,
                candidate_selection_reason=sel_reason,
                baseline_eligible=(inst_id in baseline_cands),
                baseline_exclusion_reasons=baseline_excls.get(inst_id, []),
                quantitative_trend_evidence=trend,
                fundamental_evidence=fundamental,
                event_disclosure_evidence=events,
                liquidity_execution_feasibility=liquidity,
                data_quality_freshness=freshness,
                competition_eligibility=comp_elig,
                portfolio_risk=port_risk,
                explanation=explanation,
            )
        )

    assessments.sort(
        key=lambda a: (
            0 if a.research_priority_score is not None else 1,
            -(a.research_priority_score if a.research_priority_score is not None else -999.0),
            a.instrument_id,
        )
    )
    selected_sorted = [a.instrument_id for a in assessments if a.is_selected_candidate][
        : cfg.candidate_top_k
    ]
    selected_set = set(selected_sorted)
    final_assessments: list[SparseInstrumentResearchAssessment] = []
    for a in assessments:
        if a.is_selected_candidate and a.instrument_id not in selected_set:
            final_assessments.append(
                SparseInstrumentResearchAssessment(
                    instrument_id=a.instrument_id,
                    symbol=a.symbol,
                    isin=a.isin,
                    as_of_session=a.as_of_session,
                    model_version=a.model_version,
                    research_status=a.research_status,
                    trading_eligibility=a.trading_eligibility,
                    research_priority_score=a.research_priority_score,
                    is_selected_candidate=False,
                    candidate_selection_reason=(
                        f"Below candidate_top_k={cfg.candidate_top_k} cap ({a.candidate_selection_reason})"
                    ),
                    baseline_eligible=a.baseline_eligible,
                    baseline_exclusion_reasons=a.baseline_exclusion_reasons,
                    quantitative_trend_evidence=a.quantitative_trend_evidence,
                    fundamental_evidence=a.fundamental_evidence,
                    event_disclosure_evidence=a.event_disclosure_evidence,
                    liquidity_execution_feasibility=a.liquidity_execution_feasibility,
                    data_quality_freshness=a.data_quality_freshness,
                    competition_eligibility=a.competition_eligibility,
                    portfolio_risk=a.portfolio_risk,
                    explanation=a.explanation,
                )
            )
        else:
            final_assessments.append(a)

    by_id = {a.instrument_id: a for a in final_assessments}
    return SparseMarketResearchReport(
        as_of=cutoff.isoformat(),
        latest_open_session=latest_date.isoformat(),
        model_version=cfg.model_version,
        config_sha256=cfg.config_sha256(),
        input_data_sha256=compute_bars_input_sha256(pit_bars_list),
        limit_reserved_recovery_applied=limit_reserved_recovery_applied,
        total_instruments=len(final_assessments),
        status_counts=dict(sorted(status_counts.items())),
        selected_candidate_ids=selected_sorted,
        assessments=final_assessments,
        by_instrument=by_id,
    )


# ---------------------------------------------------------------------------
# Phase 7: Prospective Forward Validation & Settlement Audit Framework
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProspectiveSignalRecord:
    """Append-only prospective research snapshot recorded strictly prior to future bars."""

    signal_id: str
    recorded_at: str
    session_date: str
    universe_version: str
    model_version: str
    config_sha256: str
    input_data_sha256: str
    instrument_id: str
    symbol: str
    research_status: ResearchStatus
    trading_eligibility_status: TradingEligibilityCode
    research_priority_score: float | None
    baseline_eligible: bool
    baseline_rank: int | None
    research_rank: int | None
    is_selected_candidate: bool
    evidence_summary: dict[str, Any]
    reference_close_tnd: str | None
    entry_assumption: str
    horizon_sessions: int = 10

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SettledSignalOutcome:
    """Prospective settlement outcome comparing realized post-cost fills vs baseline."""

    signal_id: str
    recorded_at: str
    session_date: str
    settlement_session_date: str
    horizon_sessions: int
    instrument_id: str
    symbol: str
    model_version: str
    entry_bar_date: str | None
    entry_fill_price_tnd: str | None
    entry_fill_shares: int
    exit_bar_date: str | None
    exit_price_tnd: str | None
    executable_fill_status: str
    gross_return_pct: float | None
    net_return_after_costs_pct: float | None
    baseline_selected: bool
    model_selected: bool
    is_false_positive: bool
    is_missed_opportunity: bool
    settlement_notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PromotionGateResult:
    """Explicit readiness decision enforcing multi-stock OOS validation before promotion."""

    model_version: str
    eligible_for_promotion: bool
    prospective_settled_count: int
    prospective_sessions_count: int
    non_icf_settled_count: int
    model_false_positive_rate: float | None
    baseline_false_positive_rate: float | None
    model_mean_net_return_pct: float | None
    non_icf_mean_net_return_pct: float | None
    max_drawdown_pct: float | None
    failed_gates: list[str]
    passed_gates: list[str]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _append_jsonl_record(ledger_path: Path, payload: Mapping[str, Any]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, sort_keys=True, allow_nan=False) + "\n"
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def record_prospective_signal(
    ledger_path: Path,
    signal: ProspectiveSignalRecord,
) -> ProspectiveSignalRecord:
    """Append one immutable prospective signal record (idempotent by ``signal_id``)."""
    existing = {s.signal_id for s in load_prospective_signals(ledger_path)}
    if signal.signal_id in existing:
        raise ValueError(f"Duplicate signal_id '{signal.signal_id}' in {ledger_path}")
    _append_jsonl_record(ledger_path, signal.to_dict())
    return signal


def record_prospective_report_signals(
    ledger_path: Path,
    report: SparseMarketResearchReport,
    *,
    recorded_at: datetime,
    baseline_report: SessionBaselineReport | None = None,
    horizon_sessions: int = 10,
    instrument_filter: frozenset[str] | None = None,
) -> list[ProspectiveSignalRecord]:
    """Record prospective snapshot rows from a ``SparseMarketResearchReport``."""
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("recorded_at must be timezone-aware")

    base_ranks = (
        {c.instrument_id: idx for idx, c in enumerate(baseline_report.candidates, 1)}
        if baseline_report is not None
        else {}
    )
    existing = {s.signal_id for s in load_prospective_signals(ledger_path)}
    recorded: list[ProspectiveSignalRecord] = []

    for rank_idx, a in enumerate(report.assessments, 1):
        if instrument_filter is not None and a.instrument_id not in instrument_filter:
            continue
        sig_id = f"{report.model_version}:{report.latest_open_session}:{a.instrument_id}"
        if sig_id in existing:
            continue
        ev_sum = {
            "quantitative_score": a.quantitative_trend_evidence.quantitative_score,
            "momentum_20s_pct": a.quantitative_trend_evidence.momentum_20s_pct,
            "awakening_detected": a.quantitative_trend_evidence.awakening_detected,
            "turnover_awakening_ratio": a.quantitative_trend_evidence.turnover_awakening_ratio,
            "events_count": a.event_disclosure_evidence.events_count,
            "quote_age_open_sessions": a.data_quality_freshness.quote_age_open_sessions,
            "missing_open_sessions_60s": a.data_quality_freshness.missing_open_sessions_60s,
            "execution_status": a.liquidity_execution_feasibility.execution_status,
            "candidate_reason": a.candidate_selection_reason,
        }
        ref_px = (
            a.liquidity_execution_feasibility.executable_reference_price_tnd
            or a.liquidity_execution_feasibility.last_verified_close_tnd
        )
        rec = ProspectiveSignalRecord(
            signal_id=sig_id,
            recorded_at=recorded_at.isoformat(),
            session_date=report.latest_open_session,
            universe_version=CHALLENGE_UNIVERSE_VERSION,
            model_version=report.model_version,
            config_sha256=report.config_sha256,
            input_data_sha256=report.input_data_sha256,
            instrument_id=a.instrument_id,
            symbol=a.symbol,
            research_status=a.research_status,
            trading_eligibility_status=a.trading_eligibility.status,
            research_priority_score=a.research_priority_score,
            baseline_eligible=a.baseline_eligible,
            baseline_rank=base_ranks.get(a.instrument_id),
            research_rank=rank_idx,
            is_selected_candidate=a.is_selected_candidate,
            evidence_summary=ev_sum,
            reference_close_tnd=str(ref_px) if ref_px is not None else None,
            entry_assumption="next_open_with_20bps_slippage_and_10pct_volume_cap",
            horizon_sessions=horizon_sessions,
        )
        _append_jsonl_record(ledger_path, rec.to_dict())
        recorded.append(rec)
    return recorded


def load_prospective_signals(ledger_path: Path) -> list[ProspectiveSignalRecord]:
    if not ledger_path.is_file():
        return []
    out: list[ProspectiveSignalRecord] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        out.append(ProspectiveSignalRecord(**raw))
    return out


def load_settled_outcomes(settlement_path: Path) -> list[SettledSignalOutcome]:
    if not settlement_path.is_file():
        return []
    out: list[SettledSignalOutcome] = []
    for line in settlement_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        out.append(SettledSignalOutcome(**raw))
    return out


def settle_prospective_signal(
    signal: ProspectiveSignalRecord,
    *,
    calendar: Sequence[ExchangeSession],
    bars: Sequence[DailyBar],
    config: SparseResearchConfig | None = None,
    capital_slice_tnd: Decimal = Decimal("4250.000"),
    positive_winner_threshold_pct: float = 2.0,
) -> SettledSignalOutcome | None:
    """Settle one prospective signal against strictly later verified bars (returns None if immature)."""
    if not bars:
        return None
    cfg = config or load_frozen_sparse_research_config()
    decision_day = date.fromisoformat(signal.session_date)
    future_open = sorted(
        s.session_date for s in calendar if s.is_open and s.session_date > decision_day
    )
    if len(future_open) < signal.horizon_sessions:
        return None

    target_horizon_dates = future_open[: signal.horizon_sessions]
    latest_bar_date = max(b.session_date for b in bars)
    if latest_bar_date < target_horizon_dates[-1]:
        return None
    inst_future_bars = sorted(
        (
            b
            for b in bars
            if b.instrument_id == signal.instrument_id
            and b.session_date in set(target_horizon_dates)
        ),
        key=lambda x: x.session_date,
    )
    bar_by_date = {b.session_date: b for b in inst_future_bars}

    entry_bar = bar_by_date.get(target_horizon_dates[0])
    exit_bar: DailyBar | None = None
    for d in reversed(target_horizon_dates):
        cand_b = bar_by_date.get(d)
        if cand_b is not None and cand_b.status == "traded" and cand_b.close > 0:
            exit_bar = cand_b
            break

    entry_fill_px: Decimal | None = None
    entry_shares = 0
    fill_status = "NO_FUTURE_ENTRY_BAR"
    gross_pct: float | None = None
    net_pct: float | None = None

    if entry_bar is not None:
        cap_shares = int(Decimal(entry_bar.volume_shares) * cfg.liquidity_participation_cap)
        if entry_bar.open > 0 and cap_shares > 0:
            desired = max(1, int(capital_slice_tnd // entry_bar.open))
            fill = estimate_next_bar_fill(
                MarketOrder(
                    instrument_id=signal.instrument_id,
                    decision_session=decision_day,
                    side="buy",
                    quantity=desired,
                ),
                entry_bar,
                participation_rate=cfg.liquidity_participation_cap,
                remaining_shared_capacity=cap_shares,
                slippage_bps=cfg.slippage_bps,
                commission_bps=cfg.buy_fee_rate * Decimal("10000"),
            )
            if fill.quantity > 0 and fill.price is not None:
                entry_fill_px = fill.price
                entry_shares = fill.quantity
                fill_status = "FILLED"
            else:
                fill_status = fill.reason.upper()
        else:
            fill_status = "ZERO_VOLUME_AT_NEXT_OPEN"

    if entry_fill_px is not None and exit_bar is not None and entry_bar is not None:
        exit_sell_px = exit_bar.close * (Decimal(1) - cfg.slippage_bps / Decimal(10000))
        gross_ratio = float(exit_bar.close / entry_bar.open - Decimal(1)) * 100.0
        buy_cost = entry_fill_px * (Decimal(1) + cfg.buy_fee_rate)
        sell_net = exit_sell_px * (Decimal(1) - cfg.sell_fee_rate)
        net_ratio = float(sell_net / buy_cost - Decimal(1)) * 100.0
        gross_pct = _round_float(gross_ratio, 4)
        net_pct = _round_float(net_ratio, 4)
    elif fill_status == "FILLED":
        fill_status = "NO_EXIT_TRADED_BAR_IN_HORIZON"

    baseline_sel = bool(
        signal.baseline_eligible
        and signal.baseline_rank is not None
        and signal.baseline_rank <= cfg.candidate_top_k
    )
    model_sel = signal.is_selected_candidate

    is_fp = bool(model_sel and (net_pct is None or net_pct <= 0.0))
    is_missed = bool(
        (not model_sel) and net_pct is not None and net_pct >= positive_winner_threshold_pct
    )

    notes = (
        f"Settled over {signal.horizon_sessions} sessions ({target_horizon_dates[0]}..{target_horizon_dates[-1]}): "
        f"fill={fill_status}, net={net_pct if net_pct is not None else 'None'}%."
    )
    return SettledSignalOutcome(
        signal_id=signal.signal_id,
        recorded_at=signal.recorded_at,
        session_date=signal.session_date,
        settlement_session_date=target_horizon_dates[-1].isoformat(),
        horizon_sessions=signal.horizon_sessions,
        instrument_id=signal.instrument_id,
        symbol=signal.symbol,
        model_version=signal.model_version,
        entry_bar_date=entry_bar.session_date.isoformat() if entry_bar else None,
        entry_fill_price_tnd=str(entry_fill_px.quantize(Decimal("0.001")))
        if entry_fill_px is not None
        else None,
        entry_fill_shares=entry_shares,
        exit_bar_date=exit_bar.session_date.isoformat() if exit_bar else None,
        exit_price_tnd=str(exit_bar.close) if exit_bar else None,
        executable_fill_status=fill_status,
        gross_return_pct=gross_pct,
        net_return_after_costs_pct=net_pct,
        baseline_selected=baseline_sel,
        model_selected=model_sel,
        is_false_positive=is_fp,
        is_missed_opportunity=is_missed,
        settlement_notes=notes,
    )


def settle_pending_prospective_signals(
    signal_ledger_path: Path,
    settlement_ledger_path: Path,
    *,
    calendar: Sequence[ExchangeSession],
    bars: Sequence[DailyBar],
    config: SparseResearchConfig | None = None,
) -> list[SettledSignalOutcome]:
    """Settle all un-settled mature prospective signals and append to ``settlement_ledger_path``."""
    signals = load_prospective_signals(signal_ledger_path)
    already_settled = {o.signal_id for o in load_settled_outcomes(settlement_ledger_path)}
    newly_settled: list[SettledSignalOutcome] = []
    for sig in signals:
        if sig.signal_id in already_settled:
            continue
        outcome = settle_prospective_signal(sig, calendar=calendar, bars=bars, config=config)
        if outcome is None:
            continue
        _append_jsonl_record(settlement_ledger_path, outcome.to_dict())
        newly_settled.append(outcome)
        already_settled.add(sig.signal_id)
    return newly_settled


def evaluate_promotion_readiness(
    settled_outcomes: Sequence[SettledSignalOutcome],
    *,
    config: SparseResearchConfig | None = None,
) -> PromotionGateResult:
    """Enforce conservative multi-stock promotion gates (blocks retrospective ICF-only promotion)."""
    cfg = config or load_frozen_sparse_research_config()
    gates = cfg.promotion_gates

    selected = [o for o in settled_outcomes if o.model_selected]
    non_icf_selected = [o for o in selected if o.instrument_id != "ICF"]
    base_selected = [o for o in settled_outcomes if o.baseline_selected]
    distinct_sessions = {o.session_date for o in settled_outcomes}

    settled_returns = [
        o.net_return_after_costs_pct for o in selected if o.net_return_after_costs_pct is not None
    ]
    non_icf_returns = [
        o.net_return_after_costs_pct
        for o in non_icf_selected
        if o.net_return_after_costs_pct is not None
    ]

    model_fp_rate = (
        _round_float(sum(1 for o in selected if o.is_false_positive) / len(selected), 4)
        if selected
        else None
    )
    base_fp_rate = (
        _round_float(
            sum(
                1
                for o in base_selected
                if o.net_return_after_costs_pct is None or o.net_return_after_costs_pct <= 0.0
            )
            / len(base_selected),
            4,
        )
        if base_selected
        else None
    )

    mean_net = (
        _round_float(sum(settled_returns) / len(settled_returns), 4) if settled_returns else None
    )
    non_icf_mean_net = (
        _round_float(sum(non_icf_returns) / len(non_icf_returns), 4) if non_icf_returns else None
    )

    # Sequential period equity curve drawdown across selected outcomes
    max_dd: float | None = None
    if settled_outcomes:
        by_sess: dict[str, list[float]] = defaultdict(list)
        for o in selected:
            if o.net_return_after_costs_pct is not None:
                by_sess[o.session_date].append(o.net_return_after_costs_pct)
        eq = 1.0
        peak = 1.0
        worst_dd = 0.0
        for s_date in sorted(distinct_sessions):
            rets = by_sess.get(s_date, [])
            if rets:
                avg_r = sum(rets) / len(rets) / 100.0
                eq *= 1.0 + avg_r * float(cfg.target_position_weight) * min(
                    len(rets), cfg.candidate_top_k
                )
                peak = max(peak, eq)
                worst_dd = max(worst_dd, (peak - eq) / peak * 100.0)
        max_dd = _round_float(worst_dd, 4)

    passed: list[str] = []
    failed: list[str] = []

    if len(selected) >= gates.min_prospective_settled_signals:
        passed.append(
            f"prospective_settled_count={len(selected)} >= {gates.min_prospective_settled_signals}"
        )
    else:
        failed.append(
            f"prospective_settled_count={len(selected)} < {gates.min_prospective_settled_signals}"
        )

    if len(distinct_sessions) >= gates.min_prospective_sessions:
        passed.append(
            f"prospective_sessions={len(distinct_sessions)} >= {gates.min_prospective_sessions}"
        )
    else:
        failed.append(
            f"prospective_sessions={len(distinct_sessions)} < {gates.min_prospective_sessions}"
        )

    if len(non_icf_selected) >= gates.min_non_icf_settled_signals:
        passed.append(
            f"non_icf_settled_count={len(non_icf_selected)} >= {gates.min_non_icf_settled_signals}"
        )
    else:
        failed.append(
            f"non_icf_settled_count={len(non_icf_selected)} < {gates.min_non_icf_settled_signals} (non-ICF generalization rule)"
        )

    if model_fp_rate is not None and model_fp_rate <= gates.max_false_positive_rate:
        passed.append(f"false_positive_rate={model_fp_rate:.4f} <= {gates.max_false_positive_rate}")
    else:
        failed.append(
            f"false_positive_rate={model_fp_rate} exceeds {gates.max_false_positive_rate}"
        )

    if (
        model_fp_rate is not None
        and base_fp_rate is not None
        and model_fp_rate > base_fp_rate + gates.max_false_positive_uplift_vs_baseline
    ):
        failed.append(
            f"false_positive_uplift={model_fp_rate - base_fp_rate:+.4f} > +{gates.max_false_positive_uplift_vs_baseline}"
        )

    if mean_net is not None and mean_net >= gates.min_mean_net_return_after_costs_pct:
        passed.append(
            f"mean_net_return_pct={mean_net:+.4f}% >= {gates.min_mean_net_return_after_costs_pct}%"
        )
    else:
        failed.append(
            f"mean_net_return_pct={mean_net} < {gates.min_mean_net_return_after_costs_pct}%"
        )

    if gates.require_non_icf_positive_expectancy:
        if non_icf_mean_net is not None and non_icf_mean_net > 0.0:
            passed.append(f"non_icf_mean_net_return_pct={non_icf_mean_net:+.4f}% > 0%")
        else:
            failed.append(
                f"non_icf_mean_net_return_pct={non_icf_mean_net} <= 0% (forbids ICF-only promotion)"
            )

    if max_dd is not None and max_dd <= gates.max_drawdown_pct:
        passed.append(f"max_drawdown_pct={max_dd:.2f}% <= {gates.max_drawdown_pct}%")
    else:
        failed.append(f"max_drawdown_pct={max_dd} > {gates.max_drawdown_pct}%")

    eligible = len(failed) == 0
    summary = (
        f"PROMOTION ELIGIBLE ({len(passed)} gates passed)"
        if eligible
        else f"PROMOTION BLOCKED ({len(failed)} gate(s) failed: {'; '.join(failed[:3])})"
    )
    return PromotionGateResult(
        model_version=cfg.model_version,
        eligible_for_promotion=eligible,
        prospective_settled_count=len(selected),
        prospective_sessions_count=len(distinct_sessions),
        non_icf_settled_count=len(non_icf_selected),
        model_false_positive_rate=model_fp_rate,
        baseline_false_positive_rate=base_fp_rate,
        model_mean_net_return_pct=mean_net,
        non_icf_mean_net_return_pct=non_icf_mean_net,
        max_drawdown_pct=max_dd,
        failed_gates=failed,
        passed_gates=passed,
        summary=summary,
    )
