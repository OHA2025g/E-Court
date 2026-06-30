"""Dashboard aggregation helpers for visualisation endpoints."""
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
    physical_hc_rollup_stages,
    physical_national_totals_stages,
    physical_period_totals_stages,
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
    rows = await db.physical_entries.aggregate(physical_hc_rollup_stages(match)).to_list(100)
    out = {}
    for r in rows:
        t, a = r.get("t") or 0, r.get("a") or 0
        if t:
            out[r["_id"]] = round((a / t) * 100, 2)
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
        for r in rows:
            t, a = r.get("t") or 0, r.get("a") or 0
            pct = round((a / t) * 100, 2) if t else None
            comp = r["_id"]["component"]
            hc = r["_id"]["high_court"]
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
    phys = await db.physical_entries.aggregate(physical_period_totals_stages(pmatch)).to_list(100)
    fin = await db.financial_entries.aggregate(financial_period_totals_stages(fmatch)).to_list(100)
    outcome = await db.outcome_entries.aggregate(outcome_period_reported_stages(omatch)).to_list(100)
    pmap = {p["_id"]: p for p in phys}
    fmap = {f["_id"]: f for f in fin}
    omap = {o["_id"]: o for o in outcome}
    periods_sorted = sorted(set(list(pmap.keys()) + list(fmap.keys()) + list(omap.keys())))
    periods = []
    for per in periods_sorted:
        p = pmap.get(per, {"target": 0, "achieved": 0})
        f = fmap.get(per, {"released": 0, "utilized": 0})
        o = omap.get(per, {"total": 0, "reported": 0})
        periods.append({
            "period": per,
            "phys_percent": safe_div_fn(p["achieved"], p["target"]) or 0,
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

    phys = await db.physical_entries.aggregate(physical_national_totals_stages(pmatch)).to_list(1)
    fin = await db.financial_entries.aggregate(financial_national_totals_stages(fmatch)).to_list(1)
    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    thresholds = await fetch_rag_thresholds(db)
    rag_counts: dict[str, int] = {}
    for row in rolled_phys:
        t, a = row.get("target") or 0, row.get("achieved") or 0
        pct = round((a / t) * 100, 2) if t else None
        status = compute_rag_fn(pct, thresholds)
        rag_counts[status] = rag_counts.get(status, 0) + 1

    p = phys[0] if phys else {"target": 0, "achieved": 0}
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

    phys_pct = safe_div_fn(p["achieved"], p["target"])
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

    phys = await db.physical_entries.aggregate(
        physical_rollup_stages(pmatch) + [
            {"$group": {"_id": None,
                        "target": {"$sum": {"$ifNull": ["$target", 0]}},
                        "achieved": {"$sum": {"$ifNull": ["$achieved", 0]}},
                        "count": {"$sum": 1}}},
        ]
    ).to_list(1)
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

    p = phys[0] if phys else {"target": 0, "achieved": 0, "count": 0}
    f = fin[0] if fin else {"released": 0, "utilized": 0, "target": 0, "count": 0}
    omatch = await build_agg_match(db, scope_filter_fn, user, reporting_period, False, extra_match)
    outcome_rows = await db.outcome_entries.aggregate(
        outcome_rollup_stages(omatch) + [{"$count": "n"}]
    ).to_list(1)
    outcome_count = outcome_rows[0]["n"] if outcome_rows else 0
    return {
        "physical": {
            "target": p["target"], "achieved": p["achieved"],
            "percent": safe_div_fn(p["achieved"], p["target"]),
            "indicator_count": p["count"],
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
    phys = await db.physical_entries.aggregate(
        physical_rollup_stages(pmatch) + [
            {"$group": {"_id": "$component",
                        "target": {"$sum": {"$ifNull": ["$target", 0]}},
                        "achieved": {"$sum": {"$ifNull": ["$achieved", 0]}}}},
        ]
    ).to_list(100)
    fin = await db.financial_entries.aggregate(
        financial_rollup_stages(fmatch) + [
            {"$group": {"_id": "$component",
                        "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
                        "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}}}},
        ]
    ).to_list(100)
    pmap = {p["_id"]: p for p in phys}
    fmap = {f["_id"]: f for f in fin}
    rows = []
    for c in COMPONENTS:
        name = c["name"]
        p = pmap.get(name, {"target": 0, "achieved": 0})
        f = fmap.get(name, {"released": 0, "utilized": 0})
        rows.append({
            "component": name,
            "phys_target": p["target"], "phys_achieved": p["achieved"],
            "phys_percent": safe_div_fn(p["achieved"], p["target"]),
            "fin_released": f["released"], "fin_utilized": f["utilized"],
            "fin_percent": safe_div_fn(f["utilized"], f["released"]),
        })
    return rows


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
    phys = await db.physical_entries.aggregate(physical_hc_rollup_stages(pmatch)).to_list(100)
    fin = await db.financial_entries.aggregate(financial_hc_rollup_stages(fmatch)).to_list(100)
    pmap = {p["_id"]: {"target": p["t"], "achieved": p["a"]} for p in phys}
    fmap = {f["_id"]: {"released": f["r"], "utilized": f["u"]} for f in fin}
    hcs = sorted(set(list(pmap.keys()) + list(fmap.keys())))
    rows = []
    for hc in hcs:
        p = pmap.get(hc, {"target": 0, "achieved": 0})
        f = fmap.get(hc, {"released": 0, "utilized": 0})
        rows.append({
            "high_court": hc,
            "phys_target": p["target"], "phys_achieved": p["achieved"],
            "phys_percent": safe_div_fn(p["achieved"], p["target"]),
            "fin_released": f["released"], "fin_utilized": f["utilized"],
            "fin_percent": safe_div_fn(f["utilized"], f["released"]),
        })
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
