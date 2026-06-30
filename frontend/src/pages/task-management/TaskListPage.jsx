import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { taskApi } from "@/lib/taskApi";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { taskPermissions } from "@/lib/taskPermissions";
import { useAuth } from "@/lib/auth";
import { BACKEND_URL } from "@/lib/api";
import Card from "@/components/Card";
import { TaskTable } from "@/components/task-management/TaskManagementLayout";
import TaskBulkActionsBar from "@/components/task-management/TaskBulkActionsBar";
import TaskCreateDialog from "@/components/task-management/TaskCreateDialog";
import { Plus, DownloadSimple, FilePdf, FileXls } from "@phosphor-icons/react";

export default function TaskListPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const perms = taskPermissions(user);
  const l = useTaskLabels();
  const [params, setParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const limit = 25;
  const canBulk = !perms.readOnly && (perms.canAssignLead || perms.canAssignMember || perms.canBulkCancel);

  const filters = {
    status: params.get("status") || undefined,
    priority: params.get("priority") || undefined,
    module_name: params.get("module_name") || undefined,
    search: params.get("search") || undefined,
    skip: page * limit,
    limit,
  };

  const exportFilters = {
    status: filters.status,
    priority: filters.priority,
    module_name: filters.module_name,
    search: filters.search,
  };

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["tm-list", filters],
    queryFn: () => taskApi.list(filters),
  });

  useEffect(() => {
    setSelectedIds(new Set());
  }, [page, params]);

  function exportUrl(format) {
    const q = new URLSearchParams({ format });
    if (exportFilters.status) q.set("status", exportFilters.status);
    if (exportFilters.priority) q.set("priority", exportFilters.priority);
    if (exportFilters.module_name) q.set("module_name", exportFilters.module_name);
    if (exportFilters.search) q.set("search", exportFilters.search);
    return `${BACKEND_URL}/api/tasks/export?${q.toString()}`;
  }

  return (
    <div data-testid="tm-list-root">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-xl font-semibold text-slate-900">{l.list.title}</h1>
          <p className="text-sm text-slate-500">{l.list.tasksCount(data?.total ?? 0)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            data-testid="tm-export-csv"
            href={exportUrl("csv")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 rounded-sm text-sm hover:bg-slate-50"
          >
            <DownloadSimple size={16} /> {l.common.exportCsv}
          </a>
          <a
            data-testid="tm-export-xlsx"
            href={exportUrl("xlsx")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 rounded-sm text-sm hover:bg-slate-50"
          >
            <FileXls size={16} /> {l.common.exportXlsx}
          </a>
          <a
            data-testid="tm-export-pdf"
            href={exportUrl("pdf")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 rounded-sm text-sm hover:bg-slate-50"
          >
            <FilePdf size={16} /> {l.common.exportPdf}
          </a>
          {!perms.readOnly && (
            <button type="button" onClick={() => setCreateOpen(true)}
              className="inline-flex items-center gap-2 bg-[#003B73] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
              <Plus size={16} /> {l.common.createTask}
            </button>
          )}
        </div>
      </div>
      <Card title={l.list.filters}>
        <div className="p-4 flex flex-wrap gap-3">
          <input placeholder={l.common.search} defaultValue={params.get("search") || ""}
            aria-label={l.common.search}
            onKeyDown={(e) => e.key === "Enter" && setParams({ ...Object.fromEntries(params), search: e.target.value })}
            className="px-3 py-2 border border-slate-300 rounded-sm text-sm" />
          <select value={params.get("status") || ""} onChange={(e) => setParams({ ...Object.fromEntries(params), status: e.target.value })}
            aria-label={l.list.allStatuses}
            className="px-3 py-2 border border-slate-300 rounded-sm text-sm">
            <option value="">{l.list.allStatuses}</option>
            {["UNASSIGNED", "IN_PROGRESS", "SUBMITTED_FOR_APPROVAL", "REWORK_REQUIRED", "CLOSED", "PROPOSED_BY_MEMBER"].map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
            ))}
          </select>
          <select value={params.get("priority") || ""} onChange={(e) => setParams({ ...Object.fromEntries(params), priority: e.target.value })}
            aria-label={l.list.allPriorities}
            className="px-3 py-2 border border-slate-300 rounded-sm text-sm">
            <option value="">{l.list.allPriorities}</option>
            {["Critical", "High", "Medium", "Low"].map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </Card>
      <div className="mt-4">
        {isLoading ? <div className="text-slate-500 py-8">{l.common.loading}</div> : (
          <>
            {canBulk && (
              <TaskBulkActionsBar
                selectedIds={selectedIds}
                onClear={() => setSelectedIds(new Set())}
                onDone={() => refetch()}
              />
            )}
            <TaskTable
              rows={data?.items}
              onRowClick={(t) => navigate(`/task-management/tasks/${t.id}`)}
              selectable={canBulk}
              selectedIds={selectedIds}
              onSelectedChange={setSelectedIds}
            />
            <div className="flex justify-between items-center mt-4 text-sm">
              <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="px-3 py-1 border rounded-sm disabled:opacity-40">{l.common.previous}</button>
              <span>{l.common.page(page + 1)}</span>
              <button type="button" disabled={(page + 1) * limit >= (data?.total || 0)} onClick={() => setPage((p) => p + 1)} className="px-3 py-1 border rounded-sm disabled:opacity-40">{l.common.next}</button>
            </div>
          </>
        )}
      </div>
      <TaskCreateDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={() => refetch()} />
    </div>
  );
}
