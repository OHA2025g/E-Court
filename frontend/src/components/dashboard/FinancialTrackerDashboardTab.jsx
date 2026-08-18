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
  if (!name) return "-";
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
    <div className="flex flex-col items-center gap-4 min-h-[240px]">
      <div className="relative mx-auto w-[200px] h-[200px] shrink-0">
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

      <ScrollRegion className="w-full max-w-sm max-h-[160px] overflow-y-auto" label={valueLabel}>
        <ul className="space-y-2 py-1">
          {slices.map((slice, i) => {
            const pct = total > 0 ? ((slice.value / total) * 100).toFixed(1) : "0.0";
            return (
              <li key={slice.name} className="flex items-start justify-center gap-2 text-xs">
                <span
                  className="mt-1 inline-block w-2.5 h-2.5 rounded-sm shrink-0 border border-white shadow-sm"
                  style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <div className="min-w-0 text-center">
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

const HC_COMP_SLICE = 6;

function SliceToggleButton({ view, setView, topLabel, bottomLabel }) {
  return (
    <button
      type="button"
      onClick={() => setView((v) => (v === "top" ? "bottom" : "top"))}
      className="px-2.5 py-1 rounded-sm border border-[#003B73] bg-[#003B73] text-white text-[10px] uppercase tracking-wider"
      title={view === "top" ? `Switch to ${bottomLabel}` : `Switch to ${topLabel}`}
      aria-label={
        view === "top"
          ? `Showing ${topLabel}. Switch to ${bottomLabel}`
          : `Showing ${bottomLabel}. Switch to ${topLabel}`
      }
    >
      {view === "top" ? topLabel : bottomLabel}
    </button>
  );
}

/** Pick top N or bottom N names from a desc-ranked list. */
function sliceRankedNames(rankedNames, view, n) {
  const list = rankedNames || [];
  if (list.length <= n) return list;
  if (view === "bottom") return [...list.slice(-n)].reverse();
  return list.slice(0, n);
}

/** Join HC released + utilised into stacked rows: utilised (bottom) + remainder (top = released). */
function buildHcReleasedSplitRows(hcReleased, hcUtilized) {
  const utilByHc = new Map();
  (hcUtilized || []).forEach((row) => {
    if (row?.high_court) utilByHc.set(row.high_court, row.utilized);
  });

  return (hcReleased || [])
    .map((row) => {
      const released = Number(row.released) || 0;
      const rawUtil = utilByHc.has(row.high_court) ? Number(utilByHc.get(row.high_court)) : 0;
      const utilized = Number.isFinite(rawUtil) ? Math.max(0, rawUtil) : 0;
      const cappedUtil = Math.min(utilized, released);
      const unutilized = Math.max(0, released - cappedUtil);
      const utilPct = released > 0 ? (cappedUtil / released) * 100 : null;
      return {
        high_court: row.high_court,
        label: row.label || shortLabel(row.high_court, 16),
        released,
        utilized: cappedUtil,
        unutilized,
        util_pct: utilPct,
      };
    })
    .sort((a, b) => b.released - a.released);
}

function HcReleasedSplitTooltip({ active, payload, label, labels }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="font-semibold text-slate-800 mb-1.5">{row.high_court || label}</div>
      <div className="text-slate-700">
        {labels.ftLegendReleased}:{" "}
        <span className="font-semibold tabular-nums">{fmtNum(row.released)}</span>
      </div>
      <div className="text-slate-700">
        {labels.ftLegendUtilized}:{" "}
        <span className="font-semibold tabular-nums">{fmtNum(row.utilized)}</span>
      </div>
      <div className="text-slate-700">
        {labels.ftUtilPct}:{" "}
        <span className="font-semibold tabular-nums">{fmtPct(row.util_pct)}</span>
      </div>
    </div>
  );
}

function HcReleasedSplitLegend({ labels }) {
  const items = [
    { key: "released", label: labels.ftLegendReleased, color: "#22c55e" },
    { key: "utilized", label: labels.ftLegendUtilized, color: "#003B73" },
  ];
  return (
    <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1.5 pt-2 text-[11px]">
      {items.map((item) => (
        <li key={item.key} className="inline-flex items-center gap-1.5 text-slate-600">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm shrink-0 border border-white shadow-sm"
            style={{ background: item.color }}
          />
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

/** Full component names - Recharts Legend + shortLabel was clipping e.g. Cloud Computing & Storage. */
function ComponentSeriesLegend({ names }) {
  if (!names?.length) return null;
  return (
    <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1.5 px-1 pt-2 text-[11px] leading-snug">
      {names.map((name, i) => (
        <li key={name} className="inline-flex items-start gap-1.5 max-w-full text-slate-600">
          <span
            className="mt-0.5 inline-block w-2.5 h-2.5 rounded-sm shrink-0 border border-white shadow-sm"
            style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
          />
          <span className="whitespace-normal">{name}</span>
        </li>
      ))}
    </ul>
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

export default function FinancialTrackerDashboardTab({ reportingPeriod, highCourt = "", component = "", labels }) {
  const [hcCompView, setHcCompView] = useState("top");
  const filterParams = {
    ...(reportingPeriod ? { reporting_period: reportingPeriod } : {}),
    ...(highCourt ? { high_court: highCourt } : {}),
    ...(component ? { component } : {}),
  };
  const { data, isLoading } = useQuery({
    queryKey: ["dash-financial-tracker", filterParams],
    queryFn: () => api.get("/dashboard/financial-tracker", { params: filterParams }).then(r => r.data),
  });

  const kpis = data?.kpis;
  const chartComponents = data?.chart_components || [];

  const hcReleasedSplitAll = useMemo(
    () => buildHcReleasedSplitRows(data?.hc_released, data?.hc_utilized),
    [data?.hc_released, data?.hc_utilized],
  );

  const hcSplitHint = hcReleasedSplitAll.length
    ? labels.ftHcReleasedSplitHintAll(hcReleasedSplitAll.length)
    : null;

  // Rank HCs by total funds released (desc) for Top/Bottom 6 component charts.
  const rankedHcByReleased = useMemo(
    () => (data?.hc_released || []).map((r) => r.high_court).filter(Boolean),
    [data?.hc_released],
  );

  const selectedCompHcs = useMemo(
    () => sliceRankedNames(rankedHcByReleased, hcCompView, HC_COMP_SLICE),
    [rankedHcByReleased, hcCompView],
  );

  const hcComponentReleasedRows = useMemo(() => {
    const byHc = new Map((data?.hc_component_released || []).map((r) => [r.high_court, r]));
    return selectedCompHcs.map((hc) => byHc.get(hc)).filter(Boolean);
  }, [data?.hc_component_released, selectedCompHcs]);

  const utilPctRowsForSlice = useMemo(() => {
    return (data?.utilization_by_component_hc || []).map((row) => {
      const next = { component: row.component };
      selectedCompHcs.forEach((hc) => {
        if (Object.prototype.hasOwnProperty.call(row, hc)) next[hc] = row[hc];
      });
      // Keep only components that have at least one value in the selected HC set.
      const hasVal = selectedCompHcs.some((hc) => next[hc] != null);
      return hasVal ? next : null;
    }).filter(Boolean);
  }, [data?.utilization_by_component_hc, selectedCompHcs]);

  const hcCompSliceHint = useMemo(() => {
    const n = selectedCompHcs.length;
    if (!n) return null;
    return hcCompView === "bottom"
      ? labels.ftHcCompSliceHintBottom(n)
      : labels.ftHcCompSliceHintTop(n);
  }, [selectedCompHcs.length, hcCompView, labels]);

  // Keep the smaller utilised×HC chart on top-6 by released to avoid overcrowding.
  const hcNamesUtilizedChart = useMemo(
    () => sliceRankedNames(rankedHcByReleased, "top", HC_COMP_SLICE),
    [rankedHcByReleased],
  );

  const hcComponentUtilizedRows = useMemo(() => {
    const selected = new Set(hcNamesUtilizedChart);
    return (data?.hc_component_utilized || []).filter((r) => selected.has(r.high_court));
  }, [data?.hc_component_utilized, hcNamesUtilizedChart]);

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
          value={fmtNum(kpis?.target, { digits: 2 })}
          accent="primary"
        />
        <KpiCard
          testId="ft-kpi-allocated"
          icon={Wallet}
          label={labels.ftAllocated}
          value={fmtNum(kpis?.allocated, { digits: 2 })}
          accent="amber"
        />
        <KpiCard
          testId="ft-kpi-released"
          icon={CurrencyInr}
          label={labels.ftReleased}
          value={fmtNum(kpis?.released, { digits: 2 })}
          accent="green"
        />
        <KpiCard
          testId="ft-kpi-utilized"
          icon={CurrencyInr}
          label={labels.ftUtilized}
          value={fmtNum(kpis?.utilized, { digits: 2 })}
          hint={labels.ftUtilPctHint(fmtPct(kpis?.utilisation_percent))}
          accent="slate"
        />
      </div>

      <Card
        title={labels.ftHcReleasedSplit}
        subtitle={hcSplitHint || undefined}
        elevated
      >
        <div className="h-[28rem] p-4">
          {hcReleasedSplitAll.length === 0 ? (
            <EmptyChart message={labels.noData} />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={hcReleasedSplitAll}
                margin={{ top: 8, right: 12, left: 0, bottom: 72 }}
                barCategoryGap="18%"
              >
                <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                <XAxis
                  dataKey="label"
                  stroke="#475569"
                  fontSize={9}
                  angle={-40}
                  textAnchor="end"
                  interval={0}
                  height={88}
                />
                <YAxis stroke="#475569" fontSize={11} />
                <Tooltip content={<HcReleasedSplitTooltip labels={labels} />} />
                <Legend content={<HcReleasedSplitLegend labels={labels} />} />
                <Bar
                  dataKey="utilized"
                  name={labels.ftLegendUtilized}
                  stackId="released"
                  fill="#003B73"
                  radius={[0, 0, 0, 0]}
                />
                <Bar
                  dataKey="unutilized"
                  name={labels.ftLegendReleased}
                  stackId="released"
                  fill="#22c55e"
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card
          title={labels.ftHcComponentReleased}
          subtitle={hcCompSliceHint || undefined}
          elevated
          action={
            <SliceToggleButton
              view={hcCompView}
              setView={setHcCompView}
              topLabel={labels.ftTop6}
              bottomLabel={labels.ftBottom6}
            />
          }
        >
          <div className="h-80 p-4 flex flex-col">
            {hcComponentReleasedRows.length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <>
                <div className="flex-1 min-h-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hcComponentReleasedRows} margin={{ top: 8, right: 12, left: 0, bottom: 56 }}>
                      <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                      <XAxis dataKey="label" stroke="#475569" fontSize={10} angle={-25} textAnchor="end" interval={0} height={70} />
                      <YAxis stroke="#475569" fontSize={11} />
                      <Tooltip formatter={(v) => fmtNum(v)} />
                      {chartComponents.map((comp, i) => (
                        <Bar key={comp} dataKey={comp} name={comp} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[2, 2, 0, 0]} />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <ComponentSeriesLegend names={chartComponents} />
              </>
            )}
          </div>
        </Card>

        <Card
          title={labels.ftUtilPctComponentHc}
          subtitle={hcCompSliceHint || undefined}
          elevated
          action={
            <SliceToggleButton
              view={hcCompView}
              setView={setHcCompView}
              topLabel={labels.ftTop6}
              bottomLabel={labels.ftBottom6}
            />
          }
        >
          <div className="h-80 p-4">
            {utilPctRowsForSlice.length === 0 || selectedCompHcs.length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <UtilPctComponentHcChart
                key={`${reportingPeriod || "all"}-${hcCompView}-${selectedCompHcs.join("|")}`}
                rows={utilPctRowsForSlice}
                hcNames={selectedCompHcs}
                utilPctLabel={labels.ftUtilPct}
              />
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title={labels.ftHcComponentUtilized} elevated>
          <div className="h-72 p-3 flex flex-col">
            {hcComponentUtilizedRows.length === 0 ? (
              <EmptyChart message={labels.noData} />
            ) : (
              <>
                <div className="flex-1 min-h-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hcComponentUtilizedRows} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                      <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                      <XAxis dataKey="label" stroke="#475569" fontSize={9} angle={-20} textAnchor="end" interval={0} height={56} />
                      <YAxis stroke="#475569" fontSize={10} />
                      <Tooltip formatter={(v) => fmtNum(v)} />
                      {chartComponents.slice(0, 3).map((comp, i) => (
                        <Bar key={comp} dataKey={comp} name={comp} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <ComponentSeriesLegend names={chartComponents.slice(0, 3)} />
              </>
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
      </div>
    </div>
  );
}
