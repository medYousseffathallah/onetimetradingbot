"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type OpportunityCandidate,
  type PortfolioResponse,
  type PositionDecision,
} from "@/lib/v2-api";
import {
  formatInteger,
  formatProvenanceNumber,
  formatTimestamp,
  formatTnd,
  parseDecimal,
} from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ExecutionGateBadge, MonitoringBadge } from "@/components/StateBadges";
import { ConflictBanner } from "@/components/ConflictBanner";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

type PortfolioTab = "HOLDINGS" | "SECTORS" | "AUDIT";

export default function PortfolioManagerPage() {
  const { mode, withModeHref, setAccountTruthState } = useMode();
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [decisions, setDecisions] = useState<Record<string, PositionDecision>>({});
  const [sectors, setSectors] = useState<Record<string, string>>({});
  const [tab, setTab] = useState<PortfolioTab>("HOLDINGS");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pf, disc] = await Promise.all([
        v2Api.getPortfolio(mode),
        v2Api.getDiscovery(mode, "FULL_BVMT_RESEARCH", "5_10").catch(() => null),
      ]);
      setPortfolio(pf);
      setAccountTruthState(pf.account_state_conflict ? "CONFLICTED" : "UNVERIFIED");

      if (disc) {
        const sectorMap: Record<string, string> = {};
        disc.candidates.forEach((c: OpportunityCandidate) => {
          sectorMap[c.assessment.instrument.instrument_id] =
            c.assessment.instrument.sector ?? "Unclassified";
        });
        setSectors(sectorMap);
      }

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
      setError(err instanceof Error ? err.message : "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, [mode, setAccountTruthState]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <LoadingSkeleton rows={6} />;
  if (error || !portfolio) {
    return <ApiErrorBanner error={error ?? "Missing portfolio data"} onRetry={loadData} />;
  }

  const confirmed = portfolio.snapshots.confirmed_ledger;
  const latestCapture = portfolio.snapshots.latest_dom_capture;
  const eodMark = portfolio.snapshots.eod_mark_portfolio;
  const holdings = eodMark?.holdings ?? portfolio.current.holdings;

  const sectorTotals = new Map<string, { value: number; count: number }>();
  const totalEquity = parseDecimal(eodMark?.equity_tnd.value) ?? 0;

  holdings.forEach((h) => {
    const sec = sectors[h.instrument_id] ?? "Unclassified";
    const close = parseDecimal(h.eod_reference_close_tnd.value) ?? 0;
    const val = close * h.quantity;
    const prev = sectorTotals.get(sec) ?? { value: 0, count: 0 };
    sectorTotals.set(sec, { value: prev.value + val, count: prev.count + 1 });
  });

  const sectorRows = Array.from(sectorTotals.entries())
    .map(([sector, info]) => ({
      sector,
      value: info.value,
      count: info.count,
      weightPct: totalEquity > 0 ? (info.value / totalEquity) * 100 : 0,
    }))
    .sort((a, b) => b.value - a.value);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
            GET /api/v2/portfolio?mode={mode}
          </div>
          <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
            Portfolio Manager
          </h1>
          <p className="mt-0.5 text-[13.5px] text-[#334155]">
            Holdings, displayed vs verified cost bases, single-stock concentration limits (10%
            cap), theses, and snapshot audit timeline.
          </p>
        </div>
        <ExecutionGateBadge
          state={portfolio.execution_enabled ? "ELIGIBLE_MANUAL_ONLY" : "EXECUTION_BLOCKED"}
        />
      </div>

      <ConflictBanner
        accountStateConflict={portfolio.account_state_conflict}
        confirmed={confirmed}
        latestCapture={latestCapture}
        showActionLink={false}
      />

      <section className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11.5px] font-semibold uppercase tracking-wide text-[#64748B]">
              {mode === "SYNTHETIC_DEMO" ? "Demo Cash" : "Confirmed Cash"}
            </span>
            <ProvenanceBadge
              status={
                mode === "SYNTHETIC_DEMO"
                  ? "SIMULATED"
                  : confirmed?.cash_tnd.status ?? "OBSERVED"
              }
            />
          </div>
          <div className="mono-num mt-1.5 text-[20px] font-semibold text-[#0F172A]">
            {formatProvenanceNumber(
              mode === "SYNTHETIC_DEMO" ? portfolio.current.cash_tnd : confirmed?.cash_tnd,
            )}
          </div>
          <div className="mt-1 text-[12px] text-[#64748B]">
            {confirmed?.snapshot_id ?? portfolio.current.snapshot_id}
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11.5px] font-semibold uppercase tracking-wide text-[#64748B]">
              Latest Capture Cash
            </span>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "UNVERIFIED"}
            />
          </div>
          <div className="mono-num mt-1.5 text-[20px] font-semibold text-[#0F172A]">
            {formatProvenanceNumber(
              latestCapture?.cash_tnd ?? portfolio.current.cash_tnd,
            )}
          </div>
          <div className="mt-1 text-[12px] text-[#64748B]">
            {latestCapture?.snapshot_id ?? portfolio.current.snapshot_id}
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11.5px] font-semibold uppercase tracking-wide text-[#64748B]">
              EOD Marked Holdings
            </span>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"}
            />
          </div>
          <div className="mono-num mt-1.5 text-[20px] font-semibold text-[#0F172A]">
            {formatProvenanceNumber(eodMark?.holdings_value_tnd)}
          </div>
          <div className="mt-1 text-[12px] text-[#64748B]">
            {holdings.length} positions @ {portfolio.latest_session ?? "EOD"}
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11.5px] font-semibold uppercase tracking-wide text-[#64748B]">
              Pending Orders / Movements
            </span>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "UNVERIFIED"}
            />
          </div>
          <div className="mt-1.5 text-[18px] font-semibold text-[#92400E]">
            {mode === "SYNTHETIC_DEMO" ? "0 (Fixture)" : "Unverified"}
          </div>
          <div className="mt-1 text-[12px] text-[#64748B]">
            {mode === "SYNTHETIC_DEMO"
              ? "Isolated demo ledger"
              : "movements_page_captured=false"}
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Portfolio sections">
        {(
          [
            ["HOLDINGS", `Holdings & Theses (${holdings.length})`],
            ["SECTORS", `Sector & Issuer Weights (${sectorRows.length})`],
            ["AUDIT", `Snapshots & Orders Audit (${Object.keys(portfolio.snapshots).length})`],
          ] as Array<[PortfolioTab, string]>
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`min-h-[38px] rounded-md border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors ${
              tab === key
                ? "border-[#99F6E4] bg-[#F0FDFA] font-semibold text-[#0F766E]"
                : "border-[#E2E8F0] bg-white text-[#334155] hover:bg-[#F1F5F9]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "HOLDINGS" ? (
        <section className="overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F1F5F9] text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#64748B]">
                  <th className="px-4 py-2.5">Security / ISIN</th>
                  <th className="px-4 py-2.5 text-right">Qty</th>
                  <th className="px-4 py-2.5 text-right">Displayed Avg Cost</th>
                  <th className="px-4 py-2.5 text-right">EOD Close</th>
                  <th className="px-4 py-2.5 text-right">Weight %</th>
                  <th className="px-4 py-2.5">Thesis / Horizon</th>
                  <th className="px-4 py-2.5">Monitoring / Gate</th>
                  <th className="px-4 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {holdings.map((h) => {
                  const dec = decisions[h.instrument_id];
                  const weightPv = dec?.risk?.position_weight;
                  const weightPct = weightPv?.value ? Number(weightPv.value) * 100 : null;
                  const breach = dec?.risk?.concentration_breach;

                  return (
                    <tr key={h.instrument_id} className="hover:bg-[#F8FAFC]">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-[#0F172A]">{h.symbol}</div>
                        <div className="font-mono text-[11.5px] text-[#64748B]">
                          {h.isin ?? h.instrument_id} &middot; {sectors[h.instrument_id] ?? "—"}
                        </div>
                      </td>
                      <td className="mono-num px-4 py-3 text-right text-[#0F172A]">
                        {formatInteger(h.quantity)}
                      </td>
                      <td className="mono-num px-4 py-3 text-right text-[#334155]">
                        {formatProvenanceNumber(h.displayed_avg_cost_tnd, { withUnit: false })}
                      </td>
                      <td className="mono-num px-4 py-3 text-right text-[#0F172A]">
                        {formatProvenanceNumber(h.eod_reference_close_tnd, { withUnit: false })}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {weightPct !== null ? (
                          <div className="inline-flex items-center gap-2">
                            <span className="inline-block h-1.5 w-12 overflow-hidden rounded bg-[#F1F5F9]">
                              <span
                                className={`block h-full ${
                                  breach ? "bg-[#D97706]" : "bg-[#0F766E]"
                                }`}
                                style={{ width: `${Math.min(100, weightPct * 5).toFixed(0)}%` }}
                              />
                            </span>
                            <span
                              className={`mono-num font-semibold ${
                                breach ? "text-[#92400E]" : "text-[#0F172A]"
                              }`}
                            >
                              {weightPct.toFixed(2)}%
                            </span>
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-4 py-3 text-[12px]">
                        <div className="text-[#334155]">
                          {dec?.thesis?.thesis ?? "No human thesis recorded"}
                        </div>
                        <div className="mt-0.5 text-[11px] text-[#64748B]">
                          {dec?.thesis?.origin ?? "UNVERIFIED_NONE"}
                          {dec?.thesis?.horizon_sessions
                            ? ` · ${dec.thesis.horizon_sessions}s`
                            : ""}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap items-center gap-1">
                          {dec ? (
                            <>
                              <MonitoringBadge state={dec.monitoring_state} />
                              <ExecutionGateBadge state={dec.execution_state} />
                            </>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <Link
                            href={withModeHref(
                              `/positions/${encodeURIComponent(h.instrument_id)}`,
                            )}
                            className="font-medium text-[#0F766E] hover:underline"
                          >
                            Position
                          </Link>
                          <Link
                            href={withModeHref(`/stocks/${encodeURIComponent(h.instrument_id)}`)}
                            className="font-medium text-[#334155] hover:underline"
                          >
                            Research
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="divide-y divide-[#E2E8F0] md:hidden">
            {holdings.map((h) => {
              const dec = decisions[h.instrument_id];
              const weightPv = dec?.risk?.position_weight;
              const breach = dec?.risk?.concentration_breach;

              return (
                <div key={h.instrument_id} className="space-y-2 p-4">
                  <div className="flex items-start justify-between gap-2 border-b border-[#E2E8F0] pb-2">
                    <div>
                      <div className="font-semibold text-[#0F172A]">{h.symbol}</div>
                      <div className="font-mono text-[11.5px] text-[#64748B]">
                        {h.isin ?? h.instrument_id} &middot; {sectors[h.instrument_id] ?? "—"}
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-1">
                      {dec ? (
                        <>
                          <MonitoringBadge state={dec.monitoring_state} />
                          <ExecutionGateBadge state={dec.execution_state} />
                        </>
                      ) : null}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12.5px]">
                    <div className="text-[#64748B]">Qty</div>
                    <div className="mono-num text-right font-semibold text-[#0F172A]">
                      {formatInteger(h.quantity)}
                    </div>
                    <div className="text-[#64748B]">Avg Cost</div>
                    <div className="mono-num text-right text-[#334155]">
                      {formatProvenanceNumber(h.displayed_avg_cost_tnd)}
                    </div>
                    <div className="text-[#64748B]">EOD Close</div>
                    <div className="mono-num text-right text-[#0F172A]">
                      {formatProvenanceNumber(h.eod_reference_close_tnd)}
                    </div>
                    <div className="text-[#64748B]">Weight %</div>
                    <div
                      className={`mono-num text-right font-semibold ${
                        breach ? "text-[#92400E]" : "text-[#0F172A]"
                      }`}
                    >
                      {weightPv ? formatProvenanceNumber(weightPv) : "—"}
                    </div>
                    <div className="text-[#64748B]">Thesis</div>
                    <div className="text-right text-[12px] text-[#334155]">
                      {dec?.thesis?.origin ?? "UNVERIFIED_NONE"}
                    </div>
                  </div>
                  <div className="flex justify-end gap-4 pt-1 text-[12.5px] font-medium">
                    <Link
                      href={withModeHref(`/positions/${encodeURIComponent(h.instrument_id)}`)}
                      className="text-[#0F766E] hover:underline"
                    >
                      Position &rarr;
                    </Link>
                    <Link
                      href={withModeHref(`/stocks/${encodeURIComponent(h.instrument_id)}`)}
                      className="text-[#334155] hover:underline"
                    >
                      Research &rarr;
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {tab === "SECTORS" ? (
        <section className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-3">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Sector Exposure (Marked EOD)
              </h2>
              <p className="text-[12px] text-[#64748B]">
                Share of marked portfolio equity across sectors.
              </p>
            </div>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"}
            />
          </div>
          <div className="space-y-3">
            {sectorRows.map((row) => (
              <div key={row.sector} className="space-y-1">
                <div className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                  <span className="font-semibold text-[#0F172A]">
                    {row.sector} ({row.count} {row.count === 1 ? "issuer" : "issuers"})
                  </span>
                  <span className="mono-num text-[#0F172A]">
                    {formatTnd(row.value.toFixed(3))} &middot;{" "}
                    <strong>{row.weightPct.toFixed(2)}%</strong>
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded bg-[#F1F5F9]">
                  <div
                    className="h-full rounded bg-[#0F766E]"
                    style={{ width: `${Math.min(100, row.weightPct * 2).toFixed(1)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {tab === "AUDIT" ? (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Snapshot Audit Timeline (Read-Only)
            </h2>
            <div className="space-y-3">
              {Object.entries(portfolio.snapshots).map(([key, snap]) => (
                <div
                  key={key}
                  className="rounded-md border border-[#E2E8F0] bg-[#F8F9FA] p-3 text-[12.5px]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-[#0F172A]">{key}</span>
                    <ProvenanceBadge status={snap.verification_status} />
                  </div>
                  <div className="mt-1 font-mono text-[11.5px] text-[#64748B] break-all">
                    id: {snap.snapshot_id} &middot; captured: {formatTimestamp(snap.captured_at)}
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <div>
                      Equity:{" "}
                      <strong className="mono-num">
                        {formatProvenanceNumber(snap.equity_tnd)}
                      </strong>
                    </div>
                    <div>
                      Cash:{" "}
                      <strong className="mono-num">{formatProvenanceNumber(snap.cash_tnd)}</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Orders, Movements &amp; Rejected Captures
              </h2>
              <ProvenanceBadge
                status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "UNVERIFIED"}
              />
            </div>
            <div className="rounded-md border border-[#FDE68A] bg-[#FFFBEB] p-3 text-[12.5px] text-[#92400E]">
              {mode === "SYNTHETIC_DEMO"
                ? "Synthetic demo fixture holds 1 simulated lot; no competition movements apply."
                : "Verified transaction ledger and pending orders page (display_histo.aspx / movements_page_captured=false) have NOT been imported. Never treat missing order logs as '0 pending orders confirmed'."}
            </div>
            <div>
              <div className="text-[12px] font-semibold uppercase tracking-wide text-[#64748B]">
                Rejected DOM Captures ({portfolio.rejected_captures.length})
              </div>
              {portfolio.rejected_captures.length === 0 ? (
                <p className="mt-1 text-[12.5px] text-[#64748B]">
                  No rejected capture files in current mode.
                </p>
              ) : (
                <ul className="mt-2 space-y-1.5">
                  {portfolio.rejected_captures.map((name) => (
                    <li
                      key={name}
                      className="rounded border border-[#FECACA] bg-[#FEF2F2] px-2.5 py-1.5 font-mono text-[12px] text-[#991B1B] break-all"
                    >
                      {name} (unreconciled / action button parsed as ticker)
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
