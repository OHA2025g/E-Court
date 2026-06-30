import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { useAdminLabels } from "@/lib/useAdminLabels";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import RagBadge from "@/components/RagBadge";
import { TID } from "@/lib/testIds";
import { toast } from "sonner";
import { PlugCharging, Play } from "@phosphor-icons/react";
import { SelectField } from "@/pages/PhysicalTracker";

const SAMPLE_PHYS = {
  high_court: "Allahabad",
  component: "e-Sewa Kendras",
  indicator: "No of e-sewa kendras in court complexes (in Absolute Count)",
  reporting_period: "2026-06",
  target: 400,
  achieved: 200,
  remarks: "Auto-ingested from iJuris",
};
const SAMPLE_FIN = {
  high_court: "Allahabad",
  component: "Paperless Courts",
  reporting_period: "2026-06",
  fund_target: 14.0,
  fund_allocated: 13.5,
  fund_released: 10.5,
  fund_utilized: 8.0,
  remarks: "iJuris ingestion",
};
const SAMPLE_OUT = {
  high_court: "Allahabad",
  granularity: "District",
  subject: "eFiling",
  kpi_id: "1.01",
  kpi: "How many advocates are on-boarded",
  outcome_type: "Absolute",
  value_type: "Count",
  value: 600,
  reporting_period: "2026-06",
};

export default function IjurisIntegration() {
  const { ijuris: l } = useAdminLabels();
  const qc = useQueryClient();
  const [recordType, setRecordType] = useState("physical");
  const [payload, setPayload] = useState(JSON.stringify(SAMPLE_PHYS, null, 2));
  const [busy, setBusy] = useState(false);

  const logs = useQuery({ queryKey: ["ijuris"], queryFn: () => api.get("/ijuris/logs").then(r => r.data) });

  const recordTypeOptions = [
    { label: l.typePhysical, value: "physical" },
    { label: l.typeFinancial, value: "financial" },
    { label: l.typeOutcome, value: "outcome" },
  ];

  function loadSample(rt) {
    setRecordType(rt);
    setPayload(JSON.stringify(rt === "physical" ? SAMPLE_PHYS : rt === "financial" ? SAMPLE_FIN : SAMPLE_OUT, null, 2));
  }

  async function ingest() {
    setBusy(true);
    try {
      const parsed = JSON.parse(payload);
      const r = await api.post("/ijuris/ingest", { source: "iJuris", record_type: recordType, payload: parsed });
      if (r.data.status === "accepted") toast.success(r.data.message || l.ingested);
      else toast.error(r.data.message || l.rejected);
      qc.invalidateQueries({ queryKey: ["ijuris"] });
      qc.invalidateQueries({ queryKey: ["physical"] });
      qc.invalidateQueries({ queryKey: ["financial"] });
      qc.invalidateQueries({ queryKey: ["outcome"] });
      qc.invalidateQueries({ queryKey: ["dash-summary"] });
    } catch (e) {
      toast.error(e?.response?.data?.detail ? formatApiError(e.response.data.detail) : l.invalidJson(e.message));
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <Card title={l.title}
        subtitle={l.subtitle}>
        <div className="p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex items-center gap-3">
              <SelectField label={l.recordType} value={recordType} onChange={loadSample}
                options={recordTypeOptions} />
              <div className="self-end text-xs text-slate-500">{l.editJsonHint}</div>
            </div>
            <textarea
              data-testid={TID.ijurisPayload}
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              rows={16}
              className="w-full font-mono text-xs px-3 py-2 border border-slate-300 rounded-sm bg-white focus:outline-none focus:border-[#003B73]"
            />
            <button
              data-testid={TID.ijurisIngestBtn}
              disabled={busy}
              onClick={ingest}
              className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2"
            >
              <Play size={16} /> {busy ? l.ingesting : l.runIngestion}
            </button>
          </div>
          <div className="space-y-3">
            <Card title={l.statusTitle}>
              <div className="p-4 text-sm space-y-2">
                <div className="flex items-center gap-2">
                  <PlugCharging size={18} className="text-amber-500" />
                  <span className="font-semibold">{l.pendingAccess}</span>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {l.statusDesc}
                </p>
                <div className="text-xs">
                  <div className="text-slate-500 uppercase tracking-wider text-[10px] mt-2">{l.endpointLabel}</div>
                  <code className="font-mono text-[11px]">POST /api/ijuris/ingest</code>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </Card>

      <Card title={l.logTitle} subtitle={l.logSubtitle}>
        <ScrollRegion className="overflow-x-auto max-h-[400px]" label={l.logScroll}>
          <table className="dense-table w-full">
            <thead><tr>
              <th>{l.colTimestamp}</th><th>{l.colType}</th><th>{l.colStatus}</th><th>{l.colIngestedBy}</th><th>{l.colMessage}</th>
            </tr></thead>
            <tbody>
              {(logs.data || []).map(log => (
                <tr key={log.id}>
                  <td className="font-mono text-xs">{log.ts}</td>
                  <td>{log.record_type}</td>
                  <td><RagBadge status={log.status === "accepted" ? "GREEN" : "RED"} label={log.status} /></td>
                  <td>{log.ingested_by}</td>
                  <td className="text-xs text-slate-600 max-w-md">{log.message || "—"}</td>
                </tr>
              ))}
              {(logs.data?.length || 0) === 0 && (
                <tr><td colSpan={5} className="text-center text-slate-400 py-8">{l.noAttempts}</td></tr>
              )}
            </tbody>
          </table>
        </ScrollRegion>
      </Card>
    </div>
  );
}
