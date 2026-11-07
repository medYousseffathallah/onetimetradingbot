"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { api, ReconciliationPreviewResponse } from "@/lib/api";
import { formatTnd, formatTimestamp } from "@/lib/utils";
import { Badge, Button, Card, CardContent } from "@/components/ui/primitives";
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
      <Card className="border-emerald-500/40 bg-emerald-950/20">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-emerald-200">
                Synchronized portfolio snapshot confirmed and persisted to active ledger.
              </p>
              <p className="text-xs text-emerald-300/80">
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
    <Card className="border-amber-500/50 bg-amber-950/20">
      <CardContent className="p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0" />
            <div>
              <h4 className="text-sm font-semibold text-amber-200">
                Snapshot captured — awaiting confirmation
              </h4>
              <p className="text-xs text-amber-300/80">
                Captured at {formatTimestamp(snap.retrieved_at)} • Reconciliation gap:{" "}
                {formatTnd(snap.reconciliation_gap_tnd)}
              </p>
            </div>
          </div>
          <Badge variant="warning">Pending Confirmation</Badge>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-lg bg-slate-950/70 p-3.5 border border-slate-800">
          <div>
            <p className="text-[11px] text-slate-400">Website Portfolio Total</p>
            <p className="text-sm font-mono font-semibold text-slate-100">
              {formatTnd(snap.portfolio_total_tnd)}
            </p>
            <p className="text-[11px] text-slate-400">
              Previously: {formatTnd(preview.equity_before_tnd)}
            </p>
          </div>
          <div>
            <p className="text-[11px] text-slate-400">Available Cash</p>
            <p className="text-sm font-mono font-semibold text-slate-100">
              {formatTnd(snap.available_cash_tnd)}
            </p>
            <p className="text-[11px] text-slate-400">
              Delta: {formatTnd(preview.cash_delta_tnd)}
            </p>
          </div>
          <div>
            <p className="text-[11px] text-slate-400">Holdings Market Value</p>
            <p className="text-sm font-mono font-semibold text-slate-100">
              {formatTnd(snap.holdings_market_value_tnd)}
            </p>
            <p className="text-[11px] text-slate-400">{snap.holdings_count} position(s)</p>
          </div>
          <div>
            <p className="text-[11px] text-slate-400">Competition Ranking</p>
            <p className="text-sm font-mono font-semibold text-emerald-400">
              {snap.competition_rank
                ? `#${snap.competition_rank.toLocaleString()} / ${(
                    snap.total_participants || 14530
                  ).toLocaleString()}`
                : "N/A"}
            </p>
            <p className="text-[11px] text-slate-400">Tunis Bourse Challenge</p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
          <label className="flex items-center gap-2.5 text-xs text-slate-200 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
            />
            <span>
              I confirm that the synchronized portfolio values ({formatTnd(snap.portfolio_total_tnd)}
              , {snap.holdings_count} holding(s)) match my Tunis Bourse Challenge account.
            </span>
          </label>
          <Button
            variant="amber"
            size="sm"
            disabled={!checked || submitting}
            onClick={handleConfirm}
          >
            {submitting ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                Applying...
              </>
            ) : (
              "Confirm & Apply Synchronized Snapshot"
            )}
          </Button>
        </div>

        {error && <p className="text-xs text-rose-400 font-medium">{error}</p>}
      </CardContent>
    </Card>
  );
}
