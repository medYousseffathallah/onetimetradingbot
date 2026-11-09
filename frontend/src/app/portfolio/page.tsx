"use client";

import React, { useEffect, useState } from "react";
import {
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Trophy,
  Wallet,
  TrendingUp,
  Clock,
  Layers,
  Copy,
  Check,
  Chrome,
  FileText,
  Upload,
  Play,
  StopCircle,
  Key,
  ShieldCheck,
  Info,
} from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
} from "recharts";
import {
  api,
  AccountOverviewResponse,
  HoldingsResponse,
  SnapshotsResponse,
  PairingTokenResponse,
  PlaywrightJobResponse,
} from "@/lib/api";
import { formatTnd, formatPct, formatTimestamp } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";
import { usePortfolioMode } from "@/components/app-shell";
import { SyncConfirmationBanner } from "@/components/sync-banner";

const COLORS = ["#0d9488", "#0284c7", "#f59e0b", "#8b5cf6"];

type SyncTab = "COMPANION" | "MANUAL" | "PLAYWRIGHT";

export default function PortfolioPage() {
  const { mode, refreshTrigger, triggerRefresh } = usePortfolioMode();
  const [overview, setOverview] = useState<AccountOverviewResponse | null>(null);
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Sync Hub states
  const [activeTab, setActiveTab] = useState<SyncTab>("COMPANION");
  const [pairingToken, setPairingToken] = useState<PairingTokenResponse | null>(null);
  const [tokenCopied, setTokenCopied] = useState(false);

  // Manual import state
  const [pasteText, setPasteText] = useState("");
  const [cashOverride, setCashOverride] = useState("");
  const [equityOverride, setEquityOverride] = useState("");
  const [manualLoading, setManualLoading] = useState(false);
  const [manualMessage, setManualMessage] = useState<string | null>(null);
  const [manualError, setManualError] = useState<string | null>(null);

  // Playwright async state
  const [activeJob, setActiveJob] = useState<PlaywrightJobResponse | null>(null);
  const [playwrightLoading, setPlaywrightLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getOverview(mode),
      api.getHoldings(mode),
      api.getSnapshots(mode),
      api.getPairingToken().catch(() => null),
    ])
      .then(([ov, hd, sn, tok]) => {
        setOverview(ov);
        setHoldings(hd);
        setSnapshots(sn);
        if (tok) setPairingToken(tok);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mode, refreshTrigger]);

  // Playwright job polling
  useEffect(() => {
    if (
      !activeJob ||
      activeJob.status === "COMPLETED" ||
      activeJob.status === "FAILED" ||
      activeJob.status === "CANCELLED"
    ) {
      return;
    }
    const interval = setInterval(async () => {
      try {
        const updated = await api.getPlaywrightJobStatus(activeJob.job_id);
        setActiveJob(updated);
        if (updated.status === "COMPLETED") {
          setPlaywrightLoading(false);
          triggerRefresh();
        } else if (updated.status === "FAILED" || updated.status === "CANCELLED") {
          setPlaywrightLoading(false);
        }
      } catch {
        setPlaywrightLoading(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [activeJob, triggerRefresh]);

  const handleCopyToken = () => {
    if (!pairingToken) return;
    navigator.clipboard.writeText(pairingToken.pairing_token);
    setTokenCopied(true);
    setTimeout(() => setTokenCopied(false), 2500);
  };

  const handleManualPaste = async () => {
    if (!pasteText.trim()) return;
    setManualLoading(true);
    setManualError(null);
    setManualMessage(null);
    try {
      const res = await api.syncManualPaste({
        raw_text: pasteText,
        cash_override: cashOverride.trim() || undefined,
        equity_override: equityOverride.trim() || undefined,
      });
      setManualMessage(
        `Snapshot parsed: Total ${formatTnd(
          res.captured_snapshot?.portfolio_total_tnd
        )} (Cash: ${formatTnd(
          res.captured_snapshot?.available_cash_tnd
        )}). Review & confirm in the banner above.`
      );
      setPasteText("");
      triggerRefresh();
    } catch (err: unknown) {
      setManualError(err instanceof Error ? err.message : "Failed to parse pasted text.");
    } finally {
      setManualLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (evt) => {
      const content = evt.target?.result as string;
      if (!content) return;
      setManualLoading(true);
      setManualError(null);
      setManualMessage(null);
      try {
        const res = await api.syncManualCsv({
          csv_content: content,
          cash_override: cashOverride.trim() || undefined,
          equity_override: equityOverride.trim() || undefined,
        });
        setManualMessage(
          `CSV snapshot imported: Total ${formatTnd(
            res.captured_snapshot?.portfolio_total_tnd
          )}. Review & confirm in the banner above.`
        );
        triggerRefresh();
      } catch (err: unknown) {
        setManualError(err instanceof Error ? err.message : "Failed to parse CSV file.");
      } finally {
        setManualLoading(false);
      }
    };
    reader.readAsText(file);
  };

  const handleStartPlaywright = async () => {
    setPlaywrightLoading(true);
    try {
      const job = await api.startPlaywrightJob(180);
      setActiveJob(job);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to start Playwright job.");
      setPlaywrightLoading(false);
    }
  };

  const handleCancelPlaywright = async () => {
    if (!activeJob) return;
    try {
      await api.cancelPlaywrightJob(activeJob.job_id);
      setActiveJob((prev) => (prev ? { ...prev, status: "CANCELLED" } : null));
    } catch {
      // Ignored
    }
  };

  if (loading && !overview) {
    return (
      <div className="p-16 text-center text-sm text-slate-500 dark:text-slate-400">
        Loading portfolio state and synchronization channels...
      </div>
    );
  }

  if (!overview || !holdings) {
    return (
      <Card className="border-rose-200 dark:border-rose-900 bg-rose-50/80 dark:bg-rose-950/20">
        <CardContent className="p-6 text-sm text-rose-800 dark:text-rose-300">
          Unable to load portfolio data. Ensure the local FastAPI service is running.
        </CardContent>
      </Card>
    );
  }

  const web = overview.website_reported;
  const loc = overview.local_valuation;
  const sync = overview.sync_status;
  const pnlNum = parseFloat(web.unrealized_pnl_tnd || "0");

  const cashVal = parseFloat(web.available_cash_tnd || "0");
  const holdingsVal = parseFloat(web.holdings_value_tnd || "0");
  const pieData = [
    { name: "Available Cash (TND)", value: cashVal },
    ...holdings.holdings.map((h) => ({
      name: h.symbol,
      value: parseFloat(h.website_market_value_tnd || "0"),
    })),
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Competition Portfolio & Synchronization Hub
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Resilient multi-channel account sync: Chrome Companion (zero-cookie), Manual Paste & CSV, or Background Playwright.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {sync.has_pending_snapshot ? (
            <Badge variant="warning" className="gap-1.5 py-1 px-3">
              <AlertTriangle className="h-3.5 w-3.5" />
              Snapshot Awaiting Confirmation
            </Badge>
          ) : sync.live_synchronized ? (
            <Badge variant="success" className="gap-1.5 py-1 px-3">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Confirmed & Synchronized
            </Badge>
          ) : (
            <Badge variant="warning" className="py-1 px-3">
              Baseline Snapshot
            </Badge>
          )}
        </div>
      </div>

      {/* Confirmation Banner (appears whenever a new snapshot is captured by any channel) */}
      <SyncConfirmationBanner />

      {/* Three-Channel Synchronization Hub Card */}
      {mode === "REAL_COMPETITION" && (
        <Card className="border-teal-200/80 dark:border-teal-900/60 shadow-sm bg-gradient-to-b from-white to-teal-50/20 dark:from-slate-950 dark:to-slate-900/40">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                  Account Synchronization Hub (Milestone 10)
                </CardTitle>
                <CardDescription className="text-xs">
                  Choose your preferred capture method. All methods enforce strict Decimal precision, balance validation, and require explicit confirmation.
                </CardDescription>
              </div>

              {/* Channel Tabs */}
              <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-900 p-1 rounded-lg border border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setActiveTab("COMPANION")}
                  className={`flex items-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-md transition-all ${
                    activeTab === "COMPANION"
                      ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-300 shadow-sm font-semibold"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                  }`}
                >
                  <Chrome className="h-3.5 w-3.5" />
                  <span>Browser Companion</span>
                  <Badge variant="outline" className="text-[10px] py-0 px-1 ml-1 text-teal-600 border-teal-300">
                    Recommended
                  </Badge>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("MANUAL")}
                  className={`flex items-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-md transition-all ${
                    activeTab === "MANUAL"
                      ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-300 shadow-sm font-semibold"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                  }`}
                >
                  <FileText className="h-3.5 w-3.5" />
                  <span>Manual Paste / CSV</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("PLAYWRIGHT")}
                  className={`flex items-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-md transition-all ${
                    activeTab === "PLAYWRIGHT"
                      ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-300 shadow-sm font-semibold"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                  }`}
                >
                  <Play className="h-3.5 w-3.5" />
                  <span>Automated Playwright</span>
                </button>
              </div>
            </div>
          </CardHeader>

          <CardContent className="pt-2">
            {/* TAB 1: BROWSER COMPANION */}
            {activeTab === "COMPANION" && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                <div className="md:col-span-2 space-y-4">
                  <div className="p-4 rounded-lg bg-teal-50/60 dark:bg-teal-950/20 border border-teal-200/80 dark:border-teal-900/60 space-y-2">
                    <h4 className="text-sm font-semibold text-teal-950 dark:text-teal-200 flex items-center gap-2">
                      <Chrome className="h-4 w-4 text-teal-600" />
                      Zero-Credential Read-Only Chrome Extension
                    </h4>
                    <p className="text-xs text-teal-900/80 dark:text-teal-300/80 leading-relaxed">
                      Extracts visible figures directly from your active Tunis Bourse Challenge tab (<code>displayp.aspx</code>).
                      No password, cookies, or session tokens are ever touched or transferred.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Step-by-step Setup (1 Minute):
                    </p>
                    <ol className="text-xs text-slate-600 dark:text-slate-400 space-y-1.5 list-decimal pl-4">
                      <li>
                        Open Chrome and navigate to <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">chrome://extensions</code>.
                      </li>
                      <li>Toggle <strong>Developer mode</strong> in the top-right corner.</li>
                      <li>
                        Click <strong>Load unpacked</strong> and select the repository folder:{" "}
                        <code className="font-mono text-[11px] bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-teal-800 dark:text-teal-300">
                          bvmt-starter-kit/extension
                        </code> (if already loaded, click the <strong>⟳ Reload</strong> icon).
                      </li>
                      <li>
                        Click the BVMT icon in Chrome, paste your pairing token, and click <strong>Extract & Sync to Platform</strong>.
                      </li>
                    </ol>
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      <Key className="h-3.5 w-3.5 text-amber-500" />
                      Local Pairing Token
                    </span>
                    <Badge variant="outline" className="text-[10px]">
                      Localhost Only
                    </Badge>
                  </div>

                  <div className="p-2 rounded bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 font-mono text-[11px] break-all select-all text-slate-800 dark:text-slate-200">
                    {pairingToken?.pairing_token || "Loading pairing token..."}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyToken}
                    className="w-full gap-2 text-xs"
                    disabled={!pairingToken}
                  >
                    {tokenCopied ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-emerald-600" />
                        <span className="text-emerald-700 font-semibold">Token Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" />
                        <span>Copy Pairing Token</span>
                      </>
                    )}
                  </Button>

                  <p className="text-[11px] text-slate-500 leading-tight">
                    This token authenticates transmissions from your browser extension to FastAPI (Port 8000).
                  </p>
                </div>
              </div>
            )}

            {/* TAB 2: MANUAL PASTE & CSV */}
            {activeTab === "MANUAL" && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left: Textarea */}
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center justify-between">
                      <span>Paste Table or Text from displayp.aspx</span>
                      <span className="text-[11px] font-normal text-slate-500">Supports HTML tables or plain text</span>
                    </label>
                    <textarea
                      rows={6}
                      value={pasteText}
                      onChange={(e) => setPasteText(e.target.value)}
                      placeholder="Copy the table from Tunis Bourse Challenge displayp.aspx and paste here... (e.g. Liquidités : 44 586,070 DT, Total : 49 979,070 DT, BH BANK 30 13,067 13,090)"
                      className="w-full p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-xs font-mono text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>

                  {/* Right: Overrides and CSV upload */}
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                          Cash Override (TND)
                        </label>
                        <input
                          type="text"
                          value={cashOverride}
                          onChange={(e) => setCashOverride(e.target.value)}
                          placeholder="e.g. 44586.070"
                          className="mt-1 w-full p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-xs font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                          Equity Override (TND)
                        </label>
                        <input
                          type="text"
                          value={equityOverride}
                          onChange={(e) => setEquityOverride(e.target.value)}
                          placeholder="e.g. 49979.070"
                          className="mt-1 w-full p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-xs font-mono"
                        />
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-dashed border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 text-center space-y-1.5">
                      <Upload className="h-4 w-4 mx-auto text-slate-400" />
                      <p className="text-xs text-slate-600 dark:text-slate-400">
                        Or upload a holdings CSV export
                      </p>
                      <input
                        type="file"
                        accept=".csv,.txt"
                        onChange={handleFileUpload}
                        className="text-xs text-slate-500 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100 cursor-pointer"
                      />
                    </div>
                  </div>
                </div>

                {manualMessage && (
                  <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300">
                    {manualMessage}
                  </div>
                )}

                {manualError && (
                  <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300">
                    {manualError}
                  </div>
                )}

                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={manualLoading || !pasteText.trim()}
                    onClick={handleManualPaste}
                    className="gap-2"
                  >
                    {manualLoading ? (
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    )}
                    <span>Parse, Validate & Stage Snapshot</span>
                  </Button>
                </div>
              </div>
            )}

            {/* TAB 3: PLAYWRIGHT AUTOMATED */}
            {activeTab === "PLAYWRIGHT" && (
              <div className="space-y-4">
                <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <Play className="h-4 w-4 text-sky-600" />
                      Asynchronous Background Collector
                    </h4>
                    <p className="text-xs text-slate-600 dark:text-slate-400">
                      Runs the Playwright browser subprocess in the background with lockfile collision recovery and live status polling.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {activeJob && activeJob.status === "RUNNING" ? (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={handleCancelPlaywright}
                        className="gap-1.5 text-xs"
                      >
                        <StopCircle className="h-3.5 w-3.5" />
                        <span>Cancel Task</span>
                      </Button>
                    ) : (
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={playwrightLoading}
                        onClick={handleStartPlaywright}
                        className="gap-1.5 text-xs"
                      >
                        <Play className="h-3.5 w-3.5" />
                        <span>Launch Automated Collector</span>
                      </Button>
                    )}
                  </div>
                </div>

                {activeJob && (
                  <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-700 dark:text-slate-300 font-mono">
                        Job: {activeJob.job_id}
                      </span>
                      <Badge
                        variant={
                          activeJob.status === "COMPLETED"
                            ? "success"
                            : activeJob.status === "RUNNING"
                            ? "warning"
                            : activeJob.status === "FAILED"
                            ? "danger"
                            : "outline"
                        }
                      >
                        {activeJob.status}
                      </Badge>
                    </div>

                    {activeJob.status === "RUNNING" && (
                      <div className="flex items-center gap-2 text-xs text-sky-700 dark:text-sky-300">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        <span>
                          Browser collector active. Please log in to Tunis Bourse Challenge if prompted in the opened window...
                        </span>
                      </div>
                    )}

                    {activeJob.status === "COMPLETED" && (
                      <p className="text-xs text-emerald-700 dark:text-emerald-300">
                        Collector finished successfully! Review the candidate snapshot in the banner above.
                      </p>
                    )}

                    {activeJob.status === "FAILED" && (
                      <p className="text-xs text-rose-700 dark:text-rose-300">
                        Collector failed: {activeJob.error_message || "Unknown error."}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Prominent Portfolio Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Portfolio Equity</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="portfolio_reconciliation" />
                <Wallet className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
              </div>
            </div>
            <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
              {formatTnd(web.portfolio_total_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            Reconciled Cash + Holdings
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Available Cash</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="exposure" />
                <Layers className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />
              </div>
            </div>
            <CardTitle className="text-xl font-mono font-bold text-slate-900 dark:text-slate-100">
              {formatTnd(web.available_cash_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            Holdings: {formatTnd(web.holdings_value_tnd)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Unrealized & Realized P&L</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="backtest_return" />
                <TrendingUp className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              </div>
            </div>
            <CardTitle
              className={`text-xl font-mono font-bold ${
                pnlNum > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : pnlNum < 0
                  ? "text-rose-600 dark:text-rose-400"
                  : "text-slate-900 dark:text-slate-100"
              }`}
            >
              {pnlNum > 0
                ? `+${formatTnd(web.unrealized_pnl_tnd)}`
                : formatTnd(web.unrealized_pnl_tnd)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            Realized: {formatTnd(loc.realized_pnl_tnd)} ({formatPct(web.overall_performance_pct)})
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Competition Ranking</CardDescription>
              <Trophy className="h-3.5 w-3.5 text-amber-500" />
            </div>
            <CardTitle className="text-xl font-mono font-bold text-amber-600 dark:text-amber-400">
              {web.competition_rank
                ? `#${web.competition_rank.toLocaleString()} / ${(
                    web.competition_participants || 14530
                  ).toLocaleString()}`
                : "Unranked"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400">
            {web.competition_window || "2026–2027 Edition"}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Last Successful Sync</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp metricId="source_provenance" />
                <Clock className="h-3.5 w-3.5 text-slate-400" />
              </div>
            </div>
            <CardTitle className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              {formatTimestamp(web.capture_timestamp)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400 truncate">
            {web.snapshot_id}
          </CardContent>
        </Card>
      </div>

      {/* Holdings Table + Allocation Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Authenticated Holdings & Mark-to-Market</CardTitle>
            <CardDescription>
              Displays website figures (displayp.aspx) alongside verified BVMT quotations (
              {loc.latest_market_session || "latest"})
            </CardDescription>
          </CardHeader>
          <CardContent>
            {holdings.holdings.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-900 text-xs text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-3 px-3 font-semibold">Stock</th>
                      <th className="py-3 px-3 font-semibold text-right">Shares</th>
                      <th className="py-3 px-3 font-semibold text-right">Acq. Price</th>
                      <th className="py-3 px-3 font-semibold text-right">Acq. Cost</th>
                      <th className="py-3 px-3 font-semibold text-right">Website Price</th>
                      <th className="py-3 px-3 font-semibold text-right">Market Value</th>
                      <th className="py-3 px-3 font-semibold text-right">Unrealized P&L</th>
                      <th className="py-3 px-3 font-semibold text-right">BVMT Close</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {holdings.holdings.map((h) => {
                      const pnl = parseFloat(h.website_unrealized_pnl_tnd || "0");
                      return (
                        <tr key={h.instrument_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                          <td className="py-3 px-3">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">{h.symbol}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                              {h.isin || h.instrument_id} • Weight {formatPct(h.weight_pct, false)}
                            </div>
                          </td>
                          <td className="py-3 px-3 text-right font-mono">{h.quantity}</td>
                          <td className="py-3 px-3 text-right font-mono">
                            {formatTnd(h.acquisition_price_tnd)}
                          </td>
                          <td className="py-3 px-3 text-right font-mono">
                            {formatTnd(h.acquisition_amount_tnd)}
                          </td>
                          <td className="py-3 px-3 text-right font-mono text-teal-700 dark:text-teal-300 font-medium">
                            {formatTnd(h.website_last_price_tnd)}
                          </td>
                          <td className="py-3 px-3 text-right font-mono font-semibold text-slate-900 dark:text-slate-100">
                            {formatTnd(h.website_market_value_tnd)}
                          </td>
                          <td
                            className={`py-3 px-3 text-right font-mono font-semibold ${
                              pnl > 0
                                ? "text-emerald-600 dark:text-emerald-400"
                                : pnl < 0
                                ? "text-rose-600 dark:text-rose-400"
                                : "text-slate-700 dark:text-slate-200"
                            }`}
                          >
                            {pnl > 0
                              ? `+${formatTnd(h.website_unrealized_pnl_tnd)}`
                              : formatTnd(h.website_unrealized_pnl_tnd)}
                            <div className="text-xs font-normal">
                              {formatPct(h.website_unrealized_return_pct)}
                            </div>
                          </td>
                          <td className="py-3 px-3 text-right font-mono text-slate-600 dark:text-slate-300">
                            {h.verified_market_price_tnd
                              ? formatTnd(h.verified_market_price_tnd)
                              : "N/A"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">
                No active holdings in portfolio.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Capital Allocation</CardTitle>
              <MetricHelp metricId="exposure" />
            </div>
            <CardDescription>
              Cash vs Equity Exposure ({formatPct((holdingsVal / (cashVal + holdingsVal || 1)) * 100, false)}{" "}
              invested)
            </CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {pieData.map((_, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip
                  formatter={(value: number) => formatTnd(value)}
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    borderColor: "#cbd5e1",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#0f172a",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Snapshot & Reconciliation History */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Confirmed Snapshot History & Audit Trail</CardTitle>
              <CardDescription className="mt-1">
                Immutable record of confirmed competition snapshots and captured browser syncs
              </CardDescription>
            </div>
            <MetricHelp metricId="portfolio_reconciliation" />
          </div>
        </CardHeader>
        <CardContent>
          {snapshots && snapshots.confirmed_history.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Snapshot ID</th>
                    <th className="py-2.5 px-3 font-semibold">Timestamp</th>
                    <th className="py-2.5 px-3 font-semibold">Provenance</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Portfolio Total</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Available Cash</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Rank</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {snapshots.confirmed_history.map((s) => (
                    <tr key={`${s.snapshot_id}-${s.capture_timestamp}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 font-mono font-medium text-slate-800 dark:text-slate-200">
                        {s.snapshot_id}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600 dark:text-slate-300">
                        {formatTimestamp(s.capture_timestamp)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-500 dark:text-slate-400">
                        {s.live_synchronized ? "Authenticated Browser DOM Sync" : "Opening Screenshot Baseline"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900 dark:text-slate-100">
                        {formatTnd(s.portfolio_total_tnd)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-700 dark:text-slate-300">
                        {formatTnd(s.available_cash_tnd)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-amber-600 dark:text-amber-400 font-medium">
                        {s.competition_rank ? `#${s.competition_rank.toLocaleString()}` : "N/A"}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Badge variant={s.live_synchronized ? "success" : "outline"}>
                          {s.live_synchronized ? "Confirmed Live Sync" : "Opening Baseline"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-500 dark:text-slate-400">No snapshot history recorded yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
