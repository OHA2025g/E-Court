"""Scope Charter viewing and formal electronic sign-off."""
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

CHARTER_PATH = Path(__file__).resolve().parent / "scope_charter.md"
CHARTER_VERSION = "2026-02"

SIGNOFF_SLOTS = [
    {
        "id": "doj_nodal",
        "title": "DoJ Nodal Officer",
        "allowed_roles": ["Admin"],
    },
    {
        "id": "pmu_director",
        "title": "PMU Director",
        "allowed_roles": ["Admin"],
    },
    {
        "id": "ecommittee_secretariat",
        "title": "e-Committee Secretariat Rep.",
        "allowed_roles": ["Admin", "Viewer"],
    },
    {
        "id": "hc_cpc_representative",
        "title": "HC CPC Coordinators (rep.)",
        "allowed_roles": ["Admin", "CPC"],
    },
]

ACTION_ITEMS = [
    {"id": "A-001", "status": "resolved", "label": "17 vs 24 components routing"},
    {"id": "A-002", "status": "resolved", "label": "Globally unique KPI IDs"},
    {"id": "A-003", "status": "resolved", "label": "2FA for Admin accounts"},
    {"id": "A-004", "status": "pending_external", "label": "iJuris API access timeline"},
    {"id": "A-005", "status": "pending_signoff", "label": "RAG thresholds final sign-off"},
]


class ScopeCharterSignIn(BaseModel):
    slot_id: str
    signer_name: str = Field(min_length=2, max_length=120)
    affirm: bool


def _load_charter_markdown() -> str:
    if not CHARTER_PATH.is_file():
        return "# Scope Charter\n\nCharter document not found on server."
    return CHARTER_PATH.read_text(encoding="utf-8")


def _slot_by_id(slot_id: str) -> dict:
    for slot in SIGNOFF_SLOTS:
        if slot["id"] == slot_id:
            return slot
    raise HTTPException(status_code=404, detail="Unknown sign-off slot")


async def ensure_scope_charter_indexes(database):
    await database.scope_charter_signoffs.create_index("slot_id", unique=True)


def register_scope_charter_routes(api, db, require_fully_authenticated, audit_fn, serialize_fn, now_utc_fn):
    @api.get("/scope-charter")
    async def get_scope_charter(user: dict = Depends(require_fully_authenticated)):
        signoffs = await db.scope_charter_signoffs.find().sort("signed_at", 1).to_list(20)
        signed_ids = {s["slot_id"] for s in signoffs}
        slots = []
        for slot in SIGNOFF_SLOTS:
            existing = next((s for s in signoffs if s["slot_id"] == slot["id"]), None)
            slots.append({
                **slot,
                "signed": existing is not None,
                "can_sign": (
                    slot["id"] not in signed_ids
                    and user.get("role") in slot["allowed_roles"]
                ),
                "signoff": serialize_fn(existing) if existing else None,
            })
        fully_signed = len(signed_ids) >= len(SIGNOFF_SLOTS)
        status_doc = await db.settings.find_one({"key": "scope_charter_status"})
        status_value = status_doc.get("value") if status_doc else {}
        return {
            "version": CHARTER_VERSION,
            "document_status": "SIGNED" if fully_signed else "DRAFT",
            "fully_signed": fully_signed,
            "completed_at": status_value.get("completed_at"),
            "markdown": _load_charter_markdown(),
            "action_items": ACTION_ITEMS,
            "signoff_slots": slots,
            "signed_count": len(signed_ids),
            "required_count": len(SIGNOFF_SLOTS),
        }

    @api.post("/scope-charter/sign")
    async def sign_scope_charter(body: ScopeCharterSignIn, user: dict = Depends(require_fully_authenticated)):
        if not body.affirm:
            raise HTTPException(status_code=400, detail="You must affirm authority to sign this charter")
        slot = _slot_by_id(body.slot_id)
        if user.get("role") not in slot["allowed_roles"]:
            raise HTTPException(status_code=403, detail="Your role cannot sign for this slot")
        existing = await db.scope_charter_signoffs.find_one({"slot_id": body.slot_id})
        if existing:
            raise HTTPException(status_code=409, detail="This sign-off slot is already completed")

        doc = {
            "slot_id": body.slot_id,
            "slot_title": slot["title"],
            "signer_name": body.signer_name.strip(),
            "signed_by_user_id": user["id"],
            "signed_by_email": user.get("email"),
            "signed_by_role": user.get("role"),
            "signed_at": now_utc_fn(),
        }
        await db.scope_charter_signoffs.insert_one(doc)

        count = await db.scope_charter_signoffs.count_documents({})
        fully_signed = count >= len(SIGNOFF_SLOTS)
        status_value = {"fully_signed": fully_signed, "signed_count": count}
        if fully_signed:
            status_value["completed_at"] = now_utc_fn().isoformat()
        await db.settings.update_one(
            {"key": "scope_charter_status"},
            {"$set": {"value": status_value}},
            upsert=True,
        )

        await audit_fn(
            user,
            "scope_charter",
            "sign",
            body.slot_id,
            [{
                "field": "signer_name",
                "old": None,
                "new": doc["signer_name"],
            }],
        )
        return {"ok": True, "fully_signed": fully_signed, "signoff": serialize_fn(doc)}
