"use client";

import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
} from "recharts";
import type { StrategyEvaluationReport } from "@/lib/api";

export interface StrategyComparisonDatum {
  strategy: string;
  NetReturn: number;
  EqualBudget10SlotReturn: number;
  ExSotetelReturn: number;
}

export function StrategyEquityChart({
  selectedReport,
}: {
  selectedReport: StrategyEvaluationReport;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={selectedReport.equity_curve}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="session_date"
          stroke="#94a3b8"
          fontSize={11}
          minTickGap={28}
        />
        <YAxis
          stroke="#94a3b8"
          fontSize={11}
          domain={["auto", "auto"]}
          tickFormatter={(v) => `${(Number(v) / 1000).toFixed(1)}k`}
        />
        <RechartsTooltip
          contentStyle={{
            backgroundColor: "#0f172a",
            borderColor: "#334155",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "12px" }} />
        <Line
          type="monotone"
          name={`${selectedReport.strategy_id} Equity (TND)`}
          dataKey="total_equity_tnd"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          name="Benchmark C Equity (TND)"
          dataKey="benchmark_equity_tnd"
          stroke="#64748b"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function StrategyComparisonBarChart({
  data,
}: {
  data: StrategyComparisonDatum[];
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="strategy" stroke="#94a3b8" fontSize={10} interval={0} />
        <YAxis stroke="#94a3b8" fontSize={11} unit="%" />
        <RechartsTooltip
          contentStyle={{
            backgroundColor: "#0f172a",
            borderColor: "#334155",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "12px" }} />
        <Bar name="5-Slot Raw (%)" dataKey="NetReturn" fill="#10b981" />
        <Bar name="10-Slot Equal Budget (%)" dataKey="EqualBudget10SlotReturn" fill="#38bdf8" />
        <Bar name="Ex-SOTETEL (%)" dataKey="ExSotetelReturn" fill="#f59e0b" />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function StrategyDrawdownChart({
  selectedReport,
}: {
  selectedReport: StrategyEvaluationReport;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={selectedReport.equity_curve}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="session_date"
          stroke="#94a3b8"
          fontSize={10}
          minTickGap={32}
        />
        <YAxis stroke="#94a3b8" fontSize={10} unit="%" />
        <RechartsTooltip
          contentStyle={{
            backgroundColor: "#0f172a",
            borderColor: "#334155",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Area
          type="monotone"
          name="Drawdown (%)"
          dataKey="drawdown_pct"
          stroke="#f59e0b"
          fill="#f59e0b"
          fillOpacity={0.2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

