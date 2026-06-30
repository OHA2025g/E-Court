"""Initialize tracker rows from master data."""
from typing import Callable, Optional


async def init_physical_period(
    db,
    high_court: str,
    reporting_period: str,
    user: dict,
    compute_rag_fn: Callable,
    thresholds: dict,
    now_utc_fn: Callable,
    component: Optional[str] = None,
) -> dict:
    if user["role"] == "CPC" and high_court != user.get("high_court"):
        raise ValueError("CPC limited to own High Court")

    ind_query = {}
    if component:
        ind_query["component"] = component
    indicators = await db.indicators.find(ind_query, {"_id": 0}).to_list(5000)
    created, skipped = 0, 0
    for ind in indicators:
        q = {
            "high_court": high_court,
            "component": ind["component"],
            "indicator": ind["indicator"],
            "reporting_period": reporting_period,
            "district": None,
        }
        existing = await db.physical_entries.find_one(q)
        if existing:
            skipped += 1
            continue
        doc = {
            **q,
            "target": None,
            "achieved": None,
            "percent": None,
            "rag": "NA",
            "remarks": None,
            "source": "template_init",
            "created_by": user["email"],
            "created_at": now_utc_fn(),
            "updated_by": user["email"],
            "updated_at": now_utc_fn(),
        }
        await db.physical_entries.insert_one(doc)
        created += 1
    return {"created": created, "skipped": skipped, "high_court": high_court, "reporting_period": reporting_period}


async def init_financial_period(
    db,
    high_court: str,
    reporting_period: str,
    user: dict,
    compute_rag_fn: Callable,
    thresholds: dict,
    now_utc_fn: Callable,
    component: Optional[str] = None,
) -> dict:
    if user["role"] == "CPC" and high_court != user.get("high_court"):
        raise ValueError("CPC limited to own High Court")

    comp_query = {}
    if component:
        comp_query["name"] = component
    components = await db.components.find(comp_query, {"_id": 0}).to_list(500)
    created, skipped = 0, 0
    for comp in components:
        q = {
            "high_court": high_court,
            "component": comp["name"],
            "reporting_period": reporting_period,
            "district": None,
        }
        existing = await db.financial_entries.find_one(q)
        if existing:
            skipped += 1
            continue
        doc = {
            **q,
            "description": comp.get("description"),
            "fund_target": None,
            "fund_allocated": None,
            "fund_released": None,
            "fund_utilized": None,
            "utilisation_percent": None,
            "variance": None,
            "rag": "NA",
            "remarks": None,
            "source": "template_init",
            "created_by": user["email"],
            "created_at": now_utc_fn(),
            "updated_by": user["email"],
            "updated_at": now_utc_fn(),
        }
        await db.financial_entries.insert_one(doc)
        created += 1
    return {"created": created, "skipped": skipped, "high_court": high_court, "reporting_period": reporting_period}


async def init_outcome_period(
    db,
    high_court: str,
    reporting_period: str,
    user: dict,
    safe_div_fn: Callable,
    now_utc_fn: Callable,
    subject: Optional[str] = None,
) -> dict:
    if user["role"] == "CPC" and high_court != user.get("high_court"):
        raise ValueError("CPC limited to own High Court")

    kpi_query = {}
    if subject:
        kpi_query["subject"] = subject
    kpis = await db.kpis.find(kpi_query, {"_id": 0}).to_list(5000)
    districts = await db.districts.find(
        {"high_court": high_court, "active": True}, {"_id": 0}
    ).to_list(500)
    created, skipped = 0, 0

    async def _insert_row(q: dict, kpi: dict) -> None:
        nonlocal created, skipped
        existing = await db.outcome_entries.find_one(q)
        if existing:
            skipped += 1
            return
        outcome_type = kpi.get("outcome_type") or "Absolute"
        doc = {
            **q,
            "component": kpi.get("component"),
            "sub_component": kpi.get("sub_component"),
            "kpi": kpi.get("kpi"),
            "description": kpi.get("description"),
            "periodicity": kpi.get("periodicity"),
            "outcome_type": outcome_type,
            "value_type": kpi.get("value_type") or "Count",
            "baseline": None,
            "value": None,
            "computed_percent": None,
            "remarks": None,
            "source": "template_init",
            "created_by": user["email"],
            "created_at": now_utc_fn(),
            "updated_by": user["email"],
            "updated_at": now_utc_fn(),
        }
        await db.outcome_entries.insert_one(doc)
        created += 1

    for kpi in kpis:
        gran = kpi.get("granularity") or "District"
        base = {
            "subject": kpi["subject"],
            "kpi_id": kpi["kpi_id"],
            "reporting_period": reporting_period,
            "granularity": gran,
        }
        if gran == "National":
            q = {**base, "high_court": None, "district": None}
            await _insert_row(q, kpi)
        elif gran == "State":
            q = {**base, "high_court": high_court, "district": None}
            await _insert_row(q, kpi)
        elif gran == "District":
            if not districts:
                q = {**base, "high_court": high_court, "district": None}
                await _insert_row(q, kpi)
            for dist in districts:
                q = {**base, "high_court": high_court, "district": dist["name"]}
                await _insert_row(q, kpi)

    return {"created": created, "skipped": skipped, "high_court": high_court, "reporting_period": reporting_period}
