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
  Sparkles,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";
import { usePortfolioMode } from "@/components/app-shell";
import {
  api,
  ManualTradePlan,
  TradePlansResponse,
  HoldingPeriodResearchReport,
  HoldingPeriodHorizonMetric,
  MultiHorizonIntelligenceReport,
  HorizonDecisionItem,
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

type HorizonTab = "SWING" | "POSITION" | "HOLDINGS" | "DAY_TRADING" | "ALL_PLANS";

export default function TradePlannerPage() {
  const { mode } = usePortfolioMode();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [plansData, setPlansData] = useState<TradePlansResponse | null>(null);
  const [holdingResearch, setHoldingResearch] = useState<HoldingPeriodResearchReport | null>(null);
  const [intelligence, setIntelligence] = useState<MultiHorizonIntelligenceReport | null>(null);
  const [selectedUniverse, setSelectedUniverse] = useState<"TUNIS_BOURSE_CHALLENGE" | "FULL_BVMT">("TUNIS_BOURSE_CHALLENGE");
  const [activeTab, setActiveTab] = useState<"MANUAL_ORDER_PLAN" | "PAPER_TRADE_CANDIDATE" | "RESEARCH_CANDIDATE">("MANUAL_ORDER_PLAN");
  const [horizonTab, setHorizonTab] = useState<HorizonTab>("SWING");
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
        const [plansRes, holdingRes, intellRes] = await Promise.all([
          api.getTradePlans(mode, selectedUniverse),
          api.getHoldingPeriods(selectedUniverse),
          api.getTradingIntelligence("ALL", mode).catch(() => null),
        ]);
        if (active) {
          setPlansData(plansRes);
          setHoldingResearch(holdingRes);
          setIntelligence(intellRes);
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

  // Handle horizon decision item selection in calculator
  const handleSelectHorizonItem = (item: HorizonDecisionItem) => {
    const matching = plansData?.plans.find(
      (p) => p.symbol === item.symbol || p.instrument_id === item.instrument_id
    );
    if (matching) {
      handleSelectPlan(matching);
    } else {
      setCustomLimitPrice(item.price_reference);
      setCustomHorizon(item.horizon === "POSITION_20_60S" ? 40 : 20);
    }
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
              Trade Planning & Multi-Horizon Decision Support
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
                <CardDescription>Available Cash</CardDescription>
                <Coins className="h-4 w-4 text-sky-600" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {formatTnd(plansData.available_cash_tnd)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex justify-between text-xs text-slate-500 font-mono">
                <span>Reserved: {formatTnd(plansData.reserved_cash_tnd)}</span>
                <span className="font-semibold text-emerald-600">
                  Effective: {formatTnd(plansData.effective_cash_tnd)}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Target Max Allocation</CardDescription>
                <Percent className="h-4 w-4 text-teal-600" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                8.50% Max Equity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-slate-500 font-mono">
                {(Number(plansData.portfolio_total_equity_tnd) * 0.085).toFixed(3)} TND cap per stock
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Trading Commissions</CardDescription>
                <Scale className="h-4 w-4 text-amber-600" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                0.50% Buy + 0.50% Sell
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-slate-500">
                ~1.00% round-trip hurdle accounted for
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Holding-Period Research</CardDescription>
                <Clock className="h-4 w-4 text-purple-600" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                20 Sessions Optimal
              </CardTitle>
            </CardHeader>
            <CardContent>
              <button
                type="button"
                onClick={() => setShowHoldingResearch((v) => !v)}
                className="text-xs font-medium text-teal-700 hover:text-teal-800 dark:text-teal-400 flex items-center gap-1"
              >
                <span>{showHoldingResearch ? "Hide empirical analysis" : "View 6-horizon audit"}</span>
                {showHoldingResearch ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
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

      {/* Main Content: Interactive Calculator + Horizon Candidates */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Sizing & Cost Calculator (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="border-teal-200/90 dark:border-teal-900/60 shadow-sm sticky top-6">
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
                        <option value={60}>60 sessions (Quarterly)</option>
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
                  Select a candidate from the right column to populate the calculator.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Multi-Horizon Candidate Cards (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Horizon Selector Navigation Bar */}
          <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
            <button
              type="button"
              onClick={() => setHorizonTab("SWING")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                horizonTab === "SWING"
                  ? "bg-teal-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Swing Candidates (5–20 Sessions)
            </button>
            <button
              type="button"
              onClick={() => setHorizonTab("POSITION")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                horizonTab === "POSITION"
                  ? "bg-teal-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Position Candidates (20–60+ Sessions)
            </button>
            <button
              type="button"
              onClick={() => setHorizonTab("HOLDINGS")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                horizonTab === "HOLDINGS"
                  ? "bg-teal-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Active Position Reviews ({intelligence?.active_position_reviews.length || 0})
            </button>
            <button
              type="button"
              onClick={() => setHorizonTab("DAY_TRADING")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                horizonTab === "DAY_TRADING"
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Day Trading Policy
            </button>
            <button
              type="button"
              onClick={() => setHorizonTab("ALL_PLANS")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                horizonTab === "ALL_PLANS"
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              All Order Plans
            </button>
          </div>

          {/* DAY TRADING TAB NOTICE */}
          {horizonTab === "DAY_TRADING" && intelligence?.day_trading_notice && (
            <Card className="border-rose-200 dark:border-rose-900/60 bg-rose-50/40 dark:bg-rose-950/20">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <Badge variant="warning" className="text-xs font-mono">
                    {intelligence.day_trading_notice.status}
                  </Badge>
                  <ShieldAlert className="h-5 w-5 text-rose-600" />
                </div>
                <CardTitle className="text-lg font-bold text-rose-950 dark:text-rose-200 mt-2">
                  {intelligence.day_trading_notice.headline}
                </CardTitle>
                <CardDescription className="text-xs text-rose-800/80 dark:text-rose-300/80">
                  {intelligence.day_trading_notice.disclaimer}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-xs">
                <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-900/60">
                  <div>
                    <span className="text-[11px] text-slate-500 block">Round-Trip Fee Drag:</span>
                    <span className="text-base font-bold font-mono text-rose-600">
                      {intelligence.day_trading_notice.fee_drag_pct}
                    </span>
                    <span className="text-[10px] text-slate-400 block">simulated over 194 sessions</span>
                  </div>
                  <div>
                    <span className="text-[11px] text-slate-500 block">Intraday Volatility Collar:</span>
                    <span className="text-base font-bold font-mono text-slate-800 dark:text-slate-200">
                      {intelligence.day_trading_notice.intraday_volatility_cap}
                    </span>
                    <span className="text-[10px] text-slate-400 block">static circuit breaker</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="font-semibold text-slate-900 dark:text-slate-100">
                    Structural Reasons Why Day Trading is Unavailable:
                  </div>
                  <ul className="space-y-1.5 list-disc pl-4 text-slate-600 dark:text-slate-300">
                    {intelligence.day_trading_notice.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          )}

          {/* HELD POSITIONS REVIEW TAB */}
          {horizonTab === "HOLDINGS" && intelligence && (
            <div className="space-y-3.5">
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Evaluation of currently owned competition positions against the 10.0% single-stock cap, break-even targets, and stop-loss boundaries.
              </div>
              {intelligence.active_position_reviews.map((rev) => (
                <Card key={rev.symbol} className="border-amber-200/80 dark:border-amber-800/60 bg-white dark:bg-slate-950">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-bold text-base text-slate-900 dark:text-slate-100">
                            {rev.symbol}
                          </h3>
                          <Badge variant={rev.decision_status === "REVIEW_POSITION" ? "warning" : "info"} className="text-[10px]">
                            {rev.decision_status}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            {rev.horizon_label}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          Strategy: {rev.strategy_id} • Review Date: {rev.review_date}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono font-bold text-slate-900 dark:text-slate-100 text-base">
                          {formatTnd(rev.price_reference)}
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {rev.evidence_status}
                        </div>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-3 text-xs">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800 font-mono text-[11px]">
                      <div>
                        <span className="text-[10px] text-slate-500 block">Held Shares</span>
                        <span className="font-bold text-slate-900 dark:text-slate-100">{rev.quantity_limit} sh</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block">Current Weight</span>
                        <span className="font-bold text-amber-600">{rev.risk_constraints.current_weight_pct}%</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block">Break-Even Price</span>
                        <span className="font-bold text-slate-900 dark:text-slate-100">{rev.fee_estimate.break_even_price_tnd} TND</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block">Stop-Loss Exit</span>
                        <span className="font-bold text-rose-600">{rev.exit_triggers.stop_loss_price_tnd} TND</span>
                      </div>
                    </div>

                    <div className="space-y-1">
                      {rev.supporting_factors.map((f, i) => (
                        <div key={i} className="flex items-start gap-1.5 text-[11px] text-slate-600 dark:text-slate-300">
                          <CheckCircle2 className="h-3.5 w-3.5 text-teal-600 shrink-0 mt-0.5" />
                          <span>{f}</span>
                        </div>
                      ))}
                    </div>

                    {rev.contradicting_factors.length > 0 && (
                      <div className="p-2.5 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-[11px] space-y-1">
                        {rev.contradicting_factors.map((cf, i) => (
                          <div key={i} className="flex items-start gap-1.5">
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                            <span>{cf}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* SWING TRADING OR POSITION TRADING TAB */}
          {(horizonTab === "SWING" || horizonTab === "POSITION") && intelligence && (
            <div className="space-y-3.5">
              <div className="text-xs text-slate-500 dark:text-slate-400">
                {horizonTab === "SWING"
                  ? "Swing trading candidates (5–20 sessions): Fast momentum confirmation with strict round-trip fee hurdle and volume caps."
                  : "Position trading candidates (20–60+ sessions): Multi-month trend persistence for quarterly fundamental holding."}
              </div>

              {(horizonTab === "SWING" ? intelligence.swing_candidates : intelligence.position_candidates).map((item) => (
                <Card
                  key={item.symbol}
                  className="hover:border-teal-400/80 dark:hover:border-teal-700/80 transition-all border bg-white dark:bg-slate-950"
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-bold text-base text-slate-900 dark:text-slate-100">
                            {item.symbol}
                          </h3>
                          <Badge
                            variant={item.decision_status === "MANUAL_ORDER_PLAN" ? "success" : "default"}
                            className="text-[10px]"
                          >
                            {item.decision_status}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            {item.horizon_label}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          Strategy: {item.strategy_id} • Review: {item.review_date}
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="font-mono font-bold text-slate-900 dark:text-slate-100 text-base">
                          {formatTnd(item.price_reference)}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono">
                          {item.evidence_status}
                        </div>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-3 text-xs">
                    {/* Sizing & Capital Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800 font-mono text-[11px]">
                      <div>
                        <span className="text-[10px] text-slate-500 block">Sized Quantity</span>
                        <span className="font-bold text-teal-700 dark:text-teal-400">
                          {item.quantity_limit} Shares
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block">Est. Purchase Fee</span>
                        <span className="font-bold text-slate-900 dark:text-slate-100">
                          {item.fee_estimate.estimated_purchase_fee_tnd} TND
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block">Break-Even Price</span>
                        <span className="font-bold text-amber-600">
                          {item.fee_estimate.break_even_price_tnd} TND
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block">Stop-Loss Exit</span>
                        <span className="font-bold text-rose-600">
                          {item.exit_triggers.stop_loss_price_tnd} TND
                        </span>
                      </div>
                    </div>

                    {/* Supporting Evidence */}
                    <div className="space-y-1">
                      {item.supporting_factors.map((f, idx) => (
                        <div key={idx} className="flex items-start gap-1.5 text-[11px] text-slate-600 dark:text-slate-300">
                          <span className="text-teal-600 font-bold">•</span>
                          <span>{f}</span>
                        </div>
                      ))}
                    </div>

                    {/* Contradicting Factors & Limitations */}
                    {item.contradicting_factors.length > 0 && (
                      <div className="p-2 rounded bg-amber-50/60 dark:bg-amber-950/30 border border-amber-200/70 dark:border-amber-900/40 text-amber-900 dark:text-amber-200 text-[11px] space-y-0.5">
                        {item.contradicting_factors.map((cf, idx) => (
                          <div key={idx} className="flex items-start gap-1.5">
                            <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
                            <span>{cf}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Footer Actions */}
                    <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                      <div className="text-[11px] text-slate-500">
                        Profit Target: <strong className="font-mono text-emerald-600">{item.exit_triggers.profit_target_price_tnd} TND</strong>
                      </div>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleSelectHorizonItem(item)}
                        className="gap-1 text-xs text-teal-700 dark:text-teal-400 hover:text-teal-900"
                      >
                        <span>Test in Calculator</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* ALL GENERATED PLANS TAB */}
          {horizonTab === "ALL_PLANS" && (
            <div className="space-y-3.5">
              <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("MANUAL_ORDER_PLAN")}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${
                    activeTab === "MANUAL_ORDER_PLAN" ? "bg-teal-600 text-white" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  Actionable Plans
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("PAPER_TRADE_CANDIDATE")}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${
                    activeTab === "PAPER_TRADE_CANDIDATE" ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  Paper Trade
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("RESEARCH_CANDIDATE")}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${
                    activeTab === "RESEARCH_CANDIDATE" ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  Research Candidates
                </button>
              </div>

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
                          </div>
                          <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                            {plan.model_name} • Score: {plan.composite_score ?? "N/A"}
                          </div>
                        </div>

                        <div className="text-right">
                          <div className="font-mono font-bold text-slate-900 dark:text-slate-100 text-base">
                            {formatTnd(plan.last_verified_price_tnd)}
                          </div>
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="space-y-3 text-xs">
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
                          <span className="text-[10px] text-slate-500 block">Break-Even</span>
                          <span className="font-bold text-amber-600">
                            {formatTnd(plan.break_even_price_tnd)}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">Horizon</span>
                          <span className="font-mono text-slate-800 dark:text-slate-200">
                            {plan.intended_holding_horizon_sessions} Sessions
                          </span>
                        </div>
                      </div>

                      <div className="space-y-1">
                        {plan.supporting_evidence.map((ev, idx) => (
                          <div key={idx} className="flex items-start gap-1.5 text-[11px] text-slate-600 dark:text-slate-300">
                            <span className="text-teal-600 font-bold">•</span>
                            <span>{ev}</span>
                          </div>
                        ))}
                      </div>

                      <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-end">
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
