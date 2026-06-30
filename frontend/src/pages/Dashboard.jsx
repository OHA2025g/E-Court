import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, fmtNum, fmtPct, BACKEND_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card, { KpiCard } from "@/components/Card";
import RagBadge from "@/components/RagBadge";
import { TID } from "@/lib/testIds";
import {
  FilePdf,
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
} from "@phosphor-icons/react";
import IndiaChoropleth from "@/components/IndiaChoropleth";
import FinancialTrackerDashboardTab from "@/components/dashboard/FinancialTrackerDashboardTab";
import RagDeltaWidget from "@/components/RagDeltaWidget";
import ComponentHcHeatmap from "@/components/ComponentHcHeatmap";
import ParetoChart from "@/components/ParetoChart";
import TrendChart from "@/components/TrendChart";
import DashboardAiInsights from "@/components/dashboard/DashboardAiInsights";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useDashboardLabels } from "@/lib/useDashboardLabels";
import { ragCellProps, formatRagLegendLabel, barSeriesProps, seriesLegendLabel, useAccessibleRag } from "@/lib/ragColors";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend, PieChart, Pie, Cell,
} from "recharts";

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

export default function Dashboard() {
  const { user } = useAuth();
  const labels = useDashboardLabels();
  const [period, setPeriod] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
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

  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get("/master/periods").then(r => r.data) });
  const summary = useQuery({ queryKey: ["dash-summary", period, cpcCourt], queryFn: () => api.get("/dashboard/summary", { params: period ? { reporting_period: period } : {} }).then(r => r.data) });
  const byComp = useQuery({ queryKey: ["dash-comp", period, cpcCourt], queryFn: () => api.get("/dashboard/by-component", { params: period ? { reporting_period: period } : {} }).then(r => r.data) });
  const byHc = useQuery({
    queryKey: ["dash-hc", period, cpcCourt],
    queryFn: () => api.get("/dashboard/by-high-court", { params: period ? { reporting_period: period } : {} }).then(r => r.data),
    enabled: !cpcCourt,
  });
  const trend = useQuery({
    queryKey: ["dash-trend", cpcCourt],
    queryFn: () => api.get("/dashboard/trend").then(r => r.data),
    enabled: !cpcCourt,
  });

  const s = summary.data;
  const ragData = s ? Object.entries(s.rag_physical || {}).map(([k, v]) => ({ name: k, value: v })) : [];

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
        {s?.physical?.percent != null && (
          <span className="dashboard-hero-chip dashboard-unified-chip">
            <Gauge size={14} />
            {labels.physPercent} {fmtPct(s.physical.percent)}
          </span>
        )}
        {s?.financial?.utilisation_percent != null && (
          <span className="dashboard-hero-chip dashboard-unified-chip">
            <CurrencyInr size={14} />
            {labels.finPercent} {fmtPct(s.financial.utilisation_percent)}
          </span>
        )}

        <label className="dashboard-unified-period">
          <CalendarBlank size={14} aria-hidden="true" />
          <span className="dashboard-unified-period-label">{labels.reportingPeriod}</span>
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
            href={`${BACKEND_URL}/api/export/cabinet-brief${period ? `?reporting_period=${period}` : ""}`}
            target="_blank" rel="noreferrer"
            className="dashboard-unified-cta"
          >
            <FilePdf size={16} weight="duotone" /> {labels.cabinetBrief}
          </a>
        )}
      </div>
    </div>
  );

  const kpiRow = (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      <KpiCard testId={TID.kpiPhysicalTarget} icon={Target} label={labels.physTargetSum} value={fmtNum(s?.physical?.target, { digits: 0 })} hint={labels.indicatorsHint(s?.physical?.indicator_count || 0)} accent="primary" />
      <KpiCard testId={TID.kpiPhysicalAchieved} icon={CheckCircle} label={labels.physAchieved} value={fmtNum(s?.physical?.achieved, { digits: 0 })} accent="slate" />
      <KpiCard testId={TID.kpiPhysicalPercent} icon={Gauge} label={labels.physPercent} value={fmtPct(s?.physical?.percent)} accent={s?.physical?.percent >= 80 ? "green" : s?.physical?.percent >= 65 ? "amber" : "red"} />
      <KpiCard testId={TID.kpiFinReleased} icon={CurrencyInr} label={labels.finReleased} value={fmtNum(s?.financial?.released)} hint={labels.componentRowsHint(s?.financial?.component_count || 0)} accent="primary" />
      <KpiCard testId={TID.kpiFinUtilized} icon={CurrencyInr} label={labels.finUtilized} value={fmtNum(s?.financial?.utilized)} hint={labels.varianceHint(fmtNum(s?.financial?.variance))} accent="slate" />
      <KpiCard testId={TID.kpiFinPercent} icon={TrendUp} label={labels.finPercent} value={fmtPct(s?.financial?.utilisation_percent)} accent={s?.financial?.utilisation_percent >= 80 ? "green" : s?.financial?.utilisation_percent >= 65 ? "amber" : "red"} />
    </div>
  );

  const ragDonut = (
    <Card title={labels.ragDistribution} testId={TID.ragDonut} elevated>
      <div className="h-72 p-3">
        {ragData.length === 0 ? (
          <div className="h-full grid-bg flex items-center justify-center text-sm text-slate-400">{labels.noData}</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={ragData} dataKey="value" nameKey="name" outerRadius={90} innerRadius={50} paddingAngle={2}>
                {ragData.map((d) => (
                  <Cell key={d.name} {...ragCellProps(d.name, accessibleRag)} />
                ))}
              </Pie>
              <Tooltip formatter={(value, name) => [value, formatRagLegendLabel(name, accessibleRag)]} />
              <Legend formatter={(value) => formatRagLegendLabel(value, accessibleRag)} />
            </PieChart>
          </ResponsiveContainer>
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
            <Tooltip />
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
            <Tooltip />
            <Legend />
            <Bar dataKey="phys_percent" name={seriesLegendLabel("Physical %", "phys_percent", accessibleRag)} {...barSeriesProps("phys_percent_hc", accessibleRag)} />
            <Bar dataKey="fin_percent" name={seriesLegendLabel("Financial %", "fin_percent", accessibleRag)} {...barSeriesProps("fin_percent_hc", accessibleRag)} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );

  const componentTable = (
    <Card title={labels.componentDrilldown} elevated>
      <ScrollRegion className="overflow-x-auto max-h-[560px]" label={labels.componentDrilldownTable}>
        <table className="dense-table dashboard-table w-full" data-testid="dashboard-component-table">
          <thead>
            <tr>
              <th>{labels.colComponent}</th>
              <th className="dense-table-center">{labels.colPhysT}</th>
              <th className="dense-table-center">{labels.colPhysA}</th>
              <th className="dense-table-center">{labels.colPhysPct}</th>
              <th className="dense-table-center">{labels.colRelCr}</th>
              <th className="dense-table-center">{labels.colUtilCr}</th>
              <th className="dense-table-center">{labels.colUtilPct}</th>
            </tr>
          </thead>
          <tbody>
            {(byComp.data || []).map((r) => (
              <tr key={r.component}>
                <td className="font-medium text-slate-700">{r.component}</td>
                <td className="dense-table-center">{fmtNum(r.phys_target, { digits: 0 })}</td>
                <td className="dense-table-center">{fmtNum(r.phys_achieved, { digits: 0 })}</td>
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
    <Card title={cpcCourt ? labels.hcDrilldownCpc : labels.hcDrilldown} elevated>
      <ScrollRegion className="overflow-x-auto max-h-[560px]" label={labels.hcDrilldownTable}>
        <table className="dense-table dashboard-table w-full" data-testid="dashboard-hc-table">
          <thead>
            <tr>
              <th>{labels.colHighCourt}</th>
              <th className="dense-table-center">{labels.colPhysPct}</th>
              <th className="dense-table-center">{labels.colRelCr}</th>
              <th className="dense-table-center">{labels.colUtilCr}</th>
              <th className="dense-table-center">{labels.colUtilPct}</th>
            </tr>
          </thead>
          <tbody>
            {(byHc.data || []).map((r) => (
              <tr key={r.high_court}>
                <td className="font-medium text-slate-700">{r.high_court}</td>
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

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList
          data-testid="dashboard-tabs"
          className="dashboard-tab-list w-full justify-start h-auto"
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
          <RagDeltaWidget reportingPeriod={period} />
          <DashboardAiInsights reportingPeriod={period} />
        </TabsContent>

        <TabsContent value="rag-trends" className="mt-5 space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {ragDonut}
            <Card title={labels.progressTrend} elevated>
              <TrendChart trendData={trend.data} />
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="geographic" className="mt-5 space-y-5">
          <IndiaChoropleth reportingPeriod={period} />
          <ComponentHcHeatmap reportingPeriod={period} />
        </TabsContent>

        <TabsContent value="performance" className="mt-5 space-y-5">
          <ParetoChart reportingPeriod={period} />
          {componentBars}
          {hcBars}
        </TabsContent>

        <TabsContent value="financial-tracker" className="mt-5">
          <FinancialTrackerDashboardTab reportingPeriod={period} labels={labels} />
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
