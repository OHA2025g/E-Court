"""Master Routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from seed_constants import DEFAULT_RAG_THRESHOLDS


def register_master_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    require_role,
    audit_fn,
    default_rag_thresholds: dict = DEFAULT_RAG_THRESHOLDS,
):
    @api.get("/master/high-courts")
    async def list_high_courts(_: dict = Depends(require_fully_authenticated)):
        return await db.high_courts.find({}, {"_id": 0}).sort("name", 1).to_list(100)

    class HighCourtIn(BaseModel):
        name: str
        active: bool = True

    @api.post("/master/high-courts")
    async def create_high_court(body: HighCourtIn, user: dict = Depends(require_role("Admin"))):
        if await db.high_courts.find_one({"name": body.name}):
            raise HTTPException(status_code=400, detail="High Court already exists")
        await db.high_courts.insert_one(body.model_dump())
        await audit_fn(user, "master", "create_high_court", body.name,
                    [{"field": "high_court", "old": None, "new": body.model_dump()}])
        return {"ok": True}

    @api.put("/master/high-courts/{name}")
    async def update_high_court(name: str, body: HighCourtIn, user: dict = Depends(require_role("Admin"))):
        existing = await db.high_courts.find_one({"name": name})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        if body.name != name and await db.high_courts.find_one({"name": body.name}):
            raise HTTPException(status_code=400, detail="Target name already exists")
        await db.high_courts.update_one({"name": name}, {"$set": body.model_dump()})
        await audit_fn(user, "master", "update_high_court", name,
                    [{"field": "high_court", "old": {"name": name, "active": existing.get("active")},
                      "new": body.model_dump()}])
        return {"ok": True}

    @api.delete("/master/high-courts/{name}")
    async def delete_high_court(name: str, user: dict = Depends(require_role("Admin"))):
        if await db.physical_entries.find_one({"high_court": name}) or await db.financial_entries.find_one({"high_court": name}):
            raise HTTPException(status_code=400, detail="Cannot delete: tracker entries exist for this HC")
        if await db.outcome_entries.find_one({"high_court": name}):
            raise HTTPException(status_code=400, detail="Cannot delete: outcome entries exist for this HC")
        if await db.districts.find_one({"high_court": name}):
            raise HTTPException(status_code=400, detail="Cannot delete: districts exist for this HC")
        if await db.users.find_one({"high_court": name}):
            raise HTTPException(status_code=400, detail="Cannot delete: users assigned to this HC")
        await db.high_courts.delete_one({"name": name})
        await audit_fn(user, "master", "delete_high_court", name, [])
        return {"ok": True}

    # Components
    class ComponentIn(BaseModel):
        code: str
        name: str
        uom: str
        seq: Optional[int] = None

    @api.get("/master/components")
    async def list_components(_: dict = Depends(require_fully_authenticated)):
        return await db.components.find({}, {"_id": 0}).sort("seq", 1).to_list(100)

    @api.post("/master/components")
    async def create_component(body: ComponentIn, user: dict = Depends(require_role("Admin"))):
        if await db.components.find_one({"name": body.name}) or await db.components.find_one({"code": body.code}):
            raise HTTPException(status_code=400, detail="Code or name already exists")
        doc = body.model_dump()
        if not doc.get("seq"):
            last = await db.components.find_one(sort=[("seq", -1)])
            doc["seq"] = (last.get("seq", 0) if last else 0) + 1
        await db.components.insert_one(doc)
        await audit_fn(user, "master", "create_component", body.code,
                    [{"field": "component", "old": None, "new": doc}])
        return {"ok": True}

    @api.put("/master/components/{code}")
    async def update_component(code: str, body: ComponentIn, user: dict = Depends(require_role("Admin"))):
        existing = await db.components.find_one({"code": code})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        doc = body.model_dump()
        if not doc.get("seq"):
            doc["seq"] = existing.get("seq")
        await db.components.update_one({"code": code}, {"$set": doc})
        await audit_fn(user, "master", "update_component", code,
                    [{"field": "component", "old": {k: existing.get(k) for k in doc}, "new": doc}])
        return {"ok": True}

    @api.delete("/master/components/{code}")
    async def delete_component(code: str, user: dict = Depends(require_role("Admin"))):
        comp = await db.components.find_one({"code": code})
        if not comp:
            raise HTTPException(status_code=404, detail="Not found")
        if await db.physical_entries.find_one({"component": comp["name"]}) or await db.financial_entries.find_one({"component": comp["name"]}):
            raise HTTPException(status_code=400, detail="Cannot delete: tracker entries exist for this component")
        await db.components.delete_one({"code": code})
        await db.indicators.delete_many({"component": comp["name"]})
        await audit_fn(user, "master", "delete_component", code, [])
        return {"ok": True}

    # Indicators
    class IndicatorIn(BaseModel):
        component: str
        indicator: str
        unit: str = "Count"
        data_type: str = "Int"

    @api.get("/master/indicators")
    async def list_indicators(component: Optional[str] = None, _: dict = Depends(require_fully_authenticated)):
        q = {}
        if component:
            q["component"] = component
        return await db.indicators.find(q, {"_id": 0}).to_list(500)

    @api.post("/master/indicators")
    async def create_indicator(body: IndicatorIn, user: dict = Depends(require_role("Admin"))):
        if await db.indicators.find_one({"component": body.component, "indicator": body.indicator}):
            raise HTTPException(status_code=400, detail="Indicator already exists for this component")
        await db.indicators.insert_one(body.model_dump())
        await audit_fn(user, "master", "create_indicator", body.indicator,
                    [{"field": "indicator", "old": None, "new": body.model_dump()}])
        return {"ok": True}

    @api.put("/master/indicators")
    async def update_indicator(body: IndicatorIn, original_indicator: str = Query(...),
                                user: dict = Depends(require_role("Admin"))):
        existing = await db.indicators.find_one({"component": body.component, "indicator": original_indicator})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        await db.indicators.update_one(
            {"component": body.component, "indicator": original_indicator},
            {"$set": body.model_dump()}
        )
        await audit_fn(user, "master", "update_indicator", body.indicator,
                    [{"field": "indicator", "old": {"indicator": original_indicator}, "new": body.model_dump()}])
        return {"ok": True}

    @api.delete("/master/indicators")
    async def delete_indicator(component: str = Query(...), indicator: str = Query(...),
                                user: dict = Depends(require_role("Admin"))):
        if await db.physical_entries.find_one({"component": component, "indicator": indicator}):
            raise HTTPException(status_code=400, detail="Cannot delete: physical entries exist for this indicator")
        await db.indicators.delete_one({"component": component, "indicator": indicator})
        await audit_fn(user, "master", "delete_indicator", indicator, [])
        return {"ok": True}

    # Outcome Subjects
    class OutcomeSubjectIn(BaseModel):
        name: str

    @api.get("/master/outcome-subjects")
    async def list_outcome_subjects(_: dict = Depends(require_fully_authenticated)):
        return await db.outcome_subjects.find({}, {"_id": 0}).to_list(100)

    @api.post("/master/outcome-subjects")
    async def create_outcome_subject(body: OutcomeSubjectIn, user: dict = Depends(require_role("Admin"))):
        if await db.outcome_subjects.find_one({"name": body.name}):
            raise HTTPException(status_code=400, detail="Subject already exists")
        await db.outcome_subjects.insert_one(body.model_dump())
        await audit_fn(user, "master", "create_subject", body.name, [])
        return {"ok": True}

    class OutcomeSubjectUpdateIn(BaseModel):
        name: str

    @api.put("/master/outcome-subjects/{name}")
    async def update_outcome_subject(name: str, body: OutcomeSubjectUpdateIn,
                                      user: dict = Depends(require_role("Admin"))):
        existing = await db.outcome_subjects.find_one({"name": name})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        if body.name != name:
            if await db.outcome_entries.find_one({"subject": name}):
                raise HTTPException(status_code=400, detail="Cannot rename: outcome entries exist for this subject")
            if await db.outcome_subjects.find_one({"name": body.name}):
                raise HTTPException(status_code=400, detail="Target name already exists")
            await db.outcome_subjects.update_one({"name": name}, {"$set": {"name": body.name}})
            await db.kpis.update_many({"subject": name}, {"$set": {"subject": body.name}})
            await db.outcome_entries.update_many({"subject": name}, {"$set": {"subject": body.name}})
        await audit_fn(user, "master", "update_subject", name, [])
        return {"ok": True}

    @api.delete("/master/outcome-subjects/{name}")
    async def delete_outcome_subject(name: str, user: dict = Depends(require_role("Admin"))):
        if await db.outcome_entries.find_one({"subject": name}):
            raise HTTPException(status_code=400, detail="Cannot delete: outcome entries exist for this subject")
        await db.outcome_subjects.delete_one({"name": name})
        await db.kpis.delete_many({"subject": name})
        await audit_fn(user, "master", "delete_subject", name, [])
        return {"ok": True}

    # KPIs
    class KpiIn(BaseModel):
        subject: str
        kpi_id: str
        kpi: str
        description: Optional[str] = None
        periodicity: Optional[str] = "Monthly"
        granularity: Optional[str] = "District"
        outcome_type: Optional[str] = "Absolute"
        value_type: Optional[str] = "Count"

    @api.get("/master/kpis")
    async def list_kpis(subject: Optional[str] = None, _: dict = Depends(require_fully_authenticated)):
        q = {}
        if subject:
            q["subject"] = subject
        return await db.kpis.find(q, {"_id": 0}).to_list(500)

    @api.post("/master/kpis")
    async def create_kpi(body: KpiIn, user: dict = Depends(require_role("Admin"))):
        if await db.kpis.find_one({"subject": body.subject, "kpi_id": body.kpi_id}):
            raise HTTPException(status_code=400, detail="KPI ID already exists for this subject")
        await db.kpis.insert_one(body.model_dump())
        await audit_fn(user, "master", "create_kpi", f"{body.subject}/{body.kpi_id}", [])
        return {"ok": True}

    @api.put("/master/kpis")
    async def update_kpi(body: KpiIn, original_kpi_id: str = Query(...),
                         user: dict = Depends(require_role("Admin"))):
        existing = await db.kpis.find_one({"subject": body.subject, "kpi_id": original_kpi_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        await db.kpis.update_one({"subject": body.subject, "kpi_id": original_kpi_id}, {"$set": body.model_dump()})
        await audit_fn(user, "master", "update_kpi", f"{body.subject}/{body.kpi_id}", [])
        return {"ok": True}

    @api.delete("/master/kpis")
    async def delete_kpi(subject: str = Query(...), kpi_id: str = Query(...),
                          user: dict = Depends(require_role("Admin"))):
        if await db.outcome_entries.find_one({"subject": subject, "kpi_id": kpi_id}):
            raise HTTPException(status_code=400, detail="Cannot delete: outcome entries exist for this KPI")
        await db.kpis.delete_one({"subject": subject, "kpi_id": kpi_id})
        await audit_fn(user, "master", "delete_kpi", f"{subject}/{kpi_id}", [])
        return {"ok": True}

    # Reporting Periods
    class ReportingPeriodIn(BaseModel):
        period: str  # YYYY-MM
        label: str
        is_baseline: bool = False

    @api.get("/master/periods")
    async def list_periods(_: dict = Depends(require_fully_authenticated)):
        return await db.reporting_periods.find({}, {"_id": 0}).sort("period", 1).to_list(100)

    @api.post("/master/periods")
    async def create_period(body: ReportingPeriodIn, user: dict = Depends(require_role("Admin"))):
        if await db.reporting_periods.find_one({"period": body.period}):
            raise HTTPException(status_code=400, detail="Period already exists")
        await db.reporting_periods.insert_one(body.model_dump())
        await audit_fn(user, "master", "create_period", body.period, [])
        return {"ok": True}

    @api.put("/master/periods/{period}")
    async def update_period(period: str, body: ReportingPeriodIn, user: dict = Depends(require_role("Admin"))):
        if not await db.reporting_periods.find_one({"period": period}):
            raise HTTPException(status_code=404, detail="Not found")
        await db.reporting_periods.update_one({"period": period}, {"$set": body.model_dump()})
        await audit_fn(user, "master", "update_period", period, [])
        return {"ok": True}

    @api.delete("/master/periods/{period}")
    async def delete_period(period: str, user: dict = Depends(require_role("Admin"))):
        if await db.physical_entries.find_one({"reporting_period": period}):
            raise HTTPException(status_code=400, detail="Cannot delete: physical entries exist for this period")
        if await db.financial_entries.find_one({"reporting_period": period}):
            raise HTTPException(status_code=400, detail="Cannot delete: financial entries exist for this period")
        if await db.outcome_entries.find_one({"reporting_period": period}):
            raise HTTPException(status_code=400, detail="Cannot delete: outcome entries exist for this period")
        await db.reporting_periods.delete_one({"period": period})
        await audit_fn(user, "master", "delete_period", period, [])
        return {"ok": True}

    # Districts (NEW)
    class DistrictIn(BaseModel):
        high_court: str
        name: str
        active: bool = True

    @api.get("/master/districts")
    async def list_districts(
        high_court: Optional[str] = None,
        include_inactive: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        q: dict = {}
        if not include_inactive or user.get("role") != "Admin":
            q["active"] = True
        if high_court:
            q["high_court"] = high_court
        return await db.districts.find(q, {"_id": 0}).sort([("high_court", 1), ("name", 1)]).to_list(1000)

    @api.post("/master/districts")
    async def create_district(body: DistrictIn, user: dict = Depends(require_role("Admin"))):
        if await db.districts.find_one({"high_court": body.high_court, "name": body.name}):
            raise HTTPException(status_code=400, detail="District already exists for this HC")
        await db.districts.insert_one(body.model_dump())
        await audit_fn(user, "master", "create_district", f"{body.high_court}/{body.name}", [])
        return {"ok": True}

    @api.put("/master/districts")
    async def update_district(
        body: DistrictIn,
        high_court: str = Query(...),
        name: str = Query(...),
        user: dict = Depends(require_role("Admin")),
    ):
        existing = await db.districts.find_one({"high_court": high_court, "name": name})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        if (body.high_court != high_court or body.name != name):
            if await db.districts.find_one({"high_court": body.high_court, "name": body.name}):
                raise HTTPException(status_code=400, detail="Target district already exists")
            await db.districts.update_one(
                {"high_court": high_court, "name": name},
                {"$set": body.model_dump()},
            )
        else:
            await db.districts.update_one(
                {"high_court": high_court, "name": name},
                {"$set": {"active": body.active}},
            )
        await audit_fn(user, "master", "update_district", f"{high_court}/{name}", [])
        return {"ok": True}

    @api.delete("/master/districts")
    async def delete_district(high_court: str = Query(...), name: str = Query(...),
                               user: dict = Depends(require_role("Admin"))):
        await db.districts.delete_one({"high_court": high_court, "name": name})
        await audit_fn(user, "master", "delete_district", f"{high_court}/{name}", [])
        return {"ok": True}

    # RAG thresholds (unchanged)
    @api.get("/master/rag-thresholds")
    async def get_rag_thresholds(_: dict = Depends(require_fully_authenticated)):
        doc = await db.settings.find_one({"key": "rag_thresholds"})
        return doc.get("value") if doc else default_rag_thresholds

    @api.put("/master/rag-thresholds")
    async def set_rag_thresholds(body: dict, user: dict = Depends(require_role("Admin"))):
        old = await db.settings.find_one({"key": "rag_thresholds"})
        await db.settings.update_one({"key": "rag_thresholds"}, {"$set": {"value": body}}, upsert=True)
        await audit_fn(user, "master", "update", "rag_thresholds",
                    [{"field": "thresholds", "old": old.get("value") if old else None, "new": body}])
        return {"ok": True}
