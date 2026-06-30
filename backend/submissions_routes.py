"""Submission workflow and in-app notification routes."""
from typing import Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cache_layer import cache_invalidate_prefix
from webhook_routes import enqueue_webhook


class SubmissionAction(BaseModel):
    high_court: str
    reporting_period: str
    note: Optional[str] = None


def register_submissions_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    require_role,
    audit_fn,
    serialize_fn,
    now_utc_fn,
    notify_fn,
    admin_emails_fn: Callable[[], Awaitable[list]],
    hc_cpc_emails_fn: Callable[[str], Awaitable[list]],
):
    async def _submission_webhook(high_court: str, reporting_period: str, status: str, actor: str):
        await enqueue_webhook(db, "submission_status", {
            "high_court": high_court,
            "reporting_period": reporting_period,
            "status": status,
            "actor": actor,
        }, now_utc_fn)

    @api.get("/submissions")
    async def list_submissions(
        reporting_period: Optional[str] = None,
        status: Optional[str] = None,
        user: dict = Depends(require_fully_authenticated),
    ):
        q: dict = {}
        if user["role"] == "CPC":
            q["high_court"] = user.get("high_court")
        if reporting_period:
            q["reporting_period"] = reporting_period
        if status:
            q["status"] = status
        items = await db.submissions.find(q).sort([("reporting_period", -1), ("high_court", 1)]).to_list(500)
        return serialize_fn(items)

    @api.post("/submissions/submit")
    async def submit_period(body: SubmissionAction, user: dict = Depends(require_fully_authenticated)):
        if user["role"] == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only role")
        if user["role"] == "CPC" and body.high_court != user.get("high_court"):
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")

        phys_count = await db.physical_entries.count_documents(
            {"high_court": body.high_court, "reporting_period": body.reporting_period}
        )
        fin_count = await db.financial_entries.count_documents(
            {"high_court": body.high_court, "reporting_period": body.reporting_period}
        )
        total = phys_count + fin_count
        if total == 0:
            raise HTTPException(status_code=400, detail="No tracker entries exist for this HC and period")

        key = {"high_court": body.high_court, "reporting_period": body.reporting_period}
        existing = await db.submissions.find_one(key)
        if existing and existing.get("status") == "Approved":
            raise HTTPException(status_code=400, detail="Period already approved — request a Return first")

        doc = {
            **key,
            "status": "Submitted",
            "submitted_at": now_utc_fn(),
            "submitted_by": user["email"],
            "entry_count": total,
            "physical_count": phys_count,
            "financial_count": fin_count,
            "note": body.note,
        }
        if existing:
            await db.submissions.update_one({"_id": existing["_id"]}, {"$set": doc})
            sid = str(existing["_id"])
        else:
            result = await db.submissions.insert_one(doc)
            sid = str(result.inserted_id)
        await audit_fn(
            user, "submissions", "submit", sid,
            [{"field": "status", "old": existing.get("status") if existing else None, "new": "Submitted"}],
            body.high_court, body.reporting_period,
        )
        await notify_fn(
            await admin_emails_fn(),
            f"Submission ready: {body.high_court} / {body.reporting_period}",
            f"{user['email']} has submitted {total} entries ({phys_count} physical + {fin_count} financial) for review.",
            kind="info", link="/submissions",
            meta={"high_court": body.high_court, "period": body.reporting_period},
            also_email=True,
        )
        await _submission_webhook(body.high_court, body.reporting_period, "Submitted", user["email"])
        return {"id": sid, "status": "Submitted"}

    @api.post("/submissions/approve")
    async def approve_submission(body: SubmissionAction, user: dict = Depends(require_role("Admin"))):
        existing = await db.submissions.find_one(
            {"high_court": body.high_court, "reporting_period": body.reporting_period}
        )
        if not existing:
            raise HTTPException(status_code=404, detail="No submission found for this HC and period")
        if existing.get("status") not in ("Submitted", "Returned"):
            raise HTTPException(status_code=400, detail=f"Cannot approve from status '{existing.get('status')}'")
        await db.submissions.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "status": "Approved",
                "approved_at": now_utc_fn(),
                "approved_by": user["email"],
                "approval_note": body.note,
            }},
        )
        await audit_fn(
            user, "submissions", "approve", str(existing["_id"]),
            [{"field": "status", "old": existing.get("status"), "new": "Approved"}],
            body.high_court, body.reporting_period,
        )
        await notify_fn(
            await hc_cpc_emails_fn(body.high_court),
            f"Submission Approved: {body.reporting_period}",
            f"Your monthly submission for {body.high_court} / {body.reporting_period} has been approved by {user['email']}.",
            kind="success", link="/submissions",
            meta={"high_court": body.high_court, "period": body.reporting_period},
            also_email=True,
        )
        cache_invalidate_prefix("public:progress")
        cache_invalidate_prefix("dashboard:")
        await _submission_webhook(body.high_court, body.reporting_period, "Approved", user["email"])
        return {"ok": True, "status": "Approved"}

    @api.post("/submissions/return")
    async def return_submission(body: SubmissionAction, user: dict = Depends(require_role("Admin"))):
        if not body.note:
            raise HTTPException(status_code=400, detail="A return reason is required")
        existing = await db.submissions.find_one(
            {"high_court": body.high_court, "reporting_period": body.reporting_period}
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Submission not found")
        await db.submissions.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "status": "Returned",
                "returned_at": now_utc_fn(),
                "returned_by": user["email"],
                "return_reason": body.note,
            }},
        )
        await audit_fn(
            user, "submissions", "return", str(existing["_id"]),
            [{"field": "status", "old": existing.get("status"), "new": "Returned"}],
            body.high_court, body.reporting_period,
        )
        await notify_fn(
            await hc_cpc_emails_fn(body.high_court),
            f"Submission Returned: {body.reporting_period}",
            f"Your submission for {body.high_court} / {body.reporting_period} was returned by {user['email']}. Reason: {body.note}",
            kind="warning", link="/submissions",
            meta={"high_court": body.high_court, "period": body.reporting_period, "reason": body.note},
        )
        await _submission_webhook(body.high_court, body.reporting_period, "Returned", user["email"])
        return {"ok": True, "status": "Returned"}

    @api.get("/submissions/overdue")
    async def overdue_submissions(user: dict = Depends(require_fully_authenticated)):
        today = now_utc_fn().strftime("%Y-%m")
        pers = await db.reporting_periods.find({"is_baseline": False}).sort("period", -1).to_list(50)
        target_period = next((p["period"] for p in pers if p["period"] <= today), None)
        if not target_period:
            return {"period": None, "overdue": []}
        submitted = await db.submissions.find(
            {"reporting_period": target_period, "status": {"$in": ["Submitted", "Approved"]}}
        ).to_list(100)
        submitted_hcs = {s["high_court"] for s in submitted}
        all_hcs = [h["name"] for h in await db.high_courts.find({"active": True}).to_list(100)]
        overdue = [h for h in all_hcs if h not in submitted_hcs]
        return {"period": target_period, "overdue": overdue}

    @api.get("/notifications")
    async def list_notifications(
        unread_only: bool = False,
        limit: int = 50,
        user: dict = Depends(require_fully_authenticated),
    ):
        q: dict = {"to_email": user["email"]}
        if unread_only:
            q["is_read"] = False
        items = await db.notifications.find(q).sort("ts", -1).limit(limit).to_list(limit)
        unread = await db.notifications.count_documents({"to_email": user["email"], "is_read": False})
        return {"items": serialize_fn(items), "unread_count": unread}

    @api.post("/notifications/{nid}/read")
    async def mark_read(nid: str, user: dict = Depends(require_fully_authenticated)):
        from bson import ObjectId
        await db.notifications.update_one(
            {"_id": ObjectId(nid), "to_email": user["email"]},
            {"$set": {"is_read": True, "read_at": now_utc_fn()}},
        )
        return {"ok": True}

    @api.post("/notifications/mark-all-read")
    async def mark_all_read(user: dict = Depends(require_fully_authenticated)):
        r = await db.notifications.update_many(
            {"to_email": user["email"], "is_read": False},
            {"$set": {"is_read": True, "read_at": now_utc_fn()}},
        )
        return {"ok": True, "marked": r.modified_count}

    @api.get("/email-outbox")
    async def email_outbox(user: dict = Depends(require_role("Admin"))):
        items = await db.email_outbox.find().sort("ts", -1).limit(100).to_list(100)
        return serialize_fn(items)
