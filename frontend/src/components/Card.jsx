import React from "react";

const ACCENT_STYLES = {
  primary: {
    border: "border-l-[#003B73]",
    glow: "from-[#003B73]/8 to-transparent",
    icon: "bg-[#003B73]/10 text-[#003B73]",
  },
  green: {
    border: "border-l-emerald-500",
    glow: "from-emerald-500/10 to-transparent",
    icon: "bg-emerald-100 text-emerald-700",
  },
  amber: {
    border: "border-l-amber-500",
    glow: "from-amber-500/10 to-transparent",
    icon: "bg-amber-100 text-amber-800",
  },
  red: {
    border: "border-l-red-500",
    glow: "from-red-500/10 to-transparent",
    icon: "bg-red-100 text-red-700",
  },
  slate: {
    border: "border-l-slate-400",
    glow: "from-slate-400/10 to-transparent",
    icon: "bg-slate-100 text-slate-600",
  },
};

export default function Card({
  title,
  subtitle,
  action,
  children,
  className = "",
  testId,
  elevated = false,
  accentHeader = false,
}) {
  return (
    <section
      data-testid={testId}
      className={[
        "app-card overflow-hidden",
        elevated ? "shadow-md shadow-slate-200/50" : "",
        className,
      ].join(" ")}
    >
      {(title || action) && (
        <header
          className={[
            "px-5 py-4 flex items-center justify-between gap-3 border-b border-slate-100",
            accentHeader
              ? "dashboard-ai-header text-white border-b-0"
              : "bg-gradient-to-r from-slate-50 to-white",
          ].join(" ")}
        >
          <div>
            {title && (
              <h3
                className={[
                  "font-display text-sm font-semibold uppercase tracking-[0.12em]",
                  accentHeader ? "text-white" : "text-slate-800",
                ].join(" ")}
              >
                {title}
              </h3>
            )}
            {subtitle && (
              <p className={["text-xs mt-1", accentHeader ? "text-white/90" : "text-slate-500"].join(" ")}>
                {subtitle}
              </p>
            )}
          </div>
          {action}
        </header>
      )}
      <div>{children}</div>
    </section>
  );
}

export function KpiCard({ label, value, hint, accent = "primary", testId, icon: Icon }) {
  const styles = ACCENT_STYLES[accent] || ACCENT_STYLES.primary;
  return (
    <div
      data-testid={testId}
      className={[
        "group relative overflow-hidden rounded-xl border border-slate-200/80 bg-white p-4 app-card",
        "transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-300/30",
        "border-l-4",
        styles.border,
      ].join(" ")}
    >
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${styles.glow} opacity-80`} />
      <div className="relative flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500 font-medium">{label}</div>
          <div className="font-display text-2xl sm:text-[1.75rem] font-bold tracking-tight text-slate-900 mt-1.5 tabular-nums">
            {value}
          </div>
          {hint && <div className="text-xs text-slate-500 mt-1.5">{hint}</div>}
        </div>
        {Icon && (
          <div className={`shrink-0 rounded-lg p-2.5 ${styles.icon}`}>
            <Icon size={20} weight="duotone" />
          </div>
        )}
      </div>
    </div>
  );
}
