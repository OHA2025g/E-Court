"""Scheduled notification jobs: period open, overdue, laggard reminders, auto-lock."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from period_policy import get_workflow_settings, grace_deadline

logger = logging.getLogger("pmis")


async def _all_cpc_emails(db) -> list[str]:
    docs = await db.users.find({"role": "CPC"}, {"email": 1}).to_list(200)
    return [d["email"] for d in docs]


async def _target_period(db, now_fn) -> Optional[str]:
    today = now_fn().strftime("%Y-%m")
    pers = await db.reporting_periods.find({"is_baseline": False}).sort("period", -1).to_list(50)
    return next((p["period"] for p in pers if p["period"] <= today), None)


async def notify_period_open(db, now_utc_fn, notify_fn, admin_emails_fn: Callable):
    """Run on 1st of month — alert CPCs that reporting period is open."""
    period = now_utc_fn().strftime("%Y-%m")
    key = f"period_open:{period}"
    if await db.notification_dedup.find_one({"key": key}):
        return
    cpcs = await _all_cpc_emails(db)
    await notify_fn(
        cpcs,
        f"Reporting period open: {period}",
        f"The {period} reporting period is now open for data entry and submission.",
        kind="info", link="/physical", also_email=True,
    )
    await db.notification_dedup.insert_one({"key": key, "ts": now_utc_fn()})


async def notify_overdue_submissions(db, now_utc_fn, notify_fn, admin_emails_fn: Callable, hc_cpc_emails_fn: Callable):
    settings = await get_workflow_settings(db)
    sla_day = int(settings.get("sla_due_day", 10))
    now = now_utc_fn()
    if now.day < sla_day:
        return
    period = await _target_period(db, now_utc_fn)
    if not period:
        return
    key = f"overdue:{period}:{now.strftime('%Y-%m-%d')}"
    if await db.notification_dedup.find_one({"key": key}):
        return
    subs = await db.submissions.find(
        {"reporting_period": period, "status": {"$in": ["Submitted", "Approved"]}}
    ).to_list(100)
    submitted_hcs = {s["high_court"] for s in subs}
    hcs = [h["name"] for h in await db.high_courts.find({"active": True}).to_list(100)]
    overdue = [h for h in hcs if h not in submitted_hcs]
    if not overdue:
        return
    for hc in overdue:
        emails = await hc_cpc_emails_fn(hc)
        await notify_fn(
            emails,
            f"Submission overdue: {period}",
            f"{hc} has not submitted data for {period}. Please submit before the grace period ends.",
            kind="warning", link="/submissions", also_email=True,
        )
    await notify_fn(
        await admin_emails_fn(),
        f"Overdue HCs for {period}",
        f"{len(overdue)} High Court(s) have not submitted: {', '.join(overdue[:10])}{'…' if len(overdue) > 10 else ''}",
        kind="alert", link="/submissions", also_email=True,
    )
    await db.notification_dedup.insert_one({"key": key, "ts": now_utc_fn()})


async def remind_laggards(db, now_utc_fn, notify_fn, admin_emails_fn: Callable, hc_cpc_emails_fn: Callable):
    """Weekly reminder to HCs without submission."""
    period = await _target_period(db, now_utc_fn)
    if not period:
        return
    week = now_utc_fn().strftime("%Y-W%W")
    key = f"laggard:{period}:{week}"
    if await db.notification_dedup.find_one({"key": key}):
        return
    subs = await db.submissions.find(
        {"reporting_period": period, "status": {"$in": ["Submitted", "Approved"]}}
    ).to_list(100)
    submitted_hcs = {s["high_court"] for s in subs}
    hcs = [h["name"] for h in await db.high_courts.find({"active": True}).to_list(100)]
    laggards = [h for h in hcs if h not in submitted_hcs]
    for hc in laggards:
        await notify_fn(
            await hc_cpc_emails_fn(hc),
            f"Reminder: submit {period} data",
            f"Weekly reminder — {hc} has not yet submitted monthly data for {period}.",
            kind="warning", link="/submissions", also_email=True,
        )
    if laggards:
        await notify_fn(
            await admin_emails_fn(),
            f"Weekly laggard digest ({period})",
            f"{len(laggards)} HC(s) pending submission.",
            kind="info", link="/submissions",
        )
    await db.notification_dedup.insert_one({"key": key, "ts": now_utc_fn()})


async def notify_anomaly_digest(db, now_utc_fn, notify_fn, admin_emails_fn: Callable):
    """Weekly digest of statistical outliers (>3σ) across all trackers."""
    from anomaly_routes import (
        detect_financial_anomalies,
        detect_outcome_anomalies,
        detect_physical_anomalies,
    )

    period = await _target_period(db, now_utc_fn)
    if not period:
        return
    week = now_utc_fn().strftime("%Y-W%W")
    key = f"anomaly_digest:{period}:{week}"
    if await db.notification_dedup.find_one({"key": key}):
        return

    flags = []
    flags.extend(await detect_physical_anomalies(db, period, None))
    flags.extend(await detect_financial_anomalies(db, period, None))
    flags.extend(await detect_outcome_anomalies(db, period, None))
    if not flags:
        await db.notification_dedup.insert_one({"key": key, "ts": now_utc_fn()})
        return

    by_tracker = {}
    for f in flags:
        t = f.get("tracker", "physical")
        by_tracker[t] = by_tracker.get(t, 0) + 1
    parts = [f"{t}: {n}" for t, n in sorted(by_tracker.items())]
    body = (
        f"{len(flags)} outlier(s) detected for {period} (>3σ from rolling trend). "
        f"Breakdown — {', '.join(parts)}. Review flagged rows in Physical/Financial/Outcome trackers."
    )
    await notify_fn(
        await admin_emails_fn(),
        f"Weekly anomaly digest ({period})",
        body,
        kind="info",
        link="/physical",
        also_email=True,
    )
    await db.notification_dedup.insert_one({"key": key, "ts": now_utc_fn()})


async def run_auto_lock(db, now_utc_fn):
    """Mark submissions auto_locked when grace period expired without submit."""
    settings = await get_workflow_settings(db)
    grace = int(settings.get("submission_grace_days", 7))
    now = now_utc_fn()
    pers = await db.reporting_periods.find({"is_baseline": False, "period": {"$lte": now.strftime("%Y-%m")}}).to_list(50)
    for p in pers:
        period = p["period"]
        if now <= grace_deadline(period, grace):
            continue
        await db.submissions.update_many(
            {
                "reporting_period": period,
                "status": {"$nin": ["Submitted", "Approved"]},
                "auto_locked": {"$ne": True},
            },
            {"$set": {"auto_locked": True, "auto_locked_at": now_utc_fn()}},
        )
