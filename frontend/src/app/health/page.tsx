"use client";

import React, { useEffect, useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  Lock,
  Cpu,
  Bell,
  CheckCircle2,
} from "lucide-react";
import { api, SystemHealthResponse } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { usePortfolioMode } from "@/components/app-shell";

export default function SystemHealthPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .getHealth(mode)
      .then((res) => setHealth(res))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mode, refreshTrigger]);

  if (loading && !health) {
    return <div className="p-8 text-center text-sm text-slate-400">Loading system health...</div>;
  }

  if (!health) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-rose-400">
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
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            System Health, Compliance & Safety Controls
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Localhost architecture status, competition rule blockers, LLM budget lock, and system
            alerts.
          </p>
        </div>
        <Badge variant="success" className="gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Engine v{health.version} Online
        </Badge>
      </div>

      {/* Security & Safety Guarantees */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center justify-between">
              <span>Execution Policy</span>
              <Lock className="h-4 w-4 text-emerald-400" />
            </CardDescription>
            <CardTitle className="text-base font-semibold text-emerald-400">
              {health.autonomous_trading_enabled
                ? "Autonomous Enabled"
                : "100% Manual Execution Only"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-[11px] text-slate-400">
            Trading URLs (bysell.aspx, acheter, vendre) are strictly blocked in browser collector.
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center justify-between">
              <span>Network Binding</span>
              <ShieldCheck className="h-4 w-4 text-sky-400" />
            </CardDescription>
            <CardTitle className="text-base font-semibold text-slate-100">
              {health.localhost_only ? "Localhost Only (127.0.0.1)" : "Network Exposed"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-[11px] text-slate-400">
            Zero cloud database dependencies. Streamlit fallback available on port 8501.
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center justify-between">
              <span>LLM Budget & Live API Gate</span>
              <Cpu className="h-4 w-4 text-amber-400" />
            </CardDescription>
            <CardTitle className="text-base font-semibold text-slate-100">
              {llm.network_enabled ? "Live Network Enabled" : "Offline Locked (Zero Cost)"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-[11px] text-slate-400">
            Free-quota guard: {String(llm.console_free_quota_only_verified ?? true)}
          </CardContent>
        </Card>
      </div>

      {/* Competition Rule Blockers */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <span>Unverified Competition Rule Fields (configs/competition.json)</span>
          </CardTitle>
          <CardDescription>
            Fields kept null until verified from official competition regulation documents
          </CardDescription>
        </CardHeader>
        <CardContent>
          {health.rule_blockers.length > 0 ? (
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-amber-200/90">
              {health.rule_blockers.map((b, idx) => (
                <li
                  key={idx}
                  className="rounded-lg border border-amber-800/40 bg-amber-950/15 px-3 py-2 font-mono text-[11px]"
                >
                  {b}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-emerald-400">All competition rules verified.</p>
          )}
        </CardContent>
      </Card>

      {/* Local Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-sky-400" />
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
                  className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 flex items-start justify-between gap-4"
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
                      <span className="text-xs font-semibold text-slate-100">{a.title}</span>
                    </div>
                    <p className="text-xs text-slate-400">{a.message}</p>
                  </div>
                  <span className="text-[11px] text-slate-500 shrink-0">
                    {formatTimestamp(a.created_at_utc)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No active alerts.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
