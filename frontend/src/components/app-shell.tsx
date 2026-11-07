"use client";

import React, { createContext, useContext, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  ArrowLeftRight,
  BarChart3,
  FileSearch,
  FlaskConical,
  ShieldCheck,
  Lock,
  Radio,
} from "lucide-react";
import { PortfolioMode } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/primitives";

interface ModeContextValue {
  mode: PortfolioMode;
  setMode: (m: PortfolioMode) => void;
  refreshTrigger: number;
  triggerRefresh: () => void;
}

const ModeContext = createContext<ModeContextValue>({
  mode: "REAL_COMPETITION",
  setMode: () => {},
  refreshTrigger: 0,
  triggerRefresh: () => {},
});

export function usePortfolioMode() {
  return useContext(ModeContext);
}

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/transactions", label: "Transactions & Orders", icon: ArrowLeftRight },
  { href: "/market", label: "Market Explorer", icon: BarChart3 },
  { href: "/research", label: "Stock Research", icon: FileSearch },
  { href: "/strategy", label: "Strategy Lab", icon: FlaskConical },
  { href: "/health", label: "System Health", icon: ShieldCheck },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mode, setMode] = useState<PortfolioMode>("REAL_COMPETITION");
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const triggerRefresh = () => setRefreshTrigger((n) => n + 1);

  return (
    <ModeContext.Provider value={{ mode, setMode, refreshTrigger, triggerRefresh }}>
      <div className="min-h-screen flex bg-[#090d16] text-slate-100">
        {/* Sidebar */}
        <aside className="w-64 shrink-0 border-r border-slate-800/80 bg-slate-950/90 flex flex-col justify-between">
          <div>
            <div className="p-5 border-b border-slate-800/80">
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold text-sm">
                  BV
                </div>
                <div>
                  <h1 className="text-sm font-semibold tracking-tight text-slate-100">
                    BVMT Intelligence
                  </h1>
                  <p className="text-[11px] text-slate-400">Tunis Bourse Decision Support</p>
                </div>
              </div>
            </div>

            {/* Environment Switcher */}
            <div className="px-4 py-3.5 border-b border-slate-800/80 bg-slate-900/40">
              <label className="block text-[11px] font-medium uppercase tracking-wider text-slate-400 mb-1.5">
                Portfolio Environment
              </label>
              <select
                aria-label="Portfolio Environment"
                value={mode}
                onChange={(e) => setMode(e.target.value as PortfolioMode)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-slate-100 focus:border-emerald-500 focus:outline-none"
              >
                <option value="REAL_COMPETITION">Real Competition Portfolio</option>
                <option value="SYNTHETIC_DEMO">Synthetic Demo Sandbox</option>
              </select>
            </div>

            {/* Navigation */}
            <nav className="p-3 space-y-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-xs font-medium transition-colors",
                      active
                        ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                        : "text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Safety Footer */}
          <div className="p-4 border-t border-slate-800/80 space-y-2 text-[11px] text-slate-400">
            <div className="flex items-center gap-2 text-emerald-400 font-medium">
              <Lock className="h-3.5 w-3.5" />
              <span>100% Manual Execution</span>
            </div>
            <p className="leading-relaxed text-slate-400">
              Localhost read-only terminal. Zero autonomous order submission.
            </p>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top Status Header */}
          <header className="h-14 border-b border-slate-800/80 bg-slate-950/60 px-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {mode === "REAL_COMPETITION" ? (
                <Badge variant="success" className="gap-1.5">
                  <Radio className="h-3 w-3 text-emerald-400 animate-pulse" />
                  REAL COMPETITION ACCOUNT
                </Badge>
              ) : (
                <Badge variant="warning">SYNTHETIC DEMO SANDBOX</Badge>
              )}
              <span className="text-xs text-slate-400 hidden sm:inline">
                Tunis Bourse Challenge (Oct 2026 – May 2027)
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <Badge variant="outline">Localhost Only (127.0.0.1)</Badge>
              <Badge variant="info">Read-Only Collector</Badge>
            </div>
          </header>

          <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">{children}</main>
        </div>
      </div>
    </ModeContext.Provider>
  );
}
