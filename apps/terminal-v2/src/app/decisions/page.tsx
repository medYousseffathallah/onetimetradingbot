"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type ManualTradeScenario,
  type OpportunityCandidate,
  type StockAssessment,
} from "@/lib/v2-api";
import { formatProvenanceNumber, toDecimalInputString } from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ExecutionGateBadge, StockStateBadge } from "@/components/StateBadges";
import { ScenarioResultCard } from "@/components/ScenarioResultCard";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

export default function InvestmentDecisionWorkspacePage() {
  const { mode } = useMode();
  const searchParams = useSearchParams();
  const initialInstrument = searchParams.get("instrument") || "EURO-CYCLES";

  const [candidates, setCandidates] = useState<OpportunityCandidate[]>([]);
  const [selectedId, setSelectedId] = useState<string>(initialInstrument);
  const [assessment, setAssessment] = useState<StockAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Thesis draft state (local research note only, never auto-submitted)
  const [thesisText, setThesisText] = useState(
    "Research note: evaluate liquidity capacity and 10% single-stock weight headroom before manual entry.",
  );
  const [horizonSessions, setHorizonSessions] = useState<string>("10");
  const [invalidationText, setInvalidationText] = useState(
    "Close below 20-session support OR single-stock weight exceeds 10.00% OR unverified rule conflict.",
  );
  const [thesisSavedStamp, setThesisSavedStamp] = useState<string | null>(null);

  // Buy Scenario state
  const [quantity, setQuantity] = useState<string>("50");
  const [limitPrice, setLimitPrice] = useState<string>("10.160");
  const [scenarioResult, setScenarioResult] = useState<ManualTradeScenario | null>(null);
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [scenarioError, setScenarioError] = useState<string | null>(null);

  const loadUniverseAndStock = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const disc = await v2Api.getDiscovery(mode, "FULL_BVMT_RESEARCH", "5_10");
      setCandidates(disc.candidates);
      const targetId =
        disc.candidates.find(
          (c) =>
            c.assessment.instrument.instrument_id.toUpperCase() === selectedId.toUpperCase() ||
            c.assessment.instrument.symbol.toUpperCase() === selectedId.toUpperCase(),
        )?.assessment.instrument.instrument_id ??
        disc.candidates[0]?.assessment.instrument.instrument_id ??
        selectedId;
      setSelectedId(targetId);
      const stock = await v2Api.getStock(targetId, mode, "5_10");
      setAssessment(stock);
      setLimitPrice(toDecimalInputString(stock.historical_eod_close_tnd.value, "10.000"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load decision workspace");
    } finally {
      setLoading(false);
    }
  }, [mode, selectedId]);

  useEffect(() => {
    void loadUniverseAndStock();
  }, [loadUniverseAndStock]);

  const handleInstrumentChange = async (nextId: string) => {
    setSelectedId(nextId);
    setScenarioResult(null);
    setScenarioError(null);
    try {
      const stock = await v2Api.getStock(nextId, mode, "5_10");
      setAssessment(stock);
      setLimitPrice(toDecimalInputString(stock.historical_eod_close_tnd.value, "10.000"));
    } catch (err) {
      setScenarioError(err instanceof Error ? err.message : "Failed to load instrument");
    }
  };

  const handleRunBuyScenario = async (e: React.FormEvent) => {
    e.preventDefault();
    setScenarioError(null);
    const qtyNum = Number.parseInt(quantity, 10);
    if (!Number.isInteger(qtyNum) || qtyNum <= 0) {
      setScenarioError("Quantity must be a positive integer.");
      return;
    }
    const priceNum = Number(limitPrice);
    if (!Number.isFinite(priceNum) || priceNum <= 0) {
      setScenarioError("Limit price must be a positive decimal TND value (e.g. 10.160).");
      return;
    }
    setScenarioBusy(true);
    try {
      const res = await v2Api.postBuyScenario({
        instrument_id: selectedId,
        quantity: qtyNum,
        limit_price_tnd: priceNum.toFixed(3),
        mode,
      });
      setScenarioResult(res);
    } catch (err) {
      setScenarioError(err instanceof Error ? err.message : "Buy scenario request failed");
    } finally {
      setScenarioBusy(false);
    }
  };

  if (loading) return <LoadingSkeleton rows={5} />;
  if (error || !assessment) {
    return <ApiErrorBanner error={error ?? "Missing decision workspace data"} onRetry={loadUniverseAndStock} />;
  }

  const orderedLayers = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
            POST /api/v2/decisions/buy-scenario &middot; mode={mode}
          </div>
          <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
            Investment Decision Workspace
          </h1>
          <p className="mt-0.5 text-[13.5px] text-[#334155]">
            Document structured research theses, review L1&ndash;L10 gates, and simulate manual
            BUY impact without submitting orders.
          </p>
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
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="space-y-4 min-w-0 lg:col-span-7">
          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
              <div>
                <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                  1. Structured InvestmentThesis Note
                </h2>
                <div className="text-[12px] text-[#64748B]">
                  Human review record for{" "}
                  <strong className="text-[#0F172A]">{assessment.instrument.symbol}</strong> (
                  {assessment.instrument.isin})
                </div>
              </div>
              <ProvenanceBadge
                status={thesisSavedStamp ? "UNVERIFIED" : "UNAVAILABLE"}
                label={thesisSavedStamp ? "HUMAN_REVIEW_NOTE" : "LOCAL DRAFT"}
              />
            </div>

            <div className="space-y-3">
              <div>
                <label
                  htmlFor="thesis-text"
                  className="mb-1 block text-[12px] font-semibold text-[#334155]"
                >
                  Thesis Statement
                </label>
                <textarea
                  id="thesis-text"
                  rows={3}
                  value={thesisText}
                  onChange={(e) => setThesisText(e.target.value)}
                  className="w-full rounded-md border border-[#CBD5E1] bg-white px-3 py-2 text-[13px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label
                    htmlFor="thesis-horizon"
                    className="mb-1 block text-[12px] font-semibold text-[#334155]"
                  >
                    Horizon (Sessions)
                  </label>
                  <input
                    id="thesis-horizon"
                    type="number"
                    min={1}
                    max={60}
                    value={horizonSessions}
                    onChange={(e) => setHorizonSessions(e.target.value)}
                    className="mono-num min-h-[38px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label
                    htmlFor="thesis-invalidation"
                    className="mb-1 block text-[12px] font-semibold text-[#334155]"
                  >
                    Invalidation Conditions
                  </label>
                  <input
                    id="thesis-invalidation"
                    type="text"
                    value={invalidationText}
                    onChange={(e) => setInvalidationText(e.target.value)}
                    className="min-h-[38px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <span className="text-[11.5px] text-[#64748B]">
                  {thesisSavedStamp
                    ? `Draft stamped at ${thesisSavedStamp} (browser session only)`
                    : "Local UI draft only — does not mutate canonical competition ledger."}
                </span>
                <button
                  type="button"
                  onClick={() => setThesisSavedStamp(new Date().toISOString().slice(11, 19) + " UTC")}
                  className="min-h-[36px] rounded-md border border-[#CBD5E1] bg-white px-3 py-1.5 text-[12.5px] font-medium text-[#0F172A] hover:bg-[#F1F5F9]"
                >
                  Stamp Research Note
                </button>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
              <div>
                <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                  2. L1&ndash;L10 Pre-Trade Evidence Checklist
                </h2>
                <div className="text-[12px] text-[#64748B]">
                  automatic_submission_enabled:{" "}
                  <code className="font-mono">
                    {String(assessment.execution_feasibility.automatic_submission_enabled)}
                  </code>
                </div>
              </div>
              <span className="mono-num text-[12px] text-[#64748B]">
                10% ADV Cap:{" "}
                <strong>
                  {assessment.execution_feasibility.liquidity_cap_shares_10pct ?? "Unavailable"} sh
                </strong>
              </span>
            </div>

            <div className="divide-y divide-[#E2E8F0]">
              {orderedLayers.map((layerKey) => {
                const items = assessment.layers[layerKey] ?? [];
                const hasMissing = items.some((i) => i.polarity === "MISSING");
                const hasContra = items.some((i) => i.polarity === "CONTRADICTING");
                const badgeStatus = hasContra
                  ? "UNVERIFIED"
                  : hasMissing
                    ? "UNAVAILABLE"
                    : "CALCULATED";

                return (
                  <div
                    key={layerKey}
                    className="flex flex-col gap-1.5 py-2.5 sm:flex-row sm:items-start sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="text-[12.5px] font-semibold text-[#0F172A]">
                        {layerKey}
                      </div>
                      <div className="text-[12px] text-[#475569] break-words">
                        {items.length > 0
                          ? items.map((i) => i.summary).join(" · ")
                          : "No layer entries"}
                      </div>
                    </div>
                    <ProvenanceBadge
                      status={badgeStatus}
                      label={hasContra ? "REVIEW" : hasMissing ? "MISSING" : "PASS"}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="min-w-0 lg:col-span-5">
          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
              <div>
                <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                  Manual BUY Scenario Simulator
                </h2>
                <div className="text-[12px] text-[#64748B]">
                  0.50% fee, 10% cap, 10% ADV &amp; Challenge checks
                </div>
              </div>
              <ProvenanceBadge status="SIMULATED" />
            </div>

            <form onSubmit={handleRunBuyScenario} className="space-y-3">
              <div>
                <label
                  htmlFor="buy-instrument"
                  className="mb-1 block text-[12px] font-semibold text-[#334155]"
                >
                  Instrument
                </label>
                <select
                  id="buy-instrument"
                  value={selectedId}
                  onChange={(e) => void handleInstrumentChange(e.target.value)}
                  className="min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
                >
                  {candidates.map((c) => {
                    const ins = c.assessment.instrument;
                    return (
                      <option key={ins.instrument_id} value={ins.instrument_id}>
                        {ins.symbol} ({ins.instrument_id}) &mdash;{" "}
                        {c.challenge_eligible ? "Challenge" : "Restricted"}
                      </option>
                    );
                  })}
                </select>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="buy-qty"
                    className="mb-1 block text-[12px] font-semibold text-[#334155]"
                  >
                    Quantity (Shares)
                  </label>
                  <input
                    id="buy-qty"
                    type="number"
                    min={1}
                    step={1}
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="mono-num min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13.5px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
                  />
                </div>
                <div>
                  <label
                    htmlFor="buy-price"
                    className="mb-1 block text-[12px] font-semibold text-[#334155]"
                  >
                    Limit Price (TND)
                  </label>
                  <input
                    id="buy-price"
                    type="text"
                    inputMode="decimal"
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(e.target.value)}
                    className="mono-num min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13.5px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#E2E8F0] bg-[#F8F9FA] px-3 py-2 text-[12px]">
                <span className="text-[#64748B]">Reference EOD Close</span>
                <span className="mono-num font-semibold text-[#0F172A]">
                  {formatProvenanceNumber(assessment.historical_eod_close_tnd)}
                </span>
              </div>

              {!assessment.instrument.challenge_member ? (
                <div className="rounded-md border border-[#FECACA] bg-[#FEF2F2] p-2.5 text-[12px] text-[#991B1B]">
                  <strong>RESTRICTED_CHALLENGE:</strong> Non-Challenge instrument &mdash; dry-run
                  BUY simulation is blocked at the pre-trade gate.
                </div>
              ) : null}

              {scenarioError ? (
                <div className="rounded-md border border-[#FECACA] bg-[#FEF2F2] p-2.5 text-[12px] text-[#991B1B]">
                  {scenarioError}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={scenarioBusy || !assessment.instrument.challenge_member}
                className="min-h-[42px] w-full rounded-md bg-[#0F766E] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#115E59] disabled:opacity-60"
              >
                {!assessment.instrument.challenge_member
                  ? "Blocked: Outside Challenge Universe"
                  : scenarioBusy
                    ? "Simulating BUY Scenario..."
                    : "Run Dry-Run BUY Scenario"}
              </button>
            </form>

            {scenarioResult ? <ScenarioResultCard scenario={scenarioResult} /> : null}
          </div>
        </div>
      </section>
    </div>
  );
}
