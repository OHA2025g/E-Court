"""PMU task and DPR deliverable routes."""
from typing import List, Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class PmuTaskIn(BaseModel):
    title: str
    description: Optional[str] = None
    owner: Optional[str] = None
    stakeholder: Optional[str] = None
    priority: Literal["Critical", "High", "Medium", "Low"] = "Medium"
    status: Literal["Open", "In Progress", "Completed", "Overdue"] = "Open"
    due_date: Optional[str] = None
    comments: Optional[str] = None
    attachments: Optional[List[str]] = None


class DprDeliverableIn(BaseModel):
    code: str
    title: str
    owner: Optional[str] = None
    target_date: Optional[str] = None
    actual_date: Optional[str] = None
    status: Literal["Not Started", "In Progress", "Completed", "Delayed"] = "Not Started"
    delay_reason: Optional[str] = None
    remarks: Optional[str] = None
    attachments: Optional[List[str]] = None


def register_pmu_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    require_role,
    audit_fn,
    serialize_fn,
    now_utc_fn,
):
    @api.get("/pmu-tasks")
    async def list_tasks(_: dict = Depends(require_fully_authenticated)):
        items = await db.pmu_tasks.find().sort("due_date", 1).to_list(500)
        return serialize_fn(items)

    @api.post("/pmu-tasks")
    async def create_task(body: PmuTaskIn, user: dict = Depends(require_role("Admin"))):
        doc = body.model_dump()
        doc.update({"created_by": user["email"], "created_at": now_utc_fn(), "updated_at": now_utc_fn()})
        result = await db.pmu_tasks.insert_one(doc)
        await audit_fn(user, "pmu_tasks", "create", str(result.inserted_id),
                       [{"field": "task", "old": None, "new": serialize_fn(doc)}])
        return {"id": str(result.inserted_id)}

    @api.put("/pmu-tasks/{tid}")
    async def update_task(tid: str, body: PmuTaskIn, user: dict = Depends(require_role("Admin"))):
        existing = await db.pmu_tasks.find_one({"_id": ObjectId(tid)})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        upd = body.model_dump()
        upd["updated_at"] = now_utc_fn()
        changes = [{"field": k, "old": existing.get(k), "new": upd.get(k)}
                   for k in upd if existing.get(k) != upd.get(k)]
        await db.pmu_tasks.update_one({"_id": ObjectId(tid)}, {"$set": upd})
        await audit_fn(user, "pmu_tasks", "update", tid, changes)
        return {"ok": True}

    @api.delete("/pmu-tasks/{tid}")
    async def delete_task(tid: str, user: dict = Depends(require_role("Admin"))):
        await db.pmu_tasks.delete_one({"_id": ObjectId(tid)})
        await audit_fn(user, "pmu_tasks", "delete", tid, [])
        return {"ok": True}

    @api.get("/dpr")
    async def list_dpr(_: dict = Depends(require_fully_authenticated)):
        items = await db.dpr_deliverables.find().sort("code", 1).to_list(500)
        return serialize_fn(items)

    @api.post("/dpr")
    async def create_dpr(body: DprDeliverableIn, user: dict = Depends(require_role("Admin"))):
        doc = body.model_dump()
        doc.update({"created_by": user["email"], "created_at": now_utc_fn()})
        if await db.dpr_deliverables.find_one({"code": body.code}):
            raise HTTPException(status_code=400, detail="Code already exists")
        result = await db.dpr_deliverables.insert_one(doc)
        await audit_fn(user, "dpr", "create", str(result.inserted_id),
                       [{"field": "deliverable", "old": None, "new": serialize_fn(doc)}])
        return {"id": str(result.inserted_id)}

    @api.put("/dpr/{did}")
    async def update_dpr(did: str, body: DprDeliverableIn, user: dict = Depends(require_role("Admin"))):
        existing = await db.dpr_deliverables.find_one({"_id": ObjectId(did)})
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        upd = body.model_dump()
        changes = [{"field": k, "old": existing.get(k), "new": upd.get(k)}
                   for k in upd if existing.get(k) != upd.get(k)]
        await db.dpr_deliverables.update_one({"_id": ObjectId(did)}, {"$set": upd})
        await audit_fn(user, "dpr", "update", did, changes)
        return {"ok": True}

    @api.delete("/dpr/{did}")
    async def delete_dpr(did: str, user: dict = Depends(require_role("Admin"))):
        await db.dpr_deliverables.delete_one({"_id": ObjectId(did)})
        await audit_fn(user, "dpr", "delete", did, [])
        return {"ok": True}
