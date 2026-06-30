import React from "react";
import { useQuery } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { useTaskLabels } from "@/lib/useTaskLabels";
import Card from "@/components/Card";

export default function TaskAdminConfig() {
  const l = useTaskLabels();
  const { data } = useQuery({ queryKey: ["tasks-meta"], queryFn: taskApi.meta });

  return (
    <div>
      <h1 className="font-display text-xl font-semibold text-slate-900 mb-2">{l.config.title}</h1>
      <p className="text-sm text-slate-500 mb-6">{l.config.subtitle}</p>
      <div className="grid md:grid-cols-2 gap-6">
        <Card title={l.config.slaHours}>
          <ul className="p-4 text-sm space-y-1">
            {Object.entries(data?.default_sla_hours || {}).map(([k, v]) => (
              <li key={k} className="flex justify-between"><span>{k}</span><strong>{v}h</strong></li>
            ))}
          </ul>
        </Card>
        <Card title={l.config.categories}>
          <ul className="p-4 text-sm space-y-1">
            {(data?.categories || []).map((c) => <li key={c}>{c}</li>)}
          </ul>
        </Card>
        <Card title={l.config.teamsDepartments}>
          <ul className="p-4 text-sm space-y-1 max-h-64 overflow-y-auto">
            {(data?.associated_teams || []).map((opt) => (
              <li key={opt.value}>{opt.label}</li>
            ))}
          </ul>
          <p className="px-4 pb-4 text-xs text-slate-500">{l.config.teamsDepartmentsHint}</p>
        </Card>
        <Card title={l.config.apiConfig} className="md:col-span-2">
          <p className="p-4 text-sm text-slate-600">
            {l.config.apiHint}
          </p>
        </Card>
      </div>
    </div>
  );
}
