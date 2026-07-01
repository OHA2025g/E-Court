import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, fmtNum, fmtPct, formatApiError, BACKEND_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import BulkUploadPanel from "@/components/tracker/BulkUploadPanel";
import EditableTrackerTable from "@/components/tracker/EditableTrackerTable";
import { useTrackerDraft } from "@/lib/useTrackerDraft";
import { TID } from "@/lib/testIds";
import { toast } from "sonner";
import { FloppyDisk, FileXls, FilePdf, ListPlus } from "@phosphor-icons/react";
import { SelectField, NumberField, TextField } from "@/pages/PhysicalTracker";
import { TableSkeleton } from "@/components/Skeletons";
import { useMinLoading } from "@/lib/useMinLoading";
import PeriodLockBanner from "@/components/PeriodLockBanner";
import { unwrapTrackerResponse } from "@/lib/trackerApi";
import TrackerPagination from "@/components/TrackerPagination";
import ScrollRegion from "@/components/ui/ScrollRegion";
import EntryCommentsPanel, { CommentsButton } from "@/components/EntryCommentsPanel";
import { useTrackerLabels } from "@/lib/useTrackerLabels";

const PAGE_SIZE = 50;

const GRANULARITIES = ["State", "District", "National"];
const OUTCOME_TYPES = ["Absolute", "Relative"];
const VALUE_TYPES = ["Count", "Amount", "Percentage", "Ratio"];

export default function OutcomeTracker() {
  const { user } = useAuth();
  const labels = useTrackerLabels();
  const qc = useQueryClient();
  const [period, setPeriod] = useState("");
  const [hc, setHc] = useState(user?.role === "CPC" ? user.high_court : "");
  const [subject, setSubject] = useState("");
  const [component, setComponent] = useState("");
  const [subComponent, setSubComponent] = useState("");
  const [kpiId, setKpiId] = useState("");
  const [granularity, setGranularity] = useState("District");
  const [district, setDistrict] = useState("");
  const [outcomeType, setOutcomeType] = useState("Absolute");
  const [valueType, setValueType] = useState("Count");
  const [baseline, setBaseline] = useState("");
  const [value, setValue] = useState("");
  const [remarks, setRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [initBusy, setInitBusy] = useState(false);
  const [initPromptDismissed, setInitPromptDismissed] = useState(false);
  const [page, setPage] = useState(1);
  const [commentsEntry, setCommentsEntry] = useState(null);

  const hcs = useQuery({ queryKey: ["hcs"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const allKpis = useQuery({
    queryKey: ["kpis", "all"],
    queryFn: () => api.get("/master/kpis").then(r => r.data),
  });
  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get("/master/periods").then(r => r.data) });
  useEffect(() => {
    if (!period && periods.data?.length) {
      const baseline = periods.data.find((p) => p.is_baseline);
      setPeriod(baseline?.period || periods.data[0].period);
    }
  }, [period, periods.data]);
  const districts = useQuery({
    queryKey: ["districts", hc], enabled: !!hc && granularity === "District",
    queryFn: () => api.get("/master/districts", { params: { high_court: hc } }).then(r => r.data),
  });
  const listParams = useMemo(() => ({
    high_court: hc || undefined,
    subject: subject || undefined,
    reporting_period: period || undefined,
    page,
    page_size: PAGE_SIZE,
  }), [hc, subject, period, page]);
  const list = useQuery({
    queryKey: ["outcome", listParams],
    queryFn: () => api.get("/outcome", { params: listParams }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const listItems = list.data?.items || [];
  const listTotal = list.data?.total ?? listItems.length;
  const anomalies = useQuery({
    queryKey: ["anomalies", "outcome", period],
    enabled: !!period,
    queryFn: () => api.get("/anomalies", { params: { reporting_period: period, tracker: "outcome" } }).then((r) => r.data),
  });
  const anomalyKeys = useMemo(() => {
    const s = new Set();
    (anomalies.data?.flags || []).forEach((f) => {
      s.add(`${f.high_court}|${f.subject}|${f.kpi_id}`);
    });
    return s;
  }, [anomalies.data]);

  useEffect(() => { setPage(1); }, [hc, subject, period]);
  const initPromptKey = hc && period ? `pmis-outcome-init-prompt:${hc}:${period}` : null;
  const hcPeriodRows = useQuery({
    queryKey: ["outcome", "hc-period", hc, period],
    enabled: !!hc && !!period,
    queryFn: () => api.get("/outcome", { params: { high_court: hc, reporting_period: period, page_size: 500 } }).then((r) => unwrapTrackerResponse(r.data)),
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

  const kpiMeta = useMemo(
    () => (allKpis.data || []).find(k => k.kpi_id === kpiId && (
      !subject || k.subject === subject ||
      (k.sub_component || k.subject) === subComponent
    )),
    [allKpis.data, kpiId, subject, subComponent],
  );

  const componentOptions = useMemo(() => {
    const names = new Set();
    (allKpis.data || []).forEach((k) => {
      if (k.component) names.add(k.component);
    });
    return [...names].sort();
  }, [allKpis.data]);

  const subComponentOptions = useMemo(() => {
    if (!component) return [];
    const names = new Set();
    (allKpis.data || [])
      .filter((k) => k.component === component)
      .forEach((k) => names.add(k.sub_component || k.subject));
    return [...names].sort();
  }, [allKpis.data, component]);

  const kpiOptions = useMemo(() => {
    return (allKpis.data || []).filter((k) => {
      if (component && k.component !== component) return false;
      if (subComponent && (k.sub_component || k.subject) !== subComponent) return false;
      return true;
    });
  }, [allKpis.data, component, subComponent]);

  useEffect(() => {
    if (kpiMeta?.granularity) setGranularity(kpiMeta.granularity);
    if (kpiMeta) {
      setComponent(kpiMeta.component || "");
      setSubComponent(kpiMeta.sub_component || kpiMeta.subject || "");
      setSubject(kpiMeta.subject || subComponent);
    }
  }, [kpiMeta, subComponent]);

  useEffect(() => {
    if (granularity !== "District") setDistrict("");
  }, [granularity]);

  useEffect(() => {
    if (!entryLookupItems.length || !subject || !kpiId || !period) return;
    const d = granularity === "District" ? (district || null) : null;
    const found = entryLookupItems.find(r =>
      r.subject === subject && r.kpi_id === kpiId && r.reporting_period === period &&
      r.granularity === granularity && (r.high_court || "") === (hc || "") &&
      (r.district || null) === d
    );
    if (found) {
      setComponent(found.component || kpiMeta?.component || "");
      setSubComponent(found.sub_component || found.subject || kpiMeta?.sub_component || "");
      setSubject(found.subject || subComponent);
      setBaseline(found.baseline ?? "");
      setValue(found.value ?? "");
      setRemarks(found.remarks ?? "");
      setOutcomeType(found.outcome_type || outcomeType);
      setValueType(found.value_type || valueType);
      if (found.district) setDistrict(found.district);
    } else if (user?.role !== "Admin") {
      setBaseline(""); setValue(""); setRemarks("");
    }
  }, [entryLookupItems, subject, kpiId, period, hc, granularity, district, outcomeType, valueType, kpiMeta, subComponent, user?.role]);

  const districtRequired = granularity === "District";

  const setDraftFields = useCallback((f) => {
    if (f.subject != null) setSubject(f.subject);
    if (f.component != null) setComponent(f.component);
    if (f.subComponent != null) setSubComponent(f.subComponent);
    if (f.kpiId != null) setKpiId(f.kpiId);
    if (f.granularity != null) setGranularity(f.granularity);
    if (f.district != null) setDistrict(f.district);
    if (f.outcomeType != null) setOutcomeType(f.outcomeType);
    if (f.valueType != null) setValueType(f.valueType);
    if (f.baseline != null) setBaseline(f.baseline);
    if (f.value != null) setValue(f.value);
    if (f.remarks != null) setRemarks(f.remarks);
  }, []);
  const draftFields = useMemo(() => ({
    subject, component, subComponent, kpiId, granularity, district, outcomeType, valueType, baseline, value, remarks,
  }), [subject, component, subComponent, kpiId, granularity, district, outcomeType, valueType, baseline, value, remarks]);
  const { showBanner, clearDraft, dismissBanner } = useTrackerDraft({
    userId: user?.email || user?.id, tracker: "outcome", period, hc, fields: draftFields, setFields: setDraftFields,
  });

  const canAddEntry = user?.role === "Admin";
  const canEdit = user?.role !== "Viewer";
  const formMandatoryReady = Boolean(
    kpiId && period && subject &&
    (granularity !== "District" || (hc && district)),
  );
  const selectedEntryExists = useMemo(() => {
    if (!formMandatoryReady) return false;
    const d = granularity === "District" ? (district || null) : null;
    return entryLookupItems.some((r) =>
      r.subject === subject && r.kpi_id === kpiId && r.reporting_period === period &&
      r.granularity === granularity && (r.high_court || "") === (hc || "") &&
      (r.district || null) === d
    );
  }, [entryLookupItems, formMandatoryReady, subject, kpiId, period, hc, granularity, district]);
  const canSaveEntry = canEdit && (canAddEntry ? formMandatoryReady : formMandatoryReady && selectedEntryExists);
  const showInitPrompt = canAddEntry && hc && period && !initPromptDismissed &&
    hcPeriodCount === 0 && !hcPeriodRows.isLoading;

  function dismissInitPrompt() {
    if (initPromptKey) sessionStorage.setItem(initPromptKey, "1");
    setInitPromptDismissed(true);
  }

  async function initPeriod() {
    if (!hc || !period) { toast.error(labels.selectHcPeriod); return; }
    setInitBusy(true);
    try {
      const r = await api.post("/outcome/init-period", {
        high_court: hc, reporting_period: period,
        subject: subject || undefined,
      });
      toast.success(labels.initSuccess(r.data.created, r.data.skipped));
      qc.invalidateQueries({ queryKey: ["outcome"] });
      dismissInitPrompt();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setInitBusy(false);
    }
  }

  async function save(payload) {
    const body = payload || {
      high_court: hc || null,
      component: payload?.component ?? (component || kpiMeta?.component || null),
      sub_component: payload?.sub_component ?? (subComponent || kpiMeta?.sub_component || subject || null),
      subject,
      kpi_id: kpiId,
      kpi: kpiMeta?.kpi || payload?.kpi || null,
      description: kpiMeta?.description || payload?.description || null,
      granularity: payload?.granularity || granularity,
      district: payload?.district ?? (granularity === "District" ? (district || null) : null),
      periodicity: kpiMeta?.periodicity || payload?.periodicity || null,
      outcome_type: payload?.outcome_type || outcomeType,
      value_type: payload?.value_type || valueType,
      baseline: (payload?.baseline ?? (baseline === "" ? null : Number(baseline))),
      value: (payload?.value ?? (value === "" ? null : Number(value))),
      reporting_period: payload?.reporting_period || period,
      remarks: payload?.remarks ?? (remarks || null),
    };
    if (!body.subject || !body.kpi_id || !body.reporting_period) {
      toast.error(labels.subjectKpiRequired);
      return;
    }
    if (body.granularity === "District" && !body.high_court) {
      toast.error(labels.hcRequiredDistrict);
      return;
    }
    if (body.granularity === "District" && !body.district) {
      toast.error(labels.districtRequired);
      return;
    }
    await api.post("/outcome", body);
    toast.success(labels.saved);
    clearDraft();
    qc.invalidateQueries({ queryKey: ["outcome"] });
  }

  async function saveForm() {
    setSaving(true);
    try {
      await save();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setSaving(false); }
  }

  async function saveRow(row) {
    try {
      await save({
        high_court: row.high_court,
        component: row.component,
        sub_component: row.sub_component,
        subject: row.subject,
        kpi_id: row.kpi_id,
        kpi: row.kpi,
        description: row.description,
        granularity: row.granularity,
        district: row.district || null,
        periodicity: row.periodicity,
        outcome_type: row.outcome_type,
        value_type: row.value_type,
        baseline: row.baseline,
        value: row.value,
        reporting_period: row.reporting_period,
        remarks: row.remarks,
      });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  }

  function exportUrl(fmt) {
    const params = new URLSearchParams();
    if (hc) params.set("high_court", hc);
    if (subject) params.set("subject", subject);
    if (period) params.set("reporting_period", period);
    params.set("format", fmt);
    return `${BACKEND_URL}/api/export/outcome?${params.toString()}`;
  }

  const tableColumns = useMemo(() => [
    { key: "high_court", label: labels.highCourt },
    { key: "component", label: labels.component, render: (r) => {
      const meta = (allKpis.data || []).find((k) => k.subject === r.subject && k.kpi_id === r.kpi_id);
      return r.component || meta?.component || "—";
    } },
    { key: "sub_component", label: labels.subComponent, render: (r) => {
      const meta = (allKpis.data || []).find((k) => k.subject === r.subject && k.kpi_id === r.kpi_id);
      const label = r.sub_component || r.subject || meta?.sub_component || meta?.subject || "—";
      return (
      <span className="inline-flex items-center gap-1">
        {label}
        {anomalyKeys.has(`${r.high_court}|${r.subject}|${r.kpi_id}`) && (
          <span className="text-[9px] uppercase tracking-wider bg-violet-100 text-violet-800 px-1 rounded-sm" title={labels.anomalyBadge}>3σ</span>
        )}
      </span>
    ); } },
    { key: "kpi", label: labels.kpi, render: (r) => {
      const meta = (allKpis.data || []).find((k) => k.subject === r.subject && k.kpi_id === r.kpi_id);
      return r.kpi || meta?.kpi || "—";
    } },
    { key: "granularity", label: labels.granularity },
    { key: "district", label: labels.district, render: r => r.district || (r.granularity === "District" ? "—" : "") },
    { key: "outcome_type", label: labels.type },
    { key: "periodicity", label: labels.periodicity },
    { key: "baseline", label: labels.baseline, align: "right", editable: canEdit, field: "baseline", inputType: "number", render: r => fmtNum(r.baseline) },
    { key: "value", label: labels.value, align: "right", editable: canEdit, field: "value", inputType: "number", render: r => fmtNum(r.value) },
    { key: "computed_percent", label: labels.computedPercent, align: "right", render: r => fmtPct(r.computed_percent) },
    { key: "reporting_period", label: labels.period },
    { key: "remarks", label: labels.remarks, editable: canEdit, field: "remarks" },
    {
      key: "comments",
      label: "",
      render: (r) => <CommentsButton onClick={() => setCommentsEntry(r)} />,
    },
  ], [canEdit, anomalyKeys, labels, allKpis.data]);

  return (
    <div className="space-y-6">
      <PeriodLockBanner highCourt={hc} reportingPeriod={period} />
      {showBanner && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 text-sm px-4 py-2 rounded-sm flex flex-wrap items-center justify-between gap-2">
          <span>{labels.draftRestored}</span>
          <span className="flex gap-2">
            <button type="button" onClick={dismissBanner} className="text-xs uppercase tracking-wider underline">{labels.keep}</button>
            <button type="button" onClick={() => { clearDraft(); setBaseline(""); setValue(""); setRemarks(""); }} className="text-xs uppercase tracking-wider underline">{labels.discard}</button>
          </span>
        </div>
      )}
      {showInitPrompt && (
        <div className="bg-sky-50 border border-sky-200 text-sky-900 text-sm px-4 py-3 rounded-sm flex flex-wrap items-center justify-between gap-3">
          <span>{labels.outcomeInitPrompt(hc, period)}</span>
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
          title={labels.outcomeEntry}
          subtitle={canAddEntry ? labels.outcomeEntrySubtitle : `${labels.outcomeEntrySubtitle} ${labels.entryUpdateOnlyHint}`}
          className="lg:col-span-2"
        >
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <SelectField testid={TID.hcSelect} label={labels.highCourt} value={hc} onChange={setHc} options={(hcs.data || []).map(h => h.name)} disabled={user?.role === "CPC"} />
            <SelectField testid={TID.periodSelect} label={labels.reportingMonth} value={period} onChange={setPeriod} options={(periods.data || []).map(p => ({ label: p.label, value: p.period }))} />
            <SelectField
              label={labels.component}
              value={component}
              onChange={(v) => { setComponent(v); setSubComponent(""); setSubject(""); setKpiId(""); }}
              options={componentOptions}
            />
            <SelectField
              label={labels.subComponent}
              value={subComponent}
              onChange={(v) => { setSubComponent(v); setSubject(v); setKpiId(""); }}
              options={subComponentOptions}
              disabled={!component}
            />
            <SelectField
              testid={TID.kpiSelect}
              label={labels.kpi}
              value={kpiId}
              onChange={setKpiId}
              options={kpiOptions.map(k => ({ label: k.kpi || k.kpi_id, value: k.kpi_id }))}
              disabled={!subComponent}
            />
            <SelectField label={labels.granularity} value={granularity} onChange={setGranularity} options={GRANULARITIES} />
            {districtRequired && (
              <>
                <SelectField label={labels.district} value={district} onChange={setDistrict}
                  options={(districts.data || []).map(d => ({ label: d.name, value: d.name }))}
                  disabled={!hc || !canEdit} />
                {!hc && (
                  <div className="sm:col-span-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 px-3 py-2 rounded-sm">
                    Select a High Court before choosing a district.
                  </div>
                )}
              </>
            )}
            <SelectField label="Outcome Type" value={outcomeType} onChange={setOutcomeType} options={OUTCOME_TYPES} />
            <SelectField label="Value Type" value={valueType} onChange={setValueType} options={VALUE_TYPES} />
            <NumberField testid={TID.baselineInput} label="Baseline (for Relative KPIs)" value={baseline} onChange={setBaseline} disabled={!canEdit || outcomeType !== "Relative"} />
            <NumberField testid={TID.valueInput} label="Value" value={value} onChange={setValue} disabled={!canEdit} />
            <div className="sm:col-span-2"><TextField testid={TID.remarksInput} label="Remarks" value={remarks} onChange={setRemarks} disabled={!canEdit} /></div>
            <div className="sm:col-span-2 mt-2 flex flex-wrap items-center gap-3">
              <button data-testid={TID.saveBtn} disabled={!canSaveEntry || saving} onClick={saveForm}
                className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm font-medium uppercase tracking-wider inline-flex items-center gap-2">
                <FloppyDisk size={16} /> {saving ? labels.saving : labels.saveEntry}
              </button>
              {canAddEntry && (
                <button type="button" disabled={initBusy || !hc || !period} onClick={initPeriod}
                  className="border border-[#003B73] text-[#003B73] hover:bg-slate-50 disabled:opacity-50 px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
                  <ListPlus size={16} /> {initBusy ? labels.initializing : labels.initKpiRows}
                </button>
              )}
            </div>
          </div>
        </Card>
        <Card title={labels.exportBulk}>
          <div className="p-4 space-y-3 border-b border-slate-100">
            <a data-testid={TID.exportXlsx} href={exportUrl("xlsx")} target="_blank" rel="noreferrer"
              className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
              <FileXls size={16} /> {labels.exportExcel}
            </a>
            <a data-testid={TID.exportPdf} href={exportUrl("pdf")} target="_blank" rel="noreferrer"
              className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
              <FilePdf size={16} /> {labels.exportPdf}
            </a>
            <p className="text-xs text-slate-500">{listTotal} outcome rows in current selection.</p>
          </div>
          <BulkUploadPanel
            tracker="outcome"
            period={period}
            canEdit={canAddEntry}
            templateUrl={`${BACKEND_URL}/api/outcome/bulk-template`}
            onComplete={() => qc.invalidateQueries({ queryKey: ["outcome"] })}
          />
        </Card>
      </div>

      <Card title={labels.outcomeEntries} subtitle={labels.entriesSubtitle(listTotal)} testId={TID.outcomeTable}>
        {useMinLoading(list.isLoading) ? (
          <TableSkeleton rows={8} cols={12} />
        ) : (
          <>
          <ScrollRegion className="overflow-x-auto max-h-[560px]" label={labels.outcomeEntries}>
            <EditableTrackerTable
              columns={tableColumns}
              rows={listItems}
              rowKey={(r) => r.id}
              canEdit={canEdit}
              onSaveRow={saveRow}
              onRowClick={(r) => {
                const meta = (allKpis.data || []).find((k) => k.subject === r.subject && k.kpi_id === r.kpi_id);
                setHc(r.high_court || "");
                setComponent(r.component || meta?.component || "");
                setSubComponent(r.sub_component || r.subject || meta?.sub_component || meta?.subject || "");
                setSubject(r.subject || meta?.subject || "");
                setKpiId(r.kpi_id);
                setPeriod(r.reporting_period);
                setGranularity(r.granularity);
                setDistrict(r.district || "");
                setOutcomeType(r.outcome_type);
                setValueType(r.value_type);
                setBaseline(r.baseline ?? "");
                setValue(r.value ?? "");
                setRemarks(r.remarks ?? "");
              }}
            />
            {!list.isLoading && listItems.length === 0 && (
              <div className="text-center text-slate-400 py-12">No outcome data.</div>
            )}
          </ScrollRegion>
          <TrackerPagination page={page} pageSize={PAGE_SIZE} total={listTotal} onPageChange={setPage} />
          </>
        )}
      </Card>
      <EntryCommentsPanel
        tracker="outcome"
        entryId={commentsEntry?.id}
        open={!!commentsEntry}
        onOpenChange={(open) => { if (!open) setCommentsEntry(null); }}
        entryLabel={commentsEntry ? `${commentsEntry.subject} · ${commentsEntry.kpi_id}` : ""}
      />
    </div>
  );
}
