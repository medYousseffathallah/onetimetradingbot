"""Versioned numerical research contracts; no fitted thresholds or promotion."""

import math

SCORING_VERSION = "bounded_risk_ratio_v2"


def bounded_risk_ratio(signal: float, volatility: float) -> float:
    """Map signal/vol to [-1, 1] via x/sqrt(1+x²), including its zero-vol limit.

    This monotonic transform uses no sample-dependent floor or winner tuning.
    A zero signal and zero volatility carry no directional evidence. Missing
    observations must be rejected by the caller, never represented as zero vol.
    """
    if not math.isfinite(signal) or not math.isfinite(volatility) or volatility < 0:
        raise ValueError("Require finite signal and nonnegative finite volatility")
    denominator = math.hypot(signal, volatility)
    return signal / denominator if denominator else 0.0


def bounded_momentum_score(short: float, long: float, volatility: float) -> float:
    return 0.5 * bounded_risk_ratio(short, volatility) + 0.5 * bounded_risk_ratio(long, volatility)
