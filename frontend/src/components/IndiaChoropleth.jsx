import React, { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { api } from "@/lib/api";
import Card from "@/components/Card";
import {
  INDIA_MAP_DIMENSIONS,
  INDIA_MAP_PROJECTION,
  INDIA_MAP_PROJECTION_CONFIG,
  INDIA_MAP_STYLE,
} from "@/lib/indiaMapConfig";
import { mapHoverCounts, mapHoverDetail } from "@/lib/mapHoverDetail";
import { RAG_COLORS, RAG_SYMBOLS, choroplethStrokeProps, ragLegendLabels, useAccessibleRag } from "@/lib/ragColors";

const INDIA_TOPO_URL = process.env.PUBLIC_URL
  ? `${process.env.PUBLIC_URL}/geo/india-states.geojson`
  : "/geo/india-states.geojson";

const METRICS = [
  { id: "physical", label: "Physical" },
  { id: "financial", label: "Financial" },
  { id: "outcome", label: "Outcome" },
];

function findStateInfo(states, geoName) {
  if (!states || typeof states !== "object" || Array.isArray(states)) return null;
  if (states[geoName]) return states[geoName];
  const lower = geoName.toLowerCase();
  for (const k of Object.keys(states)) {
    if (k.toLowerCase() === lower) return states[k];
  }
  return null;
}

function metricLabel(metric) {
  if (metric === "financial") return "Financial utilisation";
  if (metric === "outcome") return "Outcome reporting coverage";
  return "Physical achievement";
}

export default function IndiaChoropleth({ reportingPeriod, highCourt = "", component = "" }) {
  const [metric, setMetric] = useState("physical");
  const [accessible] = useAccessibleRag();
  const thresholds = useQuery({
    queryKey: ["rag-thresholds"],
    queryFn: () => api.get("/master/rag-thresholds").then(r => r.data),
  });
  const { data } = useQuery({
    queryKey: ["states-rag", "v14-tooltip", reportingPeriod, highCourt, component, metric],
    queryFn: () => api.get("/dashboard/states-rag", {
      params: {
        ...(reportingPeriod ? { reporting_period: reportingPeriod } : {}),
        ...(highCourt ? { high_court: highCourt } : {}),
        ...(component ? { component } : {}),
        metric,
      },
    }).then(r => r.data),
  });
  const [hover, setHover] = useState(null);
  const states = data || {};
  const legend = ragLegendLabels(thresholds.data);
  const label = metricLabel(metric);
  const detail = hover ? mapHoverDetail(hover, metric, label) : null;
  const counts = hover ? mapHoverCounts(hover, metric) : null;
  const scopedStates = Object.values(states).filter((s) => s && s.in_scope !== false);
  const hasRagData = scopedStates.some((s) => s.rag && s.rag !== "NA");
  const mapLoaded = data !== undefined;

  const onMapMouseMove = useCallback((e) => {
    setHover((prev) => {
      if (!prev) return prev;
      const rect = e.currentTarget.getBoundingClientRect();
      return {
        ...prev,
        x: e.clientX - rect.left + 12,
        y: e.clientY - rect.top + 12,
      };
    });
  }, []);

  return (
    <Card
      title={`India · ${label} RAG by High Court Jurisdiction`}
      subtitle="Each state polygon is coloured by aggregate % of its parent High Court"
      testId="india-choropleth-card"
      action={
        <div className="flex gap-1 text-[10px] uppercase tracking-wider">
          {METRICS.map(m => (
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
      <div className="p-4 grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div
          className="lg:col-span-3 bg-white rounded-sm relative overflow-visible pt-1"
          onMouseMove={onMapMouseMove}
          onMouseLeave={() => setHover(null)}
        >
          {mapLoaded && !hasRagData && (
            <div
              className="mb-3 rounded-sm border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900"
              data-testid="india-map-empty-state"
              role="status"
            >
              No {label.toLowerCase()} RAG data for the current filters. Try{" "}
              <span className="font-semibold">All periods</span>
              {" "}or a period with tracker data (e.g. Physical Achieved till Sep 2025 /
              Sep 2023 – Mar 2026).
            </div>
          )}
          <ComposableMap
            projection={INDIA_MAP_PROJECTION}
            projectionConfig={INDIA_MAP_PROJECTION_CONFIG}
            width={INDIA_MAP_DIMENSIONS.width}
            height={INDIA_MAP_DIMENSIONS.height}
            style={INDIA_MAP_STYLE}
            data-testid="india-choropleth"
          >
            <Geographies geography={INDIA_TOPO_URL}>
              {({ geographies }) => (geographies || []).map(geo => {
                const stateName = geo.properties.ST_NM || geo.properties.NAME_1 || geo.properties.name || "";
                const info = findStateInfo(states, stateName);
                const rag = info?.in_scope === false ? "NA" : (info?.rag || "NA");
                const fill = RAG_COLORS[rag] || RAG_COLORS.NA;
                const strokeStyle = choroplethStrokeProps(rag, accessible);
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={fill}
                    stroke="#FFFFFF"
                    strokeWidth={strokeStyle.strokeWidth}
                    strokeDasharray={strokeStyle.strokeDasharray}
                    style={{
                      default: { outline: "none", transition: "fill 0.2s" },
                      hover: { outline: "none", fill: "#1E40AF", cursor: "pointer" },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={(e) => {
                      const parent = e.currentTarget.ownerSVGElement?.parentElement;
                      const rect = parent?.getBoundingClientRect?.() || e.currentTarget.getBoundingClientRect();
                      setHover({
                        name: stateName,
                        ...(info || {}),
                        rag,
                        x: e.clientX - rect.left + 12,
                        y: e.clientY - rect.top + 12,
                      });
                    }}
                  />
                );
              })}
            </Geographies>
          </ComposableMap>
          {hover && (
            <div
              className="absolute z-20 max-w-xs pointer-events-none rounded-sm border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg"
              style={{ left: hover.x, top: hover.y }}
              data-testid="india-map-tooltip"
              role="tooltip"
            >
              <div className="font-semibold text-slate-900">{hover.name}</div>
              <div className="text-slate-500 text-[11px] mt-0.5">
                High Court: <span className="text-[#003B73] font-medium">{hover.high_court || "—"}</span>
              </div>
              {hover.in_scope === false ? (
                <div className="text-slate-500 text-[11px] mt-1">Outside your jurisdiction</div>
              ) : (
                <>
                  {counts && (
                    <div className="text-slate-800 text-[11px] mt-1.5 leading-snug font-medium">{counts}</div>
                  )}
                  <div className="text-slate-600 text-[11px] mt-1">
                    {label}:{" "}
                    {hover.percent != null ? `${Number(hover.percent).toFixed(1)}%` : "No data"}
                    {" · "}
                    <span className="font-semibold" style={{ color: RAG_COLORS[hover.rag] || RAG_COLORS.NA }}>
                      {accessible && RAG_SYMBOLS[hover.rag] ? `${RAG_SYMBOLS[hover.rag]} ` : ""}
                      {hover.rag}
                    </span>
                  </div>
                </>
              )}
            </div>
          )}
          <div
            className={`mt-2 text-[11px] px-2 py-1.5 rounded-sm border ${detail ? "border-[#003B73]/30 bg-[#003B73]/5 text-slate-800" : "border-slate-200 bg-slate-50 text-slate-500"}`}
            data-testid="india-map-hover-detail"
          >
            {detail || "Hover a state for Target / Achieved or Released / Utilised (same detail as heatmap)"}
          </div>
        </div>
        <div className="text-xs space-y-2 self-start">
          <div className="font-semibold uppercase tracking-wider text-[10px] text-slate-600">Legend</div>
          {["GREEN", "AMBER", "RED", "NA"].map(k => (
            <div key={k} className="flex items-center gap-2">
              <span className="inline-block w-4 h-4 rounded-sm border border-slate-300" style={{ background: RAG_COLORS[k] }} />
              <span className="text-slate-700">
                {accessible && <span className="font-mono mr-1">{RAG_SYMBOLS[k]}</span>}
                {k} {legend[k]}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
