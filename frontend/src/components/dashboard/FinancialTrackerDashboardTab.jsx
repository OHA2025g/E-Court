import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { api, fmtNum, fmtPct } from "@/lib/api";
import Card, { KpiCard } from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import {
  CurrencyInr,
  Target,
  Wallet,
} from "@phosphor-icons/react";

const CHART_COLORS = ["#f59e0b", "#fb923c", "#ea580c", "#14b8a6", "#6366f1", "#ec4899", "#84cc16", "#64748b"];

function shortLabel(name, max = 18) {
  if (!name) return "—";
  return name.length <= max ? name : `${name.slice(0, max - 1)}…`;
}

function buildDonutSlices(items, valueKey = "utilized", topN = 5) {
  const sorted = [...(items || [])].sort((a, b) => (b[valueKey] || 0) - (a[valueKey] || 0));
  const top = sorted.slice(0, topN);
  const rest = sorted.slice(topN);
  const othersTotal = rest.reduce((sum, row) => sum + (row[valueKey] || 0), 0);
  const slices = top.map(row => ({
    name: row.component,
    value: row[valueKey] || 0,
  }));
  if (othersTotal > 0) {
    slices.push({ name: "Others", value: othersTotal, isOthers: true });
  }
  return { slices, total: sorted.reduce((sum, row) => sum + (row[valueKey] || 0), 0) };
}

function ComponentUtilDonut({ items, totalLabel, valueLabel }) {
  const { slices, total } = useMemo(() => buildDonutSlices(items), [items]);

  if (!slices.length) return null;

  return (
    <div className="flex flex-col sm:flex-row items-stretch gap-4 min-h-[240px]">
      <div className="relative mx-auto sm:mx-0 w-[200px] h-[200px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={58}
              outerRadius={82}
              paddingAngle={2}
              stroke="#fff"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((slice, i) => (
                <Cell key={slice.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(v) => [fmtNum(v), valueLabel]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center px-2">
            <div className="font-display text-xl font-bold text-slate-800 tabular-nums leading-tight">
              {fmtNum(total, { digits: 0 })}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-0.5">{totalLabel}</div>
          </div>
        </div>
      </div>

      <ScrollRegion className="flex-1 min-w-0 max-h-[220px] overflow-y-auto pr-1" label={valueLabel}>
        <ul className="space-y-2 py-1">
          {slices.map((slice, i) => {
            const pct = total > 0 ? ((slice.value / total) * 100).toFixed(1) : "0.0";
            return (
              <li key={slice.name} className="flex items-start gap-2 text-xs">
                <span
                  className="mt-1 inline-block w-2.5 h-2.5 rounded-sm shrink-0 border border-white shadow-sm"
                  style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <div className="min-w-0 flex-1">
                  <div className="text-slate-700 leading-snug" title={slice.name}>
                    {slice.name}
                  </div>
                  <div className="text-slate-500 tabular-nums mt-0.5">
                    {fmtNum(slice.value)} · {pct}%
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </ScrollRegion>
    </div>
  );
}

function EmptyChart({ message }) {
  return (
    <div className="h-full min-h-[220px] grid-bg flex items-center justify-center text-sm text-slate-400">
      {message}
    </div>
  );
}

function UtilPctComponentHcChart({ rows, hcNames, utilPctLabel }) {
  const [hiddenHc, setHiddenHc] = useState(() => new Set());

  const chartData = useMemo(
    () => rows.map(r => ({ ...r, component: shortLabel(r.component, 24) })),
    [rows],
  );

  const toggleHc = (hc) => {
    setHiddenHc(prev => {
      const next = new Set(prev);
      if (next.has(hc)) next.delete(hc);
      else next.add(hc);
      return next;
    });
  };

  const renderLegend = ({ payload }) => (
    <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1.5 pt-3 text-[11px]">
      {(payload || []).map((entry) => {
        const hc = entry.dataKey;
        const isHidden = hiddenHc.has(hc);
        return (
          <li key={hc}>
            <button
              type="button"
              onClick={() => toggleHc(hc)}
              className={[
                "inline-flex items-center gap-1.5 rounded-sm px-1 py-0.5 transition-opacity",
                isHidden ? "opacity-40 line-through" : "opacity-100 hover:opacity-80",
              ].join(" ")}
              aria-pressed={!isHidden}
              title={isHidden ? `Show ${entry.value}` : `Hide ${entry.value}`}
            >
              <span
                className="inline-block w-2.5 h-2.5 rounded-sm shrink-0 border border-white shadow-sm"
                style={{ background: entry.color }}
              />
              <span className="text-slate-600">{entry.value}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        layout="vertical"
        data={chartData}
        margin={{ top: 8, right: 24, left: 8, bottom: 4 }}
      >
        <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
        <XAxis type="number" stroke="#475569" fontSize={11} unit="%" domain={[0, 100]} />
        <YAxis type="category" dataKey="component" stroke="#475569" fontSize={10} width={120} />
        <Tooltip formatter={(v) => [fmtPct(v), utilPctLabel]} />
        <Legend content={renderLegend} />
        {hcNames.map((hc, i) => (
          <Bar
            key={hc}
            dataKey={hc}
            name={shortLabel(hc, 16)}
            fill={CHART_COLORS[i % CHART_COLORS.length]}
            radius={[0, 3, 3, 0]}
            hide={hiddenHc.has(hc)}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function FinancialTrackerDashboardTab({ reportingPeriod, labels }) {
  const { data, isLoading } = useQuery({
    queryKey: ["dash-financial-tracker", reportingPeriod],
    queryFn: () => api.get("/dashboard/financial-tracker", {
      params: reportingPeriod ? { reporting_period: reportingPeriod } : {},
    }).then(r => r.data),
  });

  const kpis = data?.kpis;
  const chartComponents = data?.chart_components || [];

  const hcNames = useMemo(() => {
    const names = new Set();
    (data?.utilization_by_component_hc || []).forEach(row => {
      Object.keys(row).forEach(k => {
        if (k !== "component") names.add(k);
      });
    });
    return [...names].slice(0, 6);
  }, [data]);

  const taskPieSlices = useMemo(
    () => buildDonutSlices(
      (data?.task_count_by_component || []).map(r => ({ component: r.component || "Unassigned", utilized: r.count })),
      "utilized",
      4,
    ),
    [data],
  );

  if (isLoading) {
    return <div className="text-sm text-slate-500 py-8 text-center">{labels.loading}</div>;
  }

  return (
    <div className="space-y-5" data-testid="financial-tracker-dashboard-tab">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard
          testId="ft-kpi-target"
          icon={Target}
          label={labels.ftTarget}
          value={fmtNum(kpis?.target)}
          accent="primary"
        />
        <KpiCard
          testId="ft-kpi-allocated"
          icon={Wallet}
          label={labels.ftAllocated}
          value={fmtNum(kpis?.allocated)}
          accent="amber"
        />
        <KpiCard
          testId="ft-kpi-released"
          icon={CurrencyInr}
          label={labels.ftReleased}
          value={fmtNum(kpis?.released)}
          accent="green"
        />
        <KpiCard
          testId="ft-kpi-utilized"
          icon={CurrencyInr}
          label={labels.ftUtilized}
          value={fmtNum(kpis?.utilized)}
          hint={labels.ftUtilPctHint(fmtPct(kpis?.utilisation_percent))}
          accent="slate"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title={labels.ftHcReleased} elevated>
          <div className="h-72 p-4">
            {(data?.hc_released || []).length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.hc_released} margin={{ top: 8, right: 12, left: 0, bottom: 56 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="label" stroke="#475569" fontSize={10} angle={-25} textAnchor="end" interval={0} height={70} />
                  <YAxis stroke="#475569" fontSize={11} />
                  <Tooltip formatter={(v) => [fmtNum(v), labels.ftReleasedShort]} />
                  <Bar dataKey="released" name={labels.ftReleasedShort} fill="#22c55e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card title={labels.ftHcUtilized} elevated>
          <div className="h-72 p-4">
            {(data?.hc_utilized || []).length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.hc_utilized} margin={{ top: 8, right: 12, left: 0, bottom: 56 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="label" stroke="#475569" fontSize={10} angle={-25} textAnchor="end" interval={0} height={70} />
                  <YAxis stroke="#475569" fontSize={11} />
                  <Tooltip formatter={(v) => [fmtNum(v), labels.ftUtilizedShort]} />
                  <Bar dataKey="utilized" name={labels.ftUtilizedShort} fill="#003B73" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title={labels.ftHcComponentReleased} elevated>
          <div className="h-80 p-4">
            {(data?.hc_component_released || []).length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.hc_component_released} margin={{ top: 8, right: 12, left: 0, bottom: 56 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="label" stroke="#475569" fontSize={10} angle={-25} textAnchor="end" interval={0} height={70} />
                  <YAxis stroke="#475569" fontSize={11} />
                  <Tooltip formatter={(v) => fmtNum(v)} />
                  <Legend formatter={(v) => shortLabel(v, 22)} />
                  {chartComponents.map((comp, i) => (
                    <Bar key={comp} dataKey={comp} name={comp} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[2, 2, 0, 0]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card title={labels.ftUtilPctComponentHc} elevated>
          <div className="h-80 p-4">
            {(data?.utilization_by_component_hc || []).length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <UtilPctComponentHcChart
                key={reportingPeriod || "all"}
                rows={data.utilization_by_component_hc}
                hcNames={hcNames}
                utilPctLabel={labels.ftUtilPct}
              />
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-5">
        <Card title={labels.ftTaskCountComponent} elevated>
          <div className="p-3">
            {taskPieSlices.slices.length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <div className="flex flex-col sm:flex-row items-stretch gap-4 min-h-[220px]">
                <div className="relative mx-auto sm:mx-0 w-[180px] h-[180px] shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={taskPieSlices.slices}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={78}
                        paddingAngle={2}
                        label={false}
                      >
                        {taskPieSlices.slices.map((_, i) => (
                          <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <ul className="flex-1 space-y-2 text-xs py-1">
                  {taskPieSlices.slices.map((slice, i) => (
                    <li key={slice.name} className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                      <span className="text-slate-700 truncate" title={slice.name}>{slice.name}</span>
                      <span className="ml-auto tabular-nums text-slate-600">{slice.value}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>

        <Card title={labels.ftHcComponentUtilized} elevated className="xl:col-span-1">
          <div className="h-64 p-3">
            {(data?.hc_component_utilized || []).length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.hc_component_utilized} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="label" stroke="#475569" fontSize={9} angle={-20} textAnchor="end" interval={0} height={56} />
                  <YAxis stroke="#475569" fontSize={10} />
                  <Tooltip formatter={(v) => fmtNum(v)} />
                  <Legend formatter={(v) => shortLabel(v, 18)} />
                  {chartComponents.slice(0, 3).map((comp, i) => (
                    <Bar key={comp} dataKey={comp} name={comp} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card title={labels.ftComponentUtilDonut} elevated>
          <div className="p-3">
            {(data?.component_utilization || []).length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <ComponentUtilDonut
                items={data.component_utilization}
                totalLabel="₹ Cr"
                valueLabel={labels.ftUtilizedShort}
              />
            )}
          </div>
        </Card>

        <Card title={labels.ftWeeklyTaskStatus} elevated>
          <div className="h-64 p-3">
            {(data?.weekly_task_status || []).length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.weekly_task_status} margin={{ top: 8, right: 8, left: 0, bottom: 36 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="week" stroke="#475569" fontSize={10} />
                  <YAxis stroke="#475569" fontSize={10} allowDecimals={false} />
                  <Tooltip
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.range || ""}
                  />
                  <Legend />
                  <Bar dataKey="created" name={labels.ftTaskCreated} fill="#3b82f6" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="completed" name={labels.ftTaskCompleted} fill="#ef4444" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="still_open" name={labels.ftTaskStillOpen} fill="#14b8a6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
