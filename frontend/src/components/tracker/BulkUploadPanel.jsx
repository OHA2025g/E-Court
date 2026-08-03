import React, { useRef, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { FileArrowDown, UploadSimple } from "@phosphor-icons/react";
import BulkMappingPreviewModal from "@/components/tracker/BulkMappingPreviewModal";

/**
 * Shared bulk upload with dry-run mapping popup (Stage 1 + Stage 2) and confirm.
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

  return (
    <div className="p-4 space-y-3 text-sm">
      <p className="text-slate-500 text-xs">
        Upload Excel after selecting a reporting month. A mapping popup shows Stage 1 (Excel → template)
        and Stage 2 (Excel/template → database) before you confirm.
      </p>
      <a href={templateUrl} target="_blank" rel="noreferrer"
        className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
        <FileArrowDown size={14} /> Download Excel template
      </a>
      <label className={`w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-sm uppercase tracking-wider text-xs ${canEdit && period && !busy ? "bg-[#003B73] hover:bg-[#002B54] text-white cursor-pointer" : "bg-slate-300 text-slate-500 cursor-not-allowed"}`}>
        <UploadSimple size={14} /> {busy ? "Processing…" : "Upload & preview"}
        <input ref={inputRef} type="file" accept=".xlsx,.xls" disabled={!canEdit || busy || !period} onChange={onFileSelect} className="hidden" />
      </label>

      <BulkMappingPreviewModal
        open={Boolean(preview)}
        onOpenChange={(open) => { if (!open) cancelPreview(); }}
        tracker={tracker}
        period={period}
        preview={preview}
        busy={busy}
        canConfirm={Boolean(previewToken) && (preview?.summary?.valid ?? 0) > 0}
        onConfirm={confirmImport}
        onCancel={cancelPreview}
      />
    </div>
  );
}
