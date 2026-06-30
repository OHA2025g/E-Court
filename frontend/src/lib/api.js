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
  if (n === null || n === undefined || n === "") return "—";
  const v = Number(n);
  if (Number.isNaN(v)) return n;
  return v.toLocaleString("en-IN", { maximumFractionDigits: opts.digits ?? 2 });
}

export function fmtPct(n) {
  if (n === null || n === undefined || n === "") return "—";
  return `${Number(n).toFixed(2)}%`;
}

export function ragLabel(r) {
  if (!r || r === "NA") return "—";
  return r;
}

export const BACKEND_URL = BASE;
