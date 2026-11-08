"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { api, ReconciliationPreviewResponse } from "@/lib/api";
import { formatTnd, formatTimestamp } from "@/lib/utils";
import { Badge, Button, Card, CardContent } from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";
import { usePortfolioMode } from "@/components/app-shell";

export function SyncConfirmationBanner({ onConfirmed }: { onConfirmed?: () => void }) {
  const { mode, refreshTrigger, triggerRefresh } = usePortfolioMode();
  const [preview, setPreview] = useState<ReconciliationPreviewResponse | null>(null);
  const [checked, setChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justConfirmed, setJustConfirmed] = useState(false);

  useEffect(() => {
    if (mode !== "REAL_COMPETITION") {
      setPreview(null);
      return;
    }
    api
      .getSyncPreview(mode)
      .then((res) => setPreview(res))
      .catch(() => {});
  }, [mode, refreshTrigger]);

  if (mode !== "REAL_COMPETITION" || !preview) return null;

  if (justConfirmed && !preview.has_pending) {
    return (
      <Card className="border-emerald-300 bg-emerald-50/80 dark:border-emerald-500/40 dark:bg-emerald-950/20">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-200">
                Synchronized portfolio snapshot confirmed and persisted to active ledger.
              </p>
              <p className="text-xs text-emerald-700/80 dark:text-emerald-300/80">
                Active Portfolio Total: {formatTnd(preview.equity_after_tnd)} | Cash:{" "}
                {formatTnd(preview.cash_after_tnd)}
              </p>
            </div>
          </div>
          <Badge variant="success">Live-Synchronized</Badge>
        </CardContent>
      </Card>
    );
  }

  if (!preview.has_pending || !preview.candidate_snapshot) return null;

  const snap = preview.candidate_snapshot;

  const handleConfirm = async () => {
    if (!checked) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.confirmSnapshot(true);
      setJustConfirmed(true);
      triggerRefresh();
      if (onConfirmed) onConfirmed();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to confirm snapshot");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="border-amber-300 bg-amber-50/70 dark:border-amber-500/50 dark:bg-amber-950/20 shadow-sm">
      <CardContent className="p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                  Snapshot captured — awaiting confirmation
                </h4>
                <MetricHelp metricId="portfolio_reconciliation" />
              </div>
              <p className="text-xs text-amber-800/80 dark:text-amber-300/80">
                Captured at {formatTimestamp(snap.retrieved_at)} • Reconciliation gap:{" "}
                {formatTnd(snap.reconciliation_gap_tnd)}
              </p>
            </div>
          </div>
          <Badge variant="warning">Pending Confirmation</Badge>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-lg bg-white/90 dark:bg-slate-950/70 p-3.5 border border-amber-200/80 dark:border-slate-800">
          <div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Website Portfolio Total</p>
            <p className="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100">
              {formatTnd(snap.portfolio_total_tnd)}
            </p>
            <p className="text-[11px] text-slate-400">
              Previously: {formatTnd(preview.equity_before_tnd)}
            </p>
          </div>
          <div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Available Cash</p>
            <p className="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100">
              {formatTnd(snap.available_cash_tnd)}
            </p>
            <p className="text-[11px] text-slate-400">
              Previously: {formatTnd(preview.cash_before_tnd)}
            </p>
          </div>
          <div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Holdings Market Value</p>
            <p className="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100">
              {formatTnd(snap.holdings_market_value_tnd)}
            </p>
            <p className="text-[11px] text-slate-400">
              Active Positions: {snap.holdings_count}
            </p>
          </div>
          <div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Competition Rank</p>
            <p className="text-sm font-mono font-semibold text-amber-700 dark:text-amber-400">
              {snap.competition_rank !== null
                ? `#${snap.competition_rank} / ${snap.total_participants ?? "?"}`
                : "Unranked"}
            </p>
            <p className="text-[11px] text-slate-400">
              Performance: {snap.displayed_overall_performance_pct ?? "N/A"}
            </p>
          </div>
        </div>

        {error && (
          <div className="rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 p-3 text-xs text-rose-800 dark:text-rose-300">
            {error}
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
          <label className="flex items-center gap-2.5 text-xs text-amber-900 dark:text-amber-200 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              className="rounded border-amber-400 dark:border-slate-700 bg-white dark:bg-slate-900 text-teal-600 focus:ring-teal-500"
            />
            <span>
              I have inspected the website values above and confirm they match my Tunis Bourse
              Challenge account.
            </span>
          </label>

          <Button
            variant="amber"
            size="sm"
            disabled={!checked || submitting}
            onClick={handleConfirm}
            className="shrink-0"
          >
            {submitting ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Committing...</span>
              </>
            ) : (
              <span>Confirm & Reconcile Account</span>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
