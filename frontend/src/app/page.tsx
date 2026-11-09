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
  AlertTriangle,
  Clock,
  Sparkles,
  ShieldAlert,
  ChevronRight,
  Scale,
  Percent,
} from "lucide-react";
import {
  api,
  AccountOverviewResponse,
  HoldingsResponse,
  StockRankingsResponse,
  MultiHorizonIntelligenceReport,
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

export default function HomePage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [overview, setOverview] = useState<AccountOverviewResponse | null>(null);
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [rankings, setRankings] = useState<StockRankingsResponse | null>(null);
  const [intelligence, setIntelligence] = useState<MultiHorizonIntelligenceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.getOverview(mode),
      api.getHoldings(mode),
      api.getRankings(mode),
      api.getTradingIntelligence("ALL", mode).catch(() => null),
    ])
      .then(([ov, hd, rk, intell]) => {
        setOverview(ov);
        setHoldings(hd);
        setRankings(rk);
        setIntelligence(intell);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard state"))
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
  const totalEqNum = parseFloat(web.portfolio_total_tnd || "50000");
  const cashNum = parseFloat(web.available_cash_tnd || "50000");
  const holdingsNum = parseFloat(web.holdings_value_tnd || "0");
  const cashWeightPct = totalEqNum > 0 ? ((cashNum / totalEqNum) * 100).toFixed(1) : "100.0";
  const investedWeightPct = totalEqNum > 0 ? ((holdingsNum / totalEqNum) * 100).toFixed(1) : "0.0";

  return (
    <div className="space-y-8">
      {/* Top Banner / Session Welcome */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-teal-700 dark:text-teal-400">
              Monday, November 9, 2026 • Decision Support
            </span>
            <Badge variant="outline" className="text-[11px]">
              Session As-Of: {mkt.latest_session_date || "2026-11-06"}
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
            Investment Portfolio & Market Pulse
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Calm, source-grounded decision intelligence for your Tunis Bourse Challenge equity account.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {sync.live_synchronized ? (
            <Badge variant="success" className="gap-1.5 py-1 px-3">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Snapshot Confirmed</span>
            </Badge>
          ) : (
            <Badge variant="warning" className="gap-1.5 py-1 px-3">
              <AlertCircle className="h-3.5 w-3.5" />
              <span>Opening Baseline</span>
            </Badge>
          )}
          <Link href="/planner">
            <Button variant="primary" size="sm" className="gap-1.5">
              <span>Open Trade Planner</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Sync Confirmation Banner */}
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

      {/* QUESTION 1: HOW MUCH MONEY DO I HAVE? */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-teal-600" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Question 1 — How much money do I have?
            </h2>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Source: Tunis Bourse Challenge Confirmed Snapshot
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Equity */}
          <Card className="border-teal-200/80 dark:border-teal-900/50 bg-gradient-to-br from-teal-50/30 via-white to-white dark:from-teal-950/20 dark:via-slate-950 dark:to-slate-950">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Total Account Value</CardDescription>
                <div className="flex items-center gap-1.5">
                  <MetricHelp metricId="portfolio_reconciliation" />
                  <Wallet className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                </div>
              </div>
              <CardTitle className="text-2xl sm:text-3xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {formatTnd(web.portfolio_total_tnd)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>Baseline: 50,000.000 TND</span>
                <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                  {formatPct(web.overall_performance_pct)}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Liquid Cash */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Available Cash (Liquidités)</CardDescription>
                <div className="flex items-center gap-1.5">
                  <MetricHelp metricId="exposure" />
                  <Briefcase className="h-4 w-4 text-sky-600 dark:text-sky-400" />
                </div>
              </div>
              <CardTitle className="text-2xl sm:text-3xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {formatTnd(web.available_cash_tnd)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>Cash Ratio</span>
                <span className="font-mono text-sky-700 dark:text-sky-400 font-medium">
                  {cashWeightPct}% Liquid
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Invested Equity */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Stock Holdings Value</CardDescription>
                <div className="flex items-center gap-1.5">
                  <MetricHelp metricId="backtest_return" />
                  <Scale className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                </div>
              </div>
              <CardTitle className="text-2xl sm:text-3xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {formatTnd(web.holdings_value_tnd)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>Allocation</span>
                <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                  {investedWeightPct}% Invested ({holdings?.holdings.length || 0} stocks)
                </span>
              </div>
            </CardContent>
          </Card>

          {/* National Standing */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>National Standing</CardDescription>
                <Trophy className="h-4 w-4 text-amber-500" />
              </div>
              <CardTitle className="text-2xl sm:text-3xl font-mono font-bold text-amber-600 dark:text-amber-400">
                {web.competition_rank ? `#${web.competition_rank.toLocaleString()}` : "#133"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>Top 1.0% Nationally</span>
                <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                  of {(web.competition_participants || 14547).toLocaleString()}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* QUESTION 2: WHAT DESERVES ATTENTION TODAY? */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-amber-500" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Question 2 — What deserves attention today?
            </h2>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Multi-Horizon Risk & Opportunity Checks
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Attention 1: Concentration Cap on Delice Holding */}
          <Card className="border-amber-200 dark:border-amber-800/70 bg-amber-50/40 dark:bg-amber-950/20">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <Badge variant="warning" className="text-[11px]">
                  PORTFOLIO RISK
                </Badge>
                <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              </div>
              <CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100 mt-2">
                Delice Holding Concentration Cap
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-slate-600 dark:text-slate-300">
              <p>
                You hold <strong className="font-mono text-slate-900 dark:text-slate-100">263 shares of DH</strong> valued at{" "}
                <strong className="font-mono text-slate-900 dark:text-slate-100">5,021.99 TND</strong> (9.998% of total portfolio equity).
              </p>
              <div className="p-2 rounded bg-amber-100/70 dark:bg-amber-900/40 border border-amber-200 dark:border-amber-800 text-[11px] font-medium text-amber-900 dark:text-amber-200">
                Rule Alert: Position is directly at the 10.0% competition cap. No additional purchase orders are allowed.
              </div>
              <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                <span>Break-Even: 19.287 TND</span>
                <span>Stop-Loss: 18.140 TND</span>
              </div>
            </CardContent>
          </Card>

          {/* Attention 2: Actionable Swing Candidate */}
          <Card className="border-teal-200 dark:border-teal-800/70 bg-teal-50/40 dark:bg-teal-950/20">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <Badge variant="success" className="text-[11px]">
                  TOP SWING CANDIDATE
                </Badge>
                <Sparkles className="h-4 w-4 text-teal-600 dark:text-teal-400" />
              </div>
              <CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100 mt-2">
                STA (Société Tunisienne d'Automobiles)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-slate-600 dark:text-slate-300">
              <p>
                Rank #1 quantitative leader with <strong className="font-mono text-emerald-600">+5.85% 20s momentum</strong> and{" "}
                <strong className="font-mono text-emerald-600">+12.40% 60s momentum</strong> in the continuous auction group.
              </p>
              <p>
                Deterministic sizing suggests up to <strong className="font-mono text-slate-900 dark:text-slate-100">36 shares</strong> @ 115.900 TND (4,172 TND cost, within 8.5% target allocation).
              </p>
              <div className="pt-2">
                <Link href="/planner">
                  <Button variant="outline" size="sm" className="w-full text-xs gap-1.5 font-medium">
                    <span>Review STA in Trade Planner</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>

          {/* Attention 3: Day Trading Notice */}
          <Card className="border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <Badge variant="default" className="text-[11px]">
                  POLICY & FRICTION NOTICE
                </Badge>
                <ShieldAlert className="h-4 w-4 text-slate-500" />
              </div>
              <CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100 mt-2">
                Day Trading Unavailable
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-slate-600 dark:text-slate-300">
              <p>
                Intraday rapid execution is classified as <strong className="text-slate-800 dark:text-slate-200">RESEARCH_ONLY</strong> on BVMT.
              </p>
              <ul className="list-disc pl-4 space-y-1 text-[11px] text-slate-500 dark:text-slate-400">
                <li>Frontier round-trip fees of 1.00% create severe return drag (-16.8% over 194 sessions).</li>
                <li>Static ±3.0% / ±5.0% volatility collars restrict intraday amplitude.</li>
                <li>Lack of authorized sub-second L2 order-book feeds.</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* QUESTION 3: WHAT INVESTMENTS DO I OWN? */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-600" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Question 3 — What investments do I own?
            </h2>
          </div>
          <Link
            href="/portfolio"
            className="text-xs font-medium text-teal-700 hover:text-teal-800 dark:text-teal-400 dark:hover:underline flex items-center gap-1"
          >
            <span>Manage Portfolio</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <Card>
          <CardContent className="p-0">
            {holdings && holdings.holdings.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900/60 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-3 px-4 font-semibold">Security</th>
                      <th className="py-3 px-4 font-semibold text-right">Shares</th>
                      <th className="py-3 px-4 font-semibold text-right">Avg Cost</th>
                      <th className="py-3 px-4 font-semibold text-right">Market Price</th>
                      <th className="py-3 px-4 font-semibold text-right">Market Value</th>
                      <th className="py-3 px-4 font-semibold text-right">Weight</th>
                      <th className="py-3 px-4 font-semibold text-right">Unrealized P&L</th>
                      <th className="py-3 px-4 font-semibold text-right">Break-Even</th>
                      <th className="py-3 px-4 font-semibold text-right">Action Plan</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {holdings.holdings.map((h) => {
                      const pnl = parseFloat(h.website_unrealized_pnl_tnd || "0");
                      const cost = parseFloat(h.acquisition_price_tnd || "0");
                      const breakEven = (cost * 1.005 / 0.995).toFixed(3);
                      const isNearCap = parseFloat(h.weight_pct || "0") >= 9.5;

                      return (
                        <tr key={h.instrument_id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/30 transition-colors">
                          <td className="py-3 px-4">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">
                              {h.symbol}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              {h.instrument_id === "DH" ? "Délice Holding" : h.instrument_id === "BH" ? "Banque de l'Habitat" : h.instrument_id}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right font-mono font-medium">
                            {h.quantity}
                          </td>
                          <td className="py-3 px-4 text-right font-mono">
                            {formatTnd(h.acquisition_price_tnd)}
                          </td>
                          <td className="py-3 px-4 text-right font-mono font-semibold text-slate-900 dark:text-slate-100">
                            {formatTnd(h.website_last_price_tnd)}
                          </td>
                          <td className="py-3 px-4 text-right font-mono font-bold text-slate-900 dark:text-slate-100">
                            {formatTnd(h.website_market_value_tnd)}
                          </td>
                          <td className="py-3 px-4 text-right font-mono">
                            <div className="inline-flex items-center gap-1 font-semibold">
                              <span>{h.weight_pct}%</span>
                              {isNearCap && (
                                <Badge variant="warning" className="text-[9px] px-1 py-0 font-normal">
                                  CAP
                                </Badge>
                              )}
                            </div>
                          </td>
                          <td
                            className={`py-3 px-4 text-right font-mono font-medium ${
                              pnl > 0
                                ? "text-emerald-600 dark:text-emerald-400"
                                : pnl < 0
                                ? "text-rose-600 dark:text-rose-400"
                                : "text-slate-600"
                            }`}
                          >
                            {pnl > 0 ? `+${formatTnd(h.website_unrealized_pnl_tnd)}` : formatTnd(h.website_unrealized_pnl_tnd)}
                            <div className="text-[10px] text-slate-500">
                              {formatPct(h.website_unrealized_return_pct)}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-slate-500 dark:text-slate-400">
                            {breakEven} TND
                          </td>
                          <td className="py-3 px-4 text-right">
                            <Link href="/planner">
                              <Button variant="outline" size="sm" className="text-[11px] py-1 px-2.5 h-7">
                                Exit Plan →
                              </Button>
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
                No active equity positions currently held.
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* TOP CANDIDATES TO RESEARCH (QUESTION 4: WHAT IS WORTH RESEARCHING?) */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-sky-600" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Question 4 — What stocks are worth researching today?
            </h2>
          </div>
          <Link
            href="/market"
            className="text-xs font-medium text-teal-700 hover:text-teal-800 dark:text-teal-400 dark:hover:underline flex items-center gap-1"
          >
            <span>Discover Stocks (42 Challenge Universe)</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {rankings && rankings.rankings.slice(0, 3).map((r, idx) => (
            <Card key={r.instrument_id} className="hover:border-slate-300 dark:hover:border-slate-700 transition-colors">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-400">#{r.rank || idx + 1}</span>
                    <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100">
                      {r.symbol}
                    </CardTitle>
                  </div>
                  <Badge
                    variant={
                      r.recommendation_category === "BUY CANDIDATE"
                        ? "success"
                        : r.recommendation_category === "HOLD"
                        ? "info"
                        : "default"
                    }
                    className="text-[10px]"
                  >
                    {r.recommendation_category}
                  </Badge>
                </div>
                <CardDescription className="text-xs">
                  Close: <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{formatTnd(r.close_tnd)}</span>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-xs">
                <div className="grid grid-cols-2 gap-2 text-[11px] p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800">
                  <div>
                    <span className="text-slate-500">20s Return:</span>
                    <span className="font-mono font-semibold ml-1 text-emerald-600">
                      {formatPct(r.short_return_pct)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">60s Return:</span>
                    <span className="font-mono font-semibold ml-1 text-emerald-600">
                      {formatPct(r.long_return_pct)}
                    </span>
                  </div>
                </div>
                <Link href="/planner" className="block pt-1">
                  <Button variant="outline" size="sm" className="w-full text-xs justify-between font-medium">
                    <span>Evaluate Trade Sizing</span>
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
