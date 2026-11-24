import type { Horizon, ProvenanceValue } from "./v2-api";

export function parseDecimal(raw: string | null | undefined): number | null {
  if (raw === null || raw === undefined || raw.trim() === "") {
    return null;
  }
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function formatDecimalString(
  raw: string | null | undefined,
  decimals: number,
  options?: { signed?: boolean },
): string {
  if (raw === null || raw === undefined || raw.trim() === "") {
    return "Unavailable";
  }
  const trimmed = raw.trim();
  const isNeg = trimmed.startsWith("-");
  const unsigned = isNeg || trimmed.startsWith("+") ? trimmed.slice(1) : trimmed;
  if (!/^\d+(?:\.\d+)?$/.test(unsigned)) {
    const n = Number(trimmed);
    if (!Number.isFinite(n)) return "Unavailable";
    const formatted = Math.abs(n).toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    if (n < 0) return `-${formatted}`;
    if (options?.signed && n > 0) return `+${formatted}`;
    return formatted;
  }

  const [intPartRaw, fracPartRaw = ""] = unsigned.split(".");
  const paddedFrac = (fracPartRaw + "0".repeat(decimals + 1)).slice(0, decimals + 1);
  let roundedInt = BigInt(intPartRaw);
  let fracNum = decimals > 0 ? Number(paddedFrac.slice(0, decimals)) : 0;
  const nextDigit = Number(paddedFrac[decimals] ?? "0");
  if (nextDigit >= 5) {
    fracNum += 1;
    const base = 10 ** decimals;
    if (fracNum >= base) {
      fracNum = 0;
      roundedInt += 1n;
    }
  }

  const intFormatted = roundedInt.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const body =
    decimals > 0
      ? `${intFormatted}.${String(fracNum).padStart(decimals, "0")}`
      : intFormatted;

  const isZero = roundedInt === 0n && fracNum === 0;
  if (isNeg && !isZero) return `-${body}`;
  if (options?.signed && !isNeg && !isZero) return `+${body}`;
  return body;
}

export function formatTnd(
  raw: string | null | undefined,
  options?: { signed?: boolean; withUnit?: boolean },
): string {
  const formatted = formatDecimalString(raw, 3, { signed: options?.signed });
  if (formatted === "Unavailable") return formatted;
  return options?.withUnit === false ? formatted : `${formatted} TND`;
}

export function formatPct(
  raw: string | null | undefined,
  options?: { signed?: boolean; fromRatio?: boolean },
): string {
  const num = parseDecimal(raw);
  if (num === null) return "Unavailable";
  const pct = options?.fromRatio ? num * 100 : num;
  const formatted = Math.abs(pct).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (pct < 0) return `-${formatted}%`;
  if (options?.signed && pct > 0) return `+${formatted}%`;
  return `${formatted}%`;
}

export function formatInteger(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "Unavailable";
  return Math.trunc(n).toLocaleString("en-US");
}

export function formatProvenanceNumber(
  pv: ProvenanceValue | null | undefined,
  options?: { signed?: boolean; asPctFromRatio?: boolean; withUnit?: boolean },
): string {
  if (!pv || pv.status === "UNAVAILABLE" || pv.value === null) {
    return "Unavailable";
  }
  if (pv.unit === "TND") {
    return formatTnd(pv.value, {
      signed: options?.signed,
      withUnit: options?.withUnit ?? true,
    });
  }
  if (pv.unit === "PCT") {
    return formatPct(pv.value, { signed: options?.signed, fromRatio: false });
  }
  if (pv.unit === "RATIO") {
    if (options?.asPctFromRatio ?? true) {
      return formatPct(pv.value, { signed: options?.signed, fromRatio: true });
    }
    return formatDecimalString(pv.value, 4, { signed: options?.signed });
  }
  if (pv.unit === "SHARES") {
    const n = parseDecimal(pv.value);
    if (n === null) return "Unavailable";
    return `${formatInteger(Math.round(n))}${options?.withUnit === false ? "" : " sh"}`;
  }
  if (pv.unit === "SESSIONS") {
    const formatted = formatDecimalString(pv.value, 1, { signed: options?.signed });
    return `${formatted}${options?.withUnit === false ? "" : " sessions"}`;
  }
  return formatDecimalString(pv.value, 3, { signed: options?.signed });
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "Unavailable";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

export const HORIZON_LABELS: Record<Horizon, string> = {
  "1_2": "1–2 Sessions",
  "3_5": "3–5 Sessions",
  "5_10": "5–10 Sessions",
  "10_20": "10–20 Sessions",
  "20_60": "20–60 Sessions",
};

export const FAMILY_LABELS: Record<string, string> = {
  "BL-CASH": "Baseline · Cash (0.00%)",
  "BL-EW-CHAL": "Baseline · Equal-Weight Challenge",
  "BL-EW-FULL": "Baseline · Equal-Weight Full BVMT",
  "BL-MOM20": "Baseline · Simple 20s Momentum",
  "LEGACY-G-APPROX": "Legacy Reference · 20s Rotation",
  "V2-D-MOM-RISK": "V2-D · Risk-Bounded Momentum",
  "V2-F-LIQ-TREND": "V2-F · Liquidity-Screened Trend",
  "V2-H-PULLBACK": "V2-H · Pullback in Uptrend",
  "V2-G-AWAKENING": "V2-G · Liquidity Awakening",
};

export const EXIT_POLICY_LABELS: Record<string, string> = {
  fixed_horizon: "Fixed Horizon (Hold to End)",
  trend_deterioration: "Trend Deterioration (5s < 0)",
  trailing_profit_5pct: "Trailing Profit Stop (5%)",
  trailing_profit_8pct: "Trailing Profit Stop (8%)",
  volatility_adjusted_exit: "Volatility-Adjusted Stop (3σ)",
  partial_profit_trim: "Partial Profit Trim (+5% Half)",
  time_stop: "Time Stop (Midpoint Flat/Down)",
  opportunity_rotation: "Opportunity Rotation (Rank Loss)",
  combined_risk_trend: "Combined Risk & Trend Stop",
};

export function toDecimalInputString(raw: string | null | undefined, fallback = "10.000"): string {
  const n = parseDecimal(raw);
  if (n === null || n <= 0) return fallback;
  return n.toFixed(3);
}
