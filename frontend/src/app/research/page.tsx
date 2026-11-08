"use client";

import React, { useEffect, useState } from "react";
import { FileSearch, BookOpen, CheckCircle2, Search, Info } from "lucide-react";
import { api, ResearchResponse } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { MetricHelp } from "@/components/ui/metric-help";
import { usePortfolioMode } from "@/components/app-shell";

export default function StockResearchPage() {
  const { mode, refreshTrigger } = usePortfolioMode();
  const [query, setQuery] = useState("");
  const [data, setData] = useState<ResearchResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const runSearch = (qStr: string) => {
    setLoading(true);
    api
      .getResearch(qStr, mode)
      .then((res) => setData(res))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    runSearch(query);
  }, [mode, refreshTrigger]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Stock Research & Disclosures
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Evidence-linked company, CMF, and macroeconomic disclosures with verbatim quote
            verification.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="info" className="py-1 px-3">
            Point-in-Time Verified Disclosures
          </Badge>
          <MetricHelp metricId="source_provenance" />
        </div>
      </div>

      {/* Document Search Bar */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Search className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <span>Financial Disclosure & CMF Document Search</span>
          </CardTitle>
          <CardDescription>
            Search local indexed company reports, CMF notices, and earnings disclosures (e.g. dividende, PNB, BH)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              runSearch(query);
            }}
            className="flex gap-2"
          >
            <input
              type="text"
              placeholder="Search disclosures (e.g. dividende, PNB, modernisation, BH)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none"
            />
            <Button type="submit" variant="primary" size="md">
              Search Corpus
            </Button>
          </form>

          {loading ? (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-4 text-center">
              Searching local document index...
            </p>
          ) : data && data.document_results.length > 0 ? (
            <div className="space-y-3">
              {data.document_results.map((doc) => (
                <div
                  key={doc.chunk_id}
                  className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-4 space-y-2"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        {doc.source_document_id}
                      </span>
                      {doc.instrument_ids.map((id) => (
                        <Badge key={id} variant="outline">
                          {id}
                        </Badge>
                      ))}
                    </div>
                    <span className="text-slate-500 dark:text-slate-400">
                      {formatTimestamp(doc.published_at)}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
                    {doc.chunk_text}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-4 text-center">
              No matching document chunks found.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Verified Event Signals */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileSearch className="h-4 w-4 text-teal-600 dark:text-teal-400" />
              <span>Verified Corporate Event Signals</span>
            </CardTitle>
            <MetricHelp
              title="Verified Corporate Catalysts"
              category="governance"
              plainDefinition="Corporate events extracted from authorized French/Arabic company releases with verified verbatim quotes."
              whyItMatters="Ensures trading decisions account for recent dividends, earnings releases, and regulatory sanctions without relying on unverified rumors."
              formula="Verbatim quote match against SHA-256 snapshotted CMF/BVMT documents"
              interpretation="Positive = favorable corporate development. Negative = regulatory caution or earnings decline."
              limitations="Does not generate autonomous buy/sell orders; events serve as decision-support evidence only."
              docLink="docs/SIGNAL_METHODOLOGY.md"
            />
          </div>
          <CardDescription>
            Structured corporate catalysts with cryptographic verbatim quote verification
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data && data.verified_events.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.verified_events.map((ev) => (
                <div
                  key={ev.event_id}
                  className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-4 space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="info">{ev.instrument_id}</Badge>
                      <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {ev.event_type}
                      </span>
                    </div>
                    <Badge
                      variant={
                        ev.polarity === "positive"
                          ? "success"
                          : ev.polarity === "negative"
                          ? "danger"
                          : "default"
                      }
                    >
                      {ev.polarity.toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-sm text-slate-900 dark:text-slate-100 font-medium">
                    {ev.summary}
                  </p>
                  <blockquote className="border-l-2 border-teal-500 pl-3 text-xs italic text-slate-600 dark:text-slate-400">
                    “{ev.verbatim_quote}”
                  </blockquote>
                  <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 pt-1">
                    <span>Source: {ev.source_document_id}</span>
                    {ev.quote_verified && (
                      <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Quote Verified
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">
              No verified event signals loaded.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
