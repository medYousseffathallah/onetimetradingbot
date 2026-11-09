"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  Search,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle2,
  SlidersHorizontal,
  Info,
  ShieldAlert,
  X,
  RotateCcw,
  Clock,
  Layers,
  Scale,
} from "lucide-react";
import {
  api,
  MarketDataStatusResponse,
  StockRankingsResponse,
  StockRankingItem,
} from "@/lib/api";
import { formatTnd, formatPct } from "@/lib/utils";
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

type FilterTab =
  | "ALL"
  | "CHALLENGE_UNIVERSE"
  | "STRATEGY_ELIGIBLE"
  | "RESEARCH_READY"
  | "PARTIAL_DATA"
  | "ILLIQUID"
  | "RESTRICTED"
  | "MISSING_DATA";

export default function MarketExplorerPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [mktStatus, setMktStatus] = useState<MarketDataStatusResponse | null>(null);
  const [rankings, setRankings] = useState<StockRankingsResponse | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("CHALLENGE_UNIVERSE");
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
    const challengeUniverse = allRankings.filter((r) => r.in_challenge_universe).length;
    const eligible = allRankings.filter((r) => r.eligible).length;
    const researchReady = allRankings.filter(
      (r) =>
        r.research_coverage_status === "FULL_COVERAGE" ||
        r.signal_availability === "FULL_SIGNALS" ||
        r.signal_availability === "RESEARCH_ONLY_SIGNALS"
    ).length;
    const partialData = allRankings.filter(
      (r) =>
        r.research_coverage_status === "PARTIAL_HISTORY" ||
        r.data_quality_status === "MISSING_SESSIONS"
    ).length;
    const illiquid = allRankings.filter(
      (r) =>
        r.data_quality_status === "SPARSE_VOLUME" ||
        r.data_quality_status === "STALE_QUOTES" ||
        r.data_quality_status === "UNTRADED_ANCHOR" ||
        (r.quote_age_sessions !== undefined &&
          r.quote_age_sessions !== null &&
          r.quote_age_sessions > 3)
    ).length;
    const restricted = allRankings.filter(
      (r) =>
        r.competition_eligibility === "MARKET_RESTRICTED" ||
        r.data_quality_status === "RESTRICTED_SEGMENT"
    ).length;
    const missing = allRankings.filter(
      (r) =>
        r.research_coverage_status === "MISSING_DATA" ||
        r.research_coverage_status === "UNTRADED_HISTORY" ||
        !r.close_tnd
    ).length;

    return {
      ALL: allRankings.length,
      CHALLENGE_UNIVERSE: challengeUniverse,
      STRATEGY_ELIGIBLE: eligible,
      RESEARCH_READY: researchReady,
      PARTIAL_DATA: partialData,
      ILLIQUID: illiquid,
      RESTRICTED: restricted,
      MISSING_DATA: missing,
    };
  }, [allRankings]);

  // Filtered rows
  const filteredRows = useMemo(() => {
    return allRankings.filter((r) => {
      // Tab filter
      if (activeTab === "CHALLENGE_UNIVERSE" && !r.in_challenge_universe) return false;
      if (activeTab === "STRATEGY_ELIGIBLE" && !r.eligible) return false;
      if (activeTab === "RESEARCH_READY") {
        const isReady =
          r.research_coverage_status === "FULL_COVERAGE" ||
          r.signal_availability === "FULL_SIGNALS" ||
          r.signal_availability === "RESEARCH_ONLY_SIGNALS";
        if (!isReady) return false;
      }
      if (activeTab === "PARTIAL_DATA") {
        const isPartial =
          r.research_coverage_status === "PARTIAL_HISTORY" ||
          r.data_quality_status === "MISSING_SESSIONS";
        if (!isPartial) return false;
      }
      if (activeTab === "ILLIQUID") {
        const isIlliquid =
          r.data_quality_status === "SPARSE_VOLUME" ||
          r.data_quality_status === "STALE_QUOTES" ||
          r.data_quality_status === "UNTRADED_ANCHOR" ||
          (r.quote_age_sessions !== undefined &&
            r.quote_age_sessions !== null &&
            r.quote_age_sessions > 3);
        if (!isIlliquid) return false;
      }
      if (activeTab === "RESTRICTED") {
        const isRestricted =
          r.competition_eligibility === "MARKET_RESTRICTED" ||
          r.data_quality_status === "RESTRICTED_SEGMENT";
        if (!isRestricted) return false;
      }
      if (activeTab === "MISSING_DATA") {
        const isMissing =
          r.research_coverage_status === "MISSING_DATA" ||
          r.research_coverage_status === "UNTRADED_HISTORY" ||
          !r.close_tnd;
        if (!isMissing) return false;
      }

      // Search filter
      if (search.trim()) {
        const term = search.toLowerCase();
        const matchSymbol = r.symbol.toLowerCase().includes(term);
        const matchId = r.instrument_id.toLowerCase().includes(term);
        const matchIsin = r.isin ? r.isin.toLowerCase().includes(term) : false;
        if (!matchSymbol && !matchId && !matchIsin) return false;
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
            Market Explorer & Quantitative Research
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Analyze market-wide Tunisian equity coverage, sparse-data analytics, and conservative
            trading eligibility for the Tunis Bourse Challenge.
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
            Separation of Quantitative Research from Strategy Eligibility:
          </span>
          All 76 listed BVMT equities possess verified market quotations or last-traded benchmarks.
          A stock excluded from the active momentum strategy (e.g. due to fixing quotation group or
          61-session anchor gaps) remains 100% researchable. Missing prices are marked as{" "}
          <span className="font-semibold">Unavailable</span>, never zero dinars. Hover or click{" "}
          <span className="inline-flex items-center text-teal-700 dark:text-teal-300 font-medium">
            (?)
          </span>{" "}
          for exact formulas and microstructure caveats.
        </div>
      </div>

      {/* Market Overview Cards */}
      {mkt && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Total Listed Equities</CardDescription>
                <MetricHelp metricId="eligibility" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
                {allRankings.length || mkt.unique_instruments} Equities
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              <span className="font-medium text-teal-600 dark:text-teal-400">
                {tabCounts.STRATEGY_ELIGIBLE} Strategy Eligible
              </span>{" "}
              • {tabCounts.ALL - tabCounts.STRATEGY_ELIGIBLE} Research Only
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Research Ready Coverage</CardDescription>
                <MetricHelp metricId="data_freshness" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-teal-700 dark:text-teal-400">
                {tabCounts.RESEARCH_READY} Stocks
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              Verified historical quotations & valid returns
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Sparse / Thinly Traded</CardDescription>
                <MetricHelp metricId="liquidity" />
              </div>
              <CardTitle className="text-xl font-mono font-bold text-amber-600 dark:text-amber-400">
                {tabCounts.ILLIQUID} Stocks
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-500 dark:text-slate-400">
              Quote age &gt; 3s or low trading frequency
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription>Verified Market Archive</CardDescription>
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
        </div>
      )}

      {/* Main Table Card */}
      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <SlidersHorizontal className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                <span>Securities Master & Research Indicators</span>
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
                  placeholder="Search company, ticker or ISIN..."
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
              onClick={() => setActiveTab("CHALLENGE_UNIVERSE")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeTab === "CHALLENGE_UNIVERSE"
                  ? "bg-teal-700 text-white shadow-xs"
                  : "bg-teal-50 text-teal-800 hover:bg-teal-100 dark:bg-teal-950/60 dark:text-teal-300 dark:hover:bg-teal-900/60"
              }`}
            >
              Challenge Universe ({tabCounts.CHALLENGE_UNIVERSE})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("STRATEGY_ELIGIBLE")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "STRATEGY_ELIGIBLE"
                  ? "bg-teal-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Strategy Eligible ({tabCounts.STRATEGY_ELIGIBLE})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("RESEARCH_READY")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "RESEARCH_READY"
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Research Ready ({tabCounts.RESEARCH_READY})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("PARTIAL_DATA")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "PARTIAL_DATA"
                  ? "bg-sky-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Partial Data ({tabCounts.PARTIAL_DATA})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("ILLIQUID")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "ILLIQUID"
                  ? "bg-amber-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Illiquid / Stale ({tabCounts.ILLIQUID})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("RESTRICTED")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "RESTRICTED"
                  ? "bg-purple-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Restricted ({tabCounts.RESTRICTED})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("MISSING_DATA")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === "MISSING_DATA"
                  ? "bg-rose-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              Missing Data ({tabCounts.MISSING_DATA})
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
                          <span>Data Quality</span>
                          <MetricHelp metricId="source_provenance" />
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
                              <span>Observed Ret.</span>
                              <MetricHelp metricId="momentum_20s" />
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
                      const mom20Num = r.short_return_pct ? parseFloat(r.short_return_pct) : null;
                      const obsRetNum = r.observed_trade_return_pct
                        ? parseFloat(r.observed_trade_return_pct)
                        : null;
                      const quoteAge = r.quote_age_sessions ?? 0;

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
                                  <div className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors flex items-center gap-1.5">
                                    <span>{r.symbol}</span>
                                    {r.in_challenge_universe ? (
                                      <span className="text-[10px] font-medium bg-teal-100 text-teal-800 dark:bg-teal-950/60 dark:text-teal-300 px-1.5 py-0.2 rounded">
                                        Challenge (42)
                                      </span>
                                    ) : (
                                      <span className="text-[10px] font-medium bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 px-1.5 py-0.2 rounded">
                                        Non-Challenge
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono flex items-center gap-1.5">
                                    <span>{r.instrument_id}</span>
                                    {r.isin && <span>• {r.isin}</span>}
                                    {r.market_segment && (
                                      <span className="text-[10px] uppercase text-slate-400 dark:text-slate-500">
                                        ({r.market_segment.replace("_", " ")})
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Latest Price */}
                            <td className="py-3 px-4 text-right">
                              <div className="font-mono font-medium text-slate-900 dark:text-slate-100">
                                {formatTnd(r.close_tnd)}
                              </div>
                              {quoteAge > 0 && r.last_traded_date && (
                                <div className="text-[10px] text-amber-600 dark:text-amber-400 font-mono">
                                  Traded {r.last_traded_date} ({quoteAge}s ago)
                                </div>
                              )}
                            </td>

                            {/* 20-Day Trend */}
                            <td className="py-3 px-4 text-right">
                              {mom20Num !== null ? (
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
                              ) : obsRetNum !== null ? (
                                <div className="inline-flex flex-col items-end">
                                  <span className="font-mono text-xs text-slate-700 dark:text-slate-300">
                                    {formatPct(r.observed_trade_return_pct)}
                                  </span>
                                  <span className="text-[10px] text-slate-400 font-mono">
                                    (Observed Trade)
                                  </span>
                                </div>
                              ) : (
                                <span className="text-slate-400 font-mono text-xs">N/A</span>
                              )}
                            </td>

                            {/* Data Quality Status */}
                            <td className="py-3 px-4 text-center">
                              {r.data_quality_status === "VERIFIED_EOD" ? (
                                <Badge variant="success" className="text-[11px] py-0 px-2 font-normal">
                                  Verified EOD
                                </Badge>
                              ) : r.data_quality_status === "RESTRICTED_SEGMENT" ? (
                                <Badge variant="warning" className="text-[11px] py-0 px-2 font-normal">
                                  Restricted Segment
                                </Badge>
                              ) : r.data_quality_status === "MISSING_SESSIONS" ? (
                                <Badge variant="info" className="text-[11px] py-0 px-2 font-normal">
                                  Partial Sessions
                                </Badge>
                              ) : r.data_quality_status === "STALE_QUOTES" ? (
                                <Badge variant="outline" className="text-[11px] py-0 px-2 font-normal text-amber-600 border-amber-300">
                                  Stale Quotes
                                </Badge>
                              ) : r.data_quality_status === "UNTRADED_ANCHOR" ? (
                                <Badge variant="outline" className="text-[11px] py-0 px-2 font-normal text-sky-600 border-sky-300">
                                  Untraded Anchor
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-[11px] py-0 px-2 font-normal text-slate-400">
                                  {r.data_quality_status?.replace("_", " ") || "Review"}
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
                                  {formatPct(r.observed_trade_return_pct)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono text-xs text-slate-600 dark:text-slate-400">
                                  {formatPct(r.volatility_pct, false)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                  {formatTnd(r.median_turnover_tnd)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono font-semibold text-xs text-teal-700 dark:text-teal-300">
                                  {r.composite_score !== null
                                    ? r.composite_score.toFixed(3)
                                    : r.continuous_research_score !== null &&
                                      r.continuous_research_score !== undefined
                                    ? `${r.continuous_research_score.toFixed(3)}*`
                                    : "—"}
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
                                  Research Only
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
                                <div className="space-y-5">
                                  {/* Top Details Header */}
                                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                                    <div className="flex items-center gap-3">
                                      <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">
                                        {r.symbol} ({r.instrument_id})
                                      </h4>
                                      <Badge
                                        variant={
                                          r.eligible
                                            ? "success"
                                            : "default"
                                        }
                                      >
                                        Strategy: {r.eligible ? "ELIGIBLE" : "RESEARCH ONLY (NO TRADE)"}
                                      </Badge>
                                      {r.market_segment && (
                                        <Badge variant="outline" className="text-xs font-mono">
                                          {r.market_segment}
                                        </Badge>
                                      )}
                                    </div>

                                    <Link
                                      href={`/research?q=${encodeURIComponent(r.symbol)}`}
                                      className="inline-flex items-center gap-1.5 text-xs font-medium text-teal-700 hover:text-teal-800 dark:text-teal-400 dark:hover:underline"
                                    >
                                      <span>View in Stock Research</span>
                                      <ExternalLink className="h-3 w-3" />
                                    </Link>
                                  </div>

                                  {/* Section 1: Sparse Data Analytics & Microstructure */}
                                  <div>
                                    <h5 className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
                                      <Layers className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
                                      <span>Market Microstructure & Sparse-Data Indicators</span>
                                    </h5>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5">Last Traded Price</div>
                                        <div className="text-xs font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {formatTnd(r.last_traded_price_tnd ?? r.close_tnd)}
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">
                                          {r.last_traded_date ?? "Recent"}
                                        </div>
                                      </div>

                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5 flex items-center gap-1">
                                          <span>Quote Age</span>
                                          <Clock className="h-2.5 w-2.5" />
                                        </div>
                                        <div className="text-xs font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {quoteAge} session(s)
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">
                                          {quoteAge === 0 ? "Current" : "Historical"}
                                        </div>
                                      </div>

                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5">Observed Return</div>
                                        <div className="text-xs font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {formatPct(r.observed_trade_return_pct)}
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">
                                          {r.observed_trade_interval_sessions ?? "—"} sessions interval
                                        </div>
                                      </div>

                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5">Observation Coverage</div>
                                        <div className="text-xs font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {formatPct(r.observation_coverage_ratio, false)}
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Traded / Total</div>
                                      </div>

                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5">Trade Frequency (20s)</div>
                                        <div className="text-xs font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {formatPct(r.trade_frequency_pct, false)}
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Min 60% Hurdle</div>
                                      </div>

                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5">Median Turnover (20s)</div>
                                        <div className="text-xs font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {formatTnd(r.median_turnover_tnd)}
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Min 1,000 TND</div>
                                      </div>

                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5">Research Confidence</div>
                                        <div className="text-xs font-mono font-bold text-teal-700 dark:text-teal-400">
                                          {r.research_confidence_score !== null &&
                                          r.research_confidence_score !== undefined
                                            ? `${(r.research_confidence_score * 100).toFixed(0)}%`
                                            : "—"}
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Data Completeness</div>
                                      </div>

                                      <div className="rounded-lg bg-white dark:bg-slate-950 p-2.5 border border-slate-200 dark:border-slate-800">
                                        <div className="text-[10px] text-slate-500 mb-0.5">Continuous Score</div>
                                        <div className="text-xs font-mono font-bold text-teal-700 dark:text-teal-400">
                                          {r.continuous_research_score !== null &&
                                          r.continuous_research_score !== undefined
                                            ? r.continuous_research_score.toFixed(3)
                                            : r.composite_score !== null
                                            ? r.composite_score.toFixed(3)
                                            : "N/A"}
                                        </div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Liquidity-Damped</div>
                                      </div>
                                    </div>
                                  </div>

                                  {/* Section 2: Conservative Order Capacity (Zero Intraday Lookahead) */}
                                  <div className="rounded-lg bg-teal-50/40 dark:bg-teal-950/20 border border-teal-200/60 dark:border-teal-900/40 p-3.5 space-y-2">
                                    <div className="flex items-center justify-between">
                                      <h5 className="text-xs font-semibold text-teal-950 dark:text-teal-200 flex items-center gap-1.5">
                                        <Scale className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
                                        <span>Conservative Hypothetical Order Sizing (Zero Volume Lookahead)</span>
                                      </h5>
                                      <Badge variant="outline" className="text-[11px] font-mono">
                                        Feasibility: {r.execution_feasibility || "FEASIBLE"}
                                      </Badge>
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                                      <div>
                                        <span className="text-slate-500 dark:text-slate-400 block text-[11px]">
                                          Trailing Turnover Capacity (10% of 20s Med):
                                        </span>
                                        <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {formatTnd(r.conservative_order_capacity_tnd)}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-slate-500 dark:text-slate-400 block text-[11px]">
                                          Max Hypothetical Order Shares:
                                        </span>
                                        <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                                          {r.hypothetical_order_shares?.toLocaleString() ?? 0} shares
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-slate-500 dark:text-slate-400 block text-[11px]">
                                          Point-in-Time Assurance:
                                        </span>
                                        <span className="text-teal-800 dark:text-teal-300 text-[11px]">
                                          Calculated strictly using past trading history. Zero next-day volume lookahead.
                                        </span>
                                      </div>
                                    </div>
                                  </div>

                                  {/* Section 3: Eligibility Diagnostics & Deduplicated Explanations */}
                                  <div className="space-y-2">
                                    <h5 className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                      Strategy Eligibility Status & Operator Guidance
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
                                                  Recommended Operator Action: {expl.recommended_action}
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
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 text-xs text-slate-500 dark:text-slate-400">
                <div>
                  Showing {(currentPage - 1) * pageSize + 1} to{" "}
                  {Math.min(currentPage * pageSize, filteredRows.length)} of {filteredRows.length}{" "}
                  stocks
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage <= 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="font-mono text-slate-700 dark:text-slate-300 px-2">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage >= totalPages}
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  >
                    Next
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
