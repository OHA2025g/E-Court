import React from "react";
import { cn } from "@/lib/utils";
import { RAG_COLORS, RAG_PATTERNS, useAccessibleRag } from "@/lib/ragColors";

const STYLES = {
  GREEN:  "bg-emerald-100 text-emerald-700 border border-emerald-300",
  AMBER:  "bg-amber-100 text-amber-800 border border-amber-300",
  RED:    "bg-red-100 text-red-700 border border-red-300",
  NA:     "bg-slate-100 text-slate-500 border border-slate-300",
};

const DOT_COLORS = {
  GREEN: RAG_COLORS.GREEN,
  AMBER: RAG_COLORS.AMBER,
  RED: RAG_COLORS.RED,
  NA: RAG_COLORS.NA,
};

function RagIndicator({ status, accessible }) {
  const s = status;
  if (accessible) {
    return (
      <span
        className={cn("w-3 h-3 mr-1.5 shrink-0 border border-slate-400/50", RAG_PATTERNS[s] || RAG_PATTERNS.NA)}
        aria-hidden
      />
    );
  }
  return (
    <span
      className="w-1.5 h-1.5 rounded-full mr-1 shrink-0"
      style={{ background: DOT_COLORS[s] || DOT_COLORS.NA }}
      aria-hidden
    />
  );
}

export default function RagBadge({ status, className, label }) {
  const [accessible] = useAccessibleRag();
  const s = (status || "NA").toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center px-2 py-0.5 rounded-sm text-[11px] font-semibold uppercase tracking-wider",
        STYLES[s] || STYLES.NA,
        accessible && "font-bold",
        className,
      )}
      title={accessible ? `${s} (${label ?? s})` : undefined}
    >
      <RagIndicator status={s} accessible={accessible} />
      {accessible && <span className="mr-0.5 font-mono text-[10px]">{s === "GREEN" ? "●" : s === "AMBER" ? "▲" : s === "RED" ? "■" : "○"}</span>}
      {label ?? (s === "NA" ? "—" : s)}
    </span>
  );
}
