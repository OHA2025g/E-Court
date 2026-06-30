"""Audit log API routes."""
from typing import Optional

from fastapi import APIRouter, Depends


def register_audit_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    serialize_fn,
):
    @api.get("/audit")
    async def list_audit(
        tracker: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 200,
        user: dict = Depends(require_fully_authenticated),
    ):
        q: dict = {}
        if user["role"] != "Admin":
            q["user_email"] = user["email"]
        if tracker:
            q["tracker"] = tracker
        if action:
            q["action"] = action
        items = await db.audit_logs.find(q).sort("timestamp", -1).limit(limit).to_list(limit)
        return serialize_fn(items)
