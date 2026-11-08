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
  Scale,
  FileSpreadsheet,
  History,
  PlayCircle,
  ShieldAlert,
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
  PaperTradingResponse,
  ResearchResponse,
  StrategyEvaluationReport,
  StrategyExperimentRegistry,
  StrategyLabResponse,
} from "@/lib/api";
import { formatPct, formatTnd } from "@/lib/utils";
import {
  Badge,
  Button,
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
  const [paperData, setPaperData] = useState<PaperTradingResponse | null>(null);
  const [recordingPaper, setRecordingPaper] = useState<boolean>(false);
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

  useEffect(() => {
    api
      .getPaperTrading(selectedId)
      .then((res) => setPaperData(res))
      .catch(() => {});
  }, [selectedId, refreshTrigger]);

  const handleRecordForwardSignal = async () => {
    setRecordingPaper(true);
    try {
      const res = await api.recordPaperSignal(selectedId, null);
      setPaperData(res);
    } catch {
      // ignore
    } finally {
      setRecordingPaper(false);
    }
  };

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
    ExposureNormalizedReturn: Number(
      (r.risk_normalized_metrics?.exposure_normalized_return_pct ?? r.net_return_pct).toFixed(2)
    ),
    EqualBudget10SlotReturn: Number(
      (r.risk_normalized_metrics?.equal_budget_10slot_net_return_pct ?? r.net_return_pct).toFixed(2)
    ),
    ExSotetelReturn: Number(
      (r.risk_normalized_metrics?.ex_top_winner_net_return_pct ?? r.net_return_pct).toFixed(2)
    ),
  }));

  const paperJournal = paperData?.journal || null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            Quantitative Strategy Lab, Robustness Audit &amp; Forward Paper Trading
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Milestone 5 independent audit, exposure-normalized evaluation of Models A–I, and
            immutable forward-only paper-trading journal.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="warning" className="gap-1.5">
            <FlaskConical className="h-3.5 w-3.5" />
            Exploratory Historical Backtest (194 &lt; 250d)
          </Badge>
          <Badge variant="danger" className="gap-1.5">
            <ShieldAlert className="h-3.5 w-3.5" />
            Model G Not Validated for Auto-Promotion
          </Badge>
          <Badge variant="info" className="gap-1.5">
            <Lock className="h-3.5 w-3.5" />
            100% Manual Execution Only
          </Badge>
        </div>
      </div>

      {/* Milestone 5 Independent Strategy Audit Banner (Model G Audit Status) */}
      <Card className="border-amber-500/40 bg-amber-950/15">
        <CardContent className="p-4 space-y-3 text-xs text-amber-100">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0" />
              <span className="font-semibold text-amber-200">
                Milestone 5 Independent Strategy Audit Status: Model G (
                <span className="font-mono">
                  {registry?.audit_summary?.model_g_audit_status ||
                    "exploratory_unvalidated_high_outlier_dependency"}
                </span>
                )
              </span>
            </div>
            <Badge variant="warning" className="font-mono text-[10px]">
              Promotion Eligible:{" "}
              {registry?.audit_summary?.model_g_promotion_eligible ? "YES" : "NO — BLOCKED"}
            </Badge>
          </div>
          <p className="text-amber-200/85 leading-relaxed">
            Independent audit of the 2026 dataset (<span className="font-mono">194</span> sessions)
            established four critical findings that prevent treating Model G&apos;s{" "}
            <span className="font-mono">+18.81%</span> return as a guaranteed forecast: (1){" "}
            <strong>Low Drawdown Explained by Cash Drag:</strong> Model G&apos;s{" "}
            <span className="font-mono">4.98%</span> max drawdown reflects{" "}
            <span className="font-mono">29.79%</span> active capital utilization (~70% cash); its
            exposure-normalized sleeve drawdown is <span className="font-mono">16.73%</span>{" "}
            (matching Benchmark C&apos;s <span className="font-mono">17.40%</span>). (2){" "}
            <strong>Single-Stock Outlier Dependency (SOTETEL):</strong> Excluding{" "}
            <span className="font-mono">SOTETEL</span> (<span className="font-mono">+202.29%</span>{" "}
            gain) reduces Model G&apos;s 5-slot return from{" "}
            <span className="font-mono">+18.81%</span> to{" "}
            <span className="font-mono">+7.43%</span>. (3){" "}
            <strong>Equal-Budget Winner is Model I:</strong> At an equalized 10-slot (9.5% target)
            budget, <span className="font-mono">I_REGIME_FILTERED_QUALITY_MOMENTUM</span> outperforms
            Model G (<span className="font-mono">+28.82%</span> vs{" "}
            <span className="font-mono">+25.37%</span>, with lower drawdown{" "}
            <span className="font-mono">10.30%</span> vs <span className="font-mono">10.92%</span>).
            (4) <strong>D == F Rank Identity:</strong> Subtracting cross-sectional mean return{" "}
            <span className="font-mono">bench_20</span> is rank-invariant whenever ≥5 eligible
            stocks beat the mean.
          </p>

          {registry && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-2 border-t border-amber-800/40 text-[11px]">
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
            <Card className="border-amber-500/30">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>Model G (5-Slot vs Ex-SOTETEL)</span>
                  <Badge variant="warning">Audited Baseline</Badge>
                </CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-emerald-400">
                  {formatPct(prodBaseline?.net_return_pct ?? 18.81)}{" "}
                  <span className="text-sm text-amber-300 font-normal">
                    (Ex-Outlier:{" "}
                    {formatPct(
                      prodBaseline?.risk_normalized_metrics?.ex_top_winner_net_return_pct ?? 7.43
                    )}
                    )
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Active Util:{" "}
                {formatPct(
                  prodBaseline?.risk_normalized_metrics?.active_cash_utilization_pct ?? 29.79,
                  false
                )}{" "}
                • Sleeve DD: -
                {formatPct(
                  prodBaseline?.risk_normalized_metrics?.exposure_normalized_max_drawdown_pct ??
                    16.73,
                  false
                )}
              </CardContent>
            </Card>

            <Card className="border-sky-500/30">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>Model I (Equal-Budget 10-Slot Winner)</span>
                  <Badge variant="info">#1 Risk-Normalized</Badge>
                </CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-sky-300">
                  {formatPct(
                    regimeModel?.risk_normalized_metrics?.equal_budget_10slot_net_return_pct ??
                      28.82
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Exp-Norm Return:{" "}
                <span className="text-sky-300 font-mono">
                  {formatPct(
                    regimeModel?.risk_normalized_metrics?.exposure_normalized_return_pct ?? 63.85
                  )}
                </span>{" "}
                • 10-Slot DD: -
                {formatPct(
                  regimeModel?.risk_normalized_metrics?.equal_budget_10slot_max_drawdown_pct ??
                    10.3,
                  false
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>Forward Paper-Trading Journal</span>
                  <Badge variant="success">Prospective T+1</Badge>
                </CardDescription>
                <CardTitle className="text-xl font-mono font-bold text-emerald-400">
                  {paperJournal
                    ? `${formatTnd(paperJournal.total_equity_tnd)} TND`
                    : "50,000.000 TND"}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Snapshots: {paperJournal?.signal_snapshots.length ?? 1} • Pending Next-Open Orders:{" "}
                {paperJournal?.orders.filter((o) => o.status === "PENDING_NEXT_SESSION").length ??
                  0}
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
                Requires ≥250 multi-year sessions &amp; forward paper-trading track record.
              </CardContent>
            </Card>
          </div>

          {/* Phase 2: Exposure-Normalized, Cash-Matched, Equal-Budget & Outlier-Adjusted Table */}
          <Card className="border-sky-500/30">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Scale className="h-4 w-4 text-sky-400" />
                    <span>
                      Phase 2: Risk-Normalized, Exposure-Equalized &amp; Outlier-Adjusted Comparison
                      (Models A–I)
                    </span>
                  </CardTitle>
                  <CardDescription>
                    Eliminates cash-utilization bias by comparing Active Post-Warmup Utilization,
                    Exposure-Normalized Sleeve Return/DD, Cash-Matched Benchmark B Excess, 10-Slot
                    Equal Budget, Daily Concentration Trim, and Ex-SOTETEL Return.
                  </CardDescription>
                </div>
                <Badge variant="warning" className="font-mono text-[10px]">
                  EXPLORATORY HISTORICAL BACKTEST — NOT FORWARD PERFORMANCE
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                    <th className="py-2.5 px-2">Strategy</th>
                    <th className="py-2.5 px-2 text-right">5-Slot Net</th>
                    <th className="py-2.5 px-2 text-right">Active Util</th>
                    <th className="py-2.5 px-2 text-right">Exp-Norm Ret</th>
                    <th className="py-2.5 px-2 text-right">Exp-Norm DD</th>
                    <th className="py-2.5 px-2 text-right">Ann. Vol</th>
                    <th className="py-2.5 px-2 text-right">Cash-Match B</th>
                    <th className="py-2.5 px-2 text-right">10-Slot Equal Budget</th>
                    <th className="py-2.5 px-2 text-right">10-Slot DD</th>
                    <th className="py-2.5 px-2 text-right">Daily Cap Trim</th>
                    <th className="py-2.5 px-2 text-right">Ex-SOTETEL</th>
                    <th className="py-2.5 px-2 text-right">95% Bootstrap CI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {reports.map((r) => {
                    const rn = r.risk_normalized_metrics;
                    const isSelected = r.strategy_id === selectedReport?.strategy_id;
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
                          <div className="font-mono font-semibold text-slate-100">
                            {SHORT_LABELS[r.strategy_id] || r.strategy_id}
                          </div>
                        </td>
                        <td className="py-2.5 px-2 text-right text-emerald-400 font-semibold">
                          {formatPct(r.net_return_pct)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {formatPct(
                            rn?.active_cash_utilization_pct ?? r.avg_cash_utilization_pct,
                            false
                          )}
                        </td>
                        <td className="py-2.5 px-2 text-right text-sky-300 font-semibold">
                          {formatPct(rn?.exposure_normalized_return_pct ?? r.net_return_pct)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-amber-300">
                          -{formatPct(rn?.exposure_normalized_max_drawdown_pct ?? r.max_drawdown_pct, false)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {formatPct(rn?.realized_annualized_volatility_pct ?? 0, false)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-emerald-300">
                          {formatPct(rn?.excess_vs_cash_matched_b_pct ?? 0)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-sky-300 font-semibold">
                          {formatPct(rn?.equal_budget_10slot_net_return_pct ?? r.net_return_pct)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-amber-300">
                          -{formatPct(rn?.equal_budget_10slot_max_drawdown_pct ?? r.max_drawdown_pct, false)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-200">
                          {formatPct(
                            rn?.continuous_concentration_trim_net_return_pct ?? r.net_return_pct
                          )}{" "}
                          <span className="text-[10px] text-slate-400">
                            ({formatPct(rn?.continuous_concentration_trim_max_weight_pct ?? r.max_single_stock_weight_pct, false)} max)
                          </span>
                        </td>
                        <td className="py-2.5 px-2 text-right text-amber-200 font-semibold">
                          {formatPct(rn?.ex_top_winner_net_return_pct ?? r.net_return_pct)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-400 text-[11px]">
                          {rn?.bootstrap_return_ci_95
                            ? `[${formatPct(rn.bootstrap_return_ci_95.lower_pct)}, ${formatPct(
                                rn.bootstrap_return_ci_95.upper_pct
                              )}]`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Phase 3: Forward-Only Paper-Trading Journal (Separated from Real Competition Account) */}
          <Card className="border-emerald-500/40 bg-emerald-950/10">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <CardTitle className="flex items-center gap-2 text-emerald-300">
                      <FileSpreadsheet className="h-4 w-4 text-emerald-400" />
                      <span>
                        Phase 3: Forward-Only Paper-Trading Journal (Prospective T+1 Validation)
                      </span>
                    </CardTitle>
                    <Badge variant="success" className="text-[10px]">
                      FORWARD PAPER TRADING — ISOLATED LEDGER
                    </Badge>
                  </div>
                  <CardDescription className="text-slate-300 mt-1">
                    Generates immutable signals strictly from data available at the decision
                    timestamp, records cryptographic model/data hashes, and holds intended orders as{" "}
                    <span className="font-mono text-amber-300">PENDING_NEXT_SESSION</span> until a
                    strictly newer BVMT market session arrives. Never touches{" "}
                    <span className="font-mono">real_competition_ledger.json</span> or submits live
                    orders.
                  </CardDescription>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleRecordForwardSignal}
                  disabled={recordingPaper}
                  className="gap-1.5 shrink-0"
                >
                  <PlayCircle className="h-3.5 w-3.5" />
                  {recordingPaper
                    ? "Recording Forward Signal..."
                    : `Record Forward Signal (${SHORT_LABELS[selectedId] || selectedId})`}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-xs">
              {paperJournal ? (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
                    <div className="rounded-lg bg-slate-950/80 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Journal Mode</div>
                      <div className="font-mono font-bold text-emerald-400 mt-0.5">
                        PAPER ONLY (Manual: 100%)
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/80 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Paper Total Equity</div>
                      <div className="font-mono font-bold text-slate-100 mt-0.5">
                        {formatTnd(paperJournal.total_equity_tnd)} TND (
                        {formatPct(paperJournal.net_return_pct)})
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/80 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Available Paper Cash</div>
                      <div className="font-mono font-bold text-slate-200 mt-0.5">
                        {formatTnd(paperJournal.cash_tnd)} TND
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/80 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Paper Fees &amp; Turnover</div>
                      <div className="font-mono font-bold text-slate-200 mt-0.5">
                        {formatTnd(paperJournal.total_fees_tnd)} TND (
                        {paperJournal.turnover_ratio.toFixed(2)}x)
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/80 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Latest Settled Session</div>
                      <div className="font-mono font-bold text-sky-300 mt-0.5">
                        {paperJournal.latest_settled_session || "Awaiting Next Session"}
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/80 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Immutable Snapshots</div>
                      <div className="font-mono font-bold text-purple-300 mt-0.5">
                        {paperJournal.signal_snapshots.length} Recorded
                      </div>
                    </div>
                  </div>

                  {/* Immutable Signal Snapshots & Hypothetical Forward Orders */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="rounded-lg bg-slate-950/70 p-3 border border-slate-800 space-y-2">
                      <div className="text-[11px] font-semibold uppercase text-slate-400">
                        Immutable Forward Signal Audit Log
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse text-[11px]">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-400">
                              <th className="py-1.5 px-1.5">Snapshot ID</th>
                              <th className="py-1.5 px-1.5">Strategy</th>
                              <th className="py-1.5 px-1.5">Data Session</th>
                              <th className="py-1.5 px-1.5">Config / Data Hash</th>
                              <th className="py-1.5 px-1.5 text-right">Orders</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 font-mono">
                            {paperJournal.signal_snapshots.map((snap) => (
                              <tr key={snap.snapshot_id}>
                                <td className="py-1.5 px-1.5 text-sky-300">{snap.snapshot_id}</td>
                                <td className="py-1.5 px-1.5 text-slate-200">
                                  {SHORT_LABELS[snap.strategy_id] || snap.strategy_id} (v
                                  {snap.model_version})
                                </td>
                                <td className="py-1.5 px-1.5 text-emerald-300">
                                  {snap.market_data_session_date}
                                </td>
                                <td
                                  className="py-1.5 px-1.5 text-slate-400"
                                  title={`Config: ${snap.config_hash} | Data: ${snap.data_hash}`}
                                >
                                  {snap.config_hash.slice(0, 8)}… / {snap.data_hash.slice(0, 8)}…
                                </td>
                                <td className="py-1.5 px-1.5 text-right text-slate-200">
                                  {snap.intended_orders.length}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="rounded-lg bg-slate-950/70 p-3 border border-slate-800 space-y-2">
                      <div className="text-[11px] font-semibold uppercase text-slate-400">
                        Hypothetical Paper Orders (Strict T+1 Next-Session Execution)
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse text-[11px]">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-400">
                              <th className="py-1.5 px-1.5">Instrument</th>
                              <th className="py-1.5 px-1.5">Side</th>
                              <th className="py-1.5 px-1.5">Signal Date</th>
                              <th className="py-1.5 px-1.5 text-right">Req / Fill</th>
                              <th className="py-1.5 px-1.5 text-right">Ref / Exec Price</th>
                              <th className="py-1.5 px-1.5">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 font-mono">
                            {paperJournal.orders.slice(0, 8).map((ord) => (
                              <tr key={ord.order_id}>
                                <td className="py-1.5 px-1.5 text-slate-100 font-semibold">
                                  {ord.instrument_id}
                                </td>
                                <td
                                  className={`py-1.5 px-1.5 uppercase ${
                                    ord.side === "buy" ? "text-emerald-400" : "text-rose-400"
                                  }`}
                                >
                                  {ord.side}
                                </td>
                                <td className="py-1.5 px-1.5 text-slate-300">
                                  {ord.signal_session_date}
                                </td>
                                <td className="py-1.5 px-1.5 text-right text-slate-200">
                                  {ord.requested_shares} / {ord.filled_shares}
                                </td>
                                <td className="py-1.5 px-1.5 text-right text-slate-300">
                                  {ord.signal_close_price_tnd} → {ord.execution_price_tnd || "T+1"}
                                </td>
                                <td className="py-1.5 px-1.5 font-sans">
                                  <Badge
                                    variant={
                                      ord.status === "FILLED"
                                        ? "success"
                                        : ord.status === "PENDING_NEXT_SESSION"
                                        ? "warning"
                                        : "outline"
                                    }
                                    className="text-[10px]"
                                  >
                                    {ord.status}
                                  </Badge>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-slate-400">Initializing forward paper-trading journal...</p>
              )}
            </CardContent>
          </Card>

          {/* Original 5-Slot Baseline & Enhancement Table (Models A through I) */}
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-sky-400" />
                    <span>
                      Standard 5-Slot Historical Backtest Suite: Baselines (A–G) &amp; Enhancements
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
                              <Badge variant="warning" className="text-[10px] px-1.5 py-0">
                                Audited T04
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

          {/* Charts Row: Selected Strategy Equity Curve & Exposure-Normalized / Equal-Budget BarChart */}
          {selectedReport && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-emerald-400" />
                    <span>
                      Historical Equity Curve vs. Buy-and-Hold Benchmark (
                      {selectedReport.strategy_id})
                    </span>
                  </CardTitle>
                  <CardDescription>
                    Retrospective 2026 simulation across {selectedReport.session_count} sessions (
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
                    <span>
                      5-Slot Raw vs. 10-Slot Equal-Budget vs. Ex-SOTETEL Return (A–I)
                    </span>
                  </CardTitle>
                  <CardDescription>
                    Demonstrates impact of capital utilization scaling and single-stock outlier
                    removal
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
                      <Bar name="5-Slot Raw (%)" dataKey="NetReturn" fill="#10b981" />
                      <Bar
                        name="10-Slot Equal Budget (%)"
                        dataKey="EqualBudget10SlotReturn"
                        fill="#38bdf8"
                      />
                      <Bar name="Ex-SOTETEL (%)" dataKey="ExSotetelReturn" fill="#f59e0b" />
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
                    Raw Max DD: -{formatPct(selectedReport.max_drawdown_pct, false)} •
                    Exposure-Normalized Sleeve DD: -
                    {formatPct(
                      selectedReport.risk_normalized_metrics
                        ?.exposure_normalized_max_drawdown_pct ?? selectedReport.max_drawdown_pct,
                      false
                    )}
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
                    Formula, Subperiod Robustness &amp; Outlier Diagnostics (
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
                      <div className="text-[11px] text-slate-400">H1 Rally vs H2 Consolidation</div>
                      <div className="font-mono font-bold text-slate-100 mt-0.5">
                        {formatPct(
                          selectedReport.risk_normalized_metrics?.subperiods
                            ?.h1_2026_spring_rally?.return_pct ?? 0
                        )}{" "}
                        /{" "}
                        {formatPct(
                          selectedReport.risk_normalized_metrics?.subperiods
                            ?.h2_2026_consolidation?.return_pct ?? 0
                        )}
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-950/60 p-2.5 border border-slate-800">
                      <div className="text-[11px] text-slate-400">Top Winner Attribution</div>
                      <div className="font-mono font-bold text-amber-300 mt-0.5">
                        {selectedReport.risk_normalized_metrics?.top_winner_instrument_id || "—"}{" "}
                        (Ex:{" "}
                        {formatPct(
                          selectedReport.risk_normalized_metrics?.ex_top_winner_net_return_pct ??
                            selectedReport.net_return_pct
                        )}
                        )
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

          {/* Strategy Version History, Historical Coverage Audit & Methodological Limitations */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <History className="h-4 w-4 text-purple-400" />
                  <span>Strategy Suite Version History &amp; Archive</span>
                </CardTitle>
                <CardDescription>
                  Preserved experiment records and audit evolution
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs">
                <div className="rounded-lg bg-slate-950/70 p-2.5 border border-emerald-500/30">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-emerald-300">
                      v1.1.0 / robustness_v2
                    </span>
                    <Badge variant="success" className="text-[10px]">
                      Active Registry
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Milestone 5 Independent Audit + Exposure-Normalized, 10-Slot Equal-Budget,
                    Daily Concentration Trim, Ex-SOTETEL &amp; Forward Paper Journal (
                    <span className="font-mono">strategy_experiments_2026.json</span>).
                  </p>
                </div>
                <div className="rounded-lg bg-slate-950/70 p-2.5 border border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-slate-200">v1.0.0 (Milestone 4)</span>
                    <Badge variant="outline" className="text-[10px]">
                      Archived Record
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Initial 9-model (A–I) 5-slot comparative backtest &amp; 7-fold walk-forward
                    preserved byte-for-byte in{" "}
                    <span className="font-mono">strategy_experiments_2026_v1_archive.json</span>.
                  </p>
                </div>
                <div className="rounded-lg bg-slate-950/70 p-2.5 border border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-slate-300">
                      v0.1 (demo-momentum)
                    </span>
                    <Badge variant="outline" className="text-[10px]">
                      Synthetic Only
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    3-bar synthetic fixture smoke test (<span className="font-mono">bvmt demo</span>
                    ); blocked from real-market evaluation.
                  </p>
                </div>
              </CardContent>
            </Card>

            {registry.historical_audit && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Database className="h-4 w-4 text-emerald-400" />
                    <span>Historical Data Coverage &amp; Blockers (2020–2026)</span>
                  </CardTitle>
                  <CardDescription>
                    Checksum Verified:{" "}
                    {registry.historical_audit.canonical_checksum_matches ? "Yes" : "No"} • Corp
                    Actions: Absent
                  </CardDescription>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                        <th className="py-1.5 px-1.5">Year</th>
                        <th className="py-1.5 px-1.5 text-right">Sessions</th>
                        <th className="py-1.5 px-1.5">Daily OHLCV</th>
                        <th className="py-1.5 px-1.5">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {Object.entries(registry.historical_audit.coverage_2020_2026).map(
                        ([year, cov]) => (
                          <tr key={year} className="hover:bg-slate-900/40">
                            <td className="py-1.5 px-1.5 text-slate-200 font-semibold">{year}</td>
                            <td className="py-1.5 px-1.5 text-right text-slate-300">
                              {cov.canonical_sessions}
                            </td>
                            <td className="py-1.5 px-1.5 font-sans">
                              {cov.daily_ohlcv_available ? (
                                <Badge variant="success" className="text-[10px]">
                                  Verified (194d)
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-[10px]">
                                  Blocked
                                </Badge>
                              )}
                            </td>
                            <td className="py-1.5 px-1.5 text-slate-400 text-[10px]">
                              {cov.status}
                            </td>
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
                  <span>Research Confidence &amp; Disclosed Limitations</span>
                </CardTitle>
                <CardDescription>
                  Mandatory disclosures enforced across all Strategy Lab views
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-xs text-slate-300">
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
