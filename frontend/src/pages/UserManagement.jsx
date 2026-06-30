import React, { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { TID } from "@/lib/testIds";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, PencilSimple, Trash, Key } from "@phosphor-icons/react";
import { toast } from "sonner";
import { SelectField, TextField } from "@/pages/PhysicalTracker";
import { PASSWORD_POLICY_HINT, validatePasswordClient } from "@/lib/passwordPolicy";
import { useAdminLabels } from "@/lib/useAdminLabels";

const ROLES = ["Admin", "CPC", "Viewer"];
const TASK_ROLE_OPTIONS = ["manager", "team_lead", "team_member", "auditor", "admin"];

function UserDialog({ open, onOpenChange, user, hcs, users, onSaved }) {
  const { save, saving, saved, users: l } = useAdminLabels();
  const isEdit = !!user;
  const [form, setForm] = useState(() => user || { email: "", name: "", role: "CPC", high_court: "", password: "", task_role: "", team_lead_id: "" });
  useEffect(() => {
    setForm(user ? { ...user, password: "", task_role: user.task_role || "", team_lead_id: user.team_lead_id || "" } : { email: "", name: "", role: "CPC", high_court: "", password: "", task_role: "", team_lead_id: "" });
  }, [user, open]);
  const [busy, setBusy] = useState(false);
  const teamLeads = (users || []).filter((u) => u.task_role === "team_lead" || u.role === "CPC" || u.role === "Admin");
  async function saveUser() {
    if (!form.email || !form.name) { toast.error(l.emailNameRequired); return; }
    if (!isEdit && !form.password) { toast.error(l.passwordRequired); return; }
    if (form.password) {
      const err = validatePasswordClient(form.password);
      if (err) { toast.error(err); return; }
    }
    setBusy(true);
    try {
      const payload = {
        name: form.name,
        role: form.role,
        high_court: form.role === "CPC" ? form.high_court : null,
        task_role: form.task_role || null,
        team_lead_id: form.team_lead_id || null,
      };
      if (isEdit) {
        if (form.password) payload.password = form.password;
        await api.put(`/users/${user.id}`, payload);
      } else {
        await api.post("/users", { ...payload, email: form.email, password: form.password });
      }
      toast.success(saved); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>{isEdit ? l.editUser : l.createUser}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 gap-3">
          <TextField label={l.fieldEmail} value={form.email} onChange={(v) => setForm(f => ({ ...f, email: v }))} disabled={isEdit} />
          <TextField label={l.fieldFullName} value={form.name} onChange={(v) => setForm(f => ({ ...f, name: v }))} />
          <SelectField label={l.fieldRole} value={form.role} onChange={(v) => setForm(f => ({ ...f, role: v }))} options={ROLES} />
          {form.role === "CPC" && (
            <SelectField label={l.fieldHcScope} value={form.high_court || ""} onChange={(v) => setForm(f => ({ ...f, high_court: v }))} options={hcs.map(h => h.name)} />
          )}
          <label className="block">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">Task role (optional)</span>
            <select value={form.task_role || ""} onChange={(e) => setForm((f) => ({ ...f, task_role: e.target.value }))}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm">
              <option value="">Default from PMIS role</option>
              {TASK_ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">Reports to team lead</span>
            <select value={form.team_lead_id || ""} onChange={(e) => setForm(f => ({ ...f, team_lead_id: e.target.value }))}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm">
              <option value="">— None —</option>
              {teamLeads.filter((u) => u.id !== user?.id).map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
              ))}
            </select>
          </label>
          <div>
            <TextField
              label={isEdit ? l.resetPasswordOptional : l.initialPassword}
              type="password"
              value={form.password || ""}
              onChange={(v) => setForm(f => ({ ...f, password: v }))}
            />
            <p className="mt-1 text-xs text-slate-500">{PASSWORD_POLICY_HINT}</p>
          </div>
        </div>
        <DialogFooter>
          <button onClick={saveUser} disabled={busy} className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
            {busy ? saving : save}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TeamDialog({ open, onOpenChange, team, users, onSaved }) {
  const { save, saving, saved, teams: l } = useAdminLabels();
  const isEdit = !!team;
  const [form, setForm] = useState({ name: "", department: "", team_lead_id: "", member_ids: [] });
  const [memberSearch, setMemberSearch] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (team) {
      setForm({
        name: team.name || "",
        department: team.department || "",
        team_lead_id: team.team_lead_id || team.team_lead?.id || "",
        member_ids: (team.members || []).map((m) => m.id),
      });
    } else {
      setForm({ name: "", department: "", team_lead_id: "", member_ids: [] });
    }
    setMemberSearch("");
  }, [team, open]);

  const filteredUsers = useMemo(() => {
    const q = memberSearch.trim().toLowerCase();
    const list = users || [];
    if (!q) return list;
    return list.filter((u) =>
      (u.name || "").toLowerCase().includes(q) || (u.email || "").toLowerCase().includes(q),
    );
  }, [users, memberSearch]);

  function toggleMember(userId) {
    setForm((f) => {
      const has = f.member_ids.includes(userId);
      const member_ids = has ? f.member_ids.filter((id) => id !== userId) : [...f.member_ids, userId];
      let team_lead_id = f.team_lead_id;
      if (has && team_lead_id === userId) team_lead_id = "";
      return { ...f, member_ids, team_lead_id };
    });
  }

  async function saveTeam() {
    if (!form.name.trim() || !form.department.trim()) {
      toast.error(l.teamNameRequired);
      return;
    }
    setBusy(true);
    try {
      const payload = {
        name: form.name.trim(),
        department: form.department.trim(),
        team_lead_id: form.team_lead_id || null,
        member_ids: form.member_ids,
      };
      if (isEdit) {
        await api.put(`/teams/${team.id}`, payload);
      } else {
        await api.post("/teams", payload);
      }
      toast.success(saved);
      onSaved();
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  const leadOptions = (users || []).filter((u) => form.member_ids.includes(u.id));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{isEdit ? l.editTeam : l.createTeam}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 gap-3">
          <TextField label={l.fieldTeamName} value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} />
          <TextField label={l.fieldDepartment} value={form.department} onChange={(v) => setForm((f) => ({ ...f, department: v }))} />
          <label className="block">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.fieldTeamLead}</span>
            <select
              value={form.team_lead_id || ""}
              onChange={(e) => setForm((f) => ({ ...f, team_lead_id: e.target.value }))}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm"
            >
              <option value="">— None —</option>
              {leadOptions.map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
              ))}
            </select>
          </label>
          <div>
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.fieldMembers}</span>
            <p className="mt-1 mb-2 text-xs text-slate-500">{l.membersHint}</p>
            <input
              type="search"
              value={memberSearch}
              onChange={(e) => setMemberSearch(e.target.value)}
              placeholder={l.membersSearch}
              className="w-full px-3 py-2 border border-slate-300 rounded-sm bg-white text-sm mb-2"
            />
            <div className="max-h-48 overflow-y-auto border border-slate-200 rounded-sm divide-y divide-slate-100">
              {filteredUsers.map((u) => {
                const checked = form.member_ids.includes(u.id);
                const assignedElsewhere = u.team_id && u.team_id !== team?.id && !checked;
                return (
                  <label
                    key={u.id}
                    className={`flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-slate-50 ${assignedElsewhere ? "opacity-60" : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMember(u.id)}
                      className="rounded border-slate-300"
                    />
                    <span className="flex-1 min-w-0">
                      <span className="block truncate">{u.name}</span>
                      <span className="block text-xs text-slate-500 truncate">{u.email}</span>
                      {u.team_label && u.team_id !== team?.id && (
                        <span className="block text-[10px] text-amber-700">{u.team_label}</span>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        </div>
        <DialogFooter>
          <button onClick={saveTeam} disabled={busy} className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
            {busy ? saving : save}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function UserManagement() {
  const { user: me } = useAuth();
  const adminLabels = useAdminLabels();
  const l = adminLabels.users;
  const tl = adminLabels.teams;
  const { deleted } = adminLabels;
  const qc = useQueryClient();
  const [tab, setTab] = useState("users");
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get("/users").then(r => r.data) });
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => api.get("/teams").then(r => r.data), enabled: tab === "teams" });
  const hcs = useQuery({ queryKey: ["hcs"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const [dlg, setDlg] = useState(false);
  const [editing, setEditing] = useState(null);
  const [teamDlg, setTeamDlg] = useState(false);
  const [editingTeam, setEditingTeam] = useState(null);

  function refreshAll() {
    qc.invalidateQueries({ queryKey: ["users"] });
    qc.invalidateQueries({ queryKey: ["teams"] });
  }

  async function del(id) {
    if (!window.confirm(l.deleteConfirm)) return;
    try { await api.delete(`/users/${id}`); toast.success(deleted); refreshAll(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  }

  async function delTeam(id) {
    if (!window.confirm(tl.deleteTeamConfirm)) return;
    try {
      await api.delete(`/teams/${id}`);
      toast.success(deleted);
      refreshAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  }

  async function resetPwd(u) {
    if (!window.confirm(l.resetConfirm(u.email))) return;
    try {
      const r = await api.post(`/users/${u.id}/reset-password`);
      toast.success(r.data.message || l.resetSuccess);
      qc.invalidateQueries({ queryKey: ["users"] });
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="font-display text-lg font-semibold text-slate-900">{l.title}</h2>
          <p className="text-xs text-slate-500">{l.subtitle}</p>
        </div>
        {tab === "users" ? (
          <button data-testid={TID.userCreateBtn} onClick={() => { setEditing(null); setDlg(true); }}
            className="bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <Plus size={16} /> {l.newUser}
          </button>
        ) : (
          <button data-testid="team-create-btn" onClick={() => { setEditingTeam(null); setTeamDlg(true); }}
            className="bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <Plus size={16} /> {tl.newTeam}
          </button>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-transparent border-b border-slate-200 w-full justify-start rounded-none p-0">
          <TabsTrigger value="users" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#003B73] data-[state=active]:text-[#003B73] data-[state=inactive]:text-slate-600 uppercase tracking-wider text-xs">
            {l.tabUsers}
          </TabsTrigger>
          <TabsTrigger value="teams" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#003B73] data-[state=active]:text-[#003B73] data-[state=inactive]:text-slate-600 uppercase tracking-wider text-xs">
            {l.tabTeams}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-6">
          <Card title={l.accounts} subtitle={l.usersCount(users.data?.length || 0)}>
            <ScrollRegion className="overflow-x-auto" label={l.tableScroll} data-testid={TID.userList}>
              <table className="dense-table w-full">
                <thead><tr>
                  <th>{l.colEmail}</th><th>{l.colName}</th><th>{l.colRole}</th><th>Task role</th><th>{l.colTeam}</th><th>{l.colHighCourt}</th><th>{l.colCreated}</th><th></th>
                </tr></thead>
                <tbody>
                  {(users.data || []).map(u => (
                    <tr key={u.id}>
                      <td className="font-mono text-xs">{u.email}</td>
                      <td>{u.name}</td>
                      <td>
                        <span className={`inline-block text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${
                          u.role === "Admin" ? "bg-[#003B73]/10 text-[#003B73] border-[#003B73]/20"
                            : u.role === "CPC" ? "bg-amber-50 text-amber-800 border-amber-200"
                            : "bg-slate-100 text-slate-600 border-slate-200"
                        }`}>{u.role}</span>
                      </td>
                      <td className="text-xs text-slate-600">
                        {u.task_role ? u.task_role.replace(/_/g, " ") : "Default"}
                      </td>
                      <td className="text-xs text-slate-600">{u.team_label || "—"}</td>
                      <td>{u.high_court || "—"}</td>
                      <td className="font-mono text-xs text-slate-500">{u.created_at?.slice(0, 10) || "—"}</td>
                      <td>
                        <div className="flex gap-2">
                          <button onClick={() => { setEditing(u); setDlg(true); }} className="text-slate-600 hover:text-[#003B73]" title={l.editBtn} aria-label={l.editBtn}><PencilSimple size={14} /></button>
                          <button data-testid={`reset-pwd-${u.email}`} onClick={() => resetPwd(u)} className="text-amber-600 hover:text-amber-800" title={l.resetPassword} aria-label={l.resetPassword}><Key size={14} /></button>
                          {u.id !== me?.id && (
                            <button onClick={() => del(u.id)} className="text-red-600 hover:text-red-800" title={l.deleteConfirm} aria-label={l.deleteConfirm}><Trash size={14} /></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </Card>
        </TabsContent>

        <TabsContent value="teams" className="mt-6">
          <Card title={tl.teamsCard} subtitle={tl.teamsCount(teams.data?.length || 0)}>
            <ScrollRegion className="overflow-x-auto" label={tl.teamsTableScroll} data-testid="team-list">
              {(teams.data || []).length === 0 ? (
                <p className="p-4 text-sm text-slate-500">{tl.noTeams}</p>
              ) : (
                <table className="dense-table w-full">
                  <thead>
                    <tr>
                      <th>{tl.colTeamName}</th>
                      <th>{tl.colDepartment}</th>
                      <th>{tl.colTeamLead}</th>
                      <th>{tl.colMembers}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(teams.data || []).map((t) => (
                      <tr key={t.id}>
                        <td className="font-medium">{t.name}</td>
                        <td>{t.department}</td>
                        <td>{t.team_lead?.name || "—"}</td>
                        <td>
                          <span className="text-xs text-slate-600">
                            {t.member_count || 0}
                            {t.members?.length ? `: ${t.members.map((m) => m.name).join(", ")}` : ""}
                          </span>
                        </td>
                        <td>
                          <div className="flex gap-2">
                            <button
                              onClick={() => { setEditingTeam(t); setTeamDlg(true); }}
                              className="text-slate-600 hover:text-[#003B73]"
                              title={tl.editTeam}
                              aria-label={tl.editTeam}
                            >
                              <PencilSimple size={14} />
                            </button>
                            <button
                              onClick={() => delTeam(t.id)}
                              className="text-red-600 hover:text-red-800"
                              title={tl.deleteTeamConfirm}
                              aria-label={tl.deleteTeamConfirm}
                            >
                              <Trash size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ScrollRegion>
          </Card>
        </TabsContent>
      </Tabs>

      <UserDialog open={dlg} onOpenChange={setDlg} user={editing} hcs={hcs.data || []} users={users.data || []} onSaved={refreshAll} />
      <TeamDialog open={teamDlg} onOpenChange={setTeamDlg} team={editingTeam} users={users.data || []} onSaved={refreshAll} />
    </div>
  );
}
