"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type Horizon,
  type ResearchEvidence,
  type StockAssessment,
  type StockBarsResponse,
} from "@/lib/v2-api";
import {
  formatInteger,
  formatProvenanceNumber,
  formatTimestamp,
  HORIZON_LABELS,
} from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ProvenanceNumber } from "@/components/ProvenanceNumber";
import { ExecutionGateBadge, StockStateBadge } from "@/components/StateBadges";
import { EodPriceChart } from "@/components/EodPriceChart";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

const HORIZONS: Horizon[] = ["1_2", "3_5", "5_10", "10_20", "20_60"];

function EvidenceCard({
  title,
  items,
  tone,
}: {
  title: string;
  items: ResearchEvidence[];
  tone: "supporting" | "contradicting" | "missing";
}) {
  const borderClass =
    tone === "supporting"
      ? "border-l-[#0F766E]"
      : tone === "contradicting"
        ? "border-l-[#D97706]"
        : "border-l-[#94A3B8]";

  return (
    <div className="space-y-2">
      <div className="text-[12px] font-semibold uppercase tracking-wide text-[#64748B]">
        {title} ({items.length})
      </div>
      {items.length === 0 ? (
        <div className="rounded-md border border-[#E2E8F0] bg-[#F8F9FA] p-2.5 text-[12px] text-[#64748B]">
          None recorded for this cutoff.
        </div>
      ) : (
        items.map((item) => (
          <div
            key={item.evidence_id}
            className={`rounded-md border border-[#E2E8F0] border-l-[3px] ${borderClass} bg-[#F8F9FA] p-2.5 text-[12.5px]`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-[#0F172A]">
                {item.layer} &middot; {item.summary}
              </span>
              <ProvenanceBadge status={item.provenance_status} />
            </div>
            {item.metric_value ? (
              <div className="mt-1">
                <ProvenanceNumber
                  pv={item.metric_value}
                  signed={item.metric_value.unit === "RATIO"}
                  showBadge={false}
                  showReason
                />
              </div>
            ) : null}
          </div>
        ))
      )}
    </div>
  );
}

export default function StockResearchDetailPage() {
  const params = useParams<{ instrumentId: string }>();
  const instrumentId = decodeURIComponent(params.instrumentId ?? "EURO-CYCLES");
  const { mode, withModeHref } = useMode();

  const [horizon, setHorizon] = useState<Horizon>("5_10");
  const [assessment, setAssessment] = useState<StockAssessment | null>(null);
  const [barsData, setBarsData] = useState<StockBarsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [stockRes, barsRes] = await Promise.all([
        v2Api.getStock(instrumentId, mode, horizon),
        v2Api.getStockBars(instrumentId, mode, 60),
      ]);
      setAssessment(stockRes);
      setBarsData(barsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load stock assessment");
    } finally {
      setLoading(false);
    }
  }, [instrumentId, mode, horizon]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <LoadingSkeleton rows={6} />;
  if (error || !assessment || !barsData) {
    return <ApiErrorBanner error={error ?? "Stock data unavailable"} onRetry={loadData} />;
  }

  const ins = assessment.instrument;
  const bars = barsData.bars;
  const latestBar = bars.length > 0 ? bars[bars.length - 1] : null;
  const prov = latestBar?.provenance;

  const provenanceRows: Array<[string, string]> = prov
    ? [
        ["event_time", prov.event_time ?? "null"],
        ["exchange_session", prov.exchange_session],
        ["source_publication_time", prov.source_publication_time ?? "null (UNAVAILABLE)"],
        ["first_observed_at", prov.first_observed_at ? formatTimestamp(prov.first_observed_at) : "null"],
        ["retrieved_at", prov.retrieved_at ? formatTimestamp(prov.retrieved_at) : "null"],
        ["ingested_at", formatTimestamp(prov.ingested_at)],
        ["validated_at", formatTimestamp(prov.validated_at)],
        ["source_id", prov.source_id],
        ["source_hash", prov.source_hash],
        ["data_quality_status", prov.data_quality_status],
      ]
    : [];

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
              GET /api/v2/stocks/{ins.instrument_id}?mode={mode}&amp;horizon={horizon}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
                {ins.symbol}
              </h1>
              <span className="rounded border border-[#E2E8F0] bg-[#F8F9FA] px-2 py-0.5 font-mono text-[12px] text-[#334155]">
                {ins.isin}
              </span>
              <span className="rounded border border-[#E2E8F0] bg-[#F1F5F9] px-2 py-0.5 text-[11.5px] font-medium text-[#475569]">
                {ins.market_mode}
              </span>
              <span
                className={`rounded border px-2 py-0.5 text-[11px] font-semibold uppercase ${
                  ins.challenge_member
                    ? "border-[#99F6E4] bg-[#F0FDFA] text-[#0F766E]"
                    : "border-[#FECACA] bg-[#FEF2F2] text-[#991B1B]"
                }`}
              >
                {ins.challenge_member ? "Challenge Member" : "Non-Challenge (Restricted)"}
              </span>
            </div>
            <div className="mt-1 text-[12.5px] text-[#64748B]">
              Sector: <strong className="text-[#334155]">{ins.sector ?? "Unclassified"}</strong>{" "}
              &middot; Horizon Support:{" "}
              <code className="font-mono text-[#0F172A]">{assessment.horizon_support_status}</code>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <StockStateBadge state={assessment.state} />
            <ExecutionGateBadge
              state={
                assessment.execution_feasibility.can_plan_manual_order
                  ? "ELIGIBLE_MANUAL_ONLY"
                  : "EXECUTION_BLOCKED"
              }
            />
            <Link
              href={withModeHref(
                `/decisions?instrument=${encodeURIComponent(ins.instrument_id)}`,
              )}
              className="inline-flex min-h-[36px] items-center rounded-md bg-[#0F766E] px-3 py-1.5 text-[12.5px] font-medium text-white hover:bg-[#115E59]"
            >
              Simulate Manual BUY &rarr;
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 border-t border-[#E2E8F0] pt-3 sm:grid-cols-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Historical EOD Close ({assessment.exchange_session ?? "—"})
            </div>
            <div className="mt-1">
              <ProvenanceNumber pv={assessment.historical_eod_close_tnd} />
            </div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Current Executable Quote
            </div>
            <div className="mt-1">
              <ProvenanceNumber pv={assessment.current_executable_quote_tnd} showReason />
            </div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Liquidity Staging (10% ADV)
            </div>
            <div className="mt-1 text-[13px] font-semibold text-[#0F172A]">
              {assessment.liquidity_status} &middot;{" "}
              <span className="mono-num">
                {assessment.execution_feasibility.liquidity_cap_shares_10pct !== null
                  ? `${formatInteger(assessment.execution_feasibility.liquidity_cap_shares_10pct)} sh/session`
                  : "Unavailable"}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 border-t border-[#E2E8F0] pt-3">
          <span className="mr-1 text-[11.5px] font-semibold uppercase tracking-wide text-[#64748B]">
            Horizon:
          </span>
          {HORIZONS.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHorizon(h)}
              className={`min-h-[32px] rounded border px-2.5 py-1 text-[12px] font-medium ${
                horizon === h
                  ? "border-[#99F6E4] bg-[#F0FDFA] font-semibold text-[#0F766E]"
                  : "border-[#E2E8F0] bg-white text-[#334155] hover:bg-[#F1F5F9]"
              }`}
            >
              {HORIZON_LABELS[h]}
            </button>
          ))}
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="min-w-0 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 lg:col-span-7">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                EOD Price &amp; Volume Trajectory (Last {bars.length} Sessions)
              </h2>
              <div className="text-[12px] text-[#64748B]">
                Zero-volume / untraded sessions are explicitly flagged in amber.
              </div>
            </div>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "OBSERVED"}
            />
          </div>
          <EodPriceChart bars={bars} />
        </div>

        <div className="min-w-0 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 lg:col-span-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Research Hypothesis &amp; Balance
              </h2>
              <div className="font-mono text-[12px] text-[#0F766E]">{assessment.hypothesis}</div>
            </div>
            <span className="text-[11.5px] text-[#64748B]">{assessment.model_version}</span>
          </div>

          <div className="max-h-[320px] space-y-3 overflow-y-auto pr-1">
            <EvidenceCard
              title="Supporting Evidence"
              items={assessment.supporting_evidence}
              tone="supporting"
            />
            <EvidenceCard
              title="Contradicting Evidence"
              items={assessment.contradicting_evidence}
              tone="contradicting"
            />
            <EvidenceCard
              title="Missing Evidence"
              items={assessment.missing_evidence}
              tone="missing"
            />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              L1 &amp; L2 · Technical &amp; Liquidity State
            </h2>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"}
            />
          </div>
          <div className="divide-y divide-[#E2E8F0] text-[13px]">
            {[
              ["5-Session Return", assessment.technical_state.ret_5s],
              ["20-Session Return", assessment.technical_state.ret_20s],
              ["60-Session Return", assessment.technical_state.ret_60s],
              ["20-Session Volatility", assessment.technical_state.vol_20s],
              ["Bounded Risk Ratio V2", assessment.technical_state.bounded_risk_ratio_v2],
              ["20s Median Turnover", assessment.technical_state.adv_20s_tnd],
              ["10% ADV Share Cap", assessment.technical_state.ten_pct_adv_shares],
              ["Zero-Volume Sessions (20s)", assessment.technical_state.zero_vol_pct_20s],
              ["RS vs Challenge Median", assessment.technical_state.rs_vs_challenge_20s],
              ["Challenge Breadth", assessment.technical_state.challenge_breadth_pct],
            ].map(([label, pv]) => (
              <div key={String(label)} className="flex items-center justify-between gap-2 py-2">
                <span className="text-[#334155]">{String(label)}</span>
                <ProvenanceNumber
                  pv={typeof pv === "object" ? pv : null}
                  signed={String(label).includes("Return") || String(label).includes("RS")}
                  showBadge={false}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                L3 · Fundamental Disclosures
              </h2>
              <ProvenanceBadge status={assessment.fundamental_state.status} />
            </div>
            <div className="rounded-md border border-[#CBD5E1] bg-[#F1F5F9] p-3 text-[12.5px] text-[#475569]">
              <ProvenanceNumber pv={assessment.fundamental_state} showReason />
            </div>
          </div>

          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-2">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              L4–L8 · Events, Portfolio Suitability &amp; Execution Gate
            </h2>
            <div className="divide-y divide-[#E2E8F0] text-[12.5px]">
              <div className="flex justify-between gap-2 py-2">
                <span className="text-[#64748B]">Events (L4)</span>
                <span className="text-right text-[#334155] break-words">
                  {assessment.event_context.join("; ")}
                </span>
              </div>
              <div className="flex justify-between gap-2 py-2">
                <span className="text-[#64748B]">Issuer Weight Fit (L7)</span>
                <span className="font-mono text-[#0F172A]">
                  {assessment.portfolio_suitability.issuer ?? "UNAVAILABLE"}
                </span>
              </div>
              <div className="flex justify-between gap-2 py-2">
                <span className="text-[#64748B]">Sector Fit (L7)</span>
                <span className="font-mono text-[#0F172A]">
                  {assessment.portfolio_suitability.sector ?? "UNAVAILABLE"}
                </span>
              </div>
              <div className="flex justify-between gap-2 py-2">
                <span className="text-[#64748B]">Execution Blockers (L8)</span>
                <span className="text-right font-mono text-[#991B1B] break-words">
                  {assessment.execution_feasibility.blockers.join(", ") || "None"}
                </span>
              </div>
              <div className="flex justify-between gap-2 py-2">
                <span className="text-[#64748B]">Next Review Trigger (L10)</span>
                <span className="text-right text-[#334155] break-words">
                  {assessment.next_review_condition}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              L9 · 10-Field PriceProvenance Audit Register (Latest Bar)
            </h2>
            <div className="text-[12px] text-[#64748B]">
              Point-in-time availability timestamps and source SHA-256 integrity fields.
            </div>
          </div>
          {prov ? <ProvenanceBadge status="OBSERVED" label={prov.data_quality_status} /> : null}
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {provenanceRows.map(([field, val]) => (
            <div
              key={field}
              className="flex flex-col gap-0.5 rounded-md border border-[#E2E8F0] bg-[#F8F9FA] px-3 py-2"
            >
              <span className="font-mono text-[11px] font-semibold text-[#64748B]">{field}</span>
              <span className="font-mono text-[12px] text-[#0F172A] break-all">{val}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
