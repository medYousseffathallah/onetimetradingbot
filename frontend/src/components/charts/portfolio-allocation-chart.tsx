"use client";

import React from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
} from "recharts";
import { formatTnd } from "@/lib/utils";

export interface AllocationSlice {
  name: string;
  value: number;
}

export function PortfolioAllocationChart({
  data,
  colors,
}: {
  data: AllocationSlice[];
  colors: string[];
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={80}
          paddingAngle={3}
        >
          {data.map((_, idx) => (
            <Cell key={idx} fill={colors[idx % colors.length]} />
          ))}
        </Pie>
        <RechartsTooltip
          formatter={(value: number) => formatTnd(value)}
          contentStyle={{
            backgroundColor: "#ffffff",
            borderColor: "#cbd5e1",
            borderRadius: "8px",
            fontSize: "12px",
            color: "#0f172a",
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

