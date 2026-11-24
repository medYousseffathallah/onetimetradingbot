"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMode } from "@/components/mode-context";
import {
  v2Api,
  type Holding,
  type ManualTradeScenario,
  type PortfolioResponse,
  type PositionDecision,
} from "@/lib/v2-api";
import {
  formatInteger,
  formatProvenanceNumber,
  formatTnd,
  parseDecimal,
  toDecimalInputString,
} from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ProvenanceNumber } from "@/components/ProvenanceNumber";
import { ExecutionGateBadge, MonitoringBadge } from "@/components/StateBadges";
import { ConflictBanner } from "@/components/ConflictBanner";
import { ScenarioResultCard } from "@/components/ScenarioResultCard";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

export default function PositionDetailPage() {
  const params = useParams<{ instrumentId: string }>();
  const instrumentId = decodeURIComponent(params.instrumentId ?? "EURO-CYCLES");
  const { mode, withModeHref } = useMode();

  const [decision, setDecision] = useState<PositionDecision | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Protection scenario form
  const [protQty, setProtQty] = useState<string>("50");
  const [protPrice, setProtPrice] = useState<string>("9.650");
  const [protResult, setProtResult] = useState<ManualTradeScenario | null>(null);
  const [protBusy, setProtBusy] = useState(false);
  const [protError, setProtError] = useState<string | null>(null);

  // Partial sale simulator form
  const [sellQty, setSellQty] = useState<string>("50");
  const [sellPrice, setSellPrice] = useState<string>("10.160");
  const [sellResult, setSellResult] = useState<ManualTradeScenario | null>(null);
  const [sellBusy, setSellBusy] = useState(false);
  const [sellError, setSellError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dec, pf] = await Promise.all([
        v2Api.getPosition(instrumentId, mode),
        v2Api.getPortfolio(mode),
      ]);
      setDecision(dec);
      setPortfolio(pf);

      const holdings =
        pf.snapshots.eod_mark_portfolio?.holdings ?? pf.current.holdings;
      const holding = holdings.find((h) => h.instrument_id === dec.instrument_id);
      if (holding) {
        const defaultQty = Math.min(50, Math.max(1, Math.floor(holding.quantity * 0.25)));
        setProtQty(String(holding.quantity));
        setSellQty(String(defaultQty));
        const eodNum = parseDecimal(holding.eod_reference_close_tnd.value);
        if (eodNum && eodNum > 0) {
          setSellPrice(eodNum.toFixed(3));
          setProtPrice((eodNum * 0.95).toFixed(3));
        } else {
          const fallback = toDecimalInputString(holding.displayed_price_tnd.value, "10.000");
          setSellPrice(fallback);
          setProtPrice(fallback);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load position decision");
    } finally {
      setLoading(false);
    }
  }, [instrumentId, mode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const submitScenario = async (
    kind: "PROTECTION" | "SELL",
    qtyRaw: string,
    priceRaw: string,
  ) => {
    const qtyNum = Number.parseInt(qtyRaw, 10);
    const priceNum = Number(priceRaw);
    if (!Number.isInteger(qtyNum) || qtyNum <= 0) {
      const msg = "Quantity must be a positive integer.";
      if (kind === "PROTECTION") setProtError(msg);
      else setSellError(msg);
      return;
    }
    if (!Number.isFinite(priceNum) || priceNum <= 0) {
      const msg = "Limit/stress price must be a positive decimal TND value.";
      if (kind === "PROTECTION") setProtError(msg);
      else setSellError(msg);
      return;
    }

    if (kind === "PROTECTION") {
      setProtBusy(true);
      setProtError(null);
    } else {
      setSellBusy(true);
      setSellError(null);
    }

    try {
      const payload = {
        instrument_id: decision?.instrument_id ?? instrumentId,
        quantity: qtyNum,
        limit_price_tnd: priceNum.toFixed(3),
        mode,
      };
      const res =
        kind === "PROTECTION"
          ? await v2Api.postProtectionScenario(payload)
          : await v2Api.postSellScenario(payload);
      if (kind === "PROTECTION") setProtResult(res);
      else setSellResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Scenario failed";
      if (kind === "PROTECTION") setProtError(msg);
      else setSellError(msg);
    } finally {
      if (kind === "PROTECTION") setProtBusy(false);
      else setSellBusy(false);
    }
  };

  if (loading) return <LoadingSkeleton rows={5} />;
  if (error || !decision || !portfolio) {
    return <ApiErrorBanner error={error ?? "Position unavailable"} onRetry={loadData} />;
  }

  const holdings =
    portfolio.snapshots.eod_mark_portfolio?.holdings ?? portfolio.current.holdings;
  const holding: Holding | undefined = holdings.find(
    (h) => h.instrument_id === decision.instrument_id,
  );
  const eodCloseNum = parseDecimal(holding?.eod_reference_close_tnd.value);
  const markedValue =
    holding && eodCloseNum !== null
      ? (eodCloseNum * holding.quantity).toFixed(3)
      : null;

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
              GET /api/v2/positions/{decision.instrument_id}?mode={mode}
            </div>
            <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
              {holding?.symbol ?? decision.instrument_id}
            </h1>
            <div className="mt-1 text-[13px] text-[#334155]">
              {holding ? (
                <>
                  <strong className="mono-num">{formatInteger(holding.quantity)}</strong> sh @{" "}
                  <span className="mono-num">
                    {formatProvenanceNumber(holding.displayed_avg_cost_tnd)}
                  </span>{" "}
                  avg &rarr; EOD{" "}
                  <span className="mono-num">
                    {formatProvenanceNumber(holding.eod_reference_close_tnd)}
                  </span>{" "}
                  ={" "}
                  <strong className="mono-num">
                    {markedValue ? formatTnd(markedValue) : "Unavailable"}
                  </strong>
                </>
              ) : (
                "Position details"
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <MonitoringBadge state={decision.monitoring_state} />
            <ExecutionGateBadge state={decision.execution_state} />
            <Link
              href={withModeHref(`/stocks/${encodeURIComponent(decision.instrument_id)}`)}
              className="inline-flex min-h-[36px] items-center rounded-md border border-[#CBD5E1] bg-white px-3 py-1 text-[12.5px] font-medium text-[#0F172A] hover:bg-[#F1F5F9]"
            >
              Stock Research &rarr;
            </Link>
          </div>
        </div>
      </div>

      <ConflictBanner
        accountStateConflict={portfolio.account_state_conflict}
        confirmed={portfolio.snapshots.confirmed_ledger}
        latestCapture={portfolio.snapshots.latest_dom_capture}
      />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3 lg:col-span-7">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Decoupled Monitoring Rationale &amp; Execution Blockers
            </h2>
            <div className="flex gap-1.5">
              <MonitoringBadge state={decision.monitoring_state} />
              <ExecutionGateBadge state={decision.execution_state} />
            </div>
          </div>

          <div className="rounded-md border border-[#E2E8F0] bg-[#F8F9FA] p-3 text-[13px] text-[#0F172A]">
            <strong>Monitoring Assessment:</strong> {decision.explanation}
          </div>

          <div>
            <div className="text-[11.5px] font-semibold uppercase tracking-wide text-[#64748B]">
              Execution Blockers ({decision.blockers.length})
            </div>
            {decision.blockers.length === 0 ? (
              <p className="mt-1 text-[12.5px] text-[#065F46]">
                No deterministic execution blockers reported. Manual portal entry only.
              </p>
            ) : (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {decision.blockers.map((b) => (
                  <code
                    key={b}
                    className="rounded border border-[#FECACA] bg-[#FEF2F2] px-2 py-0.5 text-[11.5px] font-semibold text-[#991B1B] break-all"
                  >
                    {b}
                  </code>
                ))}
              </div>
            )}
          </div>

          <div className="divide-y divide-[#E2E8F0] text-[12.5px]">
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#64748B]">Next Review Trigger</span>
              <span className="text-right text-[#334155] break-words">
                {decision.next_review_trigger}
              </span>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#64748B]">Recorded Thesis</span>
              <span className="text-right text-[#334155]">
                {decision.thesis?.thesis ?? "No human thesis recorded"} (
                <code className="font-mono">{decision.thesis?.origin ?? "UNVERIFIED_NONE"}</code>)
              </span>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#64748B]">Realized P&amp;L</span>
              <ProvenanceNumber pv={decision.realized_pnl_tnd} signed showReason />
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#64748B]">Unrealized P&amp;L</span>
              <ProvenanceNumber pv={decision.unrealized_pnl_tnd} signed showReason />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-2.5 lg:col-span-5">
          <div className="flex items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">Risk &amp; Exit Budget</h2>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "CALCULATED"}
            />
          </div>
          {decision.risk ? (
            <div className="divide-y divide-[#E2E8F0] text-[13px]">
              <div className="flex items-center justify-between gap-2 py-2">
                <span className="text-[#334155]">Position Weight</span>
                <ProvenanceNumber pv={decision.risk.position_weight} showBadge={false} />
              </div>
              <div className="flex items-center justify-between gap-2 py-2">
                <span className="text-[#334155]">Max Single-Stock Cap</span>
                <ProvenanceNumber pv={decision.risk.max_single_stock_weight} showBadge={false} />
              </div>
              <div className="flex items-center justify-between gap-2 py-2">
                <span className="text-[#334155]">Concentration Breach</span>
                <span
                  className={`font-semibold ${
                    decision.risk.concentration_breach ? "text-[#92400E]" : "text-[#065F46]"
                  }`}
                >
                  {decision.risk.concentration_breach === null
                    ? "Unavailable"
                    : decision.risk.concentration_breach
                      ? "YES (> 10.00%)"
                      : "Within Cap"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 py-2">
                <span className="text-[#334155]">Exit Horizon (10% ADV)</span>
                <ProvenanceNumber pv={decision.risk.liquidity_days_to_exit} showBadge={false} />
              </div>
              <div className="flex items-center justify-between gap-2 py-2">
                <span className="text-[#334155]">20-Session Volatility</span>
                <ProvenanceNumber pv={decision.risk.volatility_20s} showBadge={false} />
              </div>
              <div className="flex items-center justify-between gap-2 py-2">
                <span className="text-[#334155]">5% Downside Stress</span>
                <ProvenanceNumber pv={decision.risk.downside_stress_tnd} />
              </div>
            </div>
          ) : (
            <p className="text-[12.5px] text-[#64748B]">Risk assessment unavailable.</p>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Downside Protection Scenario */}
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Downside Protection Scenario
              </h2>
              <div className="text-[12px] text-[#64748B]">
                POST /api/v2/positions/protection-scenario
              </div>
            </div>
            <ProvenanceBadge status="SIMULATED" />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="prot-qty"
                className="mb-1 block text-[12px] font-semibold text-[#334155]"
              >
                Shares Covered
              </label>
              <input
                id="prot-qty"
                type="number"
                min={1}
                value={protQty}
                onChange={(e) => setProtQty(e.target.value)}
                className="mono-num min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13.5px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
              />
            </div>
            <div>
              <label
                htmlFor="prot-price"
                className="mb-1 block text-[12px] font-semibold text-[#334155]"
              >
                Stop / Stress Price (TND)
              </label>
              <input
                id="prot-price"
                type="text"
                inputMode="decimal"
                value={protPrice}
                onChange={(e) => setProtPrice(e.target.value)}
                className="mono-num min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13.5px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
              />
            </div>
          </div>

          {eodCloseNum && eodCloseNum > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {[0.95, 0.92, 0.9].map((mult) => (
                <button
                  key={mult}
                  type="button"
                  onClick={() => setProtPrice((eodCloseNum * mult).toFixed(3))}
                  className="rounded border border-[#CBD5E1] bg-[#F1F5F9] px-2.5 py-1 text-[11.5px] font-medium text-[#334155] hover:bg-[#F0FDFA] hover:text-[#0F766E]"
                >
                  -{Math.round((1 - mult) * 100)}% Stress ({(eodCloseNum * mult).toFixed(3)})
                </button>
              ))}
            </div>
          ) : null}

          {protError ? (
            <div className="rounded-md border border-[#FECACA] bg-[#FEF2F2] p-2.5 text-[12px] text-[#991B1B]">
              {protError}
            </div>
          ) : null}

          <button
            type="button"
            disabled={protBusy}
            onClick={() => void submitScenario("PROTECTION", protQty, protPrice)}
            className="min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-4 py-2 text-[13px] font-semibold text-[#0F172A] hover:bg-[#F1F5F9] disabled:opacity-60"
          >
            {protBusy ? "Calculating Protection..." : "Run Protection Scenario"}
          </button>

          {protResult ? <ScenarioResultCard scenario={protResult} /> : null}
        </div>

        {/* Manual Partial Sale Simulator */}
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Manual Partial Sale Simulator
              </h2>
              <div className="text-[12px] text-[#64748B]">
                POST /api/v2/positions/sell-scenario
              </div>
            </div>
            <ProvenanceBadge status="SIMULATED" />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="sell-qty"
                className="mb-1 block text-[12px] font-semibold text-[#334155]"
              >
                Shares to Sell
              </label>
              <input
                id="sell-qty"
                type="number"
                min={1}
                value={sellQty}
                onChange={(e) => setSellQty(e.target.value)}
                className="mono-num min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13.5px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
              />
            </div>
            <div>
              <label
                htmlFor="sell-price"
                className="mb-1 block text-[12px] font-semibold text-[#334155]"
              >
                Limit Price (TND)
              </label>
              <input
                id="sell-price"
                type="text"
                inputMode="decimal"
                value={sellPrice}
                onChange={(e) => setSellPrice(e.target.value)}
                className="mono-num min-h-[40px] w-full rounded-md border border-[#CBD5E1] bg-white px-3 text-[13.5px] text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
              />
            </div>
          </div>

          {holding ? (
            <div className="flex flex-wrap gap-1.5">
              {[0.25, 0.5, 1.0].map((frac) => {
                const q = Math.max(1, Math.round(holding.quantity * frac));
                return (
                  <button
                    key={frac}
                    type="button"
                    onClick={() => setSellQty(String(q))}
                    className="rounded border border-[#CBD5E1] bg-[#F1F5F9] px-2.5 py-1 text-[11.5px] font-medium text-[#334155] hover:bg-[#F0FDFA] hover:text-[#0F766E]"
                  >
                    {Math.round(frac * 100)}% ({q} sh)
                  </button>
                );
              })}
            </div>
          ) : null}

          {sellError ? (
            <div className="rounded-md border border-[#FECACA] bg-[#FEF2F2] p-2.5 text-[12px] text-[#991B1B]">
              {sellError}
            </div>
          ) : null}

          <button
            type="button"
            disabled={sellBusy}
            onClick={() => void submitScenario("SELL", sellQty, sellPrice)}
            className="min-h-[40px] w-full rounded-md bg-[#0F766E] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#115E59] disabled:opacity-60"
          >
            {sellBusy ? "Simulating Sale..." : "Simulate Manual Sale"}
          </button>

          {sellResult ? <ScenarioResultCard scenario={sellResult} /> : null}
        </div>
      </section>
    </div>
  );
}
