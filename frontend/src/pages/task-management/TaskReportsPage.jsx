import React from "react";
import { useQuery } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { BACKEND_URL } from "@/lib/api";
import Card from "@/components/Card";
import { TaskKpiGrid } from "@/components/task-management/TaskManagementLayout";
import { DownloadSimple, FilePdf, FileXls } from "@phosphor-icons/react";

export default function TaskReportsPage() {
  const l = useTaskLabels();
  const { data, isLoading } = useQuery({ queryKey: ["tm-reports"], queryFn: taskApi.reportSummary });
  const s = data || {};

  function exportUrl(format) {
    return `${BACKEND_URL}/api/tasks/export?format=${format}`;
  }

  if (isLoading) return <div className="text-slate-500">{l.reports.loading}</div>;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-xl font-semibold text-slate-900 mb-2">{l.reports.title}</h1>
          <p className="text-sm text-slate-500">{l.reports.subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            data-testid="tm-reports-export-csv"
            href={exportUrl("csv")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 rounded-sm text-sm hover:bg-slate-50"
          >
            <DownloadSimple size={16} /> {l.common.exportCsv}
          </a>
          <a
            data-testid="tm-reports-export-xlsx"
            href={exportUrl("xlsx")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 rounded-sm text-sm hover:bg-slate-50"
          >
            <FileXls size={16} /> {l.common.exportXlsx}
          </a>
          <a
            data-testid="tm-reports-export-pdf"
            href={exportUrl("pdf")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 rounded-sm text-sm hover:bg-slate-50"
          >
            <FilePdf size={16} /> {l.common.exportPdf}
          </a>
        </div>
      </div>
      <TaskKpiGrid items={[
        { label: l.reports.kpiTotal, value: s.total },
        { label: l.reports.kpiSlaBreached, value: s.sla_breached, accent: "border-l-red-500" },
        { label: l.reports.kpiPending, value: s.submitted_approval, accent: "border-l-violet-500" },
        { label: l.reports.kpiRework, value: s.rework_required, accent: "border-l-orange-500" },
        { label: l.reports.kpiEscalated, value: s.escalated, accent: "border-l-red-500" },
        { label: l.reports.kpiClosed, value: s.closed_this_month, accent: "border-l-emerald-500" },
      ]} />
      <div className="grid md:grid-cols-2 gap-6">
        <Card title={l.reports.byStatus}>
          <ul className="p-4 space-y-1 text-sm">
            {(s.by_status || []).map((r) => (
              <li key={r.key} className="flex justify-between"><span>{r.key}</span><strong>{r.count}</strong></li>
            ))}
          </ul>
        </Card>
        <Card title={l.reports.byPriority}>
          <ul className="p-4 space-y-1 text-sm">
            {(s.by_priority || []).map((r) => (
              <li key={r.key} className="flex justify-between"><span>{r.key}</span><strong>{r.count}</strong></li>
            ))}
          </ul>
        </Card>
        <Card title={l.reports.byModule} className="md:col-span-2">
          <ul className="p-4 space-y-1 text-sm">
            {(s.by_module || []).map((r) => (
              <li key={r.key} className="flex justify-between"><span>{r.key}</span><strong>{r.count}</strong></li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
