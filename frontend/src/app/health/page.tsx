"use client";

import React, { useEffect, useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  Lock,
  Cpu,
  Bell,
  CheckCircle2,
  RefreshCw,
  Database,
  Calendar,
  Wifi,
} from "lucide-react";
import { api, SystemHealthResponse } from "@/lib/api";
import { formatTimestamp, cn } from "@/lib/utils";
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

export default function SystemHealthPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingMarket, setSyncingMarket] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .getHealth(mode)
      .then((res) => setHealth(res))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mode, refreshTrigger]);

  const handleRefreshMarket = async () => {
    setSyncingMarket(true);
    setSyncMessage(null);
    setSyncError(null);
    try {
      const res = await api.refreshMarketData(false, null, mode);
      setSyncMessage(res.message);
      const updated = await api.getHealth(mode);
      setHealth(updated);
    } catch (err: unknown) {
      setSyncError(err instanceof Error ? err.message : String(err));
    } finally {
      setSyncingMarket(false);
    }
  };

  if (loading && !health) {
    return (
      <div className="p-16 text-center text-sm text-slate-500 dark:text-slate-400">
        Loading system health and safety controls...
      </div>
    );
  }

  if (!health) {
    return (
      <Card className="border-rose-200 dark:border-rose-900 bg-rose-50/80 dark:bg-rose-950/20">
        <CardContent className="p-6 text-sm text-rose-800 dark:text-rose-300">
          Failed to reach FastAPI health endpoint (/api/health).
        </CardContent>
      </Card>
    );
  }

  const llm = health.llm_status || {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            System Health & Safety Controls
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Localhost architecture status, competition rule verification, LLM budget locks, and
            market data gateway status.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="success" className="gap-1.5 py-1 px-3">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Engine v{health.version} Online</span>
          </Badge>
          <MetricHelp metricId="data_freshness" />
        </div>
      </div>

      {/* Security & Safety Guarantees */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Execution Policy</CardDescription>
              <div className="flex items-center gap-1">
                <MetricHelp
                  title="Manual Order Placement Guard"
                  category="governance"
                  plainDefinition="Strict policy prohibiting automated order submissions to tunisbourse-challenge.com."
                  whyItMatters="Protects the competition account from rogue automated trades, network flakiness, or accidental double-executions."
                  formula="Order execution endpoints are blocked at the router and collector levels"
                  interpretation="100% Manual Execution Only: orders are placed manually by the trader in the browser."
                  limitations="Trader must log into the competition portal directly to execute signals."
                  docLink="docs/MANUAL_TRADING_WORKFLOW.md"
                />
                <Lock className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              </div>
            </div>
            <CardTitle className="text-base font-semibold text-emerald-700 dark:text-emerald-400">
              {health.autonomous_trading_enabled
                ? "Autonomous Enabled"
                : "100% Manual Execution Only"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            Trading URLs (bysell.aspx, acheter, vendre) are strictly blocked in browser collector.
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>Network Binding</CardDescription>
              <ShieldCheck className="h-4 w-4 text-sky-600 dark:text-sky-400" />
            </div>
            <CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {health.localhost_only ? "Localhost Only (127.0.0.1)" : "Network Exposed"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            Zero cloud database dependencies. Streamlit fallback available on port 8501.
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <CardDescription>LLM Budget Gate</CardDescription>
              <Cpu className="h-4 w-4 text-amber-500" />
            </div>
            <CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {llm.network_enabled ? "Live Network Enabled" : "Offline Locked (Zero Cost)"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            Free-quota guard: {String(llm.console_free_quota_only_verified ?? true)} • Zero paid calls.
          </CardContent>
        </Card>
      </div>

      {/* Automated Market Data Gateway */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Database className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                <span>Automated Market Data Gateway</span>
              </CardTitle>
              <MetricHelp metricId="source_provenance" />
            </div>
            <CardDescription className="mt-1">
              Pluggable exchange quotation synchronization with HTTP Range tail queries and EOD settlement
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={syncingMarket}
              onClick={handleRefreshMarket}
              className="gap-1.5"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", syncingMarket && "animate-spin")} />
              <span>{syncingMarket ? "Synchronizing..." : "Refresh Market Data"}</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {syncMessage && (
            <div className="rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 p-3 text-xs text-emerald-900 dark:text-emerald-300">
              {syncMessage}
            </div>
          )}
          {syncError && (
            <div className="rounded-lg border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/30 p-3 text-xs text-rose-900 dark:text-rose-300">
              {syncError}
            </div>
          )}

          {health.market_gateway ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 p-3 space-y-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">Active Provider</span>
                <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {health.market_gateway.active_provider_name}
                </div>
                <div className="flex items-center gap-1.5 pt-1">
                  <Badge
                    variant={
                      health.market_gateway.health_status === "HEALTHY"
                        ? "success"
                        : health.market_gateway.health_status === "DEGRADED"
                        ? "warning"
                        : "danger"
                    }
                  >
                    {health.market_gateway.health_status}
                  </Badge>
                  <Badge variant="outline">{health.market_gateway.data_classification}</Badge>
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 p-3 space-y-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">Calendar & Schedule</span>
                <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />
                  <span>{health.market_gateway.calendar_status}</span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 pt-1">
                  Sessions Behind:{" "}
                  <span
                    className={
                      health.market_gateway.sessions_behind <= 2
                        ? "text-emerald-600 dark:text-emerald-400 font-semibold"
                        : "text-amber-600 dark:text-amber-400 font-semibold"
                    }
                  >
                    {health.market_gateway.sessions_behind}
                  </span>{" "}
                  ({health.market_gateway.is_data_fresh ? "Fresh" : "Stale Warning"})
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 p-3 space-y-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">Canonical Dataset</span>
                <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {health.market_gateway.total_sessions_count} sessions / {health.market_gateway.total_bars_count.toLocaleString()} bars
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 pt-1">
                  Latest:{" "}
                  <span className="font-mono text-slate-800 dark:text-slate-200">
                    {health.market_gateway.latest_session_date ?? "N/A"}
                  </span>
                  {health.market_gateway.stale_instruments_count > 0 && (
                    <span className="text-amber-600 dark:text-amber-400 ml-1">
                      ({health.market_gateway.stale_instruments_count} untraded)
                    </span>
                  )}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 p-3 space-y-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">Gateway Transport & Safety</span>
                <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                  <Wifi className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
                  <span>HTTP Range Tail (~3.5 MB)</span>
                </div>
                <p className="text-xs text-emerald-700 dark:text-emerald-400 pt-1">
                  Isolated: Zero write access to ledger
                </p>
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-500 dark:text-slate-400 py-4 text-center">
              Market data gateway information not available.
            </div>
          )}

          <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3.5 text-xs text-slate-600 dark:text-slate-400 space-y-1">
            <span className="font-semibold text-slate-800 dark:text-slate-200 block">
              Safety & Execution Capacity Disclosure:
            </span>
            <p className="leading-relaxed">
              Quotation updates are strictly isolated from the competition ledger (
              <span className="font-mono text-slate-800 dark:text-slate-200">
                data/portfolio/real_competition_ledger.json
              </span>
              ). Market data gateway ingests trailing envelopes into canonical quotation stores. Recommendations
              on the real portfolio are blocked if data is synthetic or older than 5 exchange sessions.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Competition Rule Blockers */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <span>Unverified Competition Rule Fields (configs/competition.json)</span>
            </CardTitle>
            <MetricHelp metricId="eligibility" />
          </div>
          <CardDescription>
            Fields kept null until verified from official competition regulation documents
          </CardDescription>
        </CardHeader>
        <CardContent>
          {health.rule_blockers.length > 0 ? (
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-amber-900 dark:text-amber-200/90">
              {health.rule_blockers.map((b, idx) => (
                <li
                  key={idx}
                  className="rounded-lg border border-amber-200 dark:border-amber-800/40 bg-amber-50/70 dark:bg-amber-950/15 px-3 py-2 font-mono text-xs"
                >
                  {b}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-emerald-600 dark:text-emerald-400">All competition rules verified.</p>
          )}
        </CardContent>
      </Card>

      {/* Local Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Bell className="h-4 w-4 text-sky-600 dark:text-sky-400" />
            <span>System & Market Notifications ({health.alerts.length})</span>
          </CardTitle>
          <CardDescription>
            Deduplicated local alert center and power-off catch-up events
          </CardDescription>
        </CardHeader>
        <CardContent>
          {health.alerts.length > 0 ? (
            <div className="space-y-2.5">
              {health.alerts.map((a) => (
                <div
                  key={a.alert_id}
                  className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3.5 flex items-start justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          a.severity === "critical" || a.severity === "high"
                            ? "danger"
                            : a.severity === "warning" || a.severity === "medium"
                            ? "warning"
                            : "info"
                        }
                      >
                        {a.severity.toUpperCase()}
                      </Badge>
                      <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                        {a.title}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-normal">
                      {a.message}
                    </p>
                  </div>
                  <span className="text-xs text-slate-400 shrink-0 font-mono">
                    {formatTimestamp(a.created_at_utc)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-4 text-center">
              No active alerts.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
