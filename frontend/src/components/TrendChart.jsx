import React, { useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend, ReferenceLine,
} from "recharts";
import { lineSeriesProps, seriesLegendLabel, useAccessibleRag } from "@/lib/ragColors";

export default function TrendChart({ trendData }) {
  const [accessible] = useAccessibleRag();
  const [showMilestones, setShowMilestones] = useState(true);
  const periods = trendData?.periods || (Array.isArray(trendData) ? trendData : []);
  const milestones = trendData?.milestones || [];

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

  return (
    <div>
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
