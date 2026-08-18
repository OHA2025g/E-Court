import { fmtNum } from "@/lib/api";
import { formatPhysTargetAchieved } from "@/lib/physFormat";

/**
 * Heatmap-style count line for India map hover (mirrors ComponentHcHeatmap cellDetail).
 * Returns null when there are no absolute counts to show (caller can fall back to %).
 */
export function mapHoverCounts(info, metric) {
  if (!info || info.in_scope === false) return null;

  if (metric === "financial") {
    if (info.released == null && info.utilized == null) return null;
    return `Released ₹${fmtNum(info.released)} Cr / Utilised ₹${fmtNum(info.utilized)} Cr`;
  }

  if (metric === "outcome") {
    if (info.total == null && info.reported == null) return null;
    const reported = info.reported == null ? "NA" : String(info.reported);
    const total = info.total == null ? "NA" : String(info.total);
    return `Reported ${reported} / ${total} KPIs`;
  }

  // Physical: skip absolute when UOMs are mixed.
  if (info.mixed_uom || (info.target == null && info.achieved == null)) return null;
  return formatPhysTargetAchieved(info.target, info.achieved, info.uom);
}

/** Full one-line detail matching heatmap footer hint style. */
export function mapHoverDetail(info, metric, metricLabel) {
  if (!info) return null;
  const rag = info.rag || "NA";
  const hc = info.high_court || "-";
  const head = `${info.name || "State"} · ${hc}`;

  if (info.in_scope === false) {
    return `${head}: Outside your jurisdiction`;
  }

  const counts = mapHoverCounts(info, metric);
  if (counts) {
    return `${head}: ${counts} (${rag})`;
  }

  const pctBit = info.percent != null
    ? `${metricLabel}: ${Number(info.percent).toFixed(1)}%`
    : `${metricLabel}: No data for this HC`;
  return `${head}: ${pctBit} (${rag})`;
}
