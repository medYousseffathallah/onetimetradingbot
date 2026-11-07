"use client";

import React, { useEffect, useState } from "react";
import {
  Database,
  CheckCircle2,
  AlertTriangle,
  Filter,
  TrendingUp,
} from "lucide-react";
import { api, MarketDataStatusResponse, StockRankingsResponse } from "@/lib/api";
import { formatTnd, formatPct, formatTimestamp } from "@/lib/utils";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { usePortfolioMode } from "@/components/app-shell";

export default function MarketExplorerPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [mktStatus, setMktStatus] = useState<MarketDataStatusResponse | null>(null);
  const [rankings, setRankings] = useState<StockRankingsResponse | null>(null);
  const [onlyEligible, setOnlyEligible] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

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
  const rows = (rankings?.rankings || []).filter((r) => {
    if (onlyEligible && !r.eligible) return false;
    if (
      search.trim() &&
      !r.symbol.toLowerCase().includes(search.toLowerCase()) &&
      !r.instrument_id.toLowerCase().includes(search.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            BVMT Market Explorer & Quantitative Rankings
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Current session momentum, liquidity filters, and eligibility diagnostics across Bourse
            de Tunis equities.
          </p>
        </div>
        {mkt && (
          <Badge variant={mkt.is_synthetic ? "warning" : "success"} className="gap-1.5">
            {mkt.is_synthetic ? (
              <>
                <AlertTriangle className="h-3.5 w-3.5" />
                Synthetic Demo Dataset
              </>
            ) : (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" />
                Official BVMT Quotations ({mkt.latest_session_date})
              </>
            )}
          </Badge>
        )}
      </div>

      {/* Market Provenance & Freshness Cards */}
      {mkt && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Latest Verified Session</CardDescription>
              <CardTitle className="text-xl font-mono font-bold text-sky-300">
                {mkt.latest_session_date || "N/A"}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-[11px] text-slate-400">
              First session: {mkt.first_session_date || "N/A"}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Source Provenance</CardDescription>
              <CardTitle className="text-sm font-semibold text-slate-100">
                {mkt.dataset_label}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-[11px] text-slate-400">
              Sources: {mkt.source_ids.join(", ") || "official-bvmt"}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Archive Coverage</CardDescription>
              <CardTitle className="text-xl font-mono font-bold text-slate-100">
                {mkt.unique_sessions} Sessions
              </CardTitle>
            </CardHeader>
            <CardContent className="text-[11px] text-slate-400">
              {mkt.unique_instruments} equities • {mkt.total_bars.toLocaleString()} daily bars
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Data Freshness</CardDescription>
              <CardTitle className="text-sm font-semibold text-emerald-400">
                {mkt.sessions_behind === 0
                  ? "Current (0 sessions behind)"
                  : `${mkt.sessions_behind} session(s) behind`}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-[11px] text-slate-400">
              Retrieved: {formatTimestamp(mkt.retrieved_at)}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Rankings Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              <span>Current Research Signals (Session {rankings?.session_date || "Latest"})</span>
            </CardTitle>
            <CardDescription className="mt-1">
              Point-in-time momentum and liquidity rankings. Distinct from historical backtest
              simulations.
            </CardDescription>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Filter symbol..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 focus:border-emerald-500 focus:outline-none"
            />
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={onlyEligible}
                onChange={(e) => setOnlyEligible(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-emerald-500"
              />
              <Filter className="h-3.5 w-3.5 text-slate-400" />
              <span>Eligible Only</span>
            </label>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-xs text-slate-400 py-4">Computing stock rankings...</p>
          ) : rows.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-2.5 font-medium">Rank</th>
                    <th className="pb-2.5 font-medium">Stock</th>
                    <th className="pb-2.5 font-medium text-right">Close</th>
                    <th className="pb-2.5 font-medium text-right">Short Mom.</th>
                    <th className="pb-2.5 font-medium text-right">Long Mom.</th>
                    <th className="pb-2.5 font-medium text-right">Volatility</th>
                    <th className="pb-2.5 font-medium text-right">Trade Freq.</th>
                    <th className="pb-2.5 font-medium text-right">Med. Turnover</th>
                    <th className="pb-2.5 font-medium text-right">Score</th>
                    <th className="pb-2.5 font-medium">Signal / Decision</th>
                    <th className="pb-2.5 font-medium">Eligibility & Warnings</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {rows.map((r) => (
                    <tr key={r.instrument_id} className="hover:bg-slate-800/30">
                      <td className="py-2.5 font-mono text-slate-400">#{r.rank}</td>
                      <td className="py-2.5 font-semibold text-slate-100">{r.symbol}</td>
                      <td className="py-2.5 text-right font-mono">{formatTnd(r.close_tnd)}</td>
                      <td className="py-2.5 text-right font-mono">
                        {formatPct(r.short_return_pct)}
                      </td>
                      <td className="py-2.5 text-right font-mono">
                        {formatPct(r.long_return_pct)}
                      </td>
                      <td className="py-2.5 text-right font-mono text-slate-300">
                        {formatPct(r.volatility_pct, false)}
                      </td>
                      <td className="py-2.5 text-right font-mono text-slate-300">
                        {formatPct(r.trade_frequency_pct, false)}
                      </td>
                      <td className="py-2.5 text-right font-mono">
                        {formatTnd(r.median_turnover_tnd)}
                      </td>
                      <td className="py-2.5 text-right font-mono font-semibold text-sky-300">
                        {parseFloat(r.composite_score).toFixed(3)}
                      </td>
                      <td className="py-2.5">
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
                          {r.recommendation_category}
                        </Badge>
                        {r.suggested_shares > 0 && (
                          <span className="ml-1.5 text-[11px] font-mono text-slate-300">
                            ({r.suggested_side} {r.suggested_shares})
                          </span>
                        )}
                      </td>
                      <td className="py-2.5">
                        {r.eligible && r.blocked_reasons.length === 0 ? (
                          <span className="text-emerald-400">Liquidity & Risk Passed</span>
                        ) : (
                          <div className="space-y-0.5 text-[11px] text-amber-300">
                            {r.eligibility_warnings.map((w, idx) => (
                              <div key={idx}>• {w}</div>
                            ))}
                            {r.blocked_reasons.map((b, idx) => (
                              <div key={idx} className="text-rose-300">
                                • {b}
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-4">No stocks match the current filter.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
