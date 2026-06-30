"""Webhook outbox — push events to Slack/Teams/custom URLs."""
import hashlib
import hmac
import json
import logging
from typing import Callable, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from security_bootstrap import validate_outbound_url

logger = logging.getLogger("pmis")


class WebhookIn(BaseModel):
    name: str
    url: str
    secret: Optional[str] = None
    events: list[str] = ["rag_change", "submission_status"]
    active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return validate_outbound_url(value)


async def enqueue_webhook(db, event: str, payload: dict, now_utc_fn):
    hooks = await db.webhooks.find({"active": True, "events": event}).to_list(50)
    if not hooks:
        return
    rows = [{
        "webhook_id": str(h["_id"]),
        "event": event,
        "url": h["url"],
        "secret": h.get("secret"),
        "payload": payload,
        "status": "queued",
        "ts": now_utc_fn(),
    } for h in hooks]
    await db.webhook_outbox.insert_many(rows)


async def drain_webhook_outbox(db, now_utc_fn, limit: int = 25):
    items = await db.webhook_outbox.find({"status": "queued"}).sort("ts", 1).limit(limit).to_list(limit)
    for item in items:
        body = json.dumps({"event": item["event"], "payload": item["payload"]})
        headers = {"Content-Type": "application/json"}
        if item.get("secret"):
            sig = hmac.new(item["secret"].encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-PMIS-Signature"] = sig
        try:
            validate_outbound_url(item["url"])
            r = requests.post(item["url"], data=body, headers=headers, timeout=15, allow_redirects=False)
            status = "sent" if r.status_code < 400 else "failed"
            await db.webhook_outbox.update_one(
                {"_id": item["_id"]},
                {"$set": {"status": status, "http_status": r.status_code, "sent_at": now_utc_fn()}},
            )
        except Exception as e:
            await db.webhook_outbox.update_one(
                {"_id": item["_id"]},
                {"$set": {"status": "failed", "error": str(e), "failed_at": now_utc_fn()}},
            )


def register_webhook_routes(api, db, require_role, serialize_fn, now_utc_fn):
    @api.get("/admin/webhooks")
    async def list_webhooks(_: dict = Depends(require_role("Admin"))):
        items = await db.webhooks.find({}, {"secret": 0}).to_list(50)
        return serialize_fn(items)

    @api.post("/admin/webhooks")
    async def create_webhook(body: WebhookIn, _: dict = Depends(require_role("Admin"))):
        doc = {**body.model_dump(), "created_at": now_utc_fn()}
        r = await db.webhooks.insert_one(doc)
        return {"id": str(r.inserted_id)}

    @api.delete("/admin/webhooks/{wid}")
    async def delete_webhook(wid: str, _: dict = Depends(require_role("Admin"))):
        from bson import ObjectId
        await db.webhooks.delete_one({"_id": ObjectId(wid)})
        return {"ok": True}

    @api.get("/admin/webhook-outbox")
    async def webhook_outbox(_: dict = Depends(require_role("Admin"))):
        items = await db.webhook_outbox.find().sort("ts", -1).limit(100).to_list(100)
        return serialize_fn(items)
