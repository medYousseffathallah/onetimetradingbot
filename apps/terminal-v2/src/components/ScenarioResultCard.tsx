"use client";

import type { ManualTradeScenario } from "@/lib/v2-api";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { ProvenanceNumber } from "./ProvenanceNumber";

export function ScenarioResultCard({ scenario }: { scenario: ManualTradeScenario }) {
  return (
    <div className="mt-4 rounded-lg border border-[#DDD6FE] bg-[#F5F3FF] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#DDD6FE] pb-3">
        <div>
          <div className="text-[12.5px] font-semibold text-[#5B21B6]">
            {scenario.side} Dry-Run Output &middot; {scenario.instrument_id}
          </div>
          <div className="text-[11.5px] text-[#5B21B6]">
            is_executed: <strong>{String(scenario.is_executed)}</strong> &middot; Manual
            Competition Portal Entry Only
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <ProvenanceBadge status="SIMULATED" />
          <span
            className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10.5px] font-semibold uppercase ${
              scenario.is_valid
                ? "border-[#A7F3D0] bg-[#ECFDF5] text-[#065F46]"
                : "border-[#FECACA] bg-[#FEF2F2] text-[#991B1B]"
            }`}
          >
            {scenario.is_valid ? "SCENARIO VALID" : "BLOCKED / INVALID"}
          </span>
        </div>
      </div>

      <div className="mt-3 divide-y divide-[#DDD6FE]/70 text-[13px]">
        <div className="flex items-center justify-between gap-2 py-2">
          <span className="text-[#475569]">Quantity &amp; Limit Price</span>
          <span className="mono-num font-semibold text-[#0F172A]">
            {scenario.quantity.toLocaleString("en-US")} sh @{" "}
            <ProvenanceNumber pv={scenario.limit_price_tnd} showBadge={false} />
          </span>
        </div>
        <div className="flex items-center justify-between gap-2 py-2">
          <span className="text-[#475569]">Gross Value</span>
          <ProvenanceNumber pv={scenario.gross_tnd} showBadge={false} />
        </div>
        <div className="flex items-center justify-between gap-2 py-2">
          <span className="text-[#475569]">Estimated Fee (0.50%)</span>
          <ProvenanceNumber pv={scenario.estimated_fee_tnd} showBadge={false} />
        </div>
        {scenario.side !== "BUY" ? (
          <div className="flex items-center justify-between gap-2 py-2">
            <span className="text-[#475569]">Net / Stress Proceeds</span>
            <ProvenanceNumber pv={scenario.stress_proceeds_tnd} showBadge={false} />
          </div>
        ) : null}
        {scenario.downside_loss_tnd ? (
          <div className="flex items-center justify-between gap-2 py-2">
            <span className="text-[#475569]">Downside Loss vs EOD Mark</span>
            <ProvenanceNumber pv={scenario.downside_loss_tnd} showBadge={false} />
          </div>
        ) : null}
        <div className="flex items-center justify-between gap-2 py-2">
          <span className="text-[#475569]">Post-Trade Weight (10% cap)</span>
          <ProvenanceNumber pv={scenario.post_trade_weight} showBadge={false} />
        </div>
        <div className="flex items-center justify-between gap-2 py-2">
          <span className="text-[#475569]">Post-Trade Cash Reserve</span>
          <ProvenanceNumber pv={scenario.post_trade_cash_tnd} showBadge={false} />
        </div>
      </div>

      {scenario.rejection_reasons.length > 0 ? (
        <div className="mt-3 rounded-md border border-[#FECACA] bg-[#FEF2F2] p-3 text-[#991B1B]">
          <div className="text-[11.5px] font-semibold uppercase tracking-wide">
            Rejection / Execution Blockers ({scenario.rejection_reasons.length})
          </div>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px]">
            {scenario.rejection_reasons.map((reason) => (
              <li key={reason} className="break-all">
                <code>{reason}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
