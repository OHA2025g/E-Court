import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { FloppyDisk, Plus, PencilSimple, Trash } from "@phosphor-icons/react";
import { SelectField, TextField, NumberField } from "@/pages/PhysicalTracker";
import { useMasterDataLabels } from "@/lib/useMasterDataLabels";

function useAdmin() { return useAuth().user?.role === "Admin"; }

function CrudPanel({ title, queryKey, listEndpoint, columns, rowKey, dialog: DialogComp, canDelete, deleteKey, getDeleteUrl, listParams }) {
  const isAdmin = useAdmin();
  const qc = useQueryClient();
  const labels = useMasterDataLabels();
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: [queryKey, listParams || {}],
    queryFn: () => api.get(listEndpoint, { params: listParams }).then(r => r.data),
  });

  async function del(row) {
    if (!window.confirm(labels.deleteConfirm)) return;
    try {
      const url = getDeleteUrl(row);
      await api.delete(url);
      toast.success(labels.deleted);
      qc.invalidateQueries({ queryKey: [queryKey] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  }

  return (
    <Card title={title} subtitle={labels.recordsSubtitle(data?.length || 0, !isAdmin)}
      action={isAdmin && DialogComp ? (
        <button onClick={() => { setEditing(null); setOpen(true); }}
          className="inline-flex items-center gap-1.5 bg-[#003B73] hover:bg-[#002B54] text-white px-3 py-1.5 rounded-sm uppercase tracking-wider text-[11px]">
          <Plus size={14} /> {labels.add}
        </button>
      ) : null}>
      <ScrollRegion className="overflow-x-auto max-h-[520px]" label={labels.tableScroll}>
        <table className="dense-table w-full">
          <thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}{isAdmin && DialogComp && <th></th>}</tr></thead>
          <tbody>
            {(data || []).map((r) => (
              <tr key={typeof rowKey === "function" ? rowKey(r) : r[rowKey]}>
                {columns.map(c => <td key={c.key}>{c.render ? c.render(r) : (r[c.key] ?? "—")}</td>)}
                {isAdmin && DialogComp && (
                  <td>
                    <div className="flex gap-2">
                      <button onClick={() => { setEditing(r); setOpen(true); }} className="text-slate-600 hover:text-[#003B73]" aria-label={labels.edit}><PencilSimple size={14} /></button>
                      {canDelete && (
                        <button onClick={() => del(r)} className="text-red-600 hover:text-red-800" aria-label={labels.delete}><Trash size={14} /></button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
            {!isLoading && (data?.length || 0) === 0 && (
              <tr><td colSpan={columns.length + 1} className="text-center text-slate-400 py-8">{labels.noRecords}</td></tr>
            )}
          </tbody>
        </table>
      </ScrollRegion>
      {DialogComp && <DialogComp open={open} onOpenChange={setOpen} item={editing} onSaved={() => qc.invalidateQueries({ queryKey: [queryKey] })} />}
    </Card>
  );
}

function SaveDialog({ open, onOpenChange, title, isEdit, onSave, busy, children }) {
  const labels = useMasterDataLabels();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>{isEdit ? labels.editTitle(title) : labels.addTitle(title)}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 gap-3">{children}</div>
        <DialogFooter>
          <button disabled={busy} onClick={onSave} className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <FloppyDisk size={14} /> {busy ? labels.saving : labels.save}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function HighCourtDialog({ open, onOpenChange, item, onSaved }) {
  const labels = useMasterDataLabels();
  const isEdit = !!item;
  const [form, setForm] = useState({ name: "", active: true });
  const [busy, setBusy] = useState(false);
  const yn = [labels.yes, labels.no];
  React.useEffect(() => { setForm(item || { name: "", active: true }); }, [item, open]);
  async function save() {
    setBusy(true);
    try {
      if (isEdit) await api.put(`/master/high-courts/${encodeURIComponent(item.name)}`, form);
      else await api.post("/master/high-courts", form);
      toast.success(labels.saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <SaveDialog open={open} onOpenChange={onOpenChange} title={labels.entityHighCourt} isEdit={isEdit} onSave={save} busy={busy}>
      <TextField label={labels.fieldName} value={form.name} onChange={(v) => setForm(f => ({ ...f, name: v }))} />
      <SelectField label={labels.colActive} value={form.active ? labels.yes : labels.no} onChange={(v) => setForm(f => ({ ...f, active: v === labels.yes }))} options={yn} />
    </SaveDialog>
  );
}

function ComponentDialog({ open, onOpenChange, item, onSaved }) {
  const labels = useMasterDataLabels();
  const isEdit = !!item;
  const [form, setForm] = useState({ code: "", name: "", uom: "Count", seq: "" });
  const [busy, setBusy] = useState(false);
  React.useEffect(() => { setForm(item ? { ...item, seq: item.seq ?? "" } : { code: "", name: "", uom: "Count", seq: "" }); }, [item, open]);
  async function save() {
    setBusy(true);
    try {
      const payload = { ...form, seq: form.seq === "" ? null : Number(form.seq) };
      if (isEdit) await api.put(`/master/components/${encodeURIComponent(item.code)}`, payload);
      else await api.post("/master/components", payload);
      toast.success(labels.saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <SaveDialog open={open} onOpenChange={onOpenChange} title={labels.entityComponent} isEdit={isEdit} onSave={save} busy={busy}>
      <TextField label={labels.fieldCode} value={form.code} onChange={(v) => setForm(f => ({ ...f, code: v }))} disabled={isEdit} />
      <TextField label={labels.fieldName} value={form.name} onChange={(v) => setForm(f => ({ ...f, name: v }))} />
      <SelectField label={labels.fieldUom} value={form.uom} onChange={(v) => setForm(f => ({ ...f, uom: v }))} options={["Count", "Percentage", "Crore Pages", "PB", "KWH", "Ratio", "Amount"]} />
      <NumberField label={labels.fieldSequence} value={form.seq} onChange={(v) => setForm(f => ({ ...f, seq: v }))} />
    </SaveDialog>
  );
}

function IndicatorDialog({ open, onOpenChange, item, onSaved, components }) {
  const labels = useMasterDataLabels();
  const isEdit = !!item;
  const [form, setForm] = useState({ component: "", indicator: "", unit: "Count", data_type: "Int" });
  const [busy, setBusy] = useState(false);
  React.useEffect(() => { setForm(item || { component: "", indicator: "", unit: "Count", data_type: "Int" }); }, [item, open]);
  async function save() {
    setBusy(true);
    try {
      if (isEdit) {
        await api.put(`/master/indicators?original_indicator=${encodeURIComponent(item.indicator)}`, form);
      } else {
        await api.post("/master/indicators", form);
      }
      toast.success(labels.saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <SaveDialog open={open} onOpenChange={onOpenChange} title={labels.entityIndicator} isEdit={isEdit} onSave={save} busy={busy}>
      <SelectField label={labels.colComponent} value={form.component} onChange={(v) => setForm(f => ({ ...f, component: v }))} options={components.map(c => c.name)} disabled={isEdit} />
      <TextField label={labels.fieldIndicator} value={form.indicator} onChange={(v) => setForm(f => ({ ...f, indicator: v }))} />
      <SelectField label={labels.colUnit} value={form.unit} onChange={(v) => setForm(f => ({ ...f, unit: v }))} options={["Count", "Percentage", "Crore Pages", "PB"]} />
      <SelectField label={labels.fieldDataType} value={form.data_type} onChange={(v) => setForm(f => ({ ...f, data_type: v }))} options={["Int", "Float"]} />
    </SaveDialog>
  );
}

function KpiDialog({ open, onOpenChange, item, onSaved, subjects }) {
  const labels = useMasterDataLabels();
  const isEdit = !!item;
  const [form, setForm] = useState({ subject: "", kpi_id: "", kpi: "", periodicity: "Monthly", granularity: "District", outcome_type: "Absolute", value_type: "Count", description: "" });
  const [busy, setBusy] = useState(false);
  React.useEffect(() => { setForm(item || { subject: "", kpi_id: "", kpi: "", periodicity: "Monthly", granularity: "District", outcome_type: "Absolute", value_type: "Count", description: "" }); }, [item, open]);
  async function save() {
    setBusy(true);
    try {
      if (isEdit) await api.put(`/master/kpis?original_kpi_id=${encodeURIComponent(item.kpi_id)}`, form);
      else await api.post("/master/kpis", form);
      toast.success(labels.saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <SaveDialog open={open} onOpenChange={onOpenChange} title={labels.entityKpi} isEdit={isEdit} onSave={save} busy={busy}>
      <SelectField label={labels.colSubject} value={form.subject} onChange={(v) => setForm(f => ({ ...f, subject: v }))} options={subjects.map(s => s.name)} disabled={isEdit} />
      <TextField label={labels.fieldKpiId} value={form.kpi_id} onChange={(v) => setForm(f => ({ ...f, kpi_id: v }))} disabled={isEdit} />
      <TextField label={labels.fieldKpi} value={form.kpi} onChange={(v) => setForm(f => ({ ...f, kpi: v }))} />
      <TextField label={labels.fieldDescription} value={form.description || ""} onChange={(v) => setForm(f => ({ ...f, description: v }))} />
      <SelectField label={labels.fieldPeriodicity} value={form.periodicity} onChange={(v) => setForm(f => ({ ...f, periodicity: v }))} options={["Monthly", "Yearly", "Cumulative", "On-date"]} />
      <SelectField label={labels.fieldGranularity} value={form.granularity} onChange={(v) => setForm(f => ({ ...f, granularity: v }))} options={["National", "State", "District"]} />
      <SelectField label={labels.fieldOutcomeType} value={form.outcome_type} onChange={(v) => setForm(f => ({ ...f, outcome_type: v }))} options={["Absolute", "Relative"]} />
      <SelectField label={labels.fieldValueType} value={form.value_type} onChange={(v) => setForm(f => ({ ...f, value_type: v }))} options={["Count", "Amount", "Percentage", "Ratio"]} />
    </SaveDialog>
  );
}

function SubjectDialog({ open, onOpenChange, item, onSaved }) {
  const labels = useMasterDataLabels();
  const isEdit = !!item;
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  React.useEffect(() => { setName(item?.name || ""); }, [item, open]);
  async function save() {
    setBusy(true);
    try {
      if (isEdit) await api.put(`/master/outcome-subjects/${encodeURIComponent(item.name)}`, { name });
      else await api.post("/master/outcome-subjects", { name });
      toast.success(labels.saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <SaveDialog open={open} onOpenChange={onOpenChange} title={labels.entitySubject} isEdit={isEdit} onSave={save} busy={busy}>
      <TextField label={labels.fieldSubjectName} value={name} onChange={setName} disabled={isEdit} />
    </SaveDialog>
  );
}

function PeriodDialog({ open, onOpenChange, item, onSaved }) {
  const labels = useMasterDataLabels();
  const isEdit = !!item;
  const [form, setForm] = useState({ period: "", label: "", is_baseline: false });
  const [busy, setBusy] = useState(false);
  const yn = [labels.yes, labels.no];
  React.useEffect(() => { setForm(item || { period: "", label: "", is_baseline: false }); }, [item, open]);
  async function save() {
    setBusy(true);
    try {
      if (isEdit) await api.put(`/master/periods/${form.period}`, form);
      else await api.post("/master/periods", form);
      toast.success(labels.saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <SaveDialog open={open} onOpenChange={onOpenChange} title={labels.entityPeriod} isEdit={isEdit} onSave={save} busy={busy}>
      <TextField label={labels.fieldPeriod} value={form.period} onChange={(v) => setForm(f => ({ ...f, period: v }))} disabled={isEdit} />
      <TextField label={labels.fieldDisplayLabel} value={form.label} onChange={(v) => setForm(f => ({ ...f, label: v }))} />
      <SelectField label={labels.fieldIsBaseline} value={form.is_baseline ? labels.yes : labels.no} onChange={(v) => setForm(f => ({ ...f, is_baseline: v === labels.yes }))} options={yn} />
    </SaveDialog>
  );
}

function DistrictDialog({ open, onOpenChange, item, onSaved, hcs }) {
  const labels = useMasterDataLabels();
  const isEdit = !!item;
  const [form, setForm] = useState({ high_court: "", name: "", active: true });
  const [busy, setBusy] = useState(false);
  const yn = [labels.yes, labels.no];
  React.useEffect(() => { setForm(item || { high_court: "", name: "", active: true }); }, [item, open]);
  async function save() {
    setBusy(true);
    try {
      if (isEdit) {
        await api.put("/master/districts", form, {
          params: { high_court: item.high_court, name: item.name },
        });
      } else {
        await api.post("/master/districts", form);
      }
      toast.success(labels.saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <SaveDialog open={open} onOpenChange={onOpenChange} title={labels.entityDistrict} isEdit={isEdit} onSave={save} busy={busy}>
      <SelectField label={labels.colHighCourt} value={form.high_court} onChange={(v) => setForm(f => ({ ...f, high_court: v }))} options={hcs.map(h => h.name)} disabled={isEdit} />
      <TextField label={labels.fieldDistrictName} value={form.name} onChange={(v) => setForm(f => ({ ...f, name: v }))} disabled={isEdit} />
      <SelectField label={labels.colActive} value={form.active ? labels.yes : labels.no} onChange={(v) => setForm(f => ({ ...f, active: v === labels.yes }))} options={yn} />
    </SaveDialog>
  );
}

function IpAllowlistPanel() {
  const isAdmin = useAdmin();
  const labels = useMasterDataLabels();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["admin-ip-allowlist"],
    queryFn: () => api.get("/admin/security/ip-allowlist").then(r => r.data),
    enabled: isAdmin,
  });
  const [enabled, setEnabled] = useState(false);
  const [cidrs, setCidrs] = useState("");
  const [saving, setSaving] = useState(false);

  React.useEffect(() => {
    if (data) {
      setEnabled(!!data.enabled);
      setCidrs((data.cidrs || []).join("\n"));
    }
  }, [data]);

  async function save() {
    setSaving(true);
    try {
      await api.put("/admin/security/ip-allowlist", {
        enabled,
        cidrs: cidrs.split("\n").map((c) => c.trim()).filter(Boolean),
      });
      toast.success(labels.ipUpdated);
      qc.invalidateQueries({ queryKey: ["admin-ip-allowlist"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  }

  if (!isAdmin) return null;

  return (
    <Card title={labels.ipTitle} subtitle={labels.ipSubtitle}>
      <div className="p-4 space-y-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          {labels.ipEnable}
        </label>
        <label className="block">
          <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{labels.ipCidrs}</span>
          <textarea
            value={cidrs}
            onChange={(e) => setCidrs(e.target.value)}
            rows={6}
            placeholder={labels.ipPlaceholder}
            className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm font-mono text-xs focus:outline-none focus:border-[#003B73]"
          />
        </label>
        <button disabled={saving} onClick={save}
          className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
          <FloppyDisk size={14} /> {saving ? labels.saving : labels.saveAllowlist}
        </button>
      </div>
    </Card>
  );
}

function WorkflowPanel() {
  const isAdmin = useAdmin();
  const labels = useMasterDataLabels();
  const qc = useQueryClient();
  const hcs = useQuery({ queryKey: ["m-hc"], queryFn: () => api.get("/master/high-courts").then(r => r.data), enabled: isAdmin });
  const periods = useQuery({ queryKey: ["m-per"], queryFn: () => api.get("/master/periods").then(r => r.data), enabled: isAdmin });
  const { data } = useQuery({
    queryKey: ["workflow-settings"],
    queryFn: () => api.get("/workflow/settings").then(r => r.data),
    enabled: isAdmin,
  });
  const [graceDays, setGraceDays] = useState("");
  const [slaDueDay, setSlaDueDay] = useState("");
  const [requireApproval, setRequireApproval] = useState(true);
  const [saving, setSaving] = useState(false);
  const [ovHc, setOvHc] = useState("");
  const [ovPeriod, setOvPeriod] = useState("");
  const [ovReason, setOvReason] = useState("");
  const [ovHours, setOvHours] = useState("24");
  const [ovBusy, setOvBusy] = useState(false);

  React.useEffect(() => {
    if (data) {
      setGraceDays(data.submission_grace_days ?? 7);
      setSlaDueDay(data.sla_due_day ?? 10);
      setRequireApproval(data.dashboard_require_approval !== false);
    }
  }, [data]);

  async function saveSettings() {
    setSaving(true);
    try {
      await api.put("/workflow/settings", {
        submission_grace_days: Number(graceDays),
        sla_due_day: Number(slaDueDay),
        dashboard_require_approval: requireApproval,
      });
      toast.success(labels.workflowSaved);
      qc.invalidateQueries({ queryKey: ["workflow-settings"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  }

  async function submitOverride() {
    if (!ovHc || !ovPeriod || !ovReason.trim()) {
      toast.error(labels.overrideRequired);
      return;
    }
    setOvBusy(true);
    try {
      const r = await api.post("/admin/periods/override", {
        high_court: ovHc,
        reporting_period: ovPeriod,
        reason: ovReason.trim(),
        hours: Number(ovHours) || 24,
      });
      toast.success(labels.overrideSuccess(r.data.edit_override_until?.slice(0, 16)));
      setOvReason("");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setOvBusy(false);
    }
  }

  if (!isAdmin) return null;

  return (
    <div className="space-y-6">
      <Card title={labels.workflowTitle} subtitle={labels.workflowSubtitle}>
        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <NumberField label={labels.graceDays} value={graceDays} onChange={setGraceDays} />
          <NumberField label={labels.slaDueDay} value={slaDueDay} onChange={setSlaDueDay} />
          <label className="flex items-end pb-2">
            <span className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={requireApproval} onChange={(e) => setRequireApproval(e.target.checked)} />
              {labels.dashboardRequireApproval}
            </span>
          </label>
          <div className="flex items-end">
            <button disabled={saving} onClick={saveSettings}
              className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
              <FloppyDisk size={14} /> {saving ? labels.saving : labels.saveSettings}
            </button>
          </div>
        </div>
      </Card>
      <Card title={labels.overrideTitle} subtitle={labels.overrideSubtitle}>
        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <SelectField label={labels.colHighCourt} value={ovHc} onChange={setOvHc} options={(hcs.data || []).map(h => h.name)} />
          <SelectField label={labels.entityPeriod} value={ovPeriod} onChange={setOvPeriod}
            options={(periods.data || []).filter(p => !p.is_baseline).map(p => ({ label: p.label, value: p.period }))} />
          <NumberField label={labels.overrideHours} value={ovHours} onChange={setOvHours} />
          <div className="sm:col-span-2">
            <TextField label={labels.fieldReason} value={ovReason} onChange={setOvReason} />
          </div>
          <div className="sm:col-span-2">
            <button disabled={ovBusy} onClick={submitOverride}
              className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
              {ovBusy ? labels.applying : labels.applyOverride}
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}

function RagThresholds() {
  const isAdmin = useAdmin();
  const labels = useMasterDataLabels();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["rag-thresholds"], queryFn: () => api.get("/master/rag-thresholds").then(r => r.data) });
  const [green, setGreen] = useState("");
  const [amber, setAmber] = useState("");
  const [saving, setSaving] = useState(false);
  React.useEffect(() => { if (data) { setGreen(data.green_min ?? 80); setAmber(data.amber_min ?? 65); } }, [data]);
  async function save() {
    setSaving(true);
    try {
      await api.put("/master/rag-thresholds", { green_min: Number(green), amber_min: Number(amber) });
      toast.success(labels.ragUpdated);
      qc.invalidateQueries({ queryKey: ["rag-thresholds"] });
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setSaving(false); }
  }
  return (
    <Card title={labels.ragTitle} subtitle={labels.ragSubtitle}>
      <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <NumberField label={labels.greenMin} value={green} onChange={setGreen} disabled={!isAdmin} />
        <NumberField label={labels.amberMin} value={amber} onChange={setAmber} disabled={!isAdmin} />
        <div className="flex items-end">
          <button disabled={!isAdmin || saving} onClick={save}
            className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <FloppyDisk size={14} /> {saving ? labels.saving : labels.saveThresholds}
          </button>
        </div>
      </div>
    </Card>
  );
}

export default function MasterData() {
  const isAdmin = useAdmin();
  const labels = useMasterDataLabels();
  const yn = (v) => (v ? labels.yes : labels.no);
  const comps = useQuery({ queryKey: ["m-comp"], queryFn: () => api.get("/master/components").then(r => r.data) });
  const subs = useQuery({ queryKey: ["m-subj"], queryFn: () => api.get("/master/outcome-subjects").then(r => r.data) });
  const hcs = useQuery({ queryKey: ["m-hc"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const districtParams = isAdmin ? { include_inactive: true } : {};

  const tabs = [
    ["hc", labels.tabHc], ["dist", labels.tabDist], ["comp", labels.tabComp],
    ["ind", labels.tabInd], ["subj", labels.tabSubj], ["kpi", labels.tabKpi],
    ["period", labels.tabPeriod], ["rag", labels.tabRag], ["sec", labels.tabSec],
    ...(isAdmin ? [["workflow", labels.tabWorkflow]] : []),
  ];

  return (
    <div className="space-y-6">
      <Tabs defaultValue="hc" className="w-full">
        <TabsList className="bg-transparent border-b border-slate-200 w-full justify-start rounded-none p-0 flex-wrap h-auto">
          {tabs.map(([v, l]) => (
            <TabsTrigger key={v} value={v} className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#003B73] data-[state=active]:text-[#003B73] data-[state=inactive]:text-slate-600 uppercase tracking-wider text-xs">
              {l}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="hc" className="mt-4">
          <CrudPanel
            title={labels.highCourts} queryKey="m-hc" listEndpoint="/master/high-courts"
            columns={[{ key: "name", label: labels.colName }, { key: "active", label: labels.colActive, render: r => yn(r.active) }]}
            rowKey="name" dialog={HighCourtDialog} canDelete
            getDeleteUrl={(r) => `/master/high-courts/${encodeURIComponent(r.name)}`}
          />
        </TabsContent>

        <TabsContent value="dist" className="mt-4">
          <CrudPanel
            title={labels.districts} queryKey="m-dist" listEndpoint="/master/districts"
            listParams={districtParams}
            columns={[
              { key: "high_court", label: labels.colHighCourt },
              { key: "name", label: labels.colDistrict },
              { key: "active", label: labels.colActive, render: r => yn(r.active) },
            ]}
            rowKey={(r) => `${r.high_court}|${r.name}`}
            dialog={(p) => <DistrictDialog {...p} hcs={hcs.data || []} />}
            canDelete
            getDeleteUrl={(r) => `/master/districts?high_court=${encodeURIComponent(r.high_court)}&name=${encodeURIComponent(r.name)}`}
          />
        </TabsContent>

        <TabsContent value="comp" className="mt-4">
          <CrudPanel
            title={labels.components} queryKey="m-comp" listEndpoint="/master/components"
            columns={[
              { key: "seq", label: labels.colSeq }, { key: "code", label: labels.colCode },
              { key: "name", label: labels.colName }, { key: "uom", label: labels.colUom },
            ]} rowKey="code" dialog={ComponentDialog} canDelete
            getDeleteUrl={(r) => `/master/components/${encodeURIComponent(r.code)}`}
          />
        </TabsContent>

        <TabsContent value="ind" className="mt-4">
          <CrudPanel
            title={labels.physicalIndicators} queryKey="m-ind" listEndpoint="/master/indicators"
            columns={[
              { key: "component", label: labels.colComponent }, { key: "indicator", label: labels.colIndicator },
              { key: "unit", label: labels.colUnit }, { key: "data_type", label: labels.colType },
            ]} rowKey={(r) => `${r.component}|${r.indicator}`}
            dialog={(p) => <IndicatorDialog {...p} components={comps.data || []} />}
            canDelete
            getDeleteUrl={(r) => `/master/indicators?component=${encodeURIComponent(r.component)}&indicator=${encodeURIComponent(r.indicator)}`}
          />
        </TabsContent>

        <TabsContent value="subj" className="mt-4">
          <CrudPanel
            title={labels.outcomeSubjects} queryKey="m-subj" listEndpoint="/master/outcome-subjects"
            columns={[{ key: "name", label: labels.colSubject }]} rowKey="name"
            dialog={SubjectDialog} canDelete
            getDeleteUrl={(r) => `/master/outcome-subjects/${encodeURIComponent(r.name)}`}
          />
        </TabsContent>

        <TabsContent value="kpi" className="mt-4">
          <CrudPanel
            title={labels.outcomeKpis} queryKey="m-kpi" listEndpoint="/master/kpis"
            columns={[
              { key: "subject", label: labels.colSubject }, { key: "kpi_id", label: labels.colKpiId },
              { key: "kpi", label: labels.colKpi }, { key: "periodicity", label: labels.colPeriodicity },
              { key: "granularity", label: labels.colGranularity },
            ]} rowKey={(r) => `${r.subject}|${r.kpi_id}`}
            dialog={(p) => <KpiDialog {...p} subjects={subs.data || []} />}
            canDelete
            getDeleteUrl={(r) => `/master/kpis?subject=${encodeURIComponent(r.subject)}&kpi_id=${encodeURIComponent(r.kpi_id)}`}
          />
        </TabsContent>

        <TabsContent value="period" className="mt-4">
          <CrudPanel
            title={labels.reportingPeriods} queryKey="m-per" listEndpoint="/master/periods"
            columns={[
              { key: "period", label: labels.colPeriod }, { key: "label", label: labels.colLabel },
              { key: "is_baseline", label: labels.colBaseline, render: r => yn(r.is_baseline) },
            ]} rowKey="period" dialog={PeriodDialog} canDelete
            getDeleteUrl={(r) => `/master/periods/${encodeURIComponent(r.period)}`}
          />
        </TabsContent>

        <TabsContent value="rag" className="mt-4"><RagThresholds /></TabsContent>
        <TabsContent value="sec" className="mt-4"><IpAllowlistPanel /></TabsContent>
        {isAdmin && <TabsContent value="workflow" className="mt-4"><WorkflowPanel /></TabsContent>}
      </Tabs>
    </div>
  );
}
