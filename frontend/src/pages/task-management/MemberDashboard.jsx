import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { useTaskLabels } from "@/lib/useTaskLabels";
import Card from "@/components/Card";
import { TaskKpiGrid, TaskTable } from "@/components/task-management/TaskManagementLayout";
import TaskCreateDialog from "@/components/task-management/TaskCreateDialog";
import { Plus } from "@phosphor-icons/react";

export default function MemberDashboard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const l = useTaskLabels();
  const { data, isLoading } = useQuery({ queryKey: ["tm-member-dash"], queryFn: taskApi.memberDashboard });
  const [createOpen, setCreateOpen] = useState(false);
  const s = data?.stats || {};

  const kpis = [
    { label: l.member.kpiOpen, value: s.my_open },
    { label: l.member.kpiDueToday, value: s.due_today, accent: "border-l-amber-500" },
    { label: l.member.kpiOverdue, value: s.overdue, accent: "border-l-red-500" },
    { label: l.member.kpiInProgress, value: s.in_progress },
    { label: l.member.kpiRework, value: s.rework_required, accent: "border-l-orange-500" },
    { label: l.member.kpiSubmitted, value: s.submitted_approval },
    { label: l.member.kpiProposed, value: s.proposed_by_me },
  ];

  if (isLoading) return <div className="text-slate-500">{l.member.loading}</div>;

  return (
    <div data-testid="tm-member-root">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-xl font-semibold text-slate-900">{l.member.title}</h1>
          <p className="text-sm text-slate-500 mt-1">{l.member.subtitle}</p>
        </div>
        <button type="button" onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-2 bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
          <Plus size={16} /> {l.common.createTask}
        </button>
      </div>
      <TaskKpiGrid items={kpis} />
      <Card title={l.member.recentCard} subtitle={l.member.recentCardSub}>
        <TaskTable rows={data?.recent} onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)} />
      </Card>
      <TaskCreateDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={() => qc.invalidateQueries({ queryKey: ["tm-member-dash"] })} />
    </div>
  );
}
