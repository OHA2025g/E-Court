"""Saved report view bookmarks per user."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class ReportViewIn(BaseModel):
    name: str
    tracker: str
    filters: dict = {}
    sort: Optional[dict] = None
    columns: Optional[list] = None


def register_report_views_routes(api, db, require_fully_authenticated, serialize_fn, now_utc_fn):
    @api.get("/reports/views")
    async def list_views(user: dict = Depends(require_fully_authenticated)):
        items = await db.saved_report_views.find({"user_id": user["id"]}).sort("name", 1).to_list(50)
        return serialize_fn(items)

    @api.post("/reports/views")
    async def save_view(body: ReportViewIn, user: dict = Depends(require_fully_authenticated)):
        doc = {
            **body.model_dump(),
            "user_id": user["id"],
            "user_email": user["email"],
            "created_at": now_utc_fn(),
            "updated_at": now_utc_fn(),
        }
        r = await db.saved_report_views.insert_one(doc)
        return {"id": str(r.inserted_id)}

    @api.put("/reports/views/{vid}")
    async def update_view(vid: str, body: ReportViewIn, user: dict = Depends(require_fully_authenticated)):
        from bson import ObjectId
        r = await db.saved_report_views.update_one(
            {"_id": ObjectId(vid), "user_id": user["id"]},
            {"$set": {**body.model_dump(), "updated_at": now_utc_fn()}},
        )
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="View not found")
        return {"ok": True}

    @api.delete("/reports/views/{vid}")
    async def delete_view(vid: str, user: dict = Depends(require_fully_authenticated)):
        from bson import ObjectId
        await db.saved_report_views.delete_one({"_id": ObjectId(vid), "user_id": user["id"]})
        return {"ok": True}
