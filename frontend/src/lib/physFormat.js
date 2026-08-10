import { fmtNum } from "@/lib/api";

/**
 * Format physical tracker amounts for display.
 * Digitization is stored as crore-pages; convert to absolute pages so Physical
 * UI never looks like financial ₹ Cr.
 */
export function formatPhysAmount(value, uom) {
  if (value === null || value === undefined || value === "") {
    return { text: "NA", unit: "" };
  }
  const v = Number(value);
  if (Number.isNaN(v)) return { text: String(value), unit: "" };

  if (uom === "Crore Pages") {
    return { text: fmtNum(v * 1e7, { digits: 0 }), unit: "pages" };
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

/** User-facing UOM label (avoid "Crore" on Physical surfaces). */
export function displayPhysUom(uom) {
  if (!uom) return uom;
  if (uom === "Crore Pages") return "pages";
  if (uom === "GB / TB / PB") return "GB";
  return uom;
}
