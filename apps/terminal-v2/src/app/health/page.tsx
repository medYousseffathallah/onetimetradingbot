"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import { useMode } from "@/components/mode-context";
import { v2Api, type HealthResponse, type PortfolioResponse } from "@/lib/v2-api";
import { formatInteger, formatProvenanceNumber, formatTimestamp } from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ExecutionGateBadge } from "@/components/StateBadges";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

export default function DataAccountHealthPage() {
  const { mode } = useMode();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, p] = await Promise.all([
        v2Api.getHealth(mode),
        v2Api.getPortfolio(mode),
      ]);
      setHealth(h);
      setPortfolio(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load health telemetry");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <LoadingSkeleton rows={5} />;
  if (error || !health || !portfolio) {
    return <ApiErrorBanner error={error ?? "Missing health telemetry"} onRetry={loadData} />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
            GET /api/v2/health?mode={mode}
          </div>
          <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
            Data &amp; Account Health
          </h1>
          <p className="mt-0.5 text-[13.5px] text-[#334155]">
            Competition rule blockers, equity-only universe enforcement, snapshot conflict audit,
            and localhost / zero-LLM safety guardrails.
          </p>
        </div>
        <ExecutionGateBadge
          state={health.execution_enabled ? "ELIGIBLE_MANUAL_ONLY" : "EXECUTION_BLOCKED"}
        />
      </div>

      <section className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
            Execution Posture
          </div>
          <div className="pt-1">
            <ExecutionGateBadge
              state={health.execution_enabled ? "ELIGIBLE_MANUAL_ONLY" : "EXECUTION_BLOCKED"}
            />
          </div>
          <div className="pt-1 text-[12px] text-[#64748B]">
            auto_submission:{" "}
            <code className="font-mono">{String(health.automatic_submission_enabled)}</code>
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Competition Rules
            </span>
            <ProvenanceBadge
              status={health.rules_blocker_count > 0 ? "UNVERIFIED" : "OBSERVED"}
            />
          </div>
          <div className="mono-num text-[22px] font-semibold text-[#92400E]">
            {health.rules_blocker_count} Blockers
          </div>
          <div className="text-[12px] text-[#64748B]">
            Missing verified rule fields &amp; official evidence locators
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Canonical Equities
            </span>
            <ProvenanceBadge status="OBSERVED" />
          </div>
          <div className="mono-num text-[22px] font-semibold text-[#0F172A]">
            {health.equity_instruments} Equities
          </div>
          <div className="text-[12px] text-[#64748B]">
            {health.challenge_members} Challenge &middot;{" "}
            {formatInteger(health.upstream_excluded_non_equity_count)} upstream /{" "}
            {formatInteger(health.rejected_non_equity_count)} runtime non-equity excluded
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
              Live LLM Spend
            </span>
            <ProvenanceBadge status="OBSERVED" label="DISABLED" />
          </div>
          <div className="mono-num text-[22px] font-semibold text-[#065F46]">
            {health.llm_live_enabled ? "ENABLED" : "DISABLED (0)"}
          </div>
          <div className="text-[12px] text-[#64748B]">
            <code>BVMT_ALLOW_LIVE_LLM=0</code> &middot; Zero network spend
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-[#B45309]" />
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Competition Rule Blockers Audit
              </h2>
            </div>
            <ProvenanceBadge status="UNVERIFIED" />
          </div>
          <p className="text-[12.5px] text-[#334155]">
            <code>configs/competition.json</code> currently records{" "}
            <strong className="mono-num">{health.rules_blocker_count}</strong> unresolved
            field-level verification blockers across competition edition, fees, matching,
            eligibility, settlement, concentration, and automation policy. Execution remains
            deterministically blocked until verified against official Tunis Bourse competition
            documentation.
          </p>
          <div className="rounded-md border border-[#FDE68A] bg-[#FFFBEB] p-3 text-[12px] text-[#92400E]">
            In <code>REAL_COMPETITION</code> mode, all manual scenarios carry{" "}
            <code>UNVERIFIED_COMPETITION_RULES</code> and <code>is_executed: false</code>.
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Dataset &amp; Equity-Only Manifest
            </h2>
            <ProvenanceBadge
              status={mode === "SYNTHETIC_DEMO" ? "SIMULATED" : "OBSERVED"}
            />
          </div>
          <div className="divide-y divide-[#E2E8F0] text-[13px]">
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">Canonical Equity Instruments</span>
              <span className="mono-num font-semibold text-[#0F172A]">
                {health.equity_instruments}
              </span>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">Challenge Members</span>
              <span className="mono-num font-semibold text-[#0F172A]">
                {health.challenge_members}
              </span>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">Excluded Non-Equity Rows</span>
              <span className="mono-num font-semibold text-[#0F172A]">
                {formatInteger(health.upstream_excluded_non_equity_count)} upstream /{" "}
                {formatInteger(health.rejected_non_equity_count)} runtime
              </span>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">Trading Sessions</span>
              <span className="mono-num font-semibold text-[#0F172A]">
                {health.session_count} (latest: {health.latest_session ?? "—"})
              </span>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">published_at_present_count</span>
              <span className="mono-num font-semibold text-[#92400E]">
                {health.published_at_present_count} (EOD_UNVERIFIED_PUB_TIME)
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Account Sync &amp; Capture Audit
            </h2>
            <ProvenanceBadge
              status={portfolio.account_state_conflict ? "UNVERIFIED" : "OBSERVED"}
            />
          </div>
          <div className="divide-y divide-[#E2E8F0] text-[12.5px]">
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">account_state_conflict</span>
              <span
                className={`font-semibold ${
                  portfolio.account_state_conflict ? "text-[#92400E]" : "text-[#065F46]"
                }`}
              >
                {String(portfolio.account_state_conflict)}
              </span>
            </div>
            {Object.entries(portfolio.snapshots).map(([key, snap]) => (
              <div key={key} className="py-2 space-y-0.5">
                <div className="flex items-center justify-between gap-2 font-semibold text-[#0F172A]">
                  <span>{key}</span>
                  <span className="mono-num">{formatProvenanceNumber(snap.equity_tnd)}</span>
                </div>
                <div className="font-mono text-[11px] text-[#64748B] break-all">
                  {snap.snapshot_id} &middot; {formatTimestamp(snap.captured_at)}
                </div>
              </div>
            ))}
            <div className="py-2">
              <div className="font-semibold text-[#334155]">
                Rejected Captures ({portfolio.rejected_captures.length})
              </div>
              {portfolio.rejected_captures.length > 0 ? (
                <div className="mt-1 font-mono text-[11.5px] text-[#991B1B] break-all">
                  {portfolio.rejected_captures.join(", ")}
                </div>
              ) : (
                <div className="mt-1 text-[12px] text-[#64748B]">None</div>
              )}
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex items-center gap-2 border-b border-[#E2E8F0] pb-2.5">
            <ShieldCheck className="h-4 w-4 text-[#0F766E]" />
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Offline &amp; Loopback Safety Guardrails
            </h2>
          </div>
          <div className="divide-y divide-[#E2E8F0] text-[13px]">
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">execution_enabled</span>
              <code className="font-mono font-semibold text-[#0F172A]">
                {String(health.execution_enabled)}
              </code>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">automatic_submission_enabled</span>
              <code className="font-mono font-semibold text-[#0F172A]">
                {String(health.automatic_submission_enabled)}
              </code>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">llm_live_enabled</span>
              <code className="font-mono font-semibold text-[#0F172A]">
                {String(health.llm_live_enabled)}
              </code>
            </div>
            <div className="flex justify-between gap-2 py-2">
              <span className="text-[#334155]">API Binding</span>
              <code className="font-mono font-semibold text-[#0F172A]">
                127.0.0.1 loopback only
              </code>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
