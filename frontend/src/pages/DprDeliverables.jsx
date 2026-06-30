import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAdminLabels } from "@/lib/useAdminLabels";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import RagBadge from "@/components/RagBadge";
import { TID } from "@/lib/testIds";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, PencilSimple, Trash } from "@phosphor-icons/react";
import { toast } from "sonner";
import { SelectField, TextField } from "@/pages/PhysicalTracker";
import FileAttachments from "@/components/FileAttachments";

const STATUSES = ["Not Started", "In Progress", "Completed", "Delayed"];
const ragOf = (s) => s === "Completed" ? "GREEN" : s === "In Progress" ? "AMBER" : s === "Delayed" ? "RED" : "NA";

function DprDialog({ open, onOpenChange, item, onSaved }) {
  const { dpr: l, save, saving, saved } = useAdminLabels();
  const isEdit = !!item;
  const [form, setForm] = useState(() => item || { code: "", title: "", owner: "", target_date: "", actual_date: "", status: "Not Started", delay_reason: "", remarks: "", attachments: [] });
  React.useEffect(() => { setForm(item ? { attachments: [], ...item } : { code: "", title: "", owner: "", target_date: "", actual_date: "", status: "Not Started", delay_reason: "", remarks: "", attachments: [] }); }, [item, open]);
  const [busy, setBusy] = useState(false);
  async function saveItem() {
    if (!form.code || !form.title) { toast.error(l.codeTitleRequired); return; }
    setBusy(true);
    try {
      if (isEdit) await api.put(`/dpr/${item.id}`, form);
      else await api.post("/dpr", form);
      toast.success(saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader><DialogTitle>{isEdit ? l.editDeliverable : l.addDeliverable}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <TextField label={l.fieldCode} value={form.code} onChange={(v) => setForm(f => ({ ...f, code: v }))} disabled={isEdit} />
          <SelectField label={l.colStatus} value={form.status} onChange={(v) => setForm(f => ({ ...f, status: v }))} options={STATUSES} />
          <div className="sm:col-span-2"><TextField label={l.fieldTitle} value={form.title} onChange={(v) => setForm(f => ({ ...f, title: v }))} /></div>
          <TextField label={l.fieldOwner} value={form.owner || ""} onChange={(v) => setForm(f => ({ ...f, owner: v }))} />
          <label className="block">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.fieldTargetDate}</span>
            <input type="date" value={form.target_date || ""} onChange={(e) => setForm(f => ({ ...f, target_date: e.target.value }))}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm focus:outline-none focus:border-[#003B73]" />
          </label>
          <label className="block">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.fieldActualDate}</span>
            <input type="date" value={form.actual_date || ""} onChange={(e) => setForm(f => ({ ...f, actual_date: e.target.value }))}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm focus:outline-none focus:border-[#003B73]" />
          </label>
          <div className="sm:col-span-2"><TextField label={l.fieldDelayReason} value={form.delay_reason || ""} onChange={(v) => setForm(f => ({ ...f, delay_reason: v }))} /></div>
          <div className="sm:col-span-2"><TextField label={l.fieldRemarks} value={form.remarks || ""} onChange={(v) => setForm(f => ({ ...f, remarks: v }))} /></div>
          <div className="sm:col-span-2">
            <FileAttachments value={form.attachments || []} onChange={(ids) => setForm(f => ({ ...f, attachments: ids }))} />
          </div>
        </div>
        <DialogFooter>
          <button onClick={saveItem} disabled={busy} className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
            {busy ? saving : save}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function DprDeliverables() {
  const { dpr: l, deleted } = useAdminLabels();
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["dpr"], queryFn: () => api.get("/dpr").then(r => r.data) });
  const [dlg, setDlg] = useState(false);
  const [editing, setEditing] = useState(null);
  const canEdit = user?.role === "Admin";

  async function del(id) {
    if (!window.confirm(l.deleteConfirm)) return;
    try { await api.delete(`/dpr/${id}`); toast.success(deleted); qc.invalidateQueries({ queryKey: ["dpr"] }); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-slate-900">{l.title}</h2>
          <p className="text-xs text-slate-500">{l.subtitle}</p>
        </div>
        {canEdit && (
          <button data-testid={TID.dprCreateBtn} onClick={() => { setEditing(null); setDlg(true); }}
            className="bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <Plus size={16} /> {l.newDeliverable}
          </button>
        )}
      </div>

      <Card title={l.masterTitle} subtitle={l.milestonesCount(data?.length || 0)}>
        <ScrollRegion className="overflow-x-auto" label={l.tableScroll} data-testid={TID.dprList}>
          <table className="dense-table w-full">
            <thead><tr>
              <th>{l.colCode}</th><th>{l.colTitle}</th><th>{l.colOwner}</th><th>{l.colTargetDate}</th><th>{l.colActual}</th>
              <th>{l.colStatus}</th><th>{l.colDelayReason}</th>{canEdit && <th></th>}
            </tr></thead>
            <tbody>
              {(data || []).map(r => (
                <tr key={r.id}>
                  <td className="font-mono text-xs">{r.code}</td>
                  <td className="font-medium text-slate-700 max-w-md">{r.title}</td>
                  <td>{r.owner || "—"}</td>
                  <td>{r.target_date || "—"}</td>
                  <td>{r.actual_date || "—"}</td>
                  <td><RagBadge status={ragOf(r.status)} label={r.status} /></td>
                  <td className="text-slate-500 text-xs max-w-xs truncate">
                    {r.delay_reason || "—"}
                    {(r.attachments?.length || 0) > 0 && (
                      <span className="ml-2 text-[10px] text-slate-500">📎 {r.attachments.length}</span>
                    )}
                  </td>
                  {canEdit && (
                    <td>
                      <div className="flex gap-2">
                        <button onClick={() => { setEditing(r); setDlg(true); }} className="text-slate-600 hover:text-[#003B73]"><PencilSimple size={14} /></button>
                        <button onClick={() => del(r.id)} className="text-red-600 hover:text-red-800"><Trash size={14} /></button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {!isLoading && (data?.length || 0) === 0 && (
                <tr><td colSpan={canEdit ? 8 : 7} className="text-center text-slate-400 py-10">{l.noDeliverables}</td></tr>
              )}
            </tbody>
          </table>
        </ScrollRegion>
      </Card>

      <DprDialog open={dlg} onOpenChange={setDlg} item={editing} onSaved={() => qc.invalidateQueries({ queryKey: ["dpr"] })} />
    </div>
  );
}
