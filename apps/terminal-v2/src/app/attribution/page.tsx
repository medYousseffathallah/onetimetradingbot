"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type PerformanceAttribution,
  type PortfolioResponse,
} from "@/lib/v2-api";
import { formatInteger, formatProvenanceNumber, parseDecimal } from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ProvenanceNumber } from "@/components/ProvenanceNumber";
import { EquityTrajectoryChart } from "@/components/EquityTrajectoryChart";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

export default function PerformanceAttributionPage() {
  const { mode, withModeHref } = useMode();
  const [attr, setAttr] = useState<PerformanceAttribution | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [a, p] = await Promise.all([
        v2Api.getAttribution(mode),
        v2Api.getPortfolio(mode),
      ]);
      setAttr(a);
      setPortfolio(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load attribution");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <LoadingSkeleton rows={5} />;
  if (error || !attr || !portfolio) {
    return <ApiErrorBanner error={error ?? "Missing attribution data"} onRetry={loadData} />;
  }

  const holdings = portfolio.snapshots.eod_mark_portfolio?.holdings ?? portfolio.current.holdings;
  const snapshotBars = Object.entries(portfolio.snapshots).map(([key, snapshot]) => ({
    key,
    label:
      key === "confirmed_ledger"
        ? "1. Confirmed Ledger"
        : key === "latest_dom_capture"
          ? "2. Latest DOM Capture"
          : key === "unverified_screenshot"
            ? "3. Unverified Screenshot"
            : key === "eod_mark_portfolio"
              ? "4. Latest EOD Mark"
              : "Synthetic Demo Opening",
    snapshot,
  }));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
            GET /api/v2/attribution?mode={mode}
          </div>
          <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
            Performance &amp; Attribution
          </h1>
          <p className="mt-0.5 text-[13.5px] text-[#334155]">
            Window{" "}
            <strong className="mono-num">
              {attr.period_start} &rarr; {attr.period_end}
            </strong>
            . Separates realized P&amp;L, unrealized EOD marks, unexplained residual, and
            simulated benchmarks.
          </p>
        </div>
        <ProvenanceBadge status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"} />
      </div>

      {attr.failure_tags.length > 0 ? (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-lg border border-[#FDE68A] bg-[#FFFBEB] p-4 text-[#92400E]"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="min-w-0 space-y-1">
            <div className="text-[13.5px] font-semibold">
              Attribution Partial &mdash; Movements &amp; Verified Fee History Incomplete
            </div>
            <div className="text-[12.5px]">
              Unexplained residual:{" "}
              <strong className="mono-num">
                {formatProvenanceNumber(attr.unexplained_residual_tnd, { signed: true })}
              </strong>
              . Realized P&amp;L and estimated fees remain{" "}
              <code className="rounded bg-[#FEF3C7] px-1">UNAVAILABLE</code> until full account
              movements are imported.
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {attr.failure_tags.map((tag) => (
                <code
                  key={tag}
                  className="rounded border border-[#F59E0B]/50 bg-white px-1.5 py-0.5 text-[11px] font-semibold"
                >
                  {tag}
                </code>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <section className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Starting &rarr; Ending Equity
            </span>
            <ProvenanceBadge status={attr.ending_equity_tnd.status} />
          </div>
          <div className="mono-num text-[19px] font-semibold text-[#0F172A]">
            {formatProvenanceNumber(attr.ending_equity_tnd)}
          </div>
          <div className="text-[12px] text-[#64748B]">
            From {formatProvenanceNumber(attr.starting_equity_tnd)} (
            <span className="mono-num font-semibold text-[#0F172A]">
              {formatProvenanceNumber(attr.total_return_pct, { signed: true })}
            </span>
            )
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Realized P&amp;L
            </span>
            <ProvenanceBadge status={attr.realized_pnl_tnd.status} />
          </div>
          <div className="text-[19px] font-semibold text-[#0F172A]">
            <ProvenanceNumber pv={attr.realized_pnl_tnd} signed showBadge={false} showReason />
          </div>
          <div className="text-[12px] text-[#64748B]">
            Est. Fees: <ProvenanceNumber pv={attr.estimated_fees_tnd} showBadge={false} />
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Unrealized P&amp;L (EOD Marks)
            </span>
            <ProvenanceBadge status={attr.unrealized_pnl_tnd.status} />
          </div>
          <div className="mono-num text-[19px] font-semibold text-[#065F46]">
            {formatProvenanceNumber(attr.unrealized_pnl_tnd, { signed: true })}
          </div>
          <div className="text-[12px] text-[#64748B]">
            Cash Drag: {formatProvenanceNumber(attr.cash_drag_pct)}
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Unexplained Residual
            </span>
            <ProvenanceBadge
              status={
                attr.unexplained_residual_tnd.value !== null &&
                Number(attr.unexplained_residual_tnd.value) !== 0
                  ? "UNVERIFIED"
                  : attr.unexplained_residual_tnd.status
              }
            />
          </div>
          <div className="mono-num text-[19px] font-semibold text-[#92400E]">
            {formatProvenanceNumber(attr.unexplained_residual_tnd, { signed: true })}
          </div>
          <div className="text-[12px] text-[#64748B]">
            Equity delta minus open mark-to-market gains
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3 lg:col-span-6">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Account Snapshot Valuation Trajectory
              </h2>
              <div className="text-[12px] text-[#64748B]">
                Side-by-side comparison without merging truth states
              </div>
            </div>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"}
            />
          </div>
          <EquityTrajectoryChart items={snapshotBars} />
        </div>

        <div className="rounded-lg border border-[#DDD6FE] bg-[#F5F3FF] p-4 space-y-3 lg:col-span-6">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#DDD6FE] pb-2.5">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#5B21B6]">
                Simulated Benchmark Comparison Lane
              </h2>
              <div className="text-[12px] text-[#5B21B6]">
                Strictly isolated from realized account P&amp;L. TUNINDEX absent locally.
              </div>
            </div>
            <ProvenanceBadge status="SIMULATED" />
          </div>

          <div className="divide-y divide-[#DDD6FE]">
            {Object.entries(attr.benchmarks).map(([label, pv]) => (
              <div key={label} className="flex items-center justify-between gap-2 py-2.5">
                <div className="min-w-0">
                  <div className="font-mono text-[12.5px] font-semibold text-[#0F172A] break-all">
                    {label}
                  </div>
                  <div className="text-[11px] text-[#64748B] break-all">{pv.source}</div>
                </div>
                <ProvenanceNumber pv={pv} signed showReason />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] px-4 py-3.5">
          <div>
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Per-Stock EOD Mark Attribution ({holdings.length} Holdings)
            </h2>
            <div className="text-[12px] text-[#64748B]">
              Unrealized contribution computed from displayed acquisition basis vs latest EOD
              close.
            </div>
          </div>
          <ProvenanceBadge status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"} />
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-[#E2E8F0] bg-[#F1F5F9] text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#64748B]">
                <th className="px-4 py-2.5">Security</th>
                <th className="px-4 py-2.5 text-right">Qty</th>
                <th className="px-4 py-2.5 text-right">Displayed Avg Cost</th>
                <th className="px-4 py-2.5 text-right">EOD Reference Close</th>
                <th className="px-4 py-2.5 text-right">Unrealized P&amp;L</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {holdings.map((h) => {
                const rowAttr = attr.position_attributions[h.instrument_id];
                const pnlPv = rowAttr?.unrealized_pnl_tnd;
                const pnlNum = parseDecimal(pnlPv?.value);

                return (
                  <tr key={h.instrument_id} className="hover:bg-[#F8FAFC]">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-[#0F172A]">{h.symbol}</div>
                      <div className="font-mono text-[11.5px] text-[#64748B]">
                        {h.isin ?? h.instrument_id}
                      </div>
                    </td>
                    <td className="mono-num px-4 py-3 text-right text-[#0F172A]">
                      {formatInteger(h.quantity)}
                    </td>
                    <td className="mono-num px-4 py-3 text-right text-[#334155]">
                      {formatProvenanceNumber(h.displayed_avg_cost_tnd, { withUnit: false })}
                    </td>
                    <td className="mono-num px-4 py-3 text-right text-[#0F172A]">
                      {formatProvenanceNumber(
                        rowAttr?.eod_reference_close_tnd ?? h.eod_reference_close_tnd,
                        { withUnit: false },
                      )}
                    </td>
                    <td
                      className={`mono-num px-4 py-3 text-right font-semibold ${
                        pnlNum === null
                          ? "text-[#94A3B8]"
                          : pnlNum >= 0
                            ? "text-[#065F46]"
                            : "text-[#991B1B]"
                      }`}
                    >
                      {formatProvenanceNumber(pnlPv, { signed: true })}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={withModeHref(`/positions/${encodeURIComponent(h.instrument_id)}`)}
                        className="font-medium text-[#0F766E] hover:underline"
                      >
                        Manage &rarr;
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="divide-y divide-[#E2E8F0] md:hidden">
          {holdings.map((h) => {
            const rowAttr = attr.position_attributions[h.instrument_id];
            const pnlPv = rowAttr?.unrealized_pnl_tnd;
            return (
              <div key={h.instrument_id} className="space-y-1.5 p-4 text-[12.5px]">
                <div className="flex items-center justify-between gap-2 font-semibold text-[#0F172A]">
                  <span>{h.symbol}</span>
                  <ProvenanceNumber pv={pnlPv} signed showBadge={false} />
                </div>
                <div className="flex items-center justify-between text-[#64748B]">
                  <span>
                    {formatInteger(h.quantity)} sh @{" "}
                    {formatProvenanceNumber(h.displayed_avg_cost_tnd)}
                  </span>
                  <Link
                    href={withModeHref(`/positions/${encodeURIComponent(h.instrument_id)}`)}
                    className="font-medium text-[#0F766E] hover:underline"
                  >
                    Manage &rarr;
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
