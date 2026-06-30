import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { BACKEND_URL, fmtPct } from "@/lib/api";
import {
  RAG_COLORS,
  formatRagLegendLabel,
  ragCellProps,
  ragSwatchClass,
  barSeriesProps,
  seriesLegendLabel,
  useAccessibleRag,
  RAG_SYMBOLS,
} from "@/lib/ragColors";
import PublicIndiaChoropleth from "@/components/PublicIndiaChoropleth";
import PwaInstallPrompt, { OfflineBanner } from "@/components/PwaInstallPrompt";
import ComponentHcHeatmap from "@/components/ComponentHcHeatmap";
import ParetoChart from "@/components/ParetoChart";
import TrendChart from "@/components/TrendChart";
import RagDeltaWidget from "@/components/RagDeltaWidget";
import Card from "@/components/Card";
import {
  Scales,
  SignIn,
  ChartLineUp,
  CurrencyInr,
  Target,
  MapTrifold,
  Medal,
  WarningCircle,
  ArrowRight,
} from "@phosphor-icons/react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from "recharts";

async function fetchPublicProgress() {
  const r = await fetch(`${BACKEND_URL}/api/public/progress`);
  if (!r.ok) throw new Error("Failed to load public progress");
  return r.json();
}

function hcBarData(states) {
  const byHc = {};
  Object.values(states || {}).forEach(s => {
    if (s?.high_court && s.percent != null && byHc[s.high_court] == null) {
      byHc[s.high_court] = { high_court: s.high_court, phys_percent: s.percent, rag: s.rag };
    }
  });
  return Object.values(byHc).sort((a, b) => b.phys_percent - a.phys_percent);
}

function outcomeBarData(top, bottom) {
  const byHc = {};
  [...(top || []), ...(bottom || [])].forEach(h => {
    if (h?.high_court && h.reporting_percent != null) {
      byHc[h.high_court] = h;
    }
  });
  return Object.values(byHc)
    .map(h => ({
      high_court: h.high_court,
      outcome_pct: h.reporting_percent,
      reported: h.reported_count,
      total: h.kpi_count,
    }))
    .sort((a, b) => b.outcome_pct - a.outcome_pct);
}

function ProgressRing({ percent, color, size = 72 }) {
  const value = Math.min(100, Math.max(0, Number(percent) || 0));
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90" aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
        style={{ transition: "stroke-dashoffset 0.6s ease" }}
      />
    </svg>
  );
}

function MetricHeroCard({ variant, label, value, hint, percent, Icon }) {
  const colors = {
    physical: { ring: "#003B73", valueClass: "public-metric-value--physical", iconClass: "public-metric-icon--physical" },
    financial: { ring: "#d97706", valueClass: "public-metric-value--financial", iconClass: "public-metric-icon--financial" },
    outcome: { ring: "#059669", valueClass: "public-metric-value--outcome", iconClass: "public-metric-icon--outcome" },
  };
  const c = colors[variant] || colors.physical;
  return (
    <div className={`public-metric-card public-metric-card--${variant}`}>
      <div className="flex items-start justify-between gap-3">
        <div className={`public-metric-icon ${c.iconClass}`}>
          <Icon size={22} weight="duotone" />
        </div>
        <ProgressRing percent={percent} color={c.ring} />
      </div>
      <div className="mt-4 text-[10px] uppercase tracking-[0.22em] text-slate-500 font-semibold">{label}</div>
      <div className={`public-metric-value ${c.valueClass} mt-1.5`}>{value}</div>
      <div className="text-xs text-slate-500 mt-2 leading-relaxed">{hint}</div>
    </div>
  );
}

function RagDistributionPanel({ title, subtitle, counts, accessibleRag, formatValue }) {
  const entries = Object.entries(counts || {}).filter(([, v]) => v > 0);
  const total = entries.reduce((sum, [, v]) => sum + v, 0) || 1;
  const order = ["GREEN", "AMBER", "RED", "NA"];
  const displayValue = (v) => (formatValue ? formatValue(v) : v);

  return (
    <div className="public-rag-panel h-full">
      <h2 className="public-section-title">{title}</h2>
      {subtitle && <p className="public-section-sub">{subtitle}</p>}
      <div className="public-rag-stack" role="img" aria-label={`${title}: ${total} total`}>
        {order.map(k => {
          const v = counts?.[k] || 0;
          if (v <= 0) return null;
          return (
            <div
              key={k}
              className="public-rag-stack-seg"
              style={{ width: `${(v / total) * 100}%`, background: RAG_COLORS[k] || RAG_COLORS.NA }}
              title={`${formatRagLegendLabel(k, accessibleRag)}: ${v}`}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        {order.map(k => {
          const v = counts?.[k];
          if (v == null) return null;
          return (
            <div key={k} className="public-rag-stat">
              <span
                className={`w-3 h-3 rounded-sm shrink-0 border border-slate-200 ${ragSwatchClass(k, accessibleRag)}`}
                style={{ background: RAG_COLORS[k] || RAG_COLORS.NA }}
                aria-hidden="true"
              />
              <div className="min-w-0">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">
                  {formatRagLegendLabel(k, accessibleRag)}
                </div>
                <div className="public-rag-stat-count">{displayValue(v)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RankList({ title, items, valueKey, accent, icon: Icon }) {
  const accentClass = {
    green: "public-rank-header--green",
    amber: "public-rank-header--amber",
    red: "public-rank-header--red",
  }[accent] || "public-rank-header--green";

  const barColor = {
    green: "#10b981",
    amber: "#f59e0b",
    red: "#ef4444",
  }[accent] || "#003B73";

  return (
    <div className="public-rank-card">
      <div className={`public-rank-header ${accentClass}`}>
        <div className="flex items-center gap-2">
          {Icon && <Icon size={18} weight="duotone" className="text-slate-600" />}
          <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        </div>
      </div>
      <ul>
        {(items || []).map((h, i) => {
          const pct = Number(h[valueKey]) || 0;
          return (
            <li key={h.high_court} className="public-rank-item">
              <span className={`public-rank-badge ${i < 3 ? `public-rank-badge--${i + 1}` : ""}`}>{i + 1}</span>
              <span className="flex-1 truncate text-slate-700">{h.high_court}</span>
              <div className="public-rank-bar" aria-hidden="true">
                <div className="public-rank-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
              </div>
              <span className="font-mono text-sm font-semibold text-slate-900 w-14 text-right">{fmtPct(h[valueKey])}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function PublicProgress() {
  const { t } = useTranslation();
  const [accessibleRag] = useAccessibleRag();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["public-progress"],
    queryFn: fetchPublicProgress,
    staleTime: 60_000,
  });

  const hcBars = useMemo(() => hcBarData(data?.states), [data?.states]);
  const outcomeBars = useMemo(
    () => outcomeBarData(data?.top_outcome_high_courts, data?.bottom_outcome_high_courts),
    [data?.top_outcome_high_courts, data?.bottom_outcome_high_courts],
  );

  const updatedLabel = data?.updated_at ? new Date(data.updated_at).toLocaleString() : null;

  return (
    <div className="public-page" data-testid="public-progress-root">
      <header className="public-hero">
        <div className="public-hero-inner">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="public-hero-badge mb-3">
                <Scales size={12} weight="fill" className="text-amber-300" />
                {t("public.subtitle")}
              </div>
              <h1 className="public-hero-title">{t("public.title")}</h1>
              <p className="public-hero-tagline">
                Real-time national aggregates across physical infrastructure, financial utilisation, and outcome KPIs — transparent progress for citizens and stakeholders.
              </p>
              {updatedLabel && (
                <p className="mt-3 text-xs text-white/50">
                  Last updated {updatedLabel}
                </p>
              )}
            </div>
            <Link
              to="/login"
              className="app-btn-primary shrink-0 self-start lg:self-center shadow-lg shadow-black/20"
            >
              <SignIn size={16} weight="bold" />
              {t("public.officialLogin")}
              <ArrowRight size={14} weight="bold" />
            </Link>
          </div>
        </div>
      </header>

      <main className="public-main space-y-8">
        <OfflineBanner />
        <PwaInstallPrompt />

        {isLoading && (
          <div className="public-loading">
            <div className="public-loading-spinner" aria-hidden="true" />
            <p>{t("public.loading")}</p>
          </div>
        )}

        {isError && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-700 flex items-center gap-3">
            <WarningCircle size={22} weight="duotone" />
            {t("public.loadError")}
          </div>
        )}

        {data && (
          <>
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-5 -mt-2 sm:-mt-6 relative z-10">
              <MetricHeroCard
                variant="physical"
                label={t("public.physicalProgress")}
                value={fmtPct(data.physical?.percent)}
                hint={t("public.physicalSubtitle")}
                percent={data.physical?.percent}
                Icon={ChartLineUp}
              />
              <MetricHeroCard
                variant="financial"
                label={t("public.financialUtilisation")}
                value={fmtPct(data.financial?.utilisation_percent)}
                hint={t("public.financialSubtitle")}
                percent={data.financial?.utilisation_percent}
                Icon={CurrencyInr}
              />
              <MetricHeroCard
                variant="outcome"
                label={t("public.outcomeReporting")}
                value={fmtPct(data.outcome?.reporting_percent)}
                hint={t("public.outcomeSubtitle", {
                  reported: data.outcome?.reported_count ?? 0,
                  total: data.outcome?.kpi_count ?? 0,
                })}
                percent={data.outcome?.reporting_percent}
                Icon={Target}
              />
            </section>

            <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <RagDistributionPanel
                title={t("public.ragDistribution")}
                counts={data.rag_physical}
                accessibleRag={accessibleRag}
              />
              <RagDistributionPanel
                title={t("public.hcRagStatus")}
                subtitle="High Courts grouped by aggregate RAG status"
                counts={data.hc_rag_counts}
                accessibleRag={accessibleRag}
                formatValue={(v) => t("public.hcCount", { count: v })}
              />
            </section>

            <section className="app-card overflow-hidden shadow-md shadow-slate-200/40">
              <header className="dashboard-ai-header px-6 py-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-white/80 text-xs uppercase tracking-[0.18em] mb-1">
                    <MapTrifold size={16} weight="duotone" />
                    Geographic view
                  </div>
                  <h2 className="font-display text-lg font-bold text-white">{t("public.indiaMapTitle")}</h2>
                  <p className="text-sm text-white/80 mt-1 max-w-xl">{t("public.indiaMapSubtitle")}</p>
                </div>
              </header>
              <div className="p-6 bg-gradient-to-b from-slate-50 to-white">
                <PublicIndiaChoropleth
                  states={data.states}
                  statesFinancial={data.viz?.states_financial}
                  statesOutcome={data.viz?.states_outcome}
                />
              </div>
            </section>

            {data.viz?.trend && (
              <section>
                <Card
                  title="National progress trend"
                  subtitle="Physical, financial, and outcome reporting over reporting periods"
                  accentHeader
                  elevated
                >
                  <div className="p-5">
                    <TrendChart trendData={data.viz.trend} />
                  </div>
                </Card>
              </section>
            )}

            {data.comparison_period && (
              <section>
                <RagDeltaWidget
                  publicMode
                  reportingPeriod={data.comparison_period}
                  embedData={data.viz?.rag_delta}
                />
              </section>
            )}

            {data.viz?.heatmap && (
              <section>
                <ComponentHcHeatmap publicMode embedData={data.viz.heatmap} />
              </section>
            )}

            {data.viz?.pareto && (
              <section className="app-card shadow-md shadow-slate-200/40 overflow-hidden">
                <ParetoChart publicMode embedData={data.viz.pareto} />
              </section>
            )}

            {hcBars.length > 0 && (
              <section className="app-card shadow-md shadow-slate-200/40 overflow-hidden">
                <header className="px-5 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
                  <h2 className="public-section-title">High Court physical progress</h2>
                  <p className="public-section-sub">Achievement percentage by High Court jurisdiction</p>
                </header>
                <div className="p-5 h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hcBars} margin={{ top: 8, right: 8, left: 0, bottom: 72 }}>
                      <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                      <XAxis dataKey="high_court" stroke="#475569" fontSize={9} angle={-35} textAnchor="end" interval={0} height={80} />
                      <YAxis stroke="#475569" fontSize={11} unit="%" domain={[0, 100]} />
                      <Tooltip formatter={(v, _n, item) => [
                        `${Number(v).toFixed(1)}%`,
                        accessibleRag
                          ? `${RAG_SYMBOLS[item.payload.rag] || RAG_SYMBOLS.NA} ${item.payload.rag || "NA"}`
                          : "Physical",
                      ]} />
                      <Bar dataKey="phys_percent" name={seriesLegendLabel("Physical %", "phys_percent", accessibleRag)}>
                        {hcBars.map(entry => (
                          <Cell key={entry.high_court} {...ragCellProps(entry.rag, accessibleRag)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            )}

            {outcomeBars.length > 0 && (
              <section className="app-card shadow-md shadow-slate-200/40 overflow-hidden">
                <header className="px-5 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
                  <h2 className="public-section-title">High Court outcome KPI reporting</h2>
                  <p className="public-section-sub">Share of KPIs reported per High Court</p>
                </header>
                <div className="p-5 h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={outcomeBars} margin={{ top: 8, right: 8, left: 0, bottom: 72 }}>
                      <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                      <XAxis dataKey="high_court" stroke="#475569" fontSize={9} angle={-35} textAnchor="end" interval={0} height={80} />
                      <YAxis stroke="#475569" fontSize={11} unit="%" domain={[0, 100]} />
                      <Tooltip formatter={(v, _n, item) => [
                        `${Number(v).toFixed(1)}% (${item.payload.reported}/${item.payload.total} KPIs)`,
                        "Reporting",
                      ]} />
                      <Bar
                        dataKey="outcome_pct"
                        name={seriesLegendLabel("Reporting %", "outcome_pct", accessibleRag)}
                        {...barSeriesProps("outcome_pct", accessibleRag)}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            )}

            <section>
              <h2 className="public-section-title mb-1">High Court performance snapshot</h2>
              <p className="public-section-sub mb-5">Top and bottom jurisdictions across physical, financial, and outcome metrics</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <RankList
                  title="Top performing High Courts"
                  items={data.top_high_courts}
                  valueKey="phys_percent"
                  accent="green"
                  icon={Medal}
                />
                <RankList
                  title="Needs attention"
                  items={data.bottom_high_courts}
                  valueKey="phys_percent"
                  accent="red"
                  icon={WarningCircle}
                />
                <RankList
                  title="Top financial utilisation (High Courts)"
                  items={data.top_financial_high_courts}
                  valueKey="fin_percent"
                  accent="amber"
                  icon={CurrencyInr}
                />
                <RankList
                  title="Low financial utilisation (High Courts)"
                  items={data.bottom_financial_high_courts}
                  valueKey="fin_percent"
                  accent="red"
                  icon={WarningCircle}
                />
                <RankList
                  title="Top outcome reporting (High Courts)"
                  items={data.top_outcome_high_courts}
                  valueKey="reporting_percent"
                  accent="green"
                  icon={Target}
                />
                <RankList
                  title="Low outcome reporting (High Courts)"
                  items={data.bottom_outcome_high_courts}
                  valueKey="reporting_percent"
                  accent="amber"
                  icon={WarningCircle}
                />
              </div>
            </section>

            <footer className="public-footer">
              {t("public.footer", {
                date: data.updated_at ? new Date(data.updated_at).toLocaleString() : "—",
              })}
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
