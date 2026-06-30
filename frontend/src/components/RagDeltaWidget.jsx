import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, BACKEND_URL } from "@/lib/api";
import Card from "@/components/Card";
import { TrendUp, TrendDown } from "@phosphor-icons/react";

async function fetchPublicRagDelta(reportingPeriod, metric) {
  const params = new URLSearchParams({ metric });
  if (reportingPeriod) params.set("reporting_period", reportingPeriod);
  const r = await fetch(`${BACKEND_URL}/api/public/rag-delta?${params}`);
  if (!r.ok) throw new Error("Failed to load RAG delta");
  return r.json();
}

export default function RagDeltaWidget({ reportingPeriod, publicMode = false, embedData = null }) {
  const [metric, setMetric] = useState("physical");
  const { data: fetched, isLoading, isError } = useQuery({
    queryKey: ["rag-delta", reportingPeriod, metric, publicMode],
    queryFn: () => publicMode
      ? fetchPublicRagDelta(reportingPeriod, metric)
      : api.get("/dashboard/rag-delta", {
          params: {
            ...(reportingPeriod ? { reporting_period: reportingPeriod } : {}),
            metric,
          },
        }).then(r => r.data),
    enabled: !!reportingPeriod && !(embedData && metric === "physical"),
  });
  const data = embedData && metric === "physical" ? embedData : fetched;

  const unit = data?.unit || (metric === "outcome" ? "KPIs" : metric === "financial" ? "components" : "indicators");
  const metricLabel = metric === "outcome"
    ? "Outcome KPIs"
    : metric === "financial"
      ? "Financial components"
      : "Physical indicators";

  if (!reportingPeriod) {
    return (
      <Card title="Month-over-Month RAG Change" subtitle="Select a reporting period to compare RAG vs the prior month">
        <div className="p-4 text-sm text-slate-500">
          {publicMode ? "Comparison uses the latest reporting period with a prior month." : "Choose a specific reporting period above (not “All periods”)."}
        </div>
      </Card>
    );
  }

  if (isLoading) {
    return <Card title="Month-over-Month RAG Change"><div className="p-4 text-sm text-slate-400">Loading…</div></Card>;
  }

  if (isError || !data) {
    return (
      <Card title="Month-over-Month RAG Change">
        <div className="p-4 text-sm text-amber-700">No prior period available for comparison.</div>
      </Card>
    );
  }

  const net = data.net_green ?? 0;
  const positive = net >= 0;

  return (
    <Card
      title="Month-over-Month RAG Change"
      subtitle={`${data.previous_period} → ${data.current_period} · ${metricLabel}`}
      testId="rag-delta-widget"
      action={
        <div className="flex gap-1 text-[10px] uppercase tracking-wider">
          {[
            { id: "physical", label: "Physical" },
            { id: "financial", label: "Financial" },
            { id: "outcome", label: "Outcome" },
          ].map(m => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMetric(m.id)}
              className={`px-2 py-1 rounded-sm border ${metric === m.id ? "bg-[#003B73] text-white border-[#003B73]" : "bg-white text-slate-600 border-slate-300"}`}
            >
              {m.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="p-4 flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-3">
          {positive
            ? <TrendUp size={32} weight="bold" className="text-emerald-600" />
            : <TrendDown size={32} weight="bold" className="text-red-600" />}
          <div>
            <div className={`text-2xl font-display font-bold ${positive ? "text-emerald-700" : "text-red-700"}`}>
              {positive ? "+" : ""}{data.turned_green} {unit} turned Green
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              Net change: {net >= 0 ? "+" : ""}{net} · {data.turned_red} turned Red · {data.turned_amber} turned Amber
            </div>
          </div>
        </div>
        <div className="text-xs text-slate-500 border-l border-slate-200 pl-6">
          <div>{data.unchanged_green} {unit} remained Green</div>
        </div>
      </div>
    </Card>
  );
}
