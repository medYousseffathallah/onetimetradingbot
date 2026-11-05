"""Local notification & power-off catch-up alert center (Milestone 1C).

Evaluates 5 alert categories locally without paid background infrastructure or external messaging:
1. ALERT_SIGNAL_HIGH — New high-priority recommendations (BUY CANDIDATE, REDUCE, SELL CANDIDATE)
2. ALERT_RISK_CONCENTRATION — Significant portfolio concentration changes (>= 8.5% or > 10.0%)
3. ALERT_ORDER_EXPIRY — Pending orders approaching or exceeding the competition 1-week expiration
4. ALERT_DATA_STALE — Missing or stale market data relative to the exchange calendar
5. ALERT_EVENT_MATERIAL — Newly available verified corporate events
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from bvmt.calendar import ExchangeSession, validate_exchange_calendar
from bvmt.data import aware_timestamp
from bvmt.ledger import OPEN_ORDER_STATUSES, PortfolioLedger
from bvmt.recommendations import RecommendationReport, VerifiedEventSignal
from bvmt.snapshots import atomic_write_text, ensure_no_symlink_ancestors

SEVERITY_ORDER = {
    "BLOCKER": 0,
    "CRITICAL": 1,
    "URGENT": 2,
    "WARNING": 3,
    "ACTION_REVIEW": 4,
    "INFO": 5,
}


@dataclass(frozen=True)
class AlertRecord:
    alert_id: str
    created_at_utc: str
    session_date: str
    category: str
    severity: str
    instrument_id: str | None
    related_order_id: str | None
    related_recommendation_id: str | None
    caught_up_after_power_off: bool
    title: str
    message: str
    status: str  # "OPEN" | "ACKNOWLEDGED"
    acknowledged_at_utc: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class NotificationCenterState:
    last_evaluated_at_utc: str | None
    last_latest_bar_session: str | None
    missed_open_sessions_on_last_startup: list[str]
    alerts: dict[str, AlertRecord]


def _make_alert_id(category: str, session_str: str, key: str) -> str:
    digest = hashlib.sha256(f"{category}:{session_str}:{key}".encode()).hexdigest()[:10].upper()
    clean_date = session_str.replace("-", "")
    return f"ALT-{clean_date}-{category}-{digest}"


class NotificationCenter:
    """Persistent, deduplicated local alert center with startup power-off catch-up evaluation."""

    def __init__(
        self,
        *,
        last_evaluated_at_utc: str | None = None,
        last_latest_bar_session: str | None = None,
        missed_open_sessions_on_last_startup: list[str] | None = None,
        alerts: dict[str, AlertRecord] | None = None,
    ) -> None:
        self.last_evaluated_at_utc = last_evaluated_at_utc
        self.last_latest_bar_session = last_latest_bar_session
        self.missed_open_sessions_on_last_startup = list(missed_open_sessions_on_last_startup or [])
        self.alerts: dict[str, AlertRecord] = dict(alerts or {})

    def active_alerts(self) -> list[AlertRecord]:
        items = [a for a in self.alerts.values() if a.status == "OPEN"]
        items.sort(
            key=lambda a: (
                SEVERITY_ORDER.get(a.severity, 99),
                a.created_at_utc,
                a.alert_id,
            )
        )
        return items

    def all_alerts(self) -> list[AlertRecord]:
        items = list(self.alerts.values())
        items.sort(
            key=lambda a: (
                0 if a.status == "OPEN" else 1,
                SEVERITY_ORDER.get(a.severity, 99),
                a.created_at_utc,
                a.alert_id,
            )
        )
        return items

    def _upsert_alert(self, record: AlertRecord) -> bool:
        """Insert alert only if alert_id is not already present (deduplicated)."""
        if record.alert_id in self.alerts:
            return False
        self.alerts[record.alert_id] = record
        return True

    def acknowledge(self, alert_id: str, *, acknowledged_at: datetime) -> AlertRecord:
        if acknowledged_at.tzinfo is None or acknowledged_at.utcoffset() is None:
            raise ValueError("acknowledged_at must be timezone-aware")
        if alert_id not in self.alerts:
            raise ValueError(f"Unknown alert_id '{alert_id}'")
        existing = self.alerts[alert_id]
        updated = AlertRecord(
            alert_id=existing.alert_id,
            created_at_utc=existing.created_at_utc,
            session_date=existing.session_date,
            category=existing.category,
            severity=existing.severity,
            instrument_id=existing.instrument_id,
            related_order_id=existing.related_order_id,
            related_recommendation_id=existing.related_recommendation_id,
            caught_up_after_power_off=existing.caught_up_after_power_off,
            title=existing.title,
            message=existing.message,
            status="ACKNOWLEDGED",
            acknowledged_at_utc=acknowledged_at.isoformat(),
        )
        self.alerts[alert_id] = updated
        return updated

    def evaluate(
        self,
        *,
        now: datetime,
        calendar: Iterable[ExchangeSession],
        latest_bar_session: date | None,
        ledger: PortfolioLedger,
        recommendations: RecommendationReport | None = None,
        verified_events: Sequence[VerifiedEventSignal] = (),
        current_prices: Mapping[str, Decimal | str] | None = None,
    ) -> list[AlertRecord]:
        """Run all 5 alert checks plus power-off catch-up gap detection."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Evaluation timestamp 'now' must be timezone-aware")
        cal_list = validate_exchange_calendar(calendar)
        open_sessions_up_to_now = [
            s for s in cal_list if s.is_open and s.closes_at is not None and s.closes_at <= now
        ]
        latest_expected_session = (
            open_sessions_up_to_now[-1].session_date if open_sessions_up_to_now else now.date()
        )
        session_str = latest_expected_session.isoformat()

        # Detect whether the PC was switched off across one or more open exchange sessions
        missed_sessions: list[str] = []
        if self.last_evaluated_at_utc is not None:
            last_eval_dt = aware_timestamp(self.last_evaluated_at_utc)
            missed_sessions = [
                s.session_date.isoformat()
                for s in open_sessions_up_to_now
                if s.closes_at is not None and last_eval_dt < s.closes_at <= now
            ]
        caught_up = len(missed_sessions) > 0
        self.missed_open_sessions_on_last_startup = missed_sessions

        newly_created: list[AlertRecord] = []

        # 1. Missing or Stale Market Data (ALERT_DATA_STALE)
        if latest_bar_session is None:
            aid = _make_alert_id("ALERT_DATA_STALE", session_str, "NO_MARKET_DATA")
            rec = AlertRecord(
                alert_id=aid,
                created_at_utc=now.isoformat(),
                session_date=session_str,
                category="ALERT_DATA_STALE",
                severity="BLOCKER",
                instrument_id=None,
                related_order_id=None,
                related_recommendation_id=None,
                caught_up_after_power_off=caught_up,
                title="No market data available",
                message="No validated price bars are loaded for the current cutoff. Import an authorized BVMT CSV before reviewing trade sizing.",
                status="OPEN",
            )
            if self._upsert_alert(rec):
                newly_created.append(rec)
        elif open_sessions_up_to_now and latest_bar_session < latest_expected_session:
            lag_sessions = sum(
                1
                for s in open_sessions_up_to_now
                if latest_bar_session < s.session_date <= latest_expected_session
            )
            aid = _make_alert_id(
                "ALERT_DATA_STALE",
                session_str,
                f"STALE_{latest_bar_session.isoformat()}_VS_{session_str}",
            )
            rec = AlertRecord(
                alert_id=aid,
                created_at_utc=now.isoformat(),
                session_date=session_str,
                category="ALERT_DATA_STALE",
                severity="BLOCKER",
                instrument_id=None,
                related_order_id=None,
                related_recommendation_id=None,
                caught_up_after_power_off=caught_up,
                title=f"Stale market data ({lag_sessions} open session(s) behind)",
                message=(
                    f"Latest imported price bar is from {latest_bar_session.isoformat()}, "
                    f"but the exchange calendar has completed session {session_str}. "
                    "Import the latest official BVMT daily CSV before placing new orders."
                ),
                status="OPEN",
            )
            if self._upsert_alert(rec):
                newly_created.append(rec)

        # 2. Pending Orders Approaching or Exceeding 1-Week Expiration (ALERT_ORDER_EXPIRY)
        for order in sorted(ledger.orders.values(), key=lambda o: o.order_id):
            if order.status not in OPEN_ORDER_STATUSES:
                continue
            sub_dt = aware_timestamp(order.submitted_at)
            age_days = (now.date() - sub_dt.date()).days
            open_sessions_elapsed = sum(
                1 for s in open_sessions_up_to_now if sub_dt.date() <= s.session_date <= now.date()
            )
            if age_days >= 7:
                aid = _make_alert_id(
                    "ALERT_ORDER_EXPIRY", session_str, f"{order.order_id}_EXPIRED_7D"
                )
                rec = AlertRecord(
                    alert_id=aid,
                    created_at_utc=now.isoformat(),
                    session_date=session_str,
                    category="ALERT_ORDER_EXPIRY",
                    severity="URGENT",
                    instrument_id=order.instrument_id,
                    related_order_id=order.order_id,
                    related_recommendation_id=order.recommendation_id,
                    caught_up_after_power_off=caught_up,
                    title=f"Pending order {order.order_id} ({order.symbol}) reached 1-week competition expiry ({age_days} days)",
                    message=(
                        f"Order {order.order_id} ({order.side} {order.remaining_shares} {order.symbol} @ {order.limit_price_tnd} TND) "
                        f"was submitted on {sub_dt.date().isoformat()} ({age_days} calendar days ago). "
                        "Unfilled orders on tunisbourse-challenge.com expire automatically after 1 week. "
                        "Check your competition Carnet d'ordres and mark this order EXPIRED or EXECUTED."
                    ),
                    status="OPEN",
                )
                if self._upsert_alert(rec):
                    newly_created.append(rec)
            elif age_days >= 5 or open_sessions_elapsed >= 4:
                aid = _make_alert_id("ALERT_ORDER_EXPIRY", session_str, f"{order.order_id}_WARN_4S")
                rec = AlertRecord(
                    alert_id=aid,
                    created_at_utc=now.isoformat(),
                    session_date=session_str,
                    category="ALERT_ORDER_EXPIRY",
                    severity="WARNING",
                    instrument_id=order.instrument_id,
                    related_order_id=order.order_id,
                    related_recommendation_id=order.recommendation_id,
                    caught_up_after_power_off=caught_up,
                    title=f"Pending order {order.order_id} ({order.symbol}) approaching 1-week expiry ({age_days}d / {open_sessions_elapsed} sessions)",
                    message=(
                        f"Order {order.order_id} ({order.side} {order.remaining_shares} {order.symbol} @ {order.limit_price_tnd} TND) "
                        f"has been open for {open_sessions_elapsed} trading session(s) ({age_days} days). "
                        "Verify fill status on tunisbourse-challenge.com before the 7-day simulator expiration."
                    ),
                    status="OPEN",
                )
                if self._upsert_alert(rec):
                    newly_created.append(rec)

        # 3. Significant Portfolio Risk & Concentration Changes (ALERT_RISK_CONCENTRATION)
        snap = ledger.valuate(current_prices)
        for h in snap.holdings:
            if h.concentration_warning:
                sev = "CRITICAL" if h.portfolio_weight_pct > Decimal("10.000") else "WARNING"
                aid = _make_alert_id(
                    "ALERT_RISK_CONCENTRATION",
                    session_str,
                    f"{h.instrument_id}_{sev}",
                )
                rec = AlertRecord(
                    alert_id=aid,
                    created_at_utc=now.isoformat(),
                    session_date=session_str,
                    category="ALERT_RISK_CONCENTRATION",
                    severity=sev,
                    instrument_id=h.instrument_id,
                    related_order_id=None,
                    related_recommendation_id=None,
                    caught_up_after_power_off=caught_up,
                    title=f"Portfolio concentration {sev.lower()} on {h.symbol} ({h.portfolio_weight_pct}%)",
                    message=(
                        f"Holding {h.symbol} ({h.total_shares} shares, {h.market_value_tnd} TND) represents "
                        f"{h.portfolio_weight_pct}% of total portfolio equity ({snap.total_equity_tnd} TND). "
                        "Competition rules enforce a hard 10.0% single-stock cap."
                    ),
                    status="OPEN",
                )
                if self._upsert_alert(rec):
                    newly_created.append(rec)

        # 4. New High-Priority Recommendations (ALERT_SIGNAL_HIGH)
        if recommendations is not None:
            for card in recommendations.recommendations:
                if card.category in {"BUY CANDIDATE", "REDUCE", "SELL CANDIDATE"}:
                    sev = (
                        "WARNING"
                        if card.category in {"REDUCE", "SELL CANDIDATE"}
                        else "ACTION_REVIEW"
                    )
                    aid = _make_alert_id(
                        "ALERT_SIGNAL_HIGH",
                        card.latest_market_data_session,
                        f"{card.recommendation_id}_{card.category}",
                    )
                    rec = AlertRecord(
                        alert_id=aid,
                        created_at_utc=now.isoformat(),
                        session_date=card.latest_market_data_session,
                        category="ALERT_SIGNAL_HIGH",
                        severity=sev,
                        instrument_id=card.instrument_id,
                        related_order_id=None,
                        related_recommendation_id=card.recommendation_id,
                        caught_up_after_power_off=caught_up,
                        title=f"{card.category}: {card.symbol} ({card.recommendation_id})",
                        message=(
                            f"Recommendation {card.recommendation_id} classifies {card.symbol} as {card.category} "
                            f"(proposed: {card.suggested_side or 'NONE'} {card.suggested_shares} shares @ "
                            f"{card.suggested_limit_price_tnd or 'N/A'} TND, est. fee {card.estimated_fee_tnd} TND)."
                        ),
                        status="OPEN",
                    )
                    if self._upsert_alert(rec):
                        newly_created.append(rec)

        # 5. Newly Available Verified Corporate Events (ALERT_EVENT_MATERIAL)
        for ev in verified_events:
            if not ev.quote_verified:
                continue
            sev = "URGENT" if ev.polarity == "adverse_risk" else "INFO"
            aid = _make_alert_id("ALERT_EVENT_MATERIAL", session_str, ev.event_id)
            rec = AlertRecord(
                alert_id=aid,
                created_at_utc=now.isoformat(),
                session_date=session_str,
                category="ALERT_EVENT_MATERIAL",
                severity=sev,
                instrument_id=ev.instrument_id,
                related_order_id=None,
                related_recommendation_id=None,
                caught_up_after_power_off=caught_up,
                title=f"Verified corporate event [{ev.event_type}] for {ev.instrument_id}",
                message=f'{ev.summary} — Source [{ev.source_document_id}]: "{ev.verbatim_quote}"',
                status="OPEN",
            )
            if self._upsert_alert(rec):
                newly_created.append(rec)

        self.last_evaluated_at_utc = now.isoformat()
        self.last_latest_bar_session = (
            latest_bar_session.isoformat() if latest_bar_session is not None else None
        )
        return newly_created

    def to_dict(self) -> dict[str, object]:
        return {
            "alerts": {k: v.to_dict() for k, v in sorted(self.alerts.items())},
            "last_evaluated_at_utc": self.last_evaluated_at_utc,
            "last_latest_bar_session": self.last_latest_bar_session,
            "missed_open_sessions_on_last_startup": self.missed_open_sessions_on_last_startup,
            "schema_version": 1,
        }

    def save(self, path: Path) -> None:
        ensure_no_symlink_ancestors(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
        if path.exists():
            path.unlink()
        atomic_write_text(path, text, allow_identical=True)

    @classmethod
    def load(cls, path: Path) -> NotificationCenter:
        ensure_no_symlink_ancestors(path)
        if not path.is_file():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("Unsupported or corrupt notification state file")
        raw_alerts = raw.get("alerts", {})
        if not isinstance(raw_alerts, dict):
            raise ValueError("Corrupt alerts dictionary in notification state")
        alerts: dict[str, AlertRecord] = {}
        for k, a in raw_alerts.items():
            if isinstance(a, dict):
                alerts[str(k)] = AlertRecord(
                    alert_id=str(a["alert_id"]),
                    created_at_utc=str(a["created_at_utc"]),
                    session_date=str(a["session_date"]),
                    category=str(a["category"]),
                    severity=str(a["severity"]),
                    instrument_id=str(a["instrument_id"]) if a.get("instrument_id") else None,
                    related_order_id=(
                        str(a["related_order_id"]) if a.get("related_order_id") else None
                    ),
                    related_recommendation_id=(
                        str(a["related_recommendation_id"])
                        if a.get("related_recommendation_id")
                        else None
                    ),
                    caught_up_after_power_off=bool(a.get("caught_up_after_power_off", False)),
                    title=str(a["title"]),
                    message=str(a["message"]),
                    status=str(a["status"]),
                    acknowledged_at_utc=(
                        str(a["acknowledged_at_utc"]) if a.get("acknowledged_at_utc") else None
                    ),
                )
        missed = raw.get("missed_open_sessions_on_last_startup", [])
        return cls(
            last_evaluated_at_utc=(
                str(raw["last_evaluated_at_utc"]) if raw.get("last_evaluated_at_utc") else None
            ),
            last_latest_bar_session=(
                str(raw["last_latest_bar_session"]) if raw.get("last_latest_bar_session") else None
            ),
            missed_open_sessions_on_last_startup=(
                [str(x) for x in missed] if isinstance(missed, list) else []
            ),
            alerts=alerts,
        )
