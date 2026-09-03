import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Info } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import Card from "@/components/Card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { barSeriesProps, lineSeriesProps, seriesLegendLabel, useAccessibleRag } from "@/lib/ragColors";
import { TID } from "@/lib/testIds";
import {
  ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, LabelList,
} from "recharts";

function ParetoTooltip({ active, payload, label, barLabel }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="font-semibold text-slate-800 mb-1.5">{label}</div>
      <div className="text-slate-700">{barLabel}: <span className="font-semibold tabular-nums">{row.red_count ?? "-"}</span></div>
      <div className="text-slate-700">% of total: <span className="font-semibold tabular-nums">{row.pct_of_total ?? "-"}%</span></div>
      <div className="text-slate-700">Cumulative: <span className="font-semibold tabular-nums">{row.cumulative_pct ?? "-"}%</span></div>
    </div>
  );
}

function ParetoInfoDialog({ open, onOpenChange, title, closeLabel, totalRed, cutoff, metric }) {
  const metricLabel = metric === "outcome"
    ? "Outcome gaps"
    : metric === "financial"
      ? "Financial"
      : "Physical";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid={TID.paretoInfoDialog}>
        <DialogHeader>
          <DialogTitle className="font-display text-lg text-slate-900">{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 text-sm text-slate-700 leading-relaxed">
          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Purpose</h4>
            <p>
              This chart shows <strong>where red flags are concentrated</strong> across components (or outcome subjects).
              It uses the Pareto / 80–20 idea: a small number of components usually account for most of the problems,
              so those “vital few” should be prioritised first.
            </p>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Why some table rows are pink and others are white</h4>
            <p className="mb-2">
              The table under the chart highlights rows to show the Pareto cutoff — <strong>not</strong> a second RAG status.
              Every row already has a red-flag count; the background only marks priority.
            </p>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 uppercase tracking-wide">
                  <tr>
                    <th className="px-3 py-2">Row colour</th>
                    <th className="px-3 py-2">Meaning</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100 bg-red-50/50">
                    <td className="px-3 py-2 font-semibold">Pink / light red</td>
                    <td className="px-3 py-2">
                      “Vital few” — top components whose <strong>cumulative %</strong> first reaches or exceeds
                      <strong> 80%</strong> of all reds. Same set as “Top N …” in the subtitle
                      {cutoff > 0 ? (
                        <>
                          {" "}(currently top <strong>{cutoff}</strong>)
                        </>
                      ) : null}
                      . Focus remediation here first.
                    </td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-3 py-2 font-semibold">White / no tint</td>
                    <td className="px-3 py-2">
                      “Useful many” — remaining components after the 80% cutoff. They still have reds, but together
                      they account for the leftover share (for example ~16% after 83.7%).
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <ul className="mt-2 list-disc pl-5 space-y-1 text-xs text-slate-600">
              <li>Pink does <strong>not</strong> mean that row is “more red” than its RED COUNT already shows.</li>
              <li>Highlight stops at the first row where Cumulative ≥ 80% (inclusive).</li>
              <li>Example: if NSTEP brings cumulative to 83.7%, rows from Digitisation through NSTEP are pink; e-Office onward stay white.</li>
            </ul>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">How to read the chart</h4>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>
                <strong>Red bars (left axis)</strong> — count of red / problem items for that component, sorted
                highest → lowest.
              </li>
              <li>
                <strong>Number on each bar</strong> — exact count for that component.
              </li>
              <li>
                <strong>Dashed line + % labels (right axis)</strong> — running cumulative share of all reds
                (0% → 100%).
              </li>
              <li>
                <strong>Subtitle</strong> — “Top N … ≥80% … (total)” where N is the first point at which
                cumulative % reaches or exceeds 80%.
              </li>
            </ul>
            {(totalRed > 0 || cutoff > 0) && (
              <p className="mt-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-800">
                Current view ({metricLabel}): <strong>{totalRed}</strong> total
                {cutoff > 0 ? (
                  <>
                    {" "}· top <strong>{cutoff}</strong> item(s) cover ≥80%
                  </>
                ) : null}
              </p>
            )}
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">What the three tabs count</h4>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 uppercase tracking-wide">
                  <tr>
                    <th className="px-3 py-2">Tab</th>
                    <th className="px-3 py-2">What each bar counts</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100">
                    <td className="px-3 py-2 font-semibold">Physical</td>
                    <td className="px-3 py-2">
                      Physical indicator rows at <strong>RED</strong> RAG
                      (achievement % below the red threshold).
                    </td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-3 py-2 font-semibold">Financial</td>
                    <td className="px-3 py-2">
                      Financial component rows at <strong>RED</strong> RAG
                      (utilisation % vs funds released below the red threshold).
                    </td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-3 py-2 font-semibold">Outcome gaps</td>
                    <td className="px-3 py-2">
                      Outcome KPIs with <strong>no reported value</strong> (missing data — not a RAG red).
                      Bars are by subject rather than component.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">How Physical reds are calculated</h4>
            <ol className="list-decimal pl-5 space-y-1">
              <li>
                Entries are rolled up per High Court × Component × Indicator × Period (as applicable to filters).
              </li>
              <li>
                Achievement % = <span className="font-mono text-xs">(achieved ÷ target) × 100</span>
                {" "}when target &gt; 0.
              </li>
              <li>RAG thresholds classify the row as GREEN / AMBER / RED / NA.</li>
              <li>Only <strong>RED</strong> rows increment that component’s count by 1.</li>
              <li>
                Components with <strong>no usable targets</strong> (for example some Cloud-style cases) are skipped
                so they are not treated as achievement reds.
              </li>
            </ol>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">How the ≥80% cutoff is set</h4>
            <ol className="list-decimal pl-5 space-y-1">
              <li>Sum all red counts → total.</li>
              <li>Sort components by red count descending.</li>
              <li>
                Walk left → right, accumulating counts; at each step
                {" "}cumulative % = (running sum ÷ total) × 100.
              </li>
              <li>
                The first component where cumulative % ≥ 80 becomes the cutoff N shown in the subtitle
                (“Top N components…”).
              </li>
            </ol>
            <pre className="mt-2 rounded-lg bg-slate-900 text-slate-100 text-[11px] leading-relaxed p-3 overflow-x-auto whitespace-pre-wrap">{`For each component (sorted by red_count desc):
  cumulative += red_count
  cumulative_pct = cumulative / total_red × 100

pareto_cutoff = first position where cumulative_pct ≥ 80`}</pre>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">How to use it</h4>
            <ul className="list-disc pl-5 space-y-1">
              <li>Start with the pink table rows / leftmost bars — they hold ≥80% of reds.</li>
              <li>Use the table for exact red count, % of total, and cumulative %.</li>
              <li>Drill into those components in Physical / Financial trackers (or filters) to see which High Courts or indicators are red.</li>
            </ul>
            <p className="mt-2">
              <strong>Note:</strong> the chart shows <em>how many</em> red flags sit in each component — not how severe
              each red is (for example 10% vs 40% achievement). Severity is visible in RAG / tracker detail views.
            </p>
          </section>
        </div>
        <DialogFooter>
          <button type="button" className="app-btn-secondary" onClick={() => onOpenChange(false)}>
            {closeLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ParetoChart({ reportingPeriod, highCourt = "", component = "", publicMode = false, embedData = null }) {
  const { t } = useTranslation();
  const [accessible] = useAccessibleRag();
  const [metric, setMetric] = useState("physical");
  const [infoOpen, setInfoOpen] = useState(false);
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

  const infoAria = t("dashboard.paretoInfoAria");
  const infoTitle = t("dashboard.paretoInfoTitle");
  const infoClose = t("dashboard.paretoInfoClose");

  return (
    <Card
      title="Pareto - Red Flag Concentration"
      subtitle={subtitle}
      testId="pareto-chart"
      titleAction={(
        <button
          type="button"
          data-testid={TID.paretoInfoBtn}
          className="inline-flex items-center justify-center w-6 h-6 rounded-full border border-slate-300 text-slate-600 hover:bg-slate-100 hover:text-[#003B73] hover:border-[#003B73]/40 transition-colors shrink-0"
          aria-label={infoAria}
          title={infoAria}
          onClick={() => setInfoOpen(true)}
        >
          <Info size={14} weight="bold" />
        </button>
      )}
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
      <ParetoInfoDialog
        open={infoOpen}
        onOpenChange={setInfoOpen}
        title={infoTitle}
        closeLabel={infoClose}
        totalRed={totalRed}
        cutoff={cutoff}
        metric={metric}
      />
      <div className="p-4">
        {isLoading && !data ? (
          <div className="h-64 flex items-center justify-center text-slate-400 text-sm">Loading…</div>
        ) : series.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
            {isOutcome ? "All outcome KPIs reported in this period" : isFinancial ? "No red financial flags in this period" : "No red flags in this period"}
          </div>
        ) : (
          <>
            <div className="h-[22rem]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series} margin={{ top: 28, right: 20, left: 4, bottom: 72 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey={xLabel} stroke="#475569" fontSize={9} angle={-30} textAnchor="end" interval={0} height={80} dy={4} />
                  <YAxis yAxisId="left" stroke="#475569" fontSize={11} label={{ value: barLabel, angle: -90, position: "insideLeft", fontSize: 10 }} />
                  <YAxis yAxisId="right" orientation="right" stroke="#475569" fontSize={11} domain={[0, 100]} unit="%" />
                  <Tooltip content={<ParetoTooltip barLabel={barLabel} />} />
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
            <div
              className="mt-3 mb-1 flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-xs text-slate-600"
              aria-hidden="true"
            >
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block w-4 border-t-2 border-dashed"
                  style={{ borderColor: lineSeriesProps("cumulative_pct", accessible).stroke }}
                />
                <span
                  className="inline-block w-2 h-2 rounded-full border border-white shadow-sm"
                  style={{ background: lineSeriesProps("cumulative_pct", accessible).stroke }}
                />
                {seriesLegendLabel("Cumulative %", "cumulative_pct", accessible)}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block w-3 h-3 rounded-sm"
                  style={{ background: barSeriesProps("red_count", accessible).fill }}
                />
                {seriesLegendLabel(barLabel, "red_count", accessible)}
              </span>
            </div>
            {cutoff > 0 && series.length > 0 && (
              <p className="mt-3 text-[11px] text-slate-500 flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-3 h-3 rounded-sm bg-red-50 border border-red-200" aria-hidden="true" />
                  Pink rows = top {cutoff} covering ≥80% of reds (priority)
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-3 h-3 rounded-sm bg-white border border-slate-200" aria-hidden="true" />
                  White rows = remaining share
                </span>
              </p>
            )}
            <table className="dense-table w-full mt-2 text-xs table-fixed">
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
