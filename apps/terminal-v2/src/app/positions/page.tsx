"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type PortfolioResponse,
  type PositionDecision,
} from "@/lib/v2-api";
import { formatInteger, formatProvenanceNumber } from "@/lib/format";
import { ExecutionGateBadge, MonitoringBadge } from "@/components/StateBadges";
import { ConflictBanner } from "@/components/ConflictBanner";
import { ApiErrorBanner, EmptyStatePanel, LoadingSkeleton } from "@/components/StateFeedback";

export default function PositionsIndexPage() {
  const { mode, withModeHref } = useMode();
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [decisions, setDecisions] = useState<Record<string, PositionDecision>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pf = await v2Api.getPortfolio(mode);
      setPortfolio(pf);
      const ids = pf.current.holdings.map((h) => h.instrument_id);
      const settled = await Promise.allSettled(ids.map((id) => v2Api.getPosition(id, mode)));
      const next: Record<string, PositionDecision> = {};
      settled.forEach((res, idx) => {
        if (res.status === "fulfilled") {
          next[ids[idx]] = res.value;
        }
      });
      setDecisions(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load held positions");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <LoadingSkeleton rows={4} />;
  if (error || !portfolio) {
    return <ApiErrorBanner error={error ?? "Missing positions data"} onRetry={loadData} />;
  }

  const holdings = portfolio.snapshots.eod_mark_portfolio?.holdings ?? portfolio.current.holdings;

  return (
    <div className="space-y-5">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
          Position Supervision Directory
        </div>
        <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
          Position Management
        </h1>
        <p className="mt-0.5 text-[13.5px] text-[#334155]">
          Select any held position to inspect decoupled monitoring state, execution blockers,
          downside protection stress, and manual partial-sale scenarios.
        </p>
      </div>

      <ConflictBanner
        accountStateConflict={portfolio.account_state_conflict}
        confirmed={portfolio.snapshots.confirmed_ledger}
        latestCapture={portfolio.snapshots.latest_dom_capture}
      />

      {holdings.length === 0 ? (
        <EmptyStatePanel
          title="No held positions in active snapshot"
          description="No holdings are recorded for the selected mode."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
          {holdings.map((h) => {
            const dec = decisions[h.instrument_id];
            return (
              <div
                key={h.instrument_id}
                className="flex min-w-0 flex-col justify-between rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
                  <div>
                    <div className="text-[15px] font-semibold text-[#0F172A]">{h.symbol}</div>
                    <div className="font-mono text-[11.5px] text-[#64748B]">
                      {h.isin ?? h.instrument_id} &middot; {formatInteger(h.quantity)} shares
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {dec ? (
                      <>
                        <MonitoringBadge state={dec.monitoring_state} />
                        <ExecutionGateBadge state={dec.execution_state} />
                      </>
                    ) : null}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[12.5px]">
                  <div className="text-[#64748B]">EOD Reference Close</div>
                  <div className="mono-num text-right font-semibold text-[#0F172A]">
                    {formatProvenanceNumber(h.eod_reference_close_tnd)}
                  </div>
                  <div className="text-[#64748B]">Marked Weight</div>
                  <div className="mono-num text-right font-semibold text-[#0F172A]">
                    {dec?.risk ? formatProvenanceNumber(dec.risk.position_weight) : "Unavailable"}
                  </div>
                  <div className="text-[#64748B]">Exit Liquidity (10% ADV)</div>
                  <div className="mono-num text-right text-[#334155]">
                    {dec?.risk
                      ? formatProvenanceNumber(dec.risk.liquidity_days_to_exit)
                      : "Unavailable"}
                  </div>
                </div>

                {dec ? (
                  <p className="text-[12.5px] text-[#334155] break-words">{dec.explanation}</p>
                ) : null}

                <div className="flex items-center justify-between border-t border-[#E2E8F0] pt-2.5">
                  <Link
                    href={withModeHref(`/stocks/${encodeURIComponent(h.instrument_id)}`)}
                    className="text-[12.5px] font-medium text-[#334155] hover:underline"
                  >
                    Stock Research
                  </Link>
                  <Link
                    href={withModeHref(`/positions/${encodeURIComponent(h.instrument_id)}`)}
                    className="inline-flex min-h-[34px] items-center rounded-md bg-[#0F766E] px-3 py-1 text-[12.5px] font-medium text-white hover:bg-[#115E59]"
                  >
                    Manage Position &rarr;
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
