"use client";

import React, { useEffect, useState } from "react";
import { ArrowLeftRight, Clock, ShieldAlert, CheckCircle2 } from "lucide-react";
import { api, TransactionsResponse, PendingOrdersResponse } from "@/lib/api";
import { formatTnd, formatTimestamp } from "@/lib/utils";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";
import { usePortfolioMode } from "@/components/app-shell";

export default function TransactionsPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [txData, setTxData] = useState<TransactionsResponse | null>(null);
  const [pendingData, setPendingData] = useState<PendingOrdersResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.getTransactions(mode), api.getPendingOrders(mode)])
      .then(([tx, pd]) => {
        setTxData(tx);
        setPendingData(pd);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mode, refreshTrigger]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Transactions & Orders
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Audit log of executed competition movements (display_histo.aspx) and pending order
            watchdog tracking.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="info" className="gap-1.5 py-1 px-3">
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>Manual Execution (0.50% Official Fee)</span>
          </Badge>
          <MetricHelp metricId="transaction_fees" />
        </div>
      </div>

      {/* Pending Orders */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Open & Pending Working Orders</CardTitle>
              <CardDescription className="mt-1">
                Active orders captured from your competition account (display_histo.aspx)
              </CardDescription>
            </div>
            <Clock className="h-4 w-4 text-amber-500" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">
              Loading pending orders...
            </p>
          ) : pendingData && pendingData.pending_orders.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 dark:bg-slate-900 text-xs text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-3 font-semibold">Order ID</th>
                    <th className="py-3 px-3 font-semibold">Symbol</th>
                    <th className="py-3 px-3 font-semibold">Side</th>
                    <th className="py-3 px-3 font-semibold text-right">Requested</th>
                    <th className="py-3 px-3 font-semibold text-right">Filled</th>
                    <th className="py-3 px-3 font-semibold text-right">Remaining</th>
                    <th className="py-3 px-3 font-semibold text-right">Limit Price</th>
                    <th className="py-3 px-3 font-semibold">Submitted At</th>
                    <th className="py-3 px-3 font-semibold text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {pendingData.pending_orders.map((o) => (
                    <tr key={o.order_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="py-3 px-3 font-mono text-xs text-slate-600 dark:text-slate-400">
                        {o.order_id}
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-900 dark:text-slate-100">
                        {o.symbol}
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant={o.side === "BUY" ? "success" : "danger"}>{o.side}</Badge>
                      </td>
                      <td className="py-3 px-3 text-right font-mono">{o.requested_shares}</td>
                      <td className="py-3 px-3 text-right font-mono">{o.filled_shares}</td>
                      <td className="py-3 px-3 text-right font-mono font-medium">{o.remaining_shares}</td>
                      <td className="py-3 px-3 text-right font-mono">
                        {formatTnd(o.limit_price_tnd)}
                      </td>
                      <td className="py-3 px-3 text-slate-600 dark:text-slate-300 text-xs">
                        {formatTimestamp(o.submitted_at)}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Badge variant="warning">{o.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">
              <CheckCircle2 className="h-6 w-6 mx-auto text-emerald-500 mb-1" />
              <span>No open pending orders. All past orders have settled or executed.</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Executed Transactions Log */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Historical Execution Movements</CardTitle>
              <CardDescription className="mt-1">
                Completed trades on tunisbourse-challenge.com with exact reported execution prices
                and 0.50% fees
              </CardDescription>
            </div>
            <ArrowLeftRight className="h-4 w-4 text-teal-600 dark:text-teal-400" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">
              Loading executed movements...
            </p>
          ) : txData && txData.transactions.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 dark:bg-slate-900 text-xs text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-3 font-semibold">Transaction ID</th>
                    <th className="py-3 px-3 font-semibold">Executed At</th>
                    <th className="py-3 px-3 font-semibold">Symbol</th>
                    <th className="py-3 px-3 font-semibold">Side</th>
                    <th className="py-3 px-3 font-semibold text-right">Shares</th>
                    <th className="py-3 px-3 font-semibold text-right">Fill Price</th>
                    <th className="py-3 px-3 font-semibold text-right">Gross Amount</th>
                    <th className="py-3 px-3 font-semibold text-right">Fee (0.50%)</th>
                    <th className="py-3 px-3 font-semibold text-right">Provenance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {txData.transactions.map((t) => {
                    const gross =
                      parseFloat(t.filled_shares.toString()) * parseFloat(t.execution_price_tnd);
                    return (
                      <tr key={t.transaction_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                        <td className="py-3 px-3 font-mono text-xs text-slate-600 dark:text-slate-400">
                          {t.transaction_id}
                        </td>
                        <td className="py-3 px-3 text-slate-600 dark:text-slate-300 text-xs">
                          {formatTimestamp(t.executed_at)}
                        </td>
                        <td className="py-3 px-3 font-semibold text-slate-900 dark:text-slate-100">
                          {t.symbol}
                        </td>
                        <td className="py-3 px-3">
                          <Badge variant={t.side === "BUY" ? "success" : "danger"}>
                            {t.side}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-right font-mono font-medium">{t.filled_shares}</td>
                        <td className="py-3 px-3 text-right font-mono">
                          {formatTnd(t.execution_price_tnd)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono font-semibold text-slate-900 dark:text-slate-100">
                          {formatTnd(gross)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-rose-600 dark:text-rose-400">
                          {formatTnd(t.fee_tnd)}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <Badge variant="outline" className="text-xs">
                            {t.source}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">
              No executed transactions recorded yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
