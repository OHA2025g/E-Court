import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { useTaskLabels } from "@/lib/useTaskLabels";
import Card from "@/components/Card";
import { TaskKpiGrid, TaskTable } from "@/components/task-management/TaskManagementLayout";
import TaskCreateDialog from "@/components/task-management/TaskCreateDialog";
import { Plus } from "@phosphor-icons/react";

export default function TeamLeadDashboard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const l = useTaskLabels();
  const { data, isLoading } = useQuery({ queryKey: ["tm-lead-dash"], queryFn: taskApi.teamLeadDashboard });
  const [createOpen, setCreateOpen] = useState(false);
  const s = data?.stats || {};

  const kpis = [
    { label: l.lead.kpiReceived, value: s.tasks_received },
    { label: l.lead.kpiPendingDist, value: s.pending_distribution },
    { label: l.lead.kpiAssigned, value: s.assigned_members },
    { label: l.lead.kpiInProgress, value: s.in_progress },
    { label: l.lead.kpiSubmitted, value: s.submitted_approval, accent: "border-l-violet-500" },
    { label: l.lead.kpiRework, value: s.rework_required, accent: "border-l-orange-500" },
    { label: l.lead.kpiSlaRisk, value: s.sla_risk, accent: "border-l-amber-500" },
    { label: l.lead.kpiProposed, value: (data?.proposed || []).length },
  ];

  if (isLoading) return <div className="text-slate-500">{l.lead.loading}</div>;

  return (
    <div data-testid="tm-lead-root">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-xl font-semibold text-slate-900">{l.lead.title}</h1>
          <p className="text-sm text-slate-500 mt-1">{l.lead.subtitle}</p>
        </div>
        <button type="button" onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-2 bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
          <Plus size={16} /> {l.common.createTask}
        </button>
      </div>
      <TaskKpiGrid items={kpis} />
      <div className="grid lg:grid-cols-2 gap-6">
        <Card title={l.lead.submittedCard} subtitle={l.lead.submittedCardSub}>
          <TaskTable rows={data?.submitted} onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)} />
        </Card>
        <Card title={l.lead.proposedCard} subtitle={l.lead.proposedCardSub}>
          <TaskTable rows={data?.proposed} onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)} />
        </Card>
      </div>
      <TaskCreateDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={() => qc.invalidateQueries({ queryKey: ["tm-lead-dash"] })} />
    </div>
  );
}
