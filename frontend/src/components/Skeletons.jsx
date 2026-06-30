import React from "react";

export function TableSkeleton({ rows = 8, cols = 6 }) {
  return (
    <div className="p-4">
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="grid gap-2" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
            {Array.from({ length: cols }).map((_, c) => (
              <div key={c} className="h-4 rounded-sm bg-slate-200 animate-pulse" style={{ opacity: 1 - r * 0.06 }} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-white border border-slate-200 rounded-sm p-4">
      <div className="h-3 w-24 bg-slate-200 rounded-sm animate-pulse mb-3" />
      <div className="h-8 w-32 bg-slate-200 rounded-sm animate-pulse" />
      <div className="h-3 w-20 bg-slate-200 rounded-sm animate-pulse mt-3" />
    </div>
  );
}
