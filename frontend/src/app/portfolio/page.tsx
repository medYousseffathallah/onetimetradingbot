"use client";

import React, { useEffect, useState } from "react";
import {
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Trophy,
  Wallet,
  TrendingUp,
  Clock,
  Layers,
} from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
} from "recharts";
import {
  api,
  AccountOverviewResponse,
  HoldingsResponse,
  SnapshotsResponse,
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

const COLORS = ["#0d9488", "#0284c7", "#f59e0b", "#8b5cf6"];

export default function PortfolioPage() {
  const { mode, refreshTrigger, triggerRefresh } = usePortfolioMode();
  const [overview, setOverview] = useState<AccountOverviewResponse | null>(null);
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotsResponse | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.getOverview(mode), api.getHoldings(mode), api.getSnapshots(mode)])
      .then(([ov, hd, sn]) => {
        setOverview(ov);
        setHoldings(hd);
        setSnapshots(sn);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mode, refreshTrigger]);

  const handleSyncNow = async () => {
    setSyncing(true);
    setSyncMessage(
      "Launching read-only browser window... Please log in manually to Tunis Bourse Challenge (displayp.aspx)."
    );
    setSyncError(null);
    try {
      const res = await api.triggerBrowserSync(180);
      setSyncMessage(
        `Snapshot captured (${formatTnd(
          res.captured_snapshot.portfolio_total_tnd
        )}) — review and confirm below to apply.`
      );
      triggerRefresh();
    } catch (err: unknown) {
      setSyncError(
        err instanceof Error ? err.message : "Browser synchronization failed or timed out."
      );
      setSyncMessage(null);
    } finally {
      setSyncing(false);
    }
  };

  if (loading && !overview) {
    return (
      <div className="p-16 text-center text-sm text-slate-500 dark:text-slate-400">
        Loading portfolio state and reconciliation history...
      </div>
    );
  }

  if (!overview || !holdings) {
    return (
      <Card className="border-rose-200 dark:border-rose-900 bg-rose-50/80 dark:bg-rose-950/20">
        <CardContent className="p-6 text-sm text-rose-800 dark:text-rose-300">
          Unable to load portfolio data. Ensure the local FastAPI service is running.
        </CardContent>
      </Card>
    );
  }

  const web = overview.website_reported;
  const loc = overview.local_valuation;
  const sync = overview.sync_status;
  const pnlNum = parseFloat(web.unrealized_pnl_tnd || "0");

  const cashVal = parseFloat(web.available_cash_tnd || "0");
  const holdingsVal = parseFloat(web.holdings_value_tnd || "0");
  const pieData = [
    { name: "Available Cash (TND)", value: cashVal },
    ...holdings.holdings.map((h) => ({
      name: h.symbol,
      value: parseFloat(h.website_market_value_tnd || "0"),
    })),
  ];

  return (
    <div className="space-y-6">
      {/* Header & Sync Now Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Competition Portfolio & Sync
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Read-only browser synchronization, confirmation-gated reconciliation, and dual
            valuation audit.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {sync.has_pending_snapshot ? (
            <Badge variant="warning" className="gap-1.5 py-1 px-3">
              <AlertTriangle className="h-3.5 w-3.5" />
              Snapshot Awaiting Confirmation
            </Badge>
          ) : sync.live_synchronized ? (
            <Badge variant="success" className="gap-1.5 py-1 px-3">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Confirmed & Synchronized
            </Badge>
          ) : (
            <Badge variant="warning" className="py-1 px-3">
              Baseline Snapshot
            </Badge>
          )}

          {mode === "REAL_COMPETITION" && (
            <Button
              variant="primary"
              size="md"
              disabled={syncing}
              onClick={handleSyncNow}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
              <span>{syncing ? "Waiting for Browser Login..." : "Sync Portfolio"}</span>
            </Button>
          )}
        </div>
      </div>

      {syncMessage && (
        <Card className="border-sky-200 dark:border-sky-900 bg-sky-50/80 dark:bg-sky-950/20">
          <CardContent className="p-4 text-xs text-sky-900 dark:text-sky-200">{syncMessage}</CardContent>
        </Card>
      )}

      {syncError && (
        <Card className="border-rose-200 dark:border-rose-900 bg-rose-50/80 dark:bg-rose-950/20">
          <CardContent className="p-4 text-xs text-rose-800 dark:text-rose-300">{syncError}</CardContent>
        </Card>
      )}

      {/* Confirmation Banner */}
      <SyncConfirmationBanner />

      {/* Prominent Portfolio Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Portfolio Equity</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="portfolio_reconciliation" />
                <Wallet className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
              </div>
            </div>
            <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
              {formatTnd(web.portfolio_total_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            Reconciled Cash + Holdings
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Available Cash</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="exposure" />
                <Layers className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />
              </div>
            </div>
            <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
              {formatTnd(web.available_cash_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            Holdings: {formatTnd(web.holdings_value_tnd)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Unrealized & Realized P&L</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="backtest_return" />
                <TrendingUp className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              </div>
            </div>
            <CardTitle
              className={`text-xl font-mono font-bold ${
                pnlNum > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : pnlNum < 0
                  ? "text-rose-600 dark:text-rose-400"
                  : "text-slate-900 dark:text-slate-100"
              }`}
            >
              {pnlNum > 0
                ? `+${formatTnd(web.unrealized_pnl_tnd)}`
                : formatTnd(web.unrealized_pnl_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            Realized: {formatTnd(loc.realized_pnl_tnd)} ({formatPct(web.overall_performance_pct)})
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Competition Ranking</CardDescription>
              <Trophy className="h-3.5 w-3.5 text-amber-500" />
            </div>
            <CardTitle className="text-xl font-mono font-bold text-amber-600 dark:text-amber-400">
              {web.competition_rank
                ? `#${web.competition_rank.toLocaleString()} / ${(
                    web.competition_participants || 14530
                  ).toLocaleString()}`
                : "Unranked"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            {web.competition_window || "2026–2027 Edition"}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Last Successful Sync</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="source_provenance" />
                <Clock className="h-3.5 w-3.5 text-slate-400" />
              </div>
            </div>
            <CardTitle className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              {formatTimestamp(web.capture_timestamp)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400 truncate">
            {web.snapshot_id}
          </CardContent>
        </Card>
      </div>

      {/* Holdings Table + Allocation Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Authenticated Holdings & Mark-to-Market</CardTitle>
            <CardDescription>
              Displays website figures (displayp.aspx) alongside verified BVMT quotations (
              {loc.latest_market_session || "latest"})
            </CardDescription>
          </CardHeader>
          <CardContent>
            {holdings.holdings.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-900 text-xs text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-3 px-3 font-semibold">Stock</th>
                      <th className="py-3 px-3 font-semibold text-right">Shares</th>
                      <th className="py-3 px-3 font-semibold text-right">Acq. Price</th>
                      <th className="py-3 px-3 font-semibold text-right">Acq. Cost</th>
                      <th className="py-3 px-3 font-semibold text-right">Website Price</th>
                      <th className="py-3 px-3 font-semibold text-right">Market Value</th>
                      <th className="py-3 px-3 font-semibold text-right">Unrealized P&L</th>
                      <th className="py-3 px-3 font-semibold text-right">BVMT Close</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {holdings.holdings.map((h) => {
                      const pnl = parseFloat(h.website_unrealized_pnl_tnd || "0");
                      return (
                        <tr key={h.instrument_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                          <td className="py-3 px-3">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">{h.symbol}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                              {h.isin || h.instrument_id} • Weight {formatPct(h.weight_pct, false)}
                            </div>
                          </td>
                          <td className="py-3 px-3 text-right font-mono">{h.quantity}</td>
                          <td className="py-3 px-3 text-right font-mono">
                            {formatTnd(h.acquisition_price_tnd)}
                          </td>
                          <td className="py-3 px-3 text-right font-mono">
                            {formatTnd(h.acquisition_amount_tnd)}
                          </td>
                          <td className="py-3 px-3 text-right font-mono text-teal-700 dark:text-teal-300 font-medium">
                            {formatTnd(h.website_last_price_tnd)}
                          </td>
                          <td className="py-3 px-3 text-right font-mono font-semibold text-slate-900 dark:text-slate-100">
                            {formatTnd(h.website_market_value_tnd)}
                          </td>
                          <td
                            className={`py-3 px-3 text-right font-mono font-semibold ${
                              pnl > 0
                                ? "text-emerald-600 dark:text-emerald-400"
                                : pnl < 0
                                ? "text-rose-600 dark:text-rose-400"
                                : "text-slate-700 dark:text-slate-200"
                            }`}
                          >
                            {pnl > 0
                              ? `+${formatTnd(h.website_unrealized_pnl_tnd)}`
                              : formatTnd(h.website_unrealized_pnl_tnd)}
                            <div className="text-xs font-normal">
                              {formatPct(h.website_unrealized_return_pct)}
                            </div>
                          </td>
                          <td className="py-3 px-3 text-right font-mono text-slate-600 dark:text-slate-300">
                            {h.verified_market_price_tnd
                              ? formatTnd(h.verified_market_price_tnd)
                              : "N/A"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">
                No active holdings in portfolio.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Capital Allocation</CardTitle>
              <MetricHelp metricId="exposure" />
            </div>
            <CardDescription>
              Cash vs Equity Exposure ({formatPct((holdingsVal / (cashVal + holdingsVal || 1)) * 100, false)}{" "}
              invested)
            </CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {pieData.map((_, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip
                  formatter={(value: number) => formatTnd(value)}
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    borderColor: "#cbd5e1",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#0f172a",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Snapshot & Reconciliation History */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Confirmed Snapshot History & Audit Trail</CardTitle>
              <CardDescription className="mt-1">
                Immutable record of confirmed competition snapshots and captured browser syncs
              </CardDescription>
            </div>
            <MetricHelp metricId="portfolio_reconciliation" />
          </div>
        </CardHeader>
        <CardContent>
          {snapshots && snapshots.confirmed_history.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Snapshot ID</th>
                    <th className="py-2.5 px-3 font-semibold">Timestamp</th>
                    <th className="py-2.5 px-3 font-semibold">Provenance</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Portfolio Total</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Available Cash</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Rank</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {snapshots.confirmed_history.map((s) => (
                    <tr key={`${s.snapshot_id}-${s.capture_timestamp}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 font-mono font-medium text-slate-800 dark:text-slate-200">
                        {s.snapshot_id}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600 dark:text-slate-300">
                        {formatTimestamp(s.capture_timestamp)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-500 dark:text-slate-400">
                        {s.live_synchronized ? "Authenticated Browser DOM Sync" : "Opening Screenshot Baseline"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900 dark:text-slate-100">
                        {formatTnd(s.portfolio_total_tnd)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-700 dark:text-slate-300">
                        {formatTnd(s.available_cash_tnd)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-amber-600 dark:text-amber-400 font-medium">
                        {s.competition_rank ? `#${s.competition_rank.toLocaleString()}` : "N/A"}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Badge variant={s.live_synchronized ? "success" : "outline"}>
                          {s.live_synchronized ? "Confirmed Live Sync" : "Opening Baseline"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-500 dark:text-slate-400">No snapshot history recorded yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
