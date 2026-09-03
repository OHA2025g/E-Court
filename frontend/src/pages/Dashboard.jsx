import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, fmtNum, fmtPct, BACKEND_URL } from "@/lib/api";
import { formatPhysAmountLabel, formatPhysTargetAchieved } from "@/lib/physFormat";
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
  Info,
} from "@phosphor-icons/react";
import IndiaChoropleth from "@/components/IndiaChoropleth";
import FinancialTrackerDashboardTab from "@/components/dashboard/FinancialTrackerDashboardTab";
import RagDeltaWidget from "@/components/RagDeltaWidget";
import ComponentHcHeatmap from "@/components/ComponentHcHeatmap";
import DashboardTabErrorBoundary from "@/components/DashboardTabErrorBoundary";
import ParetoChart from "@/components/ParetoChart";
import TrendChart, { ProgressTrendInfoButton } from "@/components/TrendChart";
import DashboardAiInsights from "@/components/dashboard/DashboardAiInsights";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useDashboardLabels } from "@/lib/useDashboardLabels";
import { RAG_COLORS, ragCellProps, formatRagLegendLabel, barSeriesProps, seriesLegendLabel, useAccessibleRag } from "@/lib/ragColors";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend, PieChart, Pie, Cell,
} from "recharts";

const RAG_ORDER = ["GREEN", "AMBER", "RED", "NA"];

function RagDistributionInfoDialog({ open, onOpenChange, labels, ragData, ragTotal, periodLabel, highCourtLabel, componentLabel }) {
  const green = Number(ragData.find((d) => d.name === "GREEN")?.value) || 0;
  const amber = Number(ragData.find((d) => d.name === "AMBER")?.value) || 0;
  const red = Number(ragData.find((d) => d.name === "RED")?.value) || 0;
  const na = Number(ragData.find((d) => d.name === "NA")?.value) || 0;
  const sumParts = `${green} + ${amber} + ${red} + ${na} = ${ragTotal}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid={TID.ragDonutInfoDialog}>
        <DialogHeader>
          <DialogTitle className="font-display text-lg text-slate-900">{labels.ragInfoTitle}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 text-sm text-slate-700 leading-relaxed">
          <section>
            <h4 className="font-semibold text-slate-900 mb-1">What the centre TOTAL means</h4>
            <p>
              The number in the centre of the donut is the sum of all RAG legend counts for the current dashboard filters.
              It is <strong>not</strong> the number of High Courts (28) and <strong>not</strong> the number of components.
            </p>
            <p className="mt-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 font-mono text-xs text-slate-800">
              TOTAL = GREEN + AMBER + RED + NA<br />
              {sumParts}
            </p>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Current filter scope</h4>
            <ul className="list-disc pl-5 space-y-1">
              <li>Reporting period: <strong>{periodLabel}</strong></li>
              <li>High Court: <strong>{highCourtLabel}</strong></li>
              <li>Component: <strong>{componentLabel}</strong></li>
              <li>Indicator rows counted (TOTAL): <strong>{ragTotal}</strong></li>
            </ul>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">What each unit counted is</h4>
            <p>
              Backend rollup builds one physical series per:
            </p>
            <p className="mt-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 font-mono text-xs text-slate-800">
              High Court × Component × Indicator × Reporting Period
            </p>
            <p className="mt-2">
              District-level rows (if any) are summed into that key before RAG is applied. Each such rolled row contributes
              <strong> +1 </strong> to exactly one of GREEN / AMBER / RED / NA.
            </p>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">How each row is classified</h4>
            <ol className="list-decimal pl-5 space-y-1">
              <li>
                Achievement %: <span className="font-mono text-xs">(achieved ÷ target) × 100</span>
              </li>
              <li>
                If target is missing or 0, or achieved is missing → % is not computable → <strong>NA</strong>
              </li>
              <li>Otherwise apply thresholds (defaults):</li>
            </ol>
            <ul className="mt-2 list-disc pl-5 space-y-1">
              <li><strong>GREEN</strong> — % ≥ 80</li>
              <li><strong>AMBER</strong> — 65% ≤ % &lt; 80</li>
              <li><strong>RED</strong> — % &lt; 65</li>
              <li><strong>NA</strong> — no usable %</li>
            </ul>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Current breakdown</h4>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 uppercase tracking-wide">
                  <tr>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2 text-right">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {RAG_ORDER.map((name) => {
                    const value = Number(ragData.find((d) => d.name === name)?.value) || 0;
                    return (
                      <tr key={name} className="border-t border-slate-100">
                        <td className="px-3 py-2">
                          <span className="inline-flex items-center gap-2">
                            <span
                              className="inline-block w-2.5 h-2.5 rounded-sm border border-slate-200"
                              style={{ background: RAG_COLORS[name] || RAG_COLORS.NA }}
                              aria-hidden="true"
                            />
                            {formatRagLegendLabel(name, false)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums font-semibold text-slate-900">{value}</td>
                      </tr>
                    );
                  })}
                  <tr className="border-t border-slate-200 bg-slate-50">
                    <td className="px-3 py-2 font-semibold">TOTAL</td>
                    <td className="px-3 py-2 text-right tabular-nums font-bold text-slate-900">{ragTotal}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Important note on “Select All” periods</h4>
            <p>
              When Reporting Period is <strong>Select All</strong>, every matching period is counted. The same
              High Court × Component × Indicator in two months counts twice (once per period). For example,
              June 2026 consolidated rows plus Cloud Computing’s Mar 2026 cumulative window both contribute to TOTAL.
            </p>
            <p className="mt-2">
              Choosing a single reporting period (e.g. June 2026) limits the donut to that month only.
            </p>
          </section>

          <section>
            <h4 className="font-semibold text-slate-900 mb-1">Short formula</h4>
            <pre className="rounded-lg bg-slate-900 text-slate-100 text-[11px] leading-relaxed p-3 overflow-x-auto whitespace-pre-wrap">{`For each rolled physical row (HC × Component × Indicator × Period):
  pct = achieved / target × 100   (or NA if not computable)
  bucket += 1 for GREEN / AMBER / RED / NA

TOTAL = number of those rows
      = GREEN + AMBER + RED + NA
      = ${sumParts}`}</pre>
          </section>
        </div>
        <DialogFooter>
          <button type="button" className="app-btn-secondary" onClick={() => onOpenChange(false)}>
            {labels.ragInfoClose}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PerformancePctTooltip({ active, payload, label, nameKey = "component", selectedComponent = "" }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  const title = label || row[nameKey] || "-";
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
        const hasPhysTarget = row.phys_target != null && Number(row.phys_target) > 0;
        const pct = isPhys && !hasPhysTarget ? null : entry.value;
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

/** Tabs hidden for CPC officers - court-scoped view only. */
const CPC_HIDDEN_TABS = new Set(["rag-trends", "geographic", "performance", "hc-table"]);

function physRag(pct) {
  if (pct == null) return "NA";
  if (pct >= 80) return "GREEN";
  if (pct >= 65) return "AMBER";
  return "RED";
}

function withTargetBasedPhysPercent(rows) {
  return (rows || []).map((r) => {
    const hasTarget = r.phys_target != null && Number(r.phys_target) > 0;
    if (hasTarget) return r;
    return { ...r, phys_percent: null };
  });
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
  const [ragInfoOpen, setRagInfoOpen] = useState(false);
  const [trendInfoOpen, setTrendInfoOpen] = useState(false);
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
    queryKey: ["dash-hc", "v4-kpi-sum", dashParams, cpcCourt],
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
    () => sortTableRows(withTargetBasedPhysPercent(byComp.data), compSort.key, compSort.dir),
    [byComp.data, compSort],
  );
  const sortedHcRows = useMemo(
    () => sortTableRows(withTargetBasedPhysPercent(byHc.data), hcSort.key, hcSort.dir),
    [byHc.data, hcSort],
  );
  const compChartRows = useMemo(
    () => withTargetBasedPhysPercent(byComp.data),
    [byComp.data],
  );
  const hcChartRows = useMemo(
    () => withTargetBasedPhysPercent(byHc.data),
    [byHc.data],
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
  // Digitization → Cr pages; Cloud capacity (stored GB) → TB.
  const physTargetDisp = formatPhysAmountLabel(s?.physical?.target, physUom);
  const physAchievedDisp = formatPhysAmountLabel(s?.physical?.achieved, physUom);
  // Physical Target / Achieved / Avg % only when a single component is selected.
  const showPhysicalKpis = Boolean(component);
  const kpiRow = (
    <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 ${showPhysicalKpis ? "xl:grid-cols-6" : ""}`}>
      {showPhysicalKpis && (
        <>
          <KpiCard testId={TID.kpiPhysicalTarget} icon={Target} label={labels.physTargetSum} value={physTargetDisp} accent="primary" />
          <KpiCard testId={TID.kpiPhysicalAchieved} icon={CheckCircle} label={labels.physAchieved} value={physAchievedDisp} accent="slate" />
          <KpiCard testId={TID.kpiPhysicalPercent} icon={Gauge} label={labels.physPercent} value={fmtPct(s?.physical?.percent)} accent={s?.physical?.percent == null ? "slate" : s?.physical?.percent >= 80 ? "green" : s?.physical?.percent >= 65 ? "amber" : "red"} />
        </>
      )}
      <KpiCard testId={TID.kpiFinReleased} icon={CurrencyInr} label={labels.finReleased} value={fmtNum(s?.financial?.released, { digits: 2 })} accent="primary" />
      <KpiCard testId={TID.kpiFinUtilized} icon={CurrencyInr} label={labels.finUtilized} value={fmtNum(s?.financial?.utilized, { digits: 2 })} accent="slate" />
      <KpiCard testId={TID.kpiFinPercent} icon={TrendUp} label={labels.finPercent} value={fmtPct(s?.financial?.utilisation_percent)} accent={s?.financial?.utilisation_percent >= 80 ? "green" : s?.financial?.utilisation_percent >= 65 ? "amber" : "red"} />
    </div>
  );

  const ragDonut = (
    <Card
      title={labels.ragDistribution}
      testId={TID.ragDonut}
      elevated
      titleAction={(
        <button
          type="button"
          data-testid={TID.ragDonutInfoBtn}
          className="inline-flex items-center justify-center w-6 h-6 rounded-full border border-slate-300 text-slate-600 hover:bg-slate-100 hover:text-[#003B73] hover:border-[#003B73]/40 transition-colors shrink-0"
          aria-label={labels.ragInfoAria}
          title={labels.ragInfoAria}
          onClick={() => setRagInfoOpen(true)}
        >
          <Info size={14} weight="bold" />
        </button>
      )}
    >
      <RagDistributionInfoDialog
        open={ragInfoOpen}
        onOpenChange={setRagInfoOpen}
        labels={labels}
        ragData={ragData}
        ragTotal={ragTotal}
        periodLabel={
          period
            ? ((periods.data || []).find((p) => p.period === period)?.label || period)
            : labels.allPeriods
        }
        highCourtLabel={highCourt || labels.allHighCourts}
        componentLabel={component || labels.allComponents}
      />
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
          <BarChart data={compChartRows} margin={{ top: 8, right: 16, left: 0, bottom: 60 }}>
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
          <BarChart data={hcChartRows} margin={{ top: 8, right: 16, left: 0, bottom: 80 }}>
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
                <td className="dense-table-center">{formatPhysAmountLabel(r.phys_target, r.phys_uom)}</td>
                <td className="dense-table-center">{formatPhysAmountLabel(r.phys_achieved, r.phys_uom)}</td>
                <td className="dense-table-center">
                  <div className="flex justify-center">
                    <RagBadge status={physRag(r.phys_percent)} label={fmtPct(r.phys_percent)} />
                  </div>
                </td>
                <td className="dense-table-center">{fmtNum(r.fin_released, { digits: 4 })}</td>
                <td className="dense-table-center">{fmtNum(r.fin_utilized, { digits: 4 })}</td>
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
                <td className="dense-table-center">{fmtNum(r.fin_released, { digits: 4 })}</td>
                <td className="dense-table-center">{fmtNum(r.fin_utilized, { digits: 4 })}</td>
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
            <Card
              title={labels.progressTrend}
              elevated
              titleAction={(
                <ProgressTrendInfoButton
                  onClick={() => setTrendInfoOpen(true)}
                  ariaLabel={labels.progressTrendInfoAria}
                />
              )}
            >
              <TrendChart
                trendData={trend.data}
                infoOpen={trendInfoOpen}
                onInfoOpenChange={setTrendInfoOpen}
              />
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
