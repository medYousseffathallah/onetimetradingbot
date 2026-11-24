"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, AlertTriangle } from "lucide-react";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type DiscoveryResponse,
  type Horizon,
  type StockState,
  type Universe,
} from "@/lib/v2-api";
import { formatProvenanceNumber, HORIZON_LABELS } from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { StockStateBadge } from "@/components/StateBadges";
import { ApiErrorBanner, EmptyStatePanel, LoadingSkeleton } from "@/components/StateFeedback";

const HORIZONS: Horizon[] = ["1_2", "3_5", "5_10", "10_20", "20_60"];
const STATES: Array<"ALL" | StockState> = [
  "ALL",
  "HELD_POSITION_REVIEW",
  "RESEARCH_CANDIDATE",
  "WATCH",
  "NO_CURRENT_EDGE",
  "INSUFFICIENT_EVIDENCE",
  "RESTRICTED",
];

function horizonMetricKey(horizon: Horizon): string {
  if (horizon === "1_2" || horizon === "3_5") return "ret_5s";
  if (horizon === "20_60") return "ret_60s";
  return "ret_20s";
}

export default function OpportunityDiscoveryPage() {
  const { mode, withModeHref } = useMode();
  const [universe, setUniverse] = useState<Universe>("TUNIS_BOURSE_CHALLENGE");
  const [horizon, setHorizon] = useState<Horizon>("5_10");
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<"ALL" | StockState>("ALL");
  const [data, setData] = useState<DiscoveryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await v2Api.getDiscovery(mode, universe, horizon);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load discovery candidates");
    } finally {
      setLoading(false);
    }
  }, [mode, universe, horizon]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    return data.candidates.filter((c) => {
      if (stateFilter !== "ALL" && c.assessment.state !== stateFilter) return false;
      if (!q) return true;
      const ins = c.assessment.instrument;
      return (
        ins.symbol.toLowerCase().includes(q) ||
        ins.instrument_id.toLowerCase().includes(q) ||
        ins.isin.toLowerCase().includes(q) ||
        (ins.sector ?? "").toLowerCase().includes(q)
      );
    });
  }, [data, search, stateFilter]);

  const metricKey = horizonMetricKey(horizon);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
            GET /api/v2/discovery?mode={mode}&amp;universe={universe}&amp;horizon={horizon}
          </div>
          <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
            Opportunity Discovery
          </h1>
          <p className="mt-0.5 text-[13.5px] text-[#334155]">
            Track-isolated equity screener separating research attention from orderability and
            liquidity capacity.
          </p>
        </div>
        <div className="inline-flex rounded-md border border-[#E2E8F0] bg-[#F1F5F9] p-1">
          <button
            type="button"
            onClick={() => setUniverse("TUNIS_BOURSE_CHALLENGE")}
            className={`min-h-[34px] rounded px-3 py-1 text-[12px] font-semibold transition-colors ${
              universe === "TUNIS_BOURSE_CHALLENGE"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#475569] hover:text-[#0F172A]"
            }`}
          >
            Challenge Universe
          </button>
          <button
            type="button"
            onClick={() => setUniverse("FULL_BVMT_RESEARCH")}
            className={`min-h-[34px] rounded px-3 py-1 text-[12px] font-semibold transition-colors ${
              universe === "FULL_BVMT_RESEARCH"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#475569] hover:text-[#0F172A]"
            }`}
          >
            Full BVMT Research
          </button>
        </div>
      </div>

      {universe === "FULL_BVMT_RESEARCH" ? (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-lg border border-[#FECACA] bg-[#FEF2F2] p-3.5 text-[12.5px] text-[#991B1B]"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <strong>Full BVMT Research Track (Non-Challenge Included):</strong> Securities marked{" "}
            <code className="rounded bg-[#FEE2E2] px-1 py-0.5 font-semibold">RESTRICTED</code>{" "}
            (such as non-Challenge issuers like MNP or SCN) are NOT orderable in the virtual
            competition.
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Horizon">
            {HORIZONS.map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => setHorizon(h)}
                className={`min-h-[36px] rounded-md border px-2.5 py-1 text-[12px] font-medium ${
                  horizon === h
                    ? "border-[#99F6E4] bg-[#F0FDFA] font-semibold text-[#0F766E]"
                    : "border-[#E2E8F0] bg-white text-[#334155] hover:bg-[#F1F5F9]"
                }`}
              >
                {HORIZON_LABELS[h]}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[12px] text-[#64748B]">
            <span>Showing</span>
            <strong className="mono-num text-[#0F172A]">{filtered.length}</strong>
            <span>of {data?.candidates.length ?? 0} equities</span>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-12">
          <div className="relative sm:col-span-7">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748B]" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by symbol, ISIN, ID, or sector..."
              aria-label="Filter discovery equities"
              className="min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white pl-9 pr-3 text-[13px] text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#0F766E] focus:outline-none"
            />
          </div>
          <div className="sm:col-span-5">
            <select
              aria-label="Filter by assessment state"
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value as "ALL" | StockState)}
              className="min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
            >
              {STATES.map((st) => (
                <option key={st} value={st}>
                  {st === "ALL" ? "All Assessment States" : st}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : error ? (
        <ApiErrorBanner error={error} onRetry={loadData} />
      ) : filtered.length === 0 ? (
        <EmptyStatePanel
          title="0 equities match current discovery filters"
          description="Try clearing the search text or switching the assessment state filter."
          actionLabel="Reset Filters"
          onAction={() => {
            setSearch("");
            setStateFilter("ALL");
          }}
        />
      ) : (
        <section className="overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
          {/* Desktop Table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F1F5F9] text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#64748B]">
                  <th className="px-3.5 py-2.5">Rank</th>
                  <th className="px-3.5 py-2.5">Security / ISIN</th>
                  <th className="px-3.5 py-2.5 text-right">EOD Close</th>
                  <th className="px-3.5 py-2.5 text-right">Window Ret</th>
                  <th className="px-3.5 py-2.5 text-right">20s Med Turn</th>
                  <th className="px-3.5 py-2.5 text-right">10% ADV Sh</th>
                  <th className="px-3.5 py-2.5">Missing</th>
                  <th className="px-3.5 py-2.5">Assessment State</th>
                  <th className="px-3.5 py-2.5">Primary Blocker</th>
                  <th className="px-3.5 py-2.5 text-right">Workspace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {filtered.map((c) => {
                  const a = c.assessment;
                  const retPv = a.technical_state[metricKey];
                  const primaryBlocker =
                    a.execution_feasibility.blockers[0] ?? a.horizon_support_status;

                  return (
                    <tr key={a.instrument.instrument_id} className="hover:bg-[#F8FAFC]">
                      <td className="mono-num px-3.5 py-3 text-[#64748B]">
                        #{c.research_priority_rank ?? "—"}
                      </td>
                      <td className="px-3.5 py-3">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-semibold text-[#0F172A]">
                            {a.instrument.symbol}
                          </span>
                          {c.challenge_eligible ? (
                            <span className="rounded border border-[#99F6E4] bg-[#F0FDFA] px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[#0F766E]">
                              Challenge
                            </span>
                          ) : (
                            <span className="rounded border border-[#FECACA] bg-[#FEF2F2] px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[#991B1B]">
                              Restricted
                            </span>
                          )}
                        </div>
                        <div className="font-mono text-[11.5px] text-[#64748B]">
                          {a.instrument.isin} &middot; {a.instrument.sector ?? "—"}
                        </div>
                      </td>
                      <td className="mono-num px-3.5 py-3 text-right text-[#0F172A]">
                        {formatProvenanceNumber(a.historical_eod_close_tnd, { withUnit: false })}
                      </td>
                      <td className="mono-num px-3.5 py-3 text-right font-semibold text-[#0F172A]">
                        {formatProvenanceNumber(retPv, { signed: true })}
                      </td>
                      <td className="mono-num px-3.5 py-3 text-right text-[#334155]">
                        {formatProvenanceNumber(c.adv_20s_tnd, { withUnit: false })}
                      </td>
                      <td className="mono-num px-3.5 py-3 text-right text-[#334155]">
                        {formatProvenanceNumber(c.ten_pct_adv_shares, { withUnit: false })}
                      </td>
                      <td className="mono-num px-3.5 py-3 text-[#64748B]">
                        {a.missing_evidence.length} missing
                      </td>
                      <td className="px-3.5 py-3">
                        <StockStateBadge state={a.state} />
                      </td>
                      <td className="px-3.5 py-3 text-[12px] text-[#64748B] break-words">
                        {primaryBlocker}
                      </td>
                      <td className="px-3.5 py-3 text-right">
                        <Link
                          href={withModeHref(
                            `/stocks/${encodeURIComponent(a.instrument.instrument_id)}`,
                          )}
                          className="font-medium text-[#0F766E] hover:underline whitespace-nowrap"
                        >
                          Open &rarr;
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Stacked Cards */}
          <div className="divide-y divide-[#E2E8F0] md:hidden">
            {filtered.map((c) => {
              const a = c.assessment;
              const retPv = a.technical_state[metricKey];
              const primaryBlocker =
                a.execution_feasibility.blockers[0] ?? a.horizon_support_status;

              return (
                <div key={a.instrument.instrument_id} className="space-y-2 p-4">
                  <div className="flex items-start justify-between gap-2 border-b border-[#E2E8F0] pb-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="mono-num text-[12px] text-[#64748B]">
                          #{c.research_priority_rank ?? "—"}
                        </span>
                        <span className="font-semibold text-[#0F172A]">
                          {a.instrument.symbol}
                        </span>
                        {!c.challenge_eligible ? (
                          <ProvenanceBadge status="UNVERIFIED" label="RESTRICTED" />
                        ) : null}
                      </div>
                      <div className="font-mono text-[11.5px] text-[#64748B]">
                        {a.instrument.isin}
                      </div>
                    </div>
                    <StockStateBadge state={a.state} />
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12.5px]">
                    <div className="text-[#64748B]">EOD Close</div>
                    <div className="mono-num text-right text-[#0F172A]">
                      {formatProvenanceNumber(a.historical_eod_close_tnd)}
                    </div>
                    <div className="text-[#64748B]">Window Return</div>
                    <div className="mono-num text-right font-semibold text-[#0F172A]">
                      {formatProvenanceNumber(retPv, { signed: true })}
                    </div>
                    <div className="text-[#64748B]">20s Med Turnover</div>
                    <div className="mono-num text-right text-[#334155]">
                      {formatProvenanceNumber(c.adv_20s_tnd)}
                    </div>
                    <div className="text-[#64748B]">10% ADV Shares</div>
                    <div className="mono-num text-right text-[#334155]">
                      {formatProvenanceNumber(c.ten_pct_adv_shares)}
                    </div>
                    <div className="text-[#64748B]">Blocker</div>
                    <div className="text-right text-[12px] text-[#64748B] break-words">
                      {primaryBlocker}
                    </div>
                  </div>
                  <div className="pt-1 text-right">
                    <Link
                      href={withModeHref(
                        `/stocks/${encodeURIComponent(a.instrument.instrument_id)}`,
                      )}
                      className="text-[12.5px] font-medium text-[#0F766E] hover:underline"
                    >
                      Open Stock Research &rarr;
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <p className="border-t border-[#E2E8F0] pt-3 text-[12px] text-[#64748B]">
        Equity-only universe enforcement: non-equity instruments (bonds, debt, rights) are
        excluded prior to ranking. Horizon support:{" "}
        <code className="font-mono">
          {filtered[0]?.assessment.horizon_support_status ?? "EXPLORATORY"}
        </code>
        .
      </p>
    </div>
  );
}
