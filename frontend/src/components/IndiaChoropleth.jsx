import React, { useState } from "react";
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
import { RAG_COLORS, RAG_SYMBOLS, choroplethStrokeProps, formatRagLegendLabel, ragLegendLabels, useAccessibleRag } from "@/lib/ragColors";

const INDIA_TOPO_URL = process.env.PUBLIC_URL
  ? `${process.env.PUBLIC_URL}/geo/india-states.geojson`
  : "/geo/india-states.geojson";

const METRICS = [
  { id: "physical", label: "Physical" },
  { id: "financial", label: "Financial" },
  { id: "outcome", label: "Outcome" },
];

function findStateInfo(states, geoName) {
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

export default function IndiaChoropleth({ reportingPeriod }) {
  const [metric, setMetric] = useState("physical");
  const [accessible] = useAccessibleRag();
  const thresholds = useQuery({
    queryKey: ["rag-thresholds"],
    queryFn: () => api.get("/master/rag-thresholds").then(r => r.data),
  });
  const { data } = useQuery({
    queryKey: ["states-rag", reportingPeriod, metric],
    queryFn: () => api.get("/dashboard/states-rag", {
      params: {
        ...(reportingPeriod ? { reporting_period: reportingPeriod } : {}),
        metric,
      },
    }).then(r => r.data),
  });
  const [hover, setHover] = useState(null);
  const states = data || {};
  const legend = ragLegendLabels(thresholds.data);
  const label = metricLabel(metric);

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
        <div className="lg:col-span-3 bg-white rounded-sm relative overflow-visible pt-1">
          <ComposableMap
            projection={INDIA_MAP_PROJECTION}
            projectionConfig={INDIA_MAP_PROJECTION_CONFIG}
            width={INDIA_MAP_DIMENSIONS.width}
            height={INDIA_MAP_DIMENSIONS.height}
            style={INDIA_MAP_STYLE}
            data-testid="india-choropleth"
          >
            <Geographies geography={INDIA_TOPO_URL}>
              {({ geographies }) => geographies.map(geo => {
                const stateName = geo.properties.ST_NM || geo.properties.NAME_1 || geo.properties.name || "";
                const info = findStateInfo(states, stateName);
                const rag = info?.in_scope === false ? "NA" : (info?.rag || "NA");
                const fill = RAG_COLORS[rag];
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
                    onMouseEnter={() => setHover({ name: stateName, ...info, rag })}
                    onMouseLeave={() => setHover(null)}
                  />
                );
              })}
            </Geographies>
          </ComposableMap>
          {hover && (
            <div className="absolute bottom-3 left-3 bg-[#0A1128] text-white px-3 py-2 rounded-sm text-xs shadow-lg pointer-events-none">
              <div className="font-semibold">{hover.name}</div>
              <div className="text-slate-300 text-[11px]">High Court: <span className="text-amber-300">{hover.high_court || "—"}</span></div>
              {hover.in_scope === false ? (
                <div className="text-slate-400 text-[11px] mt-1">Outside your jurisdiction</div>
              ) : (
                <div className="text-slate-300 text-[11px]">
                  {label}: {hover.percent != null ? `${hover.percent.toFixed(1)}%` : "No data for this HC"} ·
                  <span className="ml-1 font-semibold" style={{ color: RAG_COLORS[hover.rag] }}>
                    {accessible && RAG_SYMBOLS[hover.rag] ? `${RAG_SYMBOLS[hover.rag]} ` : ""}{hover.rag}
                  </span>
                </div>
              )}
            </div>
          )}
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
