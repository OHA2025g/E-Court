"""Physical, Financial, and Outcome tracker CRUD routes."""
from typing import Callable, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from rollup import (
    apply_district_filter,
    entry_query_key_financial,
    entry_query_key_physical,
    resolve_storage_type,
)
from seed_constants import NSC_COMPONENT, NSC_FINANCIAL_COMPONENTS
from period_policy import assert_editable
from cache_layer import cache_invalidate_prefix
from webhook_routes import enqueue_webhook
from high_court_names import high_court_filter_value, high_court_names_equal

ADMIN_ONLY_CREATE_DETAIL = "Only administrators can create new tracker entries"


def assert_admin_can_create(user: dict, existing: Optional[dict]) -> None:
    if not existing and user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail=ADMIN_ONLY_CREATE_DETAIL)


class PhysicalEntryIn(BaseModel):
    high_court: str
    component: str
    indicator: str
    reporting_period: str
    district: Optional[str] = None
    storage_type: Optional[str] = None
    target: Optional[float] = None
    achieved: Optional[float] = None
    # e-Sewa Kendras only — ignored / cleared for other components
    target_dpr: Optional[float] = None
    achieved_ecommittee: Optional[float] = None
    target_cpc: Optional[float] = None
    achieved_cpc: Optional[float] = None
    remarks: Optional[str] = None


ESEWA_COMPONENT = "e-Sewa Kendras"


class FinancialEntryIn(BaseModel):
    high_court: str
    component: str
    reporting_period: str
    district: Optional[str] = None
    description: Optional[str] = None
    fund_target: Optional[float] = None
    fund_allocated: Optional[float] = None
    fund_released: Optional[float] = None
    fund_utilized: Optional[float] = None
    remarks: Optional[str] = None


class OutcomeEntryIn(BaseModel):
    high_court: Optional[str] = None
    district: Optional[str] = None
    granularity: str
    component: Optional[str] = None
    sub_component: Optional[str] = None
    subject: str
    kpi_id: str
    kpi: Optional[str] = None
    description: Optional[str] = None
    periodicity: Optional[str] = None
    outcome_type: Optional[str] = "Absolute"
    value_type: Optional[str] = None
    baseline: Optional[float] = None
    value: Optional[float] = None
    reporting_period: str
    remarks: Optional[str] = None


def register_tracker_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    scope_filter_fn: Callable,
    audit_fn: Callable,
    notify_fn: Callable,
    admin_emails_fn: Callable,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    serialize_fn: Callable,
    now_utc_fn: Callable,
    default_rag_thresholds: dict,
):
    async def _paginated_list(collection: str, q: dict, sort, page: int = 1, page_size: int = 500):
        page = max(1, page)
        page_size = min(max(1, page_size), 500)
        coll = getattr(db, collection)
        total = await coll.count_documents(q)
        skip = (page - 1) * page_size
        items = await coll.find(q).sort(sort).skip(skip).limit(page_size).to_list(page_size)
        return {
            "items": serialize_fn(items),
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def _invalidate_dashboard_cache():
        cache_invalidate_prefix("public:progress")
        cache_invalidate_prefix("dashboard:")

    async def _webhook_rag(tracker: str, payload: dict):
        await enqueue_webhook(db, "rag_change", {"tracker": tracker, **payload}, now_utc_fn)

    async def _notify_physical_red(body, rag: str, percent, *, is_new: bool):
        title = (
            f"New RED indicator: {body.high_court} / {body.component}"
            if is_new
            else f"RAG flipped RED: {body.high_court} / {body.component}"
        )
        detail = (
            f"Indicator '{body.indicator}' submitted for {body.reporting_period} is RED ({(percent or 0):.1f}%)."
            if is_new
            else f"Indicator '{body.indicator}' for {body.reporting_period} just turned RED ({(percent or 0):.1f}% achieved)."
        )
        await notify_fn(
            await admin_emails_fn(),
            title,
            detail,
            kind="alert",
            link="/physical",
            meta={
                "high_court": body.high_court,
                "component": body.component,
                "indicator": body.indicator,
                "period": body.reporting_period,
            },
            also_email=True,
        )
        await _webhook_rag("physical", {
            "high_court": body.high_court,
            "component": body.component,
            "indicator": body.indicator,
            "reporting_period": body.reporting_period,
            "rag": rag,
            "percent": percent,
        })

    async def _notify_financial_red(body, rag: str, utilisation, *, is_new: bool):
        cpc_docs = await db.users.find(
            {"role": "CPC", "high_court": body.high_court}, {"email": 1},
        ).to_list(10)
        title = (
            f"New financial RED: {body.high_court} / {body.component}"
            if is_new
            else f"Financial RAG RED: {body.high_court} / {body.component}"
        )
        detail = (
            f"Utilisation for {body.reporting_period} is RED ({utilisation or 0:.1f}%)."
        )
        await notify_fn(
            (await admin_emails_fn()) + [u["email"] for u in cpc_docs],
            title,
            detail,
            kind="alert",
            link="/financial",
            also_email=True,
        )
        await _webhook_rag("financial", {
            "high_court": body.high_court,
            "component": body.component,
            "reporting_period": body.reporting_period,
            "rag": rag,
            "utilisation_percent": utilisation,
        })

    async def _notify_outcome_threshold(body, computed: float, entry_id, *, is_new: bool):
        title = (
            f"New outcome below threshold: {body.subject}"
            if is_new
            else f"Outcome below threshold: {body.subject}"
        )
        detail = f"KPI {body.kpi_id} for {body.reporting_period} computed {computed:.1f}%."
        await notify_fn(
            await admin_emails_fn(),
            title,
            detail,
            kind="alert",
            link="/outcome",
            also_email=True,
        )
        await _webhook_rag("outcome", {
            "high_court": body.high_court,
            "subject": body.subject,
            "kpi_id": body.kpi_id,
            "reporting_period": body.reporting_period,
            "computed_percent": computed,
            "threshold": 65,
        })
        await db.outcome_entries.update_one(
            {"_id": entry_id},
            {"$set": {"_last_red_notified": body.reporting_period}},
        )

    @api.get("/physical")
    async def list_physical(
        high_court: Optional[str] = None, component: Optional[str] = None,
        reporting_period: Optional[str] = None, district: Optional[str] = None,
        storage_type: Optional[str] = None,
        page: int = 1, page_size: int = 500,
        user: dict = Depends(require_fully_authenticated),
    ):
        q: dict = scope_filter_fn(user)
        if high_court:
            q["high_court"] = high_court_filter_value(high_court)
        if component:
            q["component"] = component
        if reporting_period:
            q["reporting_period"] = reporting_period
        if storage_type:
            q["storage_type"] = storage_type
        apply_district_filter(q, district)
        return await _paginated_list(
            "physical_entries", q,
            [("high_court", 1), ("component", 1), ("storage_type", 1), ("indicator", 1)],
            page, page_size,
        )

    @api.post("/physical")
    async def upsert_physical(body: PhysicalEntryIn, user: dict = Depends(require_fully_authenticated)):
        if user["role"] == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only")
        if user["role"] == "CPC" and not high_court_names_equal(body.high_court, user.get("high_court")):
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")
        today = now_utc_fn().strftime("%Y-%m")
        if body.reporting_period > today:
            raise HTTPException(status_code=400, detail="Reporting month cannot be in the future")
        await assert_editable(db, body.high_court, body.reporting_period, user, now_utc_fn)
        if body.achieved is not None and body.achieved < 0:
            raise HTTPException(status_code=400, detail="Achieved cannot be negative")
        for fld, label in (
            (body.achieved_ecommittee, "Achieved as per e-Committee"),
            (body.achieved_cpc, "Achieved as per CPC"),
            (body.target_dpr, "Target as per DPR"),
            (body.target_cpc, "Target as per CPC"),
        ):
            if fld is not None and fld < 0:
                raise HTTPException(status_code=400, detail=f"{label} cannot be negative")
        try:
            storage_type = resolve_storage_type(body.component, body.storage_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        payload = {**body.model_dump(), "storage_type": storage_type}

        q = entry_query_key_physical(payload)
        existing = await db.physical_entries.find_one(q)
        assert_admin_can_create(user, existing)

        is_esewa = body.component == ESEWA_COMPONENT
        target_dpr = body.target_dpr if is_esewa else None
        achieved_ecommittee = body.achieved_ecommittee if is_esewa else None
        target_cpc = body.target_cpc if is_esewa else None
        achieved_cpc = body.achieved_cpc if is_esewa else None
        # Legacy iJuris / init payloads often omit DPR/CPC fields — do not wipe filled rows
        if is_esewa and existing and all(
            v is None for v in (target_dpr, achieved_ecommittee, target_cpc, achieved_cpc)
        ):
            target_dpr = existing.get("target_dpr")
            achieved_ecommittee = existing.get("achieved_ecommittee")
            target_cpc = existing.get("target_cpc")
            achieved_cpc = existing.get("achieved_cpc")
        percent_ecommittee = safe_div_fn(achieved_ecommittee, target_dpr) if is_esewa else None
        percent_cpc = safe_div_fn(achieved_cpc, target_cpc) if is_esewa else None
        # e-Sewa uses DPR/e-Committee/CPC fields only — no cumulative Target/Achieved
        target_val = None if is_esewa else body.target
        achieved_val = None if is_esewa else body.achieved
        percent = percent_ecommittee if is_esewa else safe_div_fn(achieved_val, target_val)
        thresholds = (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get(
            "value", default_rag_thresholds
        )
        rag = compute_rag_fn(percent, thresholds)

        doc = {
            **q, "district": body.district, "storage_type": storage_type,
            "target": target_val, "achieved": achieved_val,
            "percent": percent, "rag": rag, "remarks": body.remarks,
            "target_dpr": target_dpr,
            "achieved_ecommittee": achieved_ecommittee,
            "target_cpc": target_cpc,
            "achieved_cpc": achieved_cpc,
            "percent_ecommittee": percent_ecommittee,
            "percent_cpc": percent_cpc,
            "updated_by": user["email"], "updated_at": now_utc_fn(),
        }

        if existing:
            if user["role"] == "CPC":
                doc["target"] = existing.get("target")
                doc["target_dpr"] = existing.get("target_dpr")
            changes = [
                {"field": k, "old": existing.get(k), "new": doc.get(k)}
                for k in [
                    "target", "achieved", "remarks", "storage_type",
                    "target_dpr", "achieved_ecommittee", "target_cpc", "achieved_cpc",
                ]
                if existing.get(k) != doc.get(k)
            ]
            await db.physical_entries.update_one({"_id": existing["_id"]}, {"$set": doc})
            await _invalidate_dashboard_cache()
            await audit_fn(user, "physical", "update", str(existing["_id"]), changes,
                           body.high_court, body.reporting_period)
            if existing.get("rag") != "RED" and rag == "RED":
                await _notify_physical_red(body, rag, percent, is_new=False)
            return {"id": str(existing["_id"])}
        doc["created_by"] = user["email"]
        doc["created_at"] = now_utc_fn()
        result = await db.physical_entries.insert_one(doc)
        await _invalidate_dashboard_cache()
        await audit_fn(user, "physical", "create", str(result.inserted_id),
                       [{"field": "entry", "old": None, "new": serialize_fn(doc)}],
                       body.high_court, body.reporting_period)
        if rag == "RED":
            await _notify_physical_red(body, rag, percent, is_new=True)
        return {"id": str(result.inserted_id)}

    @api.delete("/physical/{entry_id}")
    async def delete_physical(entry_id: str, user: dict = Depends(require_fully_authenticated)):
        if user["role"] != "Admin":
            raise HTTPException(status_code=403, detail="Admin only")
        try:
            oid = ObjectId(entry_id)
        except (InvalidId, TypeError):
            raise HTTPException(status_code=400, detail="Invalid entry id")
        existing = await db.physical_entries.find_one({"_id": oid})
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found")
        await db.physical_entries.delete_one({"_id": oid})
        await _invalidate_dashboard_cache()
        await audit_fn(
            user, "physical", "delete", entry_id,
            [{"field": "entry", "old": serialize_fn(existing), "new": None}],
            existing.get("high_court"), existing.get("reporting_period"),
        )
        return {"id": entry_id, "deleted": True}

    @api.post("/physical/cleanup-empty-esewa")
    async def cleanup_empty_esewa(user: dict = Depends(require_fully_authenticated)):
        """Remove e-Sewa Kendras rows with no DPR/e-Committee/CPC (or legacy) values."""
        if user["role"] != "Admin":
            raise HTTPException(status_code=403, detail="Admin only")
        q = {
            "component": ESEWA_COMPONENT,
            "$and": [
                {"$or": [{"target_dpr": None}, {"target_dpr": {"$exists": False}}]},
                {"$or": [{"achieved_ecommittee": None}, {"achieved_ecommittee": {"$exists": False}}]},
                {"$or": [{"target_cpc": None}, {"target_cpc": {"$exists": False}}]},
                {"$or": [{"achieved_cpc": None}, {"achieved_cpc": {"$exists": False}}]},
                {"$or": [{"target": None}, {"target": {"$exists": False}}]},
                {"$or": [{"achieved": None}, {"achieved": {"$exists": False}}]},
            ],
        }
        empties = await db.physical_entries.find(q).to_list(2000)
        deleted = 0
        for doc in empties:
            await db.physical_entries.delete_one({"_id": doc["_id"]})
            await audit_fn(
                user, "physical", "delete", str(doc["_id"]),
                [{"field": "entry", "old": serialize_fn(doc), "new": None}],
                doc.get("high_court"), doc.get("reporting_period"),
            )
            deleted += 1
        if deleted:
            await _invalidate_dashboard_cache()
        return {"deleted": deleted, "component": ESEWA_COMPONENT}

    @api.get("/financial")
    async def list_financial(
        high_court: Optional[str] = None, component: Optional[str] = None,
        reporting_period: Optional[str] = None, district: Optional[str] = None,
        page: int = 1, page_size: int = 500,
        user: dict = Depends(require_fully_authenticated),
    ):
        q: dict = scope_filter_fn(user)
        if high_court:
            q["high_court"] = high_court_filter_value(high_court)
        if component:
            if component == NSC_COMPONENT:
                q["component"] = {"$in": [NSC_COMPONENT, *NSC_FINANCIAL_COMPONENTS]}
            else:
                q["component"] = component
        if reporting_period:
            q["reporting_period"] = reporting_period
        apply_district_filter(q, district)
        return await _paginated_list(
            "financial_entries", q, [("high_court", 1), ("component", 1)], page, page_size,
        )

    @api.post("/financial")
    async def upsert_financial(body: FinancialEntryIn, user: dict = Depends(require_fully_authenticated)):
        if user["role"] == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only")
        if user["role"] == "CPC" and not high_court_names_equal(body.high_court, user.get("high_court")):
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")
        today = now_utc_fn().strftime("%Y-%m")
        if body.reporting_period > today:
            raise HTTPException(status_code=400, detail="Reporting month cannot be in the future")
        await assert_editable(db, body.high_court, body.reporting_period, user, now_utc_fn)
        for f in [body.fund_released, body.fund_utilized, body.fund_target, body.fund_allocated]:
            if f is not None and f < 0:
                raise HTTPException(status_code=400, detail="Funds cannot be negative")

        warning = None
        if body.fund_released is not None and body.fund_utilized is not None and body.fund_utilized > body.fund_released:
            warning = "Funds utilised exceed funds released"

        # Absolute ₹ inputs (≥1000) are stored as exact *_rupees and converted to crore
        # without intermediate 4dp truncation so national KPIs can sum actuals first.
        rupee_floor = 1000.0
        released_rupees = allocated_rupees = target_rupees = utilized_rupees = None
        fund_released = body.fund_released
        fund_utilized = body.fund_utilized
        fund_target = body.fund_target
        fund_allocated = body.fund_allocated
        if fund_released is not None and abs(float(fund_released)) >= rupee_floor:
            released_rupees = float(fund_released)
            fund_released = released_rupees / 1e7
        if fund_utilized is not None and abs(float(fund_utilized)) >= rupee_floor:
            utilized_rupees = float(fund_utilized)
            fund_utilized = utilized_rupees / 1e7
        if fund_target is not None and abs(float(fund_target)) >= rupee_floor:
            target_rupees = float(fund_target)
            fund_target = target_rupees / 1e7
        if fund_allocated is not None and abs(float(fund_allocated)) >= rupee_floor:
            allocated_rupees = float(fund_allocated)
            fund_allocated = allocated_rupees / 1e7

        utilisation = safe_div_fn(fund_utilized, fund_released)
        variance = None
        if fund_released is not None and fund_utilized is not None:
            variance = float(fund_released) - float(fund_utilized)
        thresholds = (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get(
            "value", default_rag_thresholds
        )
        rag = compute_rag_fn(utilisation, thresholds)

        q = entry_query_key_financial(body.model_dump())
        existing = await db.financial_entries.find_one(q)
        assert_admin_can_create(user, existing)
        if user["role"] == "CPC" and existing:
            fund_target = existing.get("fund_target")
            fund_allocated = existing.get("fund_allocated")
            fund_released = existing.get("fund_released")
            target_rupees = existing.get("fund_target_rupees")
            allocated_rupees = existing.get("fund_allocated_rupees")
            released_rupees = existing.get("fund_released_rupees")
            body.fund_target = fund_target
            body.fund_allocated = fund_allocated
            body.fund_released = fund_released
        description = body.description
        if description is None and existing:
            description = existing.get("description")
        if description is None:
            comp = await db.components.find_one({"name": body.component}, {"description": 1})
            description = comp.get("description") if comp else None
        doc = {
            **q, "district": body.district,
            "description": description, "fund_target": fund_target,
            "fund_allocated": fund_allocated, "fund_released": fund_released,
            "fund_utilized": fund_utilized, "utilisation_percent": utilisation,
            "variance": variance, "rag": rag, "remarks": body.remarks,
            "updated_by": user["email"], "updated_at": now_utc_fn(),
        }
        if released_rupees is not None:
            doc["fund_released_rupees"] = released_rupees
        if utilized_rupees is not None:
            doc["fund_utilized_rupees"] = utilized_rupees
        if target_rupees is not None:
            doc["fund_target_rupees"] = target_rupees
        if allocated_rupees is not None:
            doc["fund_allocated_rupees"] = allocated_rupees
        if existing:
            change_fields = ["fund_utilized", "remarks"] if user["role"] == "CPC" else [
                "fund_released", "fund_utilized", "remarks",
            ]
            changes = [
                {"field": k, "old": existing.get(k), "new": doc.get(k)}
                for k in change_fields if existing.get(k) != doc.get(k)
            ]
            await db.financial_entries.update_one({"_id": existing["_id"]}, {"$set": doc})
            await _invalidate_dashboard_cache()
            await audit_fn(user, "financial", "update", str(existing["_id"]), changes,
                           body.high_court, body.reporting_period)
            if existing.get("rag") != "RED" and rag == "RED":
                await _notify_financial_red(body, rag, utilisation, is_new=False)
            return {"id": str(existing["_id"]), "warning": warning}
        doc["created_by"] = user["email"]
        doc["created_at"] = now_utc_fn()
        result = await db.financial_entries.insert_one(doc)
        await _invalidate_dashboard_cache()
        await audit_fn(user, "financial", "create", str(result.inserted_id),
                       [{"field": "entry", "old": None, "new": serialize_fn(doc)}],
                       body.high_court, body.reporting_period)
        if rag == "RED":
            await _notify_financial_red(body, rag, utilisation, is_new=True)
        return {"id": str(result.inserted_id), "warning": warning}

    @api.delete("/financial/{entry_id}")
    async def delete_financial(entry_id: str, user: dict = Depends(require_fully_authenticated)):
        if user["role"] != "Admin":
            raise HTTPException(status_code=403, detail="Admin only")
        try:
            oid = ObjectId(entry_id)
        except (InvalidId, TypeError):
            raise HTTPException(status_code=400, detail="Invalid entry id")
        existing = await db.financial_entries.find_one({"_id": oid})
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found")
        await db.financial_entries.delete_one({"_id": oid})
        await _invalidate_dashboard_cache()
        await audit_fn(
            user, "financial", "delete", entry_id,
            [{"field": "entry", "old": serialize_fn(existing), "new": None}],
            existing.get("high_court"), existing.get("reporting_period"),
        )
        return {"id": entry_id, "deleted": True}

    @api.post("/financial/cleanup-empty")
    async def cleanup_empty_financial(user: dict = Depends(require_fully_authenticated)):
        """Remove financial rows with no target/allocated/released/utilised values."""
        if user["role"] != "Admin":
            raise HTTPException(status_code=403, detail="Admin only")
        q = {
            "$and": [
                {"$or": [{"fund_target": None}, {"fund_target": {"$exists": False}}]},
                {"$or": [{"fund_allocated": None}, {"fund_allocated": {"$exists": False}}]},
                {"$or": [{"fund_released": None}, {"fund_released": {"$exists": False}}]},
                {"$or": [{"fund_utilized": None}, {"fund_utilized": {"$exists": False}}]},
            ],
        }
        empties = await db.financial_entries.find(q).to_list(5000)
        deleted = 0
        for doc in empties:
            await db.financial_entries.delete_one({"_id": doc["_id"]})
            await audit_fn(
                user, "financial", "delete", str(doc["_id"]),
                [{"field": "entry", "old": serialize_fn(doc), "new": None}],
                doc.get("high_court"), doc.get("reporting_period"),
            )
            deleted += 1
        if deleted:
            await _invalidate_dashboard_cache()
        return {"deleted": deleted}

    @api.get("/outcome")
    async def list_outcome(
        high_court: Optional[str] = None, subject: Optional[str] = None,
        reporting_period: Optional[str] = None,
        page: int = 1, page_size: int = 500,
        user: dict = Depends(require_fully_authenticated),
    ):
        q: dict = scope_filter_fn(user)
        if high_court:
            q["high_court"] = high_court_filter_value(high_court)
        if subject:
            q["subject"] = subject
        if reporting_period:
            q["reporting_period"] = reporting_period
        return await _paginated_list(
            "outcome_entries", q, [("high_court", 1), ("subject", 1), ("kpi_id", 1)], page, page_size,
        )

    @api.post("/outcome")
    async def upsert_outcome(body: OutcomeEntryIn, user: dict = Depends(require_fully_authenticated)):
        if user["role"] == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only")
        if user["role"] == "CPC" and body.high_court and not high_court_names_equal(body.high_court, user.get("high_court")):
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")
        today = now_utc_fn().strftime("%Y-%m")
        if body.reporting_period > today:
            raise HTTPException(status_code=400, detail="Reporting month cannot be in the future")
        if body.high_court:
            await assert_editable(db, body.high_court, body.reporting_period, user, now_utc_fn)
        if body.granularity == "District" and not body.high_court:
            raise HTTPException(status_code=400, detail="High Court required for District-level outcome KPIs")
        if body.granularity == "District" and not body.district:
            raise HTTPException(status_code=400, detail="District required for District-level outcome KPIs")
        computed = None
        if body.outcome_type == "Relative" and body.baseline and body.value is not None:
            computed = safe_div_fn(body.value, body.baseline)
        district = body.district if body.granularity == "District" else None
        q = {
            "high_court": body.high_court, "subject": body.subject,
            "kpi_id": body.kpi_id, "reporting_period": body.reporting_period,
            "granularity": body.granularity, "district": district,
        }
        existing = await db.outcome_entries.find_one(q)
        assert_admin_can_create(user, existing)
        doc = {
            **q,
            "component": body.component,
            "sub_component": body.sub_component,
            "kpi": body.kpi,
            "description": body.description,
            "periodicity": body.periodicity,
            "outcome_type": body.outcome_type,
            "value_type": body.value_type,
            "baseline": body.baseline,
            "value": body.value,
            "computed_percent": computed,
            "remarks": body.remarks,
            "updated_by": user["email"],
            "updated_at": now_utc_fn(),
        }
        if existing:
            changes = [
                {"field": k, "old": existing.get(k), "new": doc.get(k)}
                for k in ["value", "baseline", "remarks"] if existing.get(k) != doc.get(k)
            ]
            await db.outcome_entries.update_one({"_id": existing["_id"]}, {"$set": doc})
            await _invalidate_dashboard_cache()
            await audit_fn(user, "outcome", "update", str(existing["_id"]), changes,
                           body.high_court, body.reporting_period)
            if body.outcome_type == "Relative" and computed is not None and computed < 65:
                if existing.get("_last_red_notified") != body.reporting_period:
                    await _notify_outcome_threshold(body, computed, existing["_id"], is_new=False)
            return {"id": str(existing["_id"])}
        doc["created_by"] = user["email"]
        doc["created_at"] = now_utc_fn()
        result = await db.outcome_entries.insert_one(doc)
        await _invalidate_dashboard_cache()
        await audit_fn(user, "outcome", "create", str(result.inserted_id),
                       [{"field": "entry", "old": None, "new": serialize_fn(doc)}],
                       body.high_court, body.reporting_period)
        if body.outcome_type == "Relative" and computed is not None and computed < 65:
            await _notify_outcome_threshold(body, computed, result.inserted_id, is_new=True)
        return {"id": str(result.inserted_id)}

    return {
        "upsert_physical": upsert_physical,
        "upsert_financial": upsert_financial,
        "upsert_outcome": upsert_outcome,
    }
