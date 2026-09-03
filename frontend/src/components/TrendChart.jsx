import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Info } from "@phosphor-icons/react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend, ReferenceLine,
} from "recharts";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { lineSeriesProps, seriesLegendLabel, useAccessibleRag } from "@/lib/ragColors";
import { TID } from "@/lib/testIds";

function ProgressTrendInfoDialog({ open, onOpenChange, title, closeLabel, periods = [] }) {
  const byPeriod = Object.fromEntries((periods || []).map((p) => [p.period, p]));
  const mar = byPeriod["2026-03"];
  const jun = byPeriod["2026-06"];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid={TID.progressTrendInfoDialog}>
        <DialogHeader>
          <DialogTitle className="font-display text-lg text-slate-900">{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 text-sm text-slate-700 leading-relaxed">
          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Purpose</h4>
            <p>
              This chart shows <strong>Physical %</strong>, <strong>Financial %</strong>, and{" "}
              <strong>Outcome reported %</strong> across reporting periods so you can see how achievement
              moves over time. The purple dashed line (when enabled) marks a DPR milestone period — it is
              not a percentage series.
            </p>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">How each series is calculated</h4>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 uppercase tracking-wide">
                  <tr>
                    <th className="px-3 py-2">Series</th>
                    <th className="px-3 py-2">Formula (per reporting period)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100">
                    <td className="px-3 py-2 font-semibold">Financial %</td>
                    <td className="px-3 py-2">
                      <span className="font-mono text-[11px]">(Σ fund utilised ÷ Σ fund released) × 100</span>
                      <div className="mt-1 text-slate-600">Same formula as the Financial utilisation KPI card.</div>
                    </td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-3 py-2 font-semibold">Physical %</td>
                    <td className="px-3 py-2">
                      Same path as the Physical KPI card: build Count-scoped absolute totals
                      (Cloud GB/TB/PB and Percentage UOMs excluded from that sum), then
                      {" "}
                      <span className="font-mono text-[11px]">(Σ achieved ÷ Σ target) × 100</span>.
                      <div className="mt-1 text-slate-600">
                        If there is no usable target (for example Cloud-only periods), the point is blank (`null`).
                      </div>
                    </td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-3 py-2 font-semibold">Outcome reported %</td>
                    <td className="px-3 py-2">
                      <span className="font-mono text-[11px]">(KPIs with a value ÷ total outcome KPI rows) × 100</span>
                      <div className="mt-1 text-slate-600">
                        Measures reporting coverage, not outcome “achievement”. Empty when there are no outcome rows.
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Current values on this chart</h4>
            {(periods || []).length === 0 ? (
              <p className="text-slate-500 text-xs">No period data loaded.</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 uppercase tracking-wide">
                    <tr>
                      <th className="px-3 py-2">Period</th>
                      <th className="px-3 py-2 text-right">Physical %</th>
                      <th className="px-3 py-2 text-right">Financial %</th>
                      <th className="px-3 py-2 text-right">Outcome %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(periods || []).map((p) => (
                      <tr key={p.period} className="border-t border-slate-100">
                        <td className="px-3 py-2 font-medium">{p.period}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {p.phys_percent == null ? "—" : Number(p.phys_percent).toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {p.fin_percent == null ? "—" : Number(p.fin_percent).toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {p.outcome_reported_pct == null ? "—" : Number(p.outcome_reported_pct).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {(mar || jun) && (
              <ul className="mt-2 list-disc pl-5 space-y-1 text-xs text-slate-600">
                {mar && (
                  <li>
                    <strong>2026-03:</strong> Financial {mar.fin_percent ?? "—"}%
                    {mar.phys_percent == null
                      ? "; Physical blank (no usable targets)"
                      : `; Physical ${mar.phys_percent}%`}
                    ; Outcome {mar.outcome_reported_pct ?? "—"}.
                  </li>
                )}
                {jun && (
                  <li>
                    <strong>2026-06:</strong> Physical {jun.phys_percent ?? "—"}% and Financial {jun.fin_percent ?? "—"}%
                    match the KPI cards for the same period
                    {jun.phys_percent != null && jun.fin_percent != null ? " (aligned formulas)" : ""}.
                  </li>
                )}
              </ul>
            )}
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Worked example (national demo)</h4>
            <pre className="rounded-lg bg-slate-900 text-slate-100 text-[11px] leading-relaxed p-3 overflow-x-auto whitespace-pre-wrap">{`Financial 2026-03: utilised / released × 100  →  32.28%
Financial 2026-06: utilised / released × 100  →  69.78%
Physical  2026-06: Count Σ achieved / Σ target × 100
                   →  46799 / 55145  =  84.87%
Physical  2026-03: no usable targets (Cloud GB only)  →  blank
Outcome:           no outcome KPI rows  →  blank`}</pre>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">DPR milestones</h4>
            <p>
              When <strong>Show DPR milestones</strong> is checked, a purple dashed vertical line appears on
              periods that have a DPR deliverable target/actual date (for example DPR-005 at 2026-06).
              That marker is for timeline context only.
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

/** Info control for Card titleAction next to Progress Trend title. */
export function ProgressTrendInfoButton({ onClick, ariaLabel }) {
  return (
    <button
      type="button"
      data-testid={TID.progressTrendInfoBtn}
      className="inline-flex items-center justify-center w-6 h-6 rounded-full border border-slate-300 text-slate-600 hover:bg-slate-100 hover:text-[#003B73] hover:border-[#003B73]/40 transition-colors shrink-0"
      aria-label={ariaLabel}
      title={ariaLabel}
      onClick={onClick}
    >
      <Info size={14} weight="bold" />
    </button>
  );
}

export default function TrendChart({ trendData, infoOpen, onInfoOpenChange }) {
  const { t } = useTranslation();
  const [accessible] = useAccessibleRag();
  const [showMilestones, setShowMilestones] = useState(true);
  const [localInfoOpen, setLocalInfoOpen] = useState(false);
  const periods = trendData?.periods || (Array.isArray(trendData) ? trendData : []);
  const milestones = trendData?.milestones || [];

  const dialogOpen = onInfoOpenChange ? !!infoOpen : localInfoOpen;
  const setDialogOpen = onInfoOpenChange || setLocalInfoOpen;

  const milestoneByPeriod = useMemo(() => {
    const m = {};
    milestones.forEach(ms => {
      if (!ms.period) return;
      m[ms.period] = m[ms.period] || [];
      m[ms.period].push(ms);
    });
    return m;
  }, [milestones]);

  const milestonePeriods = useMemo(
    () => [...new Set(milestones.map(m => m.period).filter(Boolean))],
    [milestones],
  );

  const infoTitle = t("dashboard.progressTrendInfoTitle");
  const infoClose = t("dashboard.progressTrendInfoClose");

  return (
    <div>
      <ProgressTrendInfoDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title={infoTitle}
        closeLabel={infoClose}
        periods={periods}
      />
      <div className="flex justify-end px-3 pt-2">
        <label className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-slate-600 cursor-pointer">
          <input type="checkbox" checked={showMilestones} onChange={(e) => setShowMilestones(e.target.checked)} />
          Show DPR milestones
        </label>
      </div>
      <div className="h-72 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={periods}>
            <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
            <XAxis dataKey="period" stroke="#475569" fontSize={11} />
            <YAxis stroke="#475569" fontSize={11} />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const ms = milestoneByPeriod[label] || [];
                return (
                  <div className="bg-white border border-slate-200 rounded-sm p-2 text-xs shadow-md">
                    <div className="font-semibold mb-1">{label}</div>
                    {payload.map(p => (
                      <div key={p.dataKey}>
                        {seriesLegendLabel(p.name, p.dataKey, accessible)}: {p.value?.toFixed?.(1) ?? p.value}%
                      </div>
                    ))}
                    {ms.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-100 text-slate-600">
                        {ms.map(m => (
                          <div key={m.code}>{m.code}: {m.title}</div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              }}
            />
            <Legend />
            {showMilestones && milestonePeriods.map(p => (
              <ReferenceLine
                key={p}
                x={p}
                stroke="#9333EA"
                strokeDasharray="4 4"
                label={{ value: milestoneByPeriod[p]?.[0]?.code || p, position: "top", fontSize: 9, fill: "#9333EA" }}
              />
            ))}
            <Line
              type="monotone"
              dataKey="phys_percent"
              name={seriesLegendLabel("Physical %", "phys_percent", accessible)}
              dot
              {...lineSeriesProps("phys_percent", accessible)}
            />
            <Line
              type="monotone"
              dataKey="fin_percent"
              name={seriesLegendLabel("Financial %", "fin_percent", accessible)}
              dot
              {...lineSeriesProps("fin_percent", accessible)}
            />
            <Line
              type="monotone"
              dataKey="outcome_reported_pct"
              name={seriesLegendLabel("Outcome reported %", "outcome_reported_pct", accessible)}
              dot
              {...lineSeriesProps("outcome_reported_pct", accessible)}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
