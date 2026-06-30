import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import { TID } from "@/lib/testIds";
import {
  ArrowsClockwise,
  Lightbulb,
  ListChecks,
  Target,
  ClipboardText,
  Sparkle,
  Robot,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { ExecutiveNarrativeSection } from "@/components/dashboard/DashboardNarrative";

const SECTION_THEMES = {
  insights: {
    icon: Lightbulb,
    gradient: "from-sky-500 to-blue-600",
    surface: "from-sky-50 to-white border-sky-100",
    badge: "bg-sky-100 text-sky-800",
    ring: "ring-sky-200",
  },
  recommendations: {
    icon: Target,
    gradient: "from-violet-500 to-purple-600",
    surface: "from-violet-50 to-white border-violet-100",
    badge: "bg-violet-100 text-violet-800",
    ring: "ring-violet-200",
  },
  actionItems: {
    icon: ListChecks,
    gradient: "from-amber-500 to-orange-500",
    surface: "from-amber-50 to-white border-amber-100",
    badge: "bg-amber-100 text-amber-900",
    ring: "ring-amber-200",
  },
  actionPlan: {
    icon: ClipboardText,
    gradient: "from-emerald-500 to-teal-600",
    surface: "from-emerald-50 to-white border-emerald-100",
    badge: "bg-emerald-100 text-emerald-800",
    ring: "ring-emerald-200",
  },
};

const PHASE_COLORS = ["bg-sky-600", "bg-violet-600", "bg-emerald-600"];

function LoadingSkeleton() {
  return (
    <div className="p-5 grid grid-cols-1 lg:grid-cols-2 gap-4 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-48 rounded-xl bg-slate-100/80 border border-slate-200" />
      ))}
    </div>
  );
}

function InsightItems({ items, emptyLabel, theme }) {
  if (!items?.length) {
    return <p className="text-slate-400 text-sm italic">{emptyLabel}</p>;
  }
  return (
    <ul className="space-y-3">
      {items.map((item, i) => (
        <li
          key={i}
          className="flex gap-3 rounded-lg bg-white/80 border border-white/60 p-3 shadow-sm shadow-slate-200/30"
        >
          <span className={`shrink-0 flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${theme.badge}`}>
            {i + 1}
          </span>
          <p className="text-sm text-slate-700 leading-relaxed pt-0.5">{item}</p>
        </li>
      ))}
    </ul>
  );
}

function SectionCard({ themeKey, title, children, testId }) {
  const theme = SECTION_THEMES[themeKey];
  const Icon = theme.icon;
  return (
    <div
      data-testid={testId}
      className={`relative h-full rounded-xl border bg-gradient-to-br ${theme.surface} p-4 shadow-sm shadow-slate-200/40 ring-1 ${theme.ring}`}
    >
      <div className="flex items-center gap-3 mb-4">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${theme.gradient} text-white shadow-md`}>
          <Icon size={20} weight="duotone" />
        </div>
        <h3 className="font-display text-sm font-semibold uppercase tracking-[0.1em] text-slate-800">{title}</h3>
      </div>
      <div>{children}</div>
    </div>
  );
}

export default function DashboardAiInsights({ reportingPeriod }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const isAdmin = user?.role === "Admin";

  const insights = useQuery({
    queryKey: ["dash-ai-insights", reportingPeriod],
    queryFn: () => api.get("/dashboard/ai-insights", {
      params: reportingPeriod ? { reporting_period: reportingPeriod } : {},
    }).then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

  async function refresh() {
    setRefreshing(true);
    try {
      await api.get("/dashboard/ai-insights", {
        params: {
          ...(reportingPeriod ? { reporting_period: reportingPeriod } : {}),
          refresh: true,
        },
      });
      await qc.invalidateQueries({ queryKey: ["dash-ai-insights", reportingPeriod] });
      toast.success(t("dashboard.aiInsightsRefreshed"));
    } catch (e) {
      toast.error(e.response?.data?.detail || t("dashboard.aiInsightsError"));
    } finally {
      setRefreshing(false);
    }
  }

  const isMistral = insights.data?.source === "mistral";
  const sourceLabel = isMistral
    ? t("dashboard.aiInsightsSourceMistral", { model: insights.data?.model || "Mistral" })
    : t("dashboard.aiInsightsSourceTemplate");

  return (
    <Card
      testId={TID.dashboardAiInsights}
      elevated
      className="border-0 shadow-lg shadow-blue-900/5"
      title={(
        <span className="inline-flex items-center gap-2">
          <Sparkle size={16} weight="fill" className="text-amber-300" />
          {t("dashboard.aiInsightsTitle")}
        </span>
      )}
      subtitle={sourceLabel}
      accentHeader
      action={(
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-[10px] uppercase tracking-wider text-white border border-white/30">
            <Robot size={14} weight="duotone" />
            {isMistral ? "Mistral AI" : "Smart summary"}
          </span>
          {isAdmin && (
            <button
              type="button"
              disabled={refreshing || insights.isLoading}
              onClick={refresh}
              data-testid="dashboard-ai-insights-refresh"
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/15 hover:bg-white/25 border border-white/25 px-3 py-1.5 text-[10px] uppercase tracking-wider text-white transition-colors disabled:opacity-50"
            >
              <ArrowsClockwise size={12} className={refreshing ? "animate-spin" : ""} />
              {t("dashboard.aiInsightsRefresh")}
            </button>
          )}
        </div>
      )}
    >
      <div className="p-5 bg-gradient-to-b from-slate-50/80 to-white space-y-5">
        <ExecutiveNarrativeSection reportingPeriod={reportingPeriod} />

        {insights.isLoading && <LoadingSkeleton />}
        {insights.isError && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg border border-red-100 p-4">{t("dashboard.aiInsightsError")}</p>
        )}
        {!insights.isLoading && insights.data && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <SectionCard
            themeKey="insights"
            title={t("dashboard.aiInsightsSectionInsights")}
            testId="dashboard-ai-insights-list"
          >
            <InsightItems
              items={insights.data.insights}
              emptyLabel={t("dashboard.aiInsightsEmpty")}
              theme={SECTION_THEMES.insights}
            />
          </SectionCard>

          <SectionCard
            themeKey="recommendations"
            title={t("dashboard.aiInsightsSectionRecommendations")}
            testId="dashboard-ai-recommendations-list"
          >
            <InsightItems
              items={insights.data.recommendations}
              emptyLabel={t("dashboard.aiInsightsEmpty")}
              theme={SECTION_THEMES.recommendations}
            />
          </SectionCard>

          <SectionCard
            themeKey="actionItems"
            title={t("dashboard.aiInsightsSectionActionItems")}
            testId="dashboard-ai-action-items-list"
          >
            <InsightItems
              items={insights.data.action_items}
              emptyLabel={t("dashboard.aiInsightsEmpty")}
              theme={SECTION_THEMES.actionItems}
            />
          </SectionCard>

          <SectionCard
            themeKey="actionPlan"
            title={t("dashboard.aiInsightsSectionActionPlan")}
            testId="dashboard-ai-action-plan"
          >
            {!insights.data.action_plan?.length ? (
              <p className="text-slate-400 text-sm italic">{t("dashboard.aiInsightsEmpty")}</p>
            ) : (
              <div className="space-y-4">
                {insights.data.action_plan.map((phase, i) => (
                  <div key={i} className="relative pl-6">
                    {i < insights.data.action_plan.length - 1 && (
                      <span className="absolute left-[11px] top-8 bottom-0 w-px bg-emerald-200" />
                    )}
                    <div className="absolute left-0 top-1 flex h-6 w-6 items-center justify-center rounded-full text-white text-[10px] font-bold shadow-sm">
                      <span className={`flex h-full w-full items-center justify-center rounded-full ${PHASE_COLORS[i] || PHASE_COLORS[2]}`}>
                        {i + 1}
                      </span>
                    </div>
                    <div className="rounded-lg bg-white/80 border border-white/70 p-3 shadow-sm">
                      <p className="text-[11px] uppercase tracking-wider font-semibold text-emerald-800 mb-2">
                        {phase.phase}
                      </p>
                      <ul className="space-y-2">
                        {(phase.actions || []).map((action, j) => (
                          <li key={j} className="flex gap-2 text-sm text-slate-700 leading-relaxed">
                            <span className="text-emerald-500 mt-1">▸</span>
                            <span>{action}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
          </div>
        )}
      </div>
    </Card>
  );
}
