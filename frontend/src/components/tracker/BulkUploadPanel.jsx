import React, { useRef, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { FileArrowDown, UploadSimple } from "@phosphor-icons/react";

function previewRowLabel(tracker, row) {
  const d = row.data || {};
  if (row.status === "error") return row.error || "Invalid row";
  if (tracker === "physical") {
    return `${d.high_court} · ${d.component} · ${d.indicator}${d.district ? ` · ${d.district}` : ""}`;
  }
  if (tracker === "financial") {
    return `${d.high_court} · ${d.component}${d.district ? ` · ${d.district}` : ""}`;
  }
  const dist = d.district ? ` · ${d.district}` : "";
  return `${d.subject || "—"} · ${d.kpi_id || "—"} · ${d.granularity || "—"}${dist}`;
}

function previewRowDetail(tracker, row) {
  const d = row.data || {};
  if (row.status === "error") return "";
  if (tracker === "physical") return `Achieved: ${d.achieved ?? "—"} / Target: ${d.target ?? "—"}`;
  if (tracker === "financial") return `Released: ${d.fund_released ?? "—"} · Utilised: ${d.fund_utilized ?? "—"}`;
  return `Value: ${d.value ?? "—"}`;
}

/**
 * Shared bulk upload with dry-run preview and confirm step.
 */
export default function BulkUploadPanel({ tracker, period, canEdit, templateUrl, onComplete }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewToken, setPreviewToken] = useState(null);

  async function runPreview(file) {
    const fd = new FormData();
    fd.append("file", file);
    const params = new URLSearchParams({ reporting_period: period, dry_run: "true" });
    return api.post(`/${tracker}/bulk?${params}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
  }

  async function runCommit(token) {
    const params = new URLSearchParams({
      reporting_period: period,
      dry_run: "false",
      preview_token: token,
    });
    return api.post(`/${tracker}/bulk?${params.toString()}`);
  }

  async function onFileSelect(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!period) {
      toast.error("Select a reporting period first");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setBusy(true);
    setPreview(null);
    setPreviewToken(null);
    try {
      const r = await runPreview(file);
      setPreview(r.data);
      setPreviewToken(r.data.preview_token || null);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function confirmImport() {
    if (!previewToken || !period) return;
    setBusy(true);
    try {
      const r = await runCommit(previewToken);
      const d = r.data;
      toast.success(`Import complete: ${d.inserted} new, ${d.updated} updated, ${d.skipped} skipped`);
      setPreview(null);
      setPreviewToken(null);
      onComplete?.();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  function cancelPreview() {
    setPreview(null);
    setPreviewToken(null);
  }

  const previewRows = preview?.rows || [];

  return (
    <div className="p-4 space-y-3 text-sm">
      <p className="text-slate-500 text-xs">Upload Excel after selecting a reporting month. Preview validates rows before commit.</p>
      <a href={templateUrl} target="_blank" rel="noreferrer"
        className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
        <FileArrowDown size={14} /> Download Excel template
      </a>
      <label className={`w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-sm uppercase tracking-wider text-xs ${canEdit && period && !busy ? "bg-[#003B73] hover:bg-[#002B54] text-white cursor-pointer" : "bg-slate-300 text-slate-500 cursor-not-allowed"}`}>
        <UploadSimple size={14} /> {busy ? "Processing…" : "Upload & preview"}
        <input ref={inputRef} type="file" accept=".xlsx,.xls" disabled={!canEdit || busy || !period} onChange={onFileSelect} className="hidden" />
      </label>

      {preview && (
        <div className="border border-slate-200 rounded-sm p-3 space-y-2 bg-slate-50">
          <div className="text-xs font-semibold text-slate-700">Preview (dry-run)</div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <span>Valid rows: <strong>{preview.summary?.valid ?? 0}</strong></span>
            <span>Errors: <strong className="text-red-600">{preview.summary?.invalid ?? preview.skipped ?? 0}</strong></span>
            <span>Would insert: <strong>{preview.summary?.would_insert ?? 0}</strong></span>
            <span>Would update: <strong>{preview.summary?.would_update ?? 0}</strong></span>
          </div>

          {previewRows.length > 0 && (
            <div className="max-h-40 overflow-y-auto border border-slate-200 rounded-sm bg-white">
              <table className="w-full text-[10px]">
                <thead className="bg-slate-100 sticky top-0">
                  <tr>
                    <th className="text-left px-2 py-1 font-medium">Row</th>
                    <th className="text-left px-2 py-1 font-medium">Status</th>
                    <th className="text-left px-2 py-1 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.slice(0, 50).map((row, i) => (
                    <tr key={i} className={row.status === "error" ? "bg-red-50 text-red-800" : "bg-emerald-50/60 text-slate-800"}>
                      <td className="px-2 py-1 tabular-nums">{row.row}</td>
                      <td className="px-2 py-1 uppercase tracking-wider">{row.status === "error" ? "Error" : "OK"}</td>
                      <td className="px-2 py-1">
                        <div>{previewRowLabel(tracker, row)}</div>
                        {row.status !== "error" && (
                          <div className="text-slate-500">{previewRowDetail(tracker, row)}</div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(preview.errors?.length > 0) && !previewRows.length && (
            <ul className="text-[10px] text-red-700 max-h-24 overflow-y-auto">
              {preview.errors.slice(0, 8).map((e, i) => (
                <li key={i}>Row {e.row}: {e.error}</li>
              ))}
            </ul>
          )}
          <div className="flex gap-2 pt-1">
            <button type="button" disabled={busy || !previewToken || (preview.summary?.valid ?? 0) === 0} onClick={confirmImport}
              className="flex-1 bg-emerald-700 hover:bg-emerald-800 disabled:bg-slate-400 text-white px-3 py-1.5 rounded-sm text-xs uppercase tracking-wider">
              Confirm import
            </button>
            <button type="button" onClick={cancelPreview}
              className="px-3 py-1.5 border border-slate-300 rounded-sm text-xs uppercase tracking-wider">
              Cancel
            </button>
          </div>
          <p className="text-[10px] text-slate-500">Preview is cached for 30 minutes — confirm without re-uploading the file.</p>
        </div>
      )}
    </div>
  );
}
