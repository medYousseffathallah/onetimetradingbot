"use client";

import type { ProvenanceValue } from "@/lib/v2-api";
import { formatProvenanceNumber } from "@/lib/format";
import { ProvenanceBadge } from "./ProvenanceBadge";

export function ProvenanceNumber({
  pv,
  signed = false,
  asPctFromRatio = true,
  withUnit = true,
  showBadge = true,
  showReason = false,
  className = "",
}: {
  pv: ProvenanceValue | null | undefined;
  signed?: boolean;
  asPctFromRatio?: boolean;
  withUnit?: boolean;
  showBadge?: boolean;
  showReason?: boolean;
  className?: string;
}) {
  const unavailable = !pv || pv.status === "UNAVAILABLE" || pv.value === null;
  const formatted = formatProvenanceNumber(pv, {
    signed,
    asPctFromRatio,
    withUnit,
  });

  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 min-w-0 ${className}`}>
      <span
        className={
          unavailable
            ? "italic text-[#94A3B8] text-[13px]"
            : "mono-num font-semibold text-[#0F172A]"
        }
      >
        {formatted}
      </span>
      {showBadge && pv ? <ProvenanceBadge status={pv.status} provenance={pv} /> : null}
      {showReason && unavailable && pv?.missing_reason ? (
        <span className="text-[11.5px] text-[#64748B] break-words">
          ({pv.missing_reason})
        </span>
      ) : null}
    </span>
  );
}
