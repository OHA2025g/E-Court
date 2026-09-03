"""Dashboard aggregation helpers for visualisation endpoints."""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from rollup import (
    financial_component_hc_stages,
    financial_exact_totals_stages,
    financial_hc_rollup_stages,
    financial_national_totals_stages,
    financial_period_totals_stages,
    financial_rollup_stages,
    outcome_hc_rollup_stages,
    outcome_period_reported_stages,
    outcome_rollup_stages,
    physical_component_hc_stages,
    physical_rollup_stages,
    sum_nullable,
)
from high_court_names import normalize_high_court_dashes
from seed_constants import (
    COMPONENTS,
    DEFAULT_RAG_THRESHOLDS,
    HIGH_COURTS,
    OUTCOME_SUBJECTS,
    REPORTING_PERIODS,
)
from period_policy import merge_match

# Component → unit of measure (Count, Crore Pages, GB / TB / PB, Percentage).
COMPONENT_UOM = {c["name"]: c["uom"] for c in COMPONENTS}

# Storage capacity and percentage indicators must not enter absolute target/achieved sums.
NON_SUMMABLE_UOMS = frozenset({"GB / TB / PB", "Percentage"})
PREFERRED_ABSOLUTE_UOM = "Count"
# Skip obvious unit-mismatch rows (e.g. pages stored as crore) from mean % rollups.
MAX_PLAUSIBLE_ACHIEVEMENT_PCT = 1000.0


def _row_uom(row: dict) -> str:
    return COMPONENT_UOM.get(row.get("component"), "Unknown")


def relative_achieved_percent_by_hc(
    by_hc: dict[str, list],
    achieved_key: str = "achieved",
) -> dict[str, float]:
    """When targets are missing (e.g. Cloud GB capacity), scale each HC vs max achieved.

    Max High Court → 100%; others proportional. Returns {} if nothing positive.
    """
    hc_achieved: dict[str, float] = {}
    for hc, rows in by_hc.items():
        total = sum(float(r.get(achieved_key) or 0) for r in rows)
        if total > 0:
            hc_achieved[hc] = total
    if not hc_achieved:
        return {}
    peak = max(hc_achieved.values())
    if peak <= 0:
        return {}
    return {hc: round(100.0 * val / peak, 2) for hc, val in hc_achieved.items()}


def mean_achievement_percent(
    rows: list,
    safe_div_fn: Callable,
    target_key: str = "target",
    achieved_key: str = "achieved",
) -> Optional[float]:
    """Equal-weight mean of row-level achievement % (skips rows with target ≤ 0)."""
    pcts = []
    for row in rows:
        pct = safe_div_fn(row.get(achieved_key), row.get(target_key))
        if pct is not None and pct <= MAX_PLAUSIBLE_ACHIEVEMENT_PCT:
            pcts.append(pct)
    if not pcts:
        return None
    return round(sum(pcts) / len(pcts), 2)


def physical_kpi_achievement_percent(
    rolled_phys: list,
    phys_totals: dict,
    safe_div_fn: Callable,
) -> Optional[float]:
    """National Avg Physical % for KPI cards (Target/Achieved scope aligned)."""
    if not phys_totals.get("mixed_uom"):
        return safe_div_fn(phys_totals.get("achieved"), phys_totals.get("target"))
    scope_pct = safe_div_fn(phys_totals.get("achieved"), phys_totals.get("target"))
    if scope_pct is not None:
        return scope_pct
    summable = [r for r in rolled_phys if _row_uom(r) not in NON_SUMMABLE_UOMS]
    return mean_achievement_percent(summable, safe_div_fn)


def group_rows_by_hc(rows: list, hc_key: str = "high_court") -> dict[str, list]:
    by_hc: dict[str, list] = defaultdict(list)
    for row in rows:
        hc = row.get(hc_key)
        if hc:
            by_hc[hc].append(row)
    return by_hc


def mean_relative_achieved_percent(
    rows: list,
    achieved_key: str = "achieved",
) -> Optional[float]:
    """National/component rollup when targets are missing: mean of HC relative %."""
    rel = relative_achieved_percent_by_hc(group_rows_by_hc(rows), achieved_key=achieved_key)
    if not rel:
        return None
    return round(sum(rel.values()) / len(rel), 2)


def physical_percent_with_relative_fallback(
    rows: list,
    safe_div_fn: Callable,
    *,
    sum_ratio: bool = False,
    allow_relative: bool = False,
    target_key: str = "target",
    achieved_key: str = "achieved",
) -> Optional[float]:
    """Target-based achievement %.

    When no usable target exists (e.g. Cloud capacity with target 0/null), returns
    None so the UI shows NA - unless ``allow_relative`` is True, in which case it
    falls back to mean relative-vs-max HC achieved (ranking, not true achievement).
    """
    if sum_ratio:
        target = sum(float(r.get(target_key) or 0) for r in rows)
        achieved = sum(float(r.get(achieved_key) or 0) for r in rows)
        pct = safe_div_fn(achieved, target if target else None)
    else:
        pct = mean_achievement_percent(rows, safe_div_fn, target_key, achieved_key)
    if pct is not None:
        return pct
    if allow_relative:
        return mean_relative_achieved_percent(rows, achieved_key=achieved_key)
    return None


def physical_absolute_totals(rows: list) -> dict:
    """Sum target/achieved in a single display UOM for KPI cards.

    - Drops non-summable UOMs (Cloud GB/TB/PB, Percentage) so storage capacity
      cannot inflate Phys Achieved.
    - When Count and Crore Pages both exist, shows Count totals (primary UOM)
      and sets mixed_uom=True; KPI % uses Count sum ratio when those totals exist.
    """
    active = [
        r for r in rows
        if r.get("target") is not None or r.get("achieved") is not None
    ]
    if not active:
        return {
            "target": None,
            "achieved": None,
            "mixed_uom": False,
            "uom": None,
            "absolute_scope": None,
        }

    all_uoms = {_row_uom(r) for r in active}
    summable = [r for r in active if _row_uom(r) not in NON_SUMMABLE_UOMS]
    summable_uoms = {_row_uom(r) for r in summable}

    if not summable:
        # Only storage/percentage in scope (e.g. Cloud filter) - show that UOM.
        if len(all_uoms) == 1:
            uom = next(iter(all_uoms))
            return {
                "target": sum_nullable(r.get("target") for r in active),
                "achieved": sum_nullable(r.get("achieved") for r in active),
                "mixed_uom": False,
                "uom": uom,
                "absolute_scope": uom,
            }
        return {
            "target": None,
            "achieved": None,
            "mixed_uom": True,
            "uom": None,
            "absolute_scope": None,
        }

    if PREFERRED_ABSOLUTE_UOM in summable_uoms and len(summable_uoms) > 1:
        scoped = [r for r in summable if _row_uom(r) == PREFERRED_ABSOLUTE_UOM]
        scope = PREFERRED_ABSOLUTE_UOM
    elif len(summable_uoms) == 1:
        scope = next(iter(summable_uoms))
        scoped = summable
    else:
        # Multiple non-Count summable UOMs - pick the UOM with the most rows.
        by_uom: dict[str, list] = defaultdict(list)
        for r in summable:
            by_uom[_row_uom(r)].append(r)
        scope = max(by_uom.keys(), key=lambda u: len(by_uom[u]))
        scoped = by_uom[scope]

    return {
        "target": sum_nullable(r.get("target") for r in scoped),
        "achieved": sum_nullable(r.get("achieved") for r in scoped),
        # True whenever the underlying dataset spans more than the displayed UOM.
        "mixed_uom": len(all_uoms) > 1,
        "uom": scope,
        "absolute_scope": scope,
    }


async def build_agg_match(
    db,
    scope_filter_fn: Callable,
    user: dict,
    reporting_period: Optional[str] = None,
    include_unapproved: bool = False,
    extra_match: Optional[dict] = None,
) -> dict:
    """Scope + optional period + approval gating."""
    match = scope_filter_fn(user)
    if reporting_period:
        match["reporting_period"] = reporting_period
    if extra_match:
        match = merge_match(match, extra_match)
    return match


async def fetch_rag_thresholds(db) -> dict:
    doc = await db.settings.find_one({"key": "rag_thresholds"})
    return (doc or {}).get("value", DEFAULT_RAG_THRESHOLDS)


def resolve_period_pair(reporting_period: Optional[str] = None) -> Optional[tuple[str, str]]:
    """Return (current_period, previous_period) from ordered reporting periods."""
    ordered = [p["period"] for p in REPORTING_PERIODS]
    non_baseline = [p["period"] for p in REPORTING_PERIODS if not p.get("is_baseline")]
    pool = non_baseline if non_baseline else ordered
    if not pool:
        return None
    current = reporting_period if reporting_period else pool[-1]
    if current not in ordered:
        return None
    idx = ordered.index(current)
    if idx <= 0:
        return None
    previous = ordered[idx - 1]
    return current, previous


async def aggregate_hc_percent_physical(db, match: dict) -> dict[str, float]:
    """HC physical % aligned with High Court Comparison / KPI (Count-scoped sum ratio).

    No usable target (e.g. Cloud capacity) → omitted so callers treat it as NA.
    """
    def _pct(achieved, target):
        if achieved is None or target is None or not target:
            return None
        return round((float(achieved) / float(target)) * 100, 2)

    rows = await db.physical_entries.aggregate(physical_rollup_stages(match)).to_list(50000)
    by_hc: dict[str, list] = defaultdict(list)
    for r in rows:
        hc = r.get("high_court")
        if hc:
            by_hc[hc].append(r)
    out: dict[str, float] = {}
    for hc, hc_rows in by_hc.items():
        totals = physical_absolute_totals(hc_rows)
        pct = physical_kpi_achievement_percent(hc_rows, totals, _pct)
        if pct is not None:
            out[hc] = pct
    return out


async def aggregate_hc_percent_financial(db, match: dict) -> dict[str, float]:
    rows = await db.financial_entries.aggregate(financial_hc_rollup_stages(match)).to_list(100)
    out = {}
    for r in rows:
        rel, util = r.get("r") or 0, r.get("u") or 0
        if rel:
            out[r["_id"]] = round((util / rel) * 100, 2)
    return out


async def aggregate_hc_percent_outcome(db, match: dict) -> dict[str, float]:
    rows = await db.outcome_entries.aggregate(outcome_hc_rollup_stages(match)).to_list(100)
    out = {}
    for r in rows:
        total, reported = r.get("total") or 0, r.get("reported") or 0
        if total:
            out[r["_id"]] = round((reported / total) * 100, 2)
    return out


async def compute_states_rag(
    db,
    state_to_hc: dict,
    scope_filter_fn: Callable,
    compute_rag_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    metric: str = "physical",
    extra_match: Optional[dict] = None,
) -> dict:
    match = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    if metric == "financial":
        hc_pct = await aggregate_hc_percent_financial(db, match)
    elif metric == "outcome":
        hc_pct = await aggregate_hc_percent_outcome(db, match)
    else:
        hc_pct = await aggregate_hc_percent_physical(db, match)
    thresholds = await fetch_rag_thresholds(db)

    # Absolute counts for map tooltips (same detail style as component×HC heatmap).
    hc_detail: dict[str, dict] = {}
    if metric == "financial":
        fin_rows = await db.financial_entries.aggregate(financial_hc_rollup_stages(match)).to_list(100)
        for r in fin_rows:
            hc_detail[r["_id"]] = {
                "released": None if r.get("r") is None else float(r.get("r")),
                "utilized": None if r.get("u") is None else float(r.get("u")),
                "uom": "₹ Cr",
            }
    elif metric == "outcome":
        out_rows = await db.outcome_entries.aggregate(outcome_hc_rollup_stages(match)).to_list(100)
        for r in out_rows:
            hc_detail[r["_id"]] = {
                "reported": int(r.get("reported") or 0),
                "total": int(r.get("total") or 0),
                "uom": "KPIs",
            }
    else:
        phys_rows = await db.physical_entries.aggregate(physical_rollup_stages(match)).to_list(50000)
        by_hc: dict[str, list] = defaultdict(list)
        for r in phys_rows:
            hc = r.get("high_court")
            if hc:
                by_hc[hc].append(r)
        for hc, rows in by_hc.items():
            totals = physical_absolute_totals(rows)
            hc_detail[hc] = {
                "target": totals.get("target"),
                "achieved": totals.get("achieved"),
                "uom": totals.get("uom"),
                "mixed_uom": bool(totals.get("mixed_uom")),
            }

    user_hc = user.get("high_court") if user.get("role") == "CPC" else None
    out = {}
    for state, hc in state_to_hc.items():
        if user_hc and hc != user_hc:
            out[state] = {"high_court": hc, "percent": None, "rag": "NA", "in_scope": False}
            continue
        pct = hc_pct.get(hc)
        payload = {
            "high_court": hc,
            "percent": pct,
            "rag": compute_rag_fn(pct, thresholds),
            "in_scope": True,
        }
        payload.update(hc_detail.get(hc) or {})
        out[state] = payload
    return out


async def compute_rag_delta(
    db,
    scope_filter_fn: Callable,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    metric: str = "physical",
    extra_match: Optional[dict] = None,
) -> Optional[dict]:
    pair = resolve_period_pair(reporting_period)
    if not pair:
        return None
    current, previous = pair
    base = await build_agg_match(db, scope_filter_fn, user, None, False, extra_match)
    thresholds = await fetch_rag_thresholds(db)

    async def rolled_rag_map(period: str) -> dict:
        match = {**base, "reporting_period": period}
        out = {}
        if metric == "outcome":
            rows = await db.outcome_entries.aggregate(outcome_rollup_stages(match)).to_list(50000)
            for r in rows:
                key = (r.get("high_court"), r.get("subject"), r.get("kpi_id"))
                value = r.get("value")
                baseline = r.get("baseline")
                if value is not None and baseline:
                    pct = safe_div_fn(value, baseline)
                elif value is not None:
                    pct = 100.0
                else:
                    pct = None
                out[key] = compute_rag_fn(pct, thresholds)
            return out
        if metric == "financial":
            rows = await db.financial_entries.aggregate(financial_rollup_stages(match)).to_list(50000)
            for r in rows:
                key = (r.get("high_court"), r.get("component"))
                pct = safe_div_fn(r.get("fund_utilized"), r.get("fund_released"))
                out[key] = compute_rag_fn(pct, thresholds)
            return out
        rows = await db.physical_entries.aggregate(physical_rollup_stages(match)).to_list(50000)
        for r in rows:
            key = (r.get("high_court"), r.get("component"), r.get("indicator"))
            t, a = r.get("target") or 0, r.get("achieved") or 0
            pct = round((a / t) * 100, 2) if t else None
            out[key] = compute_rag_fn(pct, thresholds)
        return out

    prev_map = await rolled_rag_map(previous)
    cur_map = await rolled_rag_map(current)
    turned_green = turned_red = turned_amber = unchanged_green = 0
    for key, cur_rag in cur_map.items():
        prev_rag = prev_map.get(key)
        if prev_rag is None:
            continue
        if prev_rag != "GREEN" and cur_rag == "GREEN":
            turned_green += 1
        elif cur_rag == "RED" and prev_rag in ("GREEN", "AMBER"):
            turned_red += 1
        elif prev_rag != "AMBER" and cur_rag == "AMBER":
            turned_amber += 1
        elif prev_rag == "GREEN" and cur_rag == "GREEN":
            unchanged_green += 1
    unit = "KPIs" if metric == "outcome" else "components" if metric == "financial" else "indicators"
    return {
        "metric": metric,
        "unit": unit,
        "current_period": current,
        "previous_period": previous,
        "turned_green": turned_green,
        "turned_red": turned_red,
        "turned_amber": turned_amber,
        "unchanged_green": unchanged_green,
        "net_green": turned_green - turned_red,
    }


async def compute_heatmap(
    db,
    scope_filter_fn: Callable,
    compute_rag_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    metric: str = "physical",
    extra_match: Optional[dict] = None,
) -> dict:
    match = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    thresholds = await fetch_rag_thresholds(db)
    components = [c["name"] for c in COMPONENTS]
    subjects = list(OUTCOME_SUBJECTS)
    hcs = list(HIGH_COURTS)
    if user.get("role") == "CPC" and user.get("high_court"):
        hcs = [user["high_court"]]

    cell_map: dict[tuple, dict] = {}
    if metric == "financial":
        rows = await db.financial_entries.aggregate(financial_component_hc_stages(match)).to_list(500)
        for r in rows:
            rel, util = r.get("r"), r.get("u")
            if rel is not None and util is not None and float(rel):
                pct = round((float(util) / float(rel)) * 100, 2)
            else:
                pct = None
            comp = r["_id"]["component"]
            hc = r["_id"]["high_court"]
            cell_map[(comp, hc)] = {
                "percent": pct,
                "rag": compute_rag_fn(pct, thresholds),
                "released": None if rel is None else float(rel),
                "utilized": None if util is None else float(util),
                "uom": "₹ Cr",
            }
        row_keys = components
        row_field = "component"
    elif metric == "outcome":
        rolled = await db.outcome_entries.aggregate(outcome_rollup_stages(match)).to_list(50000)
        stats: dict[tuple, dict] = {}
        for r in rolled:
            key = (r.get("subject"), r.get("high_court"))
            st = stats.setdefault(key, {"total": 0, "reported": 0})
            st["total"] += 1
            if r.get("value") is not None:
                st["reported"] += 1
        for (subj, hc), st in stats.items():
            pct = round((st["reported"] / st["total"]) * 100, 2) if st["total"] else None
            cell_map[(subj, hc)] = {
                "percent": pct,
                "rag": compute_rag_fn(pct, thresholds),
                "reported": st["reported"],
                "total": st["total"],
                "uom": "KPIs",
            }
        row_keys = subjects
        row_field = "subject"
    else:
        rows = await db.physical_entries.aggregate(physical_component_hc_stages(match)).to_list(500)
        for r in rows:
            t, a = r.get("t"), r.get("a")
            comp = r["_id"]["component"]
            hc = r["_id"]["high_court"]
            t_f = None if t is None else float(t)
            a_f = None if a is None else float(a)
            if t_f:
                pct = round((a_f or 0) / t_f * 100, 2)
            else:
                pct = None
            cell_map[(comp, hc)] = {
                "percent": pct,
                "rag": compute_rag_fn(pct, thresholds),
                "target": None if t_f is None else float(t_f),
                "achieved": None if a_f is None else float(a_f),
                "uom": next((c["uom"] for c in COMPONENTS if c["name"] == comp), None),
            }
        row_keys = components
        row_field = "component"

    cells = []
    for row_key in row_keys:
        for hc in hcs:
            info = cell_map.get((row_key, hc), {"percent": None, "rag": "NA"})
            cell = {
                row_field: row_key,
                "high_court": hc,
                "percent": info.get("percent"),
                "rag": info.get("rag", "NA"),
            }
            if row_field == "component":
                cell["component"] = row_key
            for key in ("target", "achieved", "released", "utilized", "reported", "total", "uom"):
                if key in info:
                    cell[key] = info[key]
            cells.append(cell)
    result = {
        "high_courts": hcs,
        "cells": cells,
        "metric": metric,
        "row_field": row_field,
    }
    if metric == "outcome":
        result["subjects"] = row_keys
    else:
        result["components"] = row_keys
    return result


async def compute_pareto_red_flags(
    db,
    scope_filter_fn: Callable,
    compute_rag_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    metric: str = "physical",
    extra_match: Optional[dict] = None,
) -> dict:
    match = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    thresholds = await fetch_rag_thresholds(db)
    component_red: dict[str, int] = {}
    if metric == "outcome":
        rolled = await db.outcome_entries.aggregate(outcome_rollup_stages(match)).to_list(50000)
        for r in rolled:
            if r.get("value") is not None:
                continue
            comp = r.get("subject") or "Unknown"
            component_red[comp] = component_red.get(comp, 0) + 1
    elif metric == "financial":
        rolled = await db.financial_entries.aggregate(financial_rollup_stages(match)).to_list(50000)
        for r in rolled:
            rel, util = r.get("fund_released") or 0, r.get("fund_utilized") or 0
            pct = round((util / rel) * 100, 2) if rel else None
            if compute_rag_fn(pct, thresholds) != "RED":
                continue
            comp = r.get("component") or "Unknown"
            component_red[comp] = component_red.get(comp, 0) + 1
    else:
        rolled = await db.physical_entries.aggregate(physical_rollup_stages(match)).to_list(50000)
        by_comp: dict[str, list] = defaultdict(list)
        for r in rolled:
            by_comp[r.get("component") or "Unknown"].append(r)
        for comp, rows in by_comp.items():
            has_targets = any(float(r.get("target") or 0) > 0 for r in rows)
            if not has_targets:
                # No usable target (e.g. Cloud) → NA, not a RED achievement flag.
                continue
            for r in rows:
                t, a = r.get("target") or 0, r.get("achieved") or 0
                pct = round((a / t) * 100, 2) if t else None
                if compute_rag_fn(pct, thresholds) == "RED":
                    component_red[comp] = component_red.get(comp, 0) + 1
    rows = sorted(component_red.items(), key=lambda x: x[1], reverse=True)
    total = sum(c for _, c in rows)
    cumulative = 0
    series = []
    pareto_cutoff = 0
    for i, (comp, count) in enumerate(rows):
        cumulative += count
        pct_of_total = round((count / total) * 100, 1) if total else 0
        cum_pct = round((cumulative / total) * 100, 1) if total else 0
        if pareto_cutoff == 0 and cum_pct >= 80:
            pareto_cutoff = i + 1
        series.append({
            "component": comp,
            "red_count": count,
            "pct_of_total": pct_of_total,
            "cumulative_pct": cum_pct,
        })
    if not pareto_cutoff and series:
        pareto_cutoff = len(series)
    return {
        "total_red_flags": total,
        "pareto_cutoff": pareto_cutoff,
        "series": series,
        "metric": metric,
    }


def _date_to_period(dt_val: Any) -> Optional[str]:
    if not dt_val:
        return None
    if isinstance(dt_val, str):
        try:
            dt_val = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            return dt_val[:7] if len(dt_val) >= 7 else None
    if isinstance(dt_val, datetime):
        return dt_val.strftime("%Y-%m")
    return None


async def compute_trend_with_milestones(
    db,
    scope_filter_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    extra_match: Optional[dict] = None,
) -> dict:
    pmatch = await build_agg_match(db, scope_filter_fn, user, None, False, extra_match)
    fmatch = await build_agg_match(db, scope_filter_fn, user, None, False, extra_match)
    omatch = await build_agg_match(db, scope_filter_fn, user, None, False, extra_match)
    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    fin = await db.financial_entries.aggregate(financial_period_totals_stages(fmatch)).to_list(100)
    outcome = await db.outcome_entries.aggregate(outcome_period_reported_stages(omatch)).to_list(100)
    pmap: dict[str, list] = defaultdict(list)
    for row in rolled_phys:
        per = row.get("reporting_period")
        if per:
            pmap[per].append(row)
    fmap = {f["_id"]: f for f in fin}
    omap = {o["_id"]: o for o in outcome}
    periods_sorted = sorted(set(list(pmap.keys()) + list(fmap.keys()) + list(omap.keys())))
    periods = []
    for per in periods_sorted:
        f = fmap.get(per, {"released": None, "utilized": None})
        o = omap.get(per, {"total": 0, "reported": 0})
        phys_rows = pmap.get(per, [])
        phys_totals = physical_absolute_totals(phys_rows)
        periods.append({
            "period": per,
            "phys_percent": physical_kpi_achievement_percent(phys_rows, phys_totals, safe_div_fn),
            "fin_percent": safe_div_fn(f.get("utilized"), f.get("released")),
            "outcome_reported_pct": safe_div_fn(o.get("reported"), o.get("total")),
        })

    dpr_docs = await db.dpr_deliverables.find().to_list(100)
    milestones = []
    for d in dpr_docs:
        period = _date_to_period(d.get("target_date")) or _date_to_period(d.get("actual_date"))
        milestones.append({
            "code": d.get("code"),
            "title": d.get("title"),
            "target_date": d.get("target_date"),
            "period": period,
            "status": d.get("status"),
        })
    return {"periods": periods, "milestones": milestones}


async def compute_public_progress(
    db,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    reporting_period: Optional[str],
    state_to_hc: dict,
    extra_match: Optional[dict] = None,
    *,
    use_latest_snapshot: bool = True,
) -> dict:
    use_latest = use_latest_snapshot and not reporting_period

    pmatch: dict = {}
    fmatch: dict = {}
    omatch: dict = {}
    if reporting_period:
        pmatch["reporting_period"] = reporting_period
        fmatch["reporting_period"] = reporting_period
        omatch["reporting_period"] = reporting_period
    if extra_match:
        pmatch = merge_match(pmatch, extra_match)
        fmatch = merge_match(fmatch, extra_match)
        omatch = merge_match(omatch, extra_match)

    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    fin_rolled = await db.financial_entries.aggregate(financial_rollup_stages(fmatch)).to_list(50000)
    outcome_rolled = await db.outcome_entries.aggregate(outcome_rollup_stages(omatch)).to_list(50000)

    if use_latest:
        rolled_phys = _rows_latest_snapshot(
            rolled_phys, ("high_court", "component", "indicator"),
        )
        fin_rolled = _rows_latest_snapshot(fin_rolled, ("high_court", "component"))
        outcome_rolled = _rows_latest_snapshot(
            outcome_rolled, ("high_court", "subject", "kpi_id", "granularity"),
        )

    snapshot_period = reporting_period or _snapshot_label_from_rows(
        rolled_phys, fin_rolled, outcome_rolled,
    )

    phys_totals = physical_absolute_totals(rolled_phys)
    thresholds = await fetch_rag_thresholds(db)
    rag_counts: dict[str, int] = {}
    for row in rolled_phys:
        pct = safe_div_fn(row.get("achieved"), row.get("target"))
        status = compute_rag_fn(pct, thresholds)
        rag_counts[status] = rag_counts.get(status, 0) + 1

    f_totals = _financial_totals_from_rows(fin_rolled)
    outcome_reported = sum(1 for row in outcome_rolled if row.get("value") is not None)
    outcome_total = len(outcome_rolled)
    outcome_pct = safe_div_fn(outcome_reported, outcome_total)
    outcome_hc_ranking = _outcome_hc_ranking_from_rows(outcome_rolled, safe_div_fn)

    phys_pct = physical_kpi_achievement_percent(rolled_phys, phys_totals, safe_div_fn)
    fin_pct = safe_div_fn(f_totals.get("utilized"), f_totals.get("released"))

    hc_pct = _hc_percent_physical_from_rows(rolled_phys, safe_div_fn)
    hc_rag_counts = {"GREEN": 0, "AMBER": 0, "RED": 0, "NA": 0}
    hc_ranking = []
    for hc in HIGH_COURTS:
        pct = hc_pct.get(hc)
        rag = compute_rag_fn(pct, thresholds)
        hc_rag_counts[rag] = hc_rag_counts.get(rag, 0) + 1
        if pct is not None:
            hc_ranking.append({"high_court": hc, "phys_percent": pct, "rag": rag})
    hc_ranking.sort(key=lambda x: x["phys_percent"], reverse=True)

    states = {}
    for state, hc in state_to_hc.items():
        pct = hc_pct.get(hc)
        states[state] = {"high_court": hc, "percent": pct, "rag": compute_rag_fn(pct, thresholds)}

    public_user = {"role": "Viewer"}
    public_scope = lambda u: {}
    viz_period = snapshot_period if use_latest else reporting_period
    trend = await compute_trend_with_milestones(db, public_scope, safe_div_fn, public_user, extra_match)
    heatmap = await compute_heatmap(
        db, public_scope, compute_rag_fn, public_user, viz_period, "physical", extra_match,
    )
    pareto = await compute_pareto_red_flags(
        db, public_scope, compute_rag_fn, public_user, viz_period, "physical", extra_match,
    )
    states_financial = await compute_states_rag(
        db, state_to_hc, public_scope, compute_rag_fn, public_user, viz_period, "financial", extra_match,
    )
    states_outcome = await compute_states_rag(
        db, state_to_hc, public_scope, compute_rag_fn, public_user, viz_period, "outcome", extra_match,
    )

    pair = resolve_period_pair(snapshot_period)
    comparison_period = pair[0] if pair else None
    rag_delta = None
    if comparison_period:
        rag_delta = await compute_rag_delta(
            db, public_scope, compute_rag_fn, safe_div_fn, public_user, comparison_period, "physical", extra_match,
        )

    fin_hc_rows = _financial_hc_rows_from_snapshot(fin_rolled)
    fin_hc_ranking = []
    for r in fin_hc_rows:
        pct = safe_div_fn(r.get("u"), r.get("r"))
        if pct is not None:
            fin_hc_ranking.append({"high_court": r["_id"], "fin_percent": pct})
    fin_hc_ranking.sort(key=lambda x: x["fin_percent"] or 0, reverse=True)

    return {
        "reporting_period": snapshot_period,
        "snapshot_mode": "latest" if use_latest else "period",
        "comparison_period": comparison_period,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "physical": {
            "percent": phys_pct,
            "target": phys_totals["target"],
            "achieved": phys_totals["achieved"],
        },
        "financial": {
            "utilisation_percent": fin_pct,
            "released": f_totals.get("released"),
            "utilized": f_totals.get("utilized"),
        },
        "outcome": {
            "kpi_count": outcome_total,
            "reported_count": outcome_reported,
            "reporting_percent": outcome_pct,
        },
        "top_outcome_high_courts": outcome_hc_ranking[:3],
        "bottom_outcome_high_courts": list(reversed(outcome_hc_ranking[-3:])) if len(outcome_hc_ranking) >= 3 else [],
        "rag_physical": rag_counts,
        "hc_rag_counts": hc_rag_counts,
        "top_high_courts": hc_ranking[:3],
        "bottom_high_courts": list(reversed(hc_ranking[-3:])) if len(hc_ranking) >= 3 else [],
        "top_financial_high_courts": fin_hc_ranking[:3],
        "bottom_financial_high_courts": list(reversed(fin_hc_ranking[-3:])) if len(fin_hc_ranking) >= 3 else [],
        "states": states,
        "viz": {
            "trend": trend,
            "heatmap": heatmap,
            "pareto": pareto,
            "rag_delta": rag_delta,
            "states_financial": states_financial,
            "states_outcome": states_outcome,
        },
    }


async def compute_dashboard_summary(
    db,
    scope_filter_fn: Callable,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    extra_match: Optional[dict] = None,
) -> dict:
    pmatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    fmatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)

    fin = await db.financial_entries.aggregate(
        financial_exact_totals_stages(fmatch)
    ).to_list(1)
    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    phys_totals = physical_absolute_totals(rolled_phys)
    # Homogeneous UOM → ratio of sums; mixed UOMs → equal-weight mean of indicator %.
    # No usable target (e.g. Cloud GB) → NA. Do not invent relative-vs-max ranking
    # as "Avg Physical % Achieved" - that is not achievement against a target.
    phys_percent = physical_kpi_achievement_percent(rolled_phys, phys_totals, safe_div_fn)
    thresholds = await fetch_rag_thresholds(db)
    rag: dict = {}
    for row in rolled_phys:
        pct = safe_div_fn(row.get("achieved"), row.get("target"))
        status = compute_rag_fn(pct, thresholds)
        rag[status] = rag.get(status, 0) + 1
    rolled_fin = await db.financial_entries.aggregate(financial_rollup_stages(fmatch)).to_list(5000)
    rag_fin: dict = {}
    for row in rolled_fin:
        pct = safe_div_fn(row.get("fund_utilized"), row.get("fund_released"))
        status = compute_rag_fn(pct, thresholds)
        rag_fin[status] = rag_fin.get(status, 0) + 1

    f = fin[0] if fin else None
    omatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    outcome_rows = await db.outcome_entries.aggregate(
        outcome_rollup_stages(omatch) + [{"$count": "n"}]
    ).to_list(1)
    outcome_count = outcome_rows[0]["n"] if outcome_rows else 0
    if f is None:
        financial = {
            "target": None,
            "released": None,
            "utilized": None,
            "utilisation_percent": None,
            "variance": None,
            "component_count": 0,
        }
    else:
        released = f.get("released")
        utilized = f.get("utilized")
        # Null-preserving financial totals: only compute variance when both sides exist.
        variance = (
            round(float(released) - float(utilized), 2)
            if released is not None and utilized is not None
            else None
        )
        financial = {
            "target": f.get("target"),
            "released": released,
            "utilized": utilized,
            "utilisation_percent": safe_div_fn(utilized, released),
            "variance": variance,
            "component_count": f.get("count") or 0,
        }
    return {
        "physical": {
            "target": phys_totals["target"],
            "achieved": phys_totals["achieved"],
            "percent": phys_percent,
            "indicator_count": len(rolled_phys),
            "mixed_uom": phys_totals["mixed_uom"],
            "uom": phys_totals.get("uom"),
            "absolute_scope": phys_totals.get("absolute_scope"),
        },
        "financial": financial,
        "rag_physical": rag,
        "rag_financial": rag_fin,
        "outcome": {"kpi_count": outcome_count},
    }


def _match_value(extra_match: Optional[dict], key: str) -> Optional[Any]:
    """Read a simple equality filter from flat or $and-merged match dicts."""
    if not extra_match:
        return None
    if key in extra_match and not isinstance(extra_match[key], dict):
        return extra_match[key]
    for clause in extra_match.get("$and") or []:
        if isinstance(clause, dict) and key in clause and not isinstance(clause[key], dict):
            return clause[key]
    return None


def _rows_latest_snapshot(rows: list, key_fields: tuple[str, ...]) -> list:
    """Keep only the row from the latest reporting_period for each series key.

    Tracker fund/physical fields are cumulative snapshots per month — summing
    multiple periods would double-count. For DoJ component reports, take the
    newest loaded month per High Court × component (× indicator for physical).
    """
    best: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        period = str(row.get("reporting_period") or "")
        prev = best.get(key)
        if prev is None or period > str(prev.get("reporting_period") or ""):
            best[key] = row
    return list(best.values())


def _snapshot_label_from_rows(*row_sets: list) -> Optional[str]:
    periods: set[str] = set()
    for rows in row_sets:
        for row in rows:
            p = str(row.get("reporting_period") or "")
            if p:
                periods.add(p)
    return max(periods) if periods else None


def _financial_totals_from_rows(rows: list) -> dict:
    return {
        "released": sum_nullable(r.get("fund_released") for r in rows),
        "utilized": sum_nullable(r.get("fund_utilized") for r in rows),
    }


def _financial_hc_rows_from_snapshot(rows: list) -> list:
    by_hc: dict[str, dict] = defaultdict(lambda: {"r": None, "u": None})
    for row in rows:
        hc = row.get("high_court")
        if not hc:
            continue
        bucket = by_hc[hc]
        for src, dst in (("fund_released", "r"), ("fund_utilized", "u")):
            val = row.get(src)
            if val is not None:
                bucket[dst] = (bucket[dst] or 0) + float(val)
    return [{"_id": hc, "r": bucket["r"], "u": bucket["u"]} for hc, bucket in by_hc.items()]


def _hc_percent_physical_from_rows(rows: list, safe_div_fn: Callable) -> dict[str, float]:
    by_hc: dict[str, list] = defaultdict(list)
    for row in rows:
        hc = row.get("high_court")
        if hc:
            by_hc[hc].append(row)
    out: dict[str, float] = {}
    for hc, hc_rows in by_hc.items():
        totals = physical_absolute_totals(hc_rows)
        pct = physical_kpi_achievement_percent(hc_rows, totals, safe_div_fn)
        if pct is not None:
            out[hc] = pct
    return out


def _outcome_hc_ranking_from_rows(rows: list, safe_div_fn: Callable) -> list:
    by_hc: dict[str, dict] = defaultdict(lambda: {"total": 0, "reported": 0})
    for row in rows:
        hc = row.get("high_court")
        if not hc:
            continue
        by_hc[hc]["total"] += 1
        if row.get("value") is not None:
            by_hc[hc]["reported"] += 1
    ranking = []
    for hc, counts in by_hc.items():
        total = counts["total"]
        reported = counts["reported"]
        if total > 0:
            ranking.append({
                "high_court": hc,
                "reported_count": reported,
                "kpi_count": total,
                "reporting_percent": safe_div_fn(reported, total),
            })
    ranking.sort(key=lambda x: x["reporting_percent"] or 0, reverse=True)
    return ranking


def _component_source_period(*period_sets: set[str]) -> Optional[str]:
    merged = set()
    for ps in period_sets:
        merged |= {p for p in ps if p}
    return max(merged) if merged else None


async def compute_dashboard_by_component(
    db,
    scope_filter_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    extra_match: Optional[dict] = None,
    *,
    snapshot_mode: Optional[str] = None,
) -> list:
    use_latest = snapshot_mode == "latest"
    period_for_match = None if use_latest else reporting_period
    pmatch = await build_agg_match(db, scope_filter_fn, user, period_for_match, False, extra_match)
    fmatch = await build_agg_match(db, scope_filter_fn, user, period_for_match, False, extra_match)
    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    fin_rolled = await db.financial_entries.aggregate(financial_rollup_stages(fmatch)).to_list(50000)
    if use_latest:
        rolled_phys = _rows_latest_snapshot(
            rolled_phys, ("high_court", "component", "indicator"),
        )
        fin_rolled = _rows_latest_snapshot(fin_rolled, ("high_court", "component"))
    pmap: dict[str, list] = defaultdict(list)
    phys_periods: dict[str, set[str]] = defaultdict(set)
    for row in rolled_phys:
        comp = row.get("component")
        if comp:
            pmap[comp].append(row)
            if row.get("reporting_period"):
                phys_periods[comp].add(str(row["reporting_period"]))
    fmap: dict[str, dict] = {}
    fin_by_comp: dict[str, list] = defaultdict(list)
    fin_periods: dict[str, set[str]] = defaultdict(set)
    for row in fin_rolled:
        comp = row.get("component")
        if comp:
            fin_by_comp[comp].append(row)
            if row.get("reporting_period"):
                fin_periods[comp].add(str(row["reporting_period"]))
    for name, rows in fin_by_comp.items():
        fmap[name] = {
            "allocated": sum_nullable(r.get("fund_allocated") for r in rows),
            "target": sum_nullable(r.get("fund_target") for r in rows),
            "released": sum_nullable(r.get("fund_released") for r in rows),
            "utilized": sum_nullable(r.get("fund_utilized") for r in rows),
        }
    selected = _match_value(extra_match, "component")
    components = [c for c in COMPONENTS if not selected or c["name"] == selected]
    rows = []
    for c in components:
        name = c["name"]
        phys_rows = pmap.get(name, [])
        # Single-component scope is always one UOM - absolute sums are valid here.
        # Cloud with no target → Physical % is NA.
        target = sum_nullable(r.get("target") for r in phys_rows)
        achieved = sum_nullable(r.get("achieved") for r in phys_rows)
        f = fmap.get(name)
        if not f:
            fin_allocated = fin_target = fin_released = fin_utilized = None
            budget = None
        else:
            fin_allocated = f.get("allocated")
            fin_target = f.get("target")
            fin_released = f.get("released")
            fin_utilized = f.get("utilized")
            budget = fin_allocated if fin_allocated not in (None, 0) else (
                fin_target if fin_target not in (None, 0) else fin_released
            )
        rows.append({
            "component": name,
            "phys_target": target,
            "phys_achieved": achieved,
            "phys_uom": c.get("uom"),
            "phys_percent": physical_percent_with_relative_fallback(
                phys_rows, safe_div_fn, sum_ratio=True,
            ),
            "fin_allocated": fin_allocated,
            "fin_target": fin_target,
            "fin_budget": budget,
            "fin_released": fin_released, "fin_utilized": fin_utilized,
            "fin_percent": safe_div_fn(fin_utilized, fin_released),
            "fin_exp_percent": safe_div_fn(fin_utilized, budget if budget else None),
            "source_period": _component_source_period(
                phys_periods.get(name, set()),
                fin_periods.get(name, set()),
            ),
        })
    return rows


async def compute_financial_status_yoy(
    db,
    scope_filter_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    extra_match: Optional[dict] = None,
    *,
    snapshot_mode: Optional[str] = None,
) -> dict:
    """Component × FY financial status for the DoJ-style Year-on-Year report.

    PMIS stores cumulative fund fields per reporting period (not native FY splits).
    Mapping used for the layout:
      - cost_estimation ← fund_allocated (fallback fund_target, then Released)
      - FY 2023-24 expenditure ← fund_utilized (DoJ utilised 2023–24 + baseline util)
      - FY 2024-25 released ← fund_released (DoJ released 2024–27 cumulative load)
      - other FY cells ← 0 (provisional / not yet split in tracker)

    When ``snapshot_mode`` is ``latest`` (or no reporting_period is given), each
    High Court × component row uses its newest loaded month so uploading July 2026
    replaces June 2026 without summing both (cumulative double-count).
    """
    use_latest = snapshot_mode == "latest" or not reporting_period
    period_for_match = None if use_latest else reporting_period
    fmatch = await build_agg_match(
        db, scope_filter_fn, user, period_for_match, False, extra_match,
    )
    fin_rolled = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch),
    ).to_list(50000)
    if use_latest:
        fin_rolled = _rows_latest_snapshot(fin_rolled, ("high_court", "component"))

    fmap: dict[str, dict] = defaultdict(
        lambda: {"allocated": None, "target": None, "released": None, "utilized": None},
    )
    fin_periods: dict[str, set[str]] = defaultdict(set)
    for row in fin_rolled:
        comp = row.get("component")
        if not comp:
            continue
        bucket = fmap[comp]
        bucket["allocated"] = sum_nullable([bucket["allocated"], row.get("fund_allocated")])
        bucket["target"] = sum_nullable([bucket["target"], row.get("fund_target")])
        bucket["released"] = sum_nullable([bucket["released"], row.get("fund_released")])
        bucket["utilized"] = sum_nullable([bucket["utilized"], row.get("fund_utilized")])
        if row.get("reporting_period"):
            fin_periods[comp].add(str(row["reporting_period"]))

    rows = []
    latest_periods: set[str] = set()
    for c in COMPONENTS:
        name = c["name"]
        f = fmap.get(name) or {"allocated": None, "target": None, "released": None, "utilized": None}
        allocated = f["allocated"]
        target = f["target"]
        released = f["released"]
        utilized = f["utilized"]
        cost = allocated if allocated not in (None, 0) else (target if target not in (None, 0) else (released or 0))
        fy2324_rel = 0.0
        fy2324_exp = float(utilized or 0)
        fy2425_rel = float(released or 0)
        fy2425_exp = 0.0
        fy2526_rel = 0.0
        fy2526_exp = 0.0
        fy2627_rel = 0.0
        fy2627_exp = 0.0
        grand_rel = fy2324_rel + fy2425_rel + fy2526_rel + fy2627_rel
        grand_exp = fy2324_exp + fy2425_exp + fy2526_exp + fy2627_exp
        if not cost and grand_rel:
            cost = grand_rel
        exp_pct = safe_div_fn(grand_exp, cost if cost else None)
        src = _component_source_period(fin_periods.get(name, set()), set())
        if src:
            latest_periods.add(src)
        rows.append({
            "component": name,
            "cost_estimation": cost,
            "fy2324_released": fy2324_rel,
            "fy2324_expenditure": fy2324_exp,
            "fy2425_released": fy2425_rel,
            "fy2425_expenditure": fy2425_exp,
            "fy2526_released": fy2526_rel,
            "fy2526_expenditure": fy2526_exp,
            "fy2627_released": fy2627_rel,
            "fy2627_expenditure": fy2627_exp,
            "grand_released": grand_rel,
            "grand_expenditure": grand_exp,
            "exp_percent_of_allocated": exp_pct,
            "source_period": src,
        })
    snapshot_label = max(latest_periods) if latest_periods else None
    return {
        "reporting_period": reporting_period,
        "snapshot_mode": "latest" if use_latest else "period",
        "snapshot_period": snapshot_label,
        "fiscal_years": ["2023-24", "2024-25", "2025-26", "2026-27"],
        "rows": rows,
        "mapping_note": (
            "Cost = Fund Allocated (fallback Target, then Released). "
            "FY 2023-24 Expenditure = Fund Utilised. "
            "FY 2024-25 Released = Fund Released (cumulative 2024–27 load). "
            "FY 2025-26 / 2026-27 cells are provisional zeros until year-split data is tracked."
        ),
    }


def _canonical_hc_label(name: Optional[str]) -> Optional[str]:
    """Prefer HIGH_COURTS en-dash spelling; otherwise normalize dashes."""
    if not name:
        return name
    norm = normalize_high_court_dashes(name, "-")
    for canonical in HIGH_COURTS:
        if normalize_high_court_dashes(canonical, "-") == norm:
            return canonical
    return normalize_high_court_dashes(name) or name


async def compute_dashboard_by_hc(
    db,
    scope_filter_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    extra_match: Optional[dict] = None,
) -> list:
    pmatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    fmatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    fin = await db.financial_entries.aggregate(financial_hc_rollup_stages(fmatch)).to_list(100)
    # Merge ASCII/en-dash HC spellings so Gauhati - Nagaland and Gauhati – Nagaland
    # do not appear as separate drill-down rows (one NA + one with funds).
    pmap: dict[str, list] = defaultdict(list)
    hc_labels: dict[str, str] = {}
    for row in rolled_phys:
        hc = row.get("high_court")
        if not hc:
            continue
        key = normalize_high_court_dashes(hc, "-") or hc
        pmap[key].append(row)
        hc_labels[key] = _canonical_hc_label(hc)
    fmap: dict[str, dict] = {}
    for f in fin:
        raw = f.get("_id")
        if not raw:
            continue
        key = normalize_high_court_dashes(raw, "-") or raw
        prev = fmap.get(key)
        if prev:
            fmap[key] = {
                "released": sum_nullable([prev.get("released"), f.get("r")]),
                "utilized": sum_nullable([prev.get("utilized"), f.get("u")]),
            }
        else:
            fmap[key] = {"released": f.get("r"), "utilized": f.get("u")}
        hc_labels[key] = _canonical_hc_label(raw)
    hcs = sorted(set(list(pmap.keys()) + list(fmap.keys())))
    selected_comp = _match_value(extra_match, "component")
    selected_uom = COMPONENT_UOM.get(selected_comp) if selected_comp else None
    rows = []
    for hc_key in hcs:
        hc_phys = pmap.get(hc_key, [])
        totals = physical_absolute_totals(hc_phys)
        # Same formula as tooltip Target/Achieved and national Physical KPI (Count-scoped sum ratio).
        phys_pct = (
            physical_kpi_achievement_percent(hc_phys, totals, safe_div_fn) if hc_phys else None
        )
        f = fmap.get(hc_key, {"released": None, "utilized": None})
        # Prefer scoped component UOM; else homogeneous absolute scope (e.g. Cloud-only filter).
        phys_uom = selected_uom or (None if totals.get("mixed_uom") else totals.get("uom"))
        rows.append({
            "high_court": hc_labels.get(hc_key) or hc_key,
            "phys_target": totals["target"],
            "phys_achieved": totals["achieved"],
            "phys_percent": phys_pct,
            "phys_uom": phys_uom,
            "mixed_uom": totals["mixed_uom"],
            "fin_released": f["released"], "fin_utilized": f["utilized"],
            "fin_percent": safe_div_fn(f["utilized"], f["released"]),
        })
    # Rank by physical achievement so drill-down surfaces leaders/laggards first.
    rows.sort(
        key=lambda r: (
            r["phys_percent"] is None,
            -(r["phys_percent"] if r["phys_percent"] is not None else 0),
            r["high_court"] or "",
        ),
    )
    return rows


def _short_hc(name: str, max_len: int = 14) -> str:
    if not name:
        return "-"
    if len(name) <= max_len:
        return name
    return name[: max_len - 1].rstrip() + "…"


async def compute_financial_tracker_dashboard(
    db,
    scope_filter_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    extra_match: Optional[dict] = None,
) -> dict:
    """Aggregates for the Financial Tracker dashboard tab (KPIs + charts).

    KPI totals sum raw ``financial_entries`` amounts first (full stored precision),
    then utilisation % is derived from those exact sums. Display rounding happens
    in the UI - never by summing already-rounded HC/component subtotals.
    """
    fmatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)

    totals = await db.financial_entries.aggregate(
        financial_exact_totals_stages(fmatch)
    ).to_list(1)
    t = totals[0] if totals else {
        "target": None, "allocated": None, "released": None, "utilized": None, "count": 0,
    }

    def _exact(key: str) -> Optional[float]:
        val = t.get(key)
        return None if val is None else float(val)

    released_exact = _exact("released")
    utilized_exact = _exact("utilized")
    target_exact = _exact("target")
    allocated_exact = _exact("allocated")

    fin_rolled = await db.financial_entries.aggregate(financial_rollup_stages(fmatch)).to_list(50000)
    hc_acc: dict[str, dict] = defaultdict(lambda: {"released": [], "utilized": []})
    comp_acc: dict[str, dict] = defaultdict(lambda: {"released": [], "utilized": []})
    comp_hc_rows = []
    for row in fin_rolled:
        hc = row.get("high_court")
        comp = row.get("component")
        if hc:
            hc_acc[hc]["released"].append(row.get("fund_released"))
            hc_acc[hc]["utilized"].append(row.get("fund_utilized"))
        if comp:
            comp_acc[comp]["released"].append(row.get("fund_released"))
            comp_acc[comp]["utilized"].append(row.get("fund_utilized"))
        if hc and comp:
            comp_hc_rows.append({
                "_id": {"component": comp, "high_court": hc},
                "released": row.get("fund_released"),
                "utilized": row.get("fund_utilized"),
            })

    hc_rows = sorted(
        (
            {
                "_id": hc,
                "released": sum_nullable(vals["released"]),
                "utilized": sum_nullable(vals["utilized"]),
            }
            for hc, vals in hc_acc.items()
        ),
        key=lambda r: (r["released"] is None, -(r["released"] or 0)),
    )
    comp_totals = sorted(
        (
            {
                "_id": comp,
                "released": sum_nullable(vals["released"]),
                "utilized": sum_nullable(vals["utilized"]),
            }
            for comp, vals in comp_acc.items()
        ),
        key=lambda r: (r["utilized"] is None, -(r["utilized"] or 0)),
    )

    # Chart series keep full stored precision so bar sums stay aligned with KPIs.
    hc_released = [
        {"high_court": r["_id"], "label": _short_hc(r["_id"]), "released": float(r["released"])}
        for r in hc_rows if r.get("released") is not None
    ]
    hc_utilized = [
        {"high_court": r["_id"], "label": _short_hc(r["_id"]), "utilized": float(r["utilized"])}
        for r in hc_rows if r.get("utilized") is not None
    ]

    # Full HC×component matrices - frontend slices Top/Bottom 6 for the charts.
    comp_by_hc: dict[str, dict] = {}
    util_pct_rows: dict[str, dict] = {}
    hc_comp_util: dict[str, dict] = {}

    for row in comp_hc_rows:
        comp = row["_id"]["component"]
        hc = row["_id"]["high_court"]
        rel = row.get("released")
        util = row.get("utilized")
        if rel is None and util is None:
            continue
        comp_by_hc.setdefault(hc, {"high_court": hc, "label": _short_hc(hc)})
        if rel is not None:
            comp_by_hc[hc][comp] = float(rel)
        util_pct_rows.setdefault(comp, {"component": comp})
        util_pct_rows[comp][hc] = safe_div_fn(util, rel)
        hc_comp_util.setdefault(hc, {"high_court": hc, "label": _short_hc(hc)})
        if util is not None:
            hc_comp_util[hc][comp] = float(util)

    component_utilization = [
        {"component": r["_id"], "utilized": float(r["utilized"])}
        for r in comp_totals if r.get("utilized") is not None
    ]

    chart_components = sorted(
        {r["_id"]["component"] for r in comp_hc_rows if r.get("released") is not None or r.get("utilized") is not None},
        key=lambda c: next((x["utilized"] for x in comp_totals if x["_id"] == c), 0),
        reverse=True,
    )[:5]

    return {
        "kpis": {
            "target": target_exact,
            "allocated": allocated_exact,
            "released": released_exact,
            "utilized": utilized_exact,
            "utilisation_percent": safe_div_fn(utilized_exact, released_exact),
        },
        "hc_released": hc_released,
        "hc_utilized": hc_utilized,
        "hc_component_released": list(comp_by_hc.values()),
        "hc_component_utilized": list(hc_comp_util.values()),
        "utilization_by_component_hc": list(util_pct_rows.values()),
        "component_utilization": component_utilization,
        "chart_components": chart_components,
    }
