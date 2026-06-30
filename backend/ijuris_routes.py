"""iJuris integration routes."""
import logging
import os
from typing import Callable, Literal

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from tracker_routes import FinancialEntryIn, OutcomeEntryIn, PhysicalEntryIn

logger = logging.getLogger("pmis")


class IjurisIngestIn(BaseModel):
    source: str = "iJuris"
    record_type: Literal["physical", "financial", "outcome"]
    payload: dict


def register_ijuris_routes(
    api: APIRouter,
    db,
    require_role,
    serialize_fn,
    upsert_physical: Callable,
    upsert_financial: Callable,
    upsert_outcome: Callable,
    now_utc_fn,
):
    ijuris_base_url = os.environ.get("IJURIS_BASE_URL")
    ijuris_token = os.environ.get("IJURIS_TOKEN")

    @api.get("/ijuris/logs")
    async def ijuris_logs(_: dict = Depends(require_role("Admin"))):
        items = await db.ijuris_logs.find().sort("ts", -1).to_list(200)
        return serialize_fn(items)

    @api.post("/ijuris/ingest")
    async def ijuris_ingest(body: IjurisIngestIn, user: dict = Depends(require_role("Admin"))):
        """Mirrors manual-entry validation. If IJURIS_BASE_URL is configured, also
        confirms ingestion against the live iJuris instance. Otherwise runs as STUB."""
        log = {"source": body.source, "record_type": body.record_type,
               "payload": body.payload, "ts": now_utc_fn(), "ingested_by": user["email"]}
        p = body.payload
        status, message = "rejected", None
        try:
            if body.record_type == "physical":
                entry = PhysicalEntryIn(**p)
                await upsert_physical(entry, user)
                status, message = "accepted", "Upserted into physical_entries"
            elif body.record_type == "financial":
                entry = FinancialEntryIn(**p)
                await upsert_financial(entry, user)
                status, message = "accepted", "Upserted into financial_entries"
            elif body.record_type == "outcome":
                entry = OutcomeEntryIn(**p)
                await upsert_outcome(entry, user)
                status, message = "accepted", "Upserted into outcome_entries"
        except HTTPException as e:
            status, message = "rejected", e.detail
        except Exception as e:  # pragma: no cover
            status, message = "rejected", str(e)

        mode = "stub"
        if ijuris_base_url and ijuris_token and status == "accepted":
            try:
                r = requests.post(
                    f"{ijuris_base_url.rstrip('/')}/confirm",
                    headers={"Authorization": f"Bearer {ijuris_token}", "Content-Type": "application/json"},
                    json={"record_type": body.record_type, "payload": p, "pmis_status": status},
                    timeout=15,
                )
                mode = f"live (HTTP {r.status_code})"
            except Exception as e:
                mode = f"live-failed: {e}"

        log["status"] = status
        log["message"] = message
        log["mode"] = mode
        await db.ijuris_logs.insert_one(log)
        return {"status": status, "message": message, "mode": mode}

    @api.post("/ijuris/webhook")
    async def ijuris_webhook(body: IjurisIngestIn, request: Request):
        secret = os.environ.get("IJURIS_WEBHOOK_SECRET")
        if secret:
            sig = request.headers.get("X-IJuris-Signature", "")
            if sig != secret:
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        admin = await db.users.find_one({"role": "Admin"})
        if not admin:
            raise HTTPException(status_code=503, detail="No admin user for webhook ingest")
        user = serialize(admin)
        return await ijuris_ingest(body, user)

    @api.get("/ijuris/config")
    async def ijuris_config(_: dict = Depends(require_role("Admin"))):
        return {
            "live_enabled": bool(ijuris_base_url and ijuris_token),
            "base_url_present": bool(ijuris_base_url),
            "token_present": bool(ijuris_token),
        }
