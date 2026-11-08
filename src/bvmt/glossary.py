"""Machine-readable metric glossary, indicator definitions, and eligibility reason mappings.

All definitions and formulas are strictly grounded in repository source code:
- src/bvmt/features.py (Momentum, Relative Strength, Volatility, Liquidity, Composite Score)
- src/bvmt/execution.py (Backtest Returns, Slippage, Fees, Drawdown, Walk-forward)
- src/bvmt/recommendations.py (Eligibility, Concentration Cap, Recommendation States)
- src/bvmt/gateway.py & data.py (Data Freshness, Source Provenance)
- src/bvmt/ledger.py (Portfolio Reconciliation)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    name: str
    category: (
        str  # "momentum" | "risk" | "liquidity" | "execution" | "governance" | "reconciliation"
    )
    plain_definition: str
    why_it_matters: str
    formula: str
    interpretation: str
    limitations: str
    doc_link: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class EligibilityExplanation:
    code: str
    title: str
    severity: str  # "blocker" | "warning" | "info"
    plain_explanation: str
    recommended_action: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


METRIC_GLOSSARY: dict[str, MetricDefinition] = {
    "momentum_20s": MetricDefinition(
        id="momentum_20s",
        name="20-Session Momentum",
        category="momentum",
        plain_definition="Percentage price change over the last 20 open exchange trading sessions.",
        why_it_matters="Identifies stocks in an active medium-term upward price trajectory on the Bourse de Tunis.",
        formula="close_t / close_{t-20} - 1.0 (using verified traded closing prices strictly)",
        interpretation="Positive values (> 0%) indicate recent price appreciation; higher values rank higher in momentum screens.",
        limitations="Sensitive to low-volume price jumps or single-block trades common in illiquid BVMT stocks.",
        doc_link="docs/SIGNAL_METHODOLOGY.md",
    ),
    "momentum_60s": MetricDefinition(
        id="momentum_60s",
        name="60-Session Momentum",
        category="momentum",
        plain_definition="Percentage price change over the last 60 open exchange trading sessions (approximately 3 calendar months).",
        why_it_matters="Filters out short-lived speculative spikes by confirming quarterly trend persistence.",
        formula="close_t / close_{t-60} - 1.0",
        interpretation="Stocks with both positive 20-session and 60-session momentum demonstrate durable institutional support.",
        limitations="Lags rapid market trend reversals; requires at least 61 verified open sessions of history.",
        doc_link="docs/SIGNAL_METHODOLOGY.md",
    ),
    "relative_strength_20s": MetricDefinition(
        id="relative_strength_20s",
        name="Relative Strength (20s)",
        category="momentum",
        plain_definition="The difference between a stock's 20-session return and the average return of all eligible continuous-trading stocks.",
        why_it_matters="Separates true stock-specific alpha from general market-wide index movement.",
        formula="momentum_20s - mean(momentum_20s of all eligible Continu_Principal stocks)",
        interpretation="Positive values mean the stock is outperforming its BVMT peers; negative means underperforming.",
        limitations="Equal-weighted cross-sectional benchmark treats large banks (BIAT, BNA) the same as smaller equities.",
        doc_link="docs/SIGNAL_METHODOLOGY.md",
    ),
    "volatility_20s": MetricDefinition(
        id="volatility_20s",
        name="Price Volatility (20s)",
        category="risk",
        plain_definition="The standard deviation of daily percentage price changes across traded sessions over the last 20 sessions.",
        why_it_matters="Measures price unpredictability and risk; used to risk-adjust momentum scores.",
        formula="sqrt( sum((r_i - mean_r)^2) / max(1, N - 1) ) where r_i = close_i / close_{i-1} - 1.0",
        interpretation="Lower volatility indicates steadier price movement; higher volatility implies larger unpredictable swings.",
        limitations="When a stock does not trade on several sessions, volatility is calculated only across actual traded days.",
        doc_link="docs/SIGNAL_METHODOLOGY.md",
    ),
    "composite_score": MetricDefinition(
        id="composite_score",
        name="Composite Research Score",
        category="momentum",
        plain_definition="Volatility-adjusted combined score blending short-term and quarterly momentum.",
        why_it_matters="Ranks stocks so that steady, low-volatility winners score higher than erratic, volatile spikes.",
        formula="0.5 * (momentum_20s / volatility_20s) + 0.5 * (momentum_60s / volatility_20s)",
        interpretation="Higher positive score = higher ranking. Scores near zero or negative indicate stagnant or declining prices.",
        limitations="Equal weighting (50/50) between 20s and 60s is an analytical heuristic, not an optimized machine-learning forecast.",
        doc_link="docs/SIGNAL_METHODOLOGY.md",
    ),
    "trade_frequency_20s": MetricDefinition(
        id="trade_frequency_20s",
        name="Trading Frequency (20s)",
        category="liquidity",
        plain_definition="The percentage of the last 20 open exchange sessions in which at least one transaction occurred.",
        why_it_matters="Ensures recommendations only target active stocks where orders can realistically be filled.",
        formula="traded_sessions_count / 20.0 (minimum threshold: >= 0.50 or 50%)",
        interpretation="1.00 (100%) = traded every session. < 0.50 (< 50%) = stock is excluded due to illiquidity.",
        limitations="A single 10-share trade marks a session as 'traded', so this must be reviewed alongside median turnover.",
        doc_link="docs/DATA_CONTRACTS.md",
    ),
    "median_turnover_20s": MetricDefinition(
        id="median_turnover_20s",
        name="Median Daily Turnover (20s)",
        category="liquidity",
        plain_definition="The median daily traded value in Tunisian Dinars (TND) over the last 20 open sessions.",
        why_it_matters="Confirms sufficient cash volume exists so an order does not cause severe slippage.",
        formula="median( [turnover_tnd for each session in last 20 sessions] ) (threshold: >= 1,000.000 TND)",
        interpretation="Higher turnover = deeper liquidity and easier execution. Stocks below 1,000 TND are excluded.",
        limitations="Uses historical exchange turnover, which fluctuates widely around corporate earnings or dividend dates.",
        doc_link="docs/DATA_CONTRACTS.md",
    ),
    "liquidity": MetricDefinition(
        id="liquidity",
        name="Liquidity Status",
        category="liquidity",
        plain_definition="Overall assessment of how easily a stock can be bought or sold without moving the market price.",
        why_it_matters="Thin liquidity can trap capital or cause severe slippage during order execution.",
        formula="Passes both: trading_frequency >= 50% AND median_daily_turnover >= 1,000.000 TND",
        interpretation="'High': freq >= 85% & turnover >= 10k TND; 'Moderate': passes minimums; 'Low/Excluded': fails.",
        limitations="BVMT market depth order books can be thin even for stocks that pass historical volume filters.",
        doc_link="docs/DATA_CONTRACTS.md",
    ),
    "eligibility": MetricDefinition(
        id="eligibility",
        name="Strategy Research Eligibility",
        category="governance",
        plain_definition="Rule-based compliance check determining whether a stock meets all quantitative and competition criteria.",
        why_it_matters="Protects the trader from trading suspended, delisted, illiquid, or non-continuous instruments.",
        formula="Must satisfy: Continu_Principal segment + Listed + >= 61 sessions + Traded anchors + Liquidity pass + No suspension",
        interpretation="'Eligible' = stock passes all gates and can receive BUY/HOLD signals. 'Excluded' = restricted from entry.",
        limitations="Eligibility does not guarantee profitability; it only guarantees regulatory and liquidity compliance.",
        doc_link="docs/COMPETITION_RULES_CHECKLIST.md",
    ),
    "max_drawdown": MetricDefinition(
        id="max_drawdown",
        name="Maximum Drawdown",
        category="risk",
        plain_definition="The largest peak-to-trough percentage drop in portfolio equity over a test period.",
        why_it_matters="Measures worst-case downside risk and capital preservation during market declines.",
        formula="max_{t} ( (Peak_t - Equity_t) / Peak_t ) across all evaluation sessions",
        interpretation="Lower percentage = better capital defense. High drawdown (> 20%) signals severe volatility risk.",
        limitations="Drawdown in low-exposure models is suppressed by large cash holdings; always check capital utilization.",
        doc_link="docs/BACKTEST_METHODOLOGY.md",
    ),
    "exposure": MetricDefinition(
        id="exposure",
        name="Capital Utilization (Exposure)",
        category="risk",
        plain_definition="The average percentage of total portfolio equity invested in stocks versus held in risk-free cash.",
        why_it_matters="Explains whether low risk is due to superior stock selection or simply holding mostly cash.",
        formula="mean( (Equity_t - Cash_t) / Equity_t ) over active simulation sessions",
        interpretation="Higher utilization (~90%) fully deploys capital; lower utilization (~30%) keeps ~70% in cash.",
        limitations="Low capital utilization reduces portfolio volatility but sacrifices upside during broad bull markets.",
        doc_link="docs/INDEPENDENT_STRATEGY_AUDIT.md",
    ),
    "market_regime": MetricDefinition(
        id="market_regime",
        name="Market Regime Filter",
        category="momentum",
        plain_definition="Macro market state classification based on cross-sectional breadth and trend of the Bourse de Tunis.",
        why_it_matters="Allows the system to scale down risk exposure during market-wide bear or stagnant regimes.",
        formula="Bullish: benchmark 20s return > 0% AND > 50% of stocks positive. Neutral/Bearish: otherwise.",
        interpretation="In Bull regimes, up to 10 slots are permitted. In Bear regimes, capital is defensively preserved in cash.",
        limitations="Simple moving-average regime filters can experience lag at abrupt market turning points.",
        doc_link="docs/RESEARCH_ROADMAP.md",
    ),
    "backtest_return": MetricDefinition(
        id="backtest_return",
        name="Backtest Return (Marked)",
        category="execution",
        plain_definition="Simulated cumulative percentage return based on verified historical closing prices minus transaction fees.",
        why_it_matters="Evaluates how a strategy would have performed over historical 2026 trading sessions.",
        formula="(Final_Marked_Equity - Initial_Cash) / Initial_Cash (including 0.50% buy and sell fees)",
        interpretation="Positive return outperforming the equal-weight benchmark indicates potential historical edge.",
        limitations="Assumes next-open execution capacity at 10% daily volume participation; past results do not guarantee future gains.",
        doc_link="docs/BACKTEST_METHODOLOGY.md",
    ),
    "liquidated_return": MetricDefinition(
        id="liquidated_return",
        name="Liquidated Return",
        category="execution",
        plain_definition="Hypothetical return if all open stock positions were forcibly sold at the final session close minus exit costs.",
        why_it_matters="Reveals true realizable cash return without relying on unrealized mark-to-market valuations.",
        formula="(Cash_After_Selling_All_Positions_Minus_Fees - Initial_Cash) / Initial_Cash",
        interpretation="Always slightly lower than marked return due to final liquidation fees (0.50%) and slippage (0.10%).",
        limitations="Assumes full final-day liquidation is possible, which may not hold for large positions in thin stocks.",
        doc_link="docs/BACKTEST_METHODOLOGY.md",
    ),
    "transaction_fees": MetricDefinition(
        id="transaction_fees",
        name="Transaction Fees",
        category="execution",
        plain_definition="Broker and exchange commission deducted on every executed buy and sell order.",
        why_it_matters="High portfolio turnover rapidly erodes returns if transaction costs are not modeled strictly.",
        formula="0.50% (50 basis points) * gross_order_amount (rounded to 0.001 TND)",
        interpretation="Mandatory fee applied in the Tunis Bourse Challenge virtual competition simulator.",
        limitations="Does not include VAT or minimum broker ticket charges which may apply in real live brokerage accounts.",
        doc_link="docs/COMPETITION_RULES_CHECKLIST.md",
    ),
    "slippage": MetricDefinition(
        id="slippage",
        name="Execution Slippage",
        category="execution",
        plain_definition="Estimated adverse price movement between signal generation and actual fill in the market order book.",
        why_it_matters="Protects backtests from unrealistically assuming orders fill exactly at the historical printed price.",
        formula="0.10% (10 basis points) added to Buy prices and deducted from Sell prices",
        interpretation="Conservative simulation friction to represent real-world bid-ask spread and market impact.",
        limitations="In extremely illiquid BVMT stocks with wide spreads, real slippage can exceed 10 basis points.",
        doc_link="docs/BACKTEST_METHODOLOGY.md",
    ),
    "walk_forward_testing": MetricDefinition(
        id="walk_forward_testing",
        name="Walk-Forward Validation",
        category="execution",
        plain_definition="Rolling simulation technique that tests strategies strictly out-of-sample across multiple historical time slices.",
        why_it_matters="Prevents data-mining bias and curve-fitting by ensuring the model never sees future prices.",
        formula="7 rolling folds: 61 sessions training window -> 19 sessions out-of-sample test window -> 19 sessions step",
        interpretation="Consistent positive returns across folds (e.g. 6/7 positive) indicates strategy robustness.",
        limitations="2026 archive contains 194 sessions; multi-year history (2020-2025) is needed for full statistical power.",
        doc_link="docs/BACKTEST_METHODOLOGY.md",
    ),
    "paper_trading_status": MetricDefinition(
        id="paper_trading_status",
        name="Forward Paper Trading",
        category="governance",
        plain_definition="Live forward observation tracking prospective signals generated daily without risking actual capital.",
        why_it_matters="Provides definitive out-of-sample proof of strategy behavior before live execution.",
        formula="Prospective daily signals recorded timestamped as-of session close; verified against subsequent sessions",
        interpretation="'Tracking': active forward log running. Verifies zero lookahead bias in forward-testing.",
        limitations="Requires accumulating daily sessions over several calendar weeks to build statistical sample size.",
        doc_link="docs/STATE.md",
    ),
    "data_freshness": MetricDefinition(
        id="data_freshness",
        name="Data Freshness Status",
        category="governance",
        plain_definition="Measurement of how up-to-date the local market data is compared to the official BVMT exchange calendar.",
        why_it_matters="Prevents making trading decisions using stale, delayed, or missing price information.",
        formula="sessions_behind = count(open completed sessions on calendar after latest imported session)",
        interpretation="'Current (0 sessions behind)' = up to date. '>= 1 session behind' = stale warning raised.",
        limitations="Exchange closes at 14:15 Africa/Tunis; official closing files are typically published by 14:45.",
        doc_link="docs/CANONICAL_DATA_SOURCE_RULES.md",
    ),
    "source_provenance": MetricDefinition(
        id="source_provenance",
        name="Source Data Provenance",
        category="governance",
        plain_definition="Cryptographic and audit trail tracking the exact origin, timestamp, and SHA-256 hash of all imported files.",
        why_it_matters="Guarantees that market prices have not been fabricated, modified, or corrupted.",
        formula="SHA-256 hash verified against original HTTP response bytes + recorded retrieved_at timestamp",
        interpretation="Tier-1 Official: downloaded directly from bvmt.com.tn. Synthetic Demo: labeled sandbox fixtures.",
        limitations="Provenance verifies file integrity and origin, but cannot fix reporting errors made by the source exchange.",
        doc_link="docs/CANONICAL_DATA_SOURCE_RULES.md",
    ),
    "portfolio_reconciliation": MetricDefinition(
        id="portfolio_reconciliation",
        name="Portfolio Reconciliation",
        category="reconciliation",
        plain_definition="Verification that local recorded cash and share quantities match the competition portal bit-for-bit.",
        why_it_matters="Guarantees that order sizing and cash reservations reflect the exact real account balance.",
        formula="reconciliation_gap_tnd = abs(website_total_equity - local_ledger_total_equity) (must equal 0.000)",
        interpretation="'Reconciled': zero discrepancy. 'Discrepancy': requires human review before placing trades.",
        limitations="Website values reflect displayp.aspx snapshots; intra-session pending fills must be logged manually.",
        doc_link="docs/MANUAL_TRADING_WORKFLOW.md",
    ),
}

ELIGIBILITY_MAP: dict[str, EligibilityExplanation] = {
    "unlisted_or_delisted": EligibilityExplanation(
        code="unlisted_or_delisted",
        title="Unlisted or Delisted",
        severity="blocker",
        plain_explanation="This stock was not actively listed on the Bourse de Tunis on the evaluation date.",
        recommended_action="Do not trade. Wait until the security is officially relisted or choose an active security.",
    ),
    "ineligible_market_segment": EligibilityExplanation(
        code="ineligible_market_segment",
        title="Non-Continuous Market Segment",
        severity="blocker",
        plain_explanation="This stock trades on the fixing or surveillance segment rather than continuous trading (Continu_Principal).",
        recommended_action="Excluded by strategy rules. Continuous liquidity is required for predictable execution.",
    ),
    "insufficient_session_history": EligibilityExplanation(
        code="insufficient_session_history",
        title="Insufficient Historical Data",
        severity="blocker",
        plain_explanation="The stock has fewer than 61 open trading sessions of history, preventing quarterly momentum calculation.",
        recommended_action="Wait until sufficient trading history (at least 61 completed sessions) is accumulated.",
    ),
    "suspended": EligibilityExplanation(
        code="suspended",
        title="Official Regulatory Suspension",
        severity="blocker",
        plain_explanation="Trading in this stock is currently halted by the CMF or Bourse de Tunis.",
        recommended_action="Strictly prohibited from trading. Await formal market resumption announcement.",
    ),
    "missing_observation": EligibilityExplanation(
        code="missing_observation",
        title="Missing Price Observation",
        severity="blocker",
        plain_explanation="Point-in-time price data is missing for one or more open exchange sessions in the lookback window.",
        recommended_action="Run market data refresh to retrieve missing session files; never forward-fill unverified prices.",
    ),
    "stale_quote": EligibilityExplanation(
        code="stale_quote",
        title="Stale Quotation",
        severity="blocker",
        plain_explanation="The stock has had multiple consecutive sessions with zero trading activity leading up to the cutoff date.",
        recommended_action="Excluded until genuine trading volume resumes on the exchange.",
    ),
    "untraded_lookback_anchor": EligibilityExplanation(
        code="untraded_lookback_anchor",
        title="Untraded Lookback Anchor",
        severity="blocker",
        plain_explanation="The session at the exact start or end of the lookback period had zero trades, preventing accurate return computation.",
        recommended_action="System refuses to fabricate returns; the stock is excluded until valid traded anchors exist.",
    ),
    "insufficient_liquidity": EligibilityExplanation(
        code="insufficient_liquidity",
        title="Low Trading Liquidity",
        severity="blocker",
        plain_explanation="Trading frequency is below 50% or median 20-day turnover is below 1,000 TND.",
        recommended_action="Avoid buying. Low liquidity creates high risk of unfilled orders or large exit slippage.",
    ),
    "synthetic_data_on_real_portfolio": EligibilityExplanation(
        code="synthetic_data_on_real_portfolio",
        title="Synthetic Market Guard",
        severity="blocker",
        plain_explanation="Synthetic demo fixtures cannot drive recommendations for real competition portfolios.",
        recommended_action="Select the verified official BVMT dataset in the market data selector or refresh market data.",
    ),
    "pending_order_conflict": EligibilityExplanation(
        code="pending_order_conflict",
        title="Pending Order Conflict",
        severity="warning",
        plain_explanation="An active buy or sell order is currently pending on the platform for this stock.",
        recommended_action="Wait for the existing order to fill, expire, or cancel before placing a new order.",
    ),
    "concentration_limit_exceeded": EligibilityExplanation(
        code="concentration_limit_exceeded",
        title="10% Concentration Limit",
        severity="warning",
        plain_explanation="Adding more shares would exceed the competition simulator's strict 10% single-stock portfolio cap.",
        recommended_action="Allocate capital to a different eligible stock to maintain required diversification.",
    ),
    "zero_volume_fill_prohibited": EligibilityExplanation(
        code="zero_volume_fill_prohibited",
        title="Zero-Volume Trade Guard",
        severity="blocker",
        plain_explanation="The system strictly refuses to simulate or recommend orders on zero-volume trading bars.",
        recommended_action="Ensure actual market activity occurred during the session before reviewing signals.",
    ),
    "adverse_verified_event": EligibilityExplanation(
        code="adverse_verified_event",
        title="Adverse Regulatory Disclosure",
        severity="warning",
        plain_explanation="A verified negative CMF/BVMT disclosure or event was detected for this company.",
        recommended_action="Review company announcements in the Stock Research tab before considering an allocation.",
    ),
}


def get_metric_definition(metric_id: str) -> MetricDefinition | None:
    """Retrieve a metric definition by its ID."""
    return METRIC_GLOSSARY.get(metric_id)


def get_eligibility_explanation(code: str) -> EligibilityExplanation:
    """Map an eligibility reason or risk code to a human-readable explanation."""
    clean_code = code.split(":")[0].strip()
    if clean_code in ELIGIBILITY_MAP:
        return ELIGIBILITY_MAP[clean_code]
    return EligibilityExplanation(
        code=clean_code,
        title=clean_code.replace("_", " ").title(),
        severity="warning",
        plain_explanation=code,
        recommended_action="Review stock details in the Market Explorer before taking action.",
    )


def list_metrics_by_category() -> dict[str, list[dict[str, str]]]:
    """Group all glossary metrics by category for display."""
    result: dict[str, list[dict[str, str]]] = {}
    for metric in METRIC_GLOSSARY.values():
        cat = metric.category
        if cat not in result:
            result[cat] = []
        result[cat].append(metric.to_dict())
    return result


def export_full_glossary() -> dict[str, Any]:
    """Export the complete machine-readable glossary and eligibility mapping."""
    return {
        "metrics": {k: v.to_dict() for k, v in METRIC_GLOSSARY.items()},
        "eligibility_reasons": {k: v.to_dict() for k, v in ELIGIBILITY_MAP.items()},
        "categories": list_metrics_by_category(),
    }
