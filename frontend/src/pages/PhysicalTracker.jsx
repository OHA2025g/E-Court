import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, fmtNum, fmtPct, formatApiError, BACKEND_URL, downloadApiFile } from "@/lib/api";
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

const PAGE_SIZE = 50;
const TABLE_FETCH_SIZE = 500;
const CLOUD_COMPUTING_COMPONENT = "Cloud Computing & Storage";
const ESEWA_COMPONENT = "e-Sewa Kendras";
const STORAGE_TYPE_OPTIONS = ["NFS Storage", "Block Storage"];
const DEFAULT_STORAGE_TYPE = "Block Storage";

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
  const [storageType, setStorageType] = useState(DEFAULT_STORAGE_TYPE);
  const [target, setTarget] = useState("");
  const [achieved, setAchieved] = useState("");
  const [targetDpr, setTargetDpr] = useState("");
  const [achievedEcommittee, setAchievedEcommittee] = useState("");
  const [targetCpc, setTargetCpc] = useState("");
  const [achievedCpc, setAchievedCpc] = useState("");
  const [remarks, setRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [initBusy, setInitBusy] = useState(false);
  const [initPromptDismissed, setInitPromptDismissed] = useState(false);
  const [commentsEntry, setCommentsEntry] = useState(null);
  const [tablePage, setTablePage] = useState(1);

  const isCloudComponent = component === CLOUD_COMPUTING_COMPONENT;
  const isEsewaComponent = component === ESEWA_COMPONENT;

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
      page: 1,
      page_size: TABLE_FETCH_SIZE,
    };
    if (districtFilter === "__hc__") p.district = "__hc__";
    else if (districtFilter) p.district = districtFilter;
    if (component === CLOUD_COMPUTING_COMPONENT && storageType) {
      p.storage_type = storageType;
    }
    return p;
  }, [hc, component, period, districtFilter, storageType]);
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

  useEffect(() => { setTablePage(1); }, [hc, component, period, districtFilter, storageType]);
  useEffect(() => {
    if (component !== CLOUD_COMPUTING_COMPONENT) {
      setStorageType(DEFAULT_STORAGE_TYPE);
    }
    if (component !== ESEWA_COMPONENT) {
      setTargetDpr("");
      setAchievedEcommittee("");
      setTargetCpc("");
      setAchievedCpc("");
    }
  }, [component]);
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
    if (f.storageType != null) setStorageType(f.storageType);
    if (f.target != null) setTarget(f.target);
    if (f.achieved != null) setAchieved(f.achieved);
    if (f.targetDpr != null) setTargetDpr(f.targetDpr);
    if (f.achievedEcommittee != null) setAchievedEcommittee(f.achievedEcommittee);
    if (f.targetCpc != null) setTargetCpc(f.targetCpc);
    if (f.achievedCpc != null) setAchievedCpc(f.achievedCpc);
    if (f.remarks != null) setRemarks(f.remarks);
  }, []);
  const draftFields = useMemo(
    () => ({
      component, indicator, district, storageType, target, achieved,
      targetDpr, achievedEcommittee, targetCpc, achievedCpc, remarks,
    }),
    [component, indicator, district, storageType, target, achieved, targetDpr, achievedEcommittee, targetCpc, achievedCpc, remarks],
  );
  const { showBanner, clearDraft, dismissBanner } = useTrackerDraft({
    userId: user?.email || user?.id, tracker: "physical", period, hc, fields: draftFields, setFields: setDraftFields,
  });

  useEffect(() => {
    if (!entryLookupItems.length || !hc || !component || !indicator || !period) return;
    const d = district || null;
    const st = isCloudComponent ? (storageType || DEFAULT_STORAGE_TYPE) : null;
    const found = entryLookupItems.find(r =>
      r.high_court === hc && r.component === component &&
      r.indicator === indicator && r.reporting_period === period &&
      (r.district || null) === d &&
      (isCloudComponent ? (r.storage_type || DEFAULT_STORAGE_TYPE) === st : true)
    );
    if (found) {
      setTarget(found.target ?? "");
      setAchieved(found.achieved ?? "");
      setRemarks(found.remarks ?? "");
      if (found.storage_type) setStorageType(found.storage_type);
      if (component === ESEWA_COMPONENT) {
        setTargetDpr(found.target_dpr ?? "");
        setAchievedEcommittee(found.achieved_ecommittee ?? "");
        setTargetCpc(found.target_cpc ?? "");
        setAchievedCpc(found.achieved_cpc ?? "");
      }
    } else if (user?.role !== "Admin") {
      setTarget(""); setAchieved(""); setRemarks("");
      setTargetDpr(""); setAchievedEcommittee(""); setTargetCpc(""); setAchievedCpc("");
    }
  }, [entryLookupItems, hc, component, indicator, period, district, storageType, isCloudComponent, user?.role]);

  const canAddEntry = user?.role === "Admin";
  const canEditTarget = user?.role === "Admin";
  const canEdit = user?.role !== "Viewer";
  const formMandatoryReady = Boolean(
    hc && component && indicator && period && (!isCloudComponent || storageType),
  );
  const selectedEntryExists = useMemo(() => {
    if (!formMandatoryReady) return false;
    const d = district || null;
    const st = isCloudComponent ? (storageType || DEFAULT_STORAGE_TYPE) : null;
    return entryLookupItems.some((r) =>
      r.high_court === hc && r.component === component && r.indicator === indicator &&
      r.reporting_period === period && (r.district || null) === d &&
      (isCloudComponent ? (r.storage_type || DEFAULT_STORAGE_TYPE) === st : true)
    );
  }, [entryLookupItems, formMandatoryReady, hc, component, indicator, period, district, storageType, isCloudComponent]);
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
      storage_type: isCloudComponent ? (storageType || DEFAULT_STORAGE_TYPE) : null,
      target: isEsewaComponent ? null : (target === "" ? null : Number(target)),
      achieved: isEsewaComponent ? null : (achieved === "" ? null : Number(achieved)),
      target_dpr: isEsewaComponent && targetDpr !== "" ? Number(targetDpr) : null,
      achieved_ecommittee: isEsewaComponent && achievedEcommittee !== "" ? Number(achievedEcommittee) : null,
      target_cpc: isEsewaComponent && targetCpc !== "" ? Number(targetCpc) : null,
      achieved_cpc: isEsewaComponent && achievedCpc !== "" ? Number(achievedCpc) : null,
      remarks: remarks || null,
    };
    if (!body.high_court || !body.component || !body.indicator || !body.reporting_period) {
      toast.error(labels.selectRequired);
      return;
    }
    if (body.component === CLOUD_COMPUTING_COMPONENT && !body.storage_type) {
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
      const isEsewa = row.component === ESEWA_COMPONENT;
      await save({
        high_court: row.high_court,
        component: row.component,
        indicator: row.indicator,
        reporting_period: row.reporting_period,
        district: row.district || null,
        storage_type: row.component === CLOUD_COMPUTING_COMPONENT
          ? (row.storage_type || DEFAULT_STORAGE_TYPE)
          : null,
        target: isEsewa ? null : row.target,
        achieved: isEsewa ? null : row.achieved,
        target_dpr: isEsewa ? (row.target_dpr ?? null) : null,
        achieved_ecommittee: isEsewa ? (row.achieved_ecommittee ?? null) : null,
        target_cpc: isEsewa ? (row.target_cpc ?? null) : null,
        achieved_cpc: isEsewa ? (row.achieved_cpc ?? null) : null,
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

  function exportParams() {
    const params = {};
    if (hc) params.high_court = hc;
    if (component) params.component = component;
    if (period) params.reporting_period = period;
    if (districtFilter === "__hc__") params.district = "__hc__";
    else if (districtFilter) params.district = districtFilter;
    if (component === CLOUD_COMPUTING_COMPONENT && storageType) {
      params.storage_type = storageType;
    }
    return params;
  }

  async function downloadExport(fileFormat) {
    try {
      await downloadApiFile("/export/physical", {
        params: { ...exportParams(), file_format: fileFormat },
        filename: fileFormat === "pdf" ? "physical_report.pdf" : "physical_report.xlsx",
      });
    } catch (e) {
      toast.error(e?.message || formatApiError(e?.response?.data?.detail));
    }
  }

  const ragColor = (r) => r >= 80 ? "GREEN" : r >= 65 ? "AMBER" : r != null ? "RED" : "NA";

  const tableColumns = useMemo(() => {
    const rowPercent = (r) => (
      isEsewaComponent
        ? r.percent_ecommittee
        : (r.component === ESEWA_COMPONENT ? r.percent_cpc : r.percent)
    );
    const cols = [
      { key: "high_court", label: labels.highCourt },
      {
        key: "district",
        label: labels.district,
        render: (r) => r.district || labels.hcLevel,
        sortValue: (r) => r.district || labels.hcLevel,
      },
      { key: "component", label: labels.component },
    ];
    if (isCloudComponent) {
      cols.push({
        key: "storage_type",
        label: labels.typeOfStorage,
        render: (r) => r.storage_type || "NA",
        sortValue: (r) => r.storage_type || "NA",
      });
    }
    cols.push(
      {
        key: "indicator",
        label: labels.indicator,
        sortValue: (r) => r.indicator || "",
        render: (r) => (
          <span className="inline-flex items-center gap-1">
            {r.indicator}
            {anomalyKeys.has(`${r.high_court}|${r.component}|${r.indicator}`) && (
              <span className="text-[9px] uppercase tracking-wider bg-violet-100 text-violet-800 px-1 rounded-sm" title={labels.anomalyBadge}>3σ</span>
            )}
          </span>
        ),
      },
      { key: "reporting_period", label: labels.period },
    );
    if (!isEsewaComponent) {
      cols.push(
        {
          key: "target",
          label: labels.target,
          align: "right",
          editable: canEditTarget,
          field: "target",
          inputType: "number",
          sortType: "number",
          getField: (r) => (r.component === ESEWA_COMPONENT ? "target_cpc" : "target"),
          editValue: (r) => (r.component === ESEWA_COMPONENT ? r.target_cpc : r.target),
          sortValue: (r) => (r.component === ESEWA_COMPONENT ? r.target_cpc : r.target),
          render: (r) => fmtNum(
            r.component === ESEWA_COMPONENT ? r.target_cpc : r.target,
            { digits: 0 },
          ),
        },
        {
          key: "achieved",
          label: labels.achieved,
          align: "right",
          editable: canEdit,
          field: "achieved",
          inputType: "number",
          sortType: "number",
          getField: (r) => (r.component === ESEWA_COMPONENT ? "achieved_cpc" : "achieved"),
          editValue: (r) => (r.component === ESEWA_COMPONENT ? r.achieved_cpc : r.achieved),
          sortValue: (r) => (r.component === ESEWA_COMPONENT ? r.achieved_cpc : r.achieved),
          render: (r) => fmtNum(
            r.component === ESEWA_COMPONENT ? r.achieved_cpc : r.achieved,
            { digits: 0 },
          ),
        },
        {
          key: "percent",
          label: labels.percent,
          align: "right",
          sortType: "number",
          sortValue: (r) => (r.component === ESEWA_COMPONENT ? r.percent_cpc : r.percent),
          render: (r) => fmtPct(
            r.component === ESEWA_COMPONENT ? r.percent_cpc : r.percent,
          ),
        },
      );
    } else {
      cols.push(
        { key: "target_dpr", label: labels.targetDpr, align: "right", editable: canEditTarget, field: "target_dpr", inputType: "number", sortType: "number", render: (r) => fmtNum(r.target_dpr, { digits: 0 }) },
        { key: "achieved_ecommittee", label: labels.achievedEcommittee, align: "right", editable: canEdit, field: "achieved_ecommittee", inputType: "number", sortType: "number", render: (r) => fmtNum(r.achieved_ecommittee, { digits: 0 }) },
        { key: "percent_ecommittee", label: labels.percentEcommittee, align: "right", sortType: "number", render: (r) => fmtPct(r.percent_ecommittee) },
        { key: "target_cpc", label: labels.targetCpc, align: "right", editable: canEdit, field: "target_cpc", inputType: "number", sortType: "number", render: (r) => fmtNum(r.target_cpc, { digits: 0 }) },
        { key: "achieved_cpc", label: labels.achievedCpc, align: "right", editable: canEdit, field: "achieved_cpc", inputType: "number", sortType: "number", render: (r) => fmtNum(r.achieved_cpc, { digits: 0 }) },
        { key: "percent_cpc", label: labels.percentCpc, align: "right", sortType: "number", render: (r) => fmtPct(r.percent_cpc) },
      );
    }
    cols.push(
      {
        key: "rag",
        label: labels.rag,
        sortType: "number",
        sortValue: (r) => rowPercent(r),
        render: (r) => <RagBadge status={ragColor(rowPercent(r))} />,
      },
      { key: "remarks", label: labels.remarks, editable: canEdit, field: "remarks", sortValue: (r) => r.remarks || "" },
      {
        key: "comments",
        label: "",
        sortable: false,
        filterable: false,
        render: (r) => (
          <CommentsButton onClick={() => setCommentsEntry(r)} />
        ),
      },
    );
    return cols;
  }, [canEdit, canEditTarget, anomalyKeys, labels, isEsewaComponent, isCloudComponent]);

  return (
    <div className="space-y-6" data-tour="physical-tracker">
      <OnboardingTour />
      <PeriodLockBanner highCourt={hc} reportingPeriod={period} />
      {showBanner && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 text-sm px-4 py-2 rounded-sm flex flex-wrap items-center justify-between gap-2">
          <span>{labels.draftRestored}</span>
          <span className="flex gap-2">
            <button type="button" onClick={dismissBanner} className="text-xs uppercase tracking-wider underline">{labels.keep}</button>
            <button type="button" onClick={() => { clearDraft(); setTarget(""); setAchieved(""); setRemarks(""); setTargetDpr(""); setAchievedEcommittee(""); setTargetCpc(""); setAchievedCpc(""); }} className="text-xs uppercase tracking-wider underline">{labels.discard}</button>
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
              disabled={!hc}
              hideEmptyOption
            />
            <SelectField label={labels.tableFilter} value={districtFilter} onChange={setDistrictFilter}
              options={[
                { label: labels.allDistricts, value: "" },
                { label: labels.hcLevelOnly, value: "__hc__" },
                ...(districts.data || []).map(d => ({ label: d.name, value: d.name })),
              ]}
              disabled={!hc}
              hideEmptyOption
            />
            <SelectField testid={TID.componentSelect} label={labels.component} value={component} onChange={(v) => { setComponent(v); setIndicator(""); }} options={(comps.data || []).map(c => c.name)} />
            <SelectField testid={TID.indicatorSelect} label={labels.indicator} value={indicator} onChange={setIndicator} options={(inds.data || []).map(i => i.indicator)} disabled={!component} />
            {isCloudComponent && (
              <SelectField
                testid="storage-type-select"
                label={labels.typeOfStorage}
                value={storageType}
                onChange={setStorageType}
                options={STORAGE_TYPE_OPTIONS}
              />
            )}
            {!isEsewaComponent && (
              <>
                <NumberField testid={TID.targetInput} label={canEditTarget ? labels.target : labels.targetAdmin} value={target} onChange={setTarget} disabled={!canEditTarget} />
                <NumberField testid={TID.achievedInput} label={labels.achievedCumulative} value={achieved} onChange={setAchieved} disabled={!canEdit} />
              </>
            )}
            {isEsewaComponent && (
              <>
                <NumberField testid="target-dpr-input" label={labels.targetDpr} value={targetDpr} onChange={setTargetDpr} disabled={!canEditTarget} />
                <NumberField testid="achieved-ecommittee-input" label={labels.achievedEcommittee} value={achievedEcommittee} onChange={setAchievedEcommittee} disabled={!canEdit} />
                <NumberField testid="target-cpc-input" label={labels.targetCpc} value={targetCpc} onChange={setTargetCpc} disabled={!canEdit} />
                <NumberField testid="achieved-cpc-input" label={labels.achievedCpc} value={achievedCpc} onChange={setAchievedCpc} disabled={!canEdit} />
              </>
            )}
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
            <button type="button" data-testid={TID.exportXlsx} onClick={() => downloadExport("xlsx")}
              className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
              <FileXls size={16} /> {labels.exportExcel}
            </button>
            <button type="button" data-testid={TID.exportPdf} onClick={() => downloadExport("pdf")}
              className="w-full inline-flex items-center justify-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-sm uppercase tracking-wider text-xs">
              <FilePdf size={16} /> {labels.exportPdf}
            </button>
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
              enableSortFilter
              page={tablePage}
              pageSize={PAGE_SIZE}
              onPageChange={setTablePage}
              onRowClick={(r) => {
                setHc(r.high_court);
                setComponent(r.component);
                setIndicator(r.indicator);
                setPeriod(r.reporting_period);
                setDistrict(r.district || "");
                if (r.component === CLOUD_COMPUTING_COMPONENT) {
                  setStorageType(r.storage_type || DEFAULT_STORAGE_TYPE);
                }
                if (r.component === ESEWA_COMPONENT) {
                  setTargetDpr(r.target_dpr ?? "");
                  setAchievedEcommittee(r.achieved_ecommittee ?? "");
                  setTargetCpc(r.target_cpc ?? "");
                  setAchievedCpc(r.achieved_cpc ?? "");
                }
              }}
            />
            {!list.isLoading && listItems.length === 0 && (
              <div className="text-center text-slate-400 py-12">{labels.noEntries}</div>
            )}
          </ScrollRegion>
          </>
        )}
      </Card>
      <EntryCommentsPanel
        tracker="physical"
        entryId={commentsEntry?.id}
        open={!!commentsEntry}
        onOpenChange={(open) => { if (!open) setCommentsEntry(null); }}
        entryLabel={commentsEntry ? `${commentsEntry.high_court} · ${commentsEntry.component}${commentsEntry.storage_type ? ` · ${commentsEntry.storage_type}` : ""} · ${commentsEntry.indicator}` : ""}
      />
    </div>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  disabled,
  testid,
  emptyLabel,
  hideEmptyOption = false,
}) {
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
        {!hideEmptyOption && (
          <option value="">{emptyLabel ?? t("common.selectAll")}</option>
        )}
        {options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          const l = typeof o === "string" ? o : o.label;
          return <option key={`${v}::${l}`} value={v}>{l}</option>;
        })}
      </select>
    </label>
  );
}

export function NumberField({ label, value, onChange, disabled, testid, exact = false }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{label}</span>
      <input
        data-testid={testid}
        type={exact ? "text" : "number"}
        inputMode={exact ? "decimal" : undefined}
        step={exact ? undefined : "any"}
        min={exact ? undefined : "0"}
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
