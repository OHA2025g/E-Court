import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, fmtNum, fmtPct, formatApiError, BACKEND_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import RagBadge from "@/components/RagBadge";
import BulkUploadPanel from "@/components/tracker/BulkUploadPanel";
import EditableTrackerTable from "@/components/tracker/EditableTrackerTable";
import { useTrackerDraft } from "@/lib/useTrackerDraft";
import { TID } from "@/lib/testIds";
import { toast } from "sonner";
import { FloppyDisk, FileXls, FilePdf, Warning, ListPlus } from "@phosphor-icons/react";
import { SelectField, NumberField, TextField } from "@/pages/PhysicalTracker";
import { TableSkeleton } from "@/components/Skeletons";
import { useMinLoading } from "@/lib/useMinLoading";
import PeriodLockBanner from "@/components/PeriodLockBanner";
import { unwrapTrackerResponse } from "@/lib/trackerApi";
import { useTrackerLabels } from "@/lib/useTrackerLabels";
import ScrollRegion from "@/components/ui/ScrollRegion";
import EntryCommentsPanel, { CommentsButton } from "@/components/EntryCommentsPanel";
import ComponentNameCell from "@/components/tracker/ComponentNameCell";
import { TooltipProvider } from "@/components/ui/tooltip";

const PAGE_SIZE = 50;
const TABLE_FETCH_SIZE = 500;

export default function FinancialTracker() {
  const { user } = useAuth();
  const labels = useTrackerLabels();
  const qc = useQueryClient();
  const [period, setPeriod] = useState("");
  const [hc, setHc] = useState(user?.role === "CPC" ? user.high_court : "");
  const [district, setDistrict] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [component, setComponent] = useState("");
  const [target, setTarget] = useState("");
  const [allocated, setAllocated] = useState("");
  const [released, setReleased] = useState("");
  const [utilized, setUtilized] = useState("");
  const [remarks, setRemarks] = useState("");
  const [warn, setWarn] = useState(null);
  const [saving, setSaving] = useState(false);
  const [initBusy, setInitBusy] = useState(false);
  const [initPromptDismissed, setInitPromptDismissed] = useState(false);
  const [tablePage, setTablePage] = useState(1);
  const [commentsEntry, setCommentsEntry] = useState(null);

  const hcs = useQuery({ queryKey: ["hcs"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const comps = useQuery({ queryKey: ["comps"], queryFn: () => api.get("/master/components").then(r => r.data) });
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
    return p;
  }, [hc, component, period, districtFilter]);
  const list = useQuery({
    queryKey: ["financial", listParams],
    queryFn: () => api.get("/financial", { params: listParams }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const listItems = list.data?.items || [];
  const listTotal = list.data?.total ?? listItems.length;
  const anomalies = useQuery({
    queryKey: ["anomalies", "financial", period],
    enabled: !!period,
    queryFn: () => api.get("/anomalies", { params: { reporting_period: period, tracker: "financial" } }).then((r) => r.data),
  });
  const anomalyKeys = useMemo(() => {
    const s = new Set();
    (anomalies.data?.flags || []).forEach((f) => {
      s.add(`${f.high_court}|${f.component}`);
    });
    return s;
  }, [anomalies.data]);
  const pfms = useQuery({
    queryKey: ["pfms", hc, period],
    enabled: !!hc && !!period,
    queryFn: () => api.get("/pfms/reconcile", { params: { high_court: hc, reporting_period: period } }).then((r) => r.data),
  });
  const pfmsMap = useMemo(() => {
    const m = {};
    (pfms.data?.rows || []).forEach((r) => { m[r.component] = r; });
    return m;
  }, [pfms.data]);

  const componentDescMap = useMemo(() => {
    const m = {};
    (comps.data || []).forEach((c) => {
      if (c.description) m[c.name] = c.description;
    });
    listItems.forEach((r) => {
      if (r.component && r.description) m[r.component] = r.description;
    });
    return m;
  }, [comps.data, listItems]);

  useEffect(() => { setTablePage(1); }, [hc, component, period, districtFilter]);
  const initPromptKey = hc && period ? `pmis-fin-init-prompt:${hc}:${period}` : null;
  const hcPeriodRows = useQuery({
    queryKey: ["financial", "hc-period", hc, period],
    enabled: !!hc && !!period,
    queryFn: () => api.get("/financial", { params: { high_court: hc, reporting_period: period } }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const hcPeriodCount = hcPeriodRows.data?.total ?? hcPeriodRows.data?.items?.length ?? 0;

  useEffect(() => {
    if (!initPromptKey) return;
    setInitPromptDismissed(sessionStorage.getItem(initPromptKey) === "1");
  }, [initPromptKey]);

  const setDraftFields = useCallback((f) => {
    if (f.component != null) setComponent(f.component);
    if (f.district != null) setDistrict(f.district);
    if (f.target != null) setTarget(f.target);
    if (f.allocated != null) setAllocated(f.allocated);
    if (f.released != null) setReleased(f.released);
    if (f.utilized != null) setUtilized(f.utilized);
    if (f.remarks != null) setRemarks(f.remarks);
  }, []);
  const draftFields = useMemo(() => ({
    component, district, target, allocated, released, utilized, remarks,
  }), [component, district, target, allocated, released, utilized, remarks]);
  const { showBanner, clearDraft, dismissBanner } = useTrackerDraft({
    userId: user?.email || user?.id, tracker: "financial", period, hc, fields: draftFields, setFields: setDraftFields,
  });

  useEffect(() => {
    if (!listItems.length || !hc || !component || !period) return;
    const d = district || null;
    const found = listItems.find(r =>
      r.high_court === hc && r.component === component && r.reporting_period === period &&
      (r.district || null) === d
    );
    if (found) {
      setTarget(found.fund_target ?? "");
      setAllocated(found.fund_allocated ?? "");
      setReleased(found.fund_released ?? "");
      setUtilized(found.fund_utilized ?? "");
      setRemarks(found.remarks ?? "");
    } else {
      setTarget(""); setAllocated(""); setReleased(""); setUtilized(""); setRemarks("");
    }
  }, [listItems, hc, component, period, district]);

  const isCpc = user?.role === "CPC";
  const canAddEntry = user?.role === "Admin";
  const canEdit = user?.role !== "Viewer";
  const canEditFinField = useCallback((field) => {
    if (!canEdit) return false;
    if (!isCpc) return true;
    return field === "fund_utilized" || field === "remarks";
  }, [canEdit, isCpc]);
  const selectedEntryExists = useMemo(() => {
    if (!hc || !component || !period) return false;
    const d = district || null;
    return listItems.some((r) =>
      r.high_court === hc && r.component === component &&
      r.reporting_period === period && (r.district || null) === d
    );
  }, [listItems, hc, component, period, district]);
  const canSaveEntry = canEdit && (canAddEntry || selectedEntryExists);
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
      const r = await api.post("/financial/init-period", {
        high_court: hc, reporting_period: period,
        component: component || undefined,
      });
      toast.success(labels.initSuccess(r.data.created, r.data.skipped));
      qc.invalidateQueries({ queryKey: ["financial"] });
      qc.invalidateQueries({ queryKey: ["dash-summary"] });
      dismissInitPrompt();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setInitBusy(false);
    }
  }

  async function save(payload) {
    const body = payload || {
      high_court: hc, component, reporting_period: period,
      district: district || null,
      fund_target: target === "" ? null : Number(target),
      fund_allocated: allocated === "" ? null : Number(allocated),
      fund_released: released === "" ? null : Number(released),
      fund_utilized: utilized === "" ? null : Number(utilized),
      remarks: remarks || null,
    };
    if (!body.high_court || !body.component || !body.reporting_period) {
      toast.error(labels.selectHcComponentPeriod);
      return null;
    }
    const r = await api.post("/financial", body);
    toast.success(r.data?.warning ? labels.savedWithWarning : labels.saved);
    if (r.data?.warning) setWarn(r.data.warning);
    else setWarn(null);
    clearDraft();
    qc.invalidateQueries({ queryKey: ["financial"] });
    qc.invalidateQueries({ queryKey: ["dash-summary"] });
    return r.data;
  }

  async function saveForm() {
    setSaving(true);
    try {
      await save();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally { setSaving(false); }
  }

  async function saveRow(row) {
    try {
      await save({
        high_court: row.high_court,
        component: row.component,
        reporting_period: row.reporting_period,
        district: row.district || null,
        fund_target: row.fund_target,
        fund_allocated: row.fund_allocated,
        fund_released: row.fund_released,
        fund_utilized: row.fund_utilized,
        remarks: row.remarks,
      });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
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
    return `${BACKEND_URL}/api/export/financial?${params.toString()}`;
  }

  const ragColor = (r) => r >= 80 ? "GREEN" : r >= 65 ? "AMBER" : r != null ? "RED" : "NA";

  const tableColumns = useMemo(() => [
    { key: "high_court", label: labels.highCourt },
    {
      key: "district",
      label: labels.district,
      render: (r) => r.district || labels.hcLevel,
      sortValue: (r) => r.district || labels.hcLevel,
      filterValue: (r) => r.district || labels.hcLevel,
    },
    {
      key: "component",
      label: labels.component,
      render: (r) => (
        <ComponentNameCell
          name={r.component}
          description={r.description || componentDescMap[r.component]}
        >
          {anomalyKeys.has(`${r.high_court}|${r.component}`) && (
            <span className="text-[9px] uppercase tracking-wider bg-violet-100 text-violet-800 px-1 rounded-sm" title={labels.anomalyBadge}>3σ</span>
          )}
        </ComponentNameCell>
      ),
      sortValue: (r) => r.component,
      filterValue: (r) => r.component,
    },
    { key: "reporting_period", label: labels.period },
    {
      key: "fund_target",
      label: labels.fundTarget,
      align: "right",
      render: (r) => fmtNum(r.fund_target),
      sortValue: (r) => r.fund_target,
      filterValue: (r) => fmtNum(r.fund_target),
      sortType: "number",
      filterType: "number",
    },
    {
      key: "fund_allocated",
      label: labels.fundAllocated,
      align: "right",
      render: (r) => fmtNum(r.fund_allocated),
      sortValue: (r) => r.fund_allocated,
      filterValue: (r) => fmtNum(r.fund_allocated),
      sortType: "number",
      filterType: "number",
    },
    {
      key: "fund_released",
      label: labels.fundReleased,
      align: "right",
      editable: canEditFinField("fund_released"),
      field: "fund_released",
      inputType: "number",
      render: (r) => fmtNum(r.fund_released),
      sortValue: (r) => r.fund_released,
      filterValue: (r) => fmtNum(r.fund_released),
      sortType: "number",
      filterType: "number",
    },
    {
      key: "fund_utilized",
      label: labels.fundUtilized,
      align: "right",
      editable: canEditFinField("fund_utilized"),
      field: "fund_utilized",
      inputType: "number",
      render: (r) => fmtNum(r.fund_utilized),
      sortValue: (r) => r.fund_utilized,
      filterValue: (r) => fmtNum(r.fund_utilized),
      sortType: "number",
      filterType: "number",
    },
    {
      key: "utilisation_percent",
      label: labels.utilPercent,
      align: "right",
      render: (r) => fmtPct(r.utilisation_percent),
      sortValue: (r) => r.utilisation_percent,
      filterValue: (r) => fmtPct(r.utilisation_percent),
      sortType: "number",
      filterType: "number",
    },
    {
      key: "variance",
      label: labels.variance,
      align: "right",
      render: (r) => fmtNum(r.variance),
      sortValue: (r) => r.variance,
      filterValue: (r) => fmtNum(r.variance),
      sortType: "number",
      filterType: "number",
    },
    {
      key: "pfms_variance",
      label: labels.pfmsDelta,
      align: "right",
      render: (r) => {
        const row = pfmsMap[r.component];
        if (!row) return "—";
        if (row.flagged) {
          return <span className="text-amber-700 font-medium" title={labels.treasuryVariance}>{fmtNum(row.variance)}</span>;
        }
        return fmtNum(row.variance);
      },
      sortValue: (r) => pfmsMap[r.component]?.variance ?? null,
      filterValue: (r) => {
        const row = pfmsMap[r.component];
        if (!row) return "—";
        return fmtNum(row.variance);
      },
      sortType: "number",
      filterType: "number",
    },
    {
      key: "rag",
      label: labels.rag,
      render: (r) => <RagBadge status={ragColor(r.utilisation_percent)} />,
      sortValue: (r) => ragColor(r.utilisation_percent),
      filterValue: (r) => ragColor(r.utilisation_percent),
      filterType: "select",
      filterOptions: ["GREEN", "AMBER", "RED", "NA"],
    },
    {
      key: "remarks",
      label: labels.remarks,
      editable: canEditFinField("remarks"),
      field: "remarks",
      sortValue: (r) => r.remarks || "",
      filterValue: (r) => r.remarks || "",
    },
    {
      key: "comments",
      label: "",
      sortable: false,
      filterable: false,
      render: (r) => <CommentsButton onClick={() => setCommentsEntry(r)} />,
    },
  ], [canEditFinField, pfmsMap, anomalyKeys, labels, componentDescMap]);

  return (
    <TooltipProvider delayDuration={250}>
    <div className="space-y-6">
      <PeriodLockBanner highCourt={hc} reportingPeriod={period} />
      {showBanner && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 text-sm px-4 py-2 rounded-sm flex flex-wrap items-center justify-between gap-2">
          <span>{labels.draftRestored}</span>
          <span className="flex gap-2">
            <button type="button" onClick={dismissBanner} className="text-xs uppercase tracking-wider underline">{labels.keep}</button>
            <button type="button" onClick={() => { clearDraft(); setTarget(""); setAllocated(""); setReleased(""); setUtilized(""); setRemarks(""); }} className="text-xs uppercase tracking-wider underline">{labels.discard}</button>
          </span>
        </div>
      )}
      {showInitPrompt && (
        <div className="bg-sky-50 border border-sky-200 text-sky-900 text-sm px-4 py-3 rounded-sm flex flex-wrap items-center justify-between gap-3">
          <span>{labels.finInitPrompt(hc, period)}</span>
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
          title={labels.finEntry}
          subtitle={
            isCpc
              ? labels.finEntrySubtitleCpc
              : canAddEntry
                ? labels.finEntrySubtitle
                : `${labels.finEntrySubtitle} ${labels.entryUpdateOnlyHint}`
          }
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
            <SelectField testid={TID.componentSelect} label={labels.component} value={component} onChange={setComponent} options={(comps.data || []).map(c => c.name)} />
            <NumberField label="Fund Target (₹ Cr)" value={target} onChange={setTarget} disabled={!canEditFinField("fund_target")} />
            <NumberField label="Fund Allocated (₹ Cr)" value={allocated} onChange={setAllocated} disabled={!canEditFinField("fund_allocated")} />
            <NumberField testid={TID.releasedInput} label="Funds Released (₹ Cr)" value={released} onChange={setReleased} disabled={!canEditFinField("fund_released")} />
            <NumberField testid={TID.utilizedInput} label="Funds Utilised (₹ Cr)" value={utilized} onChange={setUtilized} disabled={!canEditFinField("fund_utilized")} />
            <div className="sm:col-span-2"><TextField testid={TID.remarksInput} label="Remarks" value={remarks} onChange={setRemarks} disabled={!canEditFinField("remarks")} /></div>
            {warn && (
              <div className="sm:col-span-2 flex items-start gap-2 bg-amber-50 border border-amber-200 text-amber-800 text-xs p-2 rounded-sm">
                <Warning size={16} weight="fill" /> <span>{warn}</span>
              </div>
            )}
            <div className="sm:col-span-2 mt-2 flex flex-wrap items-center gap-3">
              <button data-testid={TID.saveBtn} disabled={!canSaveEntry || saving} onClick={saveForm}
                className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm font-medium uppercase tracking-wider inline-flex items-center gap-2">
                <FloppyDisk size={16} /> {saving ? labels.saving : labels.saveEntry}
              </button>
              {canAddEntry && (
                <button type="button" disabled={initBusy || !hc || !period} onClick={initPeriod}
                  className="border border-[#003B73] text-[#003B73] hover:bg-slate-50 disabled:opacity-50 px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
                  <ListPlus size={16} /> {initBusy ? labels.initializing : labels.initComponentRows}
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
            tracker="financial"
            period={period}
            canEdit={canAddEntry}
            templateUrl={`${BACKEND_URL}/api/financial/bulk-template`}
            onComplete={() => { qc.invalidateQueries({ queryKey: ["financial"] }); qc.invalidateQueries({ queryKey: ["dash-summary"] }); }}
          />
        </Card>
      </div>

      <Card title={labels.finEntries} subtitle={labels.entriesSubtitle(listTotal)} testId={TID.financialTable}>
        {useMinLoading(list.isLoading) ? (
          <TableSkeleton rows={8} cols={12} />
        ) : (
          <>
          <ScrollRegion className="overflow-x-auto max-h-[560px]" label={labels.finEntries}>
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
                setPeriod(r.reporting_period);
                setDistrict(r.district || "");
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
        tracker="financial"
        entryId={commentsEntry?.id}
        open={!!commentsEntry}
        onOpenChange={(open) => { if (!open) setCommentsEntry(null); }}
        entryLabel={commentsEntry ? `${commentsEntry.high_court} · ${commentsEntry.component}` : ""}
      />
    </div>
    </TooltipProvider>
  );
}
