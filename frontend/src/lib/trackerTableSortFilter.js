/** Client-side sort/filter helpers for tracker tables. */

export function getColumnSortValue(row, col) {
  if (col.sortValue) return col.sortValue(row);
  return row[col.key];
}

export function getColumnFilterValue(row, col) {
  if (col.filterValue) return col.filterValue(row);
  const v = row[col.key];
  if (v == null || v === "") return "";
  return String(v);
}

function compareValues(a, b, sortType) {
  const aEmpty = a == null || a === "";
  const bEmpty = b == null || b === "";
  if (aEmpty && bEmpty) return 0;
  if (aEmpty) return 1;
  if (bEmpty) return -1;

  if (sortType === "number") {
    const na = Number(a);
    const nb = Number(b);
    if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
  }

  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

export function filterRows(rows, columns, filters) {
  const active = Object.entries(filters).filter(([, v]) => (v || "").trim());
  if (!active.length) return rows;

  return rows.filter((row) =>
    active.every(([key, raw]) => {
      const col = columns.find((c) => c.key === key);
      if (!col || col.filterable === false) return true;

      const needle = raw.trim().toLowerCase();
      const hay = getColumnFilterValue(row, col).toLowerCase();

      if (col.filterType === "select") {
        return hay === needle;
      }
      if (col.filterType === "number") {
        return hay.includes(needle);
      }
      return hay.includes(needle);
    }),
  );
}

export function sortRows(rows, columns, sortKey, sortDir) {
  if (!sortKey || !sortDir) return rows;

  const col = columns.find((c) => c.key === sortKey);
  if (!col || col.sortable === false) return rows;

  const sortType = col.sortType || (col.filterType === "number" ? "number" : "text");
  const sorted = [...rows].sort((a, b) => {
    const cmp = compareValues(getColumnSortValue(a, col), getColumnSortValue(b, col), sortType);
    return sortDir === "asc" ? cmp : -cmp;
  });
  return sorted;
}

export function paginateRows(rows, page, pageSize) {
  const start = (page - 1) * pageSize;
  return rows.slice(start, start + pageSize);
}
