"""Tests for explainability metric glossary, indicator definitions, and eligibility mappings."""

from __future__ import annotations

from fastapi.testclient import TestClient

from bvmt.api import create_app
from bvmt.glossary import (
    METRIC_GLOSSARY,
    export_full_glossary,
    get_eligibility_explanation,
    get_metric_definition,
    list_metrics_by_category,
)

REQUIRED_INDICATORS = [
    "momentum_20s",
    "momentum_60s",
    "relative_strength_20s",
    "volatility_20s",
    "composite_score",
    "trade_frequency_20s",
    "median_turnover_20s",
    "liquidity",
    "eligibility",
    "max_drawdown",
    "exposure",
    "market_regime",
    "backtest_return",
    "liquidated_return",
    "transaction_fees",
    "slippage",
    "walk_forward_testing",
    "paper_trading_status",
    "data_freshness",
    "source_provenance",
    "portfolio_reconciliation",
]


def test_required_indicators_present() -> None:
    """Verify all 21 prompt-specified indicators are present in the metric glossary."""
    for indicator in REQUIRED_INDICATORS:
        metric = get_metric_definition(indicator)
        assert metric is not None, f"Missing required indicator in glossary: {indicator}"
        assert metric.id == indicator
        assert len(metric.name) > 0
        assert len(metric.plain_definition) > 10
        assert len(metric.why_it_matters) > 10
        assert len(metric.formula) > 5
        assert len(metric.interpretation) > 10
        assert len(metric.limitations) > 10
        assert metric.doc_link.startswith("docs/")


def test_categories_grouped() -> None:
    """Verify metric categorization."""
    by_cat = list_metrics_by_category()
    expected_categories = {
        "momentum",
        "risk",
        "liquidity",
        "execution",
        "governance",
        "reconciliation",
    }
    assert set(by_cat.keys()) == expected_categories
    total_metrics = sum(len(m_list) for m_list in by_cat.values())
    assert total_metrics == len(METRIC_GLOSSARY)


def test_eligibility_mapping_known_codes() -> None:
    """Verify standard BVMT eligibility and risk blocker reasons map to readable explanations."""
    known_codes = [
        "unlisted_or_delisted",
        "ineligible_market_segment",
        "insufficient_session_history",
        "suspended",
        "missing_observation",
        "stale_quote",
        "untraded_lookback_anchor",
        "insufficient_liquidity",
        "synthetic_data_on_real_portfolio",
        "pending_order_conflict",
        "concentration_limit_exceeded",
        "zero_volume_fill_prohibited",
        "adverse_verified_event",
    ]
    for code in known_codes:
        expl = get_eligibility_explanation(code)
        assert expl.code == code
        assert len(expl.title) > 0
        assert expl.severity in {"blocker", "warning", "info"}
        assert len(expl.plain_explanation) > 10
        assert len(expl.recommended_action) > 10


def test_eligibility_mapping_colon_prefixed_code() -> None:
    """Verify reasons with embedded details (e.g. 'pending_order_conflict: detail') map cleanly."""
    raw = "pending_order_conflict: Active order exists for DEMO_A"
    expl = get_eligibility_explanation(raw)
    assert expl.code == "pending_order_conflict"
    assert expl.title == "Pending Order Conflict"
    assert expl.severity == "warning"


def test_eligibility_mapping_unknown_code_fallback() -> None:
    """Verify unknown code returns a graceful humanized fallback rather than crashing."""
    expl = get_eligibility_explanation("custom_unforeseen_rule: some reason")
    assert expl.code == "custom_unforeseen_rule"
    assert expl.title == "Custom Unforeseen Rule"
    assert expl.severity == "warning"


def test_export_full_glossary_structure() -> None:
    """Verify export_full_glossary includes complete machine-readable contract."""
    exported = export_full_glossary()
    assert "metrics" in exported
    assert "eligibility_reasons" in exported
    assert "categories" in exported
    assert len(exported["metrics"]) >= 21
    assert len(exported["eligibility_reasons"]) >= 13


def test_api_glossary_endpoint() -> None:
    """Verify FastAPI GET /api/glossary returns HTTP 200 with glossary payload."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/glossary")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "momentum_20s" in data["metrics"]
    assert data["metrics"]["momentum_20s"]["name"] == "20-Session Momentum"
    assert "eligibility_reasons" in data


def test_api_rankings_includes_eligibility_explanations() -> None:
    """Verify GET /api/rankings response contains structured eligibility explanations."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/rankings")
    assert response.status_code == 200
    data = response.json()
    rankings = data.get("rankings", [])
    assert len(rankings) > 0
    # Every item must have eligibility_explanations list
    for item in rankings:
        assert "eligibility_explanations" in item
        assert isinstance(item["eligibility_explanations"], list)
        for expl in item["eligibility_explanations"]:
            assert "code" in expl
            assert "title" in expl
            assert "severity" in expl
            assert "plain_explanation" in expl
            assert "recommended_action" in expl
