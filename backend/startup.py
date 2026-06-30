"""Application startup: migrations, seeding, scheduler, and lifespan."""
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Optional

from apscheduler.triggers.cron import CronTrigger

from auth import ensure_auth_indexes, hash_password, verify_password
from dashboard_prefs import ensure_dashboard_indexes
from seed_constants import (
    COMPONENT_INDICATORS,
    COMPONENTS,
    DEFAULT_RAG_THRESHOLDS,
    DPR_DELIVERABLES,
    HIGH_COURTS,
    OUTCOME_SUBJECTS,
    REPORTING_PERIODS,
)
from outcome_excel import build_kpi_master, outcome_seed_docs

logger = logging.getLogger("pmis")
ROOT_DIR = Path(__file__).parent
OUTCOME_SEED_VERSION = 3


async def migrate_district_indexes(database):
    """Ensure district field exists and unique indexes include district."""
    await database.physical_entries.update_many(
        {"district": {"$exists": False}}, {"$set": {"district": None}}
    )
    await database.financial_entries.update_many(
        {"district": {"$exists": False}}, {"$set": {"district": None}}
    )
    for coll, new_keys in [
        (database.physical_entries,
         [("high_court", 1), ("component", 1), ("indicator", 1), ("reporting_period", 1), ("district", 1)]),
        (database.financial_entries,
         [("high_court", 1), ("component", 1), ("reporting_period", 1), ("district", 1)]),
    ]:
        info = await coll.index_information()
        for idx_name, idx in list(info.items()):
            if idx_name == "_id_":
                continue
            keys = idx.get("key", [])
            key_fields = [k[0] for k in keys]
            if idx.get("unique") and "district" not in key_fields:
                try:
                    await coll.drop_index(idx_name)
                except Exception:
                    pass
        await coll.create_index(new_keys, unique=True)


async def migrate_outcome_district_index(database):
    """Ensure outcome district field exists and unique index includes district."""
    await database.outcome_entries.update_many(
        {"district": {"$exists": False}}, {"$set": {"district": None}}
    )
    coll = database.outcome_entries
    new_keys = [
        ("high_court", 1), ("subject", 1), ("kpi_id", 1),
        ("reporting_period", 1), ("granularity", 1), ("district", 1),
    ]
    for idx in await coll.list_indexes().to_list(20):
        idx_name = idx.get("name")
        if idx_name == "_id_":
            continue
        keys = idx.get("key", {})
        key_fields = [k[0] for k in keys]
        if idx.get("unique") and "district" not in key_fields:
            try:
                await coll.drop_index(idx_name)
            except Exception:
                pass
    await coll.create_index(new_keys, unique=True)


async def ensure_indexes(db):
    await db.users.create_index("email", unique=True)
    await migrate_district_indexes(db)
    await migrate_outcome_district_index(db)
    await db.bulk_previews.create_index("token", unique=True)
    await db.bulk_previews.create_index("expires_at", expireAfterSeconds=0)
    await db.audit_logs.create_index([("timestamp", -1)])
    await db.login_attempts.create_index([("email", 1), ("ts", -1)])
    await db.login_locks.create_index("email", unique=True)
    await db.files.create_index("id", unique=True)
    await db.districts.create_index([("high_court", 1), ("name", 1)], unique=True)
    await db.submissions.create_index([("high_court", 1), ("reporting_period", 1)], unique=True)
    await db.notifications.create_index([("to_email", 1), ("ts", -1)])
    await db.notifications.create_index([("to_email", 1), ("is_read", 1)])
    await db.notification_dedup.create_index("key", unique=True)
    await db.period_reopen_requests.create_index([("high_court", 1), ("reporting_period", 1)])
    await db.entry_comments.create_index([("tracker", 1), ("entry_id", 1)])
    await db.saved_report_views.create_index([("user_id", 1), ("name", 1)])
    await db.api_tokens.create_index("token_hash", unique=True)
    await db.webhook_outbox.create_index([("status", 1), ("ts", 1)])
    await db.narrative_reviews.create_index("reporting_period", unique=True)
    await db.dashboard_ai_insights.create_index("cache_key", unique=True)
    await db.dashboard_ai_insights.create_index("generated_at")
    await db.tm_tasks.create_index("id", unique=True)
    await db.tm_tasks.create_index("task_code", unique=True)
    await db.tm_tasks.create_index([("status", 1), ("updated_at", -1)])
    await db.tm_tasks.create_index("assigned_team_lead_id")
    await db.tm_tasks.create_index("assigned_team_member_id")
    await db.tm_tasks.create_index("created_by_id")
    await db.tm_audit_log.create_index([("task_id", 1), ("performed_at", -1)])
    await db.tm_comments.create_index([("task_id", 1), ("created_at", 1)])
    await db.tm_evidence.create_index([("task_id", 1), ("version", -1)])
    from scope_charter_routes import ensure_scope_charter_indexes
    await ensure_scope_charter_indexes(db)
    await ensure_auth_indexes(db)
    await ensure_dashboard_indexes(db)


async def seed_master(db):
    if await db.high_courts.count_documents({}) == 0:
        await db.high_courts.insert_many([{"name": n, "active": True} for n in HIGH_COURTS])
    if await db.components.count_documents({}) == 0:
        await db.components.insert_many([{"seq": i + 1, **c} for i, c in enumerate(COMPONENTS)])
    if await db.indicators.count_documents({}) == 0:
        docs = []
        for comp, inds in COMPONENT_INDICATORS.items():
            for ind in inds:
                unit = "Crore Pages" if "Cr." in ind else "PB" if "PB" in ind else "Percentage" if "%" in ind else "Count"
                docs.append({"component": comp, "indicator": ind, "unit": unit, "data_type": "Float" if unit != "Count" else "Int"})
        if docs:
            await db.indicators.insert_many(docs)
    if await db.outcome_subjects.count_documents({}) == 0:
        await db.outcome_subjects.insert_many([{"name": s} for s in OUTCOME_SUBJECTS])
    if await db.reporting_periods.count_documents({}) == 0:
        await db.reporting_periods.insert_many(REPORTING_PERIODS)
    if await db.settings.count_documents({"key": "rag_thresholds"}) == 0:
        await db.settings.insert_one({"key": "rag_thresholds", "value": DEFAULT_RAG_THRESHOLDS})
    if await db.settings.count_documents({"key": "admin_ip_allowlist"}) == 0:
        await db.settings.insert_one({"key": "admin_ip_allowlist", "value": {"enabled": False, "cidrs": []}})
    if await db.settings.count_documents({"key": "workflow_settings"}) == 0:
        await db.settings.insert_one({
            "key": "workflow_settings",
            "value": {
                "submission_grace_days": 7,
                "sla_due_day": 10,
                "dashboard_require_approval": True,
            },
        })


async def seed_districts(db):
    if await db.districts.count_documents({}) > 0:
        return
    sample = {
        "Allahabad": ["Prayagraj", "Lucknow", "Kanpur", "Varanasi"],
        "Bombay": ["Mumbai", "Pune", "Nagpur", "Aurangabad"],
        "Delhi": ["Central", "North", "South", "East", "West"],
        "Calcutta": ["Kolkata", "Howrah", "Burdwan", "Darjeeling"],
        "Madras": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli"],
        "Karnataka": ["Bengaluru Urban", "Mysuru", "Hubballi-Dharwad", "Mangaluru"],
        "Punjab & Haryana": ["Chandigarh", "Amritsar", "Ludhiana", "Gurugram", "Faridabad"],
        "Kerala": ["Ernakulam", "Thiruvananthapuram", "Kozhikode", "Thrissur"],
        "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
        "Telangana": ["Hyderabad", "Warangal", "Karimnagar", "Nizamabad"],
    }
    docs = []
    for hc, dists in sample.items():
        for d in dists:
            docs.append({"high_court": hc, "name": d, "active": True})
    if docs:
        await db.districts.insert_many(docs)


async def seed_users(db, now_utc_fn: Callable):
    spec = [
        (os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"], "PMU Administrator", "Admin", None, "manager", None),
        (os.environ["CPC_DEMO_EMAIL"], os.environ["CPC_DEMO_PASSWORD"], "Allahabad CPC Officer", "CPC", "Allahabad", "team_lead", None),
        (os.environ["VIEWER_DEMO_EMAIL"], os.environ["VIEWER_DEMO_PASSWORD"], "e-Committee Reviewer", "Viewer", None, "auditor", None),
        (os.environ.get("TASK_MEMBER_EMAIL", "member@pmis.gov.in"),
         os.environ.get("TASK_MEMBER_PASSWORD", "Member@PMIS2026"),
         "Task Team Member", "Viewer", None, "team_member", "CPC_DEMO_EMAIL"),
    ]
    cpc_id = None
    for email, pw, name, role, hc, task_role, team_lead_ref in spec:
        email = email.lower()
        existing = await db.users.find_one({"email": email})
        ph = hash_password(pw)
        team_lead_id = None
        if team_lead_ref and team_lead_ref != "CPC_DEMO_EMAIL":
            tl = await db.users.find_one({"email": team_lead_ref.lower()})
            team_lead_id = str(tl["_id"]) if tl else None
        elif team_lead_ref == "CPC_DEMO_EMAIL":
            tl = await db.users.find_one({"email": os.environ["CPC_DEMO_EMAIL"].lower()})
            team_lead_id = str(tl["_id"]) if tl else None
        doc = {
            "email": email, "name": name, "role": role, "high_court": hc,
            "task_role": task_role, "team_lead_id": team_lead_id,
            "password_hash": ph, "password_history": [], "password_changed_at": now_utc_fn(),
            "created_at": now_utc_fn(), "created_by": "system",
        }
        if not existing:
            result = await db.users.insert_one(doc)
            if role == "CPC":
                cpc_id = str(result.inserted_id)
        else:
            await db.users.update_one({"email": email}, {"$set": {
                "task_role": task_role,
                "team_lead_id": team_lead_id or existing.get("team_lead_id"),
                "name": name,
            }})
            if not verify_password(pw, existing.get("password_hash", "")):
                await db.users.update_one({"email": email}, {"$set": {"password_hash": ph}})
            if role == "CPC":
                cpc_id = str(existing["_id"])
    if cpc_id:
        member_email = os.environ.get("TASK_MEMBER_EMAIL", "member@pmis.gov.in").lower()
        await db.users.update_one(
            {"email": member_email},
            {"$set": {"team_lead_id": cpc_id}},
        )


async def migrate_outcome_seed_v2(db, now_utc_fn: Callable):
    """Replace baseline outcome rows seeded with wrong Excel subject column."""
    setting = await db.settings.find_one({"key": "outcome_seed_version"})
    if setting and setting.get("value", 0) >= OUTCOME_SEED_VERSION:
        return

    path = ROOT_DIR / "seed_data.json"
    if not path.exists():
        return
    with open(path) as f:
        data = json.load(f)

    outcome_rows = data.get("outcome_baseline") or []
    if not outcome_rows:
        return

    period = "2026-05"
    kpi_master = build_kpi_master(outcome_rows)
    out_docs = outcome_seed_docs(outcome_rows, period, now_utc_fn)

    await db.outcome_entries.delete_many({"created_by": "system", "reporting_period": period})
    await db.kpis.delete_many({})
    if kpi_master:
        await db.kpis.insert_many(list(kpi_master.values()))
    if out_docs:
        try:
            await db.outcome_entries.insert_many(out_docs, ordered=False)
        except Exception as e:
            logger.warning("Outcome seed v2 insert had dupes ignored: %s", e)

    await db.settings.update_one(
        {"key": "outcome_seed_version"},
        {"$set": {"value": OUTCOME_SEED_VERSION}},
        upsert=True,
    )
    logger.info(
        "Outcome seed v2 migration applied (%d KPIs, %d baseline rows)",
        len(kpi_master),
        len(out_docs),
    )


async def backfill_outcome_component_fields(db):
    """Populate component/sub_component on legacy outcome rows from KPI master."""
    setting = await db.settings.find_one({"key": "outcome_component_backfill"})
    if setting and setting.get("value"):
        return
    updated = 0
    cursor = db.outcome_entries.find({
        "$or": [
            {"component": None},
            {"component": {"$exists": False}},
            {"sub_component": None},
            {"sub_component": {"$exists": False}},
        ]
    })
    async for entry in cursor:
        kpi = await db.kpis.find_one({"subject": entry.get("subject"), "kpi_id": entry.get("kpi_id")})
        if not kpi:
            continue
        patch = {}
        if not entry.get("component") and kpi.get("component"):
            patch["component"] = kpi["component"]
        if not entry.get("sub_component"):
            patch["sub_component"] = kpi.get("sub_component") or kpi.get("subject")
        if patch:
            await db.outcome_entries.update_one({"_id": entry["_id"]}, {"$set": patch})
            updated += 1
    await db.settings.update_one(
        {"key": "outcome_component_backfill"},
        {"$set": {"value": True}},
        upsert=True,
    )
    if updated:
        logger.info("Backfilled component/sub_component on %d outcome rows", updated)


async def fix_outcome_kpi_names(db):
    """Replace mistaken KPI ID strings in the kpi field with full KPI names from seed."""
    setting = await db.settings.find_one({"key": "outcome_kpi_name_fix"})
    if setting and setting.get("value"):
        return
    path = ROOT_DIR / "seed_data.json"
    if not path.exists():
        return
    with open(path) as f:
        data = json.load(f)
    rows = data.get("outcome_baseline") or []
    kpi_names = {}
    for row in rows:
        key = (row["subject"], row["kpi_id"])
        if row.get("kpi") and row["kpi"] != row["kpi_id"]:
            kpi_names[key] = {
                "kpi": row["kpi"],
                "description": row.get("description"),
            }
    if not kpi_names:
        return
    updated_kpis, updated_entries = 0, 0
    for (subject, kpi_id), patch in kpi_names.items():
        res = await db.kpis.update_one(
            {"subject": subject, "kpi_id": kpi_id},
            {"$set": patch},
        )
        if res.modified_count:
            updated_kpis += 1
        res = await db.outcome_entries.update_many(
            {"subject": subject, "kpi_id": kpi_id},
            {"$set": patch},
        )
        updated_entries += res.modified_count
    await db.settings.update_one(
        {"key": "outcome_kpi_name_fix"},
        {"$set": {"value": True}},
        upsert=True,
    )
    logger.info(
        "Fixed KPI names on %d master rows and %d outcome entries",
        updated_kpis,
        updated_entries,
    )


async def seed_baseline(db, now_utc_fn: Callable, compute_rag_fn: Callable, safe_div_fn: Callable):
    if await db.physical_entries.count_documents({}) > 0:
        return
    path = ROOT_DIR / "seed_data.json"
    if not path.exists():
        return
    with open(path) as f:
        data = json.load(f)

    kpi_master = build_kpi_master(data["outcome_baseline"])
    if await db.kpis.count_documents({}) == 0 and kpi_master:
        await db.kpis.insert_many(list(kpi_master.values()))

    period = "2026-05"
    thresholds = DEFAULT_RAG_THRESHOLDS

    phys_docs = []
    for r in data["physical_baseline"]:
        target, achieved = r.get("target"), r.get("achieved")
        percent = safe_div_fn(achieved, target)
        phys_docs.append({
            "high_court": r["high_court"], "component": r["component"],
            "indicator": r["indicator"], "reporting_period": period,
            "target": target, "achieved": achieved,
            "percent": percent, "rag": compute_rag_fn(percent, thresholds),
            "remarks": None, "created_by": "system", "created_at": now_utc_fn(),
        })
    if phys_docs:
        try:
            await db.physical_entries.insert_many(phys_docs, ordered=False)
        except Exception as e:
            logger.warning("Some physical seed dupes ignored: %s", e)

    fin_docs = []
    for r in data["financial_baseline"]:
        rel, util = r.get("fund_released"), r.get("fund_utilized")
        util_pct = safe_div_fn(util, rel)
        variance = (rel - util) if (rel is not None and util is not None) else None
        fin_docs.append({
            "high_court": r["high_court"], "component": r["component"],
            "reporting_period": period, "description": r.get("description"),
            "fund_target": r.get("fund_target"),
            "fund_allocated": r.get("fund_allocated"),
            "fund_released": rel, "fund_utilized": util,
            "utilisation_percent": util_pct,
            "variance": round(variance, 2) if variance is not None else None,
            "rag": compute_rag_fn(util_pct, thresholds),
            "remarks": None, "created_by": "system", "created_at": now_utc_fn(),
        })
    if fin_docs:
        try:
            await db.financial_entries.insert_many(fin_docs, ordered=False)
        except Exception as e:
            logger.warning("Some financial seed dupes ignored: %s", e)

    out_docs = outcome_seed_docs(data["outcome_baseline"], period, now_utc_fn)
    if out_docs:
        try:
            await db.outcome_entries.insert_many(out_docs, ordered=False)
        except Exception as e:
            logger.warning("Some outcome seed dupes ignored: %s", e)


async def seed_dpr(db, now_utc_fn: Callable):
    if await db.dpr_deliverables.count_documents({}) > 0:
        return
    docs = []
    for d in DPR_DELIVERABLES:
        docs.append({**d, "rag": "GREEN" if d["status"] == "Completed" else "AMBER" if d["status"] == "In Progress" else "RED",
                     "created_at": now_utc_fn(), "created_by": "system"})
    await db.dpr_deliverables.insert_many(docs)


async def seed_pmu_tasks(db, now_utc_fn: Callable):
    if await db.pmu_tasks.count_documents({}) > 0:
        return
    sample = [
        {"title": "Validate Q1 progress submissions from all 28 HCs", "owner": "PMU Lead",
         "priority": "High", "status": "In Progress",
         "due_date": "2026-04-15", "description": "Cross-check Physical & Financial submissions against vendor reports."},
        {"title": "Finalise RAG thresholds with DoJ Secretary", "owner": "PMU Director",
         "priority": "Critical", "status": "Open",
         "due_date": "2026-03-30", "description": "Review and obtain sign-off on Green/Amber/Red thresholds."},
        {"title": "iJuris API integration discovery", "owner": "PMU Tech Lead",
         "priority": "Medium", "status": "Open",
         "due_date": "2026-05-15", "description": "Coordinate with e-Committee for API access."},
        {"title": "Quarterly progress brief for Cabinet Secretariat", "owner": "DoJ Nodal Officer",
         "priority": "High", "status": "Completed",
         "due_date": "2026-02-28", "description": "Prepare slide deck and brief note."},
        {"title": "Vendor reconciliation for digitisation milestones", "owner": "PMU Finance",
         "priority": "Medium", "status": "Overdue",
         "due_date": "2026-02-15", "description": "Match invoices with progress reports for pages digitised."},
    ]
    for s in sample:
        s.update({"stakeholder": "DoJ/e-Committee", "comments": None,
                  "created_at": now_utc_fn(), "updated_at": now_utc_fn(), "created_by": "system"})
    await db.pmu_tasks.insert_many(sample)


async def seed_tm_tasks(db, now_utc_fn: Callable):
    if await db.tm_tasks.count_documents({}) > 0:
        return
    admin = await db.users.find_one({"email": os.environ["ADMIN_EMAIL"].lower()})
    cpc = await db.users.find_one({"email": os.environ["CPC_DEMO_EMAIL"].lower()})
    member = await db.users.find_one({"email": os.environ.get("TASK_MEMBER_EMAIL", "member@pmis.gov.in").lower()})
    if not admin or not cpc:
        return
    admin_id = str(admin["_id"])
    cpc_id = str(cpc["_id"])
    member_id = str(member["_id"]) if member else None
    now = now_utc_fn()
    from datetime import timedelta
    samples = [
        {
            "id": "seed-task-001", "task_code": "TASK-2026-00001",
            "title": "MahaID integration checkpoint review",
            "description": "Review integration milestones and evidence pack for MahaID module.",
            "category": "Integration", "module_name": "Project Execution", "project_name": "MahaID",
            "priority": "Critical", "status": "MANAGER_APPROVAL_PENDING",
            "created_by_id": admin_id, "assigned_team_lead_id": cpc_id, "assigned_team_member_id": member_id,
            "current_owner_id": admin_id, "evidence_required": True, "manager_final_approval_required": True,
            "sla_hours": 24, "sla_status": "AT_RISK", "sla_started_at": now - timedelta(hours=20),
            "due_date": now + timedelta(hours=4), "created_at": now, "updated_at": now, "progress_pct": 100,
        },
        {
            "id": "seed-task-002", "task_code": "TASK-2026-00002",
            "title": "Unassigned infrastructure audit",
            "description": "Awaiting team lead assignment for datacenter readiness audit.",
            "category": "Infrastructure", "module_name": "Infrastructure", "priority": "High",
            "status": "UNASSIGNED", "created_by_id": admin_id, "evidence_required": False,
            "sla_hours": 72, "sla_status": "NOT_STARTED", "created_at": now, "updated_at": now,
        },
        {
            "id": "seed-task-003", "task_code": "TASK-2026-00003",
            "title": "CPC monthly return validation",
            "description": "Validate Allahabad HC physical tracker entries for current period.",
            "category": "Compliance", "module_name": "Compliance", "priority": "Medium",
            "status": "IN_PROGRESS", "created_by_id": cpc_id, "assigned_team_lead_id": cpc_id,
            "assigned_team_member_id": member_id, "current_owner_id": member_id,
            "evidence_required": True, "sla_hours": 168, "sla_status": "ON_TRACK",
            "sla_started_at": now - timedelta(hours=24), "due_date": now + timedelta(days=5),
            "created_at": now, "updated_at": now, "progress_pct": 45,
        },
        {
            "id": "seed-task-004", "task_code": "TASK-2026-00004",
            "title": "Documentation gap — user manual update",
            "description": "Member proposed task for updating training manual section 4.",
            "category": "Documentation", "priority": "Low", "status": "PROPOSED_BY_MEMBER",
            "created_by_id": member_id, "assigned_team_lead_id": cpc_id, "current_owner_id": cpc_id,
            "source_type": "Member Proposed", "created_at": now, "updated_at": now,
        },
        {
            "id": "seed-task-005", "task_code": "TASK-2026-00005",
            "title": "Closed — firewall rule change",
            "description": "Completed network rule update with evidence.",
            "category": "Infrastructure", "priority": "High", "status": "CLOSED",
            "created_by_id": cpc_id, "assigned_team_lead_id": cpc_id, "assigned_team_member_id": member_id,
            "evidence_required": True, "closed_at": now, "sla_status": "CLOSED_WITHIN_SLA",
            "created_at": now - timedelta(days=10), "updated_at": now, "progress_pct": 100,
        },
        {
            "id": "seed-task-006", "task_code": "TASK-2026-00006",
            "title": "SLA breached — vendor escalation",
            "description": "Vendor response overdue; escalated to manager.",
            "category": "Support", "priority": "Critical", "status": "SLA_BREACHED",
            "created_by_id": admin_id, "assigned_team_lead_id": cpc_id, "assigned_team_member_id": member_id,
            "sla_breached_at": now, "sla_status": "BREACHED", "created_at": now - timedelta(days=3),
            "updated_at": now, "evidence_required": False,
        },
    ]
    await db.tm_tasks.insert_many(samples)
    await db.tm_counters.update_one({"_id": "task_code_2026"}, {"$set": {"seq": 6}}, upsert=True)


async def run_startup(
    db,
    scheduler,
    init_storage_fn: Callable,
    run_weekly_cabinet_brief: Callable,
    now_utc_fn: Callable,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    drain_email_outbox_fn: Optional[Callable] = None,
    register_extra_jobs_fn: Optional[Callable] = None,
):
    await ensure_indexes(db)
    try:
        if init_storage_fn():
            logger.info("Object storage initialised")
    except Exception as e:
        logger.warning("Object storage init skipped: %s", e)

    await seed_master(db)
    await seed_districts(db)
    await seed_users(db, now_utc_fn)
    await migrate_outcome_seed_v2(db, now_utc_fn)
    await backfill_outcome_component_fields(db)
    await fix_outcome_kpi_names(db)
    await seed_baseline(db, now_utc_fn, compute_rag_fn, safe_div_fn)
    await seed_dpr(db, now_utc_fn)
    await seed_pmu_tasks(db, now_utc_fn)
    await seed_tm_tasks(db, now_utc_fn)

    if not scheduler.running:
        scheduler.add_job(
            run_weekly_cabinet_brief,
            CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="Asia/Kolkata"),
            id="weekly_cabinet_brief",
            name="Weekly Cabinet Brief — Mondays 09:00 IST",
            replace_existing=True,
        )
        if drain_email_outbox_fn:
            from email_worker import smtp_configured
            if smtp_configured():
                scheduler.add_job(
                    drain_email_outbox_fn,
                    "interval",
                    minutes=1,
                    id="email_outbox_drain",
                    name="Email outbox drain — every 1 min",
                    replace_existing=True,
                )
                logger.info("Email outbox drain job registered (SMTP configured)")
            else:
                logger.info("Email outbox drain skipped — set SMTP_HOST and SMTP_FROM to enable")
        if register_extra_jobs_fn:
            register_extra_jobs_fn(scheduler)
        scheduler.start()
        logger.info("Scheduler started with %d job(s)", len(scheduler.get_jobs()))

    logger.info("Startup complete.")


def create_lifespan(
    db,
    client,
    scheduler,
    init_storage_fn: Callable,
    run_weekly_cabinet_brief: Callable,
    now_utc_fn: Callable,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    drain_email_outbox_fn: Optional[Callable] = None,
    register_extra_jobs_fn: Optional[Callable] = None,
):
    @asynccontextmanager
    async def lifespan(app):
        await run_startup(
            db, scheduler, init_storage_fn, run_weekly_cabinet_brief,
            now_utc_fn, compute_rag_fn, safe_div_fn, drain_email_outbox_fn, register_extra_jobs_fn,
        )
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)
        client.close()

    return lifespan
