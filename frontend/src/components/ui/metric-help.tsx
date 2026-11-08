"use client";

import React, { useState, useRef, useEffect } from "react";
import { HelpCircle, Info, X, ExternalLink, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MetricHelpData {
  id: string;
  name: string;
  category: string;
  plain_definition: string;
  why_it_matters: string;
  formula: string;
  interpretation: string;
  limitations: string;
  doc_link?: string;
}

// Built-in fallback dictionary covering all 21 prompt indicators
export const BUILTIN_METRICS: Record<string, MetricHelpData> = {
  momentum_20s: {
    id: "momentum_20s",
    name: "20-Session Momentum",
    category: "momentum",
    plain_definition: "Percentage price change over the last 20 open exchange trading sessions (~1 calendar month).",
    why_it_matters: "Identifies stocks with strong medium-term upward price trajectory on the Bourse de Tunis.",
    formula: "close_t / close_{t-20} - 1.0",
    interpretation: "Positive values (> 0%) indicate recent price appreciation. Higher values rank higher in momentum screens.",
    limitations: "Sensitive to low-volume price jumps or single-block trades common in illiquid BVMT stocks.",
    doc_link: "docs/SIGNAL_METHODOLOGY.md",
  },
  momentum_60s: {
    id: "momentum_60s",
    name: "60-Session Momentum",
    category: "momentum",
    plain_definition: "Percentage price change over the last 60 open exchange trading sessions (~3 calendar months).",
    why_it_matters: "Filters out short-lived speculative spikes by confirming quarterly trend persistence.",
    formula: "close_t / close_{t-60} - 1.0",
    interpretation: "Stocks with both positive 20s and 60s momentum demonstrate durable institutional trend support.",
    limitations: "Lags rapid market reversals; requires at least 61 verified open sessions of history.",
    doc_link: "docs/SIGNAL_METHODOLOGY.md",
  },
  relative_strength_20s: {
    id: "relative_strength_20s",
    name: "Relative Strength (20s)",
    category: "momentum",
    plain_definition: "The difference between a stock's 20-session return and the average return of all eligible continuous stocks.",
    why_it_matters: "Separates genuine stock-specific alpha from general market-wide index movement.",
    formula: "momentum_20s - mean(momentum_20s of eligible Continu_Principal stocks)",
    interpretation: "Positive values indicate the stock is beating its BVMT peers; negative means underperforming.",
    limitations: "Equal-weighted cross-sectional benchmark treats large banks (BIAT, BNA) the same as smaller equities.",
    doc_link: "docs/SIGNAL_METHODOLOGY.md",
  },
  volatility_20s: {
    id: "volatility_20s",
    name: "Price Volatility (20s)",
    category: "risk",
    plain_definition: "Standard deviation of daily percentage price changes across traded sessions over the last 20 sessions.",
    why_it_matters: "Measures price unpredictability and risk; used to risk-adjust momentum scores.",
    formula: "sqrt( sum((r_i - mean_r)^2) / (N - 1) )",
    interpretation: "Lower volatility indicates steadier price movement; higher volatility implies larger unpredictable swings.",
    limitations: "When a stock does not trade on several sessions, volatility is calculated only across actual traded days.",
    doc_link: "docs/SIGNAL_METHODOLOGY.md",
  },
  composite_score: {
    id: "composite_score",
    name: "Composite Research Score",
    category: "momentum",
    plain_definition: "Volatility-adjusted combined score blending short-term and quarterly momentum.",
    why_it_matters: "Ranks stocks so that steady, low-volatility winners score higher than erratic, volatile spikes.",
    formula: "0.5 * (momentum_20s / volatility_20s) + 0.5 * (momentum_60s / volatility_20s)",
    interpretation: "Higher positive score = higher ranking. Scores near zero or negative indicate stagnant or declining prices.",
    limitations: "Equal weighting (50/50) between 20s and 60s is an analytical heuristic, not an optimized forecast.",
    doc_link: "docs/SIGNAL_METHODOLOGY.md",
  },
  trade_frequency_20s: {
    id: "trade_frequency_20s",
    name: "Trading Frequency (20s)",
    category: "liquidity",
    plain_definition: "The percentage of the last 20 open exchange sessions in which at least one transaction occurred.",
    why_it_matters: "Ensures recommendations only target active stocks where orders can realistically be filled.",
    formula: "traded_sessions_count / 20.0 (minimum threshold: >= 50%)",
    interpretation: "100% = traded every session. Below 50% = stock is excluded due to illiquidity.",
    limitations: "A single 10-share trade marks a session as 'traded'; must be reviewed alongside median turnover.",
    doc_link: "docs/DATA_CONTRACTS.md",
  },
  median_turnover_20s: {
    id: "median_turnover_20s",
    name: "Median Daily Turnover (20s)",
    category: "liquidity",
    plain_definition: "The median daily traded value in Tunisian Dinars (TND) over the last 20 open sessions.",
    why_it_matters: "Confirms sufficient cash volume exists so an order does not cause severe slippage.",
    formula: "median( [turnover_tnd for each session in last 20 sessions] )",
    interpretation: "Higher turnover = deeper liquidity and easier execution. Stocks below 1,000 TND are excluded.",
    limitations: "Uses historical exchange turnover, which fluctuates widely around earnings or dividend announcements.",
    doc_link: "docs/DATA_CONTRACTS.md",
  },
  liquidity: {
    id: "liquidity",
    name: "Liquidity Status",
    category: "liquidity",
    plain_definition: "Overall assessment of how easily a stock can be bought or sold without moving the market price.",
    why_it_matters: "Thin liquidity can trap capital or cause severe slippage during order execution.",
    formula: "trading_frequency >= 50% AND median_daily_turnover >= 1,000 TND",
    interpretation: "'High': freq >= 85% & turnover >= 10k TND; 'Moderate': passes minimums; 'Low/Excluded': fails.",
    limitations: "BVMT market depth order books can be thin even for stocks that pass historical volume filters.",
    doc_link: "docs/DATA_CONTRACTS.md",
  },
  eligibility: {
    id: "eligibility",
    name: "Strategy Eligibility",
    category: "governance",
    plain_definition: "Rule-based compliance check determining whether a stock meets all quantitative and competition criteria.",
    why_it_matters: "Protects the trader from trading suspended, delisted, illiquid, or non-continuous instruments.",
    formula: "Must satisfy: Continu_Principal segment + Listed + >= 61 sessions + Traded anchors + Liquidity pass + No suspension",
    interpretation: "'Eligible' = stock passes all gates. 'Excluded' = restricted from entry due to safety rules.",
    limitations: "Eligibility does not guarantee profitability; it only guarantees regulatory and liquidity compliance.",
    doc_link: "docs/COMPETITION_RULES_CHECKLIST.md",
  },
  max_drawdown: {
    id: "max_drawdown",
    name: "Maximum Drawdown",
    category: "risk",
    plain_definition: "The largest peak-to-trough percentage drop in portfolio equity over an evaluation period.",
    why_it_matters: "Measures worst-case downside risk and capital preservation during market declines.",
    formula: "max_{t} ( (Peak_t - Equity_t) / Peak_t )",
    interpretation: "Lower percentage = better capital defense. High drawdown (> 20%) signals severe volatility risk.",
    limitations: "Drawdown in low-exposure models is suppressed by large cash holdings; always check capital utilization.",
    doc_link: "docs/BACKTEST_METHODOLOGY.md",
  },
  exposure: {
    id: "exposure",
    name: "Capital Utilization (Exposure)",
    category: "risk",
    plain_definition: "The average percentage of total portfolio equity invested in stocks versus held in risk-free cash.",
    why_it_matters: "Explains whether low risk is due to superior stock selection or simply holding mostly cash.",
    formula: "mean( (Equity_t - Cash_t) / Equity_t ) over active simulation sessions",
    interpretation: "Higher utilization (~90%) fully deploys capital; lower utilization (~30%) keeps ~70% in cash.",
    limitations: "Low capital utilization reduces portfolio volatility but sacrifices upside during broad bull markets.",
    doc_link: "docs/INDEPENDENT_STRATEGY_AUDIT.md",
  },
  market_regime: {
    id: "market_regime",
    name: "Market Regime Filter",
    category: "momentum",
    plain_definition: "Macro market state classification based on cross-sectional breadth and trend of the Bourse de Tunis.",
    why_it_matters: "Allows the system to scale down risk exposure during market-wide bear or stagnant regimes.",
    formula: "Bullish: benchmark 20s return > 0% AND > 50% of stocks positive. Neutral/Bearish: otherwise.",
    interpretation: "In Bull regimes, up to 10 slots are permitted. In Bear regimes, capital is defensively preserved in cash.",
    limitations: "Simple moving-average regime filters can experience lag at abrupt market turning points.",
    doc_link: "docs/RESEARCH_ROADMAP.md",
  },
  backtest_return: {
    id: "backtest_return",
    name: "Backtest Return (Marked)",
    category: "execution",
    plain_definition: "Simulated cumulative percentage return based on verified historical closing prices minus transaction fees.",
    why_it_matters: "Evaluates how a strategy would have performed over historical 2026 trading sessions.",
    formula: "(Final_Marked_Equity - Initial_Cash) / Initial_Cash (including 0.50% buy and sell fees)",
    interpretation: "Positive return outperforming the equal-weight benchmark indicates potential historical edge.",
    limitations: "Assumes next-open execution capacity at 10% daily volume participation; past results do not guarantee future gains.",
    doc_link: "docs/BACKTEST_METHODOLOGY.md",
  },
  liquidated_return: {
    id: "liquidated_return",
    name: "Liquidated Return",
    category: "execution",
    plain_definition: "Hypothetical return if all open stock positions were forcibly sold at the final session close minus exit costs.",
    why_it_matters: "Reveals true realizable cash return without relying on unrealized mark-to-market valuations.",
    formula: "(Cash_After_Selling_All_Positions_Minus_Fees - Initial_Cash) / Initial_Cash",
    interpretation: "Always slightly lower than marked return due to final liquidation fees (0.50%) and slippage (0.10%).",
    limitations: "Assumes full final-day liquidation is possible, which may not hold for large positions in thin stocks.",
    doc_link: "docs/BACKTEST_METHODOLOGY.md",
  },
  transaction_fees: {
    id: "transaction_fees",
    name: "Transaction Fees",
    category: "execution",
    plain_definition: "Broker and exchange commission deducted on every executed buy and sell order.",
    why_it_matters: "High portfolio turnover rapidly erodes returns if transaction costs are not modeled strictly.",
    formula: "0.50% (50 basis points) * gross_order_amount (rounded to 0.001 TND)",
    interpretation: "Mandatory fee applied in the Tunis Bourse Challenge virtual competition simulator.",
    limitations: "Does not include VAT or minimum ticket charges that may apply in real live brokerage accounts.",
    doc_link: "docs/COMPETITION_RULES_CHECKLIST.md",
  },
  slippage: {
    id: "slippage",
    name: "Execution Slippage",
    category: "execution",
    plain_definition: "Estimated adverse price movement between signal generation and actual fill in the market order book.",
    why_it_matters: "Protects backtests from unrealistically assuming orders fill exactly at the historical printed price.",
    formula: "0.10% (10 basis points) added to Buy prices and deducted from Sell prices",
    interpretation: "Conservative simulation friction to represent real-world bid-ask spread and market impact.",
    limitations: "In extremely illiquid BVMT stocks with wide spreads, real slippage can exceed 10 basis points.",
    doc_link: "docs/BACKTEST_METHODOLOGY.md",
  },
  walk_forward_testing: {
    id: "walk_forward_testing",
    name: "Walk-Forward Validation",
    category: "execution",
    plain_definition: "Rolling simulation technique that tests strategies strictly out-of-sample across multiple historical time slices.",
    why_it_matters: "Prevents data-mining bias and curve-fitting by ensuring the model never sees future prices.",
    formula: "7 rolling folds: 61 sessions training window -> 19 sessions test window -> 19 sessions step",
    interpretation: "Consistent positive returns across folds (e.g. 6/7 positive) indicates strategy robustness.",
    limitations: "2026 archive contains 194 sessions; multi-year history (2020-2025) is needed for full statistical power.",
    doc_link: "docs/BACKTEST_METHODOLOGY.md",
  },
  paper_trading_status: {
    id: "paper_trading_status",
    name: "Forward Paper Trading",
    category: "governance",
    plain_definition: "Live forward observation tracking prospective signals generated daily without risking actual capital.",
    why_it_matters: "Provides definitive out-of-sample proof of strategy behavior before live execution.",
    formula: "Prospective daily signals recorded timestamped as-of session close; verified against subsequent sessions",
    interpretation: "'Tracking': active forward log running. Verifies zero lookahead bias in forward-testing.",
    limitations: "Requires accumulating daily sessions over several calendar weeks to build statistical sample size.",
    doc_link: "docs/STATE.md",
  },
  data_freshness: {
    id: "data_freshness",
    name: "Data Freshness Status",
    category: "governance",
    plain_definition: "Measurement of how up-to-date the local market data is compared to the official BVMT exchange calendar.",
    why_it_matters: "Prevents making trading decisions using stale, delayed, or missing price information.",
    formula: "sessions_behind = count(open completed sessions on calendar after latest imported session)",
    interpretation: "'Current (0 sessions behind)' = up to date. '>= 1 session behind' = stale warning raised.",
    limitations: "Exchange closes at 14:15 Africa/Tunis; official closing files are typically published by 14:45.",
    doc_link: "docs/CANONICAL_DATA_SOURCE_RULES.md",
  },
  source_provenance: {
    id: "source_provenance",
    name: "Source Data Provenance",
    category: "governance",
    plain_definition: "Cryptographic audit trail tracking the exact origin, timestamp, and SHA-256 hash of all imported files.",
    why_it_matters: "Guarantees that market prices have not been fabricated, modified, or corrupted.",
    formula: "SHA-256 hash verified against original HTTP response bytes + recorded retrieved_at timestamp",
    interpretation: "Tier-1 Official: downloaded directly from bvmt.com.tn. Synthetic Demo: labeled sandbox fixtures.",
    limitations: "Provenance verifies file integrity and origin, but cannot fix reporting errors made by the source exchange.",
    doc_link: "docs/CANONICAL_DATA_SOURCE_RULES.md",
  },
  portfolio_reconciliation: {
    id: "portfolio_reconciliation",
    name: "Portfolio Reconciliation",
    category: "reconciliation",
    plain_definition: "Verification that local recorded cash and share quantities match the competition portal bit-for-bit.",
    why_it_matters: "Guarantees that order sizing and cash reservations reflect the exact real account balance.",
    formula: "reconciliation_gap_tnd = abs(website_total_equity - local_ledger_total_equity) (must equal 0.000)",
    interpretation: "'Reconciled': zero discrepancy. 'Discrepancy': requires human review before placing trades.",
    limitations: "Website values reflect displayp.aspx snapshots; intra-session pending fills must be logged manually.",
    doc_link: "docs/MANUAL_TRADING_WORKFLOW.md",
  },
};

interface MetricHelpProps {
  metricId?: string;
  title?: string;
  plainDefinition?: string;
  whyItMatters?: string;
  formula?: string;
  interpretation?: string;
  limitations?: string;
  docLink?: string;
  category?: string;
  className?: string;
  iconClassName?: string;
  align?: "top" | "bottom";
}

export function MetricHelp({
  metricId,
  title,
  plainDefinition,
  whyItMatters,
  formula,
  interpretation,
  limitations,
  docLink,
  category,
  className,
  iconClassName,
  align = "bottom",
}: MetricHelpProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Resolve metric data from built-in dictionary or custom props
  const resolved = metricId && BUILTIN_METRICS[metricId] ? BUILTIN_METRICS[metricId] : null;
  const name = title || resolved?.name || metricId || "Indicator Info";
  const def = plainDefinition || resolved?.plain_definition || "No definition available.";
  const why = whyItMatters || resolved?.why_it_matters;
  const form = formula || resolved?.formula;
  const interp = interpretation || resolved?.interpretation;
  const lim = limitations || resolved?.limitations;
  const doc = docLink || resolved?.doc_link;
  const cat = category || resolved?.category || "metric";

  // Handle clicking outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  // Handle Escape key to close
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpen((prev) => !prev);
    }
  };

  return (
    <div
      ref={containerRef}
      className={cn("relative inline-flex items-center", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={`Learn about ${name}`}
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        onKeyDown={handleKeyDown}
        className={cn(
          "inline-flex items-center justify-center p-0.5 rounded text-slate-400 hover:text-teal-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 transition-colors",
          "dark:text-slate-400 dark:hover:text-teal-400",
          iconClassName
        )}
      >
        <HelpCircle className="h-3.5 w-3.5" />
      </button>

      {/* Accessible Popover Overlay */}
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          className={cn(
            "absolute z-50 w-80 sm:w-96 rounded-xl border p-4 shadow-xl text-left transition-all duration-150 animate-in fade-in-0 zoom-in-95",
            align === "top"
              ? "bottom-full mb-2 left-1/2 -translate-x-1/2"
              : "top-full mt-2 -right-2 sm:right-0",
            "bg-white border-slate-200 text-slate-850 shadow-slate-200/50",
            "dark:bg-slate-900 dark:border-slate-800 dark:text-slate-100 dark:shadow-black/60"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-2.5 mb-3">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{name}</h4>
                <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  {cat}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 focus:outline-none"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Body Content */}
          <div className="space-y-2.5 text-xs">
            {/* Plain definition */}
            <p className="text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
              {def}
            </p>

            {/* Why it matters */}
            {why && (
              <div>
                <span className="font-semibold text-slate-900 dark:text-slate-200 block text-[11px] mb-0.5">
                  Why it matters:
                </span>
                <p className="text-slate-600 dark:text-slate-400 leading-normal">{why}</p>
              </div>
            )}

            {/* Formula */}
            {form && (
              <div>
                <span className="font-semibold text-slate-900 dark:text-slate-200 block text-[11px] mb-0.5">
                  Formula / Definition:
                </span>
                <code className="block rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 p-2 font-mono text-[11px] text-teal-800 dark:text-teal-300 break-all select-all">
                  {form}
                </code>
              </div>
            )}

            {/* Interpretation */}
            {interp && (
              <div>
                <span className="font-semibold text-slate-900 dark:text-slate-200 block text-[11px] mb-0.5">
                  How to interpret:
                </span>
                <p className="text-slate-600 dark:text-slate-400 leading-normal">{interp}</p>
              </div>
            )}

            {/* Limitations Box */}
            {lim && (
              <div className="rounded-lg bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 p-2.5 flex items-start gap-2">
                <AlertCircle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <div className="text-[11px] text-amber-900 dark:text-amber-300 leading-tight">
                  <span className="font-semibold block mb-0.5">Limitations:</span>
                  {lim}
                </div>
              </div>
            )}

            {/* Documentation Reference Link */}
            {doc && (
              <div className="pt-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                <span>Methodology Reference</span>
                <span className="inline-flex items-center gap-1 text-teal-600 dark:text-teal-400 hover:underline">
                  <ExternalLink className="h-3 w-3" />
                  {doc.replace("docs/", "")}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
