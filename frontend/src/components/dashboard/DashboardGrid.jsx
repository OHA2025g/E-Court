import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import GridLayout, { WidthProvider } from "react-grid-layout";
import { api } from "@/lib/api";
import { toast } from "sonner";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { DEFAULT_LAYOUT, WIDGET_LABELS } from "./widgets";

const Grid = WidthProvider(GridLayout);

export default function DashboardGrid({ childrenMap, editMode, onEditModeChange }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const layoutQ = useQuery({
    queryKey: ["dashboard-layout"],
    queryFn: () => api.get("/dashboard/layout").then(r => r.data.dashboard_layout),
  });

  const [layout, setLayout] = useState(DEFAULT_LAYOUT.widgets);

  useEffect(() => {
    if (layoutQ.data?.widgets) {
      setLayout(layoutQ.data.widgets);
    }
  }, [layoutQ.data]);

  const visibleWidgets = useMemo(
    () => layout.filter(w => w.visible !== false),
    [layout],
  );

  const saveMut = useMutation({
    mutationFn: (payload) => api.put("/dashboard/layout", { dashboard_layout: payload }),
    onSuccess: () => {
      toast.success(t("dashboard.layoutSaved"));
      qc.invalidateQueries({ queryKey: ["dashboard-layout"] });
      onEditModeChange?.(false);
    },
    onError: () => toast.error(t("dashboard.layoutSaveFailed")),
  });

  const resetMut = useMutation({
    mutationFn: () => api.delete("/dashboard/layout"),
    onSuccess: () => {
      toast.success(t("dashboard.layoutReset"));
      setLayout(DEFAULT_LAYOUT.widgets);
      qc.invalidateQueries({ queryKey: ["dashboard-layout"] });
    },
  });

  const onLayoutChange = useCallback((newLayout) => {
    if (!editMode) return;
    setLayout(prev => prev.map(w => {
      const item = newLayout.find(l => l.i === w.id);
      if (!item) return w;
      return { ...w, x: item.x, y: item.y, w: item.w, h: item.h };
    }));
  }, [editMode]);

  const toggleVisible = (id) => {
    setLayout(prev => prev.map(w => w.id === id ? { ...w, visible: w.visible === false } : w));
  };

  const gridLayout = visibleWidgets.map(w => ({
    i: w.id,
    x: w.x ?? 0,
    y: w.y ?? 0,
    w: w.w ?? 12,
    h: w.h ?? 4,
    static: !editMode || w.static,
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 justify-end">
        <button
          type="button"
          onClick={() => onEditModeChange?.(!editMode)}
          className="text-xs uppercase tracking-wider px-3 py-1.5 border border-slate-300 rounded-sm hover:bg-slate-50"
        >
          {editMode ? t("dashboard.doneEditing") : t("dashboard.editLayout")}
        </button>
        {editMode && (
          <>
            <button
              type="button"
              onClick={() => saveMut.mutate({ version: 1, widgets: layout })}
              className="text-xs uppercase tracking-wider px-3 py-1.5 bg-[#003B73] text-white rounded-sm"
            >
              {t("dashboard.saveLayout")}
            </button>
            <button
              type="button"
              onClick={() => resetMut.mutate()}
              className="text-xs uppercase tracking-wider px-3 py-1.5 border border-slate-300 rounded-sm"
            >
              {t("dashboard.resetDefault")}
            </button>
          </>
        )}
      </div>
      {editMode && (
        <div className="flex flex-wrap gap-2 text-[10px] uppercase tracking-wider">
          {layout.map(w => (
            <label key={w.id} className="flex items-center gap-1 border border-slate-200 rounded-sm px-2 py-1 bg-white">
              <input type="checkbox" checked={w.visible !== false} onChange={() => toggleVisible(w.id)} />
              {WIDGET_LABELS[w.id] || w.id}
            </label>
          ))}
        </div>
      )}
      <Grid
        className="layout"
        layout={gridLayout}
        cols={12}
        rowHeight={40}
        onLayoutChange={onLayoutChange}
        draggableHandle=".widget-drag-handle"
        isDraggable={editMode}
        isResizable={editMode}
        compactType="vertical"
      >
        {visibleWidgets.map(w => (
          <div
            key={w.id}
            data-grid={{ i: w.id, x: w.x ?? 0, y: w.y ?? 0, w: w.w ?? 12, h: w.h ?? 4, static: !editMode || w.static }}
          >
            {editMode && !w.static && (
              <div className="widget-drag-handle cursor-move text-[9px] uppercase tracking-widest text-slate-400 bg-slate-50 px-2 py-0.5 border-b border-slate-100">
                Drag · {w.id}
              </div>
            )}
            <div
              className="h-full overflow-auto"
              tabIndex={0}
              role="region"
              aria-label={WIDGET_LABELS[w.id] || w.id}
            >
              {childrenMap[w.id]}
            </div>
          </div>
        ))}
      </Grid>
    </div>
  );
}
