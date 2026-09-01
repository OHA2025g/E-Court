import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({
  baseURL: `${BASE}/api`,
  withCredentials: true,
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const url = err?.config?.url || "";
    const isAuthEndpoint = url.includes("/auth/refresh") || url.includes("/auth/login") || url.includes("/auth/me");
    if (err?.response?.status === 401 && !err.config?._retry && !isAuthEndpoint) {
      err.config._retry = true;
      try {
        await api.post("/auth/refresh");
        return api.request(err.config);
      } catch (e) {
        // fall through
      }
    }
    return Promise.reject(err);
  },
);

export function formatApiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && !Array.isArray(detail)) {
    if (typeof detail.message === "string") return detail.message;
    if (typeof detail.msg === "string") return detail.msg;
  }
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export function getApiErrorCode(detail) {
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    return detail.code || null;
  }
  return null;
}

export function fmtNum(n, opts = {}) {
  if (n === null || n === undefined || n === "") return "NA";
  const v = Number(n);
  if (Number.isNaN(v)) return n;
  // Round once from the full-precision value for display (never sum pre-rounded parts).
  const digits = opts.digits ?? 2;
  const factor = 10 ** digits;
  const rounded = Math.round((v + Number.EPSILON) * factor) / factor;
  return rounded.toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

export function fmtPct(n) {
  if (n === null || n === undefined || n === "") return "NA";
  return `${Number(n).toFixed(2)}%`;
}

/** Exact ₹ crore string from integer rupees (no float rounding). */
export function rupeesToCrExactString(rupees) {
  if (rupees === null || rupees === undefined || rupees === "") return "";
  const r = Number(rupees);
  if (!Number.isFinite(r)) return "";
  const sign = r < 0 ? "-" : "";
  const abs = Math.abs(Math.round(r));
  const whole = Math.floor(abs / 1e7);
  const frac = abs % 1e7;
  if (frac === 0) return `${sign}${whole}`;
  const fracStr = String(frac).padStart(7, "0").replace(/0+$/, "");
  return `${sign}${whole}.${fracStr}`;
}

/** Format a financial form field without display rounding (table/dashboard may use fmtNum). */
export function financialFormCr(entry, croreKey, rupeesKey) {
  if (!entry) return "";
  const rupees = entry[rupeesKey];
  if (rupees !== null && rupees !== undefined && rupees !== "") {
    const exact = rupeesToCrExactString(rupees);
    if (exact !== "") return exact;
  }
  const crore = entry[croreKey];
  if (crore === null || crore === undefined || crore === "") return "";
  const v = Number(crore);
  if (!Number.isFinite(v)) return String(crore);
  // Preserve stored precision; avoid fmtNum's 2dp rounding in forms.
  const s = String(v);
  if (s.includes("e") || s.includes("E")) {
    return v.toFixed(10).replace(/\.?0+$/, "");
  }
  return s;
}

/**
 * Authenticated file download via axios (cookies) with a forced local filename.
 * Prefer this over raw <a href> for /api/export/* so Excel/PDF cannot be mixed up
 * by cross-origin navigation, caches, or missing Content-Disposition handling.
 */
export async function downloadApiFile(path, { params = {}, filename } = {}) {
  let res;
  try {
    res = await api.get(path, { params, responseType: "blob" });
  } catch (err) {
    const data = err?.response?.data;
    if (data instanceof Blob) {
      const text = await data.text();
      let detail = text;
      try {
        const parsed = JSON.parse(text);
        detail = parsed?.detail ?? text;
      } catch {
        /* keep raw text */
      }
      throw new Error(formatApiError(detail));
    }
    throw new Error(formatApiError(err?.response?.data?.detail) || err?.message || "Download failed");
  }

  const blob = res.data;
  const headerType = String(res.headers?.["content-type"] || blob?.type || "").toLowerCase();

  // Auth / validation errors often arrive as JSON with blob responseType.
  if (headerType.includes("application/json") || headerType.includes("text/plain")) {
    const text = await blob.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed?.detail ?? text;
    } catch {
      /* keep raw text */
    }
    throw new Error(formatApiError(detail));
  }

  const wantXlsx = String(filename || "").toLowerCase().endsWith(".xlsx");
  const wantPdf = String(filename || "").toLowerCase().endsWith(".pdf");
  const head = new Uint8Array(await blob.slice(0, 5).arrayBuffer());
  const isPdf = head[0] === 0x25 && head[1] === 0x50 && head[2] === 0x44 && head[3] === 0x46; // %PDF
  const isZip = head[0] === 0x50 && head[1] === 0x4b; // PK (xlsx)
  if (wantXlsx && isPdf) {
    throw new Error("Server returned a PDF instead of Excel. Please try again.");
  }
  if (wantPdf && isZip) {
    throw new Error("Server returned an Excel file instead of PDF. Please try again.");
  }

  const mime = wantPdf
    ? "application/pdf"
    : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  const fileBlob = blob.type ? blob : new Blob([blob], { type: mime });
  const url = URL.createObjectURL(fileBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || (wantPdf ? "export.pdf" : "export.xlsx");
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function ragLabel(r) {
  if (!r || r === "NA") return "NA";
  return r;
}

export const BACKEND_URL = BASE;
