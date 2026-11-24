"use client";

import { useCallback, useEffect, useState } from "react";
import { useMode } from "@/components/mode-context";
import { v2Api, type ResearchLabResponse } from "@/lib/v2-api";
import {
  EXIT_POLICY_LABELS,
  FAMILY_LABELS,
  formatInteger,
  formatProvenanceNumber,
  formatTimestamp,
} from "@/lib/format";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { ProvenanceNumber } from "@/components/ProvenanceNumber";
import { ApiErrorBanner, LoadingSkeleton } from "@/components/StateFeedback";

const LAB_HORIZONS: Array<5 | 10 | 20> = [5, 10, 20];
const EXIT_CANDIDATES = ["EURO-CYCLES", "DELICE_HOLDING", "AMEN_BANK", "MPBS", "STA"];

export default function ResearchLabPage() {
  const { mode } = useMode();
  const [horizon, setHorizon] = useState<5 | 10 | 20>(10);
  const [exitInstrumentId, setExitInstrumentId] = useState<string>("EURO-CYCLES");
  const [data, setData] = useState<ResearchLabResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await v2Api.getResearchLab(mode, horizon, exitInstrumentId);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load research lab");
    } finally {
      setLoading(false);
    }
  }, [mode, horizon, exitInstrumentId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <LoadingSkeleton rows={6} />;
  if (error || !data) {
    return <ApiErrorBanner error={error ?? "Missing research lab data"} onRetry={loadData} />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
            GET /api/v2/research-lab?mode={mode}&amp;horizon={horizon}&amp;exit_instrument_id=
            {exitInstrumentId}
          </div>
          <h1 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#0F172A]">
            Research Lab
          </h1>
          <p className="mt-0.5 text-[13.5px] text-[#334155]">
            Walk-forward strategy family comparisons, phase sensitivity across entry offsets,
            exit-policy ablation, and frozen signal journal.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceBadge status="SIMULATED" label={data.classification} />
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-lg border border-[#DDD6FE] bg-[#F5F3FF] p-4 text-[12.5px] text-[#5B21B6] sm:flex-row sm:items-center sm:justify-between">
        <div>
          <strong>Research Sandbox Notice:</strong> All strategy and exit metrics below are{" "}
          <strong>SIMULATED</strong> walk-forward backtests on EOD bars. Never equate simulated
          returns to realized account profit. Live LLM calls: <strong>DISABLED (0)</strong>.
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span>TUNINDEX:</span>
          <ProvenanceNumber pv={data.tunindex} />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[12px] font-semibold uppercase tracking-wide text-[#64748B]">
            Experiment Horizon:
          </span>
          {LAB_HORIZONS.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHorizon(h)}
              className={`min-h-[34px] rounded-md border px-3 py-1 text-[12.5px] font-semibold ${
                horizon === h
                  ? "border-[#99F6E4] bg-[#F0FDFA] text-[#0F766E]"
                  : "border-[#E2E8F0] bg-white text-[#334155] hover:bg-[#F1F5F9]"
              }`}
            >
              {h} Sessions
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label
            htmlFor="exit-instrument"
            className="text-[12px] font-semibold uppercase tracking-wide text-[#64748B]"
          >
            Exit Policy Issuer:
          </label>
          <select
            id="exit-instrument"
            value={exitInstrumentId}
            onChange={(e) => setExitInstrumentId(e.target.value)}
            className="min-h-[36px] rounded-md border border-[#CBD5E1] bg-white px-2.5 text-[12.5px] font-semibold text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
          >
            {EXIT_CANDIDATES.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Strategy Experiments */}
      <section className="overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] px-4 py-3.5">
          <div>
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Walk-Forward Strategy Comparison ({data.experiments.length} Families &middot;{" "}
              {horizon}-Session Horizon)
            </h2>
            <div className="text-[12px] text-[#64748B]">
              Includes Top-1 Winner Excluded return to guard against single-stock concentration
              illusions.
            </div>
          </div>
          <ProvenanceBadge status="SIMULATED" />
        </div>

        <div className="hidden overflow-x-auto lg:block">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-[#E2E8F0] bg-[#F1F5F9] text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#64748B]">
                <th className="px-3.5 py-2.5">Strategy Family</th>
                <th className="px-3.5 py-2.5 text-right">Folds</th>
                <th className="px-3.5 py-2.5 text-right">Net Ret</th>
                <th className="px-3.5 py-2.5 text-right">Alpha vs EW</th>
                <th className="px-3.5 py-2.5 text-right">Max DD</th>
                <th className="px-3.5 py-2.5 text-right">Top-1 Excl</th>
                <th className="px-3.5 py-2.5 text-right">Win Rate</th>
                <th className="px-3.5 py-2.5 text-right">N / Trials</th>
                <th className="px-3.5 py-2.5">Audit Hashes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {data.experiments.map((exp) => (
                <tr key={exp.experiment_id} className="hover:bg-[#F8FAFC]">
                  <td className="px-3.5 py-3">
                    <div className="font-semibold text-[#0F172A]">
                      {FAMILY_LABELS[exp.family] ?? exp.family}
                    </div>
                    <div className="font-mono text-[11px] text-[#64748B]">
                      {exp.family} &middot; {exp.scope}
                    </div>
                  </td>
                  <td className="mono-num px-3.5 py-3 text-right text-[#334155]">
                    {exp.fold_count}
                  </td>
                  <td className="mono-num px-3.5 py-3 text-right font-semibold text-[#0F172A]">
                    {formatProvenanceNumber(exp.net_return_pct, { signed: true })}
                  </td>
                  <td className="mono-num px-3.5 py-3 text-right text-[#334155]">
                    {formatProvenanceNumber(exp.alpha_vs_ew_pct, { signed: true })}
                  </td>
                  <td className="mono-num px-3.5 py-3 text-right text-[#991B1B]">
                    {formatProvenanceNumber(exp.max_drawdown_pct)}
                  </td>
                  <td className="px-3.5 py-3 text-right">
                    <div className="mono-num font-semibold text-[#0F172A]">
                      {formatProvenanceNumber(exp.top1_excluded_return_pct, { signed: true })}
                    </div>
                    {exp.top1_excluded_instrument ? (
                      <div className="text-[10.5px] text-[#64748B]">
                        excl. {exp.top1_excluded_instrument}
                      </div>
                    ) : null}
                  </td>
                  <td className="mono-num px-3.5 py-3 text-right text-[#334155]">
                    {formatProvenanceNumber(exp.win_rate)}
                  </td>
                  <td className="mono-num px-3.5 py-3 text-right text-[#334155]">
                    {formatInteger(exp.sample_count)} / {exp.trial_count}
                  </td>
                  <td className="px-3.5 py-3 font-mono text-[10.5px] text-[#64748B] break-all">
                    cfg:{exp.config_hash.slice(0, 8)} data:{exp.data_hash.slice(0, 8)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="divide-y divide-[#E2E8F0] lg:hidden">
          {data.experiments.map((exp) => (
            <div key={exp.experiment_id} className="space-y-2 p-4 text-[12.5px]">
              <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#E2E8F0] pb-2">
                <div>
                  <div className="font-semibold text-[#0F172A]">
                    {FAMILY_LABELS[exp.family] ?? exp.family}
                  </div>
                  <div className="font-mono text-[11px] text-[#64748B]">
                    {exp.family} &middot; {exp.scope}
                  </div>
                </div>
                <ProvenanceBadge status="SIMULATED" />
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                <div className="text-[#64748B]">Net Return</div>
                <div className="mono-num text-right font-semibold text-[#0F172A]">
                  {formatProvenanceNumber(exp.net_return_pct, { signed: true })}
                </div>
                <div className="text-[#64748B]">Alpha vs EW</div>
                <div className="mono-num text-right text-[#334155]">
                  {formatProvenanceNumber(exp.alpha_vs_ew_pct, { signed: true })}
                </div>
                <div className="text-[#64748B]">Top-1 Excluded</div>
                <div className="mono-num text-right font-semibold text-[#0F172A]">
                  {formatProvenanceNumber(exp.top1_excluded_return_pct, { signed: true })}
                </div>
                <div className="text-[#64748B]">Max Drawdown</div>
                <div className="mono-num text-right text-[#991B1B]">
                  {formatProvenanceNumber(exp.max_drawdown_pct)}
                </div>
                <div className="text-[#64748B]">Samples / Folds</div>
                <div className="mono-num text-right text-[#334155]">
                  {formatInteger(exp.sample_count)} / {exp.fold_count}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Phase Sensitivity */}
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Phase Sensitivity Across Fold Offsets
              </h2>
              <div className="text-[12px] text-[#64748B]">
                Min / Median / Max / IQR (pp) across starting calendar phase offsets
              </div>
            </div>
            <ProvenanceBadge status="SIMULATED" />
          </div>

          {Object.keys(data.phase_sensitivity).length === 0 ? (
            <p className="text-[12.5px] text-[#64748B]">
              Insufficient sessions for multi-offset phase sensitivity at this horizon.
            </p>
          ) : (
            <div className="divide-y divide-[#E2E8F0] text-[12.5px]">
              {Object.entries(data.phase_sensitivity).map(([family, ps]) => (
                <div key={family} className="py-2.5 space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-[#0F172A]">{family}</span>
                    <span className="mono-num text-[12px] text-[#5B21B6]">
                      IQR: {formatProvenanceNumber(ps.iqr_pp)}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[11.5px] text-[#64748B]">
                    <div>
                      Min:{" "}
                      <strong className="mono-num text-[#0F172A]">
                        {formatProvenanceNumber(ps.minimum, { signed: true })}
                      </strong>
                    </div>
                    <div>
                      Median:{" "}
                      <strong className="mono-num text-[#0F172A]">
                        {formatProvenanceNumber(ps.median, { signed: true })}
                      </strong>
                    </div>
                    <div>
                      Max:{" "}
                      <strong className="mono-num text-[#0F172A]">
                        {formatProvenanceNumber(ps.maximum, { signed: true })}
                      </strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Exit Policy Comparison */}
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
            <div>
              <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
                Exit Policy Comparison ({data.exit_instrument_id ?? exitInstrumentId})
              </h2>
              <div className="text-[12px] text-[#64748B]">
                9 exit rules evaluated on matched entry cohorts
              </div>
            </div>
            <ProvenanceBadge status="SIMULATED" />
          </div>

          {Object.keys(data.exit_policy_comparison).length === 0 ? (
            <p className="text-[12.5px] text-[#64748B]">
              No exit comparison available for this issuer/horizon.
            </p>
          ) : (
            <div className="divide-y divide-[#E2E8F0] text-[12.5px]">
              {Object.entries(data.exit_policy_comparison).map(([policy, cmp]) => (
                <div key={policy} className="py-2.5 space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-[#0F172A]">
                      {EXIT_POLICY_LABELS[policy] ?? policy}
                    </span>
                    <span className="mono-num font-semibold text-[#0F172A]">
                      Net {formatProvenanceNumber(cmp.net_return_pct, { signed: true })}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11.5px] text-[#64748B] sm:grid-cols-4">
                    <div>
                      DD:{" "}
                      <span className="mono-num text-[#991B1B]">
                        {formatProvenanceNumber(cmp.max_drawdown_pct)}
                      </span>
                    </div>
                    <div>
                      Retain:{" "}
                      <span className="mono-num text-[#0F172A]">
                        {formatProvenanceNumber(cmp.profit_retention_pct)}
                      </span>
                    </div>
                    <div>
                      False Exit:{" "}
                      <span className="mono-num text-[#0F172A]">
                        {formatProvenanceNumber(cmp.false_exit_rate_pct)}
                      </span>
                    </div>
                    <div>
                      N: <span className="mono-num text-[#0F172A]">{cmp.sample_count}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
              Frozen Forward Signal Journal ({data.signal_journal.length})
            </h2>
            <ProvenanceBadge status="OBSERVED" label="HASH-LOCKED" />
          </div>
          {data.signal_journal.length === 0 ? (
            <p className="text-[12.5px] text-[#64748B]">
              No forward signals frozen in journal yet. Forward tracking starts once prospective
              sessions are appended atomically.
            </p>
          ) : (
            <div className="divide-y divide-[#E2E8F0] text-[12px]">
              {data.signal_journal.map((entry) => (
                <div key={entry.journal_id} className="py-2 space-y-0.5">
                  <div className="flex flex-wrap items-center justify-between gap-2 font-semibold text-[#0F172A]">
                    <span>
                      {entry.instrument_id} ({entry.action_state} &middot; {entry.horizon})
                    </span>
                    <span className="font-mono text-[11px] text-[#0F766E]">
                      {entry.outcome_status}
                    </span>
                  </div>
                  <div className="font-mono text-[11px] text-[#64748B] break-all">
                    {formatTimestamp(entry.recorded_at)} &middot; sha256:{entry.frozen_hash}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-2.5">
          <h2 className="text-[14.5px] font-semibold text-[#0F172A]">
            Disclosed Research Limitations
          </h2>
          <ul className="list-disc space-y-1 pl-4 text-[12.5px] text-[#334155]">
            <li>Unadjusted EOD prices; executable intraday depth and TUNINDEX unavailable.</li>
            <li>Zero-volume bars never fill; next-open fills capped at 10% trailing ADV.</li>
            <li>All experiments are retrospective exploratory runs, never live profit claims.</li>
            {data.limitations.map((lim) => (
              <li key={lim}>{lim}</li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
