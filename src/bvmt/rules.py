"""Fail-closed evidence completeness checks; never grants order-execution authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from bvmt.data import aware_timestamp

REQUIRED_FIELDS = (
    "edition",
    "initial_cash_tnd",
    "start_date",
    "end_date",
    "eligible_instruments",
    "scoring_and_final_valuation",
    "fees_and_taxes",
    "execution_matching",
    "allowed_order_types",
    "position_and_sector_limits",
    "short_selling_and_leverage",
    "settlement_and_cash",
    "corporate_actions",
    "tick_and_lot_rules",
    "automation_policy",
)


def competition_blockers(document: object) -> list[str]:
    if not isinstance(document, dict):
        return ["config_must_be_an_object"]
    blockers: list[str] = []
    if type(document.get("schema_version")) is not int or document.get("schema_version") != 1:
        blockers.append("unsupported_schema_version")
    if document.get("mode") != "competition_exact":
        blockers.append("wrong_simulation_profile")
    if document.get("execution_enabled") is not False:
        blockers.append("execution_must_remain_disabled_in_this_starter")
    fields = document.get("fields")
    if not isinstance(fields, dict):
        return blockers + ["missing_rule_fields"]
    for name in REQUIRED_FIELDS:
        entry = fields.get(name)
        if not isinstance(entry, dict):
            blockers.append(f"{name}:missing_entry")
            continue
        value = entry.get("value")
        if (
            value is None
            or isinstance(value, str)
            and not value.strip()
            or value == []
            or value == {}
        ):
            blockers.append(f"{name}:missing_value")
        if entry.get("status") != "verified":
            blockers.append(f"{name}:not_verified")
        for key in ("source", "evidence_locator", "reviewed_by", "reviewed_at"):
            evidence = entry.get(key)
            if not isinstance(evidence, str) or not evidence.strip():
                blockers.append(f"{name}:missing_{key}")
        stamp = entry.get("reviewed_at")
        if isinstance(stamp, str) and stamp.strip():
            try:
                aware_timestamp(stamp)
            except ValueError:
                blockers.append(f"{name}:invalid_review_timestamp")
        if name == "initial_cash_tnd" and value is not None:
            try:
                amount = Decimal(str(value))
                if not amount.is_finite() or amount <= 0:
                    raise ValueError("Initial cash must be positive and finite")
            except (InvalidOperation, ValueError):
                blockers.append(f"{name}:invalid_cash")
        if name in {"start_date", "end_date"} and value is not None:
            try:
                date.fromisoformat(str(value))
            except ValueError:
                blockers.append(f"{name}:invalid_date")
    try:
        start = date.fromisoformat(str(fields["start_date"]["value"]))
        end = date.fromisoformat(str(fields["end_date"]["value"]))
        if end <= start:
            blockers.append("end_date_must_follow_start_date")
    except (KeyError, TypeError, ValueError):
        pass  # Missing/invalid values have field-specific blockers above.
    return blockers
