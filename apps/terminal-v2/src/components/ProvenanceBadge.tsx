"use client";

import type { ProvenanceValue, ValueStatus } from "@/lib/v2-api";
import { formatTimestamp } from "@/lib/format";

const STATUS_STYLES: Record<ValueStatus, string> = {
  OBSERVED: "bg-[#ECFDF5] text-[#065F46] border-[#A7F3D0]",
  CALCULATED: "bg-[#EFF6FF] text-[#1E40AF] border-[#BFDBFE]",
  SIMULATED: "bg-[#F5F3FF] text-[#5B21B6] border-[#DDD6FE]",
  UNVERIFIED: "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
  UNAVAILABLE: "bg-[#F1F5F9] text-[#475569] border-[#CBD5E1]",
};

export function ProvenanceBadge({
  status,
  provenance,
  label,
}: {
  status: ValueStatus;
  provenance?: ProvenanceValue | null;
  label?: string;
}) {
  const titleParts: string[] = [`Status: ${status}`];
  if (provenance?.source) titleParts.push(`Source: ${provenance.source}`);
  if (provenance?.observation_time) {
    titleParts.push(`Observed: ${formatTimestamp(provenance.observation_time)}`);
  }
  if (provenance?.calculation_time) {
    titleParts.push(`Calculated: ${formatTimestamp(provenance.calculation_time)}`);
  }
  if (provenance?.missing_reason) {
    titleParts.push(`Reason: ${provenance.missing_reason}`);
  }

  return (
    <span
      title={titleParts.join(" | ")}
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.04em] leading-tight whitespace-nowrap ${STATUS_STYLES[status]}`}
    >
      {label ?? status}
    </span>
  );
}
