import React, { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { UploadSimple, FileXls, Info, Trash } from "@phosphor-icons/react";
import Card from "@/components/Card";
import BulkUploadPanel from "@/components/tracker/BulkUploadPanel";
import { SelectField } from "@/pages/PhysicalTracker";
import { api, BACKEND_URL, formatApiError } from "@/lib/api";
import { TID } from "@/lib/testIds";
import { toast } from "sonner";

const TRACKERS = [
  {
    id: "physical",
    label: "Physical Tracker",
    description: "Achieved / Target by High Court, component and indicator. Digitization pages must be in Crore Pages.",
    templateUrl: `${BACKEND_URL}/api/physical/bulk-template`,
    guidePath: "/physical",
    headers: "High Court · Component · Sub-Component · Type of Storage · District · Target · Achieved · Remarks",
    queryKeys: [["physical"], ["physical-hc-period"]],
  },
  {
    id: "financial",
    label: "Financial Tracker",
    description: "Fund Released / Utilised in ₹ crore by High Court and component.",
    templateUrl: `${BACKEND_URL}/api/financial/bulk-template`,
    guidePath: "/financial",
    headers: "High Court · Component · District · Fund Released · Fund Utilized · Remarks",
    queryKeys: [["financial"], ["financial-hc-period"]],
  },
  {
    id: "outcome",
    label: "Outcome Tracker",
    description: "KPI baseline and period values by subject, granularity and High Court / district.",
    templateUrl: `${BACKEND_URL}/api/outcome/bulk-template`,
    guidePath: "/outcome",
    headers: "High Court · Subject · KPI ID · Granularity · Value · Baseline · District · Remarks",
    queryKeys: [["outcome"], ["outcome-hc-period"]],
  },
];

export default function AdminBulkUpload() {
  const qc = useQueryClient();
  const [trackerId, setTrackerId] = useState("physical");
  const [period, setPeriod] = useState("");
  const [flushScope, setFlushScope] = useState("period"); // period | all
  const [flushConfirm, setFlushConfirm] = useState("");
  const [flushBusy, setFlushBusy] = useState(false);
  const [showFlush, setShowFlush] = useState(false);

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

  function invalidateTracker() {
    tracker.queryKeys.forEach((key) => {
      qc.invalidateQueries({ queryKey: key });
    });
  }

  async function handleFlush() {
    if (flushConfirm.trim().toLowerCase() !== trackerId) {
      toast.error(`Type "${trackerId}" to confirm flush`);
      return;
    }
    if (flushScope === "period" && !period) {
      toast.error("Select a reporting period first");
      return;
    }
    setFlushBusy(true);
    try {
      const r = await api.post("/bulk/flush", {
        tracker: trackerId,
        scope: flushScope,
        reporting_period: flushScope === "period" ? period : null,
        confirm: trackerId,
      });
      const d = r.data;
      toast.success(
        flushScope === "period"
          ? `Flushed ${d.deleted} ${tracker.label} row(s) for ${period}`
          : `Flushed all ${tracker.label} data (${d.deleted} row(s))`,
      );
      setFlushConfirm("");
      setShowFlush(false);
      invalidateTracker();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setFlushBusy(false);
    }
  }

  return (
    <div className="space-y-6" data-testid={TID.bulkUploadPage}>
      <div>
        <h2 className="font-display text-2xl text-slate-900 tracking-tight">Bulk Data Upload</h2>
        <p className="text-sm text-slate-500 mt-1 max-w-3xl">
          Admin-only Excel import for Physical, Financial and Outcome trackers. Preview validates rows (dry-run),
          then confirm to commit. Same channel as tracker-page bulk upload and CLI ETL scripts.
        </p>
      </div>

      <Card title="Upload settings" subtitle="Choose tracker and reporting month before selecting a file">
        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <label className="block">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">Tracker</span>
            <div className="mt-1 flex flex-wrap gap-2" role="tablist" aria-label="Tracker type">
              {TRACKERS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={trackerId === t.id}
                  data-testid={`bulk-tab-${t.id}`}
                  onClick={() => {
                    setTrackerId(t.id);
                    setFlushConfirm("");
                    setShowFlush(false);
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
          </label>
          <SelectField
            testid={TID.periodSelect}
            label="Reporting month"
            value={period}
            onChange={setPeriod}
            options={periodOptions}
          />
          <div className="flex items-end">
            <Link
              to={tracker.guidePath}
              className="text-xs text-[#003B73] hover:underline uppercase tracking-wider"
            >
              Open {tracker.label} →
            </Link>
          </div>
        </div>
      </Card>

      <Card
        title={`${tracker.label} · Excel bulk upload`}
        subtitle={`Period ${period || "—"} · Template columns: ${tracker.headers}`}
      >
        <div className="border-b border-slate-100 px-4 py-3 bg-slate-50 text-xs text-slate-600 flex gap-2 items-start">
          <Info size={16} className="shrink-0 mt-0.5 text-[#003B73]" />
          <div>
            <p>{tracker.description}</p>
            <p className="mt-1 text-slate-500">
              Download the template, fill rows, then Upload &amp; preview. Confirm only after the dry-run looks correct.
              Blank fund/achieved cells preserve existing values where the API supports partial updates.
            </p>
          </div>
        </div>
        <BulkUploadPanel
          tracker={tracker.id}
          period={period}
          canEdit={Boolean(period)}
          templateUrl={tracker.templateUrl}
          onComplete={invalidateTracker}
        />
      </Card>

      <Card
        title="Flush tracker data"
        subtitle="Permanently delete entries for the selected tracker — use before a clean re-import"
      >
        <div className="p-4 space-y-3" data-testid={TID.bulkFlushPanel}>
          {!showFlush ? (
            <button
              type="button"
              data-testid={TID.bulkFlushOpenBtn}
              onClick={() => setShowFlush(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-sm text-xs uppercase tracking-wider border border-red-300 text-red-700 bg-white hover:bg-red-50"
            >
              <Trash size={14} /> Flush all data…
            </button>
          ) : (
            <div className="border border-red-200 bg-red-50/60 rounded-sm p-3 space-y-3">
              <p className="text-xs text-red-800">
                This cannot be undone. Choose whether to delete only the selected reporting month or
                every period for <strong>{tracker.label}</strong>.
              </p>
              <div className="flex flex-wrap gap-3 text-xs">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="flush-scope"
                    checked={flushScope === "period"}
                    onChange={() => setFlushScope("period")}
                    data-testid="bulk-flush-scope-period"
                  />
                  This period only ({period || "—"})
                </label>
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="flush-scope"
                    checked={flushScope === "all"}
                    onChange={() => setFlushScope("all")}
                    data-testid="bulk-flush-scope-all"
                  />
                  All periods (entire tracker)
                </label>
              </div>
              <label className="block text-xs">
                <span className="text-slate-700">
                  Type <code className="bg-white px-1 border border-red-200">{trackerId}</code> to confirm
                </span>
                <input
                  type="text"
                  value={flushConfirm}
                  onChange={(e) => setFlushConfirm(e.target.value)}
                  data-testid={TID.bulkFlushConfirmInput}
                  className="mt-1 w-full max-w-xs border border-red-300 rounded-sm px-2 py-1.5 text-sm"
                  placeholder={trackerId}
                  autoComplete="off"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={flushBusy || flushConfirm.trim().toLowerCase() !== trackerId}
                  onClick={handleFlush}
                  data-testid={TID.bulkFlushCommitBtn}
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-sm text-xs uppercase tracking-wider ${
                    flushBusy || flushConfirm.trim().toLowerCase() !== trackerId
                      ? "bg-slate-300 text-slate-500 cursor-not-allowed"
                      : "bg-red-700 hover:bg-red-800 text-white"
                  }`}
                >
                  <Trash size={14} />
                  {flushBusy
                    ? "Flushing…"
                    : flushScope === "period"
                      ? `Flush ${tracker.label} · ${period}`
                      : `Flush all ${tracker.label} data`}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowFlush(false);
                    setFlushConfirm("");
                  }}
                  className="px-4 py-2 rounded-sm text-xs uppercase tracking-wider border border-slate-300 bg-white hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </Card>

      <Card title="ETL & CLI (optional)">
        <div className="p-4 text-xs text-slate-600 space-y-2">
          <p className="flex items-center gap-2 font-medium text-slate-800">
            <FileXls size={14} /> Reusable pipeline for wide DoJ Excels
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              Financial released / utilised: <code className="bg-slate-100 px-1">backend/scripts/import_financial_excel.py</code>
              {" "}(<code className="bg-slate-100 px-1">--mode released|utilised --load-api</code>)
            </li>
            <li>
              Physical achieved till Sep 2025: <code className="bg-slate-100 px-1">backend/scripts/import_physical_excel.py</code>
            </li>
            <li>
              Docs: <code className="bg-slate-100 px-1">docs/FINANCIAL_ETL.md</code>,{" "}
              <code className="bg-slate-100 px-1">docs/PHYSICAL_ETL.md</code>
            </li>
          </ul>
          <p className="text-slate-500 pt-1 flex items-center gap-2">
            <UploadSimple size={14} />
            This page uses the same Admin bulk API endpoints as those scripts.
          </p>
        </div>
      </Card>
    </div>
  );
}
