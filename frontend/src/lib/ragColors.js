import { useCallback, useEffect, useState } from "react";

export const RAG_COLORS = {
  GREEN: "#10B981",
  AMBER: "#F59E0B",
  RED: "#EF4444",
  NA: "#94A3B8",
};

export const RAG_CSS_VARS = {
  green: "--rag-green",
  amber: "--rag-amber",
  red: "--rag-red",
};

/** Shape + stroke patterns for colour-blind accessible charts. */
export const RAG_SYMBOLS = { GREEN: "●", AMBER: "▲", RED: "■", NA: "○" };

export const RAG_STROKE_DASH = {
  GREEN: "0",
  AMBER: "4 2",
  RED: "2 2",
  NA: "1 3",
};

/** Choropleth border patterns when accessible RAG mode is enabled. */
export const ACCESSIBLE_STROKE = {
  GREEN: { strokeWidth: 0.5, strokeDasharray: "0" },
  AMBER: { strokeWidth: 1.2, strokeDasharray: "4 2" },
  RED: { strokeWidth: 1.5, strokeDasharray: "2 2" },
  NA: { strokeWidth: 0.5, strokeDasharray: "1 3" },
};

export function choroplethStrokeProps(rag, accessible) {
  if (!accessible) return { strokeWidth: 0.5, strokeDasharray: "0" };
  return ACCESSIBLE_STROKE[rag] || ACCESSIBLE_STROKE.NA;
}

export function ragCellProps(status, accessible) {
  const s = status || "NA";
  const base = { fill: RAG_COLORS[s] || RAG_COLORS.NA };
  if (!accessible) return base;
  return {
    ...base,
    stroke: "#334155",
    strokeWidth: s === "AMBER" || s === "RED" ? 1.5 : 0.75,
    strokeDasharray: RAG_STROKE_DASH[s] || RAG_STROKE_DASH.NA,
  };
}

export function formatRagLegendLabel(name, accessible) {
  if (!accessible) return name;
  return `${RAG_SYMBOLS[name] || RAG_SYMBOLS.NA} ${name}`;
}

/** Dual-metric chart series — distinct dash + legend symbol when accessible mode is on. */
export const CHART_SERIES = {
  phys_percent: { color: "#003B73", symbol: "●", dash: "0" },
  phys_percent_hc: { color: "#0369A1", symbol: "●", dash: "0" },
  fin_percent: { color: "#F59E0B", symbol: "▲", dash: "6 3" },
  fin_percent_hc: { color: "#10B981", symbol: "▲", dash: "6 3" },
  outcome_reported_pct: { color: "#059669", symbol: "■", dash: "4 2" },
  outcome_pct: { color: "#059669", symbol: "■", dash: "4 2" },
  red_count: { color: "#EF4444", symbol: "■", dash: "0" },
  cumulative_pct: { color: "#003B73", symbol: "○", dash: "3 3" },
};

export function chartLegendFormatter(accessible) {
  return (value) => {
    if (!accessible) return value;
    const entry = Object.values(CHART_SERIES).find((m) => value?.startsWith?.(m.symbol));
    if (entry) return value;
    const key = Object.keys(CHART_SERIES).find((k) => {
      const label = k.replace(/_/g, " ");
      return value?.toLowerCase?.().includes(label.split(" ")[0]);
    });
    const meta = key ? CHART_SERIES[key] : null;
    return meta ? `${meta.symbol} ${value}` : value;
  };
}

export function seriesLegendLabel(name, seriesKey, accessible) {
  if (!accessible) return name;
  const meta = CHART_SERIES[seriesKey];
  return meta ? `${meta.symbol} ${name}` : name;
}

export function barSeriesProps(seriesKey, accessible) {
  const meta = CHART_SERIES[seriesKey] || { color: "#003B73", dash: "0" };
  const props = { fill: meta.color };
  if (!accessible) return props;
  return {
    ...props,
    stroke: "#334155",
    strokeWidth: 1,
    ...(meta.dash !== "0" ? { strokeDasharray: meta.dash } : {}),
  };
}

export function lineSeriesProps(seriesKey, accessible) {
  const meta = CHART_SERIES[seriesKey] || { color: "#003B73", dash: "0" };
  const props = {
    stroke: meta.color,
    strokeWidth: 2,
    ...(meta.dash !== "0" ? { strokeDasharray: meta.dash } : {}),
  };
  if (!accessible) return props;
  return { ...props, strokeWidth: meta.dash !== "0" ? 2.5 : 2 };
}

export function ragSwatchClass(status, accessible) {
  if (!accessible) return "";
  return RAG_PATTERNS[status] || RAG_PATTERNS.NA;
}

/** Shape patterns for colour-blind accessible RAG (used when accessible mode is on). */
export const RAG_PATTERNS = {
  GREEN: "rag-pattern-green",
  AMBER: "rag-pattern-amber",
  RED: "rag-pattern-red",
  NA: "rag-pattern-na",
};

const ACCESSIBLE_RAG_KEY = "pmis-accessible-rag";

export function ragLegendLabels(thresholds) {
  const green = thresholds?.green_min ?? 80;
  const amber = thresholds?.amber_min ?? 65;
  return {
    GREEN: `(≥${green}%)`,
    AMBER: `(${amber}–${green - 1}%)`,
    RED: `(<${amber}%)`,
    NA: "No data",
  };
}

export function readAccessibleRag() {
  try {
    return localStorage.getItem(ACCESSIBLE_RAG_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeAccessibleRag(enabled) {
  try {
    localStorage.setItem(ACCESSIBLE_RAG_KEY, enabled ? "1" : "0");
    window.dispatchEvent(new CustomEvent("pmis-accessible-rag", { detail: enabled }));
  } catch {
    /* ignore */
  }
}

/** Hook: reads pmis-accessible-rag from localStorage; re-renders on change. */
export function useAccessibleRag() {
  const [enabled, setEnabledState] = useState(readAccessibleRag);

  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === ACCESSIBLE_RAG_KEY) setEnabledState(readAccessibleRag());
    };
    const onCustom = (e) => setEnabledState(!!e.detail);
    window.addEventListener("storage", onStorage);
    window.addEventListener("pmis-accessible-rag", onCustom);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("pmis-accessible-rag", onCustom);
    };
  }, []);

  const setEnabled = useCallback((v) => {
    writeAccessibleRag(v);
    setEnabledState(v);
  }, []);

  return [enabled, setEnabled];
}

export function injectRagCssVars(root = document.documentElement) {
  root.style.setProperty(RAG_CSS_VARS.green, RAG_COLORS.GREEN);
  root.style.setProperty(RAG_CSS_VARS.amber, RAG_COLORS.AMBER);
  root.style.setProperty(RAG_CSS_VARS.red, RAG_COLORS.RED);
}
