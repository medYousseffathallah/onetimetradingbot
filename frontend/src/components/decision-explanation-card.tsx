"use client";

import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileSearch,
  Info,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import {
  ManualTradePlan,
  ResearchDecisionExplanation,
  StockRankingItem,
  UnifiedResearchStatus,
} from "@/lib/api";
import { Badge } from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";
import { formatPct, formatTnd } from "@/lib/utils";

interface DecisionExplanationCardProps {
  symbol: string;
  ranking?: StockRankingItem;
  plan?: ManualTradePlan;
  explanation?: ResearchDecisionExplanation | null;
  className?: string;
}

function buildFallbackExplanation(
  symbol: string,
  ranking?: StockRankingItem,
  plan?: ManualTradePlan
): ResearchDecisionExplanation {
  if (ranking) {
    const missingData: string[] = [];
    const supporting: string[] = [];
    const contradicting: string[] = [];

    const hasShort = ranking.short_return_pct !== null && ranking.short_return_pct !== "";
    const hasLong = ranking.long_return_pct !== null && ranking.long_return_pct !== "";
    const quoteAge = ranking.quote_age_sessions ?? 0;
    const isRestricted =
      ranking.data_quality_status === "RESTRICTED_SEGMENT" ||
      ranking.competition_eligibility === "MARKET_RESTRICTED" ||
      ranking.execution_feasibility === "MARKET_RESTRICTED";
    const isZeroOrMissing =
      ranking.data_quality_status === "NO_BARS" ||
      ranking.research_coverage_status === "MISSING_DATA";

    if (!hasShort || !hasLong || ranking.data_quality_status === "MISSING_SESSIONS") {
      missingData.push(
        "Complete point-in-time 20-session or 60-session price windows contain gaps or untraded anchors (missing values remain N/A, never zero)."
      );
    }
    if (quoteAge > 0) {
      missingData.push(
        `No new transaction for ${quoteAge} session(s); latest observed trade was on ${
          ranking.last_traded_date ?? "an earlier session"
        }.`
      );
    }
    missingData.push(
      "Issuer CMF financial filings and earnings disclosures are unavailable locally."
    );

    if (ranking.last_traded_price_tnd ?? ranking.close_tnd) {
      supporting.push(
        `Last verified traded price: ${formatTnd(
          ranking.last_traded_price_tnd ?? ranking.close_tnd
        )}${ranking.last_traded_date ? ` (${ranking.last_traded_date})` : ""}.`
      );
    }
    if (hasShort && parseFloat(ranking.short_return_pct || "0") > 0) {
      supporting.push(
        `Positive 20-session price momentum (${formatPct(ranking.short_return_pct)}).`
      );
    } else if (
      ranking.observed_trade_return_pct &&
      parseFloat(ranking.observed_trade_return_pct) > 0
    ) {
      supporting.push(
        `Positive observed trade-to-trade return (${formatPct(
          ranking.observed_trade_return_pct
        )} across ${ranking.observed_trade_interval_sessions ?? "—"} sessions).`
      );
    }
    if (ranking.rationale && ranking.rationale.length > 0) {
      supporting.push(...ranking.rationale.slice(0, 2));
    }
    if (supporting.length === 0) {
      supporting.push(
        "Included in continuous research tracking without extrapolating missing observations."
      );
    }

    if (ranking.blocked_reasons && ranking.blocked_reasons.length > 0) {
      contradicting.push(...ranking.blocked_reasons);
    }
    if (hasShort && parseFloat(ranking.short_return_pct || "0") < 0) {
      contradicting.push(
        `Negative trailing 20-session momentum (${formatPct(ranking.short_return_pct)}).`
      );
    }
    if (hasLong && parseFloat(ranking.long_return_pct || "0") < 0) {
      contradicting.push(
        `Negative trailing 60-session trend (${formatPct(ranking.long_return_pct)}).`
      );
    }
    if (
      ranking.execution_feasibility &&
      ranking.execution_feasibility !== "FEASIBLE"
    ) {
      contradicting.push(
        `Execution constraint flagged (${ranking.execution_feasibility.replaceAll("_", " ")}).`
      );
    }
    if (contradicting.length === 0 && !ranking.eligible) {
      contradicting.push(
        "Does not currently pass all strategy eligibility and liquidity filters."
      );
    }

    let researchStatus: UnifiedResearchStatus = "PARTIAL_RESEARCH_AVAILABLE";
    let statusLabel = "Partial data";
    if (isRestricted) {
      researchStatus = "RESTRICTED_FOR_TRADING";
      statusLabel = "Restricted for trading";
    } else if (isZeroOrMissing) {
      researchStatus = "INSUFFICIENT_EVIDENCE";
      statusLabel = "Insufficient evidence";
    } else if (ranking.research_coverage_status === "FULL_COVERAGE" && hasShort && hasLong) {
      researchStatus = "FULL_RESEARCH_AVAILABLE";
      statusLabel = "Full data";
    }

    const priceStatus =
      hasShort && hasLong && ranking.data_quality_status !== "MISSING_SESSIONS"
        ? "Complete (20s & 60s verified)"
        : "Incomplete";
    const liquidityStatus =
      ranking.execution_feasibility === "FEASIBLE" &&
      ranking.eligible &&
      quoteAge === 0
        ? "Verified (active turnover)"
        : "Requires verification";
    const isTradable =
      Boolean(ranking.eligible) &&
      Boolean(ranking.in_challenge_universe) &&
      !isRestricted &&
      ranking.execution_feasibility === "FEASIBLE";

    return {
      model_version: "client_summary_v1",
      research_status: researchStatus,
      research_status_label: statusLabel,
      price_indicators_status: priceStatus,
      fundamental_evidence_status: "Unavailable locally",
      event_evidence_status: "Unavailable locally",
      liquidity_status: liquidityStatus,
      trading_eligibility_status: isTradable
        ? "Separately verified (Eligible)"
        : ranking.in_challenge_universe === false
        ? "Excluded from Challenge Universe"
        : "Separately verified (Research Only)",
      why_interesting: supporting[0] ?? `${symbol} is tracked in the BVMT research monitor.`,
      why_uncertain:
        missingData[0] ??
        "Historical liquidity, event disclosures, and price trends may shift without intraday visibility.",
      missing_data: missingData,
      supporting_evidence: supporting,
      contradicting_evidence:
        contradicting.length > 0
          ? contradicting
          : ["No disqualifying quantitative contradictions detected on local daily bars."],
      is_tradable: isTradable,
      execution_risk:
        quoteAge > 0 || liquidityStatus !== "Verified (active turnover)"
          ? `Thin or intermittent liquidity${
              ranking.median_turnover_tnd
                ? ` (20s median ${formatTnd(ranking.median_turnover_tnd)})`
                : ""
            }; manual order book depth and BVMT price collars (±6% / limit reservations) must be checked before placing any limit order.`
          : `Active continuous segment with verified turnover${
              ranking.median_turnover_tnd
                ? ` (${formatTnd(ranking.median_turnover_tnd)} 20s median)`
                : ""
            }; standard slippage and limit-collar risk applies.`,
      review_trigger:
        quoteAge > 0 || !isTradable
          ? "Review after the next verified BVMT EOD close showing active volume/turnover or after verified CMF issuer disclosure."
          : "Re-evaluate at the next 20-session review horizon or upon significant turnover/price regime change.",
      non_buy_notice:
        "Research classification only — never an automated BUY signal. Human verification required.",
    };
  }

  // Fallback derived cleanly from ManualTradePlan
  if (plan) {
    const missingData: string[] = [
      "Local issuer financial statements (CMF disclosures) are unavailable locally unless indexed in Stock Research.",
    ];
    if (plan.quote_age_sessions > 0) {
      missingData.push(
        `Quote age is ${plan.quote_age_sessions} session(s) old (${plan.data_timestamp}).`
      );
    }
    const isTradable = Boolean(plan.is_actionable) && plan.suggested_max_shares > 0;
    const researchStatus: UnifiedResearchStatus = plan.in_challenge_universe === false
      ? "RESTRICTED_FOR_TRADING"
      : isTradable
      ? "FULL_RESEARCH_AVAILABLE"
      : "PARTIAL_RESEARCH_AVAILABLE";

    return {
      model_version: plan.model_version || "manual_plan_summary",
      research_status: researchStatus,
      research_status_label:
        researchStatus === "FULL_RESEARCH_AVAILABLE"
          ? "Full data"
          : researchStatus === "RESTRICTED_FOR_TRADING"
          ? "Restricted for trading"
          : "Partial data",
      price_indicators_status: plan.composite_score ? "Complete (Model scored)" : "Incomplete",
      fundamental_evidence_status: "Unavailable locally",
      event_evidence_status: "Unavailable locally",
      liquidity_status:
        plan.execution_feasibility_status === "FEASIBLE" && plan.suggested_max_shares > 0
          ? "Verified (sized against 10% cap)"
          : "Requires verification",
      trading_eligibility_status: isTradable
        ? `Separately verified (${plan.order_entry_eligibility ?? "Eligible"})`
        : "Separately verified (Not Actionable)",
      why_interesting:
        plan.supporting_evidence[0] ??
        `Candidate evaluated under ${plan.model_name} with break-even at ${formatTnd(
          plan.break_even_price_tnd
        )}.`,
      why_uncertain:
        plan.liquidity_warnings[0] ??
        plan.execution_warnings[0] ??
        "Daily EOD snapshot does not show real-time order book depth during trading hours.",
      missing_data: missingData,
      supporting_evidence:
        plan.supporting_evidence.length > 0
          ? plan.supporting_evidence
          : [`Reference EOD close: ${formatTnd(plan.last_verified_price_tnd)}.`],
      contradicting_evidence:
        plan.rejection_reasons.length > 0
          ? plan.rejection_reasons
          : plan.liquidity_warnings.length > 0
          ? plan.liquidity_warnings
          : ["Monitor 0.50% buy + 0.50% sell fee drag and 10% concentration ceiling."],
      is_tradable: isTradable,
      execution_risk: `Binding cap: ${plan.binding_constraint}. ${
        plan.execution_warnings[0] ??
        "Verify live bid/ask liquidity inside the Tunis Bourse Challenge portal before entering manual limit orders."
      }`,
      review_trigger: `Review at ${plan.review_date} (${plan.intended_holding_horizon_sessions} sessions) or stop-loss ${formatTnd(
        plan.exit_conditions.stop_loss_price_tnd
      )}.`,
      non_buy_notice:
        "Decision support plan only — zero autonomous orders are placed.",
    };
  }

  return {
    model_version: "fallback",
    research_status: "INSUFFICIENT_EVIDENCE",
    research_status_label: "Insufficient evidence",
    price_indicators_status: "Incomplete",
    fundamental_evidence_status: "Unavailable locally",
    event_evidence_status: "Unavailable locally",
    liquidity_status: "Requires verification",
    trading_eligibility_status: "Separately verified (Requires review)",
    why_interesting: `${symbol} has limited structured coverage in this view.`,
    why_uncertain: "Insufficient point-in-time market or disclosure evidence loaded.",
    missing_data: ["Market quotation history and CMF issuer filings unavailable in current payload."],
    supporting_evidence: ["Security tracked for explicit missing-data transparency."],
    contradicting_evidence: ["Cannot establish trend or executable liquidity yet."],
    is_tradable: false,
    execution_risk: "Cannot assess execution capacity without verified trailing volume.",
    review_trigger: "Review once verified market sessions and liquidity observations arrive.",
    non_buy_notice: "Informational summary only — not a BUY signal.",
  };
}

function statusBadgeVariant(
  status: UnifiedResearchStatus
): "success" | "info" | "warning" | "danger" | "default" {
  switch (status) {
    case "FULL_RESEARCH_AVAILABLE":
      return "success";
    case "PARTIAL_RESEARCH_AVAILABLE":
      return "info";
    case "EVENT_RESEARCH_AVAILABLE":
      return "warning";
    case "RESTRICTED_FOR_TRADING":
      return "danger";
    case "INSUFFICIENT_EVIDENCE":
    default:
      return "default";
  }
}

export function DecisionExplanationCard({
  symbol,
  ranking,
  plan,
  explanation,
  className = "",
}: DecisionExplanationCardProps) {
  const detail = explanation ?? buildFallbackExplanation(symbol, ranking, plan);

  return (
    <div
      className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-4 space-y-4 ${className}`}
    >
      {/* Top Status & Separation Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-2.5 border-b border-slate-100 dark:border-slate-800 pb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="inline-flex items-center gap-1.5">
            <Badge variant={statusBadgeVariant(detail.research_status)} className="text-xs font-semibold">
              Research status: {detail.research_status_label}
            </Badge>
            <MetricHelp metricId="research_status_taxonomy" />
          </div>

          <div className="inline-flex items-center gap-1.5">
            <Badge
              variant={detail.is_tradable ? "success" : "outline"}
              className="text-xs"
            >
              Trading eligibility: {detail.trading_eligibility_status}
            </Badge>
            <MetricHelp metricId="trading_eligibility_separation" />
          </div>
        </div>

        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 dark:text-slate-400">
          <Info className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400 shrink-0" />
          <span>{detail.non_buy_notice}</span>
        </span>
      </div>

      {/* 4 Independent Evidence Pillars (Plain Language) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs">
        <div className="rounded-lg bg-slate-50 dark:bg-slate-900/70 border border-slate-200/80 dark:border-slate-800 p-2.5">
          <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">
            <span>Price-based indicators</span>
            <MetricHelp metricId="price_indicators_completeness" />
          </div>
          <div className="font-semibold text-slate-900 dark:text-slate-100">
            {detail.price_indicators_status}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 dark:bg-slate-900/70 border border-slate-200/80 dark:border-slate-800 p-2.5">
          <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">
            <span>Fundamental evidence</span>
            <MetricHelp metricId="fundamental_evidence" />
          </div>
          <div className="font-semibold text-slate-900 dark:text-slate-100">
            {detail.fundamental_evidence_status}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 dark:bg-slate-900/70 border border-slate-200/80 dark:border-slate-800 p-2.5">
          <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">
            <span>Event evidence</span>
            <MetricHelp metricId="event_disclosure_evidence" />
          </div>
          <div className="font-semibold text-slate-900 dark:text-slate-100">
            {detail.event_evidence_status}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 dark:bg-slate-900/70 border border-slate-200/80 dark:border-slate-800 p-2.5">
          <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">
            <span>Liquidity</span>
            <MetricHelp metricId="execution_risk" />
          </div>
          <div className="font-semibold text-slate-900 dark:text-slate-100">
            {detail.liquidity_status}
          </div>
        </div>
      </div>

      {/* 8-Question Structured Decision Brief */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg border border-teal-200/70 dark:border-teal-900/50 bg-teal-50/30 dark:bg-teal-950/20 p-3 space-y-1">
          <div className="font-semibold text-teal-900 dark:text-teal-200 flex items-center gap-1.5">
            <TrendingUp className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400 shrink-0" />
            <span>Why is this stock interesting?</span>
          </div>
          <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
            {detail.why_interesting}
          </p>
        </div>

        <div className="rounded-lg border border-amber-200/70 dark:border-amber-900/50 bg-amber-50/30 dark:bg-amber-950/20 p-3 space-y-1">
          <div className="font-semibold text-amber-900 dark:text-amber-200 flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
            <span>Why is the model uncertain?</span>
          </div>
          <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
            {detail.why_uncertain}
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40 p-3 space-y-1.5">
          <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
            <FileSearch className="h-3.5 w-3.5 text-slate-500 shrink-0" />
            <span>What data is missing?</span>
          </div>
          <ul className="space-y-1 text-slate-600 dark:text-slate-300">
            {detail.missing_data.map((item, i) => (
              <li key={i} className="leading-snug">
                • {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40 p-3 space-y-1.5">
          <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>What evidence supports the opportunity?</span>
          </div>
          <ul className="space-y-1 text-slate-600 dark:text-slate-300">
            {detail.supporting_evidence.map((item, i) => (
              <li key={i} className="leading-snug">
                • {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40 p-3 space-y-1.5">
          <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
            <ShieldAlert className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>What evidence contradicts it?</span>
          </div>
          <ul className="space-y-1 text-slate-600 dark:text-slate-300">
            {detail.contradicting_evidence.map((item, i) => (
              <li key={i} className="leading-snug">
                • {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40 p-3 space-y-2">
          <div>
            <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5 mb-0.5">
              <ShieldCheck className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400 shrink-0" />
              <span>Is it actually tradable &amp; what is the execution risk?</span>
            </div>
            <p className="text-slate-600 dark:text-slate-300 leading-snug">
              <strong className="text-slate-800 dark:text-slate-200">
                {detail.is_tradable ? "Tradable with human verification:" : "Not currently actionable for auto-sizing:"}
              </strong>{" "}
              {detail.execution_risk}
            </p>
          </div>
          <div className="pt-1 border-t border-slate-200/70 dark:border-slate-800">
            <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5 mb-0.5">
              <Clock className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
              <span>When should the position be reviewed?</span>
            </div>
            <p className="text-slate-600 dark:text-slate-300 leading-snug">
              {detail.review_trigger}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

