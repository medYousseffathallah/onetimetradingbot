"use client";

import type { ExecutionState, MonitoringState, StockState } from "@/lib/v2-api";

const MONITORING_STYLES: Record<MonitoringState, string> = {
  HOLD: "bg-[#ECFDF5] text-[#065F46] border-[#A7F3D0]",
  REVIEW: "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
  CONSIDER_TRIM: "bg-[#FFFBEB] text-[#92400E] border-[#F59E0B]",
  CONSIDER_EXIT: "bg-[#FEF2F2] text-[#991B1B] border-[#FECACA]",
  INSUFFICIENT_DATA: "bg-[#F1F5F9] text-[#475569] border-[#CBD5E1]",
  EXECUTION_BLOCKED: "bg-[#FEF2F2] text-[#991B1B] border-[#FECACA]",
};

const EXECUTION_STYLES: Record<ExecutionState, string> = {
  EXECUTION_BLOCKED: "bg-[#FEF2F2] text-[#991B1B] border-[#FECACA]",
  ELIGIBLE_MANUAL_ONLY: "bg-[#F0FDFA] text-[#0F766E] border-[#99F6E4]",
};

const STOCK_STATE_STYLES: Record<StockState, string> = {
  RESEARCH_CANDIDATE: "bg-[#F0FDFA] text-[#0F766E] border-[#99F6E4]",
  WATCH: "bg-[#EFF6FF] text-[#1E40AF] border-[#BFDBFE]",
  NO_CURRENT_EDGE: "bg-[#F1F5F9] text-[#475569] border-[#CBD5E1]",
  INSUFFICIENT_EVIDENCE: "bg-[#F1F5F9] text-[#475569] border-[#CBD5E1]",
  RESTRICTED: "bg-[#FEF2F2] text-[#991B1B] border-[#FECACA]",
  HELD_POSITION_REVIEW: "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
};

export function MonitoringBadge({ state }: { state: MonitoringState }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.04em] leading-tight whitespace-nowrap ${MONITORING_STYLES[state]}`}
    >
      {state}
    </span>
  );
}

export function ExecutionGateBadge({ state }: { state: ExecutionState }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.04em] leading-tight whitespace-nowrap ${EXECUTION_STYLES[state]}`}
    >
      {state}
    </span>
  );
}

export function StockStateBadge({ state }: { state: StockState }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.04em] leading-tight whitespace-nowrap ${STOCK_STATE_STYLES[state]}`}
    >
      {state}
    </span>
  );
}
