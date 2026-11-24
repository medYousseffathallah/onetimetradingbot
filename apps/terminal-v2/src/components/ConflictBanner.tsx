"use client";

import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { useMode } from "./mode-context";
import type { PortfolioSnapshot } from "@/lib/v2-api";
import { formatProvenanceNumber } from "@/lib/format";

export function ConflictBanner({
  accountStateConflict,
  confirmed,
  latestCapture,
  showActionLink = true,
}: {
  accountStateConflict: boolean;
  confirmed?: PortfolioSnapshot | null;
  latestCapture?: PortfolioSnapshot | null;
  showActionLink?: boolean;
}) {
  const { withModeHref, mode } = useMode();

  if (!accountStateConflict || mode === "SYNTHETIC_DEMO") {
    return null;
  }

  return (
    <div
      role="alert"
      className="mb-4 flex flex-col gap-3 rounded-lg border border-[#FDE68A] bg-[#FFFBEB] p-4 text-[#92400E] sm:flex-row sm:items-start sm:justify-between"
    >
      <div className="flex items-start gap-2.5 min-w-0">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#B45309]" />
        <div className="min-w-0">
          <div className="text-[13.5px] font-semibold">
            Account Truth Conflict &amp; Unimported Movements History
          </div>
          <div className="mt-1 text-[12.5px] leading-relaxed break-words">
            {confirmed && latestCapture ? (
              <>
                Confirmed ledger{" "}
                <code className="rounded bg-[#FEF3C7] px-1 py-0.5 text-[11.5px] break-all">
                  {confirmed.snapshot_id}
                </code>{" "}
                (
                <span className="mono-num font-semibold">
                  {formatProvenanceNumber(confirmed.equity_tnd)}
                </span>
                , {confirmed.holdings.length} holdings) disagrees with newer DOM capture{" "}
                <code className="rounded bg-[#FEF3C7] px-1 py-0.5 text-[11.5px] break-all">
                  {latestCapture.snapshot_id}
                </code>{" "}
                (
                <span className="mono-num font-semibold">
                  {formatProvenanceNumber(latestCapture.equity_tnd)}
                </span>
                , {latestCapture.holdings.length} holdings).{" "}
              </>
            ) : (
              <>
                Confirmed ledger and latest DOM capture disagree, and{" "}
                <code className="rounded bg-[#FEF3C7] px-1 py-0.5 text-[11.5px]">
                  movements_page_captured=false
                </code>
                .{" "}
              </>
            )}
            Automated order planning remains blocked until snapshots and pending orders are
            reconciled.
          </div>
        </div>
      </div>
      {showActionLink ? (
        <Link
          href={withModeHref("/portfolio")}
          className="inline-flex min-h-[38px] shrink-0 items-center justify-center rounded-md border border-[#F59E0B] bg-white px-3 py-1.5 text-[12.5px] font-semibold text-[#92400E] hover:bg-[#FEF3C7] whitespace-nowrap"
        >
          Review Diff &rarr;
        </Link>
      ) : null}
    </div>
  );
}
