"use client";

import React, { useEffect, useState } from "react";
import { FileSearch, BookOpen, CheckCircle2, Search } from "lucide-react";
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
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            Stock Research & Auditable Disclosures
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Evidence-linked company, CMF, and macroeconomic disclosures with verbatim quote
            verification.
          </p>
        </div>
        <Badge variant="info">Point-in-Time Verified Disclosures</Badge>
      </div>

      {/* Document Search Bar */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4 text-emerald-400" />
            <span>Financial Disclosure & CMF Document Search</span>
          </CardTitle>
          <CardDescription>
            Search local indexed French/Arabic/English company reports (e.g. dividende, PNB, BH)
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
              placeholder="Search disclosures (e.g. dividende, PNB, modernisation)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-slate-100 focus:border-emerald-500 focus:outline-none"
            />
            <Button type="submit" variant="primary" size="md">
              Search Corpus
            </Button>
          </form>

          {loading ? (
            <p className="text-xs text-slate-400">Searching local document index...</p>
          ) : data && data.document_results.length > 0 ? (
            <div className="space-y-3">
              {data.document_results.map((doc) => (
                <div
                  key={doc.chunk_id}
                  className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 space-y-2"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-3.5 w-3.5 text-sky-400" />
                      <span className="font-semibold text-slate-200">{doc.source_document_id}</span>
                      {doc.instrument_ids.map((id) => (
                        <Badge key={id} variant="outline">
                          {id}
                        </Badge>
                      ))}
                    </div>
                    <span className="text-slate-400">{formatTimestamp(doc.published_at)}</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{doc.chunk_text}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No matching document chunks found.</p>
          )}
        </CardContent>
      </Card>

      {/* Verified Event Signals */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-emerald-400" />
            <span>Verified Event Signals</span>
          </CardTitle>
          <CardDescription>
            Structured corporate catalysts with verified verbatim quotes
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data && data.verified_events.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.verified_events.map((ev) => (
                <div
                  key={ev.event_id}
                  className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="info">{ev.instrument_id}</Badge>
                      <span className="text-xs font-semibold text-slate-200">{ev.event_type}</span>
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
                  <p className="text-xs text-slate-200 font-medium">{ev.summary}</p>
                  <blockquote className="border-l-2 border-emerald-500/50 pl-3 text-[11px] italic text-slate-400">
                    “{ev.verbatim_quote}”
                  </blockquote>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                    <span>Source: {ev.source_document_id}</span>
                    {ev.quote_verified && (
                      <span className="flex items-center gap-1 text-emerald-400">
                        <CheckCircle2 className="h-3 w-3" />
                        Quote Verified
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No verified event signals loaded.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
