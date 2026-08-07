"""Dashboard aggregation helpers for visualisation endpoints."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from rollup import (
    financial_component_hc_stages,
    financial_hc_rollup_stages,
    financial_national_totals_stages,
    financial_period_totals_stages,
    financial_rollup_stages,
    outcome_hc_rollup_stages,
    outcome_period_reported_stages,
    outcome_rollup_stages,
    physical_component_hc_stages,
    physical_rollup_stages,
)
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
        if pct is not None:
            pcts.append(pct)
    if not pcts:
        return None
    return round(sum(pcts) / len(pcts), 2)


def physical_absolute_totals(rows: list) -> dict:
    """Sum target/achieved in a single display UOM for KPI cards.

    - Drops non-summable UOMs (Cloud GB/TB/PB, Percentage) so storage capacity
      cannot inflate Phys Achieved.
    - When Count and Crore Pages both exist, shows Count totals (primary UOM)
      and sets mixed_uom=True so % stays mean-of-indicators, not ratio-of-sums.
    """
    active = [
        r for r in rows
        if (r.get("target") or 0) != 0 or (r.get("achieved") or 0) != 0
    ]
    if not active:
        return {
            "target": 0.0,
            "achieved": 0.0,
            "mixed_uom": False,
            "uom": None,
            "absolute_scope": None,
        }

    all_uoms = {_row_uom(r) for r in active}
    summable = [r for r in active if _row_uom(r) not in NON_SUMMABLE_UOMS]
    summable_uoms = {_row_uom(r) for r in summable}

    if not summable:
        # Only storage/percentage in scope (e.g. Cloud filter) — show that UOM.
        if len(all_uoms) == 1:
            uom = next(iter(all_uoms))
            return {
                "target": sum(float(r.get("target") or 0) for r in active),
                "achieved": sum(float(r.get("achieved") or 0) for r in active),
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
        # Multiple non-Count summable UOMs — pick the UOM with the most rows.
        by_uom: dict[str, list] = defaultdict(list)
        for r in summable:
            by_uom[_row_uom(r)].append(r)
        scope = max(by_uom.keys(), key=lambda u: len(by_uom[u]))
        scoped = by_uom[scope]

    return {
        "target": sum(float(r.get("target") or 0) for r in scoped),
        "achieved": sum(float(r.get("achieved") or 0) for r in scoped),
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
    """HC physical % = mean of per-indicator % (avoids mixed-UOM sum/sum distortion).

    Falls back to relative-vs-max achieved when targets are absent (Cloud storage GB).
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
    out = {
        hc: pct
        for hc, hc_rows in by_hc.items()
        if (pct := mean_achievement_percent(hc_rows, _pct)) is not None
    }
    if out:
        return out
    return relative_achieved_percent_by_hc(by_hc)


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
    user_hc = user.get("high_court") if user.get("role") == "CPC" else None
    out = {}
    for state, hc in state_to_hc.items():
        if user_hc and hc != user_hc:
            out[state] = {"high_court": hc, "percent": None, "rag": "NA", "in_scope": False}
            continue
        pct = hc_pct.get(hc)
        out[state] = {
            "high_court": hc,
            "percent": pct,
            "rag": compute_rag_fn(pct, thresholds),
            "in_scope": True,
        }
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
            rel, util = r.get("r") or 0, r.get("u") or 0
            pct = round((util / rel) * 100, 2) if rel else None
            comp = r["_id"]["component"]
            hc = r["_id"]["high_court"]
            cell_map[(comp, hc)] = {"percent": pct, "rag": compute_rag_fn(pct, thresholds)}
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
            cell_map[(subj, hc)] = {"percent": pct, "rag": compute_rag_fn(pct, thresholds)}
        row_keys = subjects
        row_field = "subject"
    else:
        rows = await db.physical_entries.aggregate(physical_component_hc_stages(match)).to_list(500)
        # Per-component peak achieved for target-less rows (Cloud GB capacity)
        peak_by_comp: dict[str, float] = defaultdict(float)
        for r in rows:
            comp = r["_id"]["component"]
            a = float(r.get("a") or 0)
            if a > peak_by_comp[comp]:
                peak_by_comp[comp] = a
        for r in rows:
            t, a = float(r.get("t") or 0), float(r.get("a") or 0)
            comp = r["_id"]["component"]
            hc = r["_id"]["high_court"]
            if t:
                pct = round((a / t) * 100, 2)
            elif a > 0 and peak_by_comp.get(comp):
                pct = round(100.0 * a / peak_by_comp[comp], 2)
            else:
                pct = None
            cell_map[(comp, hc)] = {"percent": pct, "rag": compute_rag_fn(pct, thresholds)}
        row_keys = components
        row_field = "component"

    cells = []
    for row_key in row_keys:
        for hc in hcs:
            info = cell_map.get((row_key, hc), {"percent": None, "rag": "NA"})
            cell = {
                row_field: row_key,
                "high_court": hc,
                "percent": info["percent"],
                "rag": info["rag"],
            }
            if row_field == "component":
                cell["component"] = row_key
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
        for r in rolled:
            t, a = r.get("target") or 0, r.get("achieved") or 0
            pct = round((a / t) * 100, 2) if t else None
            if compute_rag_fn(pct, thresholds) != "RED":
                continue
            comp = r.get("component") or "Unknown"
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
        f = fmap.get(per, {"released": 0, "utilized": 0})
        o = omap.get(per, {"total": 0, "reported": 0})
        periods.append({
            "period": per,
            "phys_percent": mean_achievement_percent(pmap.get(per, []), safe_div_fn) or 0,
            "fin_percent": safe_div_fn(f["utilized"], f["released"]) or 0,
            "outcome_reported_pct": safe_div_fn(o["reported"], o["total"]) or 0,
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
) -> dict:
    pmatch: dict = {}
    fmatch: dict = {}
    if reporting_period:
        pmatch["reporting_period"] = reporting_period
        fmatch["reporting_period"] = reporting_period
    if extra_match:
        pmatch = merge_match(pmatch, extra_match)
        fmatch = merge_match(fmatch, extra_match)

    fin = await db.financial_entries.aggregate(financial_national_totals_stages(fmatch)).to_list(1)
    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    phys_totals = physical_absolute_totals(rolled_phys)
    thresholds = await fetch_rag_thresholds(db)
    rag_counts: dict[str, int] = {}
    for row in rolled_phys:
        pct = safe_div_fn(row.get("achieved"), row.get("target"))
        status = compute_rag_fn(pct, thresholds)
        rag_counts[status] = rag_counts.get(status, 0) + 1

    p = {
        "target": phys_totals["target"] if phys_totals["target"] is not None else 0,
        "achieved": phys_totals["achieved"] if phys_totals["achieved"] is not None else 0,
    }
    f = fin[0] if fin else {"released": 0, "utilized": 0}
    omatch: dict = {}
    if reporting_period:
        omatch["reporting_period"] = reporting_period
    if extra_match:
        omatch = merge_match(omatch, extra_match)
    outcome_rolled = await db.outcome_entries.aggregate(outcome_rollup_stages(omatch)).to_list(50000)
    outcome_reported = sum(1 for row in outcome_rolled if row.get("value") is not None)
    outcome_total = len(outcome_rolled)
    outcome_pct = safe_div_fn(outcome_reported, outcome_total)

    outcome_hc_rows = await db.outcome_entries.aggregate(outcome_hc_rollup_stages(omatch)).to_list(50)
    outcome_hc_ranking = []
    for r in outcome_hc_rows:
        total = r.get("total") or 0
        reported = r.get("reported") or 0
        if total > 0:
            pct = safe_div_fn(reported, total)
            outcome_hc_ranking.append({
                "high_court": r["_id"],
                "reported_count": reported,
                "kpi_count": total,
                "reporting_percent": pct,
            })
    outcome_hc_ranking.sort(key=lambda x: x["reporting_percent"] or 0, reverse=True)

    if phys_totals["mixed_uom"]:
        phys_pct = mean_achievement_percent(rolled_phys, safe_div_fn)
    else:
        phys_pct = safe_div_fn(phys_totals["achieved"], phys_totals["target"])
    fin_pct = safe_div_fn(f["utilized"], f["released"])

    hc_pct = await aggregate_hc_percent_physical(db, pmatch)
    thresholds = await fetch_rag_thresholds(db)
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
    trend = await compute_trend_with_milestones(db, public_scope, safe_div_fn, public_user, extra_match)
    heatmap = await compute_heatmap(db, public_scope, compute_rag_fn, public_user, reporting_period, "physical", extra_match)
    pareto = await compute_pareto_red_flags(db, public_scope, compute_rag_fn, public_user, reporting_period, "physical", extra_match)
    states_financial = await compute_states_rag(
        db, state_to_hc, public_scope, compute_rag_fn, public_user, reporting_period, "financial", extra_match,
    )
    states_outcome = await compute_states_rag(
        db, state_to_hc, public_scope, compute_rag_fn, public_user, reporting_period, "outcome", extra_match,
    )

    pair = resolve_period_pair(reporting_period)
    comparison_period = pair[0] if pair else None
    rag_delta = None
    if comparison_period:
        rag_delta = await compute_rag_delta(
            db, public_scope, compute_rag_fn, safe_div_fn, public_user, comparison_period, "physical", extra_match,
        )

    fin_hc_rows = await db.financial_entries.aggregate(financial_hc_rollup_stages(fmatch)).to_list(50)
    fin_hc_ranking = []
    for r in fin_hc_rows:
        pct = safe_div_fn(r.get("u"), r.get("r"))
        if pct is not None:
            fin_hc_ranking.append({"high_court": r["_id"], "fin_percent": pct})
    fin_hc_ranking.sort(key=lambda x: x["fin_percent"] or 0, reverse=True)

    return {
        "reporting_period": reporting_period,
        "comparison_period": comparison_period,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "physical": {
            "percent": phys_pct,
            "target": p["target"],
            "achieved": p["achieved"],
        },
        "financial": {
            "utilisation_percent": fin_pct,
            "released": f["released"],
            "utilized": f["utilized"],
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
        financial_rollup_stages(fmatch) + [
            {"$group": {"_id": None,
                        "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                        "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
                        "target": {"$sum": {"$ifNull": ["$fund_target", 0]}},
                        "count": {"$sum": 1}}},
        ]
    ).to_list(1)
    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    phys_totals = physical_absolute_totals(rolled_phys)
    # Homogeneous UOM → ratio of sums; mixed UOMs → equal-weight mean of indicator %.
    if phys_totals["mixed_uom"]:
        phys_percent = mean_achievement_percent(rolled_phys, safe_div_fn)
    else:
        phys_percent = safe_div_fn(phys_totals["achieved"], phys_totals["target"])
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

    f = fin[0] if fin else {"released": 0, "utilized": 0, "target": 0, "count": 0}
    omatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    outcome_rows = await db.outcome_entries.aggregate(
        outcome_rollup_stages(omatch) + [{"$count": "n"}]
    ).to_list(1)
    outcome_count = outcome_rows[0]["n"] if outcome_rows else 0
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
        "financial": {
            "target": f["target"], "released": f["released"], "utilized": f["utilized"],
            "utilisation_percent": safe_div_fn(f["utilized"], f["released"]),
            "variance": round((f["released"] - f["utilized"]), 2),
            "component_count": f["count"],
        },
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


async def compute_dashboard_by_component(
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
    fin = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch) + [
            {"$group": {"_id": "$component",
                        "allocated": {"$sum": {"$ifNull": ["$fund_allocated", 0]}},
                        "target": {"$sum": {"$ifNull": ["$fund_target", 0]}},
                        "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                        "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}}}},
        ]
    ).to_list(100)
    pmap: dict[str, list] = defaultdict(list)
    for row in rolled_phys:
        comp = row.get("component")
        if comp:
            pmap[comp].append(row)
    fmap = {f["_id"]: f for f in fin}
    selected = _match_value(extra_match, "component")
    components = [c for c in COMPONENTS if not selected or c["name"] == selected]
    rows = []
    for c in components:
        name = c["name"]
        phys_rows = pmap.get(name, [])
        # Single-component scope is always one UOM — absolute sums are valid here.
        target = sum(float(r.get("target") or 0) for r in phys_rows)
        achieved = sum(float(r.get("achieved") or 0) for r in phys_rows)
        f = fmap.get(name, {"allocated": 0, "target": 0, "released": 0, "utilized": 0})
        budget = f["allocated"] or f["target"] or f["released"] or 0
        rows.append({
            "component": name,
            "phys_target": target,
            "phys_achieved": achieved,
            # One UOM per component — ratio of sums; null when target is 0 (e.g. Cloud GB).
            "phys_percent": safe_div_fn(achieved, target if target else None),
            "fin_allocated": f["allocated"],
            "fin_target": f["target"],
            "fin_budget": budget,
            "fin_released": f["released"], "fin_utilized": f["utilized"],
            "fin_percent": safe_div_fn(f["utilized"], f["released"]),
            "fin_exp_percent": safe_div_fn(f["utilized"], budget if budget else None),
        })
    return rows


async def compute_financial_status_yoy(
    db,
    scope_filter_fn: Callable,
    safe_div_fn: Callable,
    user: dict,
    reporting_period: Optional[str],
    extra_match: Optional[dict] = None,
) -> dict:
    """Component × FY financial status for the DoJ-style Year-on-Year demo report.

    PMIS stores cumulative fund fields per reporting period (not native FY splits).
    Mapping used for the demo layout:
      - cost_estimation ← fund_allocated (fallback fund_target)
      - FY 2023-24 expenditure ← fund_utilized (DoJ utilised 2023–24 + baseline util)
      - FY 2024-25 released ← fund_released (DoJ released 2024–27 cumulative load)
      - other FY cells ← 0 (provisional / not yet split in tracker)
    """
    fmatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    fin = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch) + [
            {"$group": {"_id": "$component",
                        "allocated": {"$sum": {"$ifNull": ["$fund_allocated", 0]}},
                        "target": {"$sum": {"$ifNull": ["$fund_target", 0]}},
                        "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                        "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}}}},
        ]
    ).to_list(100)
    fmap = {f["_id"]: f for f in fin}
    rows = []
    for c in COMPONENTS:
        name = c["name"]
        f = fmap.get(name, {"allocated": 0, "target": 0, "released": 0, "utilized": 0})
        cost = f["allocated"] or f["target"] or 0
        fy2324_rel = 0.0
        fy2324_exp = float(f["utilized"] or 0)
        fy2425_rel = float(f["released"] or 0)
        fy2425_exp = 0.0
        fy2526_rel = 0.0
        fy2526_exp = 0.0
        fy2627_rel = 0.0
        fy2627_exp = 0.0
        grand_rel = fy2324_rel + fy2425_rel + fy2526_rel + fy2627_rel
        grand_exp = fy2324_exp + fy2425_exp + fy2526_exp + fy2627_exp
        exp_pct = safe_div_fn(grand_exp, cost if cost else None)
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
        })
    return {
        "reporting_period": reporting_period,
        "fiscal_years": ["2023-24", "2024-25", "2025-26", "2026-27"],
        "rows": rows,
        "mapping_note": (
            "Cost = Fund Allocated (fallback Target). "
            "FY 2023-24 Expenditure = Fund Utilised. "
            "FY 2024-25 Released = Fund Released (cumulative 2024–27 load). "
            "FY 2025-26 / 2026-27 cells are provisional zeros until year-split data is tracked."
        ),
    }


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
    pmap: dict[str, list] = defaultdict(list)
    for row in rolled_phys:
        hc = row.get("high_court")
        if hc:
            pmap[hc].append(row)
    fmap = {f["_id"]: {"released": f["r"], "utilized": f["u"]} for f in fin}
    hcs = sorted(set(list(pmap.keys()) + list(fmap.keys())))
    target_pcts = {
        hc: mean_achievement_percent(pmap.get(hc, []), safe_div_fn)
        for hc in hcs
        if pmap.get(hc)
    }
    target_pcts = {hc: pct for hc, pct in target_pcts.items() if pct is not None}
    relative_pcts = (
        {} if target_pcts else relative_achieved_percent_by_hc(pmap)
    )
    rows = []
    for hc in hcs:
        hc_phys = pmap.get(hc, [])
        totals = physical_absolute_totals(hc_phys)
        # Prefer target-based mean %; fall back to relative-vs-max for Cloud GB (no targets).
        phys_pct = target_pcts.get(hc)
        if phys_pct is None:
            phys_pct = relative_pcts.get(hc)
        f = fmap.get(hc, {"released": 0, "utilized": 0})
        rows.append({
            "high_court": hc,
            "phys_target": totals["target"],
            "phys_achieved": totals["achieved"],
            "phys_percent": phys_pct,
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
        return "—"
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
    """Aggregates for the Financial Tracker dashboard tab (KPIs + charts)."""
    fmatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)

    totals = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch) + [
            {"$group": {
                "_id": None,
                "target": {"$sum": {"$ifNull": ["$fund_target", 0]}},
                "allocated": {"$sum": {"$ifNull": ["$fund_allocated", 0]}},
                "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
            }},
        ]
    ).to_list(1)
    t = totals[0] if totals else {"target": 0, "allocated": 0, "released": 0, "utilized": 0}

    hc_rows = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch) + [
            {"$group": {
                "_id": "$high_court",
                "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
            }},
            {"$sort": {"released": -1}},
        ]
    ).to_list(100)

    comp_hc_rows = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch) + [
            {"$group": {
                "_id": {"component": "$component", "high_court": "$high_court"},
                "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
            }},
        ]
    ).to_list(5000)

    comp_totals = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch) + [
            {"$group": {
                "_id": "$component",
                "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
            }},
            {"$sort": {"utilized": -1}},
        ]
    ).to_list(100)

    hc_released = [
        {"high_court": r["_id"], "label": _short_hc(r["_id"]), "released": round(r["released"], 2)}
        for r in hc_rows if r.get("released")
    ]
    hc_utilized = [
        {"high_court": r["_id"], "label": _short_hc(r["_id"]), "utilized": round(r["utilized"], 2)}
        for r in hc_rows if r.get("utilized")
    ]

    top_hcs = [r["_id"] for r in hc_rows[:6]]
    comp_by_hc: dict[str, dict] = {}
    util_pct_rows: dict[str, dict] = {}
    hc_comp_util: dict[str, dict] = {}

    for row in comp_hc_rows:
        comp = row["_id"]["component"]
        hc = row["_id"]["high_court"]
        rel = row.get("released") or 0
        util = row.get("utilized") or 0
        if hc not in top_hcs:
            continue
        comp_by_hc.setdefault(hc, {"high_court": hc, "label": _short_hc(hc)})
        comp_by_hc[hc][comp] = round(rel, 2)
        util_pct_rows.setdefault(comp, {"component": comp})
        util_pct_rows[comp][hc] = safe_div_fn(util, rel)
        hc_comp_util.setdefault(hc, {"high_court": hc, "label": _short_hc(hc)})
        hc_comp_util[hc][comp] = round(util, 2)

    component_utilization = [
        {"component": r["_id"], "utilized": round(r["utilized"], 2)}
        for r in comp_totals if r.get("utilized")
    ]

    task_q: dict = {}
    if user.get("role") == "CPC" and user.get("high_court"):
        task_q["high_court_name"] = user["high_court"]

    task_by_comp = await db.tm_tasks.aggregate([
        {"$match": task_q},
        {"$group": {"_id": {"$ifNull": ["$component", "Unassigned"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]).to_list(50)

    now = datetime.now(timezone.utc)
    weekly_task_status = []
    for w in range(3, -1, -1):
        week_start = (now - timedelta(days=now.weekday() + w * 7)).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        created = await db.tm_tasks.count_documents({
            **task_q,
            "created_at": {"$gte": week_start, "$lte": week_end},
        })
        completed = await db.tm_tasks.count_documents({
            **task_q,
            "status": "CLOSED",
            "closed_at": {"$gte": week_start, "$lte": week_end},
        })
        still_open = await db.tm_tasks.count_documents({
            **task_q,
            "created_at": {"$lte": week_end},
            "status": {"$nin": ["CLOSED", "CANCELLED", "DUPLICATE"]},
        })
        weekly_task_status.append({
            "week": f"Week {4 - w}",
            "range": f"{week_start.strftime('%d-%m-%Y')} to {week_end.strftime('%d-%m-%Y')}",
            "created": created,
            "completed": completed,
            "still_open": still_open,
        })

    chart_components = sorted(
        {r["_id"]["component"] for r in comp_hc_rows if r.get("released") or r.get("utilized")},
        key=lambda c: next((x["utilized"] for x in comp_totals if x["_id"] == c), 0),
        reverse=True,
    )[:5]

    return {
        "kpis": {
            "target": round(t["target"], 2),
            "allocated": round(t["allocated"], 2),
            "released": round(t["released"], 2),
            "utilized": round(t["utilized"], 2),
            "utilisation_percent": safe_div_fn(t["utilized"], t["released"]),
        },
        "hc_released": hc_released,
        "hc_utilized": hc_utilized,
        "hc_component_released": list(comp_by_hc.values()),
        "hc_component_utilized": list(hc_comp_util.values()),
        "utilization_by_component_hc": list(util_pct_rows.values()),
        "component_utilization": component_utilization,
        "chart_components": chart_components,
        "task_count_by_component": [
            {"component": r["_id"] or "Unassigned", "count": r["count"]} for r in task_by_comp
        ],
        "weekly_task_status": weekly_task_status,
    }
