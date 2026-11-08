"use client";

import React, { useEffect, useState } from "react";
import {
  FlaskConical,
  AlertTriangle,
  TrendingUp,
  ShieldCheck,
  Hash,
  Lock,
  Layers,
  Activity,
  Database,
  CheckCircle2,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
} from "recharts";
import {
  api,
  ResearchResponse,
  StrategyEvaluationReport,
  StrategyExperimentRegistry,
  StrategyLabResponse,
} from "@/lib/api";
import { formatPct, formatTnd } from "@/lib/utils";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { usePortfolioMode } from "@/components/app-shell";

const SHORT_LABELS: Record<string, string> = {
  A_CASH_ONLY: "A: Cash Only",
  B_EQUAL_WEIGHT_ELIGIBLE: "B: Equal Weight",
  C_BUY_AND_HOLD_BENCHMARK: "C: Buy & Hold",
  D_MOMENTUM_20S: "D: Mom 20S",
  E_MOMENTUM_60S: "E: Mom 60S",
  F_RELATIVE_STRENGTH_20S: "F: Rel Strength",
  G_LIQUIDITY_FILTERED_MOMENTUM: "G: Liq-Mom (T04)",
  H_DOWNSIDE_RISK_TREND_MULTIFACTOR: "H: Multi-Factor",
  I_REGIME_FILTERED_QUALITY_MOMENTUM: "I: Regime Quality",
};

export default function StrategyLabPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [labData, setLabData] = useState<StrategyLabResponse | null>(null);
  const [researchData, setResearchData] = useState<ResearchResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string>("G_LIQUIDITY_FILTERED_MOMENTUM");

  useEffect(() => {
    api
      .getStrategyLab()
      .then((res) => {
        setLabData(res);
        if (res.registry?.reports?.length) {
          const hasDefault = res.registry.reports.some(
            (r) => r.strategy_id === "G_LIQUIDITY_FILTERED_MOMENTUM"
          );
          if (!hasDefault) {
            setSelectedId(res.registry.reports[0].strategy_id);
          }
        }
      })
      .catch(() => {});

    api
      .getResearch("", mode)
      .then((res) => setResearchData(res))
      .catch(() => {});
  }, [mode, refreshTrigger]);

  const registry: StrategyExperimentRegistry | null =
    labData?.registry || researchData?.strategy_comparison || null;
  const reports: StrategyEvaluationReport[] = registry?.reports || [];
  const selectedReport: StrategyEvaluationReport | null =
    reports.find((r) => r.strategy_id === selectedId) || reports[6] || reports[0] || null;

  const prodBaseline =
    reports.find((r) => r.strategy_id === "G_LIQUIDITY_FILTERED_MOMENTUM") || selectedReport;
  const regimeModel =
    reports.find((r) => r.strategy_id === "I_REGIME_FILTERED_QUALITY_MOMENTUM") || selectedReport;

  const comparisonChartData = reports.map((r) => ({
    strategy: SHORT_LABELS[r.strategy_id] || r.strategy_id,
    NetReturn: Number(r.net_return_pct.toFixed(2)),
    LiquidatedReturn: Number(r.liquidated_return_pct.toFixed(2)),
    MaxDrawdown: Number(r.max_drawdown_pct.toFixed(2)),
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            Quantitative Strategy Lab & Comparative Experiment Registry
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Source-grounded evaluation of Baselines A–G and Multi-Factor Enhancements H–I on 194
            verified 2026 BVMT sessions.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="warning" className="gap-1.5">
            <FlaskConical className="h-3.5 w-3.5" />
            Exploratory Single-Year Sample (194 &lt; 250d)
          </Badge>
          <Badge variant="info" className="gap-1.5">
            <Lock className="h-3.5 w-3.5" />
            Human Approval Required for Promotion
          </Badge>
        </div>
      </div>

      {/* Governance, Separation & Cryptographic Provenance Banner */}
      <Card className="border-sky-500/40 bg-sky-950/15">
        <CardContent className="p-4 space-y-3 text-xs text-sky-200">
          <div className="flex items-start gap-3">
            <ShieldCheck className="h-4 w-4 text-sky-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold">
                Scientific Governance: Zero Auto-Promotion & Assumption-Explicit T+1 Execution
              </p>
              <p className="text-sky-300/85 leading-relaxed">
                All 9 registered models are evaluated over the exact same 194 trading sessions (
                <span className="font-mono">2026-01-02</span> to{" "}
                <span className="font-mono">2026-11-06</span>, 61-session warmup, 19-session
                rebalance cadence) with T+1 next-open execution,{" "}
                <span className="font-mono">0.50%</span> buy /{" "}
                <span className="font-mono">0.50%</span> sell commissions (
                <span className="font-mono">~1.00%</span> round-trip),{" "}
                <span className="font-mono">10 bps</span> slippage,{" "}
                <span className="font-mono">8.5%</span> target /{" "}
                <span className="font-mono">10.0%</span> purchase concentration cap, and{" "}
                <span className="font-mono">10.0%</span> daily share-volume participation cap. No
                research model is ever automatically promoted into live competition trading.
              </p>
            </div>
          </div>

          {registry && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-2 border-t border-sky-800/40 text-[11px]">
              <div className="rounded bg-slate-950/70 px-2.5 py-1.5 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1">
                  <Hash className="h-3 w-3 text-sky-400" /> Config Hash
                </span>
                <span className="font-mono text-slate-200" title={registry.config_hash}>
                  {registry.config_hash.slice(0, 16)}…
                </span>
              </div>
              <div className="rounded bg-slate-950/70 px-2.5 py-1.5 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1">
                  <Database className="h-3 w-3 text-emerald-400" /> Canonical Bars SHA
                </span>
                <span
                  className="font-mono text-slate-200"
                  title={registry.canonical_sha256 || registry.data_hash}
                >
                  {(registry.canonical_sha256 || registry.data_hash).slice(0, 16)}…
                </span>
              </div>
              <div className="rounded bg-slate-950/70 px-2.5 py-1.5 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1">
                  <Hash className="h-3 w-3 text-purple-400" /> Strategy Code SHA
                </span>
                <span className="font-mono text-slate-200" title={registry.code_sha256 || ""}>
                  {(registry.code_sha256 || registry.data_hash).slice(0, 16)}…
                </span>
              </div>
              <div className="rounded bg-slate-950/70 px-2.5 py-1.5 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400">Registered Trials</span>
                <span className="font-mono text-emerald-300 font-semibold">
                  {registry.trial_count} Frozen Hypotheses (v{registry.schema_version})
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {registry && reports.length > 0 ? (
        <>
          {/* Top Summary KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="border-emerald-500/30">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>Active Baseline (G: Liq-Mom T04)</span>
                  <Badge variant="success">Production Baseline</Badge>
                </CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-emerald-400">
                  {formatPct(prodBaseline?.net_return_pct ?? 18.81)}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Liquidated: {formatPct(prodBaseline?.liquidated_return_pct ?? 18.73)} • Excess:{" "}
                <span className="text-emerald-300 font-mono">
                  {formatPct(prodBaseline?.excess_return_pct ?? 4.79)}
                </span>{" "}
                • Max DD: -{formatPct(prodBaseline?.max_drawdown_pct ?? 4.98, false)}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>Regime Quality Enhancement (Model I)</span>
                  <Badge variant="info">Highest Hit Rate</Badge>
                </CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-sky-300">
                  {formatPct(regimeModel?.net_return_pct ?? 15.74)}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Hit Rate:{" "}
                <span className="text-sky-300 font-mono">
                  {formatPct(regimeModel?.hit_rate_pct ?? 69.23, false)}
                </span>{" "}
                • Max DD: -{formatPct(regimeModel?.max_drawdown_pct ?? 5.47, false)} • Fees:{" "}
                {formatTnd(regimeModel?.total_fees_tnd ?? 1089.54)} TND
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>
                  7-Fold Chronological Walk-Forward ({selectedReport?.strategy_id.slice(0, 1)})
                </CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-emerald-400">
                  {selectedReport?.walk_forward.positive_folds ?? 4} /{" "}
                  {selectedReport?.walk_forward.total_folds ?? 7} Positive
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Mean Fold:{" "}
                {formatPct(selectedReport?.walk_forward.mean_fold_return_pct ?? 1.94)} • Train 61d
                / Test 19d
              </CardContent>
            </Card>

            <Card className="border-amber-500/30">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>ML Promotion Gate (LightGBM)</span>
                  <Badge variant="warning">Blocked</Badge>
                </CardDescription>
                <CardTitle className="text-xl font-mono font-bold text-amber-300">
                  {registry.ml_promotion_gate.session_count} /{" "}
                  {registry.ml_promotion_gate.minimum_sessions} Sessions
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Requires ≥250 multi-year sessions &amp; untouched holdout before ML promotion.
              </CardContent>
            </Card>
          </div>

          {/* Full Comparative Table (Models A through I) */}
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-sky-400" />
                    <span>
                      Comparative Strategy Suite: Baselines (A–G) &amp; Multi-Factor Enhancements
                      (H–I)
                    </span>
                  </CardTitle>
                  <CardDescription>
                    Click any strategy row to inspect its 194-session equity curve, drawdown path,
                    7 walk-forward folds, and 3×3 fee/liquidity sensitivity matrix below.
                  </CardDescription>
                </div>
                <Badge variant="outline" className="font-mono text-[11px]">
                  Selected: {selectedReport?.strategy_id}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                    <th className="py-2.5 px-2">Strategy ID &amp; Name</th>
                    <th className="py-2.5 px-2">Family</th>
                    <th className="py-2.5 px-2">Sample</th>
                    <th className="py-2.5 px-2 text-right">Marked Net</th>
                    <th className="py-2.5 px-2 text-right">Liquidated</th>
                    <th className="py-2.5 px-2 text-right">Excess vs C</th>
                    <th className="py-2.5 px-2 text-right">Max DD</th>
                    <th className="py-2.5 px-2 text-right">Turnover</th>
                    <th className="py-2.5 px-2 text-right">Fees (TND)</th>
                    <th className="py-2.5 px-2 text-right">Fills/Orders</th>
                    <th className="py-2.5 px-2 text-right">Hit Rate</th>
                    <th className="py-2.5 px-2 text-right">Cash Util</th>
                    <th className="py-2.5 px-2 text-right">Max Wt</th>
                    <th className="py-2.5 px-2 text-right">WF Mean</th>
                    <th className="py-2.5 px-2 text-right">Experiment Hash</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {reports.map((r) => {
                    const isSelected = r.strategy_id === selectedReport?.strategy_id;
                    const isProd = r.strategy_id === "G_LIQUIDITY_FILTERED_MOMENTUM";
                    return (
                      <tr
                        key={r.strategy_id}
                        onClick={() => setSelectedId(r.strategy_id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-sky-950/40 hover:bg-sky-950/50"
                            : "hover:bg-slate-900/60"
                        }`}
                      >
                        <td className="py-2.5 px-2 font-sans">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-semibold text-slate-100">
                              {r.strategy_id}
                            </span>
                            {isProd && (
                              <Badge variant="success" className="text-[10px] px-1.5 py-0">
                                Active T04
                              </Badge>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400">{r.name}</div>
                        </td>
                        <td className="py-2.5 px-2 font-sans">
                          <Badge
                            variant={r.family === "enhanced" ? "info" : "outline"}
                            className="text-[10px]"
                          >
                            {r.family} v{r.version}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-2 font-sans">
                          <Badge variant="warning" className="text-[10px]">
                            {r.sample_Classification}
                          </Badge>
                        </td>
                        <td
                          className={`py-2.5 px-2 text-right font-semibold ${
                            r.net_return_pct > 0 ? "text-emerald-400" : "text-slate-300"
                          }`}
                        >
                          {formatPct(r.net_return_pct)}
                        </td>
                        <td
                          className={`py-2.5 px-2 text-right ${
                            r.liquidated_return_pct > 0 ? "text-sky-300" : "text-slate-300"
                          }`}
                        >
                          {formatPct(r.liquidated_return_pct)}
                        </td>
                        <td
                          className={`py-2.5 px-2 text-right ${
                            r.excess_return_pct > 0
                              ? "text-emerald-400"
                              : r.excess_return_pct < 0
                              ? "text-rose-400"
                              : "text-slate-400"
                          }`}
                        >
                          {formatPct(r.excess_return_pct)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-amber-300">
                          -{formatPct(r.max_drawdown_pct, false)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {r.turnover_ratio.toFixed(2)}x
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {formatTnd(r.total_fees_tnd)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {r.trade_count} / {r.order_count}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-200">
                          {formatPct(r.hit_rate_pct, false)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {formatPct(r.avg_cash_utilization_pct, false)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {formatPct(r.max_single_stock_weight_pct, false)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-emerald-300">
                          {formatPct(r.walk_forward.mean_fold_return_pct ?? 0)}
                        </td>
                        <td
                          className="py-2.5 px-2 text-right text-slate-400 text-[11px]"
                          title={r.experiment_id}
                        >
                          {r.experiment_id.slice(0, 10)}…
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Charts Row: Selected Strategy Equity Curve & Drawdown + Cross-Model Comparison */}
          {selectedReport && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-emerald-400" />
                    <span>
                      Equity Curve vs. Buy-and-Hold Benchmark ({selectedReport.strategy_id})
                    </span>
                  </CardTitle>
                  <CardDescription>
                    Daily portfolio equity (TND) across {selectedReport.session_count} sessions (
                    {selectedReport.start_session} to {selectedReport.end_session})
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={selectedReport.equity_curve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        dataKey="session_date"
                        stroke="#94a3b8"
                        fontSize={11}
                        minTickGap={28}
                      />
                      <YAxis
                        stroke="#94a3b8"
                        fontSize={11}
                        domain={["auto", "auto"]}
                        tickFormatter={(v) => `${(Number(v) / 1000).toFixed(1)}k`}
                      />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          borderColor: "#334155",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: "12px" }} />
                      <Line
                        type="monotone"
                        name={`${selectedReport.strategy_id} Equity (TND)`}
                        dataKey="total_equity_tnd"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        name="Benchmark C Equity (TND)"
                        dataKey="benchmark_equity_tnd"
                        stroke="#64748b"
                        strokeWidth={1.5}
                        strokeDasharray="4 4"
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-sky-400" />
                    <span>Cross-Strategy Return &amp; Max Drawdown Comparison (A–I)</span>
                  </CardTitle>
                  <CardDescription>
                    Marked Net Return (%), Liquidated Return (%), and Max Drawdown (%) across all 9
                    models
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={comparisonChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="strategy" stroke="#94a3b8" fontSize={10} interval={0} />
                      <YAxis stroke="#94a3b8" fontSize={11} unit="%" />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          borderColor: "#334155",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: "12px" }} />
                      <Bar name="Marked Net (%)" dataKey="NetReturn" fill="#10b981" />
                      <Bar name="Liquidated (%)" dataKey="LiquidatedReturn" fill="#38bdf8" />
                      <Bar name="Max Drawdown (%)" dataKey="MaxDrawdown" fill="#f59e0b" />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Selected Strategy Drawdown Path & Mathematical Specification */}
          {selectedReport && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Underwater Drawdown Curve ({selectedReport.strategy_id})
                  </CardTitle>
                  <CardDescription>
                    Peak-to-trough drawdown (%) across 194 sessions (Max:{" "}
                    -{formatPct(selectedReport.max_drawdown_pct, false)})
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={selectedReport.equity_curve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        dataKey="session_date"
                        stroke="#94a3b8"
                        fontSize={10}
                        minTickGap={32}
                      />
                      <YAxis stroke="#94a3b8" fontSize={10} unit="%" />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          borderColor: "#334155",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Area
                        type="monotone"
                        name="Drawdown (%)"
                        dataKey="drawdown_pct"
                        stroke="#f59e0b"
                        fill="#f59e0b"
                        fillOpacity={0.2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="text-sm">
                    Mathematical Formula, Position P&amp;L Distribution &amp; Diagnostics (
                    {selectedReport.strategy_id})
                  </CardTitle>
                  <CardDescription>
                    {selectedReport.name} • Promotion Status:{" "}
                    <span className="font-mono text-amber-300">
                      {selectedReport.promotion_status}
                    </span>
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <div className="rounded-lg bg-slate-950/70 p-3 border border-slate-800">
                    <div className="text-[11px] text-slate-400 uppercase font-semibold mb-1">
                      Signal &amp; Allocation Formula
                    </div>
                    <div className="font-mono text-sky-300 text-xs">
                      {selectedReport.formula_summary}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    <div className="rounded-lg bg-slate-950/60 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Winning / Losing Slices</div>
                      <div className="font-mono font-bold text-slate-100 mt-0.5">
                        <span className="text-emerald-400">
                          {selectedReport.win_loss_Init_summary.winning_positions}W
                        </span>{" "}
                        /{" "}
                        <span className="text-rose-400">
                          {selectedReport.win_loss_Init_summary.losing_positions}L
                        </span>
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/60 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Best / Worst Slice</div>
                      <div className="font-mono font-bold text-slate-100 mt-0.5">
                        {selectedReport.win_loss_Init_summary.best_position_return_pct !== null
                          ? `${formatPct(
                              selectedReport.win_loss_Init_summary.best_position_return_pct
                            )} / ${formatPct(
                              selectedReport.win_loss_Init_summary.worst_position_return_pct ?? 0
                            )}`
                          : "—"}
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/60 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Purchase Cap vs Drift Max</div>
                      <div className="font-mono font-bold text-slate-100 mt-0.5">
                        10.0% Cap / {formatPct(selectedReport.max_single_stock_weight_pct, false)}{" "}
                        Drift
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/60 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Sensitivity Range (3×3)</div>
                      <div className="font-mono font-bold text-emerald-300 mt-0.5">
                        {formatPct(selectedReport.fee_and_liquidity_sensitivity.min_return_pct)} to{" "}
                        {formatPct(selectedReport.fee_and_liquidity_sensitivity.max_return_pct)}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* 7-Fold Walk-Forward Table & 3x3 Fee/Liquidity Sensitivity Grid */}
          {selectedReport && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    7-Fold Chronological Walk-Forward Breakdown ({selectedReport.strategy_id})
                  </CardTitle>
                  <CardDescription>
                    {selectedReport.walk_forward.classification} (Train:{" "}
                    {selectedReport.walk_forward.train_sessions}d, Test:{" "}
                    {selectedReport.walk_forward.test_sessions}d, Step:{" "}
                    {selectedReport.walk_forward.step_sessions}d)
                  </CardDescription>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                        <th className="py-2 px-2">Fold</th>
                        <th className="py-2 px-2">Test Window</th>
                        <th className="py-2 px-2 text-right">Strategy</th>
                        <th className="py-2 px-2 text-right">Liquidated</th>
                        <th className="py-2 px-2 text-right">Bench C</th>
                        <th className="py-2 px-2 text-right">Excess</th>
                        <th className="py-2 px-2 text-right">Fills</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {selectedReport.walk_forward.folds.map((f) => (
                        <tr key={f.fold_index} className="hover:bg-slate-900/40">
                          <td className="py-2 px-2 text-slate-300">Fold {f.fold_index}</td>
                          <td className="py-2 px-2 text-slate-400 text-[11px]">
                            {f.test_start} → {f.test_end}
                          </td>
                          <td
                            className={`py-2 px-2 text-right font-semibold ${
                              f.strategy_return_pct > 0
                                ? "text-emerald-400"
                                : f.strategy_return_pct < 0
                                ? "text-rose-400"
                                : "text-slate-300"
                            }`}
                          >
                            {formatPct(f.strategy_return_pct)}
                          </td>
                          <td className="py-2 px-2 text-right text-sky-300">
                            {formatPct(f.liquidated_return_pct)}
                          </td>
                          <td className="py-2 px-2 text-right text-slate-400">
                            {formatPct(f.benchmark_return_pct)}
                          </td>
                          <td
                            className={`py-2 px-2 text-right ${
                              f.excess_return_pct > 0
                                ? "text-emerald-400"
                                : f.excess_return_pct < 0
                                ? "text-rose-400"
                                : "text-slate-400"
                            }`}
                          >
                            {formatPct(f.excess_return_pct)}
                          </td>
                          <td className="py-2 px-2 text-right text-slate-300">{f.fill_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Fee &amp; Liquidity Participation Sensitivity Matrix (
                    {selectedReport.strategy_id})
                  </CardTitle>
                  <CardDescription>
                    Full sequential re-simulation across 30/50/70 bps fees and 5%/10%/20% daily
                    volume participation caps
                  </CardDescription>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                        <th className="py-2 px-2">Commission (bps)</th>
                        <th className="py-2 px-2">Max Vol Cap</th>
                        <th className="py-2 px-2 text-right">Marked Net</th>
                        <th className="py-2 px-2 text-right">Liquidated</th>
                        <th className="py-2 px-2 text-right">Total Fees (TND)</th>
                        <th className="py-2 px-2 text-right">Trades</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {selectedReport.fee_and_liquidity_sensitivity.scenarios.map((s, idx) => {
                        const isBaselineScenario =
                          s.commission_bps === 50 &&
                          Math.abs(s.max_volume_participation - 0.1) < 1e-6;
                        return (
                          <tr
                            key={idx}
                            className={
                              isBaselineScenario ? "bg-emerald-950/25" : "hover:bg-slate-900/40"
                            }
                          >
                            <td className="py-2 px-2 text-slate-200">
                              {s.commission_bps} bps ({(s.commission_bps / 100).toFixed(2)}%)
                              {isBaselineScenario && (
                                <span className="ml-1.5 text-[10px] text-emerald-400 font-sans">
                                  [TBC Rule]
                                </span>
                              )}
                            </td>
                            <td className="py-2 px-2 text-slate-300">
                              {(s.max_volume_participation * 100).toFixed(0)}%
                            </td>
                            <td className="py-2 px-2 text-right text-emerald-400 font-semibold">
                              {formatPct(s.net_return_pct)}
                            </td>
                            <td className="py-2 px-2 text-right text-sky-300">
                              {formatPct(s.liquidated_return_pct)}
                            </td>
                            <td className="py-2 px-2 text-right text-slate-300">
                              {formatTnd(s.total_fees_tnd)}
                            </td>
                            <td className="py-2 px-2 text-right text-slate-300">{s.trade_count}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Historical Coverage Audit (2020-2026) & Methodological Limitations */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {registry.historical_audit && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Database className="h-4 w-4 text-emerald-400" />
                    <span>Official BVMT Historical Data Coverage Audit (2020–2026)</span>
                  </CardTitle>
                  <CardDescription>
                    Source: {registry.historical_audit.source_url || "Official Bourse de Tunis"} •
                    Checksum Verified:{" "}
                    {registry.historical_audit.canonical_checksum_matches ? "Yes" : "No"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                        <th className="py-2 px-2">Year</th>
                        <th className="py-2 px-2 text-right">Canonical Daily Sessions</th>
                        <th className="py-2 px-2 text-right">Instruments</th>
                        <th className="py-2 px-2">Daily OHLCV</th>
                        <th className="py-2 px-2">Audit Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {Object.entries(registry.historical_audit.coverage_2020_2026).map(
                        ([year, cov]) => (
                          <tr key={year} className="hover:bg-slate-900/40">
                            <td className="py-2 px-2 text-slate-200 font-semibold">{year}</td>
                            <td className="py-2 px-2 text-right text-slate-300">
                              {cov.canonical_sessions}
                            </td>
                            <td className="py-2 px-2 text-right text-slate-300">
                              {cov.instrument_count}
                            </td>
                            <td className="py-2 px-2 font-sans">
                              {cov.daily_ohlcv_available ? (
                                <Badge variant="success" className="text-[10px]">
                                  Verified (194d)
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-[10px]">
                                  Absent in Public Feed
                                </Badge>
                              )}
                            </td>
                            <td className="py-2 px-2 text-slate-400 text-[11px]">{cov.status}</td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <span>Disclosed Statistical &amp; Microstructure Limitations</span>
                </CardTitle>
                <CardDescription>
                  Explicit failure modes and boundaries enforced across all Strategy Lab reports
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs text-slate-300">
                <ul className="space-y-1.5 text-[11px] text-slate-300 leading-relaxed">
                  {registry.limitations.map((lim, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-sky-400 shrink-0 mt-0.5" />
                      <span>{lim}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        </>
      ) : (
        <p className="text-xs text-slate-400">
          Loading comparative strategy experiment registry...
        </p>
      )}
    </div>
  );
}
