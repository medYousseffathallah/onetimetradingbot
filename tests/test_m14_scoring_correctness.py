import math
from dataclasses import replace
from decimal import Decimal

import pytest
from test_features import _build_session_baseline_dataset

from bvmt.features import rank_session_baseline
from bvmt.research_scoring import bounded_momentum_score, bounded_risk_ratio


def test_insufficient_returns_are_not_called_stable_prices():
    instruments, sessions, bars, days, cutoff = _build_session_baseline_dataset(65)
    missing = set(days[-20:-1])
    sparse = [
        replace(b, volume_shares=0, turnover_tnd=Decimal(0), status="no_trade")
        if b.symbol == "ALPHA" and b.session_date in missing
        else b
        for b in bars
    ]
    report = rank_session_baseline(
        instruments,
        sessions,
        sparse,
        cutoff,
        min_trade_frequency=0.01,
        min_median_turnover_tnd=Decimal(0),
    )
    assert any(
        e.symbol == "ALPHA" and e.reason == "insufficient_volatility_observations"
        for e in report.exclusions
    )


def test_flat_then_spike_has_finite_bounded_score():
    assert bounded_momentum_score(0, 0.25, 0) == 0.5
    assert bounded_momentum_score(0, 0, 0) == 0
    for volatility in (0, 1e-300, 1e-6, 0.0025, 1):
        for signal in (-1, -0.001, 0, 0.001, 1, 1e300):
            assert -1 <= bounded_risk_ratio(signal, volatility) <= 1


def test_transform_is_monotonic_and_scale_invariant():
    values = [bounded_risk_ratio(x, 0.01) for x in (-2, -1, 0, 1, 2)]
    assert values == sorted(values)
    assert bounded_risk_ratio(0.2, 0.01) == pytest.approx(bounded_risk_ratio(20, 1))


@pytest.mark.parametrize("signal,vol", [(math.nan, 1), (1, math.inf), (1, -1)])
def test_unknown_or_invalid_values_cannot_become_stable_prices(signal, vol):
    with pytest.raises(ValueError):
        bounded_risk_ratio(signal, vol)
