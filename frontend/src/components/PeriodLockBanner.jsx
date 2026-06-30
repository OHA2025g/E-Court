import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { Lock, WarningCircle } from "@phosphor-icons/react";

export default function PeriodLockBanner({ highCourt, reportingPeriod }) {
  const { t } = useTranslation();
  const status = useQuery({
    queryKey: ["period-status", highCourt, reportingPeriod],
    enabled: !!highCourt && !!reportingPeriod,
    queryFn: () =>
      api
        .get("/workflow/period-status", {
          params: { high_court: highCourt, reporting_period: reportingPeriod },
        })
        .then((r) => r.data),
  });

  if (!highCourt || !reportingPeriod || status.isLoading || !status.data) return null;
  const { editable, reason, submission_status, dashboard_excluded, grace_deadline } = status.data;
  if (editable && !dashboard_excluded) return null;

  const reasonLabel = t(`periodLock.${reason}`, {
    defaultValue: t("periodLock.lockedFallback", { reason }),
  });

  return (
    <div
      className="mb-4 rounded-sm border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 flex flex-wrap items-start gap-2"
      data-testid="period-lock-banner"
    >
      <Lock size={18} className="shrink-0 mt-0.5" />
      <div>
        {!editable && (
          <p className="font-semibold">{reasonLabel}</p>
        )}
        {dashboard_excluded && (
          <p className="flex items-center gap-1 mt-1 text-amber-800">
            <WarningCircle size={14} />
            {t("periodLock.dashboardExcluded")}
            {submission_status ? ` (status: ${submission_status})` : ""}
          </p>
        )}
        {grace_deadline && !editable && (
          <p className="text-xs text-amber-700 mt-1">
            {t("periodLock.graceDeadline", { date: grace_deadline.slice(0, 10) })}
          </p>
        )}
      </div>
    </div>
  );
}
