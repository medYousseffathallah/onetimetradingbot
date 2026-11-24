"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, ShieldAlert, CheckCircle2, AlertTriangle } from "lucide-react";
import { useMode } from "./mode-context";
import type { Mode } from "@/lib/v2-api";

interface NavItem {
  label: string;
  href: string;
  match: (pathname: string) => boolean;
  tag?: string;
}

interface NavCluster {
  label: string;
  items: NavItem[];
}

export function AppShell({
  title,
  children,
}: {
  title?: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { mode, setMode, withModeHref, health, accountTruthState } = useMode();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const clusters: NavCluster[] = [
    {
      label: "Portfolio & Supervision",
      items: [
        {
          label: "1. Investment Overview",
          href: "/",
          match: (p) => p === "/",
        },
        {
          label: "2. Portfolio Manager",
          href: "/portfolio",
          match: (p) => p.startsWith("/portfolio"),
        },
        {
          label: "6. Position Management",
          href: "/positions",
          match: (p) => p.startsWith("/positions"),
        },
      ],
    },
    {
      label: "Research & Decisions",
      items: [
        {
          label: "3. Opportunity Discovery",
          href: "/discovery",
          match: (p) => p.startsWith("/discovery"),
        },
        {
          label: "4. Stock Research",
          href: "/stocks",
          match: (p) => p.startsWith("/stocks"),
        },
        {
          label: "5. Decision Workspace",
          href: "/decisions",
          match: (p) => p.startsWith("/decisions"),
        },
      ],
    },
    {
      label: "Evaluation & Integrity",
      items: [
        {
          label: "7. Performance & Attribution",
          href: "/attribution",
          match: (p) => p.startsWith("/attribution"),
        },
        {
          label: "8. Research Lab",
          href: "/research-lab",
          match: (p) => p.startsWith("/research-lab") || p.startsWith("/research"),
        },
        {
          label: "9. Data & Account Health",
          href: "/health",
          match: (p) => p.startsWith("/health"),
          tag: health ? String(health.rules_blocker_count) : "72",
        },
      ],
    },
  ];

  const activeLabel =
    title ||
    clusters
      .flatMap((c) => c.items)
      .find((item) => item.match(pathname))?.label ||
    "BVMT Terminal V2";

  const cutoffLabel = health?.latest_session ? `${health.latest_session} EOD` : "2026-11-18 EOD";

  return (
    <div className="flex min-h-screen w-full bg-[#F8F9FA] text-[#0F172A]">
      {drawerOpen ? (
        <div
          className="fixed inset-0 z-40 bg-[#0F172A]/35 lg:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden="true"
        />
      ) : null}

      <aside
        aria-label="Primary V2 Navigation"
        className={`fixed inset-y-0 left-0 z-50 flex w-[248px] shrink-0 flex-col border-r border-[#E2E8F0] bg-[#FFFFFF] px-3.5 py-5 transition-transform duration-150 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 lg:overflow-y-auto ${
          drawerOpen ? "translate-x-0 shadow-xl" : "-translate-x-full"
        }`}
      >
        <div className="mb-4 flex items-center justify-between border-b border-[#E2E8F0] px-2 pb-4">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-[#0F766E] text-[12px] font-bold tracking-wide text-white">
              BV
            </div>
            <div className="min-w-0">
              <div className="truncate text-[14px] font-semibold leading-tight text-[#0F172A]">
                BVMT Terminal V2
              </div>
              <div className="truncate text-[11px] text-[#64748B]">
                Manual Research &amp; Risk
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setDrawerOpen(false)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#CBD5E1] text-[#334155] lg:hidden"
            aria-label="Close navigation menu"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto">
          {clusters.map((cluster) => (
            <div key={cluster.label}>
              <div className="px-2.5 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-[#64748B]">
                {cluster.label}
              </div>
              <div className="space-y-0.5">
                {cluster.items.map((item) => {
                  const active = item.match(pathname);
                  return (
                    <Link
                      key={item.href}
                      href={withModeHref(item.href)}
                      onClick={() => setDrawerOpen(false)}
                      className={`flex items-center justify-between gap-2 rounded-md border px-2.5 py-2 text-[13px] font-medium transition-colors ${
                        active
                          ? "border-[#99F6E4] bg-[#F0FDFA] font-semibold text-[#0F766E]"
                          : "border-transparent text-[#334155] hover:bg-[#F1F5F9] hover:text-[#0F172A]"
                      }`}
                    >
                      <span className="truncate">{item.label}</span>
                      {item.tag ? (
                        <span className="shrink-0 rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[10px] font-semibold text-[#64748B] mono-num">
                          {item.tag}
                        </span>
                      ) : null}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="mt-4 border-t border-[#E2E8F0] px-2 pt-3 text-[11.5px] leading-relaxed text-[#64748B]">
          <div className="font-semibold text-[#334155]">100% Localhost &amp; Manual</div>
          <div>Zero auto-orders &middot; Live LLM spend disabled (0).</div>
          <div>EOD marks are never executable quotes.</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-[56px] flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] bg-[#FFFFFF] px-4 py-2.5 lg:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="inline-flex min-h-[38px] items-center gap-1.5 rounded-md border border-[#CBD5E1] bg-white px-2.5 py-1.5 text-[12.5px] font-semibold text-[#0F172A] lg:hidden"
              aria-label="Open navigation menu"
            >
              <Menu className="h-4 w-4" />
              <span>Menu</span>
            </button>
            <div className="truncate text-[12.5px] text-[#64748B]">
              <span>BVMT V2 / </span>
              <strong className="font-semibold text-[#0F172A]">{activeLabel}</strong>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded border border-[#E2E8F0] bg-[#F8F9FA] px-2.5 py-1 text-[11.5px] font-medium text-[#334155]">
              <span>Cutoff:</span>
              <strong className="mono-num font-semibold text-[#0F172A]">{cutoffLabel}</strong>
              <span className="text-[#64748B]">(Not Live)</span>
            </span>

            {mode === "SYNTHETIC_DEMO" ? (
              <span className="inline-flex items-center gap-1 rounded border border-[#DDD6FE] bg-[#F5F3FF] px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#5B21B6]">
                <CheckCircle2 className="h-3 w-3" />
                Sandbox Fixture
              </span>
            ) : accountTruthState === "CONFLICTED" ? (
              <span className="inline-flex items-center gap-1 rounded border border-[#FDE68A] bg-[#FFFBEB] px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#92400E]">
                <AlertTriangle className="h-3 w-3" />
                Account Conflict
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded border border-[#FECACA] bg-[#FEF2F2] px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#991B1B]">
                <ShieldAlert className="h-3 w-3" />
                {accountTruthState}
              </span>
            )}

            <select
              aria-label="Workspace mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as Mode)}
              className="min-h-[36px] rounded-md border border-[#CBD5E1] bg-white px-2.5 py-1 text-[11.5px] font-semibold text-[#0F172A] focus:border-[#0F766E] focus:outline-none"
            >
              <option value="REAL_COMPETITION">REAL_COMPETITION</option>
              <option value="SYNTHETIC_DEMO">SYNTHETIC_DEMO</option>
            </select>
          </div>
        </header>

        {mode === "SYNTHETIC_DEMO" ? (
          <div className="border-b border-[#DDD6FE] bg-[#F5F3FF] px-4 py-2 text-[12.5px] font-medium text-[#5B21B6] lg:px-6">
            <strong>SYNTHETIC DEMO MODE</strong> &mdash; Illustrative fixture sandbox only. Real
            competition ledger and rules remain isolated and untouched.
          </div>
        ) : null}

        <main className="mx-auto w-full max-w-[1220px] min-w-0 flex-1 px-4 py-5 lg:px-6 lg:py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
