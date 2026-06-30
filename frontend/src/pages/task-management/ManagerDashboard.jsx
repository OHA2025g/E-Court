import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { useTaskLabels } from "@/lib/useTaskLabels";
import Card from "@/components/Card";
import { TaskKpiGrid, TaskTable } from "@/components/task-management/TaskManagementLayout";
import TaskCreateDialog from "@/components/task-management/TaskCreateDialog";
import { Plus } from "@phosphor-icons/react";

export default function ManagerDashboard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const l = useTaskLabels();
  const { data, isLoading } = useQuery({ queryKey: ["tm-manager-dash"], queryFn: taskApi.managerDashboard });
  const [createOpen, setCreateOpen] = useState(false);
  const s = data?.stats || {};

  const kpis = [
    { label: l.manager.kpiTotal, value: s.total, onClick: () => navigate("/task-management/tasks") },
    { label: l.manager.kpiUnassigned, value: s.unassigned, accent: "border-l-amber-500", onClick: () => navigate("/task-management/tasks?status=UNASSIGNED") },
    { label: l.manager.kpiInProgress, value: s.in_progress, onClick: () => navigate("/task-management/tasks?status=IN_PROGRESS") },
    { label: l.manager.kpiSubmitted, value: s.submitted_approval, accent: "border-l-violet-500" },
    { label: l.manager.kpiSlaBreached, value: s.sla_breached, accent: "border-l-red-500" },
    { label: l.manager.kpiHighPriority, value: s.high_priority_open, accent: "border-l-red-500" },
    { label: l.manager.kpiManagerPending, value: s.manager_approval_pending, accent: "border-l-violet-500" },
    { label: l.manager.kpiClosedMonth, value: s.closed_this_month, accent: "border-l-emerald-500" },
  ];

  if (isLoading) return <div className="text-slate-500">{l.manager.loading}</div>;

  return (
    <div data-testid="tm-manager-root">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-xl font-semibold text-slate-900">{l.manager.title}</h1>
          <p className="text-sm text-slate-500 mt-1">{l.manager.subtitle}</p>
        </div>
        <button type="button" data-testid="tm-create-task" onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-2 bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
          <Plus size={16} /> {l.common.createTask}
        </button>
      </div>
      <TaskKpiGrid items={kpis} />
      <div className="grid lg:grid-cols-2 gap-6">
        <Card title={l.manager.pendingApproval} subtitle={l.manager.pendingApprovalSub}>
          <TaskTable rows={data?.pending_approval} onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)} />
        </Card>
        <Card title={l.manager.unassignedPool} subtitle={l.manager.unassignedPoolSub}>
          <TaskTable rows={data?.unassigned} onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)} />
        </Card>
        <Card title={l.manager.escalations} subtitle={l.manager.escalationsSub} className="lg:col-span-2">
          <TaskTable rows={data?.escalated} onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)} />
        </Card>
        <Card title={l.manager.byModule} subtitle={l.manager.byModuleSub} className="lg:col-span-2">
          <div className="p-4 flex flex-wrap gap-3">
            {(s.by_module || []).map((m) => (
              <button key={m.key} type="button"
                onClick={() => navigate(`/task-management/tasks?module_name=${encodeURIComponent(m.key)}`)}
                className="px-4 py-2 border border-slate-200 rounded-sm hover:border-[#003B73] text-sm">
                {m.key}: <strong>{m.count}</strong>
              </button>
            ))}
          </div>
        </Card>
      </div>
      <TaskCreateDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={() => qc.invalidateQueries({ queryKey: ["tm-manager-dash"] })} />
    </div>
  );
}
