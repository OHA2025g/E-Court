import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import RagBadge from "@/components/RagBadge";
import { toast } from "sonner";
import { PaperPlaneTilt, CheckCircle, ArrowUUpLeft, Warning, XCircle, Clock } from "@phosphor-icons/react";
import { SelectField, TextField } from "@/pages/PhysicalTracker";

const STATUS_RAG = { Submitted: "AMBER", Approved: "GREEN", Returned: "RED", Draft: "NA", Open: "NA", NotSubmitted: "RED" };

export default function Submissions() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const isAdmin = user?.role === "Admin";
  const canAct = user?.role !== "Viewer";
  const [period, setPeriod] = useState("");
  const [hc, setHc] = useState(user?.role === "CPC" ? user.high_court : "");
  const [note, setNote] = useState("");
  const [reopenReason, setReopenReason] = useState("");
  const [busy, setBusy] = useState(false);

  const hcs = useQuery({ queryKey: ["hcs"], queryFn: () => api.get("/master/high-courts").then(r => r.data) });
  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get("/master/periods").then(r => r.data) });
  const subs = useQuery({ queryKey: ["submissions"], queryFn: () => api.get("/submissions").then(r => r.data) });
  const overdue = useQuery({ queryKey: ["overdue"], queryFn: () => api.get("/submissions/overdue").then(r => r.data) });
  const sla = useQuery({ queryKey: ["submissions-sla"], queryFn: () => api.get("/submissions/sla").then(r => r.data) });
  const reopenReqs = useQuery({
    queryKey: ["reopen-requests"],
    queryFn: () => api.get("/submissions/reopen-requests").then(r => r.data),
    enabled: canAct,
  });

  async function action(endpoint, body) {
    setBusy(true);
    try {
      const r = await api.post(endpoint, body);
      toast.success(`Status: ${r.data.status || r.data.ok ? "OK" : "Updated"}`);
      qc.invalidateQueries({ queryKey: ["submissions"] });
      qc.invalidateQueries({ queryKey: ["overdue"] });
      qc.invalidateQueries({ queryKey: ["submissions-sla"] });
      qc.invalidateQueries({ queryKey: ["reopen-requests"] });
      qc.invalidateQueries({ queryKey: ["notif"] });
      setNote("");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }

  async function reopenRequest() {
    if (!hc || !period || !reopenReason.trim()) {
      toast.error("High Court, period and reason required");
      return;
    }
    setBusy(true);
    try {
      await api.post("/submissions/reopen-request", {
        high_court: hc,
        reporting_period: period,
        reason: reopenReason.trim(),
      });
      toast.success("Re-open request submitted");
      setReopenReason("");
      qc.invalidateQueries({ queryKey: ["reopen-requests"] });
      qc.invalidateQueries({ queryKey: ["notif"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  async function reopenDecision(reqId, approve) {
    setBusy(true);
    try {
      await api.post(`/submissions/reopen-request/${reqId}/${approve ? "approve" : "deny"}`, { note: note || null });
      toast.success(approve ? "Re-open approved" : "Re-open denied");
      setNote("");
      qc.invalidateQueries({ queryKey: ["reopen-requests"] });
      qc.invalidateQueries({ queryKey: ["submissions"] });
      qc.invalidateQueries({ queryKey: ["notif"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Submit / Action" subtitle="CPC submits a period for review. Admin approves or returns." className="lg:col-span-2">
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <SelectField label="High Court" value={hc} onChange={setHc}
              options={(hcs.data || []).map(h => h.name)}
              disabled={user?.role === "CPC"} testid="sub-hc-select" />
            <SelectField label="Reporting Month" value={period} onChange={setPeriod}
              options={(periods.data || []).filter(p => !p.is_baseline).map(p => ({ label: p.label, value: p.period }))}
              testid="sub-period-select" />
            <div className="sm:col-span-2">
              <TextField label="Note / Reason (for Return)" value={note} onChange={setNote} testid="sub-note" />
            </div>
            <div className="sm:col-span-2 flex flex-wrap gap-2">
              <button data-testid="sub-submit-btn" disabled={busy || !hc || !period || !canAct}
                onClick={() => action("/submissions/submit", { high_court: hc, reporting_period: period, note: note || null })}
                className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
                <PaperPlaneTilt size={14} /> Submit
              </button>
              {isAdmin && (
                <>
                  <button data-testid="sub-approve-btn" disabled={busy || !hc || !period}
                    onClick={() => action("/submissions/approve", { high_court: hc, reporting_period: period, note: note || null })}
                    className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
                    <CheckCircle size={14} /> Approve
                  </button>
                  <button data-testid="sub-return-btn" disabled={busy || !hc || !period || !note}
                    onClick={() => action("/submissions/return", { high_court: hc, reporting_period: period, note })}
                    className="bg-amber-600 hover:bg-amber-700 disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
                    <ArrowUUpLeft size={14} /> Return
                  </button>
                </>
              )}
            </div>
          </div>
        </Card>

        <Card title="Overdue This Period"
          subtitle={overdue.data?.period ? `${overdue.data.overdue?.length || 0} HCs not yet submitted for ${overdue.data.period}` : "No active period"}>
          <ScrollRegion className="p-4 max-h-72 overflow-y-auto" label={t("submissions.overdueScroll")} data-testid="sub-overdue">
            {(overdue.data?.overdue || []).length === 0 ? (
              <div className="text-xs text-slate-400">All caught up.</div>
            ) : (
              <ul className="space-y-1 text-sm">
                {(overdue.data.overdue || []).map(h => (
                  <li key={h} className="flex items-center justify-between border-b border-slate-100 pb-1">
                    <span>{h}</span>
                    <Warning size={14} className="text-amber-500" />
                  </li>
                ))}
              </ul>
            )}
          </ScrollRegion>
        </Card>
      </div>

      <Card title={t("submissions.slaTitle")} subtitle={sla.data?.period ? `Period ${sla.data.period} · due day ${sla.data.sla_due_day}` : "Loading SLA…"}>
        <ScrollRegion className="overflow-x-auto max-h-[360px]" label={t("submissions.slaScroll")} data-testid="sub-sla-table">
          <table className="dense-table w-full">
            <thead><tr>
              <th>High Court</th><th>Period</th><th>Status</th>
              <th>SLA Due</th><th>Days Left</th><th>Delinquent</th>
            </tr></thead>
            <tbody>
              {(sla.data?.rows || []).map((r) => (
                <tr key={r.high_court}>
                  <td className="font-medium text-slate-700">{r.high_court}</td>
                  <td>{r.reporting_period}</td>
                  <td><RagBadge status={STATUS_RAG[r.status] || "NA"} label={r.status} /></td>
                  <td className="font-mono text-xs">{r.sla_due?.slice(0, 10) || "—"}</td>
                  <td className="text-right tabular-nums">{r.days_remaining ?? "—"}</td>
                  <td>{r.delinquent ? <Warning size={14} className="text-red-600" weight="fill" /> : "—"}</td>
                </tr>
              ))}
              {!sla.isLoading && (sla.data?.rows?.length || 0) === 0 && (
                <tr><td colSpan={6} className="text-center text-slate-400 py-8">No SLA data.</td></tr>
              )}
            </tbody>
          </table>
        </ScrollRegion>
      </Card>

      {canAct && (
        <Card title={t("submissions.reopenRequest")} subtitle="Request a correction window for an approved submission">
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <SelectField label="High Court" value={hc} onChange={setHc}
              options={(hcs.data || []).map(h => h.name)}
              disabled={user?.role === "CPC"} />
            <SelectField label="Reporting Month" value={period} onChange={setPeriod}
              options={(periods.data || []).filter(p => !p.is_baseline).map(p => ({ label: p.label, value: p.period }))} />
            <div className="sm:col-span-2">
              <TextField label={t("submissions.reopenReason")} value={reopenReason} onChange={setReopenReason} />
            </div>
            <div className="sm:col-span-2">
              <button type="button" disabled={busy || !hc || !period || !reopenReason.trim()} onClick={reopenRequest}
                className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
                <Clock size={14} /> {t("submissions.reopenRequest")}
              </button>
            </div>
          </div>
        </Card>
      )}

      {(reopenReqs.data?.length || 0) > 0 && (
        <Card title="Re-open Requests" subtitle={`${reopenReqs.data?.length || 0} request(s)`}>
          <ScrollRegion className="overflow-x-auto max-h-[320px]" label={t("submissions.reopenScroll")} data-testid="reopen-requests-table">
            <table className="dense-table w-full">
              <thead><tr>
                <th>High Court</th><th>Period</th><th>Reason</th><th>Status</th><th>Requested</th>
                {isAdmin && <th>Actions</th>}
              </tr></thead>
              <tbody>
                {(reopenReqs.data || []).map((r) => (
                  <tr key={r.id}>
                    <td>{r.high_court}</td>
                    <td>{r.reporting_period}</td>
                    <td className="text-xs text-slate-600 max-w-xs truncate">{r.reason}</td>
                    <td>{r.status}</td>
                    <td className="font-mono text-xs">{r.requested_by} · {r.ts?.slice(0, 16)}</td>
                    {isAdmin && (
                      <td>
                        {r.status === "Pending" ? (
                          <div className="flex gap-2">
                            <button type="button" disabled={busy} onClick={() => reopenDecision(r.id, true)}
                              className="text-emerald-700 hover:underline text-xs uppercase tracking-wider inline-flex items-center gap-1">
                              <CheckCircle size={12} /> Approve
                            </button>
                            <button type="button" disabled={busy} onClick={() => reopenDecision(r.id, false)}
                              className="text-red-700 hover:underline text-xs uppercase tracking-wider inline-flex items-center gap-1">
                              <XCircle size={12} /> Deny
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">{r.decided_by || "—"}</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </Card>
      )}

      <Card title="Submission Log" subtitle={`${subs.data?.length || 0} submission record(s)`}>
        <ScrollRegion className="overflow-x-auto max-h-[520px]" label={t("submissions.statusScroll")} data-testid="submissions-table">
          <table className="dense-table w-full">
            <thead><tr>
              <th>High Court</th><th>Period</th><th>Status</th>
              <th>Dashboard</th><th>Entries</th><th>Submitted</th><th>By</th>
              <th>Approved/Returned</th><th>Note</th>
            </tr></thead>
            <tbody>
              {(subs.data || []).map(s => (
                <tr key={s.id}>
                  <td className="font-medium text-slate-700">{s.high_court}</td>
                  <td>{s.reporting_period}</td>
                  <td><RagBadge status={STATUS_RAG[s.status] || "NA"} label={s.status} /></td>
                  <td>
                    {s.status !== "Approved" && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-[10px] font-semibold uppercase tracking-wider bg-slate-200 text-slate-700 border border-slate-300">
                        {t("submissions.dashboardExcluded")}
                      </span>
                    )}
                  </td>
                  <td className="text-right">{s.entry_count || 0}</td>
                  <td className="font-mono text-xs">{s.submitted_at?.slice(0, 16) || "—"}</td>
                  <td>{s.submitted_by || "—"}</td>
                  <td className="font-mono text-xs">
                    {s.approved_at ? `✓ ${s.approved_by} · ${s.approved_at.slice(0, 16)}`
                      : s.returned_at ? `↩ ${s.returned_by} · ${s.returned_at.slice(0, 16)}` : "—"}
                  </td>
                  <td className="text-slate-500 text-xs max-w-md truncate">{s.return_reason || s.approval_note || s.note || "—"}</td>
                </tr>
              ))}
              {(subs.data?.length || 0) === 0 && (
                <tr><td colSpan={9} className="text-center text-slate-400 py-12">No submissions yet.</td></tr>
              )}
            </tbody>
          </table>
        </ScrollRegion>
      </Card>
    </div>
  );
}
