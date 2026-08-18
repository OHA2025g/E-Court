import React, { useMemo, useState } from "react";
import { ArrowsLeftRight, Database, FileXls, WarningCircle } from "@phosphor-icons/react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

function fmt(v) {
  if (v == null || v === "") return "NA";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function FieldTable({ title, tone, entries }) {
  const list = Object.entries(entries || {});
  const tones = {
    amber: "border-amber-200 bg-amber-50/70",
    emerald: "border-emerald-200 bg-emerald-50/70",
    slate: "border-slate-200 bg-slate-50",
  };
  const heads = {
    amber: "text-amber-900",
    emerald: "text-emerald-900",
    slate: "text-slate-800",
  };
  return (
    <div className={`rounded-sm border ${tones[tone] || tones.slate} overflow-hidden`}>
      <div className={`px-2 py-1.5 text-[10px] uppercase tracking-wider font-semibold border-b ${heads[tone] || heads.slate}`}>
        {title}
      </div>
      <div className="max-h-48 overflow-y-auto text-[11px]">
        {list.length === 0 && <div className="px-2 py-2 text-slate-400">No data</div>}
        {list.map(([k, v]) => (
          <div key={k} className="grid grid-cols-2 gap-1 px-2 py-1 border-b border-black/5 last:border-0">
            <span className="text-slate-500 truncate" title={k}>{k}</span>
            <span className="font-medium text-slate-800 break-all">{fmt(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stage2Diff({ template, database }) {
  const keys = useMemo(() => {
    const set = new Set([
      ...Object.keys(template || {}),
      ...Object.keys(database || {}).map((k) => {
        // normalize snake_case db keys to template labels when possible
        const map = {
          high_court: "High Court",
          component: "Component",
          indicator: "Sub-Component",
          sub_component: "Sub-Component",
          subject: "Subject",
          kpi_id: "KPI ID",
          granularity: "Granularity",
          district: "District",
          target: "Target",
          achieved: "Achieved",
          fund_released: "Fund Released",
          fund_utilized: "Fund Utilized",
          value: "Value",
          baseline: "Baseline",
          remarks: "Remarks",
        };
        return map[k] || k;
      }),
    ]);
    return Array.from(set);
  }, [template, database]);

  const dbByLabel = useMemo(() => {
    const d = database || {};
    const out = { ...d };
    const pairs = [
      ["High Court", d.high_court],
      ["Component", d.component],
      ["Sub-Component", d.indicator ?? d.sub_component],
      ["Subject", d.subject],
      ["KPI ID", d.kpi_id],
      ["Granularity", d.granularity],
      ["District", d.district],
      ["Target", d.target],
      ["Achieved", d.achieved],
      ["Fund Released", d.fund_released],
      ["Fund Utilized", d.fund_utilized],
      ["Value", d.value],
      ["Baseline", d.baseline],
      ["Remarks", d.remarks],
    ];
    pairs.forEach(([k, v]) => {
      if (v !== undefined) out[k] = v;
    });
    return out;
  }, [database]);

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-sm">
      <table className="w-full text-[11px]">
        <thead className="bg-slate-100 sticky top-0">
          <tr>
            <th className="text-left px-2 py-1.5 font-semibold">Field</th>
            <th className="text-left px-2 py-1.5 font-semibold text-emerald-800">Template (from Excel)</th>
            <th className="text-left px-2 py-1.5 font-semibold text-slate-700">Database (current)</th>
            <th className="text-left px-2 py-1.5 font-semibold">Change</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const t = (template || {})[k];
            const d = dbByLabel[k];
            const changed = database != null && fmt(t) !== fmt(d);
            const neu = database == null;
            return (
              <tr key={k} className={changed ? "bg-amber-50/80" : neu ? "bg-emerald-50/50" : "bg-white"}>
                <td className="px-2 py-1 border-t border-slate-100 text-slate-600">{k}</td>
                <td className="px-2 py-1 border-t border-slate-100 font-medium">{fmt(t)}</td>
                <td className="px-2 py-1 border-t border-slate-100">{database == null ? "- (new)" : fmt(d)}</td>
                <td className="px-2 py-1 border-t border-slate-100 uppercase tracking-wider text-[10px]">
                  {neu ? <span className="text-emerald-700">Insert</span> : changed ? <span className="text-amber-800">Update</span> : <span className="text-slate-400">Same</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Full-screen-ish popup for bulk dry-run:
 * Stage 1 = uploaded Excel ↔ template columns/values
 * Stage 2 = Excel/template ↔ database existing values
 */
export default function BulkMappingPreviewModal({
  open,
  onOpenChange,
  tracker,
  period,
  preview,
  busy,
  canConfirm,
  onConfirm,
  onCancel,
}) {
  const [stage, setStage] = useState(1);
  const [page, setPage] = useState(0);
  const pageSize = 25;

  const rows = preview?.rows || [];
  const columnMappings = preview?.column_mappings || [];
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const pageRows = rows.slice(page * pageSize, page * pageSize + pageSize);

  const summary = preview?.summary || {};

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-[96vw] w-[1100px] max-h-[92vh] overflow-hidden flex flex-col p-0 gap-0"
        data-testid="bulk-mapping-modal"
      >
        <DialogHeader className="px-5 py-4 border-b border-slate-200 shrink-0">
          <DialogTitle className="font-display text-xl text-slate-900">
            Bulk mapping preview · {tracker} · {period}
          </DialogTitle>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-slate-600 mt-2">
            <span>Valid: <strong>{summary.valid ?? 0}</strong></span>
            <span>Errors: <strong className="text-red-600">{summary.invalid ?? 0}</strong></span>
            <span>Would insert: <strong>{summary.would_insert ?? 0}</strong></span>
            <span>Would update: <strong>{summary.would_update ?? 0}</strong></span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Showing {rows.length} of {preview?.rows_total ?? rows.length} mapped rows
            {(preview?.rows_total || 0) > rows.length ? " (preview capped for performance)" : ""}.
          </p>
        </DialogHeader>

        <div className="px-5 pt-3 flex gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setStage(1)}
            className={`px-3 py-1.5 text-xs uppercase tracking-wider rounded-sm border ${
              stage === 1 ? "bg-[#003B73] text-white border-[#003B73]" : "bg-white text-slate-700 border-slate-300"
            }`}
            data-testid="bulk-map-stage-1"
          >
            Stage 1 · Excel → Template
          </button>
          <button
            type="button"
            onClick={() => setStage(2)}
            className={`px-3 py-1.5 text-xs uppercase tracking-wider rounded-sm border ${
              stage === 2 ? "bg-[#003B73] text-white border-[#003B73]" : "bg-white text-slate-700 border-slate-300"
            }`}
            data-testid="bulk-map-stage-2"
          >
            Stage 2 · Excel/Template → Database
          </button>
        </div>

        <div className="px-5 py-3 overflow-y-auto flex-1 min-h-0 space-y-4">
          {stage === 1 && (
            <>
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 mb-2 flex items-center gap-2">
                  <ArrowsLeftRight size={14} /> Column mapping (uploaded header → PMIS template)
                </h3>
                <div className="overflow-x-auto border border-slate-200 rounded-sm">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-100">
                      <tr>
                        <th className="text-left px-2 py-1.5">#</th>
                        <th className="text-left px-2 py-1.5 bg-amber-50/80">Uploaded Excel column</th>
                        <th className="text-center px-2 py-1.5">→</th>
                        <th className="text-left px-2 py-1.5 bg-emerald-50/80">Template field</th>
                        <th className="text-left px-2 py-1.5">Transform</th>
                      </tr>
                    </thead>
                    <tbody>
                      {columnMappings.map((m, i) => (
                        <tr key={i} className="odd:bg-white even:bg-slate-50/70">
                          <td className="px-2 py-1 border-t border-slate-100">{i + 1}</td>
                          <td className="px-2 py-1 border-t border-slate-100 bg-amber-50/40">{m.source}</td>
                          <td className="px-2 py-1 border-t border-slate-100 text-center text-slate-400">→</td>
                          <td className="px-2 py-1 border-t border-slate-100 bg-emerald-50/40 font-medium">{m.target}</td>
                          <td className="px-2 py-1 border-t border-slate-100 text-slate-600">{m.transform}</td>
                        </tr>
                      ))}
                      {columnMappings.length === 0 && (
                        <tr><td colSpan={5} className="px-2 py-3 text-slate-500">No column map returned.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 mb-2 flex items-center gap-2">
                  <FileXls size={14} /> Row mapping · uploaded values ↔ template values
                </h3>
                <div className="space-y-3">
                  {pageRows.map((row) => (
                    <div
                      key={`s1-${row.row}`}
                      className={`border rounded-sm p-3 ${row.status === "error" ? "border-red-300 bg-red-50/40" : "border-slate-200"}`}
                    >
                      <div className="flex justify-between text-[10px] uppercase tracking-wider text-slate-500 mb-2">
                        <span>Excel row {row.row}</span>
                        {row.status === "error" ? (
                          <span className="text-red-700 inline-flex items-center gap-1"><WarningCircle size={12} /> {row.error}</span>
                        ) : (
                          <span className="text-emerald-700">OK · will {row.action || "write"}</span>
                        )}
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <FieldTable title="Uploaded Excel" tone="amber" entries={row.excel} />
                        <FieldTable title="PMIS template format" tone="emerald" entries={row.template} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {stage === 2 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 mb-2 flex items-center gap-2">
                <Database size={14} /> Field diff · template (from Excel) vs database
              </h3>
              <div className="space-y-4">
                {pageRows.map((row) => (
                  <div
                    key={`s2-${row.row}`}
                    className={`border rounded-sm p-3 ${row.status === "error" ? "border-red-300 bg-red-50/40" : "border-slate-200"}`}
                  >
                    <div className="flex justify-between text-[10px] uppercase tracking-wider text-slate-500 mb-2">
                      <span>Excel row {row.row}</span>
                      <span>
                        {row.status === "error"
                          ? row.error
                          : row.action === "insert"
                            ? "New record (not in DB)"
                            : "Existing record will update"}
                      </span>
                    </div>
                    {row.status === "error" ? (
                      <p className="text-sm text-red-700">{row.error}</p>
                    ) : (
                      <>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-2 mb-2">
                          <FieldTable title="Uploaded Excel" tone="amber" entries={row.excel} />
                          <FieldTable title="Template" tone="emerald" entries={row.template} />
                          <FieldTable title="Database" tone="slate" entries={row.database || {}} />
                        </div>
                        <Stage2Diff template={row.template} database={row.database} />
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {rows.length === 0 && (
            <p className="text-sm text-slate-500">No preview rows.</p>
          )}
        </div>

        <div className="px-5 py-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600 shrink-0">
          <span>Page {page + 1} / {pageCount}</span>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 0} onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="px-2 py-1 border border-slate-300 rounded-sm disabled:opacity-40">Prev</button>
            <button type="button" disabled={page >= pageCount - 1} onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              className="px-2 py-1 border border-slate-300 rounded-sm disabled:opacity-40">Next</button>
          </div>
        </div>

        <DialogFooter className="px-5 py-4 border-t border-slate-200 bg-slate-50 shrink-0 flex-row gap-2 sm:justify-between">
          <p className="text-[11px] text-slate-500 self-center">
            Preview cached 30 minutes - confirm without re-uploading.
          </p>
          <div className="flex gap-2">
            <button type="button" onClick={onCancel}
              className="px-4 py-2 border border-slate-300 rounded-sm text-xs uppercase tracking-wider bg-white">
              Cancel
            </button>
            <button
              type="button"
              disabled={!canConfirm || busy}
              onClick={onConfirm}
              data-testid="bulk-mapping-confirm"
              className="px-4 py-2 rounded-sm text-xs uppercase tracking-wider text-white bg-emerald-700 hover:bg-emerald-800 disabled:bg-slate-400"
            >
              {busy ? "Importing…" : "Confirm import"}
            </button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
