"""API token auth for external read-only access."""
import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel


class ApiTokenIn(BaseModel):
    name: str
    scopes: list[str] = ["public", "dashboard:read"]


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def register_api_token_routes(api, db, require_role, serialize_fn, now_utc_fn):
    @api.get("/admin/api-tokens")
    async def list_tokens(_: dict = Depends(require_role("Admin"))):
        items = await db.api_tokens.find({}, {"token_hash": 0}).to_list(50)
        return serialize_fn(items)

    @api.post("/admin/api-tokens")
    async def create_token(body: ApiTokenIn, user: dict = Depends(require_role("Admin"))):
        raw = secrets.token_urlsafe(32)
        doc = {
            "name": body.name,
            "scopes": body.scopes,
            "token_hash": _hash_token(raw),
            "created_by": user["email"],
            "created_at": now_utc_fn(),
            "active": True,
        }
        r = await db.api_tokens.insert_one(doc)
        return {"id": str(r.inserted_id), "token": raw, "note": "Store this token securely — shown once"}

    @api.delete("/admin/api-tokens/{tid}")
    async def revoke_token(tid: str, _: dict = Depends(require_role("Admin"))):
        from bson import ObjectId
        await db.api_tokens.update_one({"_id": ObjectId(tid)}, {"$set": {"active": False}})
        return {"ok": True}


async def resolve_api_token(db, request: Request) -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    raw = auth[7:].strip()
    if not raw or raw.count(".") >= 2:
        return None
    doc = await db.api_tokens.find_one({"token_hash": _hash_token(raw), "active": True})
    return doc
