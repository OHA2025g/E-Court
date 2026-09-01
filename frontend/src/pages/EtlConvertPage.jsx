import React, { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowsLeftRight, CheckCircle, UploadSimple, WarningCircle } from "@phosphor-icons/react";
import Card from "@/components/Card";
import { SelectField } from "@/pages/PhysicalTracker";
import { api, formatApiError } from "@/lib/api";
import { TID } from "@/lib/testIds";
import { toast } from "sonner";

const TRACKERS = [
  {
    id: "physical",
    label: "Physical Tracker",
    hint: "Consolidated Sr.No long sheet, wide DoJ Physical_Tracker, or long-format bulk template",
    desired: "High Court · Component · Sub-Component · District · Target · Achieved · Remarks",
  },
  {
    id: "financial",
    label: "Financial Tracker",
    hint: "Consolidated Sr.No long sheet, wide Funds_Released / Funds_Utilised, or long-format bulk template",
    desired: "High Court · Component · District · Fund Released · Fund Utilized · Remarks",
  },
  {
    id: "outcome",
    label: "Outcome Tracker",
    hint: "Phase-4 Outcome Excel or long-format bulk template",
    desired: "High Court · Subject · KPI ID · Granularity · Value · Baseline · District · Remarks",
  },
];

function fmtCell(v) {
  if (v == null || v === "") return "-";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function MappingPair({ source, target }) {
  const srcEntries = Object.entries(source || {});
  const tgtEntries = Object.entries(target || {});
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
      <div className="rounded-sm border border-amber-200 bg-amber-50/60 p-2">
        <div className="text-[9px] uppercase tracking-wider text-amber-800 mb-1">Input</div>
        {srcEntries.length === 0 && <div className="text-slate-400">-</div>}
        {srcEntries.map(([k, v]) => (
          <div key={k} className="flex gap-1 border-b border-amber-100/80 py-0.5 last:border-0">
            <span className="text-slate-500 shrink-0 w-[40%]">{k}</span>
            <span className="font-medium text-slate-800 break-all">{fmtCell(v)}</span>
          </div>
        ))}
      </div>
      <div className="rounded-sm border border-emerald-200 bg-emerald-50/60 p-2">
        <div className="text-[9px] uppercase tracking-wider text-emerald-800 mb-1">PMIS format</div>
        {tgtEntries.length === 0 && <div className="text-slate-400">-</div>}
        {tgtEntries.map(([k, v]) => (
          <div key={k} className="flex gap-1 border-b border-emerald-100/80 py-0.5 last:border-0">
            <span className="text-slate-500 shrink-0 w-[40%]">{k}</span>
            <span className="font-medium text-slate-800 break-all">{fmtCell(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EtlConvertPage() {
  const qc = useQueryClient();
  const inputRef = useRef(null);
  const [trackerId, setTrackerId] = useState("physical");
  const [period, setPeriod] = useState("");
  const [finMode, setFinMode] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [result, setResult] = useState(null);
  const [approved, setApproved] = useState(false);

  const periods = useQuery({
    queryKey: ["periods"],
    queryFn: () => api.get("/master/periods").then((r) => r.data),
  });

  const tracker = useMemo(
    () => TRACKERS.find((t) => t.id === trackerId) || TRACKERS[0],
    [trackerId],
  );

  const periodOptions = useMemo(
    () => (periods.data || []).map((p) => ({ label: p.label, value: p.period })),
    [periods.data],
  );

  useEffect(() => {
    if (!period && periodOptions.length) {
      const preferred =
        periodOptions.find((p) => p.value === "2026-05") ||
        periodOptions.find((p) => p.value === "2025-09") ||
        periodOptions[periodOptions.length - 1];
      if (preferred) setPeriod(preferred.value);
    }
  }, [period, periodOptions]);

  async function onFileSelect(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!period) {
      toast.error("Select a reporting period first");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setBusy(true);
    setResult(null);
    setApproved(false);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const params = new URLSearchParams({
        tracker: trackerId,
        reporting_period: period,
        mode: trackerId === "financial" ? finMode : "auto",
      });
      const r = await api.post(`/etl/convert?${params}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(r.data);
      toast.success(`Converted ${r.data.row_mappings_total || 0} row(s) · format: ${r.data.format_detected}`);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function commitPush() {
    if (!result?.preview_token || !period || !approved) return;
    setCommitting(true);
    try {
      const params = new URLSearchParams({
        tracker: trackerId,
        reporting_period: period,
      });
      const fd = new FormData();
      fd.append("preview_token", result.preview_token);
      const r = await api.post(`/etl/commit?${params}`, fd);
      const d = r.data;
      toast.success(`Pushed to ${tracker.label}: ${d.inserted} new, ${d.updated} updated, ${d.skipped} skipped`);
      qc.invalidateQueries({ queryKey: [trackerId] });
      qc.invalidateQueries({ queryKey: [`${trackerId}-hc-period`] });
      setResult(null);
      setApproved(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setCommitting(false);
    }
  }

  const columnMappings = result?.column_mappings || [];
  const rowMappings = result?.row_mappings || [];
  const validation = result?.validation || {};
  const issues = result?.issues || [];

  return (
    <div className="space-y-6" data-testid={TID.etlConvertPage}>
      <div>
        <h2 className="font-display text-2xl text-slate-900 tracking-tight">ETL Convert &amp; Map</h2>
        <p className="text-sm text-slate-500 mt-1 max-w-3xl">
          Upload DoJ / source Excel for any tracker, review 1:1 field mapping against the PMIS format,
          then approve to push into that tracker only.
        </p>
      </div>

      <Card title="1 · Choose tracker &amp; period" subtitle="Conversion does not write until you approve">
        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <label className="block sm:col-span-2">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">Tracker</span>
            <div className="mt-1 flex flex-wrap gap-2" role="tablist">
              {TRACKERS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={trackerId === t.id}
                  data-testid={`etl-tab-${t.id}`}
                  onClick={() => {
                    setTrackerId(t.id);
                    setResult(null);
                    setApproved(false);
                  }}
                  className={`px-3 py-2 rounded-sm text-xs uppercase tracking-wider border ${
                    trackerId === t.id
                      ? "bg-[#003B73] text-white border-[#003B73]"
                      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-slate-500">{tracker.hint}</p>
            <p className="mt-1 text-[11px] text-slate-600">
              <span className="font-medium">Desired headers:</span> {tracker.desired}
            </p>
          </label>
          <SelectField
            testid={TID.periodSelect}
            label="Reporting month"
            value={period}
            onChange={(v) => {
              setPeriod(v);
              setResult(null);
              setApproved(false);
            }}
            options={periodOptions}
          />
          {trackerId === "financial" && (
            <label className="block">
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">Fund mode</span>
              <select
                data-testid="etl-fin-mode"
                className="mt-1 w-full border border-slate-300 rounded-sm px-2 py-2 text-sm"
                value={finMode}
                onChange={(e) => setFinMode(e.target.value)}
              >
                <option value="auto">Auto-detect sheet</option>
                <option value="released">Funds Released</option>
                <option value="utilised">Funds Utilised</option>
              </select>
            </label>
          )}
        </div>
      </Card>

      <Card title="2 · Upload source Excel" subtitle="Wide DoJ files are converted automatically; long templates pass through">
        <div className="p-4 space-y-3">
          <label
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-sm uppercase tracking-wider text-xs ${
              period && !busy
                ? "bg-[#003B73] hover:bg-[#002B54] text-white cursor-pointer"
                : "bg-slate-300 text-slate-500 cursor-not-allowed"
            }`}
          >
            <UploadSimple size={14} />
            {busy ? "Converting…" : "Upload & convert"}
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls"
              disabled={!period || busy}
              onChange={onFileSelect}
              className="hidden"
              data-testid={TID.etlConvertUpload}
            />
          </label>
        </div>
      </Card>

      {result && (
        <>
          <Card
            title="3 · Column mapping (1:1)"
            subtitle={`Detected: ${result.format_detected} · Sheet: ${result.sheet || "-"} · Rows: ${result.row_mappings_total || 0}`}
          >
            <div className="p-4 overflow-x-auto">
              <table className="w-full text-xs border-collapse" data-testid={TID.etlColumnMapTable}>
                <thead>
                  <tr className="bg-slate-100 text-left">
                    <th className="border border-slate-200 px-2 py-1.5 w-[5%]">#</th>
                    <th className="border border-slate-200 px-2 py-1.5 w-[32%]">Input column / block</th>
                    <th className="border border-slate-200 px-2 py-1.5 w-[8%] text-center">
                      <ArrowsLeftRight size={14} className="inline" />
                    </th>
                    <th className="border border-slate-200 px-2 py-1.5 w-[32%]">Desired PMIS field</th>
                    <th className="border border-slate-200 px-2 py-1.5">Transform</th>
                  </tr>
                </thead>
                <tbody>
                  {columnMappings.map((m, i) => (
                    <tr key={i} className="odd:bg-white even:bg-slate-50/80">
                      <td className="border border-slate-200 px-2 py-1.5 text-center">{i + 1}</td>
                      <td className="border border-slate-200 px-2 py-1.5 bg-amber-50/40">{m.source}</td>
                      <td className="border border-slate-200 px-2 py-1.5 text-center text-slate-400">→</td>
                      <td className="border border-slate-200 px-2 py-1.5 bg-emerald-50/40 font-medium">{m.target}</td>
                      <td className="border border-slate-200 px-2 py-1.5 text-slate-600">{m.transform}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card
            title="4 · Row mapping preview"
            subtitle={`Showing ${rowMappings.length} of ${result.row_mappings_total || 0} converted rows (input ↔ PMIS)`}
          >
            <div className="p-4 space-y-3 max-h-[480px] overflow-y-auto" data-testid={TID.etlRowMapList}>
              {rowMappings.map((rm, i) => (
                <div
                  key={i}
                  className={`border rounded-sm p-2 ${
                    rm.status === "error" ? "border-red-300 bg-red-50/50" : "border-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1 text-[10px] uppercase tracking-wider text-slate-500">
                    <span>Source row {rm.source_row ?? "-"}</span>
                    {rm.status === "error" ? (
                      <span className="text-red-600 inline-flex items-center gap-1">
                        <WarningCircle size={12} /> {rm.error || "Error"}
                      </span>
                    ) : (
                      <span className="text-emerald-700 inline-flex items-center gap-1">
                        <CheckCircle size={12} /> Mapped
                      </span>
                    )}
                  </div>
                  <MappingPair source={rm.source} target={rm.target} />
                </div>
              ))}
              {rowMappings.length === 0 && (
                <p className="text-sm text-slate-500">No rows produced - check sheet format and aliases.</p>
              )}
            </div>
          </Card>

          <Card title="5 · Validation (dry-run)" subtitle="Against live masters before commit">
            <div className="p-4 space-y-2 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <span>Valid: <strong>{validation.summary?.valid ?? 0}</strong></span>
                <span>Invalid: <strong className="text-red-600">{validation.summary?.invalid ?? 0}</strong></span>
                <span>Would insert: <strong>{validation.summary?.would_insert ?? 0}</strong></span>
                <span>Would update: <strong>{validation.summary?.would_update ?? 0}</strong></span>
              </div>
              {(issues.length > 0 || (validation.errors || []).length > 0) && (
                <ul className="list-disc pl-5 text-red-700 space-y-0.5 max-h-32 overflow-y-auto">
                  {issues.slice(0, 20).map((iss, i) => (
                    <li key={`i-${i}`}>Row {iss.row}: {iss.error}</li>
                  ))}
                  {(validation.errors || []).slice(0, 20).map((err, i) => (
                    <li key={`e-${i}`}>{typeof err === "string" ? err : JSON.stringify(err)}</li>
                  ))}
                </ul>
              )}
            </div>
          </Card>

          <Card title="6 · Approve &amp; push" subtitle={`Writes to ${tracker.label} for period ${period}`}>
            <div className="p-4 space-y-3">
              <label className="flex items-start gap-2 text-sm text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={approved}
                  onChange={(e) => setApproved(e.target.checked)}
                  data-testid={TID.etlApproveCheckbox}
                />
                <span>
                  I have reviewed the 1:1 mapping above and approve pushing these converted rows into the{" "}
                  <strong>{tracker.label}</strong> for <strong>{period}</strong>.
                </span>
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!approved || !result.can_commit || committing}
                  onClick={commitPush}
                  data-testid={TID.etlCommitBtn}
                  className={`px-4 py-2 rounded-sm text-xs uppercase tracking-wider ${
                    approved && result.can_commit && !committing
                      ? "bg-emerald-700 hover:bg-emerald-800 text-white"
                      : "bg-slate-300 text-slate-500 cursor-not-allowed"
                  }`}
                >
                  {committing ? "Pushing…" : "Approve & push to tracker"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setResult(null);
                    setApproved(false);
                  }}
                  className="px-4 py-2 rounded-sm text-xs uppercase tracking-wider border border-slate-300 bg-white hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
              {!result.can_commit && (
                <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 px-2 py-1.5 rounded-sm">
                  Commit disabled - no valid rows after dry-run validation. Fix source data or aliases and re-upload.
                </p>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
