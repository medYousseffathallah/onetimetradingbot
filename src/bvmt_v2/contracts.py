"""Immutable wire contracts shared by the offline V2 services."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

ValueStatus = Literal["OBSERVED", "CALCULATED", "SIMULATED", "UNVERIFIED", "UNAVAILABLE"]
Horizon = Literal["1_2", "3_5", "5_10", "10_20", "20_60"]
Mode = Literal["REAL_COMPETITION", "SYNTHETIC_DEMO"]
Universe = Literal["TUNIS_BOURSE_CHALLENGE", "FULL_BVMT_RESEARCH"]
State = Literal[
    "RESEARCH_CANDIDATE",
    "WATCH",
    "NO_CURRENT_EDGE",
    "INSUFFICIENT_EVIDENCE",
    "RESTRICTED",
    "HELD_POSITION_REVIEW",
]
MonitoringState = Literal[
    "HOLD", "REVIEW", "CONSIDER_TRIM", "CONSIDER_EXIT", "INSUFFICIENT_DATA", "EXECUTION_BLOCKED"
]


def utc(stamp: datetime) -> datetime:
    if stamp.utcoffset() is None:
        raise ValueError("UTC offset required")
    return stamp.astimezone(UTC)


Timestamp = Annotated[datetime, AfterValidator(utc)]


def money(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("finite Decimal required")
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_money_fields(self) -> Self:
        for name in type(self).model_fields:
            if name.endswith("_tnd"):
                field = getattr(self, name)
                if field is not None and (
                    not isinstance(field, ProvenanceValue) or field.unit != "TND"
                ):
                    raise ValueError(f"{name} requires a TND provenance value")
        return self


class ProvenanceValue(Contract):
    value: Decimal | None
    unit: str = Field(min_length=1)
    status: ValueStatus
    source: str = Field(min_length=1)
    observation_time: Timestamp | None
    calculation_time: Timestamp
    missing_reason: str | None

    @field_validator("value", mode="before")
    @classmethod
    def reject_binary_number(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use an exact decimal string in financial JSON")
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation as exc:
                raise ValueError("Invalid decimal string") from exc
        return value

    @model_validator(mode="after")
    def check_availability(self) -> Self:
        if self.status == "UNAVAILABLE":
            if self.value is not None or not (self.missing_reason or "").strip():
                raise ValueError("Unavailable values require null and a missing reason")
        elif self.value is None or self.missing_reason is not None:
            raise ValueError("Present values require a number and no missing reason")
        if self.unit == "TND" and self.value is not None:
            object.__setattr__(self, "value", money(self.value))
        if self.observation_time and self.observation_time > self.calculation_time:
            raise ValueError("observation follows calculation")
        return self

    @field_serializer("value")
    def serialize_value(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")


def pv(
    value: Decimal | int | str | None,
    unit: str,
    status: ValueStatus,
    source: str,
    at: datetime,
    reason: str | None = None,
    observed: datetime | None = None,
) -> ProvenanceValue:
    if isinstance(value, (float, bool)):
        raise ValueError("Binary floats and booleans are not financial values")
    return ProvenanceValue(
        value=Decimal(value) if value is not None else None,
        unit=unit,
        status=status,
        source=source,
        calculation_time=at,
        observation_time=observed,
        missing_reason=reason,
    )


class Instrument(Contract):
    instrument_id: str
    isin: str
    symbol: str
    challenge_member: bool
    order_entry_eligibility: Literal["CONFIRMED", "UNVERIFIED", "BLOCKED", "NOT_IN_UNIVERSE"]
    market_mode: str
    listed_from: date | None = None
    listed_to: date | None = None
    currency: Literal["TND"] = "TND"
    sector: str | None = None


class PriceProvenance(Contract):
    @property
    def available_at(self) -> datetime:
        """Earliest cutoff at which every recorded source-availability constraint is satisfied."""
        return max(
            stamp
            for stamp in (
                self.ingested_at,
                self.first_observed_at,
                self.retrieved_at,
                self.source_publication_time,
            )
            if stamp is not None
        )

    event_time: date | None
    exchange_session: date
    source_publication_time: Timestamp | None
    first_observed_at: Timestamp | None
    retrieved_at: Timestamp | None
    ingested_at: Timestamp
    validated_at: Timestamp
    source_id: str
    source_hash: str
    data_quality_status: Literal[
        "VERIFIED_PIT",
        "EOD_UNVERIFIED_PUB_TIME",
        "STALE_NO_TRADE",
        "SUSPENDED",
        "SYNTHETIC_FIXTURE",
        "MISSING",
    ]
    historical_eod_close_tnd: ProvenanceValue
    current_executable_quote_tnd: ProvenanceValue

    @model_validator(mode="after")
    def validate_eod_provenance(self) -> Self:
        if self.current_executable_quote_tnd.status != "UNAVAILABLE":
            raise ValueError("Daily bars cannot substantiate an executable quote")
        if self.data_quality_status == "VERIFIED_PIT" and self.source_publication_time is None:
            raise ValueError("Verified PIT publication requires a source timestamp")
        return self


class MarketObservation(Contract):
    instrument_id: str
    session_date: date
    open_tnd: ProvenanceValue
    high_tnd: ProvenanceValue
    low_tnd: ProvenanceValue
    close_tnd: ProvenanceValue
    volume_shares: int
    turnover_tnd: ProvenanceValue
    status: str
    provenance: PriceProvenance


class ResearchEvidence(Contract):
    evidence_id: str
    layer: Literal["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"]
    polarity: Literal["SUPPORTING", "CONTRADICTING", "MISSING"]
    summary: str
    metric_value: ProvenanceValue | None = None
    provenance_status: ValueStatus
    source: str


class ExecutionFeasibility(Contract):
    can_plan_manual_order: bool
    available_unreserved_shares: int | None
    liquidity_cap_shares_10pct: int | None
    blockers: tuple[str, ...]
    automatic_submission_enabled: Literal[False] = False


class StockAssessment(Contract):
    exchange_session: date | None
    historical_eod_close_tnd: ProvenanceValue
    current_executable_quote_tnd: ProvenanceValue
    instrument: Instrument
    research_date: date
    cutoff_utc: Timestamp
    horizon: Horizon
    state: State
    hypothesis: str
    supporting_evidence: tuple[ResearchEvidence, ...]
    contradicting_evidence: tuple[ResearchEvidence, ...]
    missing_evidence: tuple[ResearchEvidence, ...]
    layers: dict[str, tuple[ResearchEvidence, ...]]
    technical_state: dict[str, ProvenanceValue]
    fundamental_state: ProvenanceValue
    event_context: tuple[str, ...]
    liquidity_status: str
    execution_feasibility: ExecutionFeasibility
    portfolio_suitability: dict[str, str]
    risk_scenarios: tuple[str, ...]
    horizon_support_status: str
    model_version: str
    next_review_condition: str


class InvestmentThesis(Contract):
    instrument_id: str
    thesis: str
    horizon_sessions: int | None
    invalidation_conditions: tuple[str, ...]
    recorded_at: Timestamp | None
    origin: Literal["HUMAN_REVIEW_NOTE", "UNVERIFIED_NONE"]


class OpportunityCandidate(Contract):
    assessment: StockAssessment
    challenge_eligible: bool
    adv_20s_tnd: ProvenanceValue
    ten_pct_adv_shares: ProvenanceValue
    research_priority_rank: int | None = None


class Holding(Contract):
    displayed_acquisition_amount_tnd: ProvenanceValue | None = None
    instrument_id: str
    isin: str | None
    symbol: str
    quantity: int = Field(ge=0)
    displayed_avg_cost_tnd: ProvenanceValue
    displayed_price_tnd: ProvenanceValue
    displayed_value_tnd: ProvenanceValue
    displayed_unrealized_pnl_tnd: ProvenanceValue
    verified_cost_basis_tnd: ProvenanceValue
    eod_reference_close_tnd: ProvenanceValue


class PortfolioSnapshot(Contract):
    snapshot_id: str
    captured_at: Timestamp | None
    source_id: str
    equity_tnd: ProvenanceValue
    cash_tnd: ProvenanceValue
    holdings_value_tnd: ProvenanceValue
    rank: int | None
    total_participants: int | None
    verification_status: ValueStatus
    holdings: tuple[Holding, ...]
    reported_holdings_count: int | None = None
    return_pct: ProvenanceValue | None = None


class Transaction(Contract):
    transaction_id: str
    instrument_id: str
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    price_tnd: ProvenanceValue
    fee_tnd: ProvenanceValue
    executed_at: Timestamp | None
    verification_status: ValueStatus


class PendingOrder(Contract):
    order_id: str
    instrument_id: str
    side: Literal["BUY", "SELL"]
    remaining_shares: int = Field(ge=0)
    limit_price_tnd: ProvenanceValue
    submitted_at: Timestamp | None
    status: str


class RiskAssessment(Contract):
    position_weight: ProvenanceValue
    max_single_stock_weight: ProvenanceValue
    concentration_breach: bool | None
    liquidity_days_to_exit: ProvenanceValue
    volatility_20s: ProvenanceValue
    downside_stress_tnd: ProvenanceValue
    risk_budget_breached: bool | None


class PositionDecision(Contract):
    instrument_id: str
    monitoring_state: MonitoringState
    execution_state: Literal["EXECUTION_BLOCKED", "ELIGIBLE_MANUAL_ONLY"]
    blockers: tuple[str, ...]
    explanation: str
    next_review_trigger: str
    exit_scenarios: tuple[str, ...]
    risk: RiskAssessment | None = None
    thesis: InvestmentThesis | None = None
    realized_pnl_tnd: ProvenanceValue | None = None
    unrealized_pnl_tnd: ProvenanceValue | None = None


class ManualTradeScenario(Contract):
    downside_loss_tnd: ProvenanceValue | None = None
    side: Literal["BUY", "SELL", "PROTECTION"]
    instrument_id: str
    quantity: int
    limit_price_tnd: ProvenanceValue
    gross_tnd: ProvenanceValue
    estimated_fee_tnd: ProvenanceValue
    stress_proceeds_tnd: ProvenanceValue
    post_trade_weight: ProvenanceValue
    post_trade_cash_tnd: ProvenanceValue
    is_valid: bool
    rejection_reasons: tuple[str, ...]
    is_executed: Literal[False] = False


class ModelExperiment(Contract):
    experiment_id: str
    family: str
    horizon: int
    scope: str
    fold_count: int
    net_return_pct: ProvenanceValue
    liquidated_return_pct: ProvenanceValue
    alpha_vs_cash_pct: ProvenanceValue
    alpha_vs_ew_pct: ProvenanceValue
    max_drawdown_pct: ProvenanceValue
    top1_excluded_return_pct: ProvenanceValue
    top1_excluded_instrument: str | None
    turnover_pct: ProvenanceValue
    active_utilization_pct: ProvenanceValue
    fees_paid_tnd: ProvenanceValue
    win_rate: ProvenanceValue
    sample_count: int
    run_mode: Literal["STRICT_PIT", "RETROSPECTIVE_EXPLORATORY", "SYNTHETIC_DEMO"] = "STRICT_PIT"
    provenance_status: ValueStatus
    limitations: tuple[str, ...]
    config_hash: str
    data_hash: str
    source_hash: str
    trial_count: int


class SignalJournal(Contract):
    forecast_session: date | None = None
    journal_id: str
    recorded_at: Timestamp
    instrument_id: str
    action_state: str
    horizon: Horizon
    frozen_hash: str
    outcome_status: str


class PerformanceAttribution(Contract):
    period_start: date
    period_end: date
    starting_equity_tnd: ProvenanceValue
    ending_equity_tnd: ProvenanceValue
    total_return_pct: ProvenanceValue
    realized_pnl_tnd: ProvenanceValue
    unrealized_pnl_tnd: ProvenanceValue
    unexplained_residual_tnd: ProvenanceValue
    cash_drag_pct: ProvenanceValue
    estimated_fees_tnd: ProvenanceValue
    position_attributions: dict[str, dict[str, ProvenanceValue]]
    benchmarks: dict[str, ProvenanceValue]
    failure_tags: tuple[str, ...]
