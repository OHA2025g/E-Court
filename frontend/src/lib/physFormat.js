import { fmtNum } from "@/lib/api";

/**
 * Format physical tracker amounts for display.
 *
 * Digitization is stored as Crore Pages (same scale as the tracker /
 * "No of pages digitized (in Cr.)"). Show that scale with unit "Cr pages"
 * — never multiply into absolute pages (inflates KPI cards), and never use
 * bare "Crore" (reads like financial ₹ Cr).
 */
export function formatPhysAmount(value, uom) {
  if (value === null || value === undefined || value === "") {
    return { text: "NA", unit: "" };
  }
  const v = Number(value);
  if (Number.isNaN(v)) return { text: String(value), unit: "" };

  if (uom === "Crore Pages") {
    return { text: fmtNum(v, { digits: 2 }), unit: "Cr pages" };
  }
  if (uom === "GB / TB / PB" || uom === "GB") {
    return { text: fmtNum(v, { digits: 2 }), unit: "GB" };
  }
  if (uom === "Percentage") {
    return { text: fmtNum(v, { digits: 2 }), unit: "%" };
  }
  return { text: fmtNum(v, { digits: 0 }), unit: "" };
}

export function formatPhysTargetAchieved(target, achieved, uom) {
  const t = formatPhysAmount(target, uom);
  const a = formatPhysAmount(achieved, uom);
  const unit = t.unit || a.unit;
  if (unit) {
    return `Target ${t.text} ${unit} / Achieved ${a.text} ${unit}`;
  }
  return `Target ${t.text} / Achieved ${a.text}`;
}

/** User-facing UOM label (avoid bare "Crore" on Physical surfaces). */
export function displayPhysUom(uom) {
  if (!uom) return uom;
  if (uom === "Crore Pages") return "Cr pages";
  if (uom === "GB / TB / PB") return "GB";
  return uom;
}
