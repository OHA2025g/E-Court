import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { Bell, BellRinging, CheckCircle, Info, Warning, X } from "@phosphor-icons/react";

const KIND_COLORS = {
  alert: "text-red-600",
  warning: "text-amber-600",
  success: "text-emerald-600",
  info: "text-sky-600",
};

const KIND_ICONS = {
  alert: Warning,
  warning: Warning,
  success: CheckCircle,
  info: Info,
};

function fmtAgo(iso) {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

export default function NotificationBell() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);

  const { data } = useQuery({
    queryKey: ["notif"],
    queryFn: () => api.get("/notifications", { params: { limit: 30 } }).then(r => r.data),
    refetchInterval: 30_000,
  });
  const items = data?.items || [];
  const unread = data?.unread_count || 0;

  async function markRead(id) {
    await api.post(`/notifications/${id}/read`);
    qc.invalidateQueries({ queryKey: ["notif"] });
  }

  async function markAll() {
    await api.post("/notifications/mark-all-read");
    qc.invalidateQueries({ queryKey: ["notif"] });
  }

  function go(n) {
    markRead(n.id);
    if (n.link) nav(n.link);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        type="button"
        data-testid="notif-bell"
        onClick={() => setOpen(!open)}
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="relative inline-flex items-center justify-center w-9 h-9 rounded-sm border border-slate-300 bg-white hover:bg-slate-50 text-slate-600"
      >
        {unread > 0 ? <BellRinging size={18} weight="fill" /> : <Bell size={18} />}
        {unread > 0 && (
          <span data-testid="notif-unread-count"
            className="absolute -top-1 -right-1 bg-red-600 text-white text-[10px] rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center font-semibold">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div data-testid="notif-panel"
            className="absolute right-0 mt-2 w-96 max-h-[480px] overflow-hidden bg-white border border-slate-200 rounded-sm shadow-lg z-50 flex flex-col">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <div className="font-display font-semibold text-sm uppercase tracking-wider text-slate-700">Notifications</div>
                <div className="text-[10px] text-slate-500">{unread} unread · {items.length} total</div>
              </div>
              {unread > 0 && (
                <button data-testid="notif-mark-all-read" onClick={markAll} className="text-[11px] text-[#003B73] hover:underline">Mark all read</button>
              )}
            </div>
            <div className="overflow-y-auto flex-1">
              {items.length === 0 ? (
                <div className="px-4 py-10 text-center text-xs text-slate-400">No notifications yet.</div>
              ) : items.map((n) => {
                const Icon = KIND_ICONS[n.kind] || Info;
                return (
                  <div key={n.id}
                    className={`px-4 py-2 border-b border-slate-100 hover:bg-slate-50 cursor-pointer ${n.is_read ? "" : "bg-blue-50/40"}`}
                    onClick={() => go(n)}
                  >
                    <div className="flex items-start gap-2">
                      <Icon size={16} className={`shrink-0 mt-0.5 ${KIND_COLORS[n.kind] || "text-slate-500"}`} weight={n.kind === "alert" ? "fill" : "regular"} />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold text-slate-800 truncate">{n.title}</div>
                        <div className="text-xs text-slate-600 line-clamp-2 mt-0.5">{n.body}</div>
                        <div className="text-[10px] text-slate-400 mt-1">{fmtAgo(n.ts)}</div>
                      </div>
                      {!n.is_read && (
                        <button onClick={(e) => { e.stopPropagation(); markRead(n.id); }}
                          className="text-slate-400 hover:text-slate-700" title="Mark read"><X size={12} /></button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
