import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTnd(val: string | number | null | undefined): string {
  if (val === null || val === undefined || val === "") return "0.000 TND";
  const num = typeof val === "number" ? val : parseFloat(String(val));
  if (Number.isNaN(num)) return `${val} TND`;
  return `${num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 3,
  })} TND`;
}

export function formatPct(val: string | number | null | undefined, signed = true): string {
  if (val === null || val === undefined || val === "") return "0.00%";
  const num = typeof val === "number" ? val : parseFloat(String(val));
  if (Number.isNaN(num)) return `${val}%`;
  const prefix = signed && num > 0 ? "+" : "";
  return `${prefix}${num.toFixed(2)}%`;
}

export function formatTimestamp(ts: string | null | undefined): string {
  if (!ts) return "Not yet synchronized";
  try {
    const dt = new Date(ts);
    if (Number.isNaN(dt.getTime())) return ts;
    return dt.toLocaleString("en-GB", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return ts;
  }
}
