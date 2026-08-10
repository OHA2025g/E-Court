import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, fmtNum, fmtPct, BACKEND_URL } from "@/lib/api";
import { formatPhysAmount, formatPhysTargetAchieved } from "@/lib/physFormat";
import { useAuth } from "@/lib/auth";
import Card, { KpiCard } from "@/components/Card";
import RagBadge from "@/components/RagBadge";
import { TID } from "@/lib/testIds";
import {
  FilePdf,
  FileXls,
  CalendarBlank,
  ChartPieSlice,
  TrendUp,
  MapTrifold,
  ChartBar,
  Table,
  Buildings,
  Target,
  CheckCircle,
  CurrencyInr,
  Gauge,
  Wallet,
  Stack,
  CaretUp,
  CaretDown,
} from "@phosphor-icons/react";
import IndiaChoropleth from "@/components/IndiaChoropleth";
import FinancialTrackerDashboardTab from "@/components/dashboard/FinancialTrackerDashboardTab";
import RagDeltaWidget from "@/components/RagDeltaWidget";
import ComponentHcHeatmap from "@/components/ComponentHcHeatmap";
import DashboardTabErrorBoundary from "@/components/DashboardTabErrorBoundary";
import ParetoChart from "@/components/ParetoChart";
import TrendChart from "@/components/TrendChart";
import DashboardAiInsights from "@/components/dashboard/DashboardAiInsights";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useDashboardLabels } from "@/lib/useDashboardLabels";
import { RAG_COLORS, ragCellProps, formatRagLegendLabel, barSeriesProps, seriesLegendLabel, useAccessibleRag } from "@/lib/ragColors";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend, PieChart, Pie, Cell,
} from "recharts";

const RAG_ORDER = ["GREEN", "AMBER", "RED", "NA"];

function PerformancePctTooltip({ active, payload, label, nameKey = "component", selectedComponent = "" }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  const title = label || row[nameKey] || "—";
  const componentName = row.component || selectedComponent || "";
  const physUom = row.phys_uom
    || (componentName === "Cloud Computing & Storage" ? "GB / TB / PB" : undefined)
    || (componentName === "Digitisation of Court Records" ? "Crore Pages" : undefined);
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md max-w-xs">
      <div className="font-semibold text-slate-800 mb-1.5">{title}</div>
      {payload.map((entry) => {
        const key = entry.dataKey;
        const isPhys = key === "phys_percent";
        const pct = entry.value;
        const countLine = isPhys
          ? formatPhysTargetAchieved(row.phys_target, row.phys_achieved, physUom)
          : `Released ₹${fmtNum(row.fin_released)} Cr / Utilised ₹${fmtNum(row.fin_utilized)} Cr`;
        return (
          <div key={key} className="mb-1 last:mb-0">
            <div className="flex items-center gap-1.5 text-slate-700">
              <span className="inline-block h-2 w-2 rounded-sm shrink-0" style={{ background: entry.color || "#64748b" }} />
              <span>{entry.name}: <span className="font-semibold tabular-nums">{fmtPct(pct)}</span></span>
            </div>
            <div className="pl-3.5 text-slate-500 tabular-nums">{countLine}</div>
          </div>
        );
      })}
    </div>
  );
}

const TAB_CONFIG = {
  overview: { icon: ChartPieSlice },
  "rag-trends": { icon: TrendUp },
  geographic: { icon: MapTrifold },
  performance: { icon: ChartBar },
  "financial-tracker": { icon: Wallet },
  "component-table": { icon: Table },
  "hc-table": { icon: Buildings },
};

const DASHBOARD_TABS = [
  "overview",
  "rag-trends",
  "geographic",
  "performance",
  "financial-tracker",
  "component-table",
  "hc-table",
];

/** Tabs hidden for CPC officers — court-scoped view only. */
const CPC_HIDDEN_TABS = new Set(["rag-trends", "geographic", "performance", "hc-table"]);

function physRag(pct) {
  if (pct == null) return "NA";
  if (pct >= 80) return "GREEN";
  if (pct >= 65) return "AMBER";
  return "RED";
}

function compareSortValues(a, b) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { sensitivity: "base", numeric: true });
}

function sortTableRows(rows, key, dir) {
  return [...rows].sort((a, b) => {
    const cmp = compareSortValues(a[key], b[key]);
    return dir === "asc" ? cmp : -cmp;
  });
}

function DashboardSortTh({ label, columnKey, sort, onSort, align = "left", testId }) {
  const active = sort.key === columnKey;
  return (
    <th className={align === "center" ? "dense-table-center" : undefined}>
      <button
        type="button"
        data-testid={testId}
        className={`dashboard-sort-th-btn ${align === "center" ? "is-center" : ""}`}
        aria-label={`Sort by ${label}`}
        onClick={() => onSort((prev) => ({
          key: columnKey,
          dir: prev.key === columnKey && prev.dir === "asc" ? "desc" : "asc",
        }))}
      >
        <span>{label}</span>
        <span className="dashboard-sort-carets" aria-hidden="true">
          <CaretUp
            size={10}
            weight="bold"
            className={active && sort.dir === "asc" ? "is-active" : ""}
          />
          <CaretDown
            size={10}
            weight="bold"
            className={active && sort.dir === "desc" ? "is-active" : ""}
          />
        </span>
      </button>
    </th>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const labels = useDashboardLabels();
  const [period, setPeriod] = useState("");
  const [periodReady, setPeriodReady] = useState(false);
  const [highCourt, setHighCourt] = useState("");
  const [component, setComponent] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [compSort, setCompSort] = useState({ key: "component", dir: "asc" });
  const [hcSort, setHcSort] = useState({ key: "high_court", dir: "asc" });
  const [accessibleRag] = useAccessibleRag();
  const cpcCourt = user?.role === "CPC" ? user?.high_court : null;
  const visibleTabs = useMemo(
    () => (cpcCourt ? DASHBOARD_TABS.filter((tab) => !CPC_HIDDEN_TABS.has(tab)) : DASHBOARD_TABS),
    [cpcCourt],
  );

  useEffect(() => {
    if (cpcCourt && CPC_HIDDEN_TABS.has(activeTab)) {
      setActiveTab("overview");
    }
  }, [cpcCourt, activeTab]);

  useEffect(() => {
    if (cpcCourt) setHighCourt(cpcCourt);
  }, [cpcCourt]);

  const onDashboardTabChange = (tab) => {
    setActiveTab(tab);
    // After Overview scroll depth, Geographic must land in view (not a blank viewport).
    requestAnimationFrame(() => {
      const tabs = document.querySelector('[data-testid="dashboard-tabs"]');
      tabs?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  };

  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get("/master/periods").then(r => r.data) });
  const hcs = useQuery({ queryKey: ["hcs"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const comps = useQuery({ queryKey: ["comps"], queryFn: () => api.get("/master/components").then(r => r.data) });
  // Default once to All periods (baseline May 2026 is no longer a filter option).
  useEffect(() => {
    if (periodReady || !periods.data) return;
    setPeriod("");
    setPeriodReady(true);
  }, [periods.data, periodReady]);

  const dashParams = useMemo(() => {
    const params = {};
    if (period) params.reporting_period = period;
    if (highCourt) params.high_court = highCourt;
    if (component) params.component = component;
    return params;
  }, [period, highCourt, component]);

  const summary = useQuery({
    queryKey: ["dash-summary", "v4-count-abs", dashParams, cpcCourt],
    queryFn: () => api.get("/dashboard/summary", { params: dashParams }).then(r => r.data),
    enabled: periodReady,
  });
  const byComp = useQuery({
    queryKey: ["dash-comp", dashParams, cpcCourt],
    queryFn: () => api.get("/dashboard/by-component", { params: dashParams }).then(r => r.data),
    enabled: periodReady,
  });
  const byHc = useQuery({
    queryKey: ["dash-hc", "v3-mean", dashParams, cpcCourt],
    queryFn: () => api.get("/dashboard/by-high-court", { params: dashParams }).then(r => r.data),
    enabled: !cpcCourt && periodReady,
  });
  const trend = useQuery({
    queryKey: ["dash-trend", highCourt, component, cpcCourt],
    queryFn: () => api.get("/dashboard/trend", {
      params: {
        ...(highCourt ? { high_court: highCourt } : {}),
        ...(component ? { component } : {}),
      },
    }).then(r => r.data),
    enabled: !cpcCourt,
  });

  const s = summary.data;
  const ragData = useMemo(() => {
    if (!s) return [];
    const counts = s.rag_physical || {};
    return RAG_ORDER
      .map((name) => ({ name, value: Number(counts[name]) || 0 }))
      .filter((d) => d.value > 0);
  }, [s]);
  const ragTotal = useMemo(() => ragData.reduce((sum, d) => sum + d.value, 0), [ragData]);

  const sortedCompRows = useMemo(
    () => sortTableRows(byComp.data || [], compSort.key, compSort.dir),
    [byComp.data, compSort],
  );
  const sortedHcRows = useMemo(
    () => sortTableRows(byHc.data || [], hcSort.key, hcSort.dir),
    [byHc.data, hcSort],
  );

  const cabinetBriefHref = useMemo(() => {
    const qs = new URLSearchParams(dashParams).toString();
    return `${BACKEND_URL}/api/export/cabinet-brief${qs ? `?${qs}` : ""}`;
  }, [dashParams]);

  const hcTableExportHref = useMemo(() => {
    const qs = new URLSearchParams(dashParams).toString();
    return `${BACKEND_URL}/api/export/dashboard/high-court-table${qs ? `?${qs}` : ""}`;
  }, [dashParams]);

  const componentTableExportHref = useMemo(() => {
    const qs = new URLSearchParams(dashParams).toString();
    return `${BACKEND_URL}/api/export/dashboard/component-table${qs ? `?${qs}` : ""}`;
  }, [dashParams]);

  const unifiedHeader = (
    <div className="dashboard-unified-header dashboard-hero-pattern">
      {cpcCourt && (
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-amber-300/40 bg-amber-400/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100">
          {labels.cpcScopeBanner(cpcCourt)}
        </div>
      )}
      <p className="dashboard-hero-desc dashboard-unified-desc">
        {cpcCourt
          ? labels.cpcHeroDesc(cpcCourt)
          : "Monitor physical progress, financial utilisation, and AI-driven action plans across High Courts and components."}
      </p>

      <div className="dashboard-unified-toolbar">
        {!cpcCourt && (
          <label className="dashboard-unified-period">
            <span className="dashboard-unified-period-heading">
              <Buildings size={14} aria-hidden="true" />
              <span className="dashboard-unified-period-label">{labels.highCourtFilter}</span>
            </span>
            <select
              data-testid={TID.highCourtSelect}
              value={highCourt}
              onChange={(e) => setHighCourt(e.target.value)}
              className="dashboard-unified-select"
              aria-label={labels.highCourtFilter}
            >
              <option value="">{labels.allHighCourts}</option>
              {(hcs.data || []).map((hc) => (
                <option key={hc.name || hc} value={hc.name || hc}>{hc.name || hc}</option>
              ))}
            </select>
          </label>
        )}

        <label className="dashboard-unified-period">
          <span className="dashboard-unified-period-heading">
            <Stack size={14} aria-hidden="true" />
            <span className="dashboard-unified-period-label">{labels.componentFilter}</span>
          </span>
          <select
            data-testid={TID.componentSelect}
            value={component}
            onChange={(e) => setComponent(e.target.value)}
            className="dashboard-unified-select"
            aria-label={labels.componentFilter}
          >
            <option value="">{labels.allComponents}</option>
            {(comps.data || []).map((c) => (
              <option key={c.code || c.name || c} value={c.name || c}>{c.name || c}</option>
            ))}
          </select>
        </label>

        <label className="dashboard-unified-period">
          <span className="dashboard-unified-period-heading">
            <CalendarBlank size={14} aria-hidden="true" />
            <span className="dashboard-unified-period-label">{labels.reportingPeriod}</span>
          </span>
          <select
            data-testid={TID.periodSelect}
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="dashboard-unified-select"
            aria-label={labels.reportingPeriod}
          >
            <option value="">{labels.allPeriods}</option>
            {(periods.data || []).map(p => (
              <option key={p.period} value={p.period}>{p.label}</option>
            ))}
          </select>
        </label>

        {user?.role !== "CPC" && (
          <a
            data-testid="cabinet-brief-btn"
            href={cabinetBriefHref}
            target="_blank" rel="noreferrer"
            className="dashboard-unified-cta"
          >
            <FilePdf size={16} weight="duotone" /> {labels.cabinetBrief}
          </a>
        )}
      </div>
    </div>
  );

  const physUom = s?.physical?.absolute_scope || s?.physical?.uom;
  // Digitization scope → Cr pages (e.g. 3,108.77), never absolute *1e7 page counts.
  const physTargetDisp = formatPhysAmount(s?.physical?.target, physUom).text;
  const physAchievedDisp = formatPhysAmount(s?.physical?.achieved, physUom).text;
  const kpiRow = (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      <KpiCard testId={TID.kpiPhysicalTarget} icon={Target} label={labels.physTargetSum} value={physTargetDisp} accent="primary" />
      <KpiCard testId={TID.kpiPhysicalAchieved} icon={CheckCircle} label={labels.physAchieved} value={physAchievedDisp} accent="slate" />
      <KpiCard testId={TID.kpiPhysicalPercent} icon={Gauge} label={labels.physPercent} value={fmtPct(s?.physical?.percent)} accent={s?.physical?.percent >= 80 ? "green" : s?.physical?.percent >= 65 ? "amber" : "red"} />
      <KpiCard testId={TID.kpiFinReleased} icon={CurrencyInr} label={labels.finReleased} value={fmtNum(s?.financial?.released, { digits: 2 })} accent="primary" />
      <KpiCard testId={TID.kpiFinUtilized} icon={CurrencyInr} label={labels.finUtilized} value={fmtNum(s?.financial?.utilized, { digits: 2 })} accent="slate" />
      <KpiCard testId={TID.kpiFinPercent} icon={TrendUp} label={labels.finPercent} value={fmtPct(s?.financial?.utilisation_percent)} accent={s?.financial?.utilisation_percent >= 80 ? "green" : s?.financial?.utilisation_percent >= 65 ? "amber" : "red"} />
    </div>
  );

  const ragDonut = (
    <Card title={labels.ragDistribution} testId={TID.ragDonut} elevated>
      <div className="px-2 pb-2 pt-0 flex flex-col">
        {ragData.length === 0 ? (
          <div className="h-64 grid-bg flex items-center justify-center text-sm text-slate-400">{labels.noData}</div>
        ) : (
          <>
            <div className="relative h-[300px] shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                  <Pie
                    data={ragData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={118}
                    innerRadius={72}
                    paddingAngle={2}
                    stroke="#fff"
                    strokeWidth={2}
                    label={false}
                    isAnimationActive={false}
                  >
                    {ragData.map((d) => (
                      <Cell key={d.name} {...ragCellProps(d.name, accessibleRag)} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value, name) => [
                      `${value} (${ragTotal ? Math.round((value / ragTotal) * 100) : 0}%)`,
                      formatRagLegendLabel(name, accessibleRag),
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 flex items-center justify-center pointer-events-none">
                <div className="text-center px-1">
                  <div className="font-display text-3xl font-bold text-slate-800 tabular-nums leading-tight" data-testid="rag-donut-total">
                    {ragTotal}
                  </div>
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 mt-0.5">Total</div>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 pt-0.5" data-testid="rag-donut-legend">
              {ragData.map((d) => (
                <div key={d.name} className="inline-flex items-center gap-1.5 text-sm text-slate-700">
                  <span
                    className="inline-block w-3 h-3 rounded-sm shrink-0 border border-slate-200"
                    style={{ background: RAG_COLORS[d.name] || RAG_COLORS.NA }}
                    aria-hidden="true"
                  />
                  <span>{formatRagLegendLabel(d.name, accessibleRag)}</span>
                  <span className="font-semibold tabular-nums text-slate-900">{d.value}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Card>
  );

  const componentBars = (
    <Card title={labels.componentPerformance} testId={TID.componentChart} elevated>
      <div className="h-96 p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={byComp.data || []} margin={{ top: 8, right: 16, left: 0, bottom: 60 }}>
            <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
            <XAxis dataKey="component" stroke="#475569" fontSize={10} angle={-25} textAnchor="end" interval={0} height={80} />
            <YAxis stroke="#475569" fontSize={11} unit="%" />
            <Tooltip content={<PerformancePctTooltip nameKey="component" selectedComponent={component} />} />
            <Legend />
            <Bar dataKey="phys_percent" name={seriesLegendLabel("Physical %", "phys_percent", accessibleRag)} {...barSeriesProps("phys_percent", accessibleRag)} />
            <Bar dataKey="fin_percent" name={seriesLegendLabel("Financial %", "fin_percent", accessibleRag)} {...barSeriesProps("fin_percent", accessibleRag)} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );

  const hcBars = (
    <Card title={cpcCourt ? labels.hcSummary : labels.hcComparison} testId={TID.hcChart} elevated>
      <div className="h-[480px] p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={byHc.data || []} margin={{ top: 8, right: 16, left: 0, bottom: 80 }}>
            <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
            <XAxis dataKey="high_court" stroke="#475569" fontSize={10} angle={-35} textAnchor="end" interval={0} height={100} />
            <YAxis stroke="#475569" fontSize={11} unit="%" />
            <Tooltip content={<PerformancePctTooltip nameKey="high_court" selectedComponent={component} />} />
            <Legend />
            <Bar dataKey="phys_percent" name={seriesLegendLabel("Physical %", "phys_percent", accessibleRag)} {...barSeriesProps("phys_percent_hc", accessibleRag)} />
            <Bar dataKey="fin_percent" name={seriesLegendLabel("Financial %", "fin_percent", accessibleRag)} {...barSeriesProps("fin_percent_hc", accessibleRag)} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );

  const componentTable = (
    <Card
      title={labels.componentDrilldown}
      elevated
      action={(
        <a
          data-testid={TID.dashboardCompExportXlsx}
          href={componentTableExportHref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-sm uppercase tracking-wider text-[11px]"
        >
          <FileXls size={14} /> {labels.downloadExcel}
        </a>
      )}
    >
      <ScrollRegion className="overflow-x-auto max-h-[560px]" label={labels.componentDrilldownTable}>
        <table className="dense-table dashboard-table w-full" data-testid="dashboard-component-table">
          <thead>
            <tr>
              <DashboardSortTh label={labels.colComponent} columnKey="component" sort={compSort} onSort={setCompSort} testId="comp-sort-component" />
              <DashboardSortTh label={labels.colPhysT} columnKey="phys_target" sort={compSort} onSort={setCompSort} align="center" testId="comp-sort-phys-target" />
              <DashboardSortTh label={labels.colPhysA} columnKey="phys_achieved" sort={compSort} onSort={setCompSort} align="center" testId="comp-sort-phys-achieved" />
              <DashboardSortTh label={labels.colPhysPct} columnKey="phys_percent" sort={compSort} onSort={setCompSort} align="center" testId="comp-sort-phys-pct" />
              <DashboardSortTh label={labels.colRelCr} columnKey="fin_released" sort={compSort} onSort={setCompSort} align="center" testId="comp-sort-fin-released" />
              <DashboardSortTh label={labels.colUtilCr} columnKey="fin_utilized" sort={compSort} onSort={setCompSort} align="center" testId="comp-sort-fin-utilized" />
              <DashboardSortTh label={labels.colUtilPct} columnKey="fin_percent" sort={compSort} onSort={setCompSort} align="center" testId="comp-sort-fin-pct" />
            </tr>
          </thead>
          <tbody>
            {sortedCompRows.map((r) => (
              <tr key={r.component}>
                <td className="font-medium text-slate-700">{r.component}</td>
                <td className="dense-table-center">{formatPhysAmount(r.phys_target, r.phys_uom).text}</td>
                <td className="dense-table-center">{formatPhysAmount(r.phys_achieved, r.phys_uom).text}</td>
                <td className="dense-table-center">
                  <div className="flex justify-center">
                    <RagBadge status={physRag(r.phys_percent)} label={fmtPct(r.phys_percent)} />
                  </div>
                </td>
                <td className="dense-table-center">{fmtNum(r.fin_released)}</td>
                <td className="dense-table-center">{fmtNum(r.fin_utilized)}</td>
                <td className="dense-table-center">
                  <div className="flex justify-center">
                    <RagBadge status={physRag(r.fin_percent)} label={fmtPct(r.fin_percent)} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </Card>
  );

  const hcTable = (
    <Card
      title={cpcCourt ? labels.hcDrilldownCpc : labels.hcDrilldown}
      elevated
      action={(
        <a
          data-testid={TID.dashboardHcExportXlsx}
          href={hcTableExportHref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-sm uppercase tracking-wider text-[11px]"
        >
          <FileXls size={14} /> {labels.downloadExcel}
        </a>
      )}
    >
      <ScrollRegion className="overflow-x-auto max-h-[560px]" label={labels.hcDrilldownTable}>
        <table className="dense-table dashboard-table w-full" data-testid="dashboard-hc-table">
          <thead>
            <tr>
              <DashboardSortTh label={labels.colHighCourt} columnKey="high_court" sort={hcSort} onSort={setHcSort} testId="hc-sort-high-court" />
              <DashboardSortTh label={labels.colRelCr} columnKey="fin_released" sort={hcSort} onSort={setHcSort} align="center" testId="hc-sort-fin-released" />
              <DashboardSortTh label={labels.colUtilCr} columnKey="fin_utilized" sort={hcSort} onSort={setHcSort} align="center" testId="hc-sort-fin-utilized" />
              <DashboardSortTh label={labels.colUtilPct} columnKey="fin_percent" sort={hcSort} onSort={setHcSort} align="center" testId="hc-sort-fin-pct" />
            </tr>
          </thead>
          <tbody>
            {sortedHcRows.map((r) => (
              <tr key={r.high_court}>
                <td className="font-medium text-slate-700">{r.high_court}</td>
                <td className="dense-table-center">{fmtNum(r.fin_released)}</td>
                <td className="dense-table-center">{fmtNum(r.fin_utilized)}</td>
                <td className="dense-table-center">
                  <div className="flex justify-center">
                    <RagBadge status={physRag(r.fin_percent)} label={fmtPct(r.fin_percent)} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </Card>
  );

  const tabLabels = useMemo(() => ({
    overview: labels.tabOverview,
    "rag-trends": labels.tabRagTrends,
    geographic: labels.tabGeographic,
    performance: labels.tabPerformance,
    "financial-tracker": labels.tabFinancialTracker,
    "component-table": labels.tabComponentTable,
    "hc-table": cpcCourt ? labels.tabHcTableCpc : labels.tabHcTable,
  }), [labels, cpcCourt]);

  return (
    <div data-testid={TID.dashboard} className="dashboard-shell">
      {unifiedHeader}

      <Tabs value={activeTab} onValueChange={onDashboardTabChange} className="w-full">
        <TabsList
          data-testid="dashboard-tabs"
          className="dashboard-tab-list w-full h-auto"
        >
          {visibleTabs.map((tab) => {
            const Icon = TAB_CONFIG[tab]?.icon;
            return (
              <TabsTrigger
                key={tab}
                value={tab}
                data-testid={`dashboard-tab-${tab}`}
                className="dashboard-tab-trigger"
              >
                {Icon && <Icon size={16} weight={activeTab === tab ? "fill" : "duotone"} />}
                {tabLabels[tab]}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="overview" className="mt-5 space-y-5">
          {kpiRow}
          <RagDeltaWidget reportingPeriod={period} highCourt={highCourt} component={component} />
          <DashboardAiInsights reportingPeriod={period} highCourt={highCourt} component={component} />
        </TabsContent>

        <TabsContent value="rag-trends" className="mt-5 space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {ragDonut}
            <Card title={labels.progressTrend} elevated>
              <TrendChart trendData={trend.data} />
            </Card>
          </div>
        </TabsContent>

        <TabsContent
          value="geographic"
          forceMount
          className="mt-5 space-y-5 data-[state=inactive]:hidden"
        >
          <DashboardTabErrorBoundary label="Geographic view" resetKey={`${period}|${highCourt}|${component}`}>
            <div data-testid="dashboard-geographic-panel" className="space-y-5">
              <IndiaChoropleth reportingPeriod={period} highCourt={highCourt} component={component} />
              <ComponentHcHeatmap reportingPeriod={period} highCourt={highCourt} component={component} />
            </div>
          </DashboardTabErrorBoundary>
        </TabsContent>

        <TabsContent value="performance" className="mt-5 space-y-5">
          <ParetoChart reportingPeriod={period} highCourt={highCourt} component={component} />
          {componentBars}
          {hcBars}
        </TabsContent>

        <TabsContent value="financial-tracker" className="mt-5">
          <FinancialTrackerDashboardTab reportingPeriod={period} highCourt={highCourt} component={component} labels={labels} />
        </TabsContent>

        <TabsContent value="component-table" className="mt-5">
          {componentTable}
        </TabsContent>

        <TabsContent value="hc-table" className="mt-5">
          {hcTable}
        </TabsContent>
      </Tabs>
    </div>
  );
}
