"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  Database,
  CheckCircle2,
  AlertTriangle,
  Search,
  SlidersHorizontal,
  ChevronRight,
  ChevronDown,
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  ShieldAlert,
  Info,
  ChevronLeft,
  X,
  RotateCcw,
} from "lucide-react";
import {
  api,
  MarketDataStatusResponse,
  StockRankingsResponse,
  StockRankingItem,
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

type FilterTab = "ALL" | "ELIGIBLE" | "REVIEW" | "EXCLUDED";

export default function MarketExplorerPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [mktStatus, setMktStatus] = useState<MarketDataStatusResponse | null>(null);
  const [rankings, setRankings] = useState<StockRankingsResponse | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("ALL");
  const [search, setSearch] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 12;

  useEffect(() => {
    setLoading(true);
    Promise.all([api.getMarketStatus(mode), api.getRankings(mode)])
      .then(([ms, rk]) => {
        setMktStatus(ms);
        setRankings(rk);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mode, refreshTrigger]);

  const mkt = mktStatus?.market_status;
  const allRankings = useMemo(() => rankings?.rankings || [], [rankings]);

  // Tab counts
  const tabCounts = useMemo(() => {
    const eligible = allRankings.filter((r) => r.eligible).length;
    const review = allRankings.filter(
      (r) =>
        (r.eligibility_warnings && r.eligibility_warnings.length > 0) ||
        r.recommendation_category === "HOLD" ||
        r.recommendation_category === "REDUCE"
    ).length;
    const excluded = allRankings.filter((r) => !r.eligible).length;
    return {
      ALL: allRankings.length,
      ELIGIBLE: eligible,
      REVIEW: review,
      EXCLUDED: excluded,
    };
  }, [allRankings]);

  // Filtered rows
  const filteredRows = useMemo(() => {
    return allRankings.filter((r) => {
      // Tab filter
      if (activeTab === "ELIGIBLE" && !r.eligible) return false;
      if (activeTab === "EXCLUDED" && r.eligible) return false;
      if (activeTab === "REVIEW") {
        const hasWarnings = r.eligibility_warnings && r.eligibility_warnings.length > 0;
        const isReviewCat =
          r.recommendation_category === "HOLD" || r.recommendation_category === "REDUCE";
        if (!hasWarnings && !isReviewCat) return false;
      }

      // Search filter
      if (search.trim()) {
        const term = search.toLowerCase();
        const matchSymbol = r.symbol.toLowerCase().includes(term);
        const matchId = r.instrument_id.toLowerCase().includes(term);
        if (!matchSymbol && !matchId) return false;
      }
      return true;
    });
  }, [allRankings, activeTab, search]);

  // Reset pagination when filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab, search]);

  // Paginated slice
  const totalPages = Math.ceil(filteredRows.length / pageSize) || 1;
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredRows.slice(start, start + pageSize);
  }, [filteredRows, currentPage, pageSize]);

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Context Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Market Explorer
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Browse listed equities, analyze momentum indicators, and review research eligibility for
            the Tunis Bourse Challenge.
          </p>
        </div>
        {mkt && (
          <Badge
            variant={mkt.is_synthetic ? "warning" : "success"}
            className="self-start sm:self-auto gap-1.5 py-1 px-3 text-xs"
          >
            {mkt.is_synthetic ? (
              <>
                <AlertTriangle className="h-3.5 w-3.5" />
                <span>Synthetic Demo Dataset</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Official BVMT Verified ({mkt.latest_session_date})</span>
              </>
            )}
          </Badge>
        )}
      </div>

      {/* Plain-Language Introduction Alert */}
      <div className="rounded-xl border border-teal-200/80 bg-teal-50/60 dark:border-teal-900/60 dark:bg-teal-950/30 p-4 text-xs text-teal-900 dark:text-teal-200 flex items-start gap-3 shadow-xs">
        <Info className="h-4 w-4 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-semibold block mb-0.5 text-teal-950 dark:text-teal-100">
            How BVMT Research Signals Work:
          </span>
          Stocks are ranked by a volatility-adjusted momentum model based on verified closing prices.
          To protect capital, only liquid stocks trading on the continuous market (
          <span className="font-mono font-medium">Continu_Principal</span>) with sufficient turnover
          are eligible for trade recommendations. Hover or click the question mark icons{" "}
          <span className="inline-flex items-center text-teal-700 dark:text-teal-300 font-medium">
            (?)
          </span>{" "}
          next to any column for full explanations and formulas.
        </div>
      </div>

      {/* Market Overview Cards */}
      {mkt && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Latest Market Session</CardDescription>
                <MetricHelp metricId="data_freshness" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-teal-700 dark:text-teal-400">
                {mkt.latest_session_date || "N/A"}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              {mkt.sessions_behind === 0 ? (
                <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                  Up to date (0 sessions behind)
                </span>
              ) : (
                <span className="text-amber-600 dark:text-amber-400 font-medium">
                  {mkt.sessions_behind} session(s) behind calendar
                </span>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Listed Equities</CardDescription>
                <MetricHelp metricId="eligibility" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {mkt.unique_instruments} Equities
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              <span className="font-medium text-teal-600 dark:text-teal-400">
                {tabCounts.ELIGIBLE} Continuous
              </span>{" "}
              • {tabCounts.EXCLUDED} Fixing/Excluded
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Historical Archive</CardDescription>
                <MetricHelp metricId="source_provenance" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {mkt.unique_sessions} Sessions
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              {mkt.total_bars.toLocaleString()} daily bars ({mkt.first_session_date} →{" "}
              {mkt.latest_session_date})
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Market Regime</CardDescription>
                <MetricHelp metricId="market_regime" />
              </div>
              <CardTitle className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                Continuous Trading
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              Source: {mkt.source_ids[0] || "official-bvmt"}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Table Card */}
      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <SlidersHorizontal className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                <span>Listed Securities & Signals</span>
              </CardTitle>
              <CardDescription className="mt-1">
                Showing {filteredRows.length} stocks for session {rankings?.session_date || "Latest"}
              </CardDescription>
            </div>

            {/* Controls: Search, Advanced Toggle */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search company or ticker..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 pl-9 pr-3 py-1.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none w-48 sm:w-64"
                />
                {search && (
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>

              {/* Advanced View Toggle */}
              <button
                type="button"
                onClick={() => setShowAdvanced((prev) => !prev)}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  showAdvanced
                    ? "border-teal-500 bg-teal-50 text-teal-800 dark:bg-teal-950/60 dark:text-teal-300 dark:border-teal-600"
                    : "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                }`}
              >
                <span>Advanced Metrics</span>
                <span
                  className={`h-2 w-2 rounded-full ${
                    showAdvanced ? "bg-teal-600 dark:bg-teal-400" : "bg-slate-300 dark:bg-slate-600"
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Filter Pills / Tabs */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={() => setActiveTab("ALL")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "ALL"
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              All Equities ({tabCounts.ALL})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("ELIGIBLE")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "ELIGIBLE"
                  ? "bg-teal-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Eligible ({tabCounts.ELIGIBLE})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("REVIEW")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "REVIEW"
                  ? "bg-amber-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Needs Review ({tabCounts.REVIEW})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("EXCLUDED")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "EXCLUDED"
                  ? "bg-rose-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Excluded ({tabCounts.EXCLUDED})
            </button>
          </div>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="py-16 text-center text-slate-500 dark:text-slate-400">
              <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-teal-600 border-t-transparent mb-2" />
              <p className="text-sm">Loading market quotations and quantitative rankings...</p>
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="py-16 text-center text-slate-500 dark:text-slate-400 space-y-3">
              <SlidersHorizontal className="h-8 w-8 mx-auto text-slate-300 dark:text-slate-600" />
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                No stocks match the selected filter.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setActiveTab("ALL");
                }}
                className="gap-1.5"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Reset Filters</span>
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50/80 dark:bg-slate-900/90 text-xs text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 select-none">
                    <tr>
                      <th className="py-3 px-4 font-semibold">Security / Ticker</th>
                      <th className="py-3 px-4 font-semibold text-right">Latest Price</th>
                      <th className="py-3 px-4 font-semibold text-right">
                        <div className="inline-flex items-center gap-1 justify-end">
                          <span>20-Day Trend</span>
                          <MetricHelp metricId="momentum_20s" />
                        </div>
                      </th>
                      <th className="py-3 px-4 font-semibold text-center">
                        <div className="inline-flex items-center gap-1 justify-center">
                          <span>Liquidity</span>
                          <MetricHelp metricId="liquidity" />
                        </div>
                      </th>

                      {/* Advanced Columns */}
                      {showAdvanced && (
                        <>
                          <th className="py-3 px-3 font-semibold text-right">
                            <div className="inline-flex items-center gap-1 justify-end">
                              <span>Mom (60s)</span>
                              <MetricHelp metricId="momentum_60s" />
                            </div>
                          </th>
                          <th className="py-3 px-3 font-semibold text-right">
                            <div className="inline-flex items-center gap-1 justify-end">
                              <span>Rel. Strength</span>
                              <MetricHelp metricId="relative_strength_20s" />
                            </div>
                          </th>
                          <th className="py-3 px-3 font-semibold text-right">
                            <div className="inline-flex items-center gap-1 justify-end">
                              <span>Volatility</span>
                              <MetricHelp metricId="volatility_20s" />
                            </div>
                          </th>
                          <th className="py-3 px-3 font-semibold text-right">
                            <div className="inline-flex items-center gap-1 justify-end">
                              <span>Med. Turnover</span>
                              <MetricHelp metricId="median_turnover_20s" />
                            </div>
                          </th>
                          <th className="py-3 px-3 font-semibold text-right">
                            <div className="inline-flex items-center gap-1 justify-end">
                              <span>Score</span>
                              <MetricHelp metricId="composite_score" />
                            </div>
                          </th>
                        </>
                      )}

                      <th className="py-3 px-4 font-semibold text-center">
                        <div className="inline-flex items-center gap-1 justify-center">
                          <span>Eligibility</span>
                          <MetricHelp metricId="eligibility" />
                        </div>
                      </th>
                      <th className="py-3 px-4 font-semibold text-right">Details</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                    {paginatedRows.map((r) => {
                      const isExpanded = expandedId === r.instrument_id;
                      const mom20Num = r.short_return_pct ? parseFloat(r.short_return_pct) : 0;
                      const hasWarnings =
                        (r.eligibility_warnings && r.eligibility_warnings.length > 0) ||
                        (r.blocked_reasons && r.blocked_reasons.length > 0);

                      // Determine liquidity category
                      const freq = r.trade_frequency_pct ? parseFloat(r.trade_frequency_pct) : 0;
                      const isHighLiq = freq >= 85;
                      const isMedLiq = freq >= 50 && freq < 85;

                      return (
                        <React.Fragment key={r.instrument_id}>
                          <tr
                            onClick={() => toggleExpand(r.instrument_id)}
                            className={`group cursor-pointer transition-colors ${
                              isExpanded
                                ? "bg-teal-50/40 dark:bg-slate-800/50"
                                : "hover:bg-slate-50 dark:hover:bg-slate-800/30"
                            }`}
                          >
                            {/* Security / Ticker */}
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs text-slate-400 w-6">
                                  {r.rank ? `#${r.rank}` : "—"}
                                </span>
                                <div>
                                  <div className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors">
                                    {r.symbol}
                                  </div>
                                  <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                                    {r.instrument_id}
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Latest Price */}
                            <td className="py-3 px-4 text-right font-mono font-medium text-slate-900 dark:text-slate-100">
                              {r.close_tnd ? formatTnd(r.close_tnd) : "—"}
                            </td>

                            {/* 20-Day Trend */}
                            <td className="py-3 px-4 text-right">
                              {r.short_return_pct !== null ? (
                                <span
                                  className={`inline-flex items-center gap-1 font-mono text-xs font-semibold px-2 py-0.5 rounded ${
                                    mom20Num > 0
                                      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                                      : mom20Num < 0
                                      ? "bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300"
                                      : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                  }`}
                                >
                                  {mom20Num > 0 ? (
                                    <TrendingUp className="h-3 w-3" />
                                  ) : mom20Num < 0 ? (
                                    <TrendingDown className="h-3 w-3" />
                                  ) : (
                                    <Minus className="h-3 w-3" />
                                  )}
                                  <span>{formatPct(r.short_return_pct)}</span>
                                </span>
                              ) : (
                                <span className="text-slate-400 font-mono text-xs">—</span>
                              )}
                            </td>

                            {/* Liquidity Status */}
                            <td className="py-3 px-4 text-center">
                              {isHighLiq ? (
                                <Badge variant="success" className="text-[11px] py-0 px-2 font-normal">
                                  High Liquidity
                                </Badge>
                              ) : isMedLiq ? (
                                <Badge variant="info" className="text-[11px] py-0 px-2 font-normal">
                                  Moderate
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-[11px] py-0 px-2 font-normal text-slate-400">
                                  Low / Thin
                                </Badge>
                              )}
                            </td>

                            {/* Advanced Columns */}
                            {showAdvanced && (
                              <>
                                <td className="py-3 px-3 text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                  {formatPct(r.long_return_pct)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                  {formatPct(r.short_return_pct)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono text-xs text-slate-600 dark:text-slate-400">
                                  {formatPct(r.volatility_pct, false)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                  {formatTnd(r.median_turnover_tnd)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono font-semibold text-xs text-teal-700 dark:text-teal-300">
                                  {r.composite_score !== null ? r.composite_score.toFixed(3) : "—"}
                                </td>
                              </>
                            )}

                            {/* Research Eligibility */}
                            <td className="py-3 px-4 text-center">
                              {r.eligible ? (
                                <Badge variant="success" className="gap-1 text-xs">
                                  <CheckCircle2 className="h-3 w-3" />
                                  <span>Eligible</span>
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-xs text-slate-500">
                                  Excluded
                                </Badge>
                              )}
                            </td>

                            {/* Action / Inspect */}
                            <td className="py-3 px-4 text-right">
                              <button
                                type="button"
                                aria-label="Toggle details"
                                className="inline-flex items-center justify-center p-1 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                              >
                                {isExpanded ? (
                                  <ChevronDown className="h-4 w-4 text-teal-600" />
                                ) : (
                                  <ChevronRight className="h-4 w-4" />
                                )}
                              </button>
                            </td>
                          </tr>

                          {/* Expanded Per-Stock Details Drawer */}
                          {isExpanded && (
                            <tr className="bg-slate-50/70 dark:bg-slate-900/60 border-y border-teal-200/60 dark:border-teal-900/40">
                              <td colSpan={showAdvanced ? 11 : 6} className="p-5">
                                <div className="space-y-4">
                                  {/* Top Details Header */}
                                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                                    <div className="flex items-center gap-3">
                                      <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">
                                        {r.symbol} ({r.instrument_id})
                                      </h4>
                                      <Badge
                                        variant={
                                          r.recommendation_category === "BUY CANDIDATE"
                                            ? "success"
                                            : r.recommendation_category === "HOLD"
                                            ? "info"
                                            : r.recommendation_category === "SELL CANDIDATE" ||
                                              r.recommendation_category === "REDUCE"
                                            ? "warning"
                                            : "default"
                                        }
                                      >
                                        Signal: {r.recommendation_category}
                                      </Badge>
                                    </div>

                                    <Link
                                      href={`/research?q=${encodeURIComponent(r.symbol)}`}
                                      className="inline-flex items-center gap-1.5 text-xs font-medium text-teal-700 hover:text-teal-800 dark:text-teal-400 dark:hover:underline"
                                    >
                                      <span>View in Stock Research</span>
                                      <ExternalLink className="h-3 w-3" />
                                    </Link>
                                  </div>

                                  {/* Metric Grid with Tooltips */}
                                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                                    <div className="rounded-lg bg-white dark:bg-slate-950 p-3 border border-slate-200 dark:border-slate-800">
                                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                                        <span>Short Mom (20s)</span>
                                        <MetricHelp metricId="momentum_20s" />
                                      </div>
                                      <div className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                                        {formatPct(r.short_return_pct)}
                                      </div>
                                    </div>

                                    <div className="rounded-lg bg-white dark:bg-slate-950 p-3 border border-slate-200 dark:border-slate-800">
                                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                                        <span>Long Mom (60s)</span>
                                        <MetricHelp metricId="momentum_60s" />
                                      </div>
                                      <div className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                                        {formatPct(r.long_return_pct)}
                                      </div>
                                    </div>

                                    <div className="rounded-lg bg-white dark:bg-slate-950 p-3 border border-slate-200 dark:border-slate-800">
                                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                                        <span>Volatility (20s)</span>
                                        <MetricHelp metricId="volatility_20s" />
                                      </div>
                                      <div className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                                        {formatPct(r.volatility_pct, false)}
                                      </div>
                                    </div>

                                    <div className="rounded-lg bg-white dark:bg-slate-950 p-3 border border-slate-200 dark:border-slate-800">
                                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                                        <span>Trade Frequency</span>
                                        <MetricHelp metricId="trade_frequency_20s" />
                                      </div>
                                      <div className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                                        {formatPct(r.trade_frequency_pct, false)}
                                      </div>
                                    </div>

                                    <div className="rounded-lg bg-white dark:bg-slate-950 p-3 border border-slate-200 dark:border-slate-800">
                                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                                        <span>Median Turnover</span>
                                        <MetricHelp metricId="median_turnover_20s" />
                                      </div>
                                      <div className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                                        {formatTnd(r.median_turnover_tnd)}
                                      </div>
                                    </div>

                                    <div className="rounded-lg bg-white dark:bg-slate-950 p-3 border border-slate-200 dark:border-slate-800">
                                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                                        <span>Research Score</span>
                                        <MetricHelp metricId="composite_score" />
                                      </div>
                                      <div className="text-sm font-mono font-bold text-teal-700 dark:text-teal-400">
                                        {r.composite_score !== null ? r.composite_score.toFixed(3) : "N/A"}
                                      </div>
                                    </div>
                                  </div>

                                  {/* Eligibility Diagnostics & Explanations */}
                                  <div className="space-y-2">
                                    <h5 className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                      Eligibility Status & Diagnostic Explanations
                                    </h5>

                                    {r.eligible && (!r.blocked_reasons || r.blocked_reasons.length === 0) ? (
                                      <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 p-3 flex items-start gap-2 text-xs text-emerald-900 dark:text-emerald-300">
                                        <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                                        <div>
                                          <span className="font-semibold block">Fully Eligible for Strategy Selection:</span>
                                          Meets continuous trading segment requirements, has over 61 verified sessions, and exceeds liquidity thresholds.
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="space-y-2">
                                        {/* Structured Explanations from Codex API */}
                                        {r.eligibility_explanations && r.eligibility_explanations.length > 0 ? (
                                          r.eligibility_explanations.map((expl, idx) => (
                                            <div
                                              key={idx}
                                              className={`rounded-lg p-3 border text-xs flex items-start gap-3 ${
                                                expl.severity === "blocker"
                                                  ? "bg-rose-50/80 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800/60 text-rose-950 dark:text-rose-200"
                                                  : "bg-amber-50/80 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60 text-amber-950 dark:text-amber-200"
                                              }`}
                                            >
                                              <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
                                              <div className="space-y-1">
                                                <div className="font-semibold">{expl.title}</div>
                                                <p className="leading-relaxed opacity-90">{expl.plain_explanation}</p>
                                                <p className="text-[11px] font-medium opacity-80">
                                                  Recommended Action: {expl.recommended_action}
                                                </p>
                                              </div>
                                            </div>
                                          ))
                                        ) : (
                                          /* Fallback for raw warning strings */
                                          <div className="rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 p-3 text-xs text-amber-900 dark:text-amber-300 space-y-1">
                                            {r.blocked_reasons.map((b, idx) => (
                                              <div key={idx} className="flex items-start gap-2">
                                                <ShieldAlert className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                                                <span>{b}</span>
                                              </div>
                                            ))}
                                            {r.eligibility_warnings.map((w, idx) => (
                                              <div key={idx} className="flex items-start gap-2 text-slate-600 dark:text-slate-400">
                                                <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                                                <span>{w}</span>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 text-xs text-slate-500 dark:text-slate-400">
                <div>
                  Showing{" "}
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    {filteredRows.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}
                  </span>{" "}
                  to{" "}
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    {Math.min(currentPage * pageSize, filteredRows.length)}
                  </span>{" "}
                  of{" "}
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    {filteredRows.length}
                  </span>{" "}
                  equities
                </div>

                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage <= 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    <span>Previous</span>
                  </Button>

                  <div className="px-3 font-medium">
                    Page {currentPage} of {totalPages}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage >= totalPages}
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    aria-label="Next page"
                  >
                    <span>Next</span>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
