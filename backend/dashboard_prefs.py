"""Per-user dashboard layout preferences."""
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

DEFAULT_DASHBOARD_LAYOUT = {
    "version": 1,
    "widgets": [
        {"id": "filters", "visible": True, "x": 0, "y": 0, "w": 12, "h": 2, "static": True},
        {"id": "rag-delta", "visible": True, "x": 0, "y": 2, "w": 12, "h": 3},
        {"id": "kpi-row", "visible": True, "x": 0, "y": 5, "w": 12, "h": 3},
        {"id": "rag-donut", "visible": True, "x": 0, "y": 8, "w": 4, "h": 6},
        {"id": "trend", "visible": True, "x": 4, "y": 8, "w": 8, "h": 6},
        {"id": "choropleth", "visible": True, "x": 0, "y": 14, "w": 12, "h": 8},
        {"id": "heatmap", "visible": True, "x": 0, "y": 22, "w": 12, "h": 8},
        {"id": "pareto", "visible": True, "x": 0, "y": 30, "w": 12, "h": 7},
        {"id": "component-bars", "visible": True, "x": 0, "y": 37, "w": 12, "h": 7},
        {"id": "hc-bars", "visible": True, "x": 0, "y": 44, "w": 12, "h": 8},
        {"id": "tables", "visible": True, "x": 0, "y": 52, "w": 12, "h": 9},
    ],
}


class LayoutIn(BaseModel):
    dashboard_layout: dict


class DashboardPrefsIn(BaseModel):
    onboarding_complete: Optional[bool] = None


def register_dashboard_pref_routes(api: APIRouter, db, require_fully_authenticated, now_utc_fn):
    @api.get("/dashboard/layout")
    async def get_dashboard_layout(user: dict = Depends(require_fully_authenticated)):
        doc = await db.user_preferences.find_one({"user_id": user["id"]})
        if doc and doc.get("dashboard_layout"):
            return {"dashboard_layout": doc["dashboard_layout"]}
        return {"dashboard_layout": DEFAULT_DASHBOARD_LAYOUT}

    @api.put("/dashboard/layout")
    async def put_dashboard_layout(body: LayoutIn, user: dict = Depends(require_fully_authenticated)):
        layout = body.dashboard_layout
        if not layout.get("widgets"):
            raise HTTPException(status_code=400, detail="dashboard_layout.widgets required")
        await db.user_preferences.update_one(
            {"user_id": user["id"]},
            {"$set": {
                "user_id": user["id"],
                "dashboard_layout": layout,
                "updated_at": now_utc_fn(),
            }},
            upsert=True,
        )
        return {"ok": True}

    @api.delete("/dashboard/layout")
    async def reset_dashboard_layout(user: dict = Depends(require_fully_authenticated)):
        await db.user_preferences.delete_one({"user_id": user["id"]})
        return {"ok": True, "dashboard_layout": DEFAULT_DASHBOARD_LAYOUT}

    @api.get("/dashboard/prefs")
    async def get_dashboard_prefs(user: dict = Depends(require_fully_authenticated)):
        doc = await db.user_preferences.find_one({"user_id": user["id"]})
        return {"onboarding_complete": bool(doc.get("onboarding_complete")) if doc else False}

    @api.put("/dashboard/prefs")
    async def put_dashboard_prefs(body: DashboardPrefsIn, user: dict = Depends(require_fully_authenticated)):
        data = body.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="No preferences provided")
        await db.user_preferences.update_one(
            {"user_id": user["id"]},
            {"$set": {**data, "user_id": user["id"], "updated_at": now_utc_fn()}},
            upsert=True,
        )
        return {"ok": True, **data}


async def ensure_dashboard_indexes(database):
    await database.user_preferences.create_index("user_id", unique=True)
