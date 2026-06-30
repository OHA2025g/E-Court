/** Dashboard widget registry — ids, labels, and default grid layout. */
export const WIDGET_IDS = [
  "filters",
  "rag-delta",
  "narrative",
  "kpi-row",
  "rag-donut",
  "trend",
  "choropleth",
  "heatmap",
  "pareto",
  "component-bars",
  "hc-bars",
  "tables",
];

export const WIDGET_LABELS = {
  filters: "Period filters",
  "rag-delta": "MoM RAG delta",
  narrative: "Executive narrative",
  "kpi-row": "KPI cards",
  "rag-donut": "RAG donut",
  trend: "Progress trend",
  choropleth: "India choropleth",
  heatmap: "Component × HC heatmap",
  pareto: "Pareto red flags",
  "component-bars": "Component bars",
  "hc-bars": "High Court bars",
  tables: "Drill-down tables",
};

export const DEFAULT_LAYOUT = {
  version: 1,
  widgets: [
    { id: "filters", visible: true, x: 0, y: 0, w: 12, h: 2, static: true },
    { id: "rag-delta", visible: true, x: 0, y: 2, w: 12, h: 3 },
    { id: "narrative", visible: true, x: 0, y: 5, w: 12, h: 4 },
    { id: "kpi-row", visible: true, x: 0, y: 9, w: 12, h: 3 },
    { id: "rag-donut", visible: true, x: 0, y: 12, w: 4, h: 6 },
    { id: "trend", visible: true, x: 4, y: 12, w: 8, h: 6 },
    { id: "choropleth", visible: true, x: 0, y: 18, w: 12, h: 8 },
    { id: "heatmap", visible: true, x: 0, y: 26, w: 12, h: 8 },
    { id: "pareto", visible: true, x: 0, y: 34, w: 12, h: 7 },
    { id: "component-bars", visible: true, x: 0, y: 41, w: 12, h: 7 },
    { id: "hc-bars", visible: true, x: 0, y: 48, w: 12, h: 8 },
    { id: "tables", visible: true, x: 0, y: 56, w: 12, h: 9 },
  ],
};
