import React, { useMemo, useState } from "react";
import { CaretDown, CaretUp, Funnel } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import TrackerPagination from "@/components/TrackerPagination";
import {
  filterRows,
  paginateRows,
  sortRows,
} from "@/lib/trackerTableSortFilter";

/**
 * Inline-editable table cell — saves on blur/Enter.
 */
function EditableCell({ value, onSave, type = "text", disabled, className = "" }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");

  React.useEffect(() => {
    if (!editing) setDraft(value ?? "");
  }, [value, editing]);

  if (disabled) {
    return <span className={className}>{value ?? "—"}</span>;
  }

  async function commit() {
    setEditing(false);
    if (String(draft) !== String(value ?? "")) {
      await onSave(draft);
    }
  }

  if (!editing) {
    return (
      <span
        role="button"
        tabIndex={0}
        className={`cursor-pointer hover:bg-blue-50 rounded px-0.5 ${className}`}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.key === "Enter" && setEditing(true)}
      >
        {value ?? "—"}
      </span>
    );
  }

  return (
    <input
      autoFocus
      type={type}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        if (e.key === "Escape") { setDraft(value ?? ""); setEditing(false); }
      }}
      className="w-full min-w-[60px] px-1 py-0.5 border border-[#003B73] rounded-sm text-xs"
    />
  );
}

function ColumnHeader({
  col,
  sortKey,
  sortDir,
  onSort,
  filterValue,
  onFilterChange,
  filterPlaceholder,
  allLabel,
}) {
  const isSorted = sortKey === col.key;
  const canSort = col.sortable !== false;
  const canFilter = col.filterable !== false;

  function toggleSort() {
    if (!canSort) return;
    onSort(col.key);
  }

  return (
    <div className="space-y-1.5 min-w-[72px]">
      <div className={`flex items-start gap-1 ${col.align === "right" ? "justify-end" : ""}`}>
        {canSort ? (
          <button
            type="button"
            onClick={toggleSort}
            className="inline-flex items-center gap-0.5 text-left hover:text-[#003B73] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#003B73] rounded-sm"
            aria-label={`Sort by ${col.label}`}
          >
            <span>{col.label}</span>
            <span className="inline-flex flex-col shrink-0 text-slate-400">
              <CaretUp
                size={10}
                weight="fill"
                className={isSorted && sortDir === "asc" ? "text-[#003B73]" : "opacity-40"}
              />
              <CaretDown
                size={10}
                weight="fill"
                className={isSorted && sortDir === "desc" ? "text-[#003B73]" : "opacity-40 -mt-1"}
              />
            </span>
          </button>
        ) : (
          <span>{col.label}</span>
        )}
        {canFilter && filterValue && (
          <Funnel size={10} weight="fill" className="text-[#003B73] shrink-0 mt-0.5" aria-hidden />
        )}
      </div>

      {canFilter && (
        col.filterType === "select" ? (
          <select
            value={filterValue}
            onChange={(e) => onFilterChange(col.key, e.target.value)}
            onClick={(e) => e.stopPropagation()}
            className="tracker-col-filter w-full normal-case font-normal tracking-normal"
            aria-label={`Filter ${col.label}`}
          >
            <option value="">{allLabel}</option>
            {(col.filterOptions || []).map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={filterValue}
            onChange={(e) => onFilterChange(col.key, e.target.value)}
            onClick={(e) => e.stopPropagation()}
            placeholder={filterPlaceholder}
            className="tracker-col-filter w-full normal-case font-normal tracking-normal"
            aria-label={`Filter ${col.label}`}
          />
        )
      )}
    </div>
  );
}

export default function EditableTrackerTable({
  columns,
  rows,
  rowKey,
  canEdit,
  onSaveRow,
  onRowClick,
  enableSortFilter = false,
  page = 1,
  pageSize = 50,
  onPageChange,
}) {
  const { t } = useTranslation();
  const [savingId, setSavingId] = useState(null);
  const [sortKey, setSortKey] = useState("");
  const [sortDir, setSortDir] = useState("");
  const [filters, setFilters] = useState({});

  function handleSort(key) {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else if (sortDir === "desc") {
      setSortKey("");
      setSortDir("");
    } else {
      setSortDir("asc");
    }
    onPageChange?.(1);
  }

  function handleFilterChange(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    onPageChange?.(1);
  }

  const processedRows = useMemo(() => {
    if (!enableSortFilter) return rows;
    const filtered = filterRows(rows, columns, filters);
    return sortRows(filtered, columns, sortKey, sortDir);
  }, [rows, columns, filters, sortKey, sortDir, enableSortFilter]);

  const displayRows = useMemo(() => {
    if (!enableSortFilter) return rows;
    return paginateRows(processedRows, page, pageSize);
  }, [enableSortFilter, processedRows, page, pageSize, rows]);

  const filteredTotal = enableSortFilter ? processedRows.length : rows.length;

  async function saveField(row, field, rawValue) {
    setSavingId(row.id);
    try {
      const patch = { ...row };
      if (rawValue === "" || rawValue == null) {
        patch[field] = null;
      } else if (typeof row[field] === "number" || ["target", "achieved", "fund_released", "fund_utilized", "fund_target", "fund_allocated", "value", "baseline"].includes(field)) {
        patch[field] = Number(rawValue);
      } else {
        patch[field] = rawValue;
      }
      await onSaveRow(patch);
    } finally {
      setSavingId(null);
    }
  }

  const filterPlaceholder = t("tracker.columnFilterPlaceholder");
  const allLabel = t("tracker.columnFilterAll");

  return (
    <>
      <table className="dense-table w-full">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={`align-top ${c.align === "right" ? "text-right" : ""} ${enableSortFilter ? "tracker-sort-filter-th" : ""}`}
              >
                {enableSortFilter ? (
                  <ColumnHeader
                    col={c}
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={handleSort}
                    filterValue={filters[c.key] || ""}
                    onFilterChange={handleFilterChange}
                    filterPlaceholder={filterPlaceholder}
                    allLabel={allLabel}
                  />
                ) : (
                  c.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayRows.map((row) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? "cursor-pointer hover:bg-slate-50" : ""}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((col) => (
                <td key={col.key} className={col.align === "right" ? "text-right" : ""}>
                  {col.editable && canEdit ? (
                    <EditableCell
                      value={col.render ? col.render(row) : row[col.key]}
                      type={col.inputType || "text"}
                      disabled={col.editable === "admin" && !canEdit}
                      onSave={(v) => saveField(row, col.field || col.key, v)}
                    />
                  ) : col.render ? (
                    col.render(row)
                  ) : (
                    row[col.key] ?? "—"
                  )}
                  {savingId === row.id && col.editable && (
                    <span className="ml-1 text-[9px] text-slate-400">…</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {enableSortFilter && onPageChange && (
        <TrackerPagination
          page={page}
          pageSize={pageSize}
          total={filteredTotal}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}

export { EditableCell };
