import React from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { resolveTaskRole } from "@/lib/taskPermissions";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { SignOut, ListChecks, ArrowLeft, House } from "@phosphor-icons/react";
import NotificationBell from "@/components/NotificationBell";
import { useTheme } from "@/lib/theme";
import { Moon, Sun } from "@phosphor-icons/react";

const NAV = [
  { to: "manager", labelKey: "commandCentre", roles: ["manager", "admin"] },
  { to: "team-lead", labelKey: "workbench", roles: ["team_lead", "manager", "admin"] },
  { to: "my-tasks", labelKey: "myTasks", roles: ["team_member", "team_lead", "manager", "admin"] },
  { to: "auditor", labelKey: "auditorOverview", roles: ["auditor"] },
  { to: "tasks", labelKey: "allTasks", roles: ["manager", "admin", "auditor", "team_lead", "team_member"] },
  { to: "reports", labelKey: "reports", roles: ["manager", "admin", "team_lead", "auditor"] },
  { to: "admin", labelKey: "configuration", roles: ["admin"], pmisAdmin: true },
];

export default function TaskManagementLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { dark, toggleTheme } = useTheme();
  const l = useTaskLabels();
  const role = resolveTaskRole(user);

  const visibleNav = NAV.filter((n) => {
    if (n.pmisAdmin && user?.role !== "Admin") return false;
    return n.roles.includes(role) || user?.role === "Admin";
  });

  return (
    <div className="flex app-shell">
      <aside className="app-sidebar">
        <div className="app-sidebar-brand">
          <div className="font-display text-xs uppercase tracking-[0.22em] text-slate-400">{l.layout.commandCentreTitle}</div>
          <div className="text-sm mt-2 text-white font-semibold">{user?.name}</div>
          <div className="text-[10px] text-slate-400 mt-1 capitalize">{role.replace(/_/g, " ")}</div>
        </div>
        <nav className="flex-1 p-3 space-y-1" aria-label={l.layout.navLabel}>
          {visibleNav.map((n) => (
            <NavLink key={n.to} to={`/task-management/${n.to}`}
              className={({ isActive }) => `app-nav-link ${isActive ? "app-nav-link-active" : ""}`}>
              <ListChecks size={16} /> {l.layout.nav[n.labelKey]}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 m-3 mt-0 rounded-xl bg-white/5 border border-white/10 space-y-1">
          <Link to="/app-selector" className="app-nav-link py-2">
            <ArrowLeft size={16} /> {l.layout.appSelector}
          </Link>
          <Link to="/dashboard" className="app-nav-link py-2">
            <House size={16} /> {l.layout.pmisApp}
          </Link>
          <button type="button" onClick={() => { logout(); navigate("/login"); }}
            className="app-nav-link py-2 w-full">
            <SignOut size={16} /> {l.layout.signOut}
          </button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0 app-main">
        <div className="app-topbar-accent" aria-hidden="true" />
        <header className="app-topbar app-topbar-compact dark:bg-slate-950 dark:border-slate-800">
          <div className="font-display text-sm uppercase tracking-[0.15em] text-[#003B73] dark:text-sky-400 font-semibold">
            {l.layout.taskManagement}
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={toggleTheme} className="app-control-btn dark:border-slate-700" aria-label={l.layout.toggleTheme}>
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <NotificationBell />
          </div>
        </header>
        <main className="flex-1 app-content overflow-auto dark:bg-slate-900">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function TaskKpiGrid({ items }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
      {items.map((k) => (
        <button
          key={k.label}
          type="button"
          onClick={k.onClick}
          disabled={!k.onClick}
          className={`text-left bg-white border border-slate-200 rounded-sm p-4 border-l-4 ${k.accent || "border-l-[#003B73]"} ${k.onClick ? "hover:shadow-sm cursor-pointer" : ""}`}
        >
          <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{k.label}</div>
          <div className="font-display text-2xl font-bold text-slate-900 mt-1 tabular-nums">{k.value ?? 0}</div>
          {k.hint && <div className="text-xs text-slate-500 mt-1">{k.hint}</div>}
        </button>
      ))}
    </div>
  );
}

export function TaskTable({ rows, onRowClick, selectable, selectedIds, onSelectedChange }) {
  const l = useTaskLabels();
  const selected = selectedIds || new Set();
  const pageIds = (rows || []).map((t) => t.id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));

  function toggleOne(id, checked) {
    if (!onSelectedChange) return;
    const next = new Set(selected);
    if (checked) next.add(id);
    else next.delete(id);
    onSelectedChange(next);
  }

  function toggleAll(checked) {
    if (!onSelectedChange) return;
    const next = new Set(selected);
    pageIds.forEach((id) => {
      if (checked) next.add(id);
      else next.delete(id);
    });
    onSelectedChange(next);
  }

  if (!rows?.length) {
    return <div className="text-center py-12 text-slate-600 text-sm">{l.common.noTasks}</div>;
  }
  return (
    <div className="overflow-x-auto border border-slate-200 rounded-sm bg-white" tabIndex={0} role="region" aria-label={l.table.listAria}>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
          <tr>
            {selectable && (
              <th className="p-3 w-10">
                <input
                  type="checkbox"
                  data-testid="tm-select-all"
                  checked={allSelected}
                  onChange={(e) => toggleAll(e.target.checked)}
                  aria-label={l.bulk.selectAll}
                />
              </th>
            )}
            <th className="text-left p-3">{l.table.code}</th>
            <th className="text-left p-3">{l.table.title}</th>
            <th className="text-left p-3">{l.table.priority}</th>
            <th className="text-left p-3">{l.table.status}</th>
            <th className="text-left p-3">{l.table.owner}</th>
            <th className="text-left p-3">{l.table.due}</th>
            <th className="text-left p-3">{l.table.sla}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer" onClick={() => onRowClick?.(t)}>
              {selectable && (
                <td className="p-3" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    data-testid={`tm-select-${t.id}`}
                    checked={selected.has(t.id)}
                    onChange={(e) => toggleOne(t.id, e.target.checked)}
                    aria-label={l.bulk.selectTask(t.task_code)}
                  />
                </td>
              )}
              <td className="p-3 font-mono text-xs">{t.task_code}</td>
              <td className="p-3">{t.title}</td>
              <td className="p-3">{t.priority}</td>
              <td className="p-3">{t.status_label || t.status}</td>
              <td className="p-3">{t.current_owner?.name || "—"}</td>
              <td className="p-3">{t.due_date ? String(t.due_date).slice(0, 10) : "—"}</td>
              <td className="p-3">{t.sla_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
