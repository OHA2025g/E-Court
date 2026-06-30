import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { taskPermissions } from "@/lib/taskPermissions";
import { useAuth } from "@/lib/auth";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";

/** Bulk assign / cancel for selected tasks on the list page. */
export default function TaskBulkActionsBar({ selectedIds, onClear, onDone }) {
  const { user } = useAuth();
  const l = useTaskLabels();
  const perms = taskPermissions(user);
  const [leadId, setLeadId] = useState("");
  const [memberId, setMemberId] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [busy, setBusy] = useState(false);

  const ids = [...selectedIds];
  const count = ids.length;

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

  if (count === 0) return null;

  async function runBulk(action, successKey) {
    setBusy(true);
    try {
      const result = await action();
      const ok = result.succeeded?.length || 0;
      const fail = result.failed?.length || 0;
      if (ok) toast.success(l.bulk[successKey](ok));
      if (fail) toast.error(l.bulk.partialFail(fail));
      onClear?.();
      onDone?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      data-testid="tm-bulk-bar"
      className="mb-4 p-4 border border-[#003B73]/30 bg-[#003B73]/5 rounded-sm flex flex-wrap items-end gap-3"
    >
      <div className="text-sm font-medium text-slate-800 mr-2">{l.bulk.selected(count)}</div>

      {perms.canAssignLead && (
        <>
          <label className="min-w-[200px] flex-1">
            <span className="text-xs text-slate-500">{l.assignment.teamLead}</span>
            <select
              value={leadId}
              onChange={(e) => setLeadId(e.target.value)}
              data-testid="tm-bulk-assign-lead"
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm"
            >
              <option value="">{l.common.select}</option>
              {(leads.data || []).map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !leadId}
            data-testid="tm-bulk-assign-lead-btn"
            onClick={() => runBulk(
              () => taskApi.bulkAssignLead(ids, leadId),
              "leadDone",
            )}
            className="bg-[#003B73] text-white px-3 py-2 rounded-sm text-xs uppercase tracking-wider disabled:opacity-50"
          >
            {l.bulk.assignLead}
          </button>
        </>
      )}

      {perms.canAssignMember && (
        <>
          <label className="min-w-[200px] flex-1">
            <span className="text-xs text-slate-500">{l.assignment.teamMember}</span>
            <select
              value={memberId}
              onChange={(e) => setMemberId(e.target.value)}
              data-testid="tm-bulk-assign-member"
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm"
            >
              <option value="">{l.common.select}</option>
              {(members.data || []).map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !memberId}
            data-testid="tm-bulk-assign-member-btn"
            onClick={() => runBulk(
              () => taskApi.bulkAssignMember(ids, memberId),
              "memberDone",
            )}
            className="bg-[#003B73] text-white px-3 py-2 rounded-sm text-xs uppercase tracking-wider disabled:opacity-50"
          >
            {l.bulk.assignMember}
          </button>
        </>
      )}

      {perms.canBulkCancel && (
        <>
          <label className="min-w-[200px] flex-1">
            <span className="text-xs text-slate-500">{l.bulk.cancelReason}</span>
            <input
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              data-testid="tm-bulk-cancel-reason"
              placeholder={l.bulk.cancelPlaceholder}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm text-sm"
            />
          </label>
          <button
            type="button"
            disabled={busy || !cancelReason.trim()}
            data-testid="tm-bulk-cancel-btn"
            onClick={() => runBulk(
              () => taskApi.bulkCancel(ids, cancelReason.trim()),
              "cancelDone",
            )}
            className="border border-red-300 text-red-700 px-3 py-2 rounded-sm text-xs uppercase tracking-wider disabled:opacity-50 hover:bg-red-50"
          >
            {l.bulk.cancel}
          </button>
        </>
      )}

      <button
        type="button"
        disabled={busy}
        onClick={onClear}
        data-testid="tm-bulk-clear"
        className="ml-auto px-3 py-2 text-sm text-slate-600 hover:text-slate-900"
      >
        {l.bulk.clear}
      </button>
    </div>
  );
}
