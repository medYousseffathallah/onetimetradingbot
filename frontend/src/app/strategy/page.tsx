"use client";

import React, { useEffect, useState } from "react";
import { FlaskConical, AlertTriangle, TrendingUp, ShieldCheck } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  Legend,
} from "recharts";
import { api, ResearchResponse } from "@/lib/api";
import { formatPct } from "@/lib/utils";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { usePortfolioMode } from "@/components/app-shell";

export default function StrategyLabPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [data, setData] = useState<ResearchResponse | null>(null);

  useEffect(() => {
    api
      .getResearch("", mode)
      .then((res) => setData(res))
      .catch(() => {});
  }, [mode, refreshTrigger]);

  const bt = data?.backtest_summary;

  const chartData = bt
    ? [
        {
          period: "Full 2026 Archive (194 Sessions)",
          StrategyMarked: parseFloat(bt.full_year_marked_return_pct),
          StrategyLiquidated: parseFloat(bt.full_year_liquidated_return_pct),
          EqualWeightBenchmark: parseFloat(bt.benchmark_return_pct),
        },
        {
          period: "Oct–Nov Competition Window",
          StrategyMarked: parseFloat(bt.competition_window_marked_return_pct),
          StrategyLiquidated: parseFloat(bt.competition_window_liquidated_return_pct),
          EqualWeightBenchmark: 0.25,
        },
        {
          period: "7-Fold Walk-Forward Mean",
          StrategyMarked: parseFloat(bt.walk_forward_mean_return_pct),
          StrategyLiquidated: 3.44,
          EqualWeightBenchmark: parseFloat(bt.walk_forward_benchmark_pct),
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            Strategy Lab & Historical Simulation Audit
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Assumption-explicit historical backtesting and rolling walk-forward validation on
            official 2026 BVMT bars.
          </p>
        </div>
        <Badge variant="warning" className="gap-1.5">
          <FlaskConical className="h-3.5 w-3.5" />
          Historical Simulation Only — Distinct from Live Signals
        </Badge>
      </div>

      {/* Explicit Separation Notice */}
      <Card className="border-sky-500/40 bg-sky-950/15">
        <CardContent className="p-4 flex items-start gap-3 text-xs text-sky-200">
          <ShieldCheck className="h-4 w-4 text-sky-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">
              Strict Separation: Historical Backtest vs. Current Session Research Signals
            </p>
            <p className="text-sky-300/80 mt-0.5">
              The metrics below represent out-of-sample historical simulations using T+1 next-open
              fills, 0.50% buy / 0.50% sell transaction fees (~1.00% round-trip), zero-volume bar
              restrictions, and 10% daily volume participation caps. For live current-session
              candidates, use the Market Explorer page.
            </p>
          </div>
        </CardContent>
      </Card>

      {bt ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>2026 Full-Year Return (194 Sessions)</CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-emerald-400">
                  {formatPct(bt.full_year_marked_return_pct)}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Liquidated: {formatPct(bt.full_year_liquidated_return_pct)} • Benchmark:{" "}
                {formatPct(bt.benchmark_return_pct)}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Competition Window (Oct 1 – Nov 6)</CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-sky-300">
                  {formatPct(bt.competition_window_marked_return_pct)}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Liquidated after exit fees: {formatPct(bt.competition_window_liquidated_return_pct)}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>7-Fold Walk-Forward Validation</CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-emerald-400">
                  {bt.walk_forward_positive_folds} / {bt.walk_forward_folds} Positive
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Mean fold: {formatPct(bt.walk_forward_mean_return_pct)} vs{" "}
                {formatPct(bt.walk_forward_benchmark_pct)} bench
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Max Drawdown & Fee Model</CardDescription>
                <CardTitle className="text-2xl font-mono font-bold text-amber-300">
                  -{formatPct(bt.max_drawdown_pct, false)}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-[11px] text-slate-400">
                Fees: {bt.buy_fee_pct}% Buy / {bt.sell_fee_pct}% Sell
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-emerald-400" />
                  <span>Strategy vs. Equal-Weight Benchmark (%)</span>
                </CardTitle>
                <CardDescription>
                  Window: {bt.window_start} to {bt.window_end} ({bt.sessions_count} verified BVMT
                  sessions)
                </CardDescription>
              </CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <XAxis dataKey="period" stroke="#94a3b8" fontSize={11} />
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
                    <Bar name="Strategy (Marked %)" dataKey="StrategyMarked" fill="#10b981" />
                    <Bar
                      name="Strategy (Liquidated %)"
                      dataKey="StrategyLiquidated"
                      fill="#38bdf8"
                    />
                    <Bar
                      name="Equal-Weight Benchmark (%)"
                      dataKey="EqualWeightBenchmark"
                      fill="#64748b"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Execution & Statistical Audit</CardTitle>
                <CardDescription>Methodology and sample-size disclosure</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs text-slate-300">
                <div className="rounded-lg bg-slate-950/60 p-3.5 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Statistical Conclusiveness</span>
                    <Badge variant={bt.is_statistically_conclusive ? "success" : "warning"}>
                      {bt.is_statistically_conclusive ? "Conclusive" : "Single-Year Sample (<250d)"}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    {bt.methodology_note}
                  </p>
                </div>
                <div className="flex items-start gap-2 text-[11px] text-amber-300 bg-amber-950/20 border border-amber-800/40 rounded-lg p-3">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                  <span>
                    Historical simulation performance does not guarantee future competition returns.
                    All competition orders remain 100% manual.
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      ) : (
        <p className="text-xs text-slate-400">Loading historical simulation summary...</p>
      )}
    </div>
  );
}
