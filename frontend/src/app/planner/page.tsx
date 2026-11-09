"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Calculator,
  ShieldAlert,
  Clock,
  TrendingUp,
  AlertTriangle,
  Info,
  CheckCircle2,
  Calendar,
  Layers,
  Percent,
  Coins,
  Scale,
  ArrowRight,
  Sliders,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { usePortfolioMode } from "@/components/app-shell";
import {
  api,
  ManualTradePlan,
  TradePlansResponse,
  HoldingPeriodResearchReport,
  HoldingPeriodHorizonMetric,
} from "@/lib/api";
import { formatTnd, formatPct } from "@/lib/utils";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Badge,
  Button,
} from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";

export default function TradePlannerPage() {
  const { mode } = usePortfolioMode();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [plansData, setPlansData] = useState<TradePlansResponse | null>(null);
  const [holdingResearch, setHoldingResearch] = useState<HoldingPeriodResearchReport | null>(null);
  const [selectedUniverse, setSelectedUniverse] = useState<"TUNIS_BOURSE_CHALLENGE" | "FULL_BVMT">("TUNIS_BOURSE_CHALLENGE");
  const [activeTab, setActiveTab] = useState<"MANUAL_ORDER_PLAN" | "PAPER_TRADE_CANDIDATE" | "RESEARCH_CANDIDATE">("MANUAL_ORDER_PLAN");
  const [showHoldingResearch, setShowHoldingResearch] = useState(false);

  // Interactive Calculator State
  const [selectedPlan, setSelectedPlan] = useState<ManualTradePlan | null>(null);
  const [customLimitPrice, setCustomLimitPrice] = useState<string>("");
  const [customAllocationRatio, setCustomAllocationRatio] = useState<string>("0.0850");
  const [customRiskBudget, setCustomRiskBudget] = useState<string>("");
  const [customHorizon, setCustomHorizon] = useState<number>(20);
  const [calculating, setCalculating] = useState(false);
  const [calculatedPlan, setCalculatedPlan] = useState<ManualTradePlan | null>(null);

  useEffect(() => {
    let active = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [plansRes, holdingRes] = await Promise.all([
          api.getTradePlans(mode, selectedUniverse),
          api.getHoldingPeriods(selectedUniverse),
        ]);
        if (active) {
          setPlansData(plansRes);
          setHoldingResearch(holdingRes);
          // Default select the top actionable plan if available
          const topActionable = plansRes.plans.find((p) => p.is_actionable);
          if (topActionable) {
            setSelectedPlan(topActionable);
            setCustomLimitPrice(topActionable.proposed_limit_price_tnd);
            setCustomHorizon(topActionable.intended_holding_horizon_sessions);
            setCalculatedPlan(topActionable);
          } else if (plansRes.plans.length > 0) {
            setSelectedPlan(plansRes.plans[0]);
            setCustomLimitPrice(plansRes.plans[0].proposed_limit_price_tnd);
            setCustomHorizon(plansRes.plans[0].intended_holding_horizon_sessions);
            setCalculatedPlan(plansRes.plans[0]);
          }
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load trade plans.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    loadData();
    return () => {
      active = false;
    };
  }, [mode, selectedUniverse]);

  // Handle plan selection in calculator
  const handleSelectPlan = (plan: ManualTradePlan) => {
    setSelectedPlan(plan);
    setCustomLimitPrice(plan.proposed_limit_price_tnd);
    setCustomHorizon(plan.intended_holding_horizon_sessions);
    setCalculatedPlan(plan);
  };

  // Recalculate on-the-fly
  const handleRecalculate = async () => {
    if (!selectedPlan || !customLimitPrice) return;
    setCalculating(true);
    try {
      const res = await api.calculateTradePlan({
        instrument_id: selectedPlan.instrument_id,
        symbol: selectedPlan.symbol,
        limit_price_tnd: customLimitPrice,
        target_weight_ratio: customAllocationRatio,
        risk_budget_tnd: customRiskBudget.trim() ? customRiskBudget : null,
        intended_holding_horizon_sessions: customHorizon,
        portfolio_mode: mode,
        universe: selectedUniverse,
      });
      setCalculatedPlan(res);
    } catch (err) {
      console.error("Recalculation error:", err);
    } finally {
      setCalculating(false);
    }
  };

  // Filter plans by category
  const filteredPlans = useMemo(() => {
    if (!plansData) return [];
    return plansData.plans.filter((p) => {
      if (activeTab === "MANUAL_ORDER_PLAN") return p.plan_category === "MANUAL_ORDER_PLAN";
      if (activeTab === "PAPER_TRADE_CANDIDATE") return p.plan_category === "PAPER_TRADE_CANDIDATE";
      return p.plan_category === "RESEARCH_CANDIDATE";
    });
  }, [plansData, activeTab]);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Trade Planning & Position Sizing
            </h2>
            <Badge variant="warning" className="gap-1 px-2.5 py-0.5 text-xs font-medium">
              <ShieldAlert className="h-3.5 w-3.5" />
              <span>100% Manual Execution — Zero Autonomous Orders</span>
            </Badge>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Deterministic order sizing, round-trip fee accounting, holding horizon planning, and explicit risk exits for the Tunis Bourse Challenge.
          </p>

          {/* Challenge Universe Mode Toggle */}
          <div className="flex flex-wrap items-center gap-2 mt-2.5">
            <div className="inline-flex rounded-lg border border-slate-300 dark:border-slate-700 p-0.5 bg-slate-100 dark:bg-slate-800">
              <button
                type="button"
                onClick={() => setSelectedUniverse("TUNIS_BOURSE_CHALLENGE")}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                  selectedUniverse === "TUNIS_BOURSE_CHALLENGE"
                    ? "bg-teal-600 text-white shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                }`}
              >
                Tunis Bourse Challenge (42 Equities)
              </button>
              <button
                type="button"
                onClick={() => setSelectedUniverse("FULL_BVMT")}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                  selectedUniverse === "FULL_BVMT"
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                }`}
              >
                Full BVMT Research (76 Equities)
              </button>
            </div>
            {selectedUniverse === "TUNIS_BOURSE_CHALLENGE" ? (
              <Badge variant="success" className="text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300">
                Official Challenge Universe (42 Observed)
              </Badge>
            ) : (
              <Badge variant="warning" className="text-xs font-medium">
                Full Research Universe — Non-Challenge Orders Blocked
              </Badge>
            )}
          </div>
        </div>

        {plansData && (
          <div className="text-right">
            <div className="text-xs text-slate-500 dark:text-slate-400">Decision Session Cutoff</div>
            <div className="font-mono font-semibold text-slate-900 dark:text-slate-100">
              {plansData.session_date} (09:00 Africa/Tunis)
            </div>
          </div>
        )}
      </div>

      {/* Plain-Language Operational Notice */}
      <div className="rounded-xl border border-teal-200/80 bg-teal-50/70 dark:border-teal-900/60 dark:bg-teal-950/30 p-4 text-xs text-teal-900 dark:text-teal-200 flex items-start gap-3 shadow-xs">
        <Info className="h-4 w-4 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
        <div className="leading-relaxed space-y-1">
          <div>
            <span className="font-semibold text-teal-950 dark:text-teal-100">
              Human-Supervised Decision Support:
            </span>{" "}
            All values are calculated with zero lookahead from verified official BVMT session closes. Position sizes respect competition cash, a 10% single-stock cap (8.5% target), 10% daily volume participation, and 0.50% purchase + 0.50% sale fees.
          </div>
          <div className="text-teal-800 dark:text-teal-300">
            Never place market orders on BVMT. Use the calculator below to size limit orders at or near verified reference prices.
          </div>
        </div>
      </div>

      {/* Top Capital & Execution KPI Cards */}
      {plansData && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Total Account Equity</CardDescription>
                <MetricHelp metricId="cash_and_liquidity" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {formatTnd(plansData.portfolio_total_equity_tnd)}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              Locally marked against verified BVMT quotes
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Available Purchasing Cash</CardDescription>
                <MetricHelp metricId="cash_and_liquidity" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-teal-700 dark:text-teal-400">
                {formatTnd(plansData.effective_cash_tnd)}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              {Number(plansData.reserved_cash_tnd) > 0 ? (
                <span className="text-amber-600 font-medium">
                  {formatTnd(plansData.reserved_cash_tnd)} reserved for open orders
                </span>
              ) : (
                "100% available — 0.000 TND pending commitments"
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Max Single-Stock Cap (10%)</CardDescription>
                <MetricHelp metricId="concentration_ratio" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {formatTnd((Number(plansData.portfolio_total_equity_tnd) * 0.10).toFixed(3))}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              Safe Target (8.5%):{" "}
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                {formatTnd((Number(plansData.portfolio_total_equity_tnd) * 0.085).toFixed(3))}
              </span>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Review Horizon</CardDescription>
                <MetricHelp metricId="holding_period" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-amber-600 dark:text-amber-400">
                20 Sessions (~1 Mo)
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400 flex items-center justify-between">
              <span>Empirical fee-optimal window</span>
              <button
                type="button"
                onClick={() => setShowHoldingResearch((prev) => !prev)}
                className="text-teal-600 hover:text-teal-800 font-medium underline"
              >
                {showHoldingResearch ? "Hide Evidence" : "View Evidence"}
              </button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Expandable Holding Period Empirical Research Section */}
      {showHoldingResearch && holdingResearch && (
        <Card className="border-amber-200/90 bg-amber-50/40 dark:border-amber-900/60 dark:bg-amber-950/20 shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base text-amber-950 dark:text-amber-200 flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-amber-600" />
                  <span>Empirical Holding-Period Evaluation (Model G on 194 BVMT Sessions)</span>
                </CardTitle>
                <CardDescription className="text-xs text-amber-800/80 dark:text-amber-300/80 mt-1">
                  Comparing turnover, transaction fee drag, drawdown, and outlier sensitivity across 6 holding horizons.
                </CardDescription>
              </div>
              <Badge variant="warning" className="text-xs font-mono">
                {holdingResearch.verdict}
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="space-y-4 text-xs">
            {/* Horizon Comparison Table */}
            <div className="overflow-x-auto rounded-lg border border-amber-200 dark:border-amber-800/60 bg-white dark:bg-slate-900">
              <table className="w-full text-left">
                <thead className="bg-amber-100/60 dark:bg-slate-800/80 font-semibold text-slate-700 dark:text-slate-300 border-b border-amber-200 dark:border-amber-800">
                  <tr>
                    <th className="py-2.5 px-3">Horizon</th>
                    <th className="py-2.5 px-3 text-right">Net Return</th>
                    <th className="py-2.5 px-3 text-right">Liquidated</th>
                    <th className="py-2.5 px-3 text-right">Max Drawdown</th>
                    <th className="py-2.5 px-3 text-right">Total Fees</th>
                    <th className="py-2.5 px-3 text-right">Turnover</th>
                    <th className="py-2.5 px-3 text-center">Fills</th>
                    <th className="py-2.5 px-center">Win Rate</th>
                    <th className="py-2.5 px-3">Top Winner Share</th>
                    <th className="py-2.5 px-3">Feasibility</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                  {holdingResearch.horizons.map((h) => {
                    const isOptimal = h.horizon_sessions === 19 || h.horizon_sessions === 20;
                    return (
                      <tr
                        key={h.horizon_sessions}
                        className={isOptimal ? "bg-teal-50/50 dark:bg-teal-950/30 font-semibold" : "hover:bg-slate-50/50"}
                      >
                        <td className="py-2.5 px-3 font-sans">
                          {h.horizon_label}
                          {isOptimal && (
                            <span className="ml-1.5 inline-block text-[10px] text-teal-700 dark:text-teal-300 font-medium bg-teal-100 dark:bg-teal-900/60 px-1.5 py-0.2 rounded">
                              Recommended
                            </span>
                          )}
                        </td>
                        <td className={`py-2.5 px-3 text-right ${h.net_return_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                          {h.net_return_pct >= 0 ? `+${h.net_return_pct}%` : `${h.net_return_pct}%`}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">
                          {h.liquidated_return_pct >= 0 ? `+${h.liquidated_return_pct}%` : `${h.liquidated_return_pct}%`}
                        </td>
                        <td className="py-2.5 px-3 text-right text-amber-600">
                          {h.max_drawdown_pct}%
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-900 dark:text-slate-100 font-semibold">
                          {formatTnd(h.total_fees_tnd)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">
                          {h.turnover_ratio}x
                        </td>
                        <td className="py-2.5 px-3 text-center">{h.trade_count}</td>
                        <td className="py-2.5 px-3 text-center text-slate-700 dark:text-slate-300">
                          {h.hit_rate_pct}%
                        </td>
                        <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400 font-sans">
                          {h.top_winner_symbol} ({h.top_winner_pnl_share_pct}%)
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              h.execution_feasibility_score === "GOOD"
                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                                : h.execution_feasibility_score === "MODERATE"
                                ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                                : "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
                            }`}
                          >
                            {h.execution_feasibility_score}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Scientific Caveats and Reasoning */}
            <div className="space-y-1.5 text-slate-600 dark:text-slate-400 leading-relaxed">
              <div className="font-semibold text-slate-900 dark:text-slate-100">
                Key Empirical Insights:
              </div>
              {holdingResearch.reasoning.map((r, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-teal-600 dark:text-teal-400 font-bold">•</span>
                  <span>{r}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Content: Interactive Calculator + Candidate Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Sizing & Cost Calculator (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="border-teal-200/90 dark:border-teal-900/60 shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2 text-slate-900 dark:text-slate-100">
                  <Calculator className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                  <span>Manual Order Sizing Calculator</span>
                </CardTitle>
                <Badge variant="outline" className="text-[11px] font-mono">
                  {selectedPlan ? selectedPlan.symbol : "Select Candidate"}
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Adjust limit price, target allocation, and horizon to test hypothetical execution costs.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4 pt-4 text-xs">
              {selectedPlan ? (
                <>
                  {/* Inputs Grid */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                        Intended Limit Price (TND)
                      </label>
                      <input
                        type="number"
                        step="0.010"
                        min="0.001"
                        value={customLimitPrice}
                        onChange={(e) => setCustomLimitPrice(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-2.5 py-1.5 font-mono text-xs focus:border-teal-500 focus:outline-none"
                      />
                      <span className="text-[10px] text-slate-400">Ref: {formatTnd(selectedPlan.last_verified_price_tnd)}</span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                        Target Allocation
                      </label>
                      <select
                        value={customAllocationRatio}
                        onChange={(e) => setCustomAllocationRatio(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-xs font-mono focus:border-teal-500 focus:outline-none"
                      >
                        <option value="0.0500">5.0% (Conservative)</option>
                        <option value="0.0850">8.5% (Target Buffer)</option>
                        <option value="0.1000">10.0% (Hard Max Cap)</option>
                      </select>
                      <span className="text-[10px] text-slate-400">Cap: 10.0% max</span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                        Review Horizon (Sessions)
                      </label>
                      <select
                        value={customHorizon}
                        onChange={(e) => setCustomHorizon(Number(e.target.value))}
                        className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-xs font-mono focus:border-teal-500 focus:outline-none"
                      >
                        <option value={10}>10 sessions (2 weeks)</option>
                        <option value={20}>20 sessions (~1 month)</option>
                        <option value={40}>40 sessions (2 months)</option>
                      </select>
                      <span className="text-[10px] text-slate-400">Time stop window</span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                        Risk Budget (TND, Opt.)
                      </label>
                      <input
                        type="number"
                        step="50"
                        min="0"
                        placeholder="e.g. 500"
                        value={customRiskBudget}
                        onChange={(e) => setCustomRiskBudget(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-2.5 py-1.5 font-mono text-xs focus:border-teal-500 focus:outline-none"
                      />
                      <span className="text-[10px] text-slate-400">Max portfolio risk</span>
                    </div>
                  </div>

                  <Button
                    onClick={handleRecalculate}
                    disabled={calculating}
                    variant="outline"
                    className="w-full justify-center gap-1.5 py-1.5 text-xs border-teal-600 text-teal-700 hover:bg-teal-50 dark:hover:bg-teal-950/40"
                  >
                    <Sliders className="h-3.5 w-3.5" />
                    <span>{calculating ? "Recalculating..." : "Recalculate Size & Friction"}</span>
                  </Button>

                  {/* Calculated Output Breakdown */}
                  {calculatedPlan && (
                    <div className="space-y-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                      <div className="grid grid-cols-2 gap-2">
                        <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800">
                          <div className="text-[10px] text-slate-500">Suggested Max Quantity</div>
                          <div className="text-base font-bold font-mono text-teal-700 dark:text-teal-400">
                            {calculatedPlan.suggested_max_shares} Shares
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono">
                            Bound by: {calculatedPlan.binding_constraint}
                          </div>
                        </div>

                        <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800">
                          <div className="text-[10px] text-slate-500">Gross Order Value</div>
                          <div className="text-base font-bold font-mono text-slate-900 dark:text-slate-100">
                            {formatTnd(calculatedPlan.estimated_gross_order_value_tnd)}
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono">
                            {calculatedPlan.proposed_position_weight_pct}% total equity
                          </div>
                        </div>
                      </div>

                      {/* Fee and Break-even Breakdown */}
                      <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-1.5 font-mono text-[11px]">
                        <div className="flex justify-between text-slate-600 dark:text-slate-400">
                          <span>Purchase Fee (0.50%):</span>
                          <span className="font-semibold text-rose-600">+{formatTnd(calculatedPlan.estimated_purchase_fee_tnd)}</span>
                        </div>
                        <div className="flex justify-between text-slate-600 dark:text-slate-400">
                          <span>Total Capital Outlay:</span>
                          <span className="font-bold text-slate-900 dark:text-slate-100">{formatTnd(calculatedPlan.estimated_total_purchase_cost_tnd)}</span>
                        </div>
                        <div className="flex justify-between text-slate-600 dark:text-slate-400">
                          <span>Est. Sale Fee (0.50%):</span>
                          <span className="text-rose-600">+{formatTnd(calculatedPlan.estimated_sale_fee_tnd)}</span>
                        </div>
                        <div className="border-t border-slate-100 dark:border-slate-800 pt-1.5 flex justify-between font-semibold">
                          <span className="text-amber-700 dark:text-amber-400">Break-Even Exit Price:</span>
                          <span className="text-amber-700 dark:text-amber-400">{formatTnd(calculatedPlan.break_even_price_tnd)} ({calculatedPlan.break_even_gain_pct}%)</span>
                        </div>
                        <div className="flex justify-between text-slate-500 text-[10px]">
                          <span>Remaining Cash After Trade:</span>
                          <span>{formatTnd(calculatedPlan.cash_remaining_after_purchase_tnd)}</span>
                        </div>
                      </div>

                      {/* Explicit Risk Management Conditions */}
                      <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-2 text-xs">
                        <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center justify-between">
                          <span>Exit & Risk Triggers</span>
                          <span className="text-[10px] font-mono text-slate-500">Review: {calculatedPlan.review_date}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                          <div className="p-2 rounded bg-rose-50/70 border border-rose-200 dark:bg-rose-950/30 dark:border-rose-900/50">
                            <span className="text-rose-700 dark:text-rose-300 font-semibold block">Stop Loss (-5.0%):</span>
                            <span className="text-rose-900 dark:text-rose-100 font-bold">{formatTnd(calculatedPlan.exit_conditions.stop_loss_price_tnd)}</span>
                          </div>
                          <div className="p-2 rounded bg-emerald-50/70 border border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-900/50">
                            <span className="text-emerald-700 dark:text-emerald-300 font-semibold block">Profit Target (+12.0%):</span>
                            <span className="text-emerald-900 dark:text-emerald-100 font-bold">{formatTnd(calculatedPlan.exit_conditions.profit_target_price_tnd)}</span>
                          </div>
                        </div>
                        <p className="text-[10px] text-slate-500 leading-normal">
                          {calculatedPlan.exit_conditions.trailing_support_rule}
                        </p>
                      </div>

                      {/* Warnings or Rejection Reasons */}
                      {calculatedPlan.rejection_reasons.length > 0 && (
                        <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 dark:bg-rose-950/40 dark:border-rose-900 text-xs space-y-1">
                          <span className="font-semibold block">Order Blocked / Sized to 0 Shares:</span>
                          {calculatedPlan.rejection_reasons.map((r, i) => (
                            <div key={i} className="text-[11px] leading-tight">• {r}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="py-12 text-center text-slate-400">
                  Select a candidate from the list to populate the calculator.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Candidate Plan Cards (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Plan Category Tabs */}
          <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
            <button
              type="button"
              onClick={() => setActiveTab("MANUAL_ORDER_PLAN")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeTab === "MANUAL_ORDER_PLAN"
                  ? "bg-teal-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Manual Order Plans (Top Candidates)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("PAPER_TRADE_CANDIDATE")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeTab === "PAPER_TRADE_CANDIDATE"
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Paper-Trade Candidates
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("RESEARCH_CANDIDATE")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeTab === "RESEARCH_CANDIDATE"
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Research Universe
            </button>
          </div>

          {/* Cards List */}
          {loading ? (
            <div className="py-16 text-center text-slate-400">
              <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-teal-600 border-t-transparent mb-2" />
              <p className="text-sm">Calculating portfolio constraints and trade plans...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">
              {error}
            </div>
          ) : filteredPlans.length === 0 ? (
            <div className="py-16 text-center text-slate-500 text-sm">
              No candidates in category {activeTab}.
            </div>
          ) : (
            <div className="space-y-3.5">
              {filteredPlans.map((plan) => {
                const isSelected = selectedPlan?.instrument_id === plan.instrument_id;
                return (
                  <Card
                    key={plan.plan_id}
                    className={`cursor-pointer transition-all border ${
                      isSelected
                        ? "border-teal-500 ring-2 ring-teal-500/20 bg-teal-50/20 dark:bg-teal-950/20"
                        : "hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-950"
                    }`}
                    onClick={() => handleSelectPlan(plan)}
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-xs font-bold text-slate-400">
                              {plan.research_rank ? `#${plan.research_rank}` : "—"}
                            </span>
                            <h3 className="font-bold text-base text-slate-900 dark:text-slate-100">
                              {plan.symbol}
                            </h3>
                            <span className="text-xs text-slate-500 font-mono">({plan.instrument_id})</span>
                            {plan.in_challenge_universe === false ? (
                              <Badge variant="warning" className="text-[10px] font-semibold bg-amber-100 text-amber-900 border-amber-300">
                                Excluded from Challenge Universe
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-[10px] font-semibold bg-teal-50 text-teal-800 border-teal-300 dark:bg-teal-950/40 dark:text-teal-300">
                                Challenge Universe (42)
                              </Badge>
                            )}
                            {plan.trading_activity_status === "non_cote" && (
                              <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-800 border-blue-200">
                                Pre-Opening Non Coté
                              </Badge>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                            {plan.model_name} • Score: {plan.composite_score ?? "N/A"}
                          </div>
                        </div>

                        <div className="text-right">
                          <div className="font-mono font-bold text-slate-900 dark:text-slate-100 text-base">
                            {formatTnd(plan.last_verified_price_tnd)}
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">
                            {plan.quote_age_sessions > 0
                              ? `Quote age: ${plan.quote_age_sessions}s`
                              : "Verified EOD Quote"}
                          </div>
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="space-y-3 text-xs">
                      {/* Non-Challenge Universe Exclusion Notice */}
                      {plan.in_challenge_universe === false && (
                        <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-200 text-[11px] flex items-start gap-2">
                          <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold block">Not in Challenge Universe:</span>
                            This security is listed on BVMT but excluded from the 42 official Tunis Bourse Challenge quotation sheets. Cannot be entered as an actionable manual order.
                          </div>
                        </div>
                      )}

                      {/* Sizing & Capital Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800 font-mono text-[11px]">
                        <div>
                          <span className="text-[10px] text-slate-500 block">Sized Quantity</span>
                          <span className="font-bold text-teal-700 dark:text-teal-400">
                            {plan.suggested_max_shares} Shares
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">Total Cost</span>
                          <span className="font-bold text-slate-900 dark:text-slate-100">
                            {formatTnd(plan.estimated_total_purchase_cost_tnd)}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">Round-Trip Fees</span>
                          <span className="text-rose-600 font-medium">
                            {formatTnd(Number(plan.estimated_purchase_fee_tnd) + Number(plan.estimated_sale_fee_tnd))}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">Break-Even</span>
                          <span className="font-bold text-amber-600">
                            {formatTnd(plan.break_even_price_tnd)}
                          </span>
                        </div>
                      </div>

                      {/* Supporting Evidence Bullets */}
                      <div className="space-y-1 text-slate-600 dark:text-slate-400 leading-normal">
                        {plan.supporting_evidence.map((ev, idx) => (
                          <div key={idx} className="flex items-start gap-1.5 text-[11px]">
                            <span className="text-teal-600 font-bold">•</span>
                            <span>{ev}</span>
                          </div>
                        ))}
                      </div>

                      {/* Liquidity and Execution Warnings */}
                      {plan.liquidity_warnings.length > 0 && (
                        <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 text-amber-800 dark:text-amber-300 text-[11px] space-y-0.5">
                          {plan.liquidity_warnings.map((w, idx) => (
                            <div key={idx} className="flex items-center gap-1.5">
                              <AlertTriangle className="h-3 w-3 shrink-0" />
                              <span>{w}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Footer Actions / Details Trigger */}
                      <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px] font-mono">
                            Horizon: {plan.intended_holding_horizon_sessions}s
                          </Badge>
                          <Badge variant="outline" className="text-[10px] font-mono">
                            Target: {plan.proposed_position_weight_pct}%
                          </Badge>
                        </div>

                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectPlan(plan);
                          }}
                          className="gap-1 text-xs text-teal-700 dark:text-teal-400 hover:text-teal-900"
                        >
                          <span>Load in Calculator</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
