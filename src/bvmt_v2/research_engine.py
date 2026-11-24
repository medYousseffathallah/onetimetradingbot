"""Point-in-time, evidence-first stock research. Return series use raw EOD prices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from statistics import mean, median, pstdev
from typing import Literal
from zoneinfo import ZoneInfo

from .contracts import (
    ExecutionFeasibility,
    Horizon,
    MarketObservation,
    OpportunityCandidate,
    ProvenanceValue,
    ResearchEvidence,
    State,
    StockAssessment,
    Universe,
    pv,
    utc,
)
from .market_data import REGISTRY_KNOWN, MarketData

SUPPORT: dict[Horizon, str] = {
    "1_2": "BLOCKED",
    "3_5": "DIAGNOSTIC_ONLY",
    "5_10": "EXPLORATORY",
    "10_20": "EXPLORATORY",
    "20_60": "BLOCKED_INSUFFICIENT_HISTORY",
}
FUNDAMENTALS = "No PIT quarterly/annual financial filings in local archive"
MODEL = "v2.0.0-layers"


@dataclass(frozen=True)
class Disclosure:
    instrument_id: str
    summary: str
    published_at: datetime
    first_observed_at: datetime
    source: str


@dataclass(frozen=True)
class ResearchContext:
    held: tuple[str, ...] = ()
    position_weights: Mapping[str, Decimal] | None = None
    events: tuple[Disclosure, ...] = ()


def valid_isin(code: str) -> bool:
    if (
        len(code) != 12
        or not code.startswith("TN")
        or not code.isascii()
        or not code.isalnum()
        or not code[-1].isdigit()
    ):
        return False
    digits = "".join(str(int(c, 36)) for c in code)
    return (
        sum(sum(divmod(int(n) * (2 if i % 2 else 1), 10)) for i, n in enumerate(reversed(digits)))
        % 10
        == 0
    )


def bounded_risk_ratio_v2(signal: Decimal, volatility: Decimal) -> Decimal:
    denominator = (signal**2 + volatility**2).sqrt()
    return signal / denominator if denominator else Decimal(0)


class ResearchEngine:
    """Prepare one cross-section once per decision cutoff and reuse it in discovery."""

    def __init__(
        self, market: MarketData, cutoff: datetime, context: ResearchContext | None = None
    ):
        self.market = market
        self.cutoff = utc(cutoff)
        self.context = context or ResearchContext()
        self.date = self.cutoff.astimezone(ZoneInfo("Africa/Tunis")).date()
        self.sessions = tuple(d for d in market.sessions if d <= self.date)[-61:]
        self.asof: dict[str, dict[date, MarketObservation]] = {}
        self.features: dict[str, dict[str, Decimal | None]] = {}
        for key, instrument in market.instruments.items():
            listed = (not instrument.listed_from or instrument.listed_from <= self.date) and (
                not instrument.listed_to or self.date <= instrument.listed_to
            )
            self.asof[key] = {
                b.session_date: b
                for b in market.bars.get(key, ())
                if self.sessions
                and self.sessions[0] <= b.session_date <= self.sessions[-1]
                and listed
                and b.provenance.available_at <= self.cutoff
            }
            self.features[key] = self._features(key)
        cohort = [
            self.features[k]
            for k, i in market.instruments.items()
            if i.challenge_member and self._registry_available(k)
        ]
        returns = [r for f in cohort if (r := f["ret_20s"]) is not None]
        above = [r for f in cohort if (r := f["above_ma20"]) is not None]
        self.challenge_median = median(returns) if returns else None
        self.breadth = mean(above) * 100 if above else None
        self.breadth_count = len(above)

    def _registry_available(self, key: str) -> bool:
        bars = self.asof[key]
        return self.cutoff >= REGISTRY_KNOWN or any(
            b.provenance.data_quality_status == "SYNTHETIC_FIXTURE" for b in bars.values()
        )

    def _features(self, key: str) -> dict[str, Decimal | None]:
        by_day = self.asof[key]
        days = self.sessions
        values: dict[str, Decimal | None] = {}

        def window(n: int) -> list[MarketObservation]:
            if len(days) < n or any(d not in by_day for d in days[-n:]):
                return []
            return [by_day[d] for d in days[-n:]]

        for span in (5, 20, 60):
            series = window(span + 1)
            closes = [b.close_tnd.value for b in series]
            a = closes[0] if closes else None
            z = closes[-1] if closes else None
            values[f"ret_{span}s"] = (
                z / a - 1
                if z and a and a > 0 and all(c is not None and c > 0 for c in closes)
                else None
            )
        month = window(20)
        valid_prices = [c for b in month if (c := b.close_tnd.value) is not None and c > 0]
        values["above_ma20"] = (
            Decimal(int(valid_prices[-1] > mean(valid_prices))) if len(valid_prices) == 20 else None
        )
        prices = [c for b in window(21) if (c := b.close_tnd.value) is not None and c > 0]
        vol = (
            pstdev([b / a - 1 for a, b in zip(prices[:-1], prices[1:], strict=True)])
            if len(prices) == 21
            else None
        )
        values["vol_20s"] = vol
        r20 = values["ret_20s"]
        values["bounded_risk_ratio_v2"] = (
            bounded_risk_ratio_v2(r20, vol) if r20 is not None and vol is not None else None
        )
        turns = [v for b in month if (v := b.turnover_tnd.value) is not None]
        values["adv_20s_tnd"] = median(turns) if len(turns) == 20 else None
        med = median([Decimal(b.volume_shares) for b in month]) if month else None
        values["median_vol_20s"] = med
        values["ten_pct_adv_shares"] = Decimal(int(med / 10)) if med is not None else None
        values["zero_vol_pct_20s"] = (
            Decimal(sum(b.volume_shares == 0 for b in month)) * 5 if month else None
        )
        last = window(1)
        values["close"] = last[0].close_tnd.value if last else None
        previous = window(21)
        highs = [v for b in previous[:-1] if (v := b.high_tnd.value) is not None]
        close = values["close"]
        values["breakout_expansion"] = (
            Decimal(int(close > max(highs) and month[-1].volume_shares > med))
            if len(highs) == 20 and med is not None and close
            else None
        )
        return values

    def candidate(self, identifier: str, horizon: Horizon = "5_10") -> OpportunityCandidate:
        key = self.market.resolve(identifier)
        ins = self.market.instruments[key]
        values = self.features[key].copy()
        latest = self.asof[key].get(self.sessions[-1]) if self.sessions else None
        source = f"{MODEL}/{latest.provenance.source_id}/{latest.session_date}" if latest else MODEL
        cutoff = self.cutoff
        simulated = bool(latest and latest.provenance.data_quality_status == "SYNTHETIC_FIXTURE")

        def metric(
            value: Decimal | None, unit: str, reason: str = "Incomplete session-aligned PIT window"
        ) -> ProvenanceValue:
            return pv(
                value,
                unit,
                ("SIMULATED" if simulated else "CALCULATED")
                if value is not None
                else "UNAVAILABLE",
                source,
                cutoff,
                reason if value is None else None,
            )

        r20 = values["ret_20s"]
        values["rs_vs_challenge_20s"] = (
            r20 - self.challenge_median
            if r20 is not None and self.challenge_median is not None
            else None
        )
        values["challenge_breadth_pct"] = self.breadth
        metrics = {
            k: metric(
                v,
                {
                    "close": "TND",
                    "adv_20s_tnd": "TND",
                    "ten_pct_adv_shares": "SHARES",
                    "median_vol_20s": "SHARES",
                    "zero_vol_pct_20s": "PCT",
                    "challenge_breadth_pct": "PCT",
                }.get(k, "RATIO"),
            )
            for k, v in values.items()
        }
        layers: dict[str, list[ResearchEvidence]] = {f"L{i}": [] for i in range(1, 11)}

        def evidence(
            layer: Literal["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"],
            polarity: Literal["SUPPORTING", "CONTRADICTING", "MISSING"],
            summary: str,
            value: ProvenanceValue | None = None,
            origin: str = source,
        ) -> None:
            layers[layer].append(
                ResearchEvidence(
                    evidence_id=f"{key}/{layer}/{len(layers[layer]) + 1}",
                    layer=layer,
                    polarity=polarity,
                    summary=summary,
                    metric_value=value,
                    provenance_status=value.status
                    if value
                    else (
                        "UNAVAILABLE"
                        if polarity == "MISSING"
                        else "SIMULATED"
                        if simulated
                        else "CALCULATED"
                    ),
                    source=origin,
                )
            )

        eligible = (
            ins.challenge_member
            and ins.order_entry_eligibility == "CONFIRMED"
            and self._registry_available(key)
            and valid_isin(ins.isin)
        )
        evidence(
            "L1",
            "SUPPORTING" if eligible else "CONTRADICTING",
            "Challenge registry and ISIN confirmed"
            if eligible
            else "RESTRICTED_CHALLENGE: membership or ISIN unconfirmed at cutoff",
        )
        if not latest or latest.provenance.source_publication_time is None:
            evidence("L1", "MISSING", "Source publication time unavailable")
        for name in ("ret_5s", "ret_20s", "ret_60s", "vol_20s", "bounded_risk_ratio_v2"):
            val = values[name]
            evidence(
                "L2",
                "MISSING" if val is None else "CONTRADICTING" if val < 0 else "SUPPORTING",
                name,
                metrics[name],
            )
        trend = values["ret_60s"]
        short = values["ret_5s"]
        hypothesis = (
            "PULLBACK_IN_UPTREND"
            if trend is not None and trend > 0 and short is not None and short < 0
            else "BREAKOUT_EXPANSION"
            if values["breakout_expansion"]
            else "TREND_OBSERVATION"
        )
        fundamentals = metric(None, "RATIO", FUNDAMENTALS)
        evidence("L3", "MISSING", FUNDAMENTALS, fundamentals)
        events = [
            e
            for e in self.context.events
            if e.instrument_id == key
            and max(utc(e.published_at), utc(e.first_observed_at)) <= cutoff
        ]
        for e in events:
            evidence("L4", "SUPPORTING", e.summary, origin=e.source)
        if not events:
            evidence("L4", "MISSING", "No PIT corporate disclosures available")
        for name in ("rs_vs_challenge_20s", "challenge_breadth_pct"):
            v = values[name]
            evidence(
                "L5",
                "MISSING"
                if v is None
                else "CONTRADICTING"
                if v < (50 if name == "challenge_breadth_pct" else 0)
                else "SUPPORTING",
                f"{name} (breadth coverage {self.breadth_count})",
                metrics[name],
            )
        evidence(
            "L5", "MISSING", "TUNINDEX", metric(None, "RATIO", "No TUNINDEX series in archive")
        )
        cap = values["ten_pct_adv_shares"]
        close = values["close"]
        capacity = cap * close if cap is not None and close and close > 0 else None
        staging = (
            "UNAVAILABLE"
            if capacity is None
            else "ONE_DAY"
            if capacity >= 5000
            else "THREE_DAY"
            if capacity * 3 >= 5000
            else "INSUFFICIENT_THREE_DAY"
        )
        for name in ("adv_20s_tnd", "median_vol_20s", "ten_pct_adv_shares", "zero_vol_pct_20s"):
            evidence(
                "L6",
                "MISSING"
                if values[name] is None
                else "CONTRADICTING"
                if staging == "INSUFFICIENT_THREE_DAY"
                else "SUPPORTING",
                f"{name}; 5000 TND sleeve: {staging}",
                metrics[name],
            )
        weights = self.context.position_weights or {}
        weight = weights.get(key)
        evidence(
            "L7",
            "MISSING"
            if weight is None
            else "CONTRADICTING"
            if weight >= Decimal(".10")
            else "SUPPORTING",
            "Issuer concentration relative to 10% single-stock cap",
            metric(weight, "RATIO", "No verified portfolio weight"),
        )
        sector = (
            "UNAVAILABLE"
            if not ins.sector
            or any(
                not self.market.instruments.get(k) or not self.market.instruments[k].sector
                for k in weights
            )
            or not weights
            else "SHARED"
            if any(
                k != key and w > 0 and self.market.instruments[k].sector == ins.sector
                for k, w in weights.items()
            )
            else "DISTINCT"
        )
        evidence(
            "L7",
            "MISSING"
            if sector == "UNAVAILABLE"
            else "CONTRADICTING"
            if sector == "SHARED"
            else "SUPPORTING",
            f"Sector diversification: {sector}",
        )
        held = key in self.context.held
        evidence(
            "L8",
            "SUPPORTING",
            "HELD_POSITION_REVIEW" if held else "No linked holding in supplied context",
        )
        evidence(
            "L9",
            "CONTRADICTING",
            f"Horizon {horizon}: {SUPPORT[horizon]}; probabilities uncalibrated",
        )
        trigger = "Next observed traded EOD bar, dated disclosure, or reconciled portfolio capture"
        evidence("L10", "SUPPORTING", f"{MODEL}. {trigger}")
        state: State
        if not eligible:
            state = "RESTRICTED"
        elif held:
            state = "HELD_POSITION_REVIEW"
        elif (
            trend is None
            or r20 is None
            or SUPPORT[horizon].startswith("BLOCKED")
            or not latest
            or latest.volume_shares <= 0
            or latest.status != "traded"
        ):
            state = "INSUFFICIENT_EVIDENCE"
        elif (
            r20 > 0
            and trend > 0
            and staging in {"ONE_DAY", "THREE_DAY"}
            and SUPPORT[horizon] == "EXPLORATORY"
        ):
            state = "RESEARCH_CANDIDATE"
        elif r20 > 0 or trend > 0:
            state = "WATCH"
        else:
            state = "NO_CURRENT_EDGE"
        all_e = [e for group in layers.values() for e in group]
        assessment = StockAssessment(
            instrument=ins,
            exchange_session=latest.session_date if latest else None,
            historical_eod_close_tnd=pv(
                latest.close_tnd.value,
                "TND",
                latest.close_tnd.status,
                latest.close_tnd.source,
                cutoff,
                latest.close_tnd.missing_reason,
                latest.provenance.first_observed_at,
            )
            if latest
            else metric(None, "TND", "No visible EOD bar at cutoff"),
            current_executable_quote_tnd=metric(
                None, "TND", "EOD archive contains no executable quote"
            ),
            research_date=self.date,
            cutoff_utc=cutoff,
            horizon=horizon,
            state=state,
            hypothesis=hypothesis,
            supporting_evidence=tuple(e for e in all_e if e.polarity == "SUPPORTING"),
            contradicting_evidence=tuple(e for e in all_e if e.polarity == "CONTRADICTING"),
            missing_evidence=tuple(e for e in all_e if e.polarity == "MISSING"),
            layers={k: tuple(v) for k, v in layers.items()},
            technical_state=metrics,
            fundamental_state=fundamentals,
            event_context=tuple(e.summary for e in events) or ("UNAVAILABLE",),
            liquidity_status=staging,
            execution_feasibility=ExecutionFeasibility(
                can_plan_manual_order=False,
                available_unreserved_shares=None,
                liquidity_cap_shares_10pct=int(cap) if cap is not None else None,
                blockers=("No executable quote",)
                if eligible
                else ("RESTRICTED_CHALLENGE", "No executable quote"),
            ),
            portfolio_suitability={
                "issuer": "UNAVAILABLE"
                if weight is None
                else "AT_OR_ABOVE_CAP"
                if weight >= Decimal(".10")
                else "BELOW_CAP",
                "sector": sector,
                "max_single_stock_weight": "0.10",
            },
            risk_scenarios=("Unadjusted corporate actions", "Thin or suspended trading"),
            horizon_support_status=SUPPORT[horizon],
            model_version=MODEL,
            next_review_condition=trigger,
        )
        return OpportunityCandidate(
            assessment=assessment,
            challenge_eligible=eligible,
            adv_20s_tnd=metrics["adv_20s_tnd"],
            ten_pct_adv_shares=metrics["ten_pct_adv_shares"],
        )

    def discover(self, universe: Universe, horizon: Horizon) -> Sequence[OpportunityCandidate]:
        candidates = [
            self.candidate(k, horizon)
            for k, i in self.market.instruments.items()
            if universe == "FULL_BVMT_RESEARCH"
            or (i.challenge_member and self._registry_available(k))
        ]
        priority = [
            "HELD_POSITION_REVIEW",
            "RESEARCH_CANDIDATE",
            "WATCH",
            "NO_CURRENT_EDGE",
            "INSUFFICIENT_EVIDENCE",
            "RESTRICTED",
        ]
        candidates.sort(
            key=lambda c: (
                priority.index(c.assessment.state),
                c.assessment.instrument.instrument_id,
            )
        )
        return [
            c.model_copy(update={"research_priority_rank": n}) for n, c in enumerate(candidates, 1)
        ]
