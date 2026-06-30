import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAdminLabels } from "@/lib/useAdminLabels";
import Card from "@/components/Card";
import RagBadge from "@/components/RagBadge";
import { TID } from "@/lib/testIds";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, PencilSimple, Trash, ClockCounterClockwise } from "@phosphor-icons/react";
import { toast } from "sonner";
import { SelectField, TextField } from "@/pages/PhysicalTracker";
import FileAttachments from "@/components/FileAttachments";

const PRIORITIES = ["Critical", "High", "Medium", "Low"];
const STATUSES = ["Open", "In Progress", "Completed", "Overdue"];

function priorityColor(p) {
  return p === "Critical" ? "bg-red-100 text-red-700 border-red-300"
    : p === "High" ? "bg-amber-100 text-amber-800 border-amber-300"
    : p === "Medium" ? "bg-sky-100 text-sky-700 border-sky-300"
    : "bg-slate-100 text-slate-600 border-slate-300";
}
function statusColor(s) {
  return s === "Completed" ? "GREEN" : s === "In Progress" ? "AMBER" : s === "Overdue" ? "RED" : "NA";
}

function TaskDialog({ open, onOpenChange, task, onSaved }) {
  const { pmu: l, save, saving, saved } = useAdminLabels();
  const isEdit = !!task;
  const [form, setForm] = useState(() => task || { title: "", owner: "", priority: "Medium", status: "Open", due_date: "", description: "", stakeholder: "", comments: "", attachments: [] });
  React.useEffect(() => { if (task) setForm({ attachments: [], ...task }); else setForm({ title: "", owner: "", priority: "Medium", status: "Open", due_date: "", description: "", stakeholder: "", comments: "", attachments: [] }); }, [task, open]);
  const [busy, setBusy] = useState(false);
  async function saveTask() {
    if (!form.title) { toast.error(l.titleRequired); return; }
    setBusy(true);
    try {
      if (isEdit) await api.put(`/pmu-tasks/${task.id}`, form);
      else await api.post("/pmu-tasks", form);
      toast.success(saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader><DialogTitle>{isEdit ? l.editTask : l.createTask}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="sm:col-span-2"><TextField label={l.fieldTitle} value={form.title} onChange={(v) => setForm(f => ({ ...f, title: v }))} /></div>
          <TextField label={l.fieldOwner} value={form.owner || ""} onChange={(v) => setForm(f => ({ ...f, owner: v }))} />
          <TextField label={l.fieldStakeholder} value={form.stakeholder || ""} onChange={(v) => setForm(f => ({ ...f, stakeholder: v }))} />
          <SelectField label={l.fieldPriority} value={form.priority} onChange={(v) => setForm(f => ({ ...f, priority: v }))} options={PRIORITIES} />
          <SelectField label={l.fieldStatus} value={form.status} onChange={(v) => setForm(f => ({ ...f, status: v }))} options={STATUSES} />
          <label className="block sm:col-span-2">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.fieldDueDate}</span>
            <input type="date" value={form.due_date || ""} onChange={(e) => setForm(f => ({ ...f, due_date: e.target.value }))}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm focus:outline-none focus:border-[#003B73]" />
          </label>
          <div className="sm:col-span-2"><TextField label={l.fieldDescription} value={form.description || ""} onChange={(v) => setForm(f => ({ ...f, description: v }))} /></div>
          <div className="sm:col-span-2"><TextField label={l.fieldComments} value={form.comments || ""} onChange={(v) => setForm(f => ({ ...f, comments: v }))} /></div>
          <div className="sm:col-span-2">
            <FileAttachments value={form.attachments || []} onChange={(ids) => setForm(f => ({ ...f, attachments: ids }))} />
          </div>
        </div>
        <DialogFooter>
          <button onClick={saveTask} disabled={busy} className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
            {busy ? saving : save}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function PmuTasks() {
  const { pmu: l, edit, delete: delLabel, deleted } = useAdminLabels();
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["tasks"], queryFn: () => api.get("/pmu-tasks").then(r => r.data) });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const buckets = {
    Open: [], "In Progress": [], Completed: [], Overdue: [],
  };
  (data || []).forEach(t => buckets[t.status]?.push(t));

  async function del(id) {
    if (!window.confirm(l.deleteConfirm)) return;
    try { await api.delete(`/pmu-tasks/${id}`); toast.success(deleted); qc.invalidateQueries({ queryKey: ["tasks"] }); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  }

  const canEdit = user?.role === "Admin";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-slate-900">{l.title}</h2>
          <p className="text-xs text-slate-500">{l.subtitle}</p>
        </div>
        {canEdit && (
          <button data-testid={TID.pmuCreateBtn} onClick={() => { setEditing(null); setDialogOpen(true); }}
            className="bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <Plus size={16} /> {l.newTask}
          </button>
        )}
      </div>

      <div data-testid={TID.pmuList} className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4">
        {Object.entries(buckets).map(([k, items]) => (
          <Card key={k} title={l.bucketCount(k, items.length)} subtitle="">
            <div className="p-3 space-y-2">
              {items.length === 0 && <div className="text-xs text-slate-400 px-1 py-3">{l.noTasks}</div>}
              {items.map(t => (
                <div key={t.id} className="border border-slate-200 rounded-sm p-3 bg-white hover:border-[#003B73] transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-sm font-medium text-slate-900 leading-snug flex-1">{t.title}</div>
                    <RagBadge status={statusColor(t.status)} label={t.status} />
                  </div>
                  {t.description && <p className="text-xs text-slate-500 mt-1 line-clamp-3">{t.description}</p>}
                  <div className="mt-2 flex items-center justify-between text-[11px]">
                    <span className={`inline-flex px-2 py-0.5 rounded-sm border ${priorityColor(t.priority)}`}>{t.priority}</span>
                    <span className="text-slate-500 inline-flex items-center gap-1"><ClockCounterClockwise size={12} /> {t.due_date || "—"}</span>
                  </div>
                  <div className="mt-2 text-[11px] text-slate-500">{l.ownerLabel(t.owner)}</div>
                  {(t.attachments?.length || 0) > 0 && (
                    <div className="mt-1 inline-flex items-center gap-1 text-[10px] text-slate-500">
                      <span>{l.attachments(t.attachments.length)}</span>
                    </div>
                  )}
                  {canEdit && (
                    <div className="mt-3 flex gap-2">
                      <button onClick={() => { setEditing(t); setDialogOpen(true); }} className="text-xs text-slate-600 hover:text-[#003B73] inline-flex items-center gap-1"><PencilSimple size={12} /> {edit}</button>
                      <button onClick={() => del(t.id)} className="text-xs text-red-600 hover:text-red-800 inline-flex items-center gap-1"><Trash size={12} /> {delLabel}</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      <TaskDialog open={dialogOpen} onOpenChange={setDialogOpen} task={editing} onSaved={() => qc.invalidateQueries({ queryKey: ["tasks"] })} />
    </div>
  );
}
