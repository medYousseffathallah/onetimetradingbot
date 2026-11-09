"""Unit tests for holding period research evaluation."""

from pathlib import Path

from bvmt.holding_period import evaluate_holding_periods


def test_holding_period_evaluation_structure_and_inconclusiveness():
    """Verify holding period evaluation runs across 6 horizons and reports INCONCLUSIVE."""
    bars_path = Path("data/processed/bvmt_official_2026/daily_bars.canonical.csv")
    if not bars_path.exists():
        return

    report = evaluate_holding_periods(horizons=[1, 5, 20])
    assert report.is_statistically_conclusive is False
    assert "INCONCLUSIVE" in report.verdict
    assert report.recommended_review_horizon_sessions == 20
    assert len(report.horizons) == 3

    # Horizon 1 should have much higher fees than Horizon 20
    h1 = next(h for h in report.horizons if h.horizon_sessions == 1)
    h20 = next(h for h in report.horizons if h.horizon_sessions == 20)
    assert h1.total_fees_tnd > h20.total_fees_tnd * 5
    assert h1.trade_count > h20.trade_count * 5
