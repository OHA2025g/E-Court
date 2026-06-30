import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { taskPermissions } from "@/lib/taskPermissions";
import { useAuth } from "@/lib/auth";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { api, formatApiError } from "@/lib/api";
import { StatusBadge, PriorityBadge, SlaBadge } from "@/components/task-management/TaskBadges";
import TaskCreateDialog from "@/components/task-management/TaskCreateDialog";
import TaskAssignmentPanel from "@/components/task-management/TaskAssignmentPanel";
import FileAttachments from "@/components/FileAttachments";
import { toast } from "sonner";
import {
  Plus, CaretDown, Folder, LinkSimple, ChatCircle, Clock, User,
} from "@phosphor-icons/react";

const CHECKLIST_KEYS = [
  "resolution_matches", "evidence_uploaded", "evidence_relevant", "no_dependency_pending", "sla_checked",
];
const WORKFLOW_ACTIVE = [
  "UNASSIGNED", "ASSIGNED_TO_TEAM_LEAD", "ASSIGNED_TO_TEAM_MEMBER", "ACCEPTED", "IN_PROGRESS", "REWORK_REQUIRED", "BLOCKED",
];
const TAB_DEFS = [
  { id: "comments", testId: "tm-tab-comments" },
  { id: "subtasks", testId: "tm-tab-subtasks" },
  { id: "logHours", testId: "tm-tab-log-hours" },
  { id: "evidence", testId: "tm-tab-evidence" },
  { id: "dependency", testId: "tm-tab-dependency" },
  { id: "statusTimeline", testId: "tm-tab-status-timeline" },
  { id: "issues", testId: "tm-tab-issues" },
  { id: "activity", testId: "tm-tab-activity" },
  { id: "assignment", testId: "tm-tab-assignment" },
  { id: "approval", testId: "tm-tab-approval" },
];

function fmtDate(v) {
  if (!v) return "";
  return String(v).slice(0, 10);
}

function daysUntil(due) {
  if (!due) return null;
  const d = new Date(String(due).slice(0, 10));
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  d.setHours(0, 0, 0, 0);
  return Math.ceil((d - now) / (1000 * 60 * 60 * 24));
}

function taskToForm(task) {
  if (!task) return {};
  return {
    associated_team: task.associated_team || task.department_name || "",
    current_owner_id: task.current_owner_id || task.current_owner?.id || "",
    start_date: fmtDate(task.start_date || task.sla_started_at || task.created_at),
    billing_type: task.billing_type || "None",
    fund_target_cr: task.fund_target_cr ?? "",
    hardware_count: task.hardware_count ?? "",
    funds_utilised_cr: task.funds_utilised_cr ?? "",
    utilisation_pct: task.utilisation_pct ?? "",
    fund_allocated_cr: task.fund_allocated_cr ?? "",
    funds_released_cr: task.funds_released_cr ?? "",
    high_court_name: task.high_court_name || "",
    component: task.component || "",
    recurrence: task.recurrence || "None",
    reminder: task.reminder || "None",
    tags: (task.tags || []).join(", "),
    priority: task.priority || "Medium",
    due_date: fmtDate(task.due_date),
    module_name: task.module_name || "",
    project_name: task.project_name || "",
  };
}

function InfoField({ label, children, className = "" }) {
  return (
    <div className={`tm-info-field ${className}`}>
      <label className="tm-info-label">{label}</label>
      <div className="tm-info-value">{children}</div>
    </div>
  );
}

export default function TaskDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const l = useTaskLabels();
  const perms = taskPermissions(user);
  const [tab, setTab] = useState("subtasks");
  const [infoOpen, setInfoOpen] = useState(true);
  const [hcFilter, setHcFilter] = useState("");
  const [comment, setComment] = useState("");
  const [rejectRemarks, setRejectRemarks] = useState("");
  const [progress, setProgress] = useState(0);
  const [subtaskOpen, setSubtaskOpen] = useState(false);
  const [fileIds, setFileIds] = useState([]);
  const [infoForm, setInfoForm] = useState({});
  const [checklist, setChecklist] = useState({
    resolution_matches: false, evidence_uploaded: false, evidence_relevant: false,
    no_dependency_pending: false, sla_checked: false,
  });

  const { data: meta } = useQuery({ queryKey: ["tm-meta"], queryFn: taskApi.meta });
  const { data: sidebarList } = useQuery({
    queryKey: ["tm-sidebar", hcFilter],
    queryFn: () => taskApi.list({ limit: 40, high_court_name: hcFilter || undefined }),
  });
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["tm-task", id],
    queryFn: () => taskApi.get(id),
  });

  const task = data?.task;
  const readOnly = perms.readOnly || ["CLOSED", "CANCELLED"].includes(task?.status);

  useEffect(() => {
    if (task) setInfoForm(taskToForm(task));
  }, [task]);

  const allSubtasks = useMemo(() => {
    const parent = task ? [task, ...(data?.subtasks || [])] : (data?.subtasks || []);
    return parent.filter(Boolean);
  }, [task, data?.subtasks]);

  const selectedTeamOption = useMemo(
    () => (meta?.associated_teams || []).find((o) => o.value === infoForm.associated_team),
    [meta?.associated_teams, infoForm.associated_team],
  );
  const ownerOptions = selectedTeamOption?.members || [];

  const activityItems = useMemo(() => {
    const items = [];
    (data?.comments || []).forEach((c) => items.push({
      type: "comment", at: c.created_at, title: c.user_email, body: c.comment_text,
    }));
    (data?.audit_log || []).forEach((a) => items.push({
      type: "audit", at: a.performed_at, title: a.action, body: a.performed_by_email,
    }));
    return items.sort((a, b) => String(b.at).localeCompare(String(a.at)));
  }, [data?.comments, data?.audit_log]);

  async function act(fn, msg) {
    try {
      await fn();
      toast.success(msg);
      refetch();
      qc.invalidateQueries({ queryKey: ["tm-sidebar"] });
      qc.invalidateQueries({ queryKey: ["tm-manager-dash"] });
      qc.invalidateQueries({ queryKey: ["tm-lead-dash"] });
      qc.invalidateQueries({ queryKey: ["tm-member-dash"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  }

  async function saveTaskInfo() {
    const body = {
      ...infoForm,
      tags: infoForm.tags ? infoForm.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
      fund_target_cr: infoForm.fund_target_cr === "" ? null : Number(infoForm.fund_target_cr),
      hardware_count: infoForm.hardware_count === "" ? null : Number(infoForm.hardware_count),
      funds_utilised_cr: infoForm.funds_utilised_cr === "" ? null : Number(infoForm.funds_utilised_cr),
      utilisation_pct: infoForm.utilisation_pct === "" ? null : Number(infoForm.utilisation_pct),
      fund_allocated_cr: infoForm.fund_allocated_cr === "" ? null : Number(infoForm.fund_allocated_cr),
      funds_released_cr: infoForm.funds_released_cr === "" ? null : Number(infoForm.funds_released_cr),
      current_owner_id: infoForm.current_owner_id || null,
    };
    await act(() => taskApi.updateInfo(id, body), l.detail.toast.infoSaved);
  }

  async function uploadEvidence() {
    for (const fid of fileIds) {
      const metaRes = await api.get(`/files/${fid}/meta`).then((r) => r.data).catch(() => ({}));
      await taskApi.evidence(id, {
        file_id: fid,
        file_name: metaRes.original_filename,
        file_size: metaRes.size,
        mime_type: metaRes.content_type,
        evidence_type: "Document",
      });
    }
    setFileIds([]);
    toast.success(l.detail.toast.evidenceUploaded);
    refetch();
  }

  if (isLoading) return <div className="text-slate-500 p-6">{l.detail.loading}</div>;
  if (!task) return <div className="text-red-600 p-6">{l.detail.notFound}</div>;

  const ownerName = task.current_owner?.name || l.common.unassigned;
  const durationLabel = task.duration_days != null ? `${task.duration_days} days` : "—";
  const dueDays = daysUntil(task.due_date);
  const canShowEscalate = perms.canEscalate && WORKFLOW_ACTIVE.includes(task.status);
  const canShowBlock = perms.canMarkBlocked && !readOnly && task.status !== "BLOCKED" && WORKFLOW_ACTIVE.includes(task.status)
    && (task.assigned_team_member_id === user.id || perms.canVerify || perms.canApproveClosure);
  const showRemarks = !readOnly && (perms.canVerify || perms.canApproveClosure || canShowEscalate || canShowBlock);

  function setField(key, value) {
    setInfoForm((f) => ({ ...f, [key]: value }));
  }

  function setAssociatedTeam(value) {
    setInfoForm((f) => {
      const next = { ...f, associated_team: value };
      const team = (meta?.associated_teams || []).find((o) => o.value === value);
      const memberIds = new Set((team?.members || []).map((m) => m.id));
      if (f.current_owner_id && !memberIds.has(f.current_owner_id)) {
        next.current_owner_id = "";
      }
      return next;
    });
  }

  return (
    <div className="tm-detail-layout" data-testid="tm-task-detail">
      <aside className="tm-detail-sidebar">
        <select
          className="tm-detail-hc-select"
          value={hcFilter}
          onChange={(e) => setHcFilter(e.target.value)}
          aria-label={l.detail.highCourtsFilter}
        >
          <option value="">{l.detail.allHighCourts}</option>
          {(meta?.high_courts || []).map((hc) => (
            <option key={hc} value={hc}>{hc}</option>
          ))}
        </select>
        <div className="tm-detail-sidebar-list">
          {(sidebarList?.items || []).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => navigate(`/task-management/tasks/${t.id}`)}
              className={`tm-detail-sidebar-card ${t.id === id ? "is-active" : ""}`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-mono text-[10px] text-slate-500">{t.task_code}</span>
                <StatusBadge status={t.status} label={t.status_label} />
              </div>
              <div className="text-sm font-medium text-slate-800 line-clamp-2 text-left">{t.title}</div>
              <div className="flex items-center justify-between mt-2 text-xs text-slate-500">
                <span className="truncate">{t.current_owner?.name || l.common.unassigned}</span>
                <span className="flex gap-2">
                  <Clock size={12} /><ChatCircle size={12} /><User size={12} />
                </span>
              </div>
            </button>
          ))}
        </div>
      </aside>

      <div className="tm-detail-main">
        <header className="tm-detail-header">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="tm-detail-task-badge">Task</span>
                <span className="font-mono text-sm text-slate-600">{task.task_code}</span>
                <span data-testid="tm-task-status"><StatusBadge status={task.status} label={task.status_label} /></span>
              </div>
              <h1 className="tm-detail-title">{task.title}</h1>
              <div className="tm-detail-meta">
                <span>{l.detail.byCreator(task.created_by_user?.name || "—")}</span>
                {task.module_name && (
                  <span className="inline-flex items-center gap-1 text-[#003B73]">
                    <Folder size={14} /> {task.module_name}
                    {task.project_name && ` · ${task.project_name}`}
                  </span>
                )}
                <LinkSimple size={14} className="text-slate-400" />
                <ChatCircle size={14} className="text-slate-400" />
              </div>
            </div>
            <div className="tm-detail-status-select">
              <StatusBadge status={task.status} label={task.status_label} />
              <PriorityBadge priority={task.priority} />
              <SlaBadge slaStatus={task.sla_status} pct={task.sla_pct_consumed} />
            </div>
          </div>

          {!readOnly && (
            <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-slate-100">
              {perms.canAcceptTask && task.status === "ASSIGNED_TO_TEAM_MEMBER" && task.assigned_team_member_id === user.id && (
                <ActionBtn testId="tm-action-accept" onClick={() => act(() => taskApi.accept(id), l.detail.toast.accepted)}>{l.detail.actions.accept}</ActionBtn>
              )}
              {task.assigned_team_member_id === user.id && ["ACCEPTED", "ASSIGNED_TO_TEAM_MEMBER", "IN_PROGRESS", "REWORK_REQUIRED"].includes(task.status) && (
                <>
                  <ActionBtn testId="tm-action-start" onClick={() => act(() => taskApi.start(id), l.detail.toast.started)}>{l.detail.actions.start}</ActionBtn>
                  <ActionBtn testId="tm-action-progress" onClick={() => act(() => taskApi.progress(id, { progress_pct: progress || task.progress_pct || 10 }), l.detail.toast.progressUpdated)}>{l.detail.actions.updateProgress}</ActionBtn>
                  <input type="range" min={0} max={100} value={progress || task.progress_pct || 0} onChange={(e) => setProgress(Number(e.target.value))} className="w-32" />
                  <ActionBtn testId="tm-action-submit" onClick={() => act(() => taskApi.submit(id), l.detail.toast.submitted)}>{l.detail.actions.submitApproval}</ActionBtn>
                </>
              )}
              {task.status === "PROPOSED_BY_MEMBER" && perms.canVerify && (
                <>
                  <ActionBtn testId="tm-action-accept-proposed" onClick={() => act(() => taskApi.acceptProposed(id), l.detail.toast.proposedAccepted)}>{l.detail.actions.acceptProposed}</ActionBtn>
                  <ActionBtn testId="tm-action-reject-proposed" danger onClick={() => rejectRemarks && act(() => taskApi.rejectProposed(id, rejectRemarks), l.detail.toast.rejected)}>{l.detail.actions.rejectProposed}</ActionBtn>
                </>
              )}
              {task.status === "SUBMITTED_FOR_APPROVAL" && perms.canVerify && (
                <>
                  <ActionBtn testId="tm-action-verify" onClick={() => act(() => taskApi.verify(id, { decision: "Verified", checklist }), l.detail.toast.verified)}>{l.detail.actions.verify}</ActionBtn>
                  <ActionBtn testId="tm-action-reject" danger onClick={() => rejectRemarks && act(() => taskApi.verify(id, { decision: "Rejected", remarks: rejectRemarks, checklist }), l.detail.toast.rework)}>{l.detail.actions.reject}</ActionBtn>
                </>
              )}
              {task.status === "MANAGER_APPROVAL_PENDING" && perms.canApproveClosure && (
                <>
                  <ActionBtn testId="tm-action-approve-closure" onClick={() => act(() => taskApi.approveClosure(id), l.detail.toast.closed)}>{l.detail.actions.approveClosure}</ActionBtn>
                  <ActionBtn danger onClick={() => rejectRemarks && act(() => taskApi.rejectClosure(id, rejectRemarks), l.detail.toast.rework)}>{l.detail.actions.rejectClosure}</ActionBtn>
                </>
              )}
              {canShowEscalate && (
                <ActionBtn testId="tm-action-escalate" danger onClick={() => rejectRemarks && act(() => taskApi.escalate(id, rejectRemarks), l.detail.toast.escalated)}>{l.detail.actions.escalate}</ActionBtn>
              )}
              {canShowBlock && (
                <ActionBtn testId="tm-action-block" danger onClick={() => rejectRemarks && act(() => taskApi.blocked(id, rejectRemarks), l.detail.toast.blocked)}>{l.detail.actions.markBlocked}</ActionBtn>
              )}
              <ActionBtn onClick={() => setSubtaskOpen(true)}><Plus size={14} /> {l.detail.actions.subtask}</ActionBtn>
            </div>
          )}
          {showRemarks && (
            <input placeholder={l.detail.actionRemarksPlaceholder} value={rejectRemarks} onChange={(e) => setRejectRemarks(e.target.value)}
              data-testid="tm-action-remarks" className="mt-3 w-full max-w-md px-3 py-2 border border-slate-300 rounded-md text-sm" />
          )}
        </header>

        <section className="tm-info-panel">
          <button type="button" className="tm-info-panel-toggle" onClick={() => setInfoOpen((o) => !o)}>
            <span>{l.detail.taskInformation}</span>
            <CaretDown size={16} className={infoOpen ? "rotate-180" : ""} />
          </button>
          {infoOpen && (
            <div className="tm-info-grid">
              <InfoField label={l.detail.fields.associatedTeam}>
                {readOnly ? (
                  <span className="tm-info-readonly">{infoForm.associated_team || "—"}</span>
                ) : (
                  <select
                    disabled={readOnly}
                    value={infoForm.associated_team || ""}
                    onChange={(e) => setAssociatedTeam(e.target.value)}
                    className="tm-info-input"
                  >
                    <option value="">{l.common.select}</option>
                    {infoForm.associated_team
                      && !(meta?.associated_teams || []).some((o) => o.value === infoForm.associated_team) && (
                      <option value={infoForm.associated_team}>{infoForm.associated_team}</option>
                    )}
                    {Object.entries(
                      (meta?.associated_teams || []).reduce((acc, opt) => {
                        if (!acc[opt.team]) acc[opt.team] = [];
                        acc[opt.team].push(opt);
                        return acc;
                      }, {}),
                    )
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([team, opts]) => (
                        <optgroup key={team} label={team}>
                          {opts.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.department}</option>
                          ))}
                        </optgroup>
                      ))}
                  </select>
                )}
              </InfoField>
              <InfoField label={l.detail.fields.startDate}>
                <input type="date" disabled={readOnly} value={infoForm.start_date || ""} onChange={(e) => setField("start_date", e.target.value)} className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.owner}>
                {readOnly ? (
                  <span className="tm-info-readonly">{ownerName}</span>
                ) : (
                  <select
                    disabled={readOnly || !infoForm.associated_team}
                    value={infoForm.current_owner_id || ""}
                    onChange={(e) => setField("current_owner_id", e.target.value)}
                    className="tm-info-input"
                  >
                    <option value="">{l.common.select}</option>
                    {infoForm.current_owner_id
                      && !ownerOptions.some((m) => m.id === infoForm.current_owner_id) && (
                      <option value={infoForm.current_owner_id}>{ownerName}</option>
                    )}
                    {ownerOptions.map((m) => (
                      <option key={m.id} value={m.id}>{m.name} ({m.email})</option>
                    ))}
                  </select>
                )}
              </InfoField>
              <InfoField label={l.detail.fields.duration}>
                <span className="tm-info-readonly">{durationLabel}</span>
              </InfoField>
              <InfoField label={l.detail.fields.workHours}>
                <span className="tm-info-readonly">{task.work_hours_display || "—"}</span>
              </InfoField>
              <InfoField label={l.detail.fields.completionPct}>
                <span className="tm-info-readonly">{task.progress_pct ?? 0} %</span>
              </InfoField>
              <InfoField label={l.detail.fields.status}>
                <span className="tm-info-readonly">{task.status_label}</span>
              </InfoField>
              <InfoField label={l.detail.fields.recurrence}>
                <select disabled={readOnly} value={infoForm.recurrence || "None"} onChange={(e) => setField("recurrence", e.target.value)} className="tm-info-input">
                  {(meta?.recurrence_options || ["None"]).map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </InfoField>
              <InfoField label={l.detail.fields.dueDate}>
                <input type="date" disabled={readOnly} value={infoForm.due_date || ""} onChange={(e) => setField("due_date", e.target.value)} className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.component}>
                <select disabled={readOnly} value={infoForm.component || ""} onChange={(e) => setField("component", e.target.value)} className="tm-info-input">
                  <option value="">{l.common.select}</option>
                  {(meta?.components || []).map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </InfoField>
              <InfoField label={l.detail.fields.priority}>
                <select disabled={readOnly} value={infoForm.priority || "Medium"} onChange={(e) => setField("priority", e.target.value)} className="tm-info-input">
                  {(meta?.priorities || []).map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </InfoField>
              <InfoField label={l.detail.fields.fundAllocated}>
                <input type="number" step="0.01" disabled={readOnly} value={infoForm.fund_allocated_cr} onChange={(e) => setField("fund_allocated_cr", e.target.value)} className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.tags}>
                <input disabled={readOnly} value={infoForm.tags || ""} onChange={(e) => setField("tags", e.target.value)} placeholder="tag1, tag2" className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.fundsReleased}>
                <input type="number" step="0.01" disabled={readOnly} value={infoForm.funds_released_cr} onChange={(e) => setField("funds_released_cr", e.target.value)} className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.reminder}>
                <select disabled={readOnly} value={infoForm.reminder || "None"} onChange={(e) => setField("reminder", e.target.value)} className="tm-info-input">
                  <option value="None">None</option>
                  <option value="1 day before">1 day before</option>
                  <option value="3 days before">3 days before</option>
                  <option value="1 week before">1 week before</option>
                </select>
              </InfoField>
              <InfoField label={l.detail.fields.highCourtName}>
                <select disabled={readOnly} value={infoForm.high_court_name || ""} onChange={(e) => setField("high_court_name", e.target.value)} className="tm-info-input">
                  <option value="">{l.common.select}</option>
                  {(meta?.high_courts || []).map((hc) => <option key={hc} value={hc}>{hc}</option>)}
                </select>
              </InfoField>
              <InfoField label={l.detail.fields.billingType}>
                <select disabled={readOnly} value={infoForm.billing_type || "None"} onChange={(e) => setField("billing_type", e.target.value)} className="tm-info-input">
                  {(meta?.billing_types || ["None"]).map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </InfoField>
              <InfoField label={l.detail.fields.fundTarget}>
                <input type="number" step="0.01" disabled={readOnly} value={infoForm.fund_target_cr} onChange={(e) => setField("fund_target_cr", e.target.value)} className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.hardwareCount}>
                <input type="number" disabled={readOnly} value={infoForm.hardware_count} onChange={(e) => setField("hardware_count", e.target.value)} className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.fundsUtilised}>
                <input type="number" step="0.01" disabled={readOnly} value={infoForm.funds_utilised_cr} onChange={(e) => setField("funds_utilised_cr", e.target.value)} className="tm-info-input" />
              </InfoField>
              <InfoField label={l.detail.fields.utilisationPct}>
                <input type="number" step="0.01" disabled={readOnly} value={infoForm.utilisation_pct ?? task.utilisation_pct ?? ""} onChange={(e) => setField("utilisation_pct", e.target.value)} className="tm-info-input" />
              </InfoField>
              {!readOnly && (
                <div className="col-span-full flex justify-end pt-2">
                  <button type="button" onClick={saveTaskInfo} className="app-btn-primary text-xs">{l.detail.saveTaskInfo}</button>
                </div>
              )}
            </div>
          )}
        </section>

        <nav className="tm-detail-tabs">
          {TAB_DEFS.map(({ id: tabId, testId }) => (
            <button
              key={tabId}
              type="button"
              data-testid={testId}
              onClick={() => setTab(tabId)}
              className={`tm-detail-tab ${tab === tabId ? "is-active" : ""}`}
            >
              {l.detail.tabs[tabId]}
              {tabId === "subtasks" && allSubtasks.length > 0 && ` (${allSubtasks.length})`}
            </button>
          ))}
        </nav>

        <div className="tm-detail-tab-body">
          {tab === "subtasks" && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-slate-600">{l.detail.onlySubtasks}</span>
                {!readOnly && (
                  <button type="button" onClick={() => setSubtaskOpen(true)} className="app-btn-primary text-xs">
                    <Plus size={14} /> {l.detail.addSubtask}
                  </button>
                )}
              </div>
              <table className="tm-subtask-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Task Name</th>
                    <th>Status</th>
                    <th>Owner</th>
                    <th>Start Date</th>
                    <th>Due Date</th>
                    <th>Duration</th>
                    <th>Priority</th>
                  </tr>
                </thead>
                <tbody>
                  {allSubtasks.map((st, idx) => {
                    const days = daysUntil(st.due_date);
                    return (
                      <tr key={st.id} className={idx === 0 ? "tm-subtask-parent" : ""}>
                        <td className="font-mono text-xs">{st.task_code}</td>
                        <td>
                          <button type="button" className="text-[#003B73] text-left hover:underline" onClick={() => navigate(`/task-management/tasks/${st.id}`)}>
                            {idx > 0 && "↳ "}{st.title}
                          </button>
                        </td>
                        <td><StatusBadge status={st.status} label={st.status_label} /></td>
                        <td>{st.current_owner?.name || l.common.unassigned}</td>
                        <td>{fmtDate(st.start_date || st.sla_started_at || st.created_at) || "—"}</td>
                        <td>
                          {fmtDate(st.due_date) || "—"}
                          {days != null && days >= 0 && (
                            <span className="text-emerald-600 text-xs ml-1">({l.detail.daysToGo(days)})</span>
                          )}
                        </td>
                        <td>{st.duration_days != null ? `${st.duration_days} days` : "—"}</td>
                        <td><PriorityBadge priority={st.priority} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {tab === "comments" && (
            <div className="p-2">
              {!readOnly && (
                <div className="flex gap-2 mb-4">
                  <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder={l.detail.comments.placeholder} className="flex-1 px-3 py-2 border rounded-md text-sm" />
                  <button type="button" onClick={() => comment && act(() => taskApi.comment(id, comment).then(() => setComment("")), l.detail.toast.commentAdded)} className="app-btn-primary text-xs">{l.common.post}</button>
                </div>
              )}
              <ul className="space-y-3">
                {(data?.comments || []).map((c) => (
                  <li key={c.id} className="border-b border-slate-100 pb-3 text-sm">
                    <span className="font-medium">{c.user_email}</span>
                    <span className="text-slate-400 text-xs ml-2">{c.created_at ? String(c.created_at).slice(0, 16) : ""}</span>
                    <p className="text-slate-700 mt-1">{c.comment_text}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {tab === "logHours" && (
            <div className="tm-empty-tab">
              <Clock size={32} className="text-slate-300 mb-2" />
              <p>Work hours budget: {task.work_hours_display || "—"} (SLA hours)</p>
              <p className="text-sm text-slate-500 mt-1">Detailed time logging will be available in a future release.</p>
            </div>
          )}

          {tab === "evidence" && (
            <div className="p-2">
              {!readOnly && task.assigned_team_member_id === user.id && (
                <div className="mb-4">
                  <FileAttachments value={fileIds} onChange={setFileIds} />
                  <button type="button" onClick={uploadEvidence} disabled={!fileIds.length} data-testid="tm-evidence-upload-btn" className="mt-2 app-btn-primary text-xs">{l.detail.evidence.upload}</button>
                </div>
              )}
              <ul className="space-y-3">
                {(data?.evidence || []).map((ev) => (
                  <li key={ev.id} className="border border-slate-200 rounded-md p-3 text-sm">
                    <div className="font-medium">v{ev.version} · {ev.evidence_type} · {ev.verification_status}</div>
                    <div className="text-slate-500">{ev.file_name || ev.description}</div>
                    {ev.file_id && (
                      <a href={`${api.defaults.baseURL}/files/${ev.file_id}`} target="_blank" rel="noreferrer" className="text-[#003B73] text-xs">{l.common.download}</a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {tab === "dependency" && (
            <div className="tm-empty-tab text-sm space-y-2">
              <p><strong>Source type:</strong> {task.source_type || "—"}</p>
              <p><strong>Source reference:</strong> {task.source_reference_id || "—"}</p>
              {task.parent_task_id && (
                <p><strong>Parent task:</strong> linked</p>
              )}
            </div>
          )}

          {tab === "statusTimeline" && (
            <ul className="space-y-3">
              {(data?.audit_log || []).map((a) => (
                <li key={a.id} className="tm-timeline-item">
                  <div className="text-xs text-slate-500">{a.performed_at ? String(a.performed_at).slice(0, 19) : ""}</div>
                  <div className="font-medium text-sm">{a.action}</div>
                  <div className="text-xs text-slate-600">{a.performed_by_email}</div>
                </li>
              ))}
            </ul>
          )}

          {tab === "issues" && (
            <div className="tm-empty-tab text-sm text-slate-500">No linked issues for this task.</div>
          )}

          {tab === "activity" && (
            <ul className="space-y-3">
              {activityItems.map((item, i) => (
                <li key={i} className="border-l-2 border-slate-200 pl-3 text-sm">
                  <div className="text-xs text-slate-500">{item.at ? String(item.at).slice(0, 19) : ""}</div>
                  <div className="font-medium capitalize">{item.type}: {item.title}</div>
                  {item.body && <div className="text-slate-600">{item.body}</div>}
                </li>
              ))}
            </ul>
          )}

          {tab === "assignment" && (
            <div className="text-sm space-y-2 p-2">
              <p>{l.detail.assignmentCard.lead(task.team_lead?.name || "—")}</p>
              <p>{l.detail.assignmentCard.member(task.team_member?.name || "—")}</p>
              {!readOnly && <TaskAssignmentPanel taskId={id} task={task} onUpdated={refetch} />}
            </div>
          )}

          {tab === "approval" && (
            <div>
              {task.status === "SUBMITTED_FOR_APPROVAL" && perms.canVerify && !readOnly && (
                <div className="p-4 border-b border-slate-100 space-y-2" data-testid="tm-verification-checklist">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{l.detail.checklist.title}</div>
                  {CHECKLIST_KEYS.map((key) => (
                    <label key={key} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" data-testid={`tm-checklist-${key}`} checked={checklist[key]} onChange={(e) => setChecklist((c) => ({ ...c, [key]: e.target.checked }))} />
                      {l.detail.checklist[key]}
                    </label>
                  ))}
                </div>
              )}
              <ul className="p-4 space-y-2 text-sm">
                {(data?.approvals || []).map((a) => (
                  <li key={a.id} className="border-l-2 border-violet-300 pl-3">{a.approval_level}: {a.decision} — {a.remarks || "—"}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      <TaskCreateDialog open={subtaskOpen} onOpenChange={setSubtaskOpen} parentTaskId={id} onCreated={() => refetch()} />
    </div>
  );
}

function ActionBtn({ children, onClick, danger, testId }) {
  return (
    <button type="button" data-testid={testId} onClick={onClick}
      className={`px-3 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider ${
        danger ? "bg-red-600 hover:bg-red-700 text-white" : "bg-[#003B73] hover:bg-[#002B54] text-white"
      }`}>
      {children}
    </button>
  );
}
