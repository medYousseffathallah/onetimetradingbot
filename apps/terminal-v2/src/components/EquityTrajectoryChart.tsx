"use client";

import type { PortfolioSnapshot } from "@/lib/v2-api";
import { formatTnd, parseDecimal } from "@/lib/format";

interface SnapshotBarItem {
  key: string;
  label: string;
  snapshot: PortfolioSnapshot;
}

const BAR_COLORS: Record<string, string> = {
  confirmed_ledger: "#065F46",
  latest_dom_capture: "#D97706",
  unverified_screenshot: "#92400E",
  eod_mark_portfolio: "#1E40AF",
  synthetic_demo: "#5B21B6",
};

export function EquityTrajectoryChart({ items }: { items: SnapshotBarItem[] }) {
  const valid = items
    .map((item) => ({
      ...item,
      equity: parseDecimal(item.snapshot.equity_tnd.value),
      cash: parseDecimal(item.snapshot.cash_tnd.value) ?? 0,
    }))
    .filter((item) => item.equity !== null);

  if (valid.length === 0) {
    return (
      <div className="rounded-md border border-[#E2E8F0] bg-[#F8F9FA] p-6 text-center text-[13px] text-[#64748B]">
        No snapshot equity valuations available to plot.
      </div>
    );
  }

  const values = valid.map((v) => v.equity as number);
  const minVal = Math.min(...values, 49500);
  const maxVal = Math.max(...values, 50500);
  const span = Math.max(maxVal - minVal, 100);

  return (
    <div className="space-y-3">
      {valid.map((item) => {
        const eq = item.equity as number;
        const pct = Math.max(8, Math.min(100, ((eq - minVal) / span) * 84 + 16));
        const fill = BAR_COLORS[item.key] ?? "#0F766E";
        return (
          <div key={item.key} className="space-y-1">
            <div className="flex flex-wrap items-center justify-between gap-2 text-[12.5px]">
              <span className="font-semibold text-[#0F172A]">{item.label}</span>
              <span className="mono-num font-semibold text-[#0F172A]">
                {formatTnd(item.snapshot.equity_tnd.value)}
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded bg-[#F1F5F9]">
              <div
                className="h-full rounded transition-all"
                style={{ width: `${pct.toFixed(1)}%`, backgroundColor: fill }}
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#64748B]">
              <span>
                Status: <strong>{item.snapshot.verification_status}</strong> &middot;{" "}
                {item.snapshot.holdings.length} holdings
              </span>
              <span className="mono-num">
                Cash: {formatTnd(item.snapshot.cash_tnd.value)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
