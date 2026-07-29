import React, { useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Printer, FileXls } from "@phosphor-icons/react";
import { api, fmtNum } from "@/lib/api";
import { TID } from "@/lib/testIds";

/** Excel-like pastel RAG fills matching DoJ component-wise report */
const ROW_FILL = {
  GREEN: "#A9D08E",
  AMBER: "#FFE699",
  RED: "#F4B183",
  NA: "#FFFFFF",
};

function reportRag(expPct) {
  if (expPct == null || Number.isNaN(Number(expPct))) return "RED";
  const p = Number(expPct);
  if (p >= 80) return "GREEN";
  if (p > 0) return "AMBER";
  return "RED";
}

function fmtBudget(n) {
  if (n == null || n === "" || Number.isNaN(Number(n))) return "-";
  const v = Number(n);
  return v.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 0 });
}

function fmtExp(utilized, pct) {
  const amt = utilized == null ? "0" : Number(utilized).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  const p = pct == null || Number.isNaN(Number(pct)) ? 0 : Math.round(Number(pct));
  return `${amt} (${p}%)`;
}

function fmtPhysTarget(n) {
  if (n == null || n === "" || Number(n) === 0) return "-";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function fmtPhysAch(pct, target) {
  if (target == null || Number(target) === 0) return "-";
  if (pct == null || Number.isNaN(Number(pct))) return "-";
  return `${Math.round(Number(pct))}%`;
}

/** Compact DoJ-style emblem for report header (decorative branding). */
function DojEmblem() {
  return (
    <div className="cwpf-emblem" aria-hidden="true">
      <svg viewBox="0 0 64 64" width="48" height="48">
        <circle cx="32" cy="32" r="31" fill="#1a237e" />
        <circle cx="32" cy="32" r="26" fill="none" stroke="#c9a227" strokeWidth="2" />
        <g fill="#c9a227">
          <ellipse cx="32" cy="22" rx="7" ry="5" />
          <rect x="28" y="26" width="8" height="14" rx="1" />
          <path d="M18 40 L32 28 L46 40 Z" />
        </g>
        <text x="32" y="54" textAnchor="middle" fill="#c9a227" fontSize="6" fontFamily="serif">सत्यमेव जयते</text>
      </svg>
      <div className="cwpf-emblem-text">
        <div className="cwpf-emblem-hi">न्याय विभाग</div>
        <div className="cwpf-emblem-en">DEPARTMENT OF JUSTICE</div>
      </div>
    </div>
  );
}

/**
 * Pixel-faithful "Demo Component Wise Physical & Financial Report"
 * styled like the DoJ Overall Component Wise Physical & Financial Report.
 */
export default function ComponentWiseDemoReport({ period, periodLabel }) {
  const printRef = useRef(null);

  const { data: rows = [], isLoading, isError } = useQuery({
    queryKey: ["demo-cwpf-report", period],
    queryFn: () =>
      api
        .get("/dashboard/by-component", {
          params: { reporting_period: period || undefined },
        })
        .then((r) => r.data),
  });

  const enriched = useMemo(() => {
    return (rows || []).map((r) => {
      const budget = r.fin_budget ?? r.fin_allocated ?? r.fin_released ?? 0;
      const utilized = r.fin_utilized ?? 0;
      const expPct =
        r.fin_exp_percent != null
          ? r.fin_exp_percent
          : budget
            ? Math.round((utilized / budget) * 10000) / 100
            : r.fin_percent;
      return {
        ...r,
        budget,
        utilized,
        expPct,
        rag: reportRag(expPct),
      };
    });
  }, [rows]);

  const totals = useMemo(() => {
    const budget = enriched.reduce((s, r) => s + (Number(r.budget) || 0), 0);
    const utilized = enriched.reduce((s, r) => s + (Number(r.utilized) || 0), 0);
    return { budget, utilized };
  }, [enriched]);

  const asOnLabel = periodLabel || period || "selected period";

  function handlePrint() {
    window.print();
  }

  function exportCsv() {
    const header = ["Sn", "Component", "Budget", "Expenditure", "Expenditure %", "Physical Target", "Physical Achievement %"];
    const lines = [header.join(",")];
    enriched.forEach((r, i) => {
      lines.push([
        i + 1,
        `"${(r.component || "").replace(/"/g, '""')}"`,
        r.budget ?? "",
        r.utilized ?? "",
        r.expPct ?? "",
        r.phys_target ?? "",
        r.phys_percent ?? "",
      ].join(","));
    });
    lines.push(["", "Total", totals.budget, totals.utilized, "", "", ""].join(","));
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `demo-component-wise-physical-financial-${period || "all"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="cwpf-wrap" data-testid={TID.demoCwpfReport}>
      <div className="cwpf-toolbar no-print">
        <button type="button" onClick={handlePrint} className="cwpf-tool-btn">
          <Printer size={14} /> Print / PDF
        </button>
        <button type="button" onClick={exportCsv} className="cwpf-tool-btn secondary" disabled={!enriched.length}>
          <FileXls size={14} /> Export CSV
        </button>
      </div>

      <div className="cwpf-sheet" ref={printRef}>
        <header className="cwpf-header">
          <div className="cwpf-header-spacer" />
          <h1 className="cwpf-title">
            Demo Component Wise Physical &amp; Financial Report
            <span className="cwpf-title-asof"> as on {asOnLabel}</span>
          </h1>
          <DojEmblem />
        </header>
        <div className="cwpf-rule" />

        {isLoading && <div className="cwpf-status">Loading report…</div>}
        {isError && <div className="cwpf-status error">Unable to load component-wise data.</div>}

        {!isLoading && !isError && (
          <table className="cwpf-table">
            <thead>
              <tr>
                <th className="col-sn">Sn</th>
                <th className="col-comp">Component</th>
                <th className="col-num">Budget</th>
                <th className="col-num">Expenditure (%)</th>
                <th className="col-num">Physical Target</th>
                <th className="col-num">Physical Achievement (%)</th>
              </tr>
            </thead>
            <tbody>
              {enriched.map((r, idx) => (
                <tr key={r.component} style={{ background: ROW_FILL[r.rag] || ROW_FILL.NA }}>
                  <td className="col-sn">{idx + 1}</td>
                  <td className="col-comp">{r.component}</td>
                  <td className="col-num">{fmtBudget(r.budget)}</td>
                  <td className="col-num">{fmtExp(r.utilized, r.expPct)}</td>
                  <td className="col-num">{fmtPhysTarget(r.phys_target)}</td>
                  <td className="col-num">{fmtPhysAch(r.phys_percent, r.phys_target)}</td>
                </tr>
              ))}
              <tr className="cwpf-total">
                <td className="col-sn" />
                <td className="col-comp">Total</td>
                <td className="col-num">{fmtBudget(totals.budget)}</td>
                <td className="col-num">{fmtNum(totals.utilized)}</td>
                <td className="col-num" />
                <td className="col-num" />
              </tr>
            </tbody>
          </table>
        )}

        <p className="cwpf-footnote no-print">
          Budget = Fund Allocated (fallback Released) ₹ Cr · Expenditure = Fund Utilised · Row colour by expenditure %
          (Green ≥80%, Amber &gt;0%, Red 0%). Physical figures roll up all indicators under each BRD component.
        </p>
      </div>

      <style>{`
        .cwpf-wrap { background: #f1f5f9; padding: 12px; border-radius: 2px; }
        .cwpf-toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
        .cwpf-tool-btn {
          display: inline-flex; align-items: center; gap: 6px;
          background: #003B73; color: #fff; border: none; border-radius: 2px;
          padding: 8px 12px; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; cursor: pointer;
        }
        .cwpf-tool-btn.secondary { background: #fff; color: #334155; border: 1px solid #cbd5e1; }
        .cwpf-tool-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .cwpf-sheet {
          background: #fff; padding: 28px 32px 36px; box-shadow: 0 1px 3px rgba(15,23,42,0.12);
          max-width: 1100px; margin: 0 auto;
        }
        .cwpf-header {
          display: grid; grid-template-columns: 100px 1fr 200px; align-items: center; gap: 8px;
          margin-bottom: 8px;
        }
        .cwpf-header-spacer { width: 100px; }
        .cwpf-title {
          margin: 0; text-align: center; font-family: Arial, Helvetica, sans-serif;
          font-size: 20px; font-weight: 700; color: #000; line-height: 1.25; padding-top: 2px;
        }
        .cwpf-title-asof { display: inline; font-size: 20px; font-weight: 700; }
        .cwpf-emblem { display: flex; flex-direction: row; align-items: center; gap: 8px; justify-content: flex-end; }
        .cwpf-emblem-text { text-align: left; line-height: 1.15; }
        .cwpf-emblem-hi { font-size: 13px; font-weight: 700; color: #1a237e; }
        .cwpf-emblem-en { font-size: 8px; font-weight: 700; color: #1a237e; letter-spacing: 0.02em; }
        .cwpf-rule { height: 3px; background: #1e3a5f; margin: 10px 0 14px; }
        .cwpf-table {
          width: 100%; border-collapse: collapse; table-layout: fixed;
          font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #000;
        }
        .cwpf-table th, .cwpf-table td {
          border: 1px solid #000; padding: 6px 8px; vertical-align: middle;
        }
        .cwpf-table thead th {
          background: #e8e8e8; font-weight: 700; text-align: center;
        }
        .cwpf-table .col-sn { width: 48px; text-align: center; }
        .cwpf-table .col-comp { text-align: left; font-weight: 500; }
        .cwpf-table .col-num { text-align: center; font-variant-numeric: tabular-nums; }
        .cwpf-table tbody td.col-comp { font-weight: 400; }
        .cwpf-total td { background: #fff !important; font-weight: 700; }
        .cwpf-status { padding: 24px; text-align: center; color: #64748b; }
        .cwpf-status.error { color: #b91c1c; }
        .cwpf-footnote { margin-top: 12px; font-size: 11px; color: #64748b; line-height: 1.4; }
        @media print {
          .no-print, .app-sidebar, .app-topbar, nav, [data-testid="app-sidebar"] { display: none !important; }
          .cwpf-wrap { background: #fff; padding: 0; }
          .cwpf-sheet { box-shadow: none; max-width: none; padding: 0; }
          .cwpf-title { font-size: 18px; }
          .cwpf-table { font-size: 11px; }
          body { background: #fff; }
        }
      `}</style>
    </div>
  );
}
