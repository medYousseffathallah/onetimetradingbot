"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
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
  Calculator,
  Lock,
  Radio,
  Sun,
  Moon,
  Menu,
  X,
} from "lucide-react";
import { PortfolioMode } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/primitives";
import { useTheme } from "@/components/theme-provider";

interface ModeContextValue {
  mode: PortfolioMode;
  setMode: (m: PortfolioMode) => void;
  refreshTrigger: number;
  triggerRefresh: () => void;
}

const ModeContext = createContext<ModeContextValue>({
  mode: "REAL_COMPETITION",
  setMode: () => { },
  refreshTrigger: 0,
  triggerRefresh: () => { },
});

export function usePortfolioMode() {
  return useContext(ModeContext);
}

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/planner", label: "Trade Planner", icon: Calculator },
  { href: "/transactions", label: "Transactions & Orders", icon: ArrowLeftRight },
  { href: "/market", label: "Market Explorer", icon: BarChart3 },
  { href: "/research", label: "Stock Research", icon: FileSearch },
  { href: "/strategy", label: "Strategy Lab", icon: FlaskConical },
  { href: "/health", label: "System Health", icon: ShieldCheck },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const [mode, setMode] = useState<PortfolioMode>("REAL_COMPETITION");
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  const triggerRefresh = () => setRefreshTrigger((n) => n + 1);

  return (
    <ModeContext.Provider value={{ mode, setMode, refreshTrigger, triggerRefresh }}>
      <div className="min-h-screen flex bg-[#f8f9fa] text-slate-850 dark:bg-[#090d16] dark:text-slate-100 transition-colors">
        {/* Sidebar */}
        <aside className="hidden md:flex w-64 shrink-0 border-r border-slate-200/90 bg-white/95 dark:border-slate-800/80 dark:bg-slate-950/90 flex-col justify-between transition-colors">
          <div>
            <div className="p-5 border-b border-slate-200/90 dark:border-slate-800/80">
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700 font-bold text-sm dark:bg-teal-500/15 dark:border-teal-500/40 dark:text-teal-400">
                  BV
                </div>
                <div>
                  <h1 className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
                    BVMT Intelligence
                  </h1>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    Tunis Bourse Decision Support
                  </p>
                </div>
              </div>
            </div>

            {/* Environment Switcher */}
            <div className="px-4 py-3.5 border-b border-slate-200/90 bg-slate-50/70 dark:border-slate-800/80 dark:bg-slate-900/40">
              <label className="block text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                Portfolio Environment
              </label>
              <select
                aria-label="Portfolio Environment"
                value={mode}
                onChange={(e) => setMode(e.target.value as PortfolioMode)}
                className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 focus:border-teal-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-teal-500"
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
                        ? "bg-teal-50 text-teal-800 border border-teal-200/80 font-semibold shadow-xs dark:bg-teal-500/15 dark:text-teal-300 dark:border-teal-500/30"
                        : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 border border-transparent dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
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
          <div className="p-4 border-t border-slate-200/90 dark:border-slate-800/80 space-y-2 text-[11px] text-slate-500 dark:text-slate-400">
            <div className="flex items-center gap-2 text-teal-700 dark:text-teal-400 font-medium">
              <Lock className="h-3.5 w-3.5" />
              <span>100% Manual Execution</span>
            </div>
            <p className="leading-relaxed text-slate-500 dark:text-slate-400">
              Localhost read-only terminal. Zero autonomous order submission.
            </p>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top Status Header */}
          <header className="h-14 border-b border-slate-200/90 bg-white/80 dark:border-slate-800/80 dark:bg-slate-950/60 backdrop-blur-sm px-4 sm:px-6 flex items-center justify-between transition-colors">
            <div className="flex items-center gap-2.5 sm:gap-3">
              <button
                type="button"
                onClick={() => setMobileMenuOpen((o) => !o)}
                aria-label="Toggle navigation menu"
                className="md:hidden p-1.5 -ml-1 rounded-lg text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 transition-colors"
              >
                {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
              {mode === "REAL_COMPETITION" ? (
                <Badge variant="success" className="gap-1.5 text-xs">
                  <Radio className="h-3 w-3 text-emerald-600 dark:text-emerald-400 animate-pulse" />
                  <span className="hidden sm:inline">REAL COMPETITION ACCOUNT</span>
                  <span className="sm:hidden">REAL ACCT</span>
                </Badge>
              ) : (
                <Badge variant="warning" className="text-xs">
                  <span className="hidden sm:inline">SYNTHETIC DEMO SANDBOX</span>
                  <span className="sm:hidden">DEMO</span>
                </Badge>
              )}
              <span className="text-xs text-slate-500 dark:text-slate-400 hidden lg:inline">
                Tunis Bourse Challenge (Oct 2026 – May 2027)
              </span>
            </div>

            <div className="flex items-center gap-2.5 sm:gap-3 text-xs">
              <Badge variant="outline" className="hidden md:inline-flex">
                Localhost (127.0.0.1)
              </Badge>
              <Badge variant="info" className="hidden sm:inline-flex">
                Read-Only Collector
              </Badge>

              {/* Theme Toggle Button */}
              <button
                type="button"
                onClick={toggleTheme}
                aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-200/80 dark:hover:bg-slate-700 transition-colors cursor-pointer select-none"
              >
                {theme === "light" ? (
                  <>
                    <Moon className="h-3.5 w-3.5 text-slate-600" />
                    <span className="hidden sm:inline">Dark</span>
                  </>
                ) : (
                  <>
                    <Sun className="h-3.5 w-3.5 text-amber-400" />
                    <span className="hidden sm:inline">Light</span>
                  </>
                )}
              </button>
            </div>
          </header>

          {/* Mobile Navigation Dropdown */}
          {mobileMenuOpen && (
            <div className="md:hidden border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-4 space-y-3 shadow-lg animate-in slide-in-from-top-2">
              <div>
                <label className="block text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                  Portfolio Environment
                </label>
                <select
                  aria-label="Portfolio Environment"
                  value={mode}
                  onChange={(e) => setMode(e.target.value as PortfolioMode)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 focus:border-teal-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="REAL_COMPETITION">Real Competition Portfolio</option>
                  <option value="SYNTHETIC_DEMO">Synthetic Demo Sandbox</option>
                </select>
              </div>
              <nav className="space-y-1 pt-1">
                {NAV_ITEMS.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                        active
                          ? "bg-teal-50 text-teal-800 border border-teal-200/80 font-semibold dark:bg-teal-500/15 dark:text-teal-300 dark:border-teal-500/30"
                          : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>
          )}

          <main className="flex-1 p-4 sm:p-6 max-w-7xl w-full mx-auto space-y-6">{children}</main>
        </div>
      </div>
    </ModeContext.Provider>
  );
}
