"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Wallet,
  TrendingUp,
  Trophy,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Briefcase,
  SlidersHorizontal,
  Info,
} from "lucide-react";
import {
  api,
  AccountOverviewResponse,
  HoldingsResponse,
  StockRankingsResponse,
} from "@/lib/api";
import { formatTnd, formatPct, formatTimestamp } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";
import { usePortfolioMode } from "@/components/app-shell";
import { SyncConfirmationBanner } from "@/components/sync-banner";

export default function OverviewPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [overview, setOverview] = useState<AccountOverviewResponse | null>(null);
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [rankings, setRankings] = useState<StockRankingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.getOverview(mode), api.getHoldings(mode), api.getRankings(mode)])
      .then(([ov, hd, rk]) => {
        setOverview(ov);
        setHoldings(hd);
        setRankings(rk);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load overview"))
      .finally(() => setLoading(false));
  }, [mode, refreshTrigger]);

  if (loading && !overview) {
    return (
      <div className="p-16 text-center text-sm text-slate-500 dark:text-slate-400">
        Loading Tunis Bourse Challenge portfolio and official BVMT market data...
      </div>
    );
  }

  if (error || !overview) {
    return (
      <Card className="border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/20">
        <CardContent className="p-6 text-sm text-rose-800 dark:text-rose-300">
          Error loading dashboard state: {error || "Unknown error"}
        </CardContent>
      </Card>
    );
  }

  const web = overview.website_reported;
  const loc = overview.local_valuation;
  const sync = overview.sync_status;
  const mkt = overview.market_status;
  const pnlNum = parseFloat(web.unrealized_pnl_tnd || "0");

  return (
    <div className="space-y-6">
      {/* Page Title & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Account Overview
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Unified view of your authenticated Tunis Bourse Challenge account and verified BVMT
            market quotations.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          {sync.live_synchronized ? (
            <Badge variant="success" className="gap-1.5 py-1 px-3">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Live-Synchronized
            </Badge>
          ) : (
            <Badge variant="warning" className="gap-1.5 py-1 px-3">
              <AlertCircle className="h-3.5 w-3.5" />
              Opening Baseline Snapshot
            </Badge>
          )}
          <Link href="/portfolio">
            <Button variant="primary" size="sm" className="gap-1.5">
              <span>Manage Portfolio & Sync</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Pending Browser Snapshot Banner */}
      <SyncConfirmationBanner />

      {/* Stale warning if any */}
      {sync.is_stale && sync.warning_message && !sync.has_pending_snapshot && (
        <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/80 dark:bg-amber-950/20">
          <CardContent className="p-4 flex items-center gap-3 text-xs text-amber-900 dark:text-amber-200">
            <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
            <span>{sync.warning_message}</span>
          </CardContent>
        </Card>
      )}

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Total Portfolio Equity</CardDescription>
              <div className="flex items-center gap-1.5">
                <MetricHelp metricId="portfolio_reconciliation" />
                <Wallet className="h-4 w-4 text-teal-600 dark:text-teal-400" />
              </div>
            </div>
            <CardTitle className="text-2xl font-mono font-bold text-slate-900 dark:text-slate-100">
              {formatTnd(web.portfolio_total_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Website-Reported Total</span>
              <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                {formatPct(web.overall_performance_pct)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Available Cash (Liquidités)</CardDescription>
              <div className="flex items-center gap-1.5">
                <MetricHelp metricId="exposure" />
                <Briefcase className="h-4 w-4 text-sky-600 dark:text-sky-400" />
              </div>
            </div>
            <CardTitle className="text-2xl font-mono font-bold text-slate-900 dark:text-slate-100">
              {formatTnd(web.available_cash_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Holdings Value</span>
              <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                {formatTnd(web.holdings_value_tnd)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Unrealized P&L</CardDescription>
              <div className="flex items-center gap-1.5">
                <MetricHelp metricId="backtest_return" />
                <TrendingUp className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              </div>
            </div>
            <CardTitle
              className={`text-2xl font-mono font-bold ${
                pnlNum > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : pnlNum < 0
                  ? "text-rose-600 dark:text-rose-400"
                  : "text-slate-900 dark:text-slate-100"
              }`}
            >
              {pnlNum > 0 ? `+${formatTnd(web.unrealized_pnl_tnd)}` : formatTnd(web.unrealized_pnl_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Realized P&L</span>
              <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                {formatTnd(loc.realized_pnl_tnd)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Competition Standing</CardDescription>
              <Trophy className="h-4 w-4 text-amber-500" />
            </div>
            <CardTitle className="text-2xl font-mono font-bold text-amber-600 dark:text-amber-400">
              {web.competition_rank
                ? `#${web.competition_rank.toLocaleString()}`
                : "Unranked"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Total Participants</span>
              <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                {(web.competition_participants || 14530).toLocaleString()}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Dual Provenance & Valuation Comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Competition Website Snapshot (displayp.aspx)</CardTitle>
                <CardDescription className="mt-1">
                  Reported by Tunis Bourse Challenge at last confirmed snapshot
                </CardDescription>
              </div>
              <Badge variant={web.live_synchronized ? "success" : "warning"}>
                {web.snapshot_id}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 p-3.5 border border-slate-200 dark:border-slate-800">
              <div>
                <p className="text-slate-500 dark:text-slate-400">Portfolio Total</p>
                <p className="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                  {formatTnd(web.portfolio_total_tnd)}
                </p>
              </div>
              <div>
                <p className="text-slate-500 dark:text-slate-400">Holdings Market Value</p>
                <p className="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                  {formatTnd(web.holdings_value_tnd)}
                </p>
              </div>
              <div>
                <p className="text-slate-500 dark:text-slate-400">Website Unrealized P&L</p>
                <p className="text-sm font-mono font-semibold text-emerald-600 dark:text-emerald-400 mt-0.5">
                  {pnlNum > 0
                    ? `+${formatTnd(web.unrealized_pnl_tnd)}`
                    : formatTnd(web.unrealized_pnl_tnd)}
                </p>
              </div>
              <div>
                <p className="text-slate-500 dark:text-slate-400">Last Confirmed Sync</p>
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300 mt-0.5">
                  {formatTimestamp(web.capture_timestamp)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Local Mark-to-Market & Data Status</CardTitle>
                <CardDescription className="mt-1">
                  Independent valuation against official Bourse de Tunis daily quotations
                </CardDescription>
              </div>
              <Badge variant={mkt.is_synthetic ? "warning" : "info"}>
                {mkt.is_synthetic ? "Synthetic Demo Data" : "Verified Official BVMT"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 p-3.5 border border-slate-200 dark:border-slate-800">
              <div>
                <p className="text-slate-500 dark:text-slate-400">Latest Market Session</p>
                <p className="text-sm font-mono font-semibold text-teal-700 dark:text-teal-400 mt-0.5">
                  {mkt.latest_session_date || "N/A"}
                </p>
              </div>
              <div>
                <p className="text-slate-500 dark:text-slate-400">Dataset Coverage</p>
                <p className="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                  {mkt.unique_sessions} sessions • {mkt.unique_instruments} stocks
                </p>
              </div>
              <div>
                <p className="text-slate-500 dark:text-slate-400">Local Marked Equity</p>
                <p className="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                  {formatTnd(loc.total_equity_tnd)}
                </p>
              </div>
              <div>
                <p className="text-slate-500 dark:text-slate-400">Dataset Source</p>
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300 mt-0.5 truncate">
                  {mkt.dataset_label}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Active Holdings Summary & Top Opportunities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Current Holdings</CardTitle>
              <CardDescription className="mt-1">
                Active equity positions in your competition portfolio
              </CardDescription>
            </div>
            <Link
              href="/portfolio"
              className="text-xs font-medium text-teal-700 hover:text-teal-800 dark:text-teal-400 dark:hover:underline"
            >
              Full Portfolio →
            </Link>
          </CardHeader>
          <CardContent>
            {holdings && holdings.holdings.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400">
                    <tr className="border-b border-slate-200 dark:border-slate-800">
                      <th className="py-2.5 px-3 font-semibold">Stock</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Shares</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Last Price</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Market Value</th>
                      <th className="py-2.5 px-3 font-semibold text-right">P&L</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {holdings.holdings.map((h) => {
                      const g = parseFloat(h.website_unrealized_pnl_tnd || "0");
                      return (
                        <tr key={h.instrument_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                          <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-slate-100">
                            {h.symbol}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono">{h.quantity}</td>
                          <td className="py-2.5 px-3 text-right font-mono">
                            {formatTnd(h.website_last_price_tnd)}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900 dark:text-slate-100">
                            {formatTnd(h.website_market_value_tnd)}
                          </td>
                          <td
                            className={`py-2.5 px-3 text-right font-mono font-medium ${
                              g > 0
                                ? "text-emerald-600 dark:text-emerald-400"
                                : g < 0
                                ? "text-rose-600 dark:text-rose-400"
                                : "text-slate-600 dark:text-slate-300"
                            }`}
                          >
                            {g > 0
                              ? `+${formatTnd(h.website_unrealized_pnl_tnd)}`
                              : formatTnd(h.website_unrealized_pnl_tnd)}{" "}
                            ({formatPct(h.website_unrealized_return_pct)})
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-500 dark:text-slate-400 py-4">
                No active equity holdings.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Top Quantitative Signals ({rankings?.session_date || "Latest"})</CardTitle>
              <CardDescription className="mt-1">
                Current session momentum and liquidity rankings
              </CardDescription>
            </div>
            <Link
              href="/market"
              className="text-xs font-medium text-teal-700 hover:text-teal-800 dark:text-teal-400 dark:hover:underline"
            >
              Market Explorer →
            </Link>
          </CardHeader>
          <CardContent>
            {rankings && rankings.rankings.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400">
                    <tr className="border-b border-slate-200 dark:border-slate-800">
                      <th className="py-2.5 px-3 font-semibold">Rank</th>
                      <th className="py-2.5 px-3 font-semibold">Symbol</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Close</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Score</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Decision</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {rankings.rankings.slice(0, 5).map((r) => (
                      <tr key={r.instrument_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                        <td className="py-2.5 px-3 font-mono text-slate-500">#{r.rank ?? "-"}</td>
                        <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-slate-100">
                          {r.symbol}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono">{formatTnd(r.close_tnd)}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-medium text-teal-700 dark:text-teal-300">
                          {r.composite_score !== null ? r.composite_score.toFixed(3) : "N/A"}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <Badge
                            variant={
                              r.recommendation_category === "BUY CANDIDATE"
                                ? "success"
                                : r.recommendation_category === "HOLD"
                                ? "info"
                                : "default"
                            }
                          >
                            {r.recommendation_category}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-500 dark:text-slate-400 py-4">
                No rankings available.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
