"use client";

import { AlertCircle, RefreshCw, Inbox } from "lucide-react";

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading terminal data">
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, idx) => (
          <div
            key={idx}
            className="h-28 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4"
          >
            <div className="h-3 w-24 rounded bg-[#F1F5F9]" />
            <div className="mt-3 h-7 w-36 rounded bg-[#F1F5F9]" />
            <div className="mt-3 h-3 w-28 rounded bg-[#F1F5F9]" />
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
        {Array.from({ length: rows }).map((_, idx) => (
          <div key={idx} className="h-10 w-full rounded bg-[#F1F5F9]" />
        ))}
      </div>
    </div>
  );
}

export function ApiErrorBanner({
  error,
  onRetry,
}: {
  error: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="mb-4 flex flex-col gap-3 rounded-lg border border-[#FECACA] bg-[#FEF2F2] p-4 text-[#991B1B] sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-2.5 min-w-0">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="min-w-0">
          <div className="text-[13.5px] font-semibold">
            Local V2 API Unavailable or Returned Error
          </div>
          <div className="mt-0.5 text-[12.5px] break-words">
            {error}. No synthetic fallback is applied in REAL_COMPETITION mode.
          </div>
        </div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex min-h-[38px] shrink-0 items-center justify-center gap-1.5 rounded-md border border-[#FCA5A5] bg-white px-3 py-1.5 text-[12.5px] font-semibold text-[#991B1B] hover:bg-[#FEE2E2]"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function EmptyStatePanel({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] px-6 py-10 text-center">
      <Inbox className="h-7 w-7 text-[#64748B]" />
      <h3 className="mt-3 text-[14.5px] font-semibold text-[#0F172A]">{title}</h3>
      <p className="mt-1 max-w-md text-[13px] text-[#64748B]">{description}</p>
      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="mt-4 inline-flex min-h-[38px] items-center rounded-md border border-[#CBD5E1] bg-white px-3.5 py-1.5 text-[12.5px] font-semibold text-[#0F172A] hover:bg-[#F1F5F9]"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
