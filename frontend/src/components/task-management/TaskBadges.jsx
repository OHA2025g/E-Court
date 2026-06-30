import React from "react";

export function StatusBadge({ status, label }) {
  const text = label || status;
  const cls =
    status === "CLOSED" ? "bg-emerald-100 text-emerald-800 border-emerald-300"
    : status === "SLA_BREACHED" || status === "REJECTED" ? "bg-red-100 text-red-800 border-red-300"
    : status === "SUBMITTED_FOR_APPROVAL" || status === "MANAGER_APPROVAL_PENDING" ? "bg-violet-100 text-violet-800 border-violet-300"
    : status === "REWORK_REQUIRED" ? "bg-orange-100 text-orange-800 border-orange-300"
    : status === "IN_PROGRESS" || status === "ACCEPTED" ? "bg-sky-100 text-sky-800 border-sky-300"
    : "bg-slate-100 text-slate-700 border-slate-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider font-medium ${cls}`}>
      {text}
    </span>
  );
}

export function PriorityBadge({ priority }) {
  const cls =
    priority === "Critical" ? "bg-red-100 text-red-800 border-red-300"
    : priority === "High" ? "bg-amber-100 text-amber-800 border-amber-300"
    : priority === "Medium" ? "bg-sky-100 text-sky-700 border-sky-300"
    : "bg-slate-100 text-slate-600 border-slate-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider font-medium ${cls}`}>
      {priority}
    </span>
  );
}

export function SlaBadge({ slaStatus, pct }) {
  const cls =
    slaStatus === "BREACHED" || slaStatus === "CLOSED_AFTER_SLA" ? "bg-red-100 text-red-800"
    : slaStatus === "AT_RISK" ? "bg-amber-100 text-amber-800"
    : slaStatus === "CLOSED_WITHIN_SLA" ? "bg-emerald-100 text-emerald-800"
    : "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-[10px] uppercase tracking-wider font-medium ${cls}`}>
      SLA: {slaStatus?.replace(/_/g, " ")}{pct != null ? ` · ${pct}%` : ""}
    </span>
  );
}
