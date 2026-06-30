"""Tests for scheduled Task Management SLA warning jobs."""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from task_sla_jobs import notify_task_sla_warnings

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "pmis_ecourts")
_sync_db = __import__("pymongo").MongoClient(MONGO_URL)[DB_NAME]


async def _run_job(notifications=None):
    captured = notifications if notifications is not None else []
    async_db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

    async def notify(emails, title, body, kind="info", link=None, also_email=False, **kwargs):
        captured.append({
            "emails": emails,
            "title": title,
            "body": body,
            "kind": kind,
            "link": link,
        })

    now = datetime.now(timezone.utc)
    await notify_task_sla_warnings(async_db, lambda: now, notify)
    return captured, now


def test_sla_threshold_notification_dedup():
    task_id = str(uuid.uuid4())
    task_code = f"TASK-TEST-SLA-{task_id[:8]}"
    started = datetime.now(timezone.utc) - timedelta(hours=9)
    _sync_db.tm_tasks.delete_many({"id": task_id})
    _sync_db.tm_tasks.insert_one({
        "id": task_id,
        "task_code": task_code,
        "title": "SLA threshold test",
        "status": "IN_PROGRESS",
        "priority": "High",
        "sla_hours": 12,
        "sla_started_at": started,
        "created_at": started,
        "assigned_team_member_id": str(_sync_db.users.find_one({"email": "member@pmis.gov.in"})["_id"]),
    })
    _sync_db.notification_dedup.delete_many({"key": {"$regex": f"task_sla:.*:{task_id}"}})

    async def run_both():
        notes1, _ = await _run_job()
        notes2, _ = await _run_job()
        return notes1, notes2

    notes1, notes2 = asyncio.run(run_both())

    threshold_titles = [n["title"] for n in notes1 if "SLA" in n["title"]]
    assert any("50%" in t or "75%" in t or "90%" in t for t in threshold_titles)
    assert len([n for n in notes2 if "SLA" in n["title"]]) == 0

    _sync_db.tm_tasks.delete_one({"id": task_id})
    _sync_db.notification_dedup.delete_many({"key": {"$regex": f"task_sla:.*:{task_id}"}})


def test_sla_breach_marks_task_and_notifies_managers():
    task_id = str(uuid.uuid4())
    task_code = f"TASK-TEST-BREACH-{task_id[:8]}"
    started = datetime.now(timezone.utc) - timedelta(hours=25)
    _sync_db.tm_tasks.delete_many({"id": task_id})
    _sync_db.tm_tasks.insert_one({
        "id": task_id,
        "task_code": task_code,
        "title": "SLA breach test",
        "status": "IN_PROGRESS",
        "priority": "Medium",
        "sla_hours": 8,
        "sla_started_at": started,
        "created_at": started,
        "assigned_team_lead_id": str(_sync_db.users.find_one({"email": "cpc.allahabad@pmis.gov.in"})["_id"]),
    })
    _sync_db.notification_dedup.delete_many({"key": f"task_sla:breach:{task_id}"})

    notes, _ = asyncio.run(_run_job())

    doc = _sync_db.tm_tasks.find_one({"id": task_id})
    assert doc["status"] == "SLA_BREACHED"
    assert doc.get("sla_breached_at") is not None
    assert any("breached" in n["title"].lower() for n in notes)

    _sync_db.tm_tasks.delete_one({"id": task_id})
    _sync_db.notification_dedup.delete_many({"key": f"task_sla:breach:{task_id}"})
