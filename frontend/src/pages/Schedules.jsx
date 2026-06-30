import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { toast } from "sonner";
import { Play, Clock, EnvelopeSimple, FilePdf, Plus, Trash, WebhooksLogo } from "@phosphor-icons/react";
import { BACKEND_URL } from "@/lib/api";
import { TextField } from "@/pages/PhysicalTracker";
import { useSchedulesLabels } from "@/lib/useSchedulesLabels";

function WebhooksCard() {
  const labels = useSchedulesLabels();
  const qc = useQueryClient();
  const hooks = useQuery({ queryKey: ["webhooks"], queryFn: () => api.get("/admin/webhooks").then(r => r.data) });
  const outbox = useQuery({ queryKey: ["webhook-outbox"], queryFn: () => api.get("/admin/webhook-outbox").then(r => r.data) });
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [events, setEvents] = useState("rag_change,submission_status");
  const [busy, setBusy] = useState(false);

  async function create(e) {
    e.preventDefault();
    if (!name.trim() || !url.trim()) {
      toast.error(labels.nameUrlRequired);
      return;
    }
    setBusy(true);
    try {
      await api.post("/admin/webhooks", {
        name: name.trim(),
        url: url.trim(),
        secret: secret.trim() || null,
        events: events.split(",").map((s) => s.trim()).filter(Boolean),
        active: true,
      });
      toast.success(labels.webhookCreated);
      setName(""); setUrl(""); setSecret("");
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!window.confirm(labels.deleteWebhookConfirm)) return;
    try {
      await api.delete(`/admin/webhooks/${id}`);
      toast.success(labels.deleted);
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  }

  return (
    <Card title={labels.webhooksTitle} subtitle={labels.webhooksSubtitle}
      action={<WebhooksLogo size={18} className="text-slate-400" />}>
      <form onSubmit={create} className="p-4 border-b border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <TextField label={labels.fieldName} value={name} onChange={setName} />
        <TextField label={labels.fieldUrl} value={url} onChange={setUrl} />
        <TextField label={labels.fieldSecret} value={secret} onChange={setSecret} type="password" />
        <TextField label={labels.fieldEvents} value={events} onChange={setEvents} />
        <div className="sm:col-span-2">
          <button type="submit" disabled={busy}
            className="inline-flex items-center gap-1.5 bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-3 py-1.5 rounded-sm uppercase tracking-wider text-[11px]">
            <Plus size={14} /> {labels.addWebhook}
          </button>
        </div>
      </form>
      <ScrollRegion className="overflow-x-auto max-h-[240px]" label={labels.webhooksScroll}>
        <table className="dense-table w-full">
          <thead><tr><th>{labels.colWebhookName}</th><th>{labels.colWebhookUrl}</th><th>{labels.colWebhookEvents}</th><th>{labels.colWebhookActive}</th><th></th></tr></thead>
          <tbody>
            {(hooks.data || []).map((h) => (
              <tr key={h.id}>
                <td>{h.name}</td>
                <td className="font-mono text-xs max-w-xs truncate">{h.url}</td>
                <td className="text-xs">{(h.events || []).join(", ")}</td>
                <td>{h.active ? labels.yes : labels.no}</td>
                <td>
                  <button type="button" onClick={() => remove(h.id)} className="text-red-600 hover:text-red-800" aria-label={labels.deleteWebhookConfirm}>
                    <Trash size={14} />
                  </button>
                </td>
              </tr>
            ))}
            {(hooks.data?.length || 0) === 0 && !hooks.isLoading && (
              <tr><td colSpan={5} className="text-center text-slate-400 py-6">{labels.noWebhooks}</td></tr>
            )}
          </tbody>
        </table>
      </ScrollRegion>
      <div className="p-4 border-t border-slate-100">
        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">{labels.recentOutbox}</div>
        <ScrollRegion className="overflow-x-auto max-h-[180px]" label={labels.webhookOutboxScroll}>
          <table className="dense-table w-full">
            <thead><tr><th>{labels.colTime}</th><th>{labels.colEvent}</th><th>{labels.colStatus}</th><th>{labels.colHttp}</th></tr></thead>
            <tbody>
              {(outbox.data || []).slice(0, 20).map((o) => (
                <tr key={o.id}>
                  <td className="font-mono text-xs">{o.ts?.slice(0, 19).replace("T", " ")}</td>
                  <td>{o.event}</td>
                  <td>{o.status}</td>
                  <td className="text-xs">{o.http_status ?? "—"}</td>
                </tr>
              ))}
              {(outbox.data?.length || 0) === 0 && (
                <tr><td colSpan={4} className="text-center text-slate-400 py-4">{labels.webhookOutboxEmpty}</td></tr>
              )}
            </tbody>
          </table>
        </ScrollRegion>
      </div>
    </Card>
  );
}

export default function Schedules() {
  const labels = useSchedulesLabels();
  const qc = useQueryClient();
  const jobs = useQuery({ queryKey: ["sched-jobs"], queryFn: () => api.get("/admin/scheduled-jobs").then(r => r.data) });
  const deliveries = useQuery({ queryKey: ["sched-deliveries"], queryFn: () => api.get("/admin/scheduled-deliveries").then(r => r.data) });
  const outbox = useQuery({ queryKey: ["outbox"], queryFn: () => api.get("/email-outbox").then(r => r.data) });
  const worker = useQuery({ queryKey: ["email-worker"], queryFn: () => api.get("/admin/email-worker/status").then(r => r.data) });

  async function runNow() {
    try {
      await api.post("/admin/scheduled-deliveries/run-now");
      toast.success(labels.briefTriggered);
      qc.invalidateQueries({ queryKey: ["sched-deliveries"] });
      qc.invalidateQueries({ queryKey: ["outbox"] });
      qc.invalidateQueries({ queryKey: ["notif"] });
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  }

  async function drainOutbox() {
    try {
      const r = await api.post("/admin/email-outbox/drain");
      toast.success(labels.drainSuccess(r.data.sent, r.data.failed));
      qc.invalidateQueries({ queryKey: ["outbox"] });
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  }

  return (
    <div className="space-y-6">
      <Card title={labels.jobsTitle} subtitle={labels.jobsSubtitle}>
        <div className="p-4">
          <table className="dense-table w-full">
            <thead><tr><th>{labels.colJobName}</th><th>{labels.colNextRun}</th><th>{labels.colTrigger}</th><th></th></tr></thead>
            <tbody>
              {(jobs.data || []).map(j => (
                <tr key={j.id}>
                  <td><Clock size={14} className="inline mr-1 text-slate-500" />{j.name}</td>
                  <td className="font-mono text-xs">{j.next_run_time?.replace("T", " ").slice(0, 19) || "—"}</td>
                  <td className="font-mono text-[11px] text-slate-500">{j.trigger}</td>
                  <td>
                    {j.id === "weekly_cabinet_brief" && (
                      <button data-testid="run-cabinet-now" onClick={runNow}
                        className="inline-flex items-center gap-1.5 bg-[#003B73] hover:bg-[#002B54] text-white px-2.5 py-1 rounded-sm uppercase tracking-wider text-[10px]">
                        <Play size={12} /> {labels.runNow}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {(jobs.data?.length || 0) === 0 && <tr><td colSpan={4} className="text-center text-slate-400 py-6">{labels.noJobs}</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={labels.deliveriesTitle}>
        <ScrollRegion className="overflow-x-auto max-h-[300px]" label={labels.deliveriesScroll}>
          <table className="dense-table w-full">
            <thead><tr><th>{labels.colTimestamp}</th><th>{labels.colJob}</th><th>{labels.colPeriod}</th><th>{labels.colRecipients}</th><th>{labels.colStatus}</th><th></th></tr></thead>
            <tbody>
              {(deliveries.data || []).map(d => (
                <tr key={d.id}>
                  <td className="font-mono text-xs">{d.ts?.slice(0, 19).replace("T", " ")}</td>
                  <td>{d.job}</td>
                  <td>{d.period_label || d.period || "—"}</td>
                  <td className="text-xs text-slate-500">{(d.recipients || []).join(", ") || "—"}</td>
                  <td>{d.status}</td>
                  <td>
                    {d.pdf_size_bytes > 0 && (
                      <a
                        href={`${BACKEND_URL}/api/admin/scheduled-deliveries/${d.id}/pdf`}
                        data-testid={`download-brief-${d.id}`}
                        className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-[#003B73] hover:underline"
                      >
                        <FilePdf size={12} /> PDF
                      </a>
                    )}
                  </td>
                </tr>
              ))}
              {(deliveries.data?.length || 0) === 0 && <tr><td colSpan={6} className="text-center text-slate-400 py-6">{labels.noDeliveries}</td></tr>}
            </tbody>
          </table>
        </ScrollRegion>
      </Card>

      <Card title={labels.outboxTitle}
        subtitle={worker.data?.smtp_configured ? labels.outboxSubtitleSmtp : labels.outboxSubtitleMock}
        action={worker.data?.smtp_configured ? (
          <button
            type="button"
            data-testid="drain-outbox-btn"
            onClick={drainOutbox}
            className="inline-flex items-center gap-1.5 bg-[#003B73] hover:bg-[#002B54] text-white px-2.5 py-1 rounded-sm uppercase tracking-wider text-[10px]"
          >
            {labels.drainNow}
          </button>
        ) : null}>
        <ScrollRegion className="overflow-x-auto max-h-[360px]" label={labels.outboxScroll}>
          <table className="dense-table w-full">
            <thead><tr><th>{labels.colTimestamp}</th><th>{labels.colTo}</th><th>{labels.colSubject}</th><th>{labels.colStatus}</th></tr></thead>
            <tbody>
              {(outbox.data || []).map(e => (
                <tr key={e.id}>
                  <td className="font-mono text-xs">{e.ts?.slice(0, 19).replace("T", " ")}</td>
                  <td><EnvelopeSimple size={12} className="inline mr-1 text-slate-500" />{e.to}</td>
                  <td>{e.subject}</td>
                  <td>{e.status}</td>
                </tr>
              ))}
              {(outbox.data?.length || 0) === 0 && <tr><td colSpan={4} className="text-center text-slate-400 py-6">{labels.outboxEmpty}</td></tr>}
            </tbody>
          </table>
        </ScrollRegion>
      </Card>

      <WebhooksCard />
    </div>
  );
}
