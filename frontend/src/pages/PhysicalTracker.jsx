import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, fmtNum, fmtPct, formatApiError, BACKEND_URL } from "@/lib/api";
import { useTrackerLabels } from "@/lib/useTrackerLabels";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import RagBadge from "@/components/RagBadge";
import BulkUploadPanel from "@/components/tracker/BulkUploadPanel";
import EditableTrackerTable from "@/components/tracker/EditableTrackerTable";
import { useTrackerDraft } from "@/lib/useTrackerDraft";
import { TID } from "@/lib/testIds";
import { toast } from "sonner";
import { FloppyDisk, FileXls, FilePdf, ListPlus } from "@phosphor-icons/react";
import { TableSkeleton } from "@/components/Skeletons";
import { useMinLoading } from "@/lib/useMinLoading";
import PeriodLockBanner from "@/components/PeriodLockBanner";
import ScrollRegion from "@/components/ui/ScrollRegion";
import OnboardingTour from "@/components/OnboardingTour";
import EntryCommentsPanel, { CommentsButton } from "@/components/EntryCommentsPanel";
import { unwrapTrackerResponse } from "@/lib/trackerApi";
import TrackerPagination from "@/components/TrackerPagination";

const PAGE_SIZE = 50;

export default function PhysicalTracker() {
  const { user } = useAuth();
  const labels = useTrackerLabels();
  const qc = useQueryClient();
  const [period, setPeriod] = useState("");
  const [hc, setHc] = useState(user?.role === "CPC" ? user.high_court : "");
  const [district, setDistrict] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [component, setComponent] = useState("");
  const [indicator, setIndicator] = useState("");
  const [target, setTarget] = useState("");
  const [achieved, setAchieved] = useState("");
  const [remarks, setRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [initBusy, setInitBusy] = useState(false);
  const [initPromptDismissed, setInitPromptDismissed] = useState(false);
  const [commentsEntry, setCommentsEntry] = useState(null);
  const [page, setPage] = useState(1);

  const hcs = useQuery({ queryKey: ["hcs"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const comps = useQuery({ queryKey: ["comps"], queryFn: () => api.get("/master/components").then(r => r.data) });
  const inds = useQuery({ queryKey: ["inds", component], enabled: !!component, queryFn: () => api.get("/master/indicators", { params: { component } }).then(r => r.data) });
  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get("/master/periods").then(r => r.data) });
  const districts = useQuery({
    queryKey: ["districts", hc], enabled: !!hc,
    queryFn: () => api.get("/master/districts", { params: { high_court: hc } }).then(r => r.data),
  });
  const listParams = useMemo(() => {
    const p = {
      high_court: hc || undefined,
      component: component || undefined,
      reporting_period: period || undefined,
      page,
      page_size: PAGE_SIZE,
    };
    if (districtFilter === "__hc__") p.district = "__hc__";
    else if (districtFilter) p.district = districtFilter;
    return p;
  }, [hc, component, period, districtFilter, page]);
  const list = useQuery({
    queryKey: ["physical", listParams],
    queryFn: () => api.get("/physical", { params: listParams }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const listItems = list.data?.items || [];
  const listTotal = list.data?.total ?? listItems.length;
  const anomalies = useQuery({
    queryKey: ["anomalies", period],
    enabled: !!period,
    queryFn: () => api.get("/anomalies", { params: { reporting_period: period } }).then((r) => r.data),
  });
  const anomalyKeys = useMemo(() => {
    const s = new Set();
    (anomalies.data?.flags || []).forEach((f) => {
      s.add(`${f.high_court}|${f.component}|${f.indicator}`);
    });
    return s;
  }, [anomalies.data]);

  useEffect(() => { setPage(1); }, [hc, component, period, districtFilter]);
  const initPromptKey = hc && period ? `pmis-init-prompt:${hc}:${period}` : null;
  const hcPeriodRows = useQuery({
    queryKey: ["physical", "hc-period", hc, period],
    enabled: !!hc && !!period,
    queryFn: () => api.get("/physical", { params: { high_court: hc, reporting_period: period, page_size: 500 } }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const hcPeriodCount = hcPeriodRows.data?.total ?? hcPeriodRows.data?.items?.length ?? 0;
  const entryLookupItems = useMemo(
    () => (hc && period ? hcPeriodRows.data?.items : null) || listItems,
    [hc, period, hcPeriodRows.data?.items, listItems],
  );

  useEffect(() => {
    if (!initPromptKey) return;
    setInitPromptDismissed(sessionStorage.getItem(initPromptKey) === "1");
  }, [initPromptKey]);

  const setDraftFields = useCallback((f) => {
    if (f.component != null) setComponent(f.component);
    if (f.indicator != null) setIndicator(f.indicator);
    if (f.district != null) setDistrict(f.district);
    if (f.target != null) setTarget(f.target);
    if (f.achieved != null) setAchieved(f.achieved);
    if (f.remarks != null) setRemarks(f.remarks);
  }, []);
  const draftFields = useMemo(() => ({ component, indicator, district, target, achieved, remarks }), [component, indicator, district, target, achieved, remarks]);
  const { showBanner, clearDraft, dismissBanner } = useTrackerDraft({
    userId: user?.email || user?.id, tracker: "physical", period, hc, fields: draftFields, setFields: setDraftFields,
  });

  useEffect(() => {
    if (!entryLookupItems.length || !hc || !component || !indicator || !period) return;
    const d = district || null;
    const found = entryLookupItems.find(r =>
      r.high_court === hc && r.component === component &&
      r.indicator === indicator && r.reporting_period === period &&
      (r.district || null) === d
    );
    if (found) {
      setTarget(found.target ?? "");
      setAchieved(found.achieved ?? "");
      setRemarks(found.remarks ?? "");
    } else if (user?.role !== "Admin") {
      setTarget(""); setAchieved(""); setRemarks("");
    }
  }, [entryLookupItems, hc, component, indicator, period, district, user?.role]);

  const canAddEntry = user?.role === "Admin";
  const canEditTarget = user?.role === "Admin";
  const canEdit = user?.role !== "Viewer";
  const formMandatoryReady = Boolean(hc && component && indicator && period);
  const selectedEntryExists = useMemo(() => {
    if (!formMandatoryReady) return false;
    const d = district || null;
    return entryLookupItems.some((r) =>
      r.high_court === hc && r.component === component && r.indicator === indicator &&
      r.reporting_period === period && (r.district || null) === d
    );
  }, [entryLookupItems, formMandatoryReady, hc, component, indicator, period, district]);
  const canSaveEntry = canEdit && (canAddEntry ? formMandatoryReady : formMandatoryReady && selectedEntryExists);
  const showInitPrompt = canAddEntry && hc && period && !initPromptDismissed &&
    hcPeriodCount === 0 && !hcPeriodRows.isLoading;

  function dismissInitPrompt() {
    if (initPromptKey) sessionStorage.setItem(initPromptKey, "1");
    setInitPromptDismissed(true);
  }

  async function save(payload) {
    const body = payload || {
      high_court: hc, component, indicator, reporting_period: period,
      district: district || null,
      target: target === "" ? null : Number(target),
      achieved: achieved === "" ? null : Number(achieved),
      remarks: remarks || null,
    };
    if (!body.high_court || !body.component || !body.indicator || !body.reporting_period) {
      toast.error(labels.selectRequired);
      return;
    }
    await api.post("/physical", body);
    toast.success(labels.saved);
    clearDraft();
    qc.invalidateQueries({ queryKey: ["physical"] });
    qc.invalidateQueries({ queryKey: ["dash-summary"] });
  }

  async function saveForm() {
    setSaving(true);
    try {
      await save();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  }

  async function saveRow(row) {
    try {
      await save({
        high_court: row.high_court,
        component: row.component,
        indicator: row.indicator,
        reporting_period: row.reporting_period,
        district: row.district || null,
        target: row.target,
        achieved: row.achieved,
        remarks: row.remarks,
      });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  }

  async function initPeriod() {
    if (!hc || !period) { toast.error(labels.selectHcPeriod); return; }
    setInitBusy(true);
    try {
      const r = await api.post("/physical/init-period", {
        high_court: hc, reporting_period: period,
        component: component || undefined,
      });
      toast.success(labels.initSuccess(r.data.created, r.data.skipped));
      qc.invalidateQueries({ queryKey: ["physical"] });
      qc.invalidateQueries({ queryKey: ["dash-summary"] });
      dismissInitPrompt();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setInitBusy(false);
    }
  }

  function exportUrl(fmt) {
    const params = new URLSearchParams();
    if (hc) params.set("high_court", hc);
    if (component) params.set("component", component);
    if (period) params.set("reporting_period", period);
    if (districtFilter === "__hc__") params.set("district", "__hc__");
    else if (districtFilter) params.set("district", districtFilter);
    params.set("format", fmt);
    return `${BACKEND_URL}/api/export/physical?${params.toString()}`;
  }

  const ragColor = (r) => r >= 80 ? "GREEN" : r >= 65 ? "AMBER" : r != null ? "RED" : "NA";

  const tableColumns = useMemo(() => [
    { key: "high_court", label: labels.highCourt },
    { key: "district", label: labels.district, render: r => r.district || labels.hcLevel },
    { key: "component", label: labels.component },
    { key: "indicator", label: labels.indicator, render: (r) => (
      <span className="inline-flex items-center gap-1">
        {r.indicator}
        {anomalyKeys.has(`${r.high_court}|${r.component}|${r.indicator}`) && (
          <span className="text-[9px] uppercase tracking-wider bg-violet-100 text-violet-800 px-1 rounded-sm" title={labels.anomalyBadge}>3σ</span>
        )}
      </span>
    ) },
    { key: "reporting_period", label: labels.period },
    { key: "target", label: labels.target, align: "right", editable: canEditTarget, field: "target", inputType: "number", render: r => fmtNum(r.target, { digits: 0 }) },
    { key: "achieved", label: labels.achieved, align: "right", editable: canEdit, field: "achieved", inputType: "number", render: r => fmtNum(r.achieved, { digits: 0 }) },
    { key: "percent", label: labels.percent, align: "right", render: r => fmtPct(r.percent) },
    { key: "rag", label: labels.rag, render: r => <RagBadge status={ragColor(r.percent)} /> },
    { key: "remarks", label: labels.remarks, editable: canEdit, field: "remarks" },
    {
      key: "comments",
      label: "",
      render: (r) => (
        <CommentsButton onClick={() => setCommentsEntry(r)} />
      ),
    },
  ], [canEdit, canEditTarget, anomalyKeys, labels]);

  return (
    <div className="space-y-6" data-tour="physical-tracker">
      <OnboardingTour />
      <PeriodLockBanner highCourt={hc} reportingPeriod={period} />
      {showBanner && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 text-sm px-4 py-2 rounded-sm flex flex-wrap items-center justify-between gap-2">
          <span>{labels.draftRestored}</span>
          <span className="flex gap-2">
            <button type="button" onClick={dismissBanner} className="text-xs uppercase tracking-wider underline">{labels.keep}</button>
            <button type="button" onClick={() => { clearDraft(); setTarget(""); setAchieved(""); setRemarks(""); }} className="text-xs uppercase tracking-wider underline">{labels.discard}</button>
          </span>
        </div>
      )}
      {showInitPrompt && (
        <div className="bg-sky-50 border border-sky-200 text-sky-900 text-sm px-4 py-3 rounded-sm flex flex-wrap items-center justify-between gap-3">
          <span>{labels.initPrompt(hc, period)}</span>
          <span className="flex gap-2">
            <button type="button" disabled={initBusy} onClick={initPeriod}
              className="bg-[#003B73] hover:bg-[#002B54] disabled:opacity-50 text-white px-3 py-1.5 rounded-sm text-xs uppercase tracking-wider inline-flex items-center gap-1">
              <ListPlus size={14} /> {labels.initialize}
            </button>
            <button type="button" onClick={dismissInitPrompt}
              className="px-3 py-1.5 border border-sky-300 rounded-sm text-xs uppercase tracking-wider">
              {labels.dismiss}
            </button>
          </span>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card
          title={labels.dataEntry}
          subtitle={canAddEntry ? labels.dataEntrySubtitle : `${labels.dataEntrySubtitle} ${labels.entryUpdateOnlyHint}`}
          className="lg:col-span-2"
        >
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <SelectField testid={TID.hcSelect} label={labels.highCourt} value={hc} onChange={setHc} options={(hcs.data || []).map(h => h.name)} disabled={user?.role === "CPC"} />
            <SelectField testid={TID.periodSelect} label={labels.reportingMonth} value={period} onChange={setPeriod} options={(periods.data || []).map(p => ({ label: p.label, value: p.period }))} />
            <SelectField testid="district-select" label={labels.districtOptional} value={district} onChange={setDistrict}
              options={[{ label: labels.hcLevel, value: "" }, ...(districts.data || []).map(d => ({ label: d.name, value: d.name }))]}
              disabled={!hc} />
            <SelectField label={labels.tableFilter} value={districtFilter} onChange={setDistrictFilter}
              options={[
                { label: labels.allDistricts, value: "" },
                { label: labels.hcLevelOnly, value: "__hc__" },
                ...(districts.data || []).map(d => ({ label: d.name, value: d.name })),
              ]}
              disabled={!hc} />
            <SelectField testid={TID.componentSelect} label={labels.component} value={component} onChange={(v) => { setComponent(v); setIndicator(""); }} options={(comps.data || []).map(c => c.name)} />
            <SelectField testid={TID.indicatorSelect} label={labels.indicator} value={indicator} onChange={setIndicator} options={(inds.data || []).map(i => i.indicator)} disabled={!component} />
            <NumberField testid={TID.targetInput} label={canEditTarget ? labels.target : labels.targetAdmin} value={target} onChange={setTarget} disabled={!canEditTarget} />
            <NumberField testid={TID.achievedInput} label={labels.achievedCumulative} value={achieved} onChange={setAchieved} disabled={!canEdit} />
            <div className="sm:col-span-2">
              <TextField testid={TID.remarksInput} label={labels.remarksOptional} value={remarks} onChange={setRemarks} disabled={!canEdit} />
            </div>
            <div className="sm:col-span-2 flex flex-wrap items-center gap-3 mt-2">
              <button data-testid={TID.saveBtn} disabled={!canSaveEntry || saving} onClick={saveForm}
                className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm font-medium uppercase tracking-wider inline-flex items-center gap-2">
                <FloppyDisk size={16} /> {saving ? labels.saving : labels.saveEntry}
              </button>
              {canAddEntry && (
                <button type="button" disabled={initBusy || !hc || !period} onClick={initPeriod}
                  className="border border-[#003B73] text-[#003B73] hover:bg-slate-50 disabled:opacity-50 px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
                  <ListPlus size={16} /> {initBusy ? labels.initializing : labels.initRows}
                </button>
              )}
            </div>
          </div>
        </Card>

        <Card title={labels.exportBulk} subtitle={labels.exportBulkSubtitle}>
          <div className="p-4 space-y-3 border-b border-slate-100">
            <a data-testid={TID.exportXlsx} href={exportUrl("xlsx")} target="_blank" rel="noreferrer"
              className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
              <FileXls size={16} /> {labels.exportExcel}
            </a>
            <a data-testid={TID.exportPdf} href={exportUrl("pdf")} target="_blank" rel="noreferrer"
              className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
              <FilePdf size={16} /> {labels.exportPdf}
            </a>
          </div>
          <BulkUploadPanel
            tracker="physical"
            period={period}
            canEdit={canAddEntry}
            templateUrl={`${BACKEND_URL}/api/physical/bulk-template`}
            onComplete={() => { qc.invalidateQueries({ queryKey: ["physical"] }); qc.invalidateQueries({ queryKey: ["dash-summary"] }); }}
          />
        </Card>
      </div>

      <Card title={labels.physicalEntries} subtitle={labels.entriesSubtitle(listTotal)} testId={TID.physicalTable}>
        {useMinLoading(list.isLoading) ? (
          <TableSkeleton rows={8} cols={10} />
        ) : (
          <>
          <ScrollRegion className="overflow-x-auto max-h-[560px]" label={labels.physicalEntries}>
            <EditableTrackerTable
              columns={tableColumns}
              rows={listItems}
              rowKey={(r) => r.id}
              canEdit={canEdit}
              onSaveRow={saveRow}
              onRowClick={(r) => {
                setHc(r.high_court);
                setComponent(r.component);
                setIndicator(r.indicator);
                setPeriod(r.reporting_period);
                setDistrict(r.district || "");
              }}
            />
            {!list.isLoading && listItems.length === 0 && (
              <div className="text-center text-slate-400 py-12">{labels.noEntries}</div>
            )}
          </ScrollRegion>
          <TrackerPagination page={page} pageSize={PAGE_SIZE} total={listTotal} onPageChange={setPage} />
          </>
        )}
      </Card>
      <EntryCommentsPanel
        tracker="physical"
        entryId={commentsEntry?.id}
        open={!!commentsEntry}
        onOpenChange={(open) => { if (!open) setCommentsEntry(null); }}
        entryLabel={commentsEntry ? `${commentsEntry.high_court} · ${commentsEntry.component} · ${commentsEntry.indicator}` : ""}
      />
    </div>
  );
}

export function SelectField({ label, value, onChange, options, disabled, testid }) {
  const { t } = useTranslation();
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{label}</span>
      <select
        data-testid={testid}
        disabled={disabled}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm focus:outline-none focus:border-[#003B73] focus:ring-1 focus:ring-[#003B73] disabled:bg-slate-100 disabled:text-slate-500"
      >
        <option value="">{t("common.select")}</option>
        {options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          const l = typeof o === "string" ? o : o.label;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
    </label>
  );
}

export function NumberField({ label, value, onChange, disabled, testid }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{label}</span>
      <input
        data-testid={testid}
        type="number"
        step="any"
        min="0"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm tabular-nums focus:outline-none focus:border-[#003B73] focus:ring-1 focus:ring-[#003B73] disabled:bg-slate-100 disabled:text-slate-500"
      />
    </label>
  );
}

export function TextField({ label, value, onChange, disabled, testid, type = "text" }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{label}</span>
      <input
        data-testid={testid}
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm focus:outline-none focus:border-[#003B73] focus:ring-1 focus:ring-[#003B73] disabled:bg-slate-100 disabled:text-slate-500"
      />
    </label>
  );
}
