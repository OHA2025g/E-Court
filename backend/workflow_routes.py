"""Workflow settings, period status, overrides, re-open requests, and SLA."""
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from period_policy import (
    assert_editable,
    get_submission,
    get_workflow_settings,
    grace_deadline,
    is_editable,
    save_workflow_settings,
)


class WorkflowSettingsIn(BaseModel):
    submission_grace_days: Optional[int] = None
    sla_due_day: Optional[int] = None
    dashboard_require_approval: Optional[bool] = None


class PeriodOverrideIn(BaseModel):
    high_court: str
    reporting_period: str
    reason: str
    hours: int = 24


class ReopenRequestIn(BaseModel):
    high_court: str
    reporting_period: str
    reason: str


class ReopenDecisionIn(BaseModel):
    note: Optional[str] = None
    hours: int = 48


def register_workflow_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    require_role,
    audit_fn: Callable,
    serialize_fn: Callable,
    now_utc_fn: Callable,
    notify_fn: Callable,
    admin_emails_fn: Callable,
    hc_cpc_emails_fn: Callable,
):
    @api.get("/workflow/settings")
    async def get_settings(_: dict = Depends(require_fully_authenticated)):
        return await get_workflow_settings(db)

    @api.put("/workflow/settings")
    async def put_settings(body: WorkflowSettingsIn, user: dict = Depends(require_role("Admin"))):
        data = body.model_dump(exclude_none=True)
        saved = await save_workflow_settings(db, data)
        await audit_fn(user, "settings", "update", "workflow_settings",
                       [{"field": k, "old": None, "new": v} for k, v in data.items()])
        return saved

    @api.get("/workflow/period-status")
    async def period_status(
        high_court: str,
        reporting_period: str,
        user: dict = Depends(require_fully_authenticated),
    ):
        if user["role"] == "CPC" and user.get("high_court") != high_court:
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")
        editable, reason = await is_editable(db, high_court, reporting_period, user, now_utc_fn)
        sub = await get_submission(db, high_court, reporting_period)
        settings = await get_workflow_settings(db)
        grace = settings.get("submission_grace_days", 7)
        return {
            "high_court": high_court,
            "reporting_period": reporting_period,
            "editable": editable,
            "reason": reason,
            "submission_status": sub.get("status") if sub else None,
            "grace_deadline": grace_deadline(reporting_period, grace).isoformat(),
            "dashboard_excluded": sub and sub.get("status") not in ("Approved",) and settings.get("dashboard_require_approval"),
        }

    @api.post("/admin/periods/override")
    async def period_override(body: PeriodOverrideIn, user: dict = Depends(require_role("Admin"))):
        until = now_utc_fn() + timedelta(hours=body.hours)
        key = {"high_court": body.high_court, "reporting_period": body.reporting_period}
        sub = await get_submission(db, body.high_court, body.reporting_period)
        if not sub:
            await db.submissions.insert_one({
                **key, "status": "Open", "created_at": now_utc_fn(),
            })
            sub = await get_submission(db, body.high_court, body.reporting_period)
        await db.submissions.update_one(
            {"_id": sub["_id"]},
            {"$set": {
                "edit_override_until": until,
                "override_reason": body.reason,
                "override_by": user["email"],
            }},
        )
        await audit_fn(
            user, "submissions", "override", str(sub["_id"]),
            [{"field": "edit_override_until", "old": None, "new": until.isoformat()}],
            body.high_court, body.reporting_period,
        )
        return {"ok": True, "edit_override_until": until.isoformat()}

    @api.post("/submissions/reopen-request")
    async def reopen_request(body: ReopenRequestIn, user: dict = Depends(require_fully_authenticated)):
        if user["role"] == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only")
        if user["role"] == "CPC" and body.high_court != user.get("high_court"):
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")
        sub = await get_submission(db, body.high_court, body.reporting_period)
        if not sub or sub.get("status") != "Approved":
            raise HTTPException(status_code=400, detail="Re-open only applies to approved submissions")
        doc = {
            "high_court": body.high_court,
            "reporting_period": body.reporting_period,
            "reason": body.reason,
            "status": "Pending",
            "requested_by": user["email"],
            "ts": now_utc_fn(),
        }
        result = await db.period_reopen_requests.insert_one(doc)
        await notify_fn(
            await admin_emails_fn(),
            f"Re-open request: {body.high_court} / {body.reporting_period}",
            f"{user['email']} requested a correction window. Reason: {body.reason}",
            kind="info", link="/submissions", also_email=True,
        )
        return {"id": str(result.inserted_id), "status": "Pending"}

    @api.get("/submissions/reopen-requests")
    async def list_reopen_requests(user: dict = Depends(require_fully_authenticated)):
        q = {}
        if user["role"] == "CPC":
            q["high_court"] = user.get("high_court")
        elif user["role"] != "Admin":
            q["requested_by"] = user["email"]
        items = await db.period_reopen_requests.find(q).sort("ts", -1).limit(100).to_list(100)
        return serialize_fn(items)

    @api.post("/submissions/reopen-request/{req_id}/approve")
    async def approve_reopen(req_id: str, body: ReopenDecisionIn, user: dict = Depends(require_role("Admin"))):
        from bson import ObjectId
        req = await db.period_reopen_requests.find_one({"_id": ObjectId(req_id)})
        if not req or req.get("status") != "Pending":
            raise HTTPException(status_code=404, detail="Request not found or already decided")
        until = now_utc_fn() + timedelta(hours=body.hours)
        await db.period_reopen_requests.update_one(
            {"_id": req["_id"]},
            {"$set": {"status": "Approved", "decided_by": user["email"], "decided_at": now_utc_fn(), "note": body.note}},
        )
        sub = await get_submission(db, req["high_court"], req["reporting_period"])
        if sub:
            await db.submissions.update_one(
                {"_id": sub["_id"]},
                {"$set": {"reopen_until": until, "status": "Returned"}},
            )
        await notify_fn(
            await hc_cpc_emails_fn(req["high_court"]),
            f"Re-open approved: {req['reporting_period']}",
            f"Correction window open until {until.isoformat()}",
            kind="success", link="/submissions", also_email=True,
        )
        return {"ok": True, "reopen_until": until.isoformat()}

    @api.post("/submissions/reopen-request/{req_id}/deny")
    async def deny_reopen(req_id: str, body: ReopenDecisionIn, user: dict = Depends(require_role("Admin"))):
        from bson import ObjectId
        req = await db.period_reopen_requests.find_one({"_id": ObjectId(req_id)})
        if not req or req.get("status") != "Pending":
            raise HTTPException(status_code=404, detail="Request not found or already decided")
        await db.period_reopen_requests.update_one(
            {"_id": req["_id"]},
            {"$set": {"status": "Denied", "decided_by": user["email"], "decided_at": now_utc_fn(), "note": body.note}},
        )
        await notify_fn(
            await hc_cpc_emails_fn(req["high_court"]),
            f"Re-open denied: {req['reporting_period']}",
            body.note or "Request denied by Admin",
            kind="warning", link="/submissions",
        )
        return {"ok": True}

    @api.get("/submissions/sla")
    async def submission_sla(user: dict = Depends(require_fully_authenticated)):
        settings = await get_workflow_settings(db)
        sla_day = int(settings.get("sla_due_day", 10))
        today = now_utc_fn()
        period = today.strftime("%Y-%m")
        pers = await db.reporting_periods.find({"is_baseline": False}).sort("period", -1).to_list(50)
        target_period = next((p["period"] for p in pers if p["period"] <= period), period)
        due = datetime(today.year, today.month, min(sla_day, 28), tzinfo=timezone.utc)
        if today.day > sla_day:
            due = due + timedelta(days=32)
            due = due.replace(day=min(sla_day, 28))
        subs = await db.submissions.find({"reporting_period": target_period}).to_list(100)
        sub_map = {s["high_court"]: s for s in subs}
        hcs = [h["name"] for h in await db.high_courts.find({"active": True}).to_list(100)]
        if user["role"] == "CPC" and user.get("high_court"):
            hcs = [user["high_court"]]
        rows = []
        for hc in hcs:
            sub = sub_map.get(hc)
            status = sub.get("status") if sub else "NotSubmitted"
            days_left = (due - today).days
            rows.append({
                "high_court": hc,
                "reporting_period": target_period,
                "status": status,
                "sla_due": due.isoformat(),
                "days_remaining": days_left,
                "delinquent": status not in ("Submitted", "Approved") and today > due,
            })
        return {"period": target_period, "sla_due_day": sla_day, "rows": rows}
