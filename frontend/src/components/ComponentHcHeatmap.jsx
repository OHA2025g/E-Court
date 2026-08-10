import React, { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, fmtNum } from "@/lib/api";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { formatRagLegendLabel, useAccessibleRag } from "@/lib/ragColors";
import { formatPhysTargetAchieved } from "@/lib/physFormat";

const METRICS = [
  { id: "physical", label: "Physical" },
  { id: "financial", label: "Financial" },
  { id: "outcome", label: "Outcome" },
];

const RAG_CLASS = {
  GREEN: "heatmap-cell--green",
  AMBER: "heatmap-cell--amber",
  RED: "heatmap-cell--red",
  NA: "heatmap-cell--na",
};

const LEGEND_ORDER = ["GREEN", "AMBER", "RED", "NA"];

/** Short vertical labels for long Gauhati / compound HC names. */
const HC_COLUMN_LABEL = {
  "Gauhati – Arunachal Pradesh": "Gauhati·AP",
  "Gauhati – Assam": "Gauhati·AS",
  "Gauhati – Mizoram": "Gauhati·MZ",
  "Gauhati – Nagaland": "Gauhati·NL",
  "Gauhati - Nagaland": "Gauhati·NL",
  "Punjab & Haryana": "P&H",
  "Andhra Pradesh": "Andhra Pr.",
  "Himachal Pradesh": "H.Pradesh",
  "Jammu & Kashmir": "J&K",
  "Madhya Pradesh": "M.Pradesh",
};

function hcColumnLabel(hc) {
  return HC_COLUMN_LABEL[hc] || hc;
}

function cellDetail(rowKey, hc, cell, metric) {
  const rag = cell?.rag || "NA";
  const head = `${rowKey} · ${hc}`;
  const hasCounts = (
    cell?.target != null
    || cell?.achieved != null
    || cell?.released != null
    || cell?.utilized != null
    || cell?.total != null
  );
  if (!hasCounts && cell?.percent == null && rag === "NA") {
    return `${head}: No data (NA)`;
  }

  if (metric === "financial") {
    return `${head}: Released ₹${fmtNum(cell.released)} Cr / Utilised ₹${fmtNum(cell.utilized)} Cr (${rag})`;
  }
  if (metric === "outcome") {
    return `${head}: Reported ${fmtNum(cell.reported, { digits: 0 })} / ${fmtNum(cell.total, { digits: 0 })} KPIs (${rag})`;
  }

  // Physical: Digitization shown as Cr pages (not ₹ Cr).
  return `${head}: ${formatPhysTargetAchieved(cell.target, cell.achieved, cell.uom)} (${rag})`;
}

export default function ComponentHcHeatmap({ reportingPeriod, highCourt = "", component = "", publicMode = false, embedData = null }) {
  const [accessible] = useAccessibleRag();
  const [metric, setMetric] = useState("physical");
  const [hover, setHover] = useState(null);

  const { data: fetched, isLoading } = useQuery({
    queryKey: ["heatmap", "v2-counts", reportingPeriod, highCourt, component, metric, publicMode],
    queryFn: () => api.get(`${publicMode ? "/public" : "/dashboard"}/heatmap`, {
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

  const rowField = data?.row_field || (metric === "outcome" ? "subject" : "component");
  const rowKeys = metric === "outcome"
    ? (data?.subjects || [])
    : (data?.components || []);

  const cellMap = useMemo(() => {
    const m = new Map();
    (data?.cells || []).forEach(c => {
      const rowKey = c[rowField] || c.component || c.subject;
      m.set(`${rowKey}|${c.high_court}`, c);
    });
    return m;
  }, [data, rowField]);

  const hcs = data?.high_courts || [];
  const rowLabel = metric === "outcome" ? "Subject" : "Component";
  const title = metric === "outcome"
    ? "Outcome Subject × High Court Heatmap"
    : "Component × High Court Heatmap";
  const subtitle = metric === "outcome"
    ? "RAG by outcome reporting coverage (KPI counts) per subject and High Court"
    : "RAG status by component and High Court jurisdiction";

  const clearHover = useCallback(() => setHover(null), []);

  const cellCount = (data?.cells || []).length;
  const hoverDetail = hover
    ? cellDetail(hover.rowKey, hover.hc, hover.cell || { rag: "NA" }, metric)
    : null;

  return (
    <Card
      title={title}
      subtitle={subtitle}
      testId="component-hc-heatmap"
      elevated
      action={
        <div className="flex flex-wrap gap-2">
          {METRICS.map(m => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMetric(m.id)}
              className={`public-map-metric-btn ${metric === m.id ? "public-map-metric-btn--active" : ""}`}
            >
              {m.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="heatmap-shell">
        <ScrollRegion
          className="heatmap-scroll"
          label="Component and high court heatmap"
          onMouseLeave={clearHover}
        >
          {isLoading && !data ? (
            <div className="heatmap-loading">Loading heatmap…</div>
          ) : (
            <table className="heatmap-table">
              <thead>
                <tr>
                  <th scope="col" className="heatmap-th-corner">{rowLabel}</th>
                  {hcs.map(hc => (
                    <th
                      key={hc}
                      scope="col"
                      className={`heatmap-th-col ${hover?.hc === hc ? "is-active" : ""}`}
                      title={hc}
                    >
                      <span>{hcColumnLabel(hc)}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rowKeys.map(rowKey => (
                  <tr
                    key={rowKey}
                    className={hover?.rowKey === rowKey ? "is-active-row" : undefined}
                  >
                    <th scope="row" className="heatmap-th-row" title={rowKey}>
                      {rowKey}
                    </th>
                    {hcs.map(hc => {
                      const cell = cellMap.get(`${rowKey}|${hc}`) || { rag: "NA" };
                      const rag = cell.rag || "NA";
                      const isActive = hover?.rowKey === rowKey && hover?.hc === hc;
                      const detail = cellDetail(rowKey, hc, cell, metric);
                      return (
                        <td key={hc} className="heatmap-td">
                          <button
                            type="button"
                            className={[
                              "heatmap-cell",
                              RAG_CLASS[rag] || RAG_CLASS.NA,
                              isActive ? "is-active" : "",
                            ].join(" ")}
                            title={detail}
                            aria-label={detail}
                            onMouseEnter={() => setHover({ rowKey, hc, cell })}
                            onFocus={() => setHover({ rowKey, hc, cell })}
                            onBlur={clearHover}
                          />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </ScrollRegion>

        <footer className="heatmap-footer">
          <div className="heatmap-legend" aria-label="RAG legend">
            {LEGEND_ORDER.map(k => (
              <span key={k} className="heatmap-legend-item">
                <span className={`heatmap-legend-swatch heatmap-legend-swatch--${k.toLowerCase()}`} aria-hidden="true" />
                {formatRagLegendLabel(k, accessible)}
              </span>
            ))}
          </div>
          <div
            className={`heatmap-hint${hoverDetail ? " is-detail" : ""}`}
            data-testid="heatmap-hover-detail"
          >
            {hoverDetail || (cellCount > 0
              ? `${cellCount.toLocaleString()} cells · hover for Target / Achieved or Released / Utilised`
              : null)}
          </div>
        </footer>
      </div>
    </Card>
  );
}
