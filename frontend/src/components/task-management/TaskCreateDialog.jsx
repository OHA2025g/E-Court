import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { taskPermissions } from "@/lib/taskPermissions";
import { useAuth } from "@/lib/auth";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { formatApiError } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { SelectField, TextField } from "@/pages/PhysicalTracker";
import { toast } from "sonner";

const PRIORITIES = ["Critical", "High", "Medium", "Low"];

export default function TaskCreateDialog({ open, onOpenChange, onCreated, parentTaskId }) {
  const { user } = useAuth();
  const l = useTaskLabels();
  const perms = taskPermissions(user);
  const meta = useQuery({ queryKey: ["tasks-meta"], queryFn: taskApi.meta, enabled: open });
  const assignableLead = useQuery({
    queryKey: ["assignable-lead"],
    queryFn: () => taskApi.assignableUsers("team_lead"),
    enabled: open && perms.canAssignLead,
  });
  const assignableMember = useQuery({
    queryKey: ["assignable-member"],
    queryFn: () => taskApi.assignableUsers("team_member"),
    enabled: open && perms.canAssignMember,
  });

  const [form, setForm] = useState({
    title: "", description: "", category: "", module_name: "", project_name: "",
    department_name: "", priority: "Medium", due_date: "", evidence_required: false,
    manager_final_approval_required: false, assigned_team_lead_id: "", assigned_team_member_id: "",
    source_type: "", instructions: "", attachments: [],
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm({
      title: "", description: "", category: meta.data?.categories?.[0] || "Project Execution",
      module_name: "", project_name: "", department_name: "", priority: "Medium", due_date: "",
      evidence_required: false, manager_final_approval_required: false,
      assigned_team_lead_id: "", assigned_team_member_id: "", source_type: "",
      instructions: "", attachments: [], parent_task_id: parentTaskId || "",
    });
  }, [open, parentTaskId, meta.data]);

  async function save() {
    if (!form.title.trim()) { toast.error(l.create.titleRequired); return; }
    setBusy(true);
    try {
      const body = { ...form, parent_task_id: parentTaskId || undefined };
      if (!body.assigned_team_lead_id) delete body.assigned_team_lead_id;
      if (!body.assigned_team_member_id) delete body.assigned_team_member_id;
      if (body.priority === "Critical") body.manager_final_approval_required = true;
      const task = await taskApi.create(body);
      toast.success(l.create.created(task.task_code));
      onCreated?.(task);
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  const categories = meta.data?.categories || PRIORITIES;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{l.create.title}</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="sm:col-span-2">
            <TextField label={l.create.titleField} value={form.title} onChange={(v) => setForm((f) => ({ ...f, title: v }))} testid="tm-task-title" />
          </div>
          <div className="sm:col-span-2">
            <TextField label={l.create.descriptionField} value={form.description} onChange={(v) => setForm((f) => ({ ...f, description: v }))} testid="tm-task-description" />
          </div>
          <SelectField label={l.create.category} value={form.category} onChange={(v) => setForm((f) => ({ ...f, category: v }))} options={categories} />
          <SelectField label={l.create.priority} value={form.priority} onChange={(v) => setForm((f) => ({ ...f, priority: v }))} options={PRIORITIES} />
          <TextField label={l.create.module} value={form.module_name} onChange={(v) => setForm((f) => ({ ...f, module_name: v }))} />
          <TextField label={l.create.project} value={form.project_name} onChange={(v) => setForm((f) => ({ ...f, project_name: v }))} />
          <TextField label={l.create.department} value={form.department_name} onChange={(v) => setForm((f) => ({ ...f, department_name: v }))} />
          <label className="block">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.create.dueDate}</span>
            <input type="date" value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm focus:outline-none focus:border-[#003B73]" />
          </label>
          {perms.canAssignLead && (
            <label className="block sm:col-span-2">
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.create.assignLead}</span>
              <select value={form.assigned_team_lead_id} onChange={(e) => setForm((f) => ({ ...f, assigned_team_lead_id: e.target.value }))}
                className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm">
                <option value="">{l.common.select}</option>
                {(assignableLead.data || []).map((u) => (
                  <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                ))}
              </select>
            </label>
          )}
          {perms.canAssignMember && (
            <label className="block sm:col-span-2">
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.create.assignMember}</span>
              <select value={form.assigned_team_member_id} onChange={(e) => setForm((f) => ({ ...f, assigned_team_member_id: e.target.value }))}
                className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm">
                <option value="">{l.common.select}</option>
                {(assignableMember.data || []).map((u) => (
                  <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                ))}
              </select>
            </label>
          )}
          <div className="sm:col-span-2 flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" data-testid="tm-task-evidence-required" checked={form.evidence_required} onChange={(e) => setForm((f) => ({ ...f, evidence_required: e.target.checked }))} />
              {l.create.evidenceRequired}
            </label>
            {perms.canAssignLead && (
              <label className="flex items-center gap-2">
                <input type="checkbox" data-testid="tm-task-manager-approval" checked={form.manager_final_approval_required} onChange={(e) => setForm((f) => ({ ...f, manager_final_approval_required: e.target.checked }))} />
                {l.create.managerApproval}
              </label>
            )}
          </div>
          <div className="sm:col-span-2">
            <TextField label={l.create.instructions} value={form.instructions} onChange={(v) => setForm((f) => ({ ...f, instructions: v }))} />
          </div>
        </div>
        <DialogFooter>
          <button type="button" onClick={() => onOpenChange(false)} className="px-4 py-2 text-sm border border-slate-300 rounded-sm">{l.common.cancel}</button>
          <button type="button" onClick={save} disabled={busy} data-testid="tm-task-submit"
            className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
            {busy ? l.common.creating : l.common.createTask}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
