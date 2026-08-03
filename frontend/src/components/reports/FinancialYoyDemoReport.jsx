import React, { useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Printer, FileXls } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TID } from "@/lib/testIds";
import DojEmblem from "@/components/reports/DojEmblem";

/** DoJ Financial Status YoY row fills (legend: ≥50 / 50–20 / <20). */
const ROW_FILL = {
  GREEN: "#92D050",
  AMBER: "#FFC000",
  RED: "#F8CBAD",
  NA: "#FFFFFF",
};

function yoyRag(expPct) {
  if (expPct == null || Number.isNaN(Number(expPct))) return "RED";
  const p = Number(expPct);
  if (p >= 50) return "GREEN";
  if (p >= 20) return "AMBER";
  return "RED";
}

function fmtAmt(n) {
  if (n == null || n === "" || Number.isNaN(Number(n))) return "0";
  const v = Number(n);
  if (v === 0) return "0";
  return v.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 0 });
}

function fmtPctWhole(n) {
  if (n == null || Number.isNaN(Number(n))) return "0%";
  return `${Math.round(Number(n))}%`;
}

/**
 * Pixel-faithful "Demo Financial Status of 24 Components – Year on Year"
 * (uses the system's 17 BRD components; FY cells mapped from tracker fund fields).
 */
export default function FinancialYoyDemoReport({ period, periodLabel }) {
  const printRef = useRef(null);
  const { user } = useAuth();
  const isAdmin = user?.role === "Admin";

  const { data, isLoading, isError } = useQuery({
    queryKey: ["demo-fin-yoy-report", period, isAdmin],
    queryFn: () =>
      api
        .get("/dashboard/financial-status-yoy", {
          params: {
            reporting_period: period || undefined,
            include_unapproved: isAdmin ? true : undefined,
          },
        })
        .then((r) => r.data),
  });

  const rows = useMemo(() => {
    return (data?.rows || []).map((r) => ({
      ...r,
      rag: yoyRag(r.exp_percent_of_allocated),
    }));
  }, [data]);

  const totals = useMemo(() => {
    const sum = (key) => rows.reduce((s, r) => s + (Number(r[key]) || 0), 0);
    const cost = sum("cost_estimation");
    const grandExp = sum("grand_expenditure");
    return {
      cost_estimation: cost,
      fy2324_released: sum("fy2324_released"),
      fy2324_expenditure: sum("fy2324_expenditure"),
      fy2425_released: sum("fy2425_released"),
      fy2425_expenditure: sum("fy2425_expenditure"),
      fy2526_released: sum("fy2526_released"),
      fy2526_expenditure: sum("fy2526_expenditure"),
      fy2627_released: sum("fy2627_released"),
      fy2627_expenditure: sum("fy2627_expenditure"),
      grand_released: sum("grand_released"),
      grand_expenditure: grandExp,
      exp_percent_of_allocated: cost ? Math.round((grandExp / cost) * 10000) / 100 : null,
    };
  }, [rows]);

  const hasData = useMemo(
    () => rows.some((r) => (Number(r.cost_estimation) || 0) > 0 || (Number(r.grand_released) || 0) > 0 || (Number(r.grand_expenditure) || 0) > 0),
    [rows],
  );

  function handlePrint() {
    window.print();
  }

  function exportCsv() {
    const header = [
      "Sr. No.", "Component", "Total Cost estimation for 4 years",
      "FY 2023-24 Total Released", "FY 2023-24 Total Expenditure",
      "FY 2024-25 Total Released", "FY 2024-25 Total Expenditure",
      "FY 2025-26 Total Released", "FY 2025-26 Total Expenditure",
      "FY 2026-27 Total Released", "FY 2026-27 Total Expenditure",
      "Grand Total Released", "Grand Total Expenditure", "Expenditure % of total allocated",
    ];
    const lines = [header.join(",")];
    rows.forEach((r, i) => {
      lines.push([
        i + 1,
        `"${(r.component || "").replace(/"/g, '""')}"`,
        r.cost_estimation ?? 0,
        r.fy2324_released ?? 0,
        r.fy2324_expenditure ?? 0,
        r.fy2425_released ?? 0,
        r.fy2425_expenditure ?? 0,
        r.fy2526_released ?? 0,
        r.fy2526_expenditure ?? 0,
        r.fy2627_released ?? 0,
        r.fy2627_expenditure ?? 0,
        r.grand_released ?? 0,
        r.grand_expenditure ?? 0,
        r.exp_percent_of_allocated ?? 0,
      ].join(","));
    });
    lines.push([
      "", "Total (in crores)",
      totals.cost_estimation, totals.fy2324_released, totals.fy2324_expenditure,
      totals.fy2425_released, totals.fy2425_expenditure, totals.fy2526_released, totals.fy2526_expenditure,
      totals.fy2627_released, totals.fy2627_expenditure, totals.grand_released, totals.grand_expenditure,
      totals.exp_percent_of_allocated ?? "",
    ].join(","));
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `demo-financial-status-yoy-${period || "all"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="fyoy-wrap" data-testid={TID.demoFinYoyReport}>
      <div className="fyoy-toolbar no-print">
        <button type="button" onClick={handlePrint} className="fyoy-tool-btn">
          <Printer size={14} /> Print / PDF
        </button>
        <button type="button" onClick={exportCsv} className="fyoy-tool-btn secondary" disabled={!rows.length}>
          <FileXls size={14} /> Export CSV
        </button>
      </div>

      <div className="fyoy-sheet" ref={printRef}>
        <header className="fyoy-header">
          <h1 className="fyoy-title">Demo Financial Status of 24 Components – Year on Year</h1>
          <div className="fyoy-header-right">
            <DojEmblem />
          </div>
        </header>

        {periodLabel || period ? (
          <p className="fyoy-period no-print">Reporting period: {periodLabel || period}</p>
        ) : null}

        {isLoading && <div className="fyoy-status">Loading report…</div>}
        {isError && <div className="fyoy-status error">Unable to load year-on-year financial data.</div>}

        {!isLoading && !isError && !hasData && (
          <div className="fyoy-status warn no-print">
            No financial figures for this period. Select the baseline period
            (“Baseline — cum. to May 2026”) or another period with loaded tracker data.
          </div>
        )}

        {!isLoading && !isError && (
          <div className="fyoy-table-scroll">
            <table className="fyoy-table">
              <thead>
                <tr>
                  <th rowSpan={2} className="col-sn">Sr. No.</th>
                  <th rowSpan={2} className="col-comp">Component</th>
                  <th rowSpan={2} className="col-num">Total Cost estimation for 4 years</th>
                  <th colSpan={2}>FY 2023-24</th>
                  <th colSpan={2}>FY 2024-25</th>
                  <th colSpan={2}>FY 2025-26</th>
                  <th colSpan={2}>FY 2026-27</th>
                  <th rowSpan={2} className="col-num">Grand Total Released</th>
                  <th rowSpan={2} className="col-num">Grand Total Expenditure</th>
                  <th rowSpan={2} className="col-num">Expenditure % of total allocated</th>
                </tr>
                <tr>
                  <th className="col-num">Total Released</th>
                  <th className="col-num">Total Expenditure</th>
                  <th className="col-num">Total Released</th>
                  <th className="col-num">Total Expenditure</th>
                  <th className="col-num">Total Released</th>
                  <th className="col-num star">Total Expenditure*</th>
                  <th className="col-num">Total Released</th>
                  <th className="col-num star">Total Expenditure*</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, idx) => (
                  <tr key={r.component} style={{ background: ROW_FILL[r.rag] || ROW_FILL.NA }}>
                    <td className="col-sn">{idx + 1}</td>
                    <td className="col-comp">{r.component}</td>
                    <td className="col-num">{fmtAmt(r.cost_estimation)}</td>
                    <td className="col-num">{fmtAmt(r.fy2324_released)}</td>
                    <td className="col-num">{fmtAmt(r.fy2324_expenditure)}</td>
                    <td className="col-num">{fmtAmt(r.fy2425_released)}</td>
                    <td className="col-num">{fmtAmt(r.fy2425_expenditure)}</td>
                    <td className="col-num">{fmtAmt(r.fy2526_released)}</td>
                    <td className="col-num">{fmtAmt(r.fy2526_expenditure)}</td>
                    <td className="col-num">{fmtAmt(r.fy2627_released)}</td>
                    <td className="col-num">{fmtAmt(r.fy2627_expenditure)}</td>
                    <td className="col-num">{fmtAmt(r.grand_released)}</td>
                    <td className="col-num">{fmtAmt(r.grand_expenditure)}</td>
                    <td className="col-num">{fmtPctWhole(r.exp_percent_of_allocated)}</td>
                  </tr>
                ))}
                <tr className="fyoy-total">
                  <td className="col-sn" colSpan={2}>Total (in crores)</td>
                  <td className="col-num">{fmtAmt(totals.cost_estimation)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2324_released)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2324_expenditure)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2425_released)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2425_expenditure)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2526_released)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2526_expenditure)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2627_released)}</td>
                  <td className="col-num">{fmtAmt(totals.fy2627_expenditure)}</td>
                  <td className="col-num">{fmtAmt(totals.grand_released)}</td>
                  <td className="col-num">{fmtAmt(totals.grand_expenditure)}</td>
                  <td className="col-num">{fmtPctWhole(totals.exp_percent_of_allocated)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        <div className="fyoy-legend" aria-label="Expenditure percentage legend">
          <div className="fyoy-leg-item"><span className="fyoy-swatch green" /> ≥ 50% High</div>
          <div className="fyoy-leg-item"><span className="fyoy-swatch amber" /> 50-20% Moderate</div>
          <div className="fyoy-leg-item"><span className="fyoy-swatch red" /> &lt;20% Low</div>
        </div>

        <p className="fyoy-footnote no-print">
          {data?.mapping_note ||
            "Amounts ₹ Cr. Row colour by expenditure % of allocated (Green ≥50%, Amber 20–50%, Red <20%)."}
          {" "}System has {rows.length} BRD components (demo title retains DoJ “24 Components” wording).
        </p>
      </div>

      <style>{`
        .fyoy-wrap { background: #f1f5f9; padding: 8px; border-radius: 2px; width: 100%; }
        .fyoy-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
        .fyoy-tool-btn {
          display: inline-flex; align-items: center; gap: 6px;
          background: #003B73; color: #fff; border: none; border-radius: 2px;
          padding: 8px 12px; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; cursor: pointer;
        }
        .fyoy-tool-btn.secondary { background: #fff; color: #334155; border: 1px solid #cbd5e1; }
        .fyoy-tool-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .fyoy-sheet {
          background: #fff; padding: 16px 12px 24px; box-shadow: 0 1px 3px rgba(15,23,42,0.12);
          width: 100%; max-width: none; margin: 0; overflow: visible;
        }
        .fyoy-header {
          display: flex; justify-content: space-between; align-items: center; gap: 16px;
          margin-bottom: 10px; flex-wrap: nowrap;
        }
        .fyoy-title {
          margin: 0; font-family: Georgia, "Times New Roman", serif;
          font-size: 20px; font-weight: 700; color: #000; line-height: 1.2;
          white-space: nowrap; max-width: none; flex: 1 1 auto; min-width: 0;
        }
        .fyoy-header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
        .fyoy-legend {
          display: flex; flex-direction: row; flex-wrap: wrap; justify-content: center; align-items: center;
          gap: 20px; margin: 14px auto 4px; font-size: 12px; color: #111; width: 100%;
        }
        .fyoy-leg-item { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
        .fyoy-swatch { width: 28px; height: 14px; border: 1px solid #333; display: inline-block; flex-shrink: 0; }
        .fyoy-swatch.green { background: #92D050; }
        .fyoy-swatch.amber { background: #FFC000; }
        .fyoy-swatch.red { background: #F8CBAD; }
        .fyoy-period { margin: 0 0 8px; font-size: 12px; color: #475569; }
        .fyoy-table-scroll { overflow-x: visible; width: 100%; }
        .fyoy-table {
          width: 100%; border-collapse: collapse; table-layout: fixed;
          font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #000;
        }
        .fyoy-table th, .fyoy-table td {
          border: 1px solid #000; padding: 3px 2px; vertical-align: middle;
          word-wrap: break-word; overflow-wrap: anywhere;
        }
        .fyoy-table thead th {
          background: #bdbdbd; font-weight: 700; text-align: center; line-height: 1.15;
        }
        .fyoy-table thead th.star { color: #c62828; }
        .fyoy-table .col-sn { width: 3%; text-align: center; }
        .fyoy-table .col-comp { text-align: left; width: 14%; }
        .fyoy-table .col-num { text-align: center; font-variant-numeric: tabular-nums; white-space: normal; }
        .fyoy-total td { background: #dce6f1 !important; font-weight: 700; }
        .fyoy-status { padding: 24px; text-align: center; color: #64748b; }
        .fyoy-status.error { color: #b91c1c; }
        .fyoy-status.warn { color: #92400e; background: #fffbeb; border: 1px solid #fcd34d; padding: 12px; margin-bottom: 12px; }
        .fyoy-footnote { margin-top: 12px; font-size: 11px; color: #64748b; line-height: 1.4; }
        @media print {
          .no-print, .app-sidebar, .app-topbar, nav, [data-testid="app-sidebar"] { display: none !important; }
          .fyoy-wrap { background: #fff; padding: 0; }
          .fyoy-sheet { box-shadow: none; max-width: none; padding: 0; }
          .fyoy-table { font-size: 8px; }
          body { background: #fff; }
        }
      `}</style>
    </div>
  );
}
