import React, { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, fmtNum, fmtPct, BACKEND_URL, formatApiError } from "@/lib/api";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import RagBadge from "@/components/RagBadge";
import { TID } from "@/lib/testIds";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { FileXls, FilePdf, MagnifyingGlass, FloppyDisk, Trash } from "@phosphor-icons/react";
import { SelectField } from "@/pages/PhysicalTracker";
import { toast } from "sonner";
import { unwrapTrackerResponse } from "@/lib/trackerApi";

function ExportBtn({ url, kind, testid }) {
  return (
    <a data-testid={testid} href={url} target="_blank" rel="noreferrer"
      className="inline-flex items-center gap-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-sm uppercase tracking-wider text-[11px]">
      {kind === "xlsx" ? <FileXls size={14} /> : <FilePdf size={14} />} {kind.toUpperCase()}
    </a>
  );
}

function SearchInput({ value, onChange, placeholder }) {
  return (
    <div className="relative">
      <MagnifyingGlass size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="pl-7 pr-3 py-1.5 border border-slate-300 rounded-sm bg-white text-sm w-56 focus:outline-none focus:border-[#003B73]"
      />
    </div>
  );
}

function SortableTable({ rows, columns, search, sortDefault, scrollLabel, noDataLabel }) {
  const [sort, setSort] = useState(sortDefault || { key: columns[0].key, dir: "asc" });
  const filtered = useMemo(() => {
    let r = rows;
    if (search) {
      const q = search.toLowerCase();
      r = r.filter(row => columns.some(c => String(row[c.key] ?? "").toLowerCase().includes(q)));
    }
    r = [...r].sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      if (typeof x === "number" && typeof y === "number") return sort.dir === "asc" ? x - y : y - x;
      return sort.dir === "asc" ? String(x).localeCompare(String(y)) : String(y).localeCompare(String(x));
    });
    return r;
  }, [rows, search, sort, columns]);

  return (
    <ScrollRegion className="overflow-x-auto max-h-[600px]" label={scrollLabel}>
      <table className="dense-table w-full">
        <thead className="sticky top-0">
          <tr>
            {columns.map(c => (
              <th key={c.key} className={c.align === "right" ? "text-right" : ""}>
                <button onClick={() => setSort(s => ({ key: c.key, dir: s.key === c.key && s.dir === "asc" ? "desc" : "asc" }))}
                  className="uppercase tracking-wider hover:text-[#003B73]">
                  {c.label}{sort.key === c.key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.slice(0, 1000).map((r, i) => (
            <tr key={r.id || i}>
              {columns.map(c => (
                <td key={c.key} className={c.align === "right" ? "text-right" : ""}>
                  {c.render ? c.render(r) : (r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
          {filtered.length === 0 && (
            <tr><td colSpan={columns.length} className="text-center text-slate-400 py-12">{noDataLabel}</td></tr>
          )}
        </tbody>
      </table>
    </ScrollRegion>
  );
}

export default function Reports() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [hc, setHc] = useState("");
  const [component, setComponent] = useState("");
  const [subject, setSubject] = useState("");
  const [period, setPeriod] = useState("");
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("physical");
  const [selectedViewId, setSelectedViewId] = useState("");
  const [viewName, setViewName] = useState("");
  const [viewBusy, setViewBusy] = useState(false);

  const savedViews = useQuery({
    queryKey: ["report-views"],
    queryFn: () => api.get("/reports/views").then(r => r.data),
  });

  const hcs = useQuery({ queryKey: ["hcs"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const comps = useQuery({ queryKey: ["comps"], queryFn: () => api.get("/master/components").then(r => r.data) });
  const subs = useQuery({ queryKey: ["subjects"], queryFn: () => api.get("/master/outcome-subjects").then(r => r.data) });
  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get("/master/periods").then(r => r.data) });

  const phys = useQuery({
    queryKey: ["rep-phys", hc, component, period],
    queryFn: () => api.get("/physical", { params: { high_court: hc || undefined, component: component || undefined, reporting_period: period || undefined } }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const fin = useQuery({
    queryKey: ["rep-fin", hc, component, period],
    queryFn: () => api.get("/financial", { params: { high_court: hc || undefined, component: component || undefined, reporting_period: period || undefined } }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const out = useQuery({
    queryKey: ["rep-out", hc, subject, period],
    queryFn: () => api.get("/outcome", { params: { high_court: hc || undefined, subject: subject || undefined, reporting_period: period || undefined } }).then((r) => unwrapTrackerResponse(r.data)),
  });
  const physItems = phys.data?.items || [];
  const finItems = fin.data?.items || [];
  const outItems = out.data?.items || [];

  const physUrl = (f) => {
    const p = new URLSearchParams(); if (hc) p.set("high_court", hc); if (component) p.set("component", component); if (period) p.set("reporting_period", period); p.set("format", f);
    return `${BACKEND_URL}/api/export/physical?${p}`;
  };
  const finUrl = (f) => {
    const p = new URLSearchParams(); if (hc) p.set("high_court", hc); if (component) p.set("component", component); if (period) p.set("reporting_period", period); p.set("format", f);
    return `${BACKEND_URL}/api/export/financial?${p}`;
  };
  const outUrl = (f) => {
    const p = new URLSearchParams(); if (hc) p.set("high_court", hc); if (subject) p.set("subject", subject); if (period) p.set("reporting_period", period); p.set("format", f);
    return `${BACKEND_URL}/api/export/outcome?${p}`;
  };

  const ragOf = (r) => r >= 80 ? "GREEN" : r >= 65 ? "AMBER" : r != null ? "RED" : "NA";

  function applyView(view) {
    if (!view) return;
    const f = view.filters || {};
    setHc(f.high_court || "");
    setComponent(f.component || "");
    setSubject(f.subject || "");
    setPeriod(f.reporting_period || "");
    if (view.tracker) setActiveTab(view.tracker);
  }

  function onSelectView(id) {
    setSelectedViewId(id);
    const view = (savedViews.data || []).find((v) => v.id === id);
    if (view) applyView(view);
  }

  async function saveCurrentView() {
    if (!viewName.trim()) {
      toast.error(t("reports.enterViewName"));
      return;
    }
    setViewBusy(true);
    try {
      await api.post("/reports/views", {
        name: viewName.trim(),
        tracker: activeTab,
        filters: {
          high_court: hc || undefined,
          component: component || undefined,
          subject: subject || undefined,
          reporting_period: period || undefined,
        },
      });
      toast.success(t("reports.viewSaved"));
      setViewName("");
      qc.invalidateQueries({ queryKey: ["report-views"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setViewBusy(false);
    }
  }

  async function deleteSelectedView() {
    if (!selectedViewId) return;
    if (!window.confirm(t("reports.deleteViewConfirm"))) return;
    try {
      await api.delete(`/reports/views/${selectedViewId}`);
      toast.success(t("reports.viewDeleted"));
      setSelectedViewId("");
      qc.invalidateQueries({ queryKey: ["report-views"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  }

  const tabViews = useMemo(
    () => (savedViews.data || []).filter((v) => v.tracker === activeTab),
    [savedViews.data, activeTab],
  );

  return (
    <div data-testid={TID.reportsRoot} className="space-y-6">
      <Card title={t("reports.filtersTitle")} subtitle={t("reports.filtersSubtitle")}>
        <div className="p-4 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <label className="block">
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{t("reports.savedViews")}</span>
              <select value={selectedViewId} onChange={(e) => onSelectView(e.target.value)}
                className="mt-1 block w-56 px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm focus:outline-none focus:border-[#003B73]">
                <option value="">{t("reports.selectSavedView")}</option>
                {tabViews.map((v) => (
                  <option key={v.id} value={v.id}>{v.name}</option>
                ))}
              </select>
            </label>
            <input type="text" value={viewName} onChange={(e) => setViewName(e.target.value)} placeholder={t("reports.viewNamePlaceholder")}
              className="px-3 py-2 border border-slate-300 rounded-sm text-sm w-40 focus:outline-none focus:border-[#003B73]" />
            <button type="button" disabled={viewBusy || !viewName.trim()} onClick={saveCurrentView}
              className="inline-flex items-center gap-1.5 bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-3 py-2 rounded-sm uppercase tracking-wider text-[11px]">
              <FloppyDisk size={14} /> {t("reports.saveView")}
            </button>
            {selectedViewId && (
              <button type="button" onClick={deleteSelectedView}
                className="inline-flex items-center gap-1.5 border border-red-300 text-red-700 hover:bg-red-50 px-3 py-2 rounded-sm uppercase tracking-wider text-[11px]">
                <Trash size={14} /> {t("reports.deleteView")}
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <SelectField label={t("reports.colHighCourt")} value={hc} onChange={setHc} options={(hcs.data || []).map(h => h.name)} />
          <SelectField label={t("reports.colComponent")} value={component} onChange={setComponent} options={(comps.data || []).map(c => c.name)} />
          <SelectField label={t("reports.colSubject")} value={subject} onChange={setSubject} options={(subs.data || []).map(s => s.name)} />
          <SelectField label={t("reports.colPeriod")} value={period} onChange={setPeriod} options={(periods.data || []).map(p => ({ label: p.label, value: p.period }))} />
          </div>
        </div>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-transparent border-b border-slate-200 w-full justify-start rounded-none p-0">
          <TabsTrigger value="physical" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#003B73] data-[state=active]:text-[#003B73] data-[state=inactive]:text-slate-600 uppercase tracking-wider text-xs">{t("reports.tabPhysical")}</TabsTrigger>
          <TabsTrigger value="financial" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#003B73] data-[state=active]:text-[#003B73] data-[state=inactive]:text-slate-600 uppercase tracking-wider text-xs">{t("reports.tabFinancial")}</TabsTrigger>
          <TabsTrigger value="outcome" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#003B73] data-[state=active]:text-[#003B73] data-[state=inactive]:text-slate-600 uppercase tracking-wider text-xs">{t("reports.tabOutcome")}</TabsTrigger>
        </TabsList>

        <TabsContent value="physical" className="mt-4">
          <Card title={t("reports.physicalReport", { count: phys.data?.total ?? physItems.length })}
            action={<div className="flex gap-2"><SearchInput value={search} onChange={setSearch} placeholder={t("common.search", { defaultValue: "Search…" })} /><ExportBtn url={physUrl("xlsx")} kind="xlsx" testid={TID.exportXlsx} /><ExportBtn url={physUrl("pdf")} kind="pdf" testid={TID.exportPdf} /></div>}>
            <SortableTable
              scrollLabel={t("reports.reportTable")}
              noDataLabel={t("reports.noData")}
              rows={physItems}
              search={search}
              sortDefault={{ key: "high_court", dir: "asc" }}
              columns={[
                { key: "high_court", label: t("reports.colHighCourt") },
                { key: "component", label: t("reports.colComponent") },
                { key: "indicator", label: t("reports.colIndicator") },
                { key: "reporting_period", label: t("reports.colPeriod") },
                { key: "target", label: t("reports.colTarget"), align: "right", render: r => fmtNum(r.target, { digits: 0 }) },
                { key: "achieved", label: t("reports.colAchieved"), align: "right", render: r => fmtNum(r.achieved, { digits: 0 }) },
                { key: "percent", label: t("reports.colPercent"), align: "right", render: r => fmtPct(r.percent) },
                { key: "rag", label: t("reports.colRag"), render: r => <RagBadge status={ragOf(r.percent)} /> },
                { key: "remarks", label: t("reports.colRemarks"), render: r => <span className="text-slate-500">{r.remarks || "—"}</span> },
              ]} />
          </Card>
        </TabsContent>

        <TabsContent value="financial" className="mt-4">
          <Card title={t("reports.financialReport", { count: fin.data?.total ?? finItems.length })}
            action={<div className="flex gap-2"><SearchInput value={search} onChange={setSearch} placeholder={t("common.search", { defaultValue: "Search…" })} /><ExportBtn url={finUrl("xlsx")} kind="xlsx" /><ExportBtn url={finUrl("pdf")} kind="pdf" /></div>}>
            <SortableTable
              scrollLabel={t("reports.reportTable")}
              noDataLabel={t("reports.noData")}
              rows={finItems}
              search={search}
              sortDefault={{ key: "high_court", dir: "asc" }}
              columns={[
                { key: "high_court", label: t("reports.colHighCourt") },
                { key: "component", label: t("reports.colComponent") },
                { key: "reporting_period", label: t("reports.colPeriod") },
                { key: "fund_released", label: t("reports.colReleased"), align: "right", render: r => fmtNum(r.fund_released) },
                { key: "fund_utilized", label: t("reports.colUtilised"), align: "right", render: r => fmtNum(r.fund_utilized) },
                { key: "utilisation_percent", label: t("reports.colUtilPct"), align: "right", render: r => fmtPct(r.utilisation_percent) },
                { key: "variance", label: t("reports.colVariance"), align: "right", render: r => fmtNum(r.variance) },
                { key: "rag", label: t("reports.colRag"), render: r => <RagBadge status={ragOf(r.utilisation_percent)} /> },
              ]} />
          </Card>
        </TabsContent>

        <TabsContent value="outcome" className="mt-4">
          <Card title={t("reports.outcomeReport", { count: out.data?.total ?? outItems.length })}
            action={<div className="flex gap-2"><SearchInput value={search} onChange={setSearch} placeholder={t("common.search", { defaultValue: "Search…" })} /><ExportBtn url={outUrl("xlsx")} kind="xlsx" /><ExportBtn url={outUrl("pdf")} kind="pdf" /></div>}>
            <SortableTable
              scrollLabel={t("reports.reportTable")}
              noDataLabel={t("reports.noData")}
              rows={outItems}
              search={search}
              sortDefault={{ key: "subject", dir: "asc" }}
              columns={[
                { key: "high_court", label: t("reports.colHighCourt") },
                { key: "granularity", label: t("reports.colGranularity") },
                { key: "subject", label: t("reports.colSubject") },
                { key: "kpi_id", label: t("master.colKpiId") },
                { key: "kpi", label: t("reports.colKpi") },
                { key: "outcome_type", label: t("master.colType") },
                { key: "baseline", label: t("reports.colBaseline"), align: "right", render: r => fmtNum(r.baseline) },
                { key: "value", label: t("reports.colValue"), align: "right", render: r => fmtNum(r.value) },
                { key: "computed_percent", label: t("tracker.percent"), align: "right", render: r => fmtPct(r.computed_percent) },
                { key: "reporting_period", label: t("reports.colPeriod") },
              ]} />
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
