"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { v2Api, type HealthResponse, type Mode } from "@/lib/v2-api";

interface ModeContextValue {
  mode: Mode;
  setMode: (next: Mode) => void;
  withModeHref: (path: string) => string;
  health: HealthResponse | null;
  accountTruthState: "CONFLICTED" | "UNVERIFIED" | "VERIFIED";
  setAccountTruthState: (next: "CONFLICTED" | "UNVERIFIED" | "VERIFIED") => void;
}

const ModeContext = createContext<ModeContextValue | null>(null);

function normalizeMode(raw: string | null): Mode {
  return raw === "SYNTHETIC_DEMO" ? "SYNTHETIC_DEMO" : "REAL_COMPETITION";
}

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const urlMode = normalizeMode(searchParams.get("mode"));
  const [mode, setModeState] = useState<Mode>(urlMode);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [accountTruthState, setAccountTruthState] = useState<
    "CONFLICTED" | "UNVERIFIED" | "VERIFIED"
  >("CONFLICTED");

  useEffect(() => {
    setModeState(urlMode);
  }, [urlMode]);

  useEffect(() => {
    let cancelled = false;
    setAccountTruthState(mode === "SYNTHETIC_DEMO" ? "UNVERIFIED" : "CONFLICTED");
    v2Api
      .getHealth(mode)
      .then((res) => {
        if (!cancelled) setHealth(res);
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const setMode = useCallback(
    (next: Mode) => {
      setModeState(next);
      const params = new URLSearchParams(searchParams.toString());
      if (next === "REAL_COMPETITION") {
        params.delete("mode");
      } else {
        params.set("mode", next);
      }
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const withModeHref = useCallback(
    (path: string) => {
      if (mode !== "SYNTHETIC_DEMO") return path;
      return path.includes("?")
        ? `${path}&mode=SYNTHETIC_DEMO`
        : `${path}?mode=SYNTHETIC_DEMO`;
    },
    [mode],
  );

  const value = useMemo<ModeContextValue>(
    () => ({
      mode,
      setMode,
      withModeHref,
      health,
      accountTruthState,
      setAccountTruthState,
    }),
    [mode, setMode, withModeHref, health, accountTruthState],
  );

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode(): ModeContextValue {
  const ctx = useContext(ModeContext);
  if (!ctx) {
    throw new Error("useMode must be used inside ModeProvider");
  }
  return ctx;
}
