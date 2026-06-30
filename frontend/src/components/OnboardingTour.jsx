import React, { useCallback, useEffect, useState } from "react";
import { Joyride, STATUS, EVENTS } from "react-joyride";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";

const STEPS = [
  { target: "[data-tour='physical-tracker']", contentKey: "onboarding.welcome", placement: "center" },
  { target: "[data-testid='hc-select']", contentKey: "onboarding.filters", placement: "bottom" },
  { target: "[data-testid='save-btn']", contentKey: "onboarding.entry", placement: "top" },
  { target: "[data-testid='physical-table']", contentKey: "onboarding.table", placement: "top" },
  { target: "[data-tour='physical-tracker']", contentKey: "onboarding.done", placement: "center" },
];

export default function OnboardingTour({ enabled = true }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [run, setRun] = useState(false);

  const prefs = useQuery({
    queryKey: ["dashboard-prefs"],
    queryFn: () => api.get("/dashboard/prefs").then((r) => r.data),
    enabled,
  });

  useEffect(() => {
    if (enabled && prefs.data && !prefs.data.onboarding_complete) {
      const timer = setTimeout(() => setRun(true), 600);
      return () => clearTimeout(timer);
    }
  }, [enabled, prefs.data]);

  const steps = STEPS.map((s) => ({
    target: s.target,
    content: t(s.contentKey),
    placement: s.placement,
    skipBeacon: true,
  }));

  const finish = useCallback(async () => {
    setRun(false);
    try {
      await api.put("/dashboard/prefs", { onboarding_complete: true });
      qc.invalidateQueries({ queryKey: ["dashboard-prefs"] });
    } catch {
      /* best-effort */
    }
  }, [qc]);

  const onEvent = useCallback(
    (data) => {
      if (
        data.type === EVENTS.TOUR_END
        || data.status === STATUS.FINISHED
        || data.status === STATUS.SKIPPED
      ) {
        finish();
      }
    },
    [finish],
  );

  if (!enabled || prefs.isLoading || prefs.data?.onboarding_complete) return null;

  return (
    <Joyride
      steps={steps}
      run={run}
      continuous
      scrollToFirstStep
      onEvent={onEvent}
      options={{
        primaryColor: "#003B73",
        showProgress: true,
        skipBeacon: true,
        zIndex: 10000,
        buttons: ["back", "skip", "primary"],
      }}
      locale={{
        back: "Back",
        close: "Close",
        last: "Done",
        next: "Next",
        skip: "Skip tour",
      }}
    />
  );
}
