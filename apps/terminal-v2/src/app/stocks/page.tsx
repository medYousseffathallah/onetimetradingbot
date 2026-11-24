"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { useMode } from "@/components/mode-context";
import { v2Api, type OpportunityCandidate } from "@/lib/v2-api";
import { formatProvenanceNumber } from "@/lib/format";
import { StockStateBadge } from "@/components/StateBadges";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

const QUICK_FEATURED = ["EURO-CYCLES", "DELICE_HOLDING", "AMEN_BANK", "MPBS", "STA"];

export default function StocksIndexPage() {
  const { mode, withModeHref } = useMode();
  const [candidates, setCandidates] = useState<OpportunityCandidate[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await v2Api.getDiscovery(mode, "FULL_BVMT_RESEARCH", "5_10");
      setCandidates(res.candidates);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load equity directory");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter((c) => {
      const ins = c.assessment.instrument;
      return (
        ins.symbol.toLowerCase().includes(q) ||
        ins.instrument_id.toLowerCase().includes(q) ||
        ins.isin.toLowerCase().includes(q)
      );
    });
  }, [candidates, search]);

  if (loading) return <LoadingSkeleton rows={5} />;
  if (error) return <ApiErrorBanner error={error} onRetry={loadData} />;

  return (
    <div className="space-y-5">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
          Stock Research Directory
        </div>
        <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
          Stock Research Workspace
        </h1>
        <p className="mt-0.5 text-[13.5px] text-[#334155]">
          Select an equity issuer to inspect L1&ndash;L10 evidence, EOD price/volume charts, and
          the 10-field provenance register.
        </p>
      </div>

      <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
        <div className="text-[12px] font-semibold uppercase tracking-wide text-[#64748B]">
          Quick Access (Held &amp; Challenge Issuers)
        </div>
        <div className="flex flex-wrap gap-2">
          {QUICK_FEATURED.map((id) => (
            <Link
              key={id}
              href={withModeHref(`/stocks/${encodeURIComponent(id)}`)}
              className="inline-flex min-h-[36px] items-center rounded-md border border-[#99F6E4] bg-[#F0FDFA] px-3 py-1.5 text-[12.5px] font-semibold text-[#0F766E] hover:bg-[#CCFBF1]"
            >
              {id} &rarr;
            </Link>
          ))}
        </div>

        <div className="relative pt-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748B]" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search all canonical BVMT equities by symbol or ISIN..."
            aria-label="Search equities"
            className="min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white pl-9 pr-3 text-[13px] text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#0F766E] focus:outline-none"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((c) => {
          const ins = c.assessment.instrument;
          return (
            <Link
              key={ins.instrument_id}
              href={withModeHref(`/stocks/${encodeURIComponent(ins.instrument_id)}`)}
              className="flex min-w-0 flex-col justify-between rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 hover:border-[#0F766E]"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-semibold text-[#0F172A]">{ins.symbol}</div>
                  <div className="font-mono text-[11.5px] text-[#64748B]">{ins.isin}</div>
                </div>
                <StockStateBadge state={c.assessment.state} />
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-[#E2E8F0] pt-2.5 text-[12.5px]">
                <span className="text-[#64748B]">
                  {c.challenge_eligible ? "Challenge" : "Research Only"}
                </span>
                <span className="mono-num font-semibold text-[#0F172A]">
                  {formatProvenanceNumber(c.assessment.historical_eod_close_tnd)}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
