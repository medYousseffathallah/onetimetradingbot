"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type OverviewResponse,
  type PortfolioResponse,
  type PositionDecision,
  type PerformanceAttribution,
  type PortfolioSnapshot,
  type ValueStatus,
} from "@/lib/v2-api";
import {
  formatInteger,
  formatProvenanceNumber,
  formatTnd,
  parseDecimal,
} from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ExecutionGateBadge, MonitoringBadge } from "@/components/StateBadges";
import { ConflictBanner } from "@/components/ConflictBanner";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

export default function InvestmentOverviewPage() {
  const { mode, withModeHref, setAccountTruthState } = useMode();
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [attribution, setAttribution] = useState<PerformanceAttribution | null>(null);
  const [decisions, setDecisions] = useState<Record<string, PositionDecision>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, pf, attr] = await Promise.all([
        v2Api.getOverview(mode),
        v2Api.getPortfolio(mode),
        v2Api.getAttribution(mode),
      ]);
      setOverview(ov);
      setPortfolio(pf);
      setAttribution(attr);
      setAccountTruthState(ov.account_state_conflict ? "CONFLICTED" : "UNVERIFIED");

      const holdingIds = ov.current.holdings.map((h) => h.instrument_id);
      const settled = await Promise.allSettled(
        holdingIds.map((id) => v2Api.getPosition(id, mode)),
      );
      const nextDecisions: Record<string, PositionDecision> = {};
      settled.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          nextDecisions[holdingIds[idx]] = result.value;
        }
      });
      setDecisions(nextDecisions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load overview");
    } finally {
      setLoading(false);
    }
  }, [mode, setAccountTruthState]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <LoadingSkeleton rows={5} />;
  if (error || !overview || !portfolio) {
    return <ApiErrorBanner error={error ?? "Missing overview data"} onRetry={loadData} />;
  }

  const snaps = portfolio.snapshots;
  const confirmed: PortfolioSnapshot | undefined = snaps.confirmed_ledger;
  const latestCapture: PortfolioSnapshot | undefined = snaps.latest_dom_capture;
  const screenshot: PortfolioSnapshot | undefined = snaps.unverified_screenshot;
  const eodMark: PortfolioSnapshot | undefined = snaps.eod_mark_portfolio;
  const syntheticDemo: PortfolioSnapshot | undefined = snaps.synthetic_demo;

  const truthCards: Array<{
    key: string;
    title: string;
    snap: PortfolioSnapshot | undefined;
    overrideStatus?: ValueStatus;
    footerLeft: string;
    footerRight: string;
    isEodMark?: boolean;
  }> =
    mode === "SYNTHETIC_DEMO"
      ? [
          {
            key: "synthetic_demo",
            title: "1. Synthetic Demo Opening",
            snap: syntheticDemo,
            overrideStatus: "SIMULATED",
            footerLeft: syntheticDemo?.snapshot_id ?? "synthetic_demo_opening",
            footerRight: `${syntheticDemo?.holdings.length ?? 0} holding`,
          },
          {
            key: "eod_mark_portfolio",
            title: "2. Synthetic EOD Mark",
            snap: eodMark,
            overrideStatus: "SIMULATED",
            footerLeft: "Live quote:",
            footerRight: "UNAVAILABLE",
            isEodMark: true,
          },
        ]
      : [
          {
            key: "confirmed_ledger",
            title: "1. Confirmed Ledger",
            snap: confirmed,
            overrideStatus: confirmed?.verification_status ?? "OBSERVED",
            footerLeft: confirmed?.snapshot_id ?? "confirmed_ledger",
            footerRight: confirmed?.rank
              ? `Rank ${formatInteger(confirmed.rank)} / ${formatInteger(confirmed.total_participants)}`
              : "Rank Unavailable",
          },
          {
            key: "latest_dom_capture",
            title: "2. Latest DOM Capture",
            snap: latestCapture,
            overrideStatus: "UNVERIFIED",
            footerLeft: latestCapture?.snapshot_id ?? "latest_dom_capture",
            footerRight: latestCapture?.rank
              ? `Rank ${formatInteger(latestCapture.rank)} / ${formatInteger(latestCapture.total_participants)}`
              : "Rank Unavailable",
          },
          {
            key: "unverified_screenshot",
            title: "3. User Screenshot",
            snap: screenshot,
            overrideStatus: "UNVERIFIED",
            footerLeft: screenshot?.reported_holdings_count
              ? `Unverified (${screenshot.reported_holdings_count} pos)`
              : "Unverified Screenshot",
            footerRight: screenshot?.rank
              ? `Rank ${formatInteger(screenshot.rank)} / ${formatInteger(screenshot.total_participants)}`
              : "Rank Unavailable",
          },
          {
            key: "eod_mark_portfolio",
            title: `4. ${overview.latest_market_session ?? "EOD"} Mark`,
            snap: eodMark,
            overrideStatus: "CALCULATED",
            footerLeft: "Live quote:",
            footerRight: "UNAVAILABLE",
            isEodMark: true,
          },
        ];

  const cashVal = parseDecimal(eodMark?.cash_tnd.value ?? overview.current.cash_tnd.value) ?? 0;
  const holdingsVal =
    parseDecimal(eodMark?.holdings_value_tnd.value ?? overview.current.holdings_value_tnd.value) ??
    0;
  const totalEquity = parseDecimal(eodMark?.equity_tnd.value ?? overview.current.equity_tnd.value);
  const investedPct =
    totalEquity && totalEquity > 0 ? Math.max(0, Math.min(100, (holdingsVal / totalEquity) * 100)) : 0;
  const cashPct = totalEquity && totalEquity > 0 ? 100 - investedPct : 0;
  const circumference = 2 * Math.PI * 46;
  const investedDash = (investedPct / 100) * circumference;

  const markedHoldings = eodMark?.holdings ?? overview.current.holdings;

  const priorityItems: Array<{
    id: string;
    title: string;
    badge: React.ReactNode;
    desc: string;
    href: string;
    cta: string;
  }> = [];

  if (overview.account_state_conflict) {
    priorityItems.push({
      id: "conflict",
      title: "Resolve Out-of-Order Snapshot Conflict",
      badge: <ProvenanceBadge status="UNVERIFIED" />,
      desc: "Confirmed ledger and newer DOM capture disagree; movements history is unimported.",
      href: "/portfolio",
      cta: "Open Portfolio Reconciliation →",
    });
  }

  Object.values(decisions)
    .filter(
      (d) =>
        d.monitoring_state === "CONSIDER_TRIM" ||
        d.monitoring_state === "CONSIDER_EXIT" ||
        d.monitoring_state === "REVIEW" ||
        d.risk?.concentration_breach,
    )
    .slice(0, 3)
    .forEach((d) => {
      const weightText = d.risk?.position_weight
        ? formatProvenanceNumber(d.risk.position_weight)
        : "Weight unavailable";
      priorityItems.push({
        id: d.instrument_id,
        title: `${d.instrument_id} (${weightText})`,
        badge: (
          <div className="flex flex-wrap items-center gap-1">
            <MonitoringBadge state={d.monitoring_state} />
            <ExecutionGateBadge state={d.execution_state} />
          </div>
        ),
        desc: d.explanation,
        href: `/positions/${encodeURIComponent(d.instrument_id)}`,
        cta: "Manage Position →",
      });
    });

  if (attribution && attribution.unexplained_residual_tnd.value !== null) {
    priorityItems.push({
      id: "residual",
      title: `Unexplained P&L Residual (${formatProvenanceNumber(attribution.unexplained_residual_tnd, { signed: true })})`,
      badge: <ProvenanceBadge status="UNVERIFIED" label="ATTRIBUTION PARTIAL" />,
      desc: "Unreconciled delta requires full competition movements/orders history import.",
      href: "/attribution",
      cta: "Inspect Attribution →",
    });
  }

  if (overview.rules_blocker_count > 0 && mode === "REAL_COMPETITION") {
    priorityItems.push({
      id: "rules",
      title: `${overview.rules_blocker_count} Unverified Competition Rule Blockers`,
      badge: <ExecutionGateBadge state="EXECUTION_BLOCKED" />,
      desc: "Order execution remains blocked until official competition rules and live quotes are verified.",
      href: "/health",
      cta: "Audit Blockers →",
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
            GET /api/v2/overview?mode={mode}
          </div>
          <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
            Investment Overview
          </h1>
          <p className="mt-0.5 text-[13.5px] text-[#334155]">
            Separate confirmed ledger state, newer captures, unverified screenshots, and EOD
            mark-to-market valuations.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ExecutionGateBadge
            state={overview.execution_enabled ? "ELIGIBLE_MANUAL_ONLY" : "EXECUTION_BLOCKED"}
          />
          <Link
            href={withModeHref("/portfolio")}
            className="inline-flex min-h-[38px] items-center rounded-md bg-[#0F766E] px-3.5 py-1.5 text-[13px] font-medium text-white hover:bg-[#115E59]"
          >
            Inspect Portfolio &rarr;
          </Link>
        </div>
      </div>

      <ConflictBanner
        accountStateConflict={overview.account_state_conflict}
        confirmed={confirmed}
        latestCapture={latestCapture}
      />

      <section
        aria-label="Account valuation truth states"
        className={`grid grid-cols-1 gap-3.5 sm:grid-cols-2 ${
          truthCards.length === 4 ? "xl:grid-cols-4" : "xl:grid-cols-2"
        }`}
      >
        {truthCards.map((card) => {
          const status = card.overrideStatus ?? card.snap?.verification_status ?? "UNAVAILABLE";
          const eqStr = formatProvenanceNumber(card.snap?.equity_tnd, { withUnit: false });
          const cashStr = formatProvenanceNumber(card.snap?.cash_tnd);
          const count = card.snap?.reported_holdings_count ?? card.snap?.holdings.length ?? 0;

          return (
            <article
              key={card.key}
              className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11.5px] font-semibold uppercase tracking-[0.04em] text-[#64748B]">
                  {card.title}
                </span>
                <ProvenanceBadge status={status} provenance={card.snap?.equity_tnd} />
              </div>
              <div className="mono-num text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
                {eqStr}
                {eqStr !== "Unavailable" ? (
                  <small className="ml-1 text-[12px] font-medium text-[#64748B]">TND</small>
                ) : null}
              </div>
              <div className="text-[12px] text-[#334155]">
                {card.key === "unverified_screenshot" && attribution ? (
                  <>
                    Residual vs open gains:{" "}
                    <strong className="mono-num text-[#92400E]">
                      {formatProvenanceNumber(attribution.unexplained_residual_tnd, {
                        signed: true,
                      })}
                    </strong>
                  </>
                ) : (
                  <>
                    Cash: <strong className="mono-num">{cashStr}</strong> &middot; {count} holdings
                  </>
                )}
              </div>
              <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-[#E2E8F0] pt-2 text-[11.5px] text-[#64748B]">
                <span className="break-all font-mono">{card.footerLeft}</span>
                {card.isEodMark ? (
                  <ProvenanceBadge status="UNAVAILABLE" label="UNAVAILABLE" />
                ) : (
                  <span className="mono-num">{card.footerRight}</span>
                )}
              </div>
            </article>
          );
        })}
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="min-w-0 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] lg:col-span-7">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] px-4 py-3.5">
            <div className="min-w-0">
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Capital Structure &amp; Cash Drag
              </h2>
              <div className="text-[12px] text-[#64748B]">
                Marked holdings ({formatTnd(holdingsVal.toFixed(3))}) + cash reserve (
                {formatTnd(cashVal.toFixed(3))})
              </div>
            </div>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"}
            />
          </div>

          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:items-center">
              <div className="flex items-center gap-4">
                <svg
                  width="104"
                  height="104"
                  viewBox="0 0 120 120"
                  role="img"
                  aria-label={`Allocation ${cashPct.toFixed(1)}% cash, ${investedPct.toFixed(1)}% equities`}
                  className="shrink-0"
                >
                  <circle
                    cx="60"
                    cy="60"
                    r="46"
                    fill="none"
                    stroke="#E2E8F0"
                    strokeWidth="14"
                  />
                  <circle
                    cx="60"
                    cy="60"
                    r="46"
                    fill="none"
                    stroke="#0F766E"
                    strokeWidth="14"
                    strokeDasharray={`${investedDash.toFixed(1)} ${circumference.toFixed(1)}`}
                    transform="rotate(-90 60 60)"
                  />
                  <text
                    x="60"
                    y="57"
                    textAnchor="middle"
                    fontFamily="JetBrains Mono, monospace"
                    fontSize="15"
                    fontWeight="700"
                    fill="#0F172A"
                  >
                    {investedPct.toFixed(1)}%
                  </text>
                  <text
                    x="60"
                    y="73"
                    textAnchor="middle"
                    fontFamily="Inter, sans-serif"
                    fontSize="9.5"
                    fontWeight="600"
                    fill="#64748B"
                  >
                    INVESTED
                  </text>
                </svg>

                <div className="min-w-0">
                  <div className="text-[11.5px] font-semibold uppercase tracking-wide text-[#64748B]">
                    Idle Cash Share
                  </div>
                  <div className="mono-num text-[22px] font-semibold text-[#0F172A]">
                    {cashPct.toFixed(2)}%
                  </div>
                  <div className="text-[12px] text-[#334155]">
                    {attribution
                      ? `Attribution cash drag: ${formatProvenanceNumber(attribution.cash_drag_pct)}`
                      : "Confirmed cash share"}
                  </div>
                </div>
              </div>

              <div className="divide-y divide-[#E2E8F0] text-[13px]">
                <div className="flex items-center justify-between gap-2 py-2">
                  <span className="text-[#334155]">Cash Reserve</span>
                  <span className="mono-num font-semibold text-[#0F172A]">
                    {formatTnd(cashVal.toFixed(3))}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2 py-2">
                  <span className="text-[#334155]">EOD Holdings Value</span>
                  <span className="mono-num font-semibold text-[#0F172A]">
                    {formatTnd(holdingsVal.toFixed(3))}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2 py-2">
                  <span className="text-[#334155]">Pending Orders</span>
                  <ProvenanceBadge
                    status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "UNVERIFIED"}
                  />
                </div>
              </div>
            </div>

            <div className="rounded-md border border-[#E2E8F0] bg-[#F1F5F9] p-3 text-[12.5px] text-[#334155]">
              <strong>Cash Drag Note:</strong> Idle cash reduced effective equity exposure by{" "}
              <strong className="mono-num">{cashPct.toFixed(2)}%</strong>. High cash is preserved
              while <code className="font-mono">{overview.rules_blocker_count}</code> rule
              blockers and unverified movements remain open.
            </div>
          </div>
        </div>

        <div className="min-w-0 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] lg:col-span-5">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] px-4 py-3.5">
            <div className="min-w-0">
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">Review Priorities</h2>
              <div className="text-[12px] text-[#64748B]">
                Ordered by portfolio integrity &amp; risk severity
              </div>
            </div>
            <span className="rounded border border-[#FDE68A] bg-[#FFFBEB] px-2 py-0.5 text-[10.5px] font-semibold uppercase text-[#92400E]">
              {priorityItems.length} ITEMS
            </span>
          </div>

          <div className="divide-y divide-[#E2E8F0]">
            {priorityItems.map((item, idx) => (
              <div key={item.id} className="space-y-1.5 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-[#0F172A]">
                    {idx + 1}. {item.title}
                  </span>
                  {item.badge}
                </div>
                <p className="text-[12.5px] text-[#334155] break-words">{item.desc}</p>
                <Link
                  href={withModeHref(item.href)}
                  className="inline-block text-[12.5px] font-medium text-[#0F766E] hover:text-[#115E59] hover:underline"
                >
                  {item.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] px-4 py-3.5">
          <div className="min-w-0">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Holdings Pulse ({markedHoldings.length} Positions @ {overview.latest_market_session ?? "EOD"})
            </h2>
            <div className="text-[12px] text-[#64748B]">
              Current executable quotes are UNAVAILABLE; prices reflect latest BVMT EOD closes.
            </div>
          </div>
          <Link
            href={withModeHref("/portfolio")}
            className="inline-flex min-h-[36px] items-center rounded-md border border-[#CBD5E1] bg-white px-3 py-1 text-[12.5px] font-medium text-[#0F172A] hover:bg-[#F1F5F9]"
          >
            Full Portfolio Table &rarr;
          </Link>
        </div>

        {/* Desktop Table */}
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-[#E2E8F0] bg-[#F1F5F9] text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#64748B]">
                <th className="px-4 py-2.5">Security / ISIN</th>
                <th className="px-4 py-2.5 text-right">Qty</th>
                <th className="px-4 py-2.5 text-right">Avg Cost</th>
                <th className="px-4 py-2.5 text-right">EOD Close</th>
                <th className="px-4 py-2.5 text-right">EOD Value</th>
                <th className="px-4 py-2.5 text-right">Weight %</th>
                <th className="px-4 py-2.5">Monitoring / Gate</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {markedHoldings.map((h) => {
                const dec = decisions[h.instrument_id];
                const eodCloseNum = parseDecimal(h.eod_reference_close_tnd.value);
                const eodVal = eodCloseNum !== null ? (eodCloseNum * h.quantity).toFixed(3) : null;
                const weightPv = dec?.risk?.position_weight;
                const breach = dec?.risk?.concentration_breach;

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
                      {formatProvenanceNumber(h.eod_reference_close_tnd, { withUnit: false })}
                    </td>
                    <td className="mono-num px-4 py-3 text-right font-semibold text-[#0F172A]">
                      {eodVal ? formatTnd(eodVal, { withUnit: false }) : "Unavailable"}
                    </td>
                    <td
                      className={`mono-num px-4 py-3 text-right font-semibold ${
                        breach ? "text-[#92400E]" : "text-[#0F172A]"
                      }`}
                    >
                      {weightPv ? formatProvenanceNumber(weightPv) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-1">
                        {dec ? (
                          <>
                            <MonitoringBadge state={dec.monitoring_state} />
                            <ExecutionGateBadge state={dec.execution_state} />
                          </>
                        ) : (
                          <ProvenanceBadge status="UNAVAILABLE" label="NO DECISION" />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <Link
                          href={withModeHref(`/positions/${encodeURIComponent(h.instrument_id)}`)}
                          className="font-medium text-[#0F766E] hover:underline"
                        >
                          Manage
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

        {/* Mobile Stacked Cards (< 768px) */}
        <div className="divide-y divide-[#E2E8F0] md:hidden">
          {markedHoldings.map((h) => {
            const dec = decisions[h.instrument_id];
            const eodCloseNum = parseDecimal(h.eod_reference_close_tnd.value);
            const eodVal = eodCloseNum !== null ? (eodCloseNum * h.quantity).toFixed(3) : null;
            const weightPv = dec?.risk?.position_weight;
            const breach = dec?.risk?.concentration_breach;

            return (
              <div key={h.instrument_id} className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2 border-b border-[#E2E8F0] pb-2">
                  <div>
                    <div className="font-semibold text-[#0F172A]">{h.symbol}</div>
                    <div className="font-mono text-[11.5px] text-[#64748B]">
                      {h.isin ?? h.instrument_id}
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
                  <div className="text-[#64748B]">Quantity</div>
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
                  <div className="text-[#64748B]">EOD Value</div>
                  <div className="mono-num text-right font-semibold text-[#0F172A]">
                    {eodVal ? formatTnd(eodVal) : "Unavailable"}
                  </div>
                  <div className="text-[#64748B]">Weight %</div>
                  <div
                    className={`mono-num text-right font-semibold ${
                      breach ? "text-[#92400E]" : "text-[#0F172A]"
                    }`}
                  >
                    {weightPv ? formatProvenanceNumber(weightPv) : "—"}
                  </div>
                </div>
                <div className="flex items-center justify-end gap-4 pt-1 text-[12.5px] font-medium">
                  <Link
                    href={withModeHref(`/positions/${encodeURIComponent(h.instrument_id)}`)}
                    className="text-[#0F766E] hover:underline"
                  >
                    Manage Position &rarr;
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

      <p className="border-t border-[#E2E8F0] pt-3 text-[12px] text-[#64748B]">
        <strong>Canonical Dataset Provenance:</strong> {overview.equity_instruments} equities (
        {overview.challenge_members} Challenge members) across {overview.session_count} sessions
        &middot; {formatInteger(overview.rejected_non_equity_count)} non-equity rows excluded
        &middot; <code>published_at_present_count = {overview.published_at_present_count}</code>{" "}
        &middot; <code>automatic_submission_enabled = {String(overview.automatic_submission_enabled)}</code>
      </p>
    </div>
  );
}
