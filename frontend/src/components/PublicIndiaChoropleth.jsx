import React, { useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import {
  INDIA_MAP_COMPACT_DIMENSIONS,
  INDIA_MAP_COMPACT_PROJECTION_CONFIG,
  INDIA_MAP_PROJECTION,
  INDIA_MAP_STYLE,
} from "@/lib/indiaMapConfig";
import {
  RAG_COLORS,
  RAG_SYMBOLS,
  choroplethStrokeProps,
  formatRagLegendLabel,
  ragLegendLabels,
  useAccessibleRag,
} from "@/lib/ragColors";

const INDIA_TOPO_URL = process.env.PUBLIC_URL
  ? `${process.env.PUBLIC_URL}/geo/india-states.geojson`
  : "/geo/india-states.geojson";

const METRICS = [
  { id: "physical", label: "Physical" },
  { id: "financial", label: "Financial" },
  { id: "outcome", label: "Outcome" },
];

function findStateInfo(states, geoName) {
  if (!states) return null;
  if (states[geoName]) return states[geoName];
  const lower = geoName.toLowerCase();
  for (const k of Object.keys(states)) {
    if (k.toLowerCase() === lower) return states[k];
  }
  return null;
}

/** Read-only India map for the public transparency page (no auth). */
export default function PublicIndiaChoropleth({
  states = {},
  statesFinancial = {},
  statesOutcome = {},
}) {
  const [accessible] = useAccessibleRag();
  const [metric, setMetric] = useState("physical");
  const [hover, setHover] = useState(null);
  const legend = useMemo(() => ragLegendLabels(), []);

  const activeStates = useMemo(() => {
    if (metric === "financial") return statesFinancial;
    if (metric === "outcome") return statesOutcome;
    return states;
  }, [metric, states, statesFinancial, statesOutcome]);

  const metricLabel = metric === "financial" ? "Utilisation" : metric === "outcome" ? "Reporting" : "Physical";

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
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
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <div className="lg:col-span-3 bg-white rounded-xl relative overflow-visible border border-slate-200/80 shadow-inner shadow-slate-100/80 p-2 pt-3">
          <ComposableMap
            projection={INDIA_MAP_PROJECTION}
            projectionConfig={INDIA_MAP_COMPACT_PROJECTION_CONFIG}
            width={INDIA_MAP_COMPACT_DIMENSIONS.width}
            height={INDIA_MAP_COMPACT_DIMENSIONS.height}
            style={INDIA_MAP_STYLE}
            data-testid="public-india-choropleth"
          >
            <Geographies geography={INDIA_TOPO_URL}>
              {({ geographies }) => geographies.map(geo => {
                const stateName = geo.properties.ST_NM || geo.properties.NAME_1 || geo.properties.name || "";
                const info = findStateInfo(activeStates, stateName);
                const rag = info?.rag || "NA";
                const strokeStyle = choroplethStrokeProps(rag, accessible);
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={RAG_COLORS[rag]}
                    stroke="#FFFFFF"
                    strokeWidth={strokeStyle.strokeWidth}
                    strokeDasharray={strokeStyle.strokeDasharray}
                    style={{
                      default: { outline: "none" },
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
            <div className="absolute bottom-4 left-4 bg-[#0A1128]/95 backdrop-blur-sm text-white px-4 py-3 rounded-xl text-xs shadow-xl pointer-events-none border border-white/10">
              <div className="font-semibold">{hover.name}</div>
              <div className="text-slate-300 text-[11px]">High Court: {hover.high_court || "—"}</div>
              <div className="text-slate-300 text-[11px]">
                {metricLabel}: {hover.percent != null ? `${hover.percent.toFixed(1)}%` : "No data for this HC"} ·
                <span className="ml-1 font-semibold" style={{ color: RAG_COLORS[hover.rag] }}>
                  {accessible && RAG_SYMBOLS[hover.rag] ? `${RAG_SYMBOLS[hover.rag]} ` : ""}{hover.rag}
                </span>
              </div>
            </div>
          )}
        </div>
        <div className="text-xs space-y-3 self-start p-4 rounded-xl bg-slate-50 border border-slate-200/80">
          <div className="font-semibold uppercase tracking-wider text-[10px] text-slate-600">Legend</div>
          {["GREEN", "AMBER", "RED", "NA"].map(k => (
            <div key={k} className="flex items-center gap-2">
              <span className="inline-block w-4 h-4 rounded-sm border border-slate-300" style={{ background: RAG_COLORS[k] }} />
              <span className="text-slate-700">
                {formatRagLegendLabel(k, accessible)} {legend[k]}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
