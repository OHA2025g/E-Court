"""Drain db.email_outbox via SMTP when configured."""
import base64
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Callable, Optional

from fastapi import Depends, HTTPException

logger = logging.getLogger("pmis")
BATCH_SIZE = 25


def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"))


def _smtp_settings() -> dict:
    return {
        "host": os.environ["SMTP_HOST"],
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER") or None,
        "password": os.environ.get("SMTP_PASSWORD") or None,
        "from_addr": os.environ["SMTP_FROM"],
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"),
    }


def send_smtp_message(
    to_addr: str,
    subject: str,
    body: str,
    from_addr: str,
    settings: dict,
    attachment: Optional[dict] = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    if attachment and attachment.get("data"):
        msg.add_attachment(
            attachment["data"],
            maintype=attachment.get("maintype", "application"),
            subtype=attachment.get("subtype", "pdf"),
            filename=attachment.get("filename", "attachment.pdf"),
        )
    with smtplib.SMTP(settings["host"], settings["port"], timeout=60) as smtp:
        if settings["use_tls"]:
            smtp.starttls()
        if settings["user"]:
            smtp.login(settings["user"], settings["password"] or "")
        smtp.send_message(msg)


async def drain_email_outbox(db, now_utc_fn: Callable, batch_size: int = BATCH_SIZE) -> dict:
    """Send queued outbox rows. Marks sent/failed in MongoDB."""
    if not smtp_configured():
        return {"skipped": True, "reason": "SMTP not configured", "sent": 0, "failed": 0}

    settings = _smtp_settings()
    items = await db.email_outbox.find({"status": "queued"}).sort("ts", 1).limit(batch_size).to_list(batch_size)
    sent = failed = 0
    for item in items:
        try:
            attachment = None
            if item.get("attachment_base64"):
                attachment = {
                    "data": base64.b64decode(item["attachment_base64"]),
                    "filename": item.get("attachment_filename", "cabinet_brief.pdf"),
                    "maintype": "application",
                    "subtype": "pdf",
                }
            send_smtp_message(
                item["to"], item["subject"], item.get("body") or "",
                settings["from_addr"], settings, attachment=attachment,
            )
            await db.email_outbox.update_one(
                {"_id": item["_id"]},
                {"$set": {"status": "sent", "sent_at": now_utc_fn()}},
            )
            sent += 1
        except Exception as e:
            logger.warning("SMTP send failed for %s: %s", item.get("to"), e)
            await db.email_outbox.update_one(
                {"_id": item["_id"]},
                {"$set": {"status": "failed", "error": str(e), "failed_at": now_utc_fn()}},
            )
            failed += 1
    if sent or failed:
        logger.info("Email outbox drain: sent=%d failed=%d", sent, failed)
    return {"skipped": False, "sent": sent, "failed": failed, "processed": len(items)}


def register_email_worker_routes(api, db, require_role, now_utc_fn: Callable):
    @api.get("/admin/email-worker/status")
    async def email_worker_status(_: dict = Depends(require_role("Admin"))):
        return {"smtp_configured": smtp_configured(), "batch_size": BATCH_SIZE}

    @api.post("/admin/email-outbox/drain")
    async def drain_outbox_now(_: dict = Depends(require_role("Admin"))):
        result = await drain_email_outbox(db, now_utc_fn)
        if result.get("skipped"):
            raise HTTPException(status_code=503, detail=result.get("reason", "SMTP not configured"))
        return result
