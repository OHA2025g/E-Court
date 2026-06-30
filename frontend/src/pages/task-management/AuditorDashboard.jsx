import React from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { useTaskLabels } from "@/lib/useTaskLabels";
import Card from "@/components/Card";
import { TaskKpiGrid, TaskTable } from "@/components/task-management/TaskManagementLayout";

/** Read-only auditor overview — organisation task metrics and recent activity. */
export default function AuditorDashboard() {
  const navigate = useNavigate();
  const l = useTaskLabels();
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["tm-reports"],
    queryFn: taskApi.reportSummary,
  });
  const { data: list, isLoading: listLoading } = useQuery({
    queryKey: ["tm-auditor-list"],
    queryFn: () => taskApi.list({ limit: 15 }),
  });

  if (summaryLoading) return <div className="text-slate-500">{l.auditor.loading}</div>;

  const s = summary || {};

  return (
    <div data-testid="tm-auditor-root">
      <div className="mb-6">
        <h1 className="font-display text-xl font-semibold text-slate-900">{l.auditor.title}</h1>
        <p className="text-sm text-slate-500 mt-1">{l.auditor.subtitle}</p>
      </div>
      <TaskKpiGrid items={[
        { label: l.reports.kpiTotal, value: s.total, onClick: () => navigate("/task-management/tasks") },
        { label: l.reports.kpiSlaBreached, value: s.sla_breached, accent: "border-l-red-500" },
        { label: l.reports.kpiPending, value: s.submitted_approval, accent: "border-l-violet-500" },
        { label: l.reports.kpiRework, value: s.rework_required, accent: "border-l-orange-500" },
        { label: l.reports.kpiEscalated, value: s.escalated, accent: "border-l-red-500" },
        { label: l.reports.kpiClosed, value: s.closed_this_month, accent: "border-l-emerald-500" },
      ]} />
      <div className="grid lg:grid-cols-2 gap-6">
        <Card title={l.reports.byStatus}>
          <ul className="p-4 space-y-1 text-sm">
            {(s.by_status || []).map((r) => (
              <li key={r.key} className="flex justify-between"><span>{r.key}</span><strong>{r.count}</strong></li>
            ))}
          </ul>
        </Card>
        <Card title={l.reports.byPriority}>
          <ul className="p-4 space-y-1 text-sm">
            {(s.by_priority || []).map((r) => (
              <li key={r.key} className="flex justify-between"><span>{r.key}</span><strong>{r.count}</strong></li>
            ))}
          </ul>
        </Card>
        <Card title={l.auditor.recentTasks} subtitle={l.auditor.recentTasksSub} className="lg:col-span-2">
          {listLoading ? (
            <div className="p-4 text-slate-500">{l.common.loading}</div>
          ) : (
            <TaskTable rows={list?.items} onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)} />
          )}
        </Card>
      </div>
    </div>
  );
}
