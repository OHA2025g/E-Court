import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import Card from "@/components/Card";
import ScrollRegion from "@/components/ui/ScrollRegion";
import { TID } from "@/lib/testIds";
import { SelectField } from "@/pages/PhysicalTracker";
import { useAdminLabels } from "@/lib/useAdminLabels";
import { useTranslation } from "react-i18next";

const TRACKERS = ["physical", "financial", "outcome", "users", "pmu_tasks", "dpr", "master", "ijuris"];
const ACTIONS = ["create", "update", "delete"];

function val(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v).slice(0, 80);
  return String(v).slice(0, 80);
}

export default function AuditLogs() {
  const l = useAdminLabels().audit;
  const { t } = useTranslation();
  const [tracker, setTracker] = useState("");
  const [action, setAction] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["audit", tracker, action],
    queryFn: () => api.get("/audit", { params: { tracker: tracker || undefined, action: action || undefined, limit: 300 } }).then(r => r.data),
  });

  return (
    <div className="space-y-6">
      <Card title={l.title} subtitle={l.subtitle}>
        <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <SelectField label={l.fieldTracker} value={tracker} onChange={setTracker} options={TRACKERS} />
          <SelectField label={l.fieldAction} value={action} onChange={setAction} options={ACTIONS} />
          <div className="text-xs text-slate-500 flex items-end">
            {isLoading ? t("common.loading") : l.rowsLoaded(data?.length || 0)}
          </div>
        </div>
      </Card>

      <Card>
        <ScrollRegion className="overflow-x-auto max-h-[640px]" label={l.tableScroll} data-testid={TID.auditTable}>
          <table className="dense-table w-full">
            <thead className="sticky top-0"><tr>
              <th>{l.colTimestamp}</th><th>{l.colUser}</th><th>{l.colRole}</th><th>{l.colTracker}</th><th>{l.colAction}</th>
              <th>{l.colHighCourt}</th><th>{l.colPeriod}</th><th>{l.colChanges}</th>
            </tr></thead>
            <tbody>
              {(data || []).map(r => (
                <tr key={r.id}>
                  <td className="font-mono text-xs">{r.timestamp}</td>
                  <td>{r.user_email}</td>
                  <td>{r.role}</td>
                  <td>{r.tracker}</td>
                  <td>{r.action}</td>
                  <td>{r.high_court || "—"}</td>
                  <td>{r.reporting_period || "—"}</td>
                  <td className="max-w-md">
                    {(r.changes || []).slice(0, 3).map((c, i) => (
                      <div key={i} className="text-xs">
                        <span className="font-semibold text-slate-700">{c.field}:</span>{" "}
                        <span className="text-red-600 line-through">{val(c.old)}</span>{" → "}
                        <span className="text-emerald-700">{val(c.new)}</span>
                      </div>
                    ))}
                    {(r.changes || []).length > 3 && <div className="text-[10px] text-slate-400">{l.moreChanges(r.changes.length - 3)}</div>}
                  </td>
                </tr>
              ))}
              {!isLoading && (data?.length || 0) === 0 && (
                <tr><td colSpan={8} className="text-center text-slate-400 py-12">{l.noLogs}</td></tr>
              )}
            </tbody>
          </table>
        </ScrollRegion>
      </Card>
    </div>
  );
}
