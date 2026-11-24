"use client";

import type { MarketObservation } from "@/lib/v2-api";
import { formatInteger, formatTnd, parseDecimal } from "@/lib/format";

export function EodPriceChart({ bars }: { bars: MarketObservation[] }) {
  const validBars = bars
    .map((bar) => ({
      bar,
      close: parseDecimal(bar.close_tnd.value),
      untraded: bar.status.toLowerCase() !== "traded" || bar.volume_shares === 0,
    }))
    .filter((item) => item.close !== null);

  if (validBars.length === 0) {
    return (
      <div className="rounded-md border border-[#E2E8F0] bg-[#F8F9FA] p-6 text-center text-[13px] text-[#64748B]">
        No observed EOD close observations available for charting.
      </div>
    );
  }

  const width = 680;
  const height = 240;
  const padLeft = 56;
  const padRight = 16;
  const padTop = 18;
  const priceHeight = 136;
  const volTop = 172;
  const volHeight = 46;

  const closes = validBars.map((item) => item.close as number);
  const minClose = Math.min(...closes);
  const maxClose = Math.max(...closes);
  const closeSpan = Math.max(maxClose - minClose, 0.01);
  const maxVol = Math.max(...validBars.map((item) => item.bar.volume_shares), 1);

  const plotWidth = width - padLeft - padRight;
  const stepX = validBars.length > 1 ? plotWidth / (validBars.length - 1) : 0;

  const points = validBars.map((item, idx) => {
    const x = validBars.length > 1 ? padLeft + idx * stepX : padLeft + plotWidth / 2;
    const y = padTop + priceHeight - (((item.close as number) - minClose) / closeSpan) * priceHeight;
    return { ...item, x, y };
  });

  const polylinePoints = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const barWidth = Math.max(3, Math.min(10, plotWidth / Math.max(validBars.length, 1) - 2));

  const midClose = (minClose + maxClose) / 2;
  const firstSession = validBars[0].bar.session_date;
  const lastSession = validBars[validBars.length - 1].bar.session_date;
  const untradedCount = validBars.filter((p) => p.untraded).length;

  return (
    <div className="w-full min-w-0">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="block h-auto w-full"
        role="img"
        aria-label={`EOD Close and Volume chart from ${firstSession} to ${lastSession}`}
      >
        {[minClose, midClose, maxClose].map((tick, idx) => {
          const y = padTop + priceHeight - ((tick - minClose) / closeSpan) * priceHeight;
          return (
            <g key={idx}>
              <line
                x1={padLeft}
                y1={y}
                x2={width - padRight}
                y2={y}
                stroke="#E2E8F0"
                strokeDasharray="3 3"
              />
              <text
                x={padLeft - 6}
                y={y + 3.5}
                textAnchor="end"
                fontSize="10"
                fontFamily="JetBrains Mono, monospace"
                fill="#64748B"
              >
                {tick.toFixed(3)}
              </text>
            </g>
          );
        })}

        <line
          x1={padLeft}
          y1={volTop + volHeight}
          x2={width - padRight}
          y2={volTop + volHeight}
          stroke="#CBD5E1"
        />

        {points.map((p) => {
          const vh = (p.bar.volume_shares / maxVol) * volHeight;
          return (
            <rect
              key={`vol-${p.bar.session_date}`}
              x={p.x - barWidth / 2}
              y={volTop + volHeight - vh}
              width={barWidth}
              height={Math.max(vh, p.untraded ? 2 : 1)}
              fill={p.untraded ? "#F59E0B" : "#CBD5E1"}
              rx={1}
            >
              <title>
                {`${p.bar.session_date}: Close ${formatTnd(p.bar.close_tnd.value)} | Vol ${formatInteger(p.bar.volume_shares)} sh | Status: ${p.bar.status}`}
              </title>
            </rect>
          );
        })}

        <polyline
          fill="none"
          stroke="#0F766E"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={polylinePoints}
        />

        {points.map((p) =>
          p.untraded ? (
            <circle
              key={`ut-${p.bar.session_date}`}
              cx={p.x}
              cy={p.y}
              r={3.5}
              fill="#FFFBEB"
              stroke="#D97706"
              strokeWidth="1.5"
            >
              <title>{`${p.bar.session_date}: UNTRADED / 0 vol (${formatTnd(p.bar.close_tnd.value)})`}</title>
            </circle>
          ) : null,
        )}

        <text
          x={padLeft}
          y={height - 4}
          fontSize="10"
          fontFamily="JetBrains Mono, monospace"
          fill="#64748B"
        >
          {firstSession}
        </text>
        <text
          x={width - padRight}
          y={height - 4}
          textAnchor="end"
          fontSize="10"
          fontFamily="JetBrains Mono, monospace"
          fill="#64748B"
        >
          {lastSession}
        </text>
      </svg>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11.5px] text-[#64748B]">
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-4 rounded-sm bg-[#0F766E]" />
            EOD Close (TND)
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full border border-[#D97706] bg-[#FFFBEB]" />
            Zero-Vol / Untraded ({untradedCount})
          </span>
        </div>
        <span className="mono-num">
          Range: {minClose.toFixed(3)} &ndash; {maxClose.toFixed(3)} TND ({validBars.length} sessions)
        </span>
      </div>
    </div>
  );
}
