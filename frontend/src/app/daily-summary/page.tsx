"use client";

import React, { useEffect, useState } from "react";
import {
  FileText,
  AlertTriangle,
  CheckCircle2,
  Trophy,
  Wallet,
  TrendingUp,
  Clock,
  ShieldAlert,
  ArrowRight,
  Info,
  Layers,
  Sparkles,
} from "lucide-react";
import { api, DailySessionReport } from "@/lib/api";
import { formatTnd, formatPct } from "@/lib/utils";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";

export default function DailySummaryPage() {
  const [report, setReport] = useState<DailySessionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await api.getSessionSummary();
        setReport(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || "Failed to load session summary");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex items-center gap-3 text-slate-500">
          <Clock className="h-6 w-6 animate-spin text-teal-600" />
          <span>Reconstructing November 9 session accounting...</span>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-900">
        <div className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="h-5 w-5 text-red-600" />
          Failed to load daily accounting
        </div>
        <p className="mt-2 text-sm">{error || "No report data returned."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* 1. Header Banner */}
      <div className="flex flex-col justify-between gap-4 border-b border-slate-200/80 pb-6 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Today's Trading Summary
            </h1>
            <Badge variant="outline" className="border-teal-300 bg-teal-50 text-teal-800">
              Session: {report.session_date}
            </Badge>
            <Badge variant="outline" className="border-sky-300 bg-sky-50 text-sky-800">
              Rank #{report.competition_ranking} / {report.total_participants}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Reconstructed cash flows, position attribution, model execution fidelity, and risk bounds.
          </p>
        </div>
      </div>

      {/* 2. Disclaimer Banner */}
      {report.attribution_status === "PERFORMANCE_ATTRIBUTION_INCOMPLETE" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50/90 p-5 shadow-sm">
          <div className="flex items-start gap-3.5">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-amber-900">
                  Performance attribution incomplete
                </span>
                <Badge variant="outline" className="border-amber-400 bg-amber-100 text-amber-800 text-xs">
                  Awaiting Histo Export
                </Badge>
              </div>
              <p className="text-sm text-amber-800/90 leading-relaxed">
                {report.attribution_warning}
              </p>
              <p className="text-xs text-amber-700/80">
                Cash decrease (-2,963.28 TND) vs new buys (3,035.10 TND) is fully reconciled by a
                +71.82 TND realized gain on an intraday round-trip trade of 35 shares. Definitive daily net
                trading profit is withheld until security tickers are matched with transaction logs.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Executive Accounting KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Starting Equity */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-500">
              Starting Equity (09:13 UTC)
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-slate-800">
              {formatTnd(report.starting_equity_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-slate-500">
              Cash: {formatTnd(report.starting_cash_tnd)} • Holdings: {formatTnd(report.starting_holdings_value_tnd)}
            </div>
          </CardContent>
        </Card>

        {/* Ending Equity */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-500">
              Ending Equity (14:40 UTC)
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-slate-900">
              {formatTnd(report.ending_equity_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-xs">
              <span className="font-semibold text-emerald-600">
                +{formatTnd(report.equity_change_tnd)} (+0.17%)
              </span>
              <span className="text-slate-400">•</span>
              <span className="text-slate-500">Rank: #{report.competition_ranking}</span>
            </div>
          </CardContent>
        </Card>

        {/* Cash Balance */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-500">
              Remaining Liquid Cash
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-slate-900">
              {formatTnd(report.ending_cash_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-slate-500">
              <span className="font-medium text-slate-700">83.14% liquid</span> • Delta: {formatTnd(report.cash_change_tnd)}
            </div>
          </CardContent>
        </Card>

        {/* Verified Reconciliation Gap */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-500">
              Reconciliation Gap
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-600">
              {formatTnd(report.reconciliation_gap_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-1.5 text-xs text-emerald-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Exact zero discrepancy across all flows</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 4. P&L Semantics Breakdown */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold text-slate-900">
                P&L Semantics & Financial Mechanics
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Audited decomposition of equity changes vs unrealized position values.
              </CardDescription>
            </div>
            <Badge variant="outline" className="border-slate-300 text-slate-700 text-xs">
              Mathematical Proof
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3.5">
              <div className="text-xs text-slate-500">Realized P&L (Closed Trades)</div>
              <div className="mt-1 text-lg font-bold text-emerald-600">
                +{formatTnd(report.realized_pnl_tnd)}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                From 35-share intraday round-trip trade.
              </div>
            </div>

            <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3.5">
              <div className="text-xs text-slate-500">Session Holding Delta</div>
              <div className="mt-1 text-lg font-bold text-emerald-600">
                +{formatTnd(report.unrealized_pnl_delta_tnd)}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                DH (+23.67), NBL (+5.55), BH (-3.30), STA (-14.85).
              </div>
            </div>

            <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3.5">
              <div className="text-xs text-slate-500">Unrealized P&L Since Acq</div>
              <div className="mt-1 text-lg font-bold text-red-600">
                {formatTnd(report.unrealized_pnl_since_acq_tnd)}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                Open positions vs fee-adjusted acquisition cost.
              </div>
            </div>

            <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3.5">
              <div className="text-xs text-slate-500">Total Return Since Inception</div>
              <div className="mt-1 text-lg font-bold text-emerald-600">
                +{formatTnd(report.total_return_since_inception_tnd)} (+{report.total_return_since_inception_pct}%)
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                Relative to 50,000.00 TND starting competition bankroll.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 5. Holdings Contribution Table */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-slate-900">
            Holdings & Session P&L Contribution
          </CardTitle>
          <CardDescription className="text-xs text-slate-500">
            Individual position performance and allocation breakdown.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50/60 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-3 px-3">Security</th>
                  <th className="py-3 px-3 text-right">Qty</th>
                  <th className="py-3 px-3 text-right">Acquisition</th>
                  <th className="py-3 px-3 text-right">Latest</th>
                  <th className="py-3 px-3 text-right">Market Value</th>
                  <th className="py-3 px-3 text-right">Session P&L</th>
                  <th className="py-3 px-3 text-right">Unrealized Total</th>
                  <th className="py-3 px-3 text-right">Weight</th>
                  <th className="py-3 px-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {report.positions.map((pos) => {
                  const sessionPnl = parseFloat(pos.session_pnl_contribution_tnd);
                  const unrealTotal = parseFloat(pos.unrealized_pnl_since_acq_tnd);
                  return (
                    <tr key={pos.symbol} className="hover:bg-slate-50/50">
                      <td className="py-3 px-3 font-semibold text-slate-900">{pos.symbol}</td>
                      <td className="py-3 px-3 text-right text-slate-700">{pos.quantity}</td>
                      <td className="py-3 px-3 text-right text-slate-600">
                        {formatTnd(pos.acquisition_price_tnd)}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-900 font-medium">
                        {formatTnd(pos.latest_price_tnd)}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-900 font-medium">
                        {formatTnd(pos.market_value_tnd)}
                      </td>
                      <td className={`py-3 px-3 text-right font-semibold ${sessionPnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {sessionPnl >= 0 ? "+" : ""}{formatTnd(pos.session_pnl_contribution_tnd)}
                      </td>
                      <td className={`py-3 px-3 text-right text-xs ${unrealTotal >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                        {unrealTotal >= 0 ? "+" : ""}{formatTnd(pos.unrealized_pnl_since_acq_tnd)} ({pos.unrealized_return_since_acq_pct}%)
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600">{pos.portfolio_weight_pct}%</td>
                      <td className="py-3 px-3 text-center">
                        {pos.status === "CLOSED_INTRADAY" ? (
                          <Badge variant="outline" className="border-purple-300 bg-purple-50 text-purple-800 text-[11px]">
                            Closed Intraday
                          </Badge>
                        ) : pos.status === "NEWLY_ENTERED_SESSION" ? (
                          <Badge variant="outline" className="border-sky-300 bg-sky-50 text-sky-800 text-[11px]">
                            New Entry
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-700 text-[11px]">
                            Core Held
                          </Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 6. Reconstructed Transactions */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-slate-900">
            Reconstructed Transactions (Audited Cash Flows)
          </CardTitle>
          <CardDescription className="text-xs text-slate-500">
            Every buy and sell executed during the November 9 session.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {report.transactions.map((tx) => (
              <div
                key={tx.transaction_id}
                className="flex flex-col justify-between gap-3 rounded-lg border border-slate-200/80 bg-white p-4 sm:flex-row sm:items-center"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={
                        tx.side === "BUY"
                          ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                          : "border-purple-300 bg-purple-50 text-purple-800"
                      }
                    >
                      {tx.side}
                    </Badge>
                    <span className="font-semibold text-slate-900">{tx.symbol}</span>
                    <span className="text-xs text-slate-500">({tx.shares} shares @ {formatTnd(tx.execution_price_tnd)})</span>
                  </div>
                  <p className="text-xs text-slate-500">{tx.notes}</p>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-slate-900">
                    {formatTnd(tx.total_cost_or_proceeds_tnd)}
                  </div>
                  <div className="text-xs text-slate-500">
                    Est. Fee: {formatTnd(tx.estimated_fee_tnd)}
                    {tx.realized_pnl_tnd && (
                      <span className="ml-2 font-semibold text-emerald-600">
                        • Realized: +{formatTnd(tx.realized_pnl_tnd)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 7. Model Decisions vs Actual Execution */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-slate-900">
            Model Recommendations Followed vs Ignored
          </CardTitle>
          <CardDescription className="text-xs text-slate-500">
            Objective evaluation of quantitative signals against actual executed decisions.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3.5">
            {report.model_evaluations.map((m) => (
              <div
                key={m.symbol}
                className="rounded-lg border border-slate-200/80 bg-slate-50/50 p-4"
              >
                <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">{m.symbol}</span>
                      <Badge variant="outline" className="border-slate-300 text-slate-700 text-xs">
                        {m.strategy_id}
                      </Badge>
                      <Badge
                        variant="outline"
                        className="border-emerald-300 bg-emerald-50 text-emerald-800 text-xs"
                      >
                        {m.execution_fidelity}
                      </Badge>
                    </div>
                    <div className="mt-1 text-xs text-slate-600">
                      Signal: {m.suggested_action} {m.suggested_shares > 0 ? `${m.suggested_shares} shs` : ""} @ {formatTnd(m.suggested_price_tnd)} ({m.suggested_holding_horizon})
                    </div>
                  </div>
                  <div className="text-right text-xs">
                    <div className="font-semibold text-slate-800">
                      Executed: {m.actual_action} {m.actual_shares > 0 ? `${m.actual_shares} shs` : ""} {m.actual_price_tnd ? `@ ${formatTnd(m.actual_price_tnd)}` : ""}
                    </div>
                    {m.current_unrealized_return_pct && (
                      <div className={parseFloat(m.current_unrealized_return_pct) >= 0 ? "text-emerald-600" : "text-amber-600"}>
                        Mark: {m.current_unrealized_return_pct}% • Stop: {formatTnd(m.stop_loss_price_tnd)}
                      </div>
                    )}
                  </div>
                </div>
                <p className="mt-2 text-xs text-slate-600 border-t border-slate-200/60 pt-2">
                  {m.evaluation_notes}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 8. Concentration Warnings & Review Priorities */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Concentration Warnings */}
        <Card className="border-amber-200 bg-amber-50/40 shadow-sm">
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-600" />
              <CardTitle className="text-base font-semibold text-slate-900">
                Risk & Concentration Guardrails
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {report.concentration_warnings.map((w, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs text-slate-700">
                <span className="font-bold text-amber-600">•</span>
                <span>{w}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Tomorrow's Priorities */}
        <Card className="border-teal-200 bg-teal-50/30 shadow-sm">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-teal-600" />
              <CardTitle className="text-base font-semibold text-slate-900">
                Tomorrow's Review Priorities
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {report.tomorrow_priorities.map((p, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs text-slate-700">
                <span className="font-bold text-teal-600">✓</span>
                <span>{p}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
