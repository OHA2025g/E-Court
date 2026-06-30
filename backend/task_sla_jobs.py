"""Scheduled Task Management SLA warning jobs (50/75/90% + breach)."""
import logging
from datetime import datetime, timezone

from bson import ObjectId

from task_permissions import resolve_task_role
from task_sla import compute_sla_status

logger = logging.getLogger("pmis")

SLA_THRESHOLDS = (50, 75, 90)
TERMINAL_STATUSES = frozenset({"CLOSED", "CANCELLED", "DUPLICATE"})


async def _user_email(db, user_id: str | None) -> str | None:
    if not user_id:
        return None
    try:
        doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"email": 1})
    except Exception:
        return None
    return doc.get("email") if doc else None


async def _task_owner_emails(db, task: dict) -> list[str]:
    emails = []
    for field in ("current_owner_id", "assigned_team_member_id", "assigned_team_lead_id"):
        email = await _user_email(db, task.get(field))
        if email:
            emails.append(email)
    return list(dict.fromkeys(emails))


async def _manager_emails(db) -> list[str]:
    docs = await db.users.find({}, {"email": 1, "role": 1, "task_role": 1}).to_list(500)
    return [
        d["email"] for d in docs
        if d.get("email") and resolve_task_role(d) == "manager"
    ]


async def notify_task_sla_warnings(db, now_utc_fn, notify_fn):
    """Scan active tasks and emit deduplicated SLA threshold notifications."""
    now = now_utc_fn()
    tasks = await db.tm_tasks.find({
        "status": {"$nin": list(TERMINAL_STATUSES)},
        "sla_started_at": {"$exists": True, "$ne": None},
    }).to_list(500)

    for task in tasks:
        sla = compute_sla_status(task, now)
        pct = float(sla.get("sla_pct_consumed") or 0)
        code = task.get("task_code") or task.get("id", "")
        title = task.get("title") or ""
        link = f"/task-management/tasks/{task['id']}"

        for threshold in SLA_THRESHOLDS:
            if pct < threshold:
                continue
            key = f"task_sla:{threshold}:{task['id']}"
            if await db.notification_dedup.find_one({"key": key}):
                continue

            emails = await _task_owner_emails(db, task)
            if threshold >= 90:
                kind, subject = "warning", f"SLA critical ({threshold}%): {code}"
                body = f"Task {code} has consumed {pct}% of SLA time — {title}. Immediate action required."
            elif threshold >= 75:
                kind, subject = "warning", f"SLA at risk ({threshold}%): {code}"
                body = f"Task {code} is at {pct}% SLA consumption — {title}."
            else:
                kind, subject = "info", f"SLA halfway ({threshold}%): {code}"
                body = f"Task {code} has reached {threshold}% of allocated SLA time — {title}."

            if emails and notify_fn:
                await notify_fn(emails, subject, body, kind=kind, link=link)
            await db.notification_dedup.insert_one({"key": key, "ts": now})

        if pct >= 100 and task.get("status") != "SLA_BREACHED":
            breach_key = f"task_sla:breach:{task['id']}"
            if await db.notification_dedup.find_one({"key": breach_key}):
                continue

            await db.tm_tasks.update_one(
                {"id": task["id"]},
                {"$set": {
                    "status": "SLA_BREACHED",
                    "sla_breached_at": task.get("sla_breached_at") or now,
                    "updated_at": now,
                }},
            )
            recipients = list(dict.fromkeys(
                (await _task_owner_emails(db, task)) + (await _manager_emails(db))
            ))
            if recipients and notify_fn:
                await notify_fn(
                    recipients,
                    f"SLA breached: {code}",
                    f"Task {code} ({title}) has breached its SLA deadline.",
                    kind="alert",
                    link=link,
                    also_email=True,
                )
            await db.notification_dedup.insert_one({"key": breach_key, "ts": now})

    logger.debug("Task SLA warning scan completed for %d active tasks", len(tasks))
