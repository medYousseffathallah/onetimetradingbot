"use client";

import React, { useEffect, useState } from "react";
import { ArrowLeftRight, Clock, ShieldAlert } from "lucide-react";
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
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            Transactions & Pending Orders
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Read-only audit log of executed competition movements (display_histo.aspx) and manual
            order journal entries.
          </p>
        </div>
        <Badge variant="info" className="gap-1.5">
          <ShieldAlert className="h-3.5 w-3.5" />
          Manual Execution Only (0.50% Buy / 0.50% Sell Fee)
        </Badge>
      </div>

      {/* Pending Orders */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Open & Pending Orders</CardTitle>
              <CardDescription className="mt-1">
                Active working orders captured from your competition account or local journal
              </CardDescription>
            </div>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-xs text-slate-400 py-4">Loading pending orders...</p>
          ) : pendingData && pendingData.pending_orders.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-2 font-medium">Order ID</th>
                    <th className="pb-2 font-medium">Symbol</th>
                    <th className="pb-2 font-medium">Side</th>
                    <th className="pb-2 font-medium text-right">Requested</th>
                    <th className="pb-2 font-medium text-right">Filled</th>
                    <th className="pb-2 font-medium text-right">Remaining</th>
                    <th className="pb-2 font-medium text-right">Limit Price</th>
                    <th className="pb-2 font-medium">Submitted At</th>
                    <th className="pb-2 font-medium text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {pendingData.pending_orders.map((o) => (
                    <tr key={o.order_id} className="hover:bg-slate-800/30">
                      <td className="py-2.5 font-mono text-slate-200">{o.order_id}</td>
                      <td className="py-2.5 font-semibold text-slate-100">{o.symbol}</td>
                      <td className="py-2.5">
                        <Badge variant={o.side === "BUY" ? "success" : "danger"}>{o.side}</Badge>
                      </td>
                      <td className="py-2.5 text-right font-mono">{o.requested_shares}</td>
                      <td className="py-2.5 text-right font-mono">{o.filled_shares}</td>
                      <td className="py-2.5 text-right font-mono">{o.remaining_shares}</td>
                      <td className="py-2.5 text-right font-mono">
                        {formatTnd(o.limit_price_tnd)}
                      </td>
                      <td className="py-2.5 text-slate-300">{formatTimestamp(o.submitted_at)}</td>
                      <td className="py-2.5 text-right">
                        <Badge variant="warning">{o.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-4">
              Zero open or pending orders currently working.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Executed Transactions */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Executed Transaction History</CardTitle>
              <CardDescription className="mt-1">
                Verified trade executions and fee ledger
              </CardDescription>
            </div>
            <ArrowLeftRight className="h-4 w-4 text-emerald-400" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-xs text-slate-400 py-4">Loading executed transactions...</p>
          ) : txData && txData.transactions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-2 font-medium">Transaction ID</th>
                    <th className="pb-2 font-medium">Symbol</th>
                    <th className="pb-2 font-medium">Side</th>
                    <th className="pb-2 font-medium text-right">Shares</th>
                    <th className="pb-2 font-medium text-right">Exec. Price</th>
                    <th className="pb-2 font-medium text-right">Gross Amount</th>
                    <th className="pb-2 font-medium text-right">Fee (TND)</th>
                    <th className="pb-2 font-medium">Executed At</th>
                    <th className="pb-2 font-medium text-right">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {txData.transactions.map((t) => {
                    const gross = t.filled_shares * parseFloat(t.execution_price_tnd || "0");
                    return (
                      <tr key={t.transaction_id} className="hover:bg-slate-800/30">
                        <td className="py-2.5 font-mono text-slate-200">{t.transaction_id}</td>
                        <td className="py-2.5 font-semibold text-slate-100">{t.symbol}</td>
                        <td className="py-2.5">
                          <Badge variant={t.side === "BUY" ? "success" : "danger"}>{t.side}</Badge>
                        </td>
                        <td className="py-2.5 text-right font-mono">{t.filled_shares}</td>
                        <td className="py-2.5 text-right font-mono">
                          {formatTnd(t.execution_price_tnd)}
                        </td>
                        <td className="py-2.5 text-right font-mono font-semibold">
                          {formatTnd(gross)}
                        </td>
                        <td className="py-2.5 text-right font-mono text-slate-400">
                          {formatTnd(t.fee_tnd)}
                        </td>
                        <td className="py-2.5 text-slate-300">{formatTimestamp(t.executed_at)}</td>
                        <td className="py-2.5 text-right">
                          <Badge variant="outline">{t.source}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-4">
              No executed transactions recorded in the current ledger snapshot.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
