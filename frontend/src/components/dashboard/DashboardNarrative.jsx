import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TID } from "@/lib/testIds";
import { CheckCircle, ArrowsClockwise, Article } from "@phosphor-icons/react";
import { toast } from "sonner";

const STATUS_BADGE = {
  approved: "bg-emerald-100 text-emerald-800 border-emerald-300",
  draft: "bg-amber-100 text-amber-900 border-amber-300",
};

export function ExecutiveNarrativeSection({ reportingPeriod }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const isAdmin = user?.role === "Admin";

  const narrative = useQuery({
    queryKey: ["dash-narrative", reportingPeriod],
    queryFn: () => api.get("/dashboard/narrative", {
      params: reportingPeriod ? { reporting_period: reportingPeriod } : {},
    }).then((r) => r.data),
  });

  const status = narrative.data?.review_status || "draft";
  const requiresReview = narrative.data?.requires_review !== false;

  async function approve() {
    setBusy(true);
    try {
      await api.post("/admin/narrative/approve", {
        reporting_period: reportingPeriod || null,
        text: narrative.data?.draft_text || narrative.data?.narrative,
      });
      toast.success(t("dashboard.narrativeApproved"));
      qc.invalidateQueries({ queryKey: ["dash-narrative"] });
    } catch (e) {
      toast.error(e.response?.data?.detail || t("dashboard.narrativeApproveFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    setBusy(true);
    try {
      await api.post("/admin/narrative/regenerate", { reporting_period: reportingPeriod || null });
      toast.success(t("dashboard.narrativeRegenerated"));
      qc.invalidateQueries({ queryKey: ["dash-narrative"] });
    } catch (e) {
      toast.error(e.response?.data?.detail || t("dashboard.narrativeRegenerateFailed"));
    } finally {
      setBusy(false);
    }
  }

  const subtitle = narrative.data?.llm_enabled
    ? t("dashboard.narrativeSubtitleAi")
    : t("dashboard.narrativeSubtitle");

  return (
    <section
      data-testid={TID.dashboardNarrative}
      className="rounded-xl border border-slate-200/80 bg-white/90 p-4 sm:p-5 shadow-sm shadow-slate-200/40"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-slate-600 to-slate-800 text-white shadow-md">
            <Article size={20} weight="duotone" />
          </div>
          <div className="min-w-0">
            <h3 className="font-display text-sm font-semibold uppercase tracking-[0.1em] text-slate-800">
              {t("dashboard.narrativeTitle")}
            </h3>
            <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
          </div>
        </div>

        {isAdmin && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || status === "approved"}
              onClick={approve}
              data-testid="narrative-approve-btn"
              className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-3 py-1.5 border border-emerald-300 text-emerald-800 rounded-lg hover:bg-emerald-50 disabled:opacity-50 shadow-sm"
            >
              <CheckCircle size={12} /> {t("dashboard.narrativeApprove")}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={regenerate}
              data-testid="narrative-regenerate-btn"
              className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 shadow-sm"
            >
              <ArrowsClockwise size={12} /> {t("dashboard.narrativeRegenerate")}
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider mb-3">
        <span className={`inline-flex px-2.5 py-1 rounded-full border ${STATUS_BADGE[status] || STATUS_BADGE.draft}`}>
          {status === "approved" ? t("dashboard.narrativeStatusApproved") : t("dashboard.narrativeStatusDraft")}
        </span>
        {requiresReview && status !== "approved" && (
          <span className="text-slate-500 normal-case tracking-normal text-xs">
            {t("dashboard.narrativeCabinetHint")}
          </span>
        )}
        {narrative.data?.reviewed_by && status === "approved" && (
          <span className="text-slate-500 normal-case tracking-normal text-xs">
            {t("dashboard.narrativeReviewedBy", { name: narrative.data.reviewed_by })}
          </span>
        )}
      </div>

      <div
        className="rounded-xl border border-slate-100 bg-gradient-to-br from-slate-50 to-white p-4 sm:p-5 text-sm text-slate-700 leading-relaxed shadow-inner shadow-slate-100/50"
        role="region"
        aria-live="polite"
        aria-label={t("dashboard.narrativeTitle")}
      >
        {narrative.isLoading && <p className="text-slate-500">{t("dashboard.narrativeLoading")}</p>}
        {narrative.isError && <p className="text-red-600">{t("dashboard.narrativeError")}</p>}
        {!narrative.isLoading && narrative.data?.narrative && (
          <p>{narrative.data.narrative}</p>
        )}
      </div>
    </section>
  );
}

export default ExecutiveNarrativeSection;
