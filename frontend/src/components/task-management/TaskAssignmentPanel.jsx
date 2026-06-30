import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { taskPermissions } from "@/lib/taskPermissions";
import { useAuth } from "@/lib/auth";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";

/** Assign / reassign team lead or member on an existing task. */
export default function TaskAssignmentPanel({ taskId, task, onUpdated }) {
  const { user } = useAuth();
  const l = useTaskLabels();
  const perms = taskPermissions(user);
  const [leadId, setLeadId] = useState("");
  const [memberId, setMemberId] = useState("");
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState(false);

  const leads = useQuery({
    queryKey: ["assignable-lead"],
    queryFn: () => taskApi.assignableUsers("team_lead"),
    enabled: perms.canAssignLead,
  });
  const members = useQuery({
    queryKey: ["assignable-member"],
    queryFn: () => taskApi.assignableUsers("team_member"),
    enabled: perms.canAssignMember,
  });

  if (!perms.canAssignLead && !perms.canAssignMember) {
    return null;
  }

  async function assignLead() {
    if (!leadId) { toast.error(l.assignment.selectLead); return; }
    setBusy(true);
    try {
      await taskApi.assignLead(taskId, leadId, remarks);
      toast.success(l.assignment.leadAssigned);
      onUpdated?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  async function assignMember() {
    if (!memberId) { toast.error(l.assignment.selectMember); return; }
    setBusy(true);
    try {
      await taskApi.assignMember(taskId, memberId, remarks);
      toast.success(l.assignment.memberAssigned);
      onUpdated?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 p-4 border border-slate-200 rounded-sm bg-slate-50 space-y-3" data-testid="tm-assignment-panel">
      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.assignment.assignReassign}</div>
      {perms.canAssignLead && (
        <div className="flex flex-wrap gap-2 items-end">
          <label className="flex-1 min-w-[200px]">
            <span className="text-xs text-slate-500">{l.assignment.teamLead}</span>
            <select value={leadId} onChange={(e) => setLeadId(e.target.value)} data-testid="tm-assign-lead"
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm">
              <option value="">{l.common.select}</option>
              {(leads.data || []).map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
              ))}
            </select>
          </label>
          <button type="button" disabled={busy} onClick={assignLead} data-testid="tm-assign-lead-btn"
            className="bg-[#003B73] text-white px-3 py-2 rounded-sm text-xs uppercase tracking-wider disabled:opacity-50">
            {l.assignment.assignLeadBtn}
          </button>
        </div>
      )}
      {perms.canAssignMember && (
        <div className="flex flex-wrap gap-2 items-end">
          <label className="flex-1 min-w-[200px]">
            <span className="text-xs text-slate-500">{l.assignment.teamMember}</span>
            <select value={memberId} onChange={(e) => setMemberId(e.target.value)} data-testid="tm-assign-member"
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm">
              <option value="">{l.common.select}</option>
              {(members.data || []).map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
              ))}
            </select>
          </label>
          <button type="button" disabled={busy} onClick={assignMember} data-testid="tm-assign-member-btn"
            className="bg-[#003B73] text-white px-3 py-2 rounded-sm text-xs uppercase tracking-wider disabled:opacity-50">
            {l.assignment.assignMemberBtn}
          </button>
        </div>
      )}
      <label className="block">
        <span className="text-xs text-slate-500">{l.common.remarksOptional}</span>
        <input value={remarks} onChange={(e) => setRemarks(e.target.value)} data-testid="tm-assign-remarks"
          className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm text-sm" placeholder={l.common.assignmentNotes} />
      </label>
      {task?.assigned_team_lead_id && (
        <p className="text-xs text-slate-500">{l.assignment.currentLead(task.team_lead?.name || task.assigned_team_lead_id)}</p>
      )}
      {task?.assigned_team_member_id && (
        <p className="text-xs text-slate-500">{l.assignment.currentMember(task.team_member?.name || task.assigned_team_member_id)}</p>
      )}
    </div>
  );
}
