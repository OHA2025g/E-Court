import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import Card from "@/components/Card";
import { barSeriesProps, lineSeriesProps, seriesLegendLabel, useAccessibleRag } from "@/lib/ragColors";
import {
  ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend, LabelList,
} from "recharts";

function ParetoTooltip({ active, payload, label, barLabel }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="font-semibold text-slate-800 mb-1.5">{label}</div>
      <div className="text-slate-700">{barLabel}: <span className="font-semibold tabular-nums">{row.red_count ?? "—"}</span></div>
      <div className="text-slate-700">% of total: <span className="font-semibold tabular-nums">{row.pct_of_total ?? "—"}%</span></div>
      <div className="text-slate-700">Cumulative: <span className="font-semibold tabular-nums">{row.cumulative_pct ?? "—"}%</span></div>
    </div>
  );
}

export default function ParetoChart({ reportingPeriod, highCourt = "", component = "", publicMode = false, embedData = null }) {
  const [accessible] = useAccessibleRag();
  const [metric, setMetric] = useState("physical");
  const { data: fetched, isLoading } = useQuery({
    queryKey: ["pareto", reportingPeriod, highCourt, component, metric, publicMode],
    queryFn: () => api.get(`${publicMode ? "/public" : "/dashboard"}/pareto-red-flags`, {
      params: {
        ...(reportingPeriod ? { reporting_period: reportingPeriod } : {}),
        ...(highCourt ? { high_court: highCourt } : {}),
        ...(component ? { component } : {}),
        metric,
      },
    }).then(r => r.data),
    enabled: !embedData || metric !== "physical",
  });
  const data = embedData && metric === "physical" ? embedData : fetched;

  const series = data?.series || [];
  const cutoff = data?.pareto_cutoff || 0;
  const totalRed = data?.total_red_flags ?? series.reduce((s, r) => s + (r.red_count || 0), 0);
  const isOutcome = metric === "outcome";
  const isFinancial = metric === "financial";
  const xLabel = isOutcome ? "subject" : "component";
  const barLabel = isOutcome ? "Unreported KPIs" : isFinancial ? "Red components" : "Red indicators";
  const subtitle = cutoff
    ? `Top ${cutoff} ${isOutcome ? "subject(s)" : "component(s)"} account for ≥80% of ${isOutcome ? "missing outcome values" : isFinancial ? "red financial components" : "red indicators"} (${totalRed} total)`
    : isOutcome ? "Outcome KPIs without reported values" : isFinancial ? "Financial components at RED RAG" : "Physical indicators at RED RAG";

  return (
    <Card
      title="Pareto — Red Flag Concentration"
      subtitle={subtitle}
      testId="pareto-chart"
      action={
        <div className="flex gap-1 text-[10px] uppercase tracking-wider">
          {[
            { id: "physical", label: "Physical" },
            { id: "financial", label: "Financial" },
            { id: "outcome", label: "Outcome gaps" },
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
      <div className="p-4">
        {isLoading && !data ? (
          <div className="h-64 flex items-center justify-center text-slate-400 text-sm">Loading…</div>
        ) : series.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
            {isOutcome ? "All outcome KPIs reported in this period" : isFinancial ? "No red financial flags in this period" : "No red flags in this period"}
          </div>
        ) : (
          <>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series} margin={{ top: 28, right: 20, left: 4, bottom: 60 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey={xLabel} stroke="#475569" fontSize={9} angle={-30} textAnchor="end" interval={0} height={70} />
                  <YAxis yAxisId="left" stroke="#475569" fontSize={11} label={{ value: barLabel, angle: -90, position: "insideLeft", fontSize: 10 }} />
                  <YAxis yAxisId="right" orientation="right" stroke="#475569" fontSize={11} domain={[0, 100]} unit="%" />
                  <Tooltip content={<ParetoTooltip barLabel={barLabel} />} />
                  <Legend />
                  <Bar
                    yAxisId="left"
                    dataKey="red_count"
                    name={seriesLegendLabel(barLabel, "red_count", accessible)}
                    {...barSeriesProps("red_count", accessible)}
                  >
                    <LabelList
                      dataKey="red_count"
                      position="top"
                      className="fill-slate-700"
                      fontSize={11}
                      fontWeight={600}
                    />
                  </Bar>
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="cumulative_pct"
                    name={seriesLegendLabel("Cumulative %", "cumulative_pct", accessible)}
                    dot
                    {...lineSeriesProps("cumulative_pct", accessible)}
                  >
                    <LabelList
                      dataKey="cumulative_pct"
                      position="top"
                      offset={12}
                      className="fill-slate-600"
                      fontSize={10}
                      formatter={(v) => `${v}%`}
                    />
                  </Line>
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <table className="dense-table w-full mt-4 text-xs table-fixed">
              <colgroup>
                <col className="w-[40%]" />
                <col className="w-[20%]" />
                <col className="w-[20%]" />
                <col className="w-[20%]" />
              </colgroup>
              <thead>
                <tr>
                  <th>{isOutcome ? "Subject" : "Component"}</th>
                  <th className="dense-table-right">{isOutcome ? "Missing" : "Red count"}</th>
                  <th className="dense-table-right">% of total</th>
                  <th className="dense-table-right">Cumulative</th>
                </tr>
              </thead>
              <tbody>
                {series.map((r, i) => (
                  <tr key={r[xLabel]} className={i < cutoff ? "bg-red-50/50" : ""}>
                    <td>{r[xLabel]}</td>
                    <td className="dense-table-right tabular-nums font-medium">{r.red_count}</td>
                    <td className="dense-table-right tabular-nums">{r.pct_of_total}% <span className="text-slate-500">({r.red_count})</span></td>
                    <td className="dense-table-right tabular-nums">{r.cumulative_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </Card>
  );
}
