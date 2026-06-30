"""Task Management — core business logic and workflow."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional

from bson import ObjectId
from fastapi import HTTPException

from task_constants import (
    DEFAULT_ASSOCIATED_TEAMS,
    DEFAULT_CATEGORIES,
    DEFAULT_SLA_HOURS,
    EVIDENCE_VERIFICATION,
    PRIORITIES,
    SOURCE_TYPES,
    STATUS_LABELS,
    TASK_STATUSES,
    format_associated_team_label,
)
from task_permissions import (
    can_access_task,
    is_task_admin,
    permissions_for,
    resolve_task_role,
    team_lead_visibility_filter,
)
from task_sla import compute_sla_status, parse_dt, sla_hours_for


async def next_task_code(db) -> str:
    year = datetime.now(timezone.utc).year
    key = f"task_code_{year}"
    doc = await db.tm_counters.find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = doc.get("seq", 1)
    return f"TASK-{year}-{seq:05d}"


async def log_task_audit(
    db,
    task_id: str,
    user: dict,
    action: str,
    old_value: Any = None,
    new_value: Any = None,
    request=None,
):
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
    await db.tm_audit_log.insert_one({
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "action": action,
        "old_value": old_value,
        "new_value": new_value,
        "performed_by_id": user["id"],
        "performed_by_email": user.get("email"),
        "performed_by_role": resolve_task_role(user),
        "performed_at": datetime.now(timezone.utc),
        "ip_address": ip,
        "user_agent": ua,
    })


async def get_user_brief(db, user_id: Optional[str]) -> Optional[dict]:
    if not user_id:
        return None
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
    if not u:
        return None
    return {"id": str(u["_id"]), "name": u.get("name"), "email": u.get("email"), "task_role": resolve_task_role(u)}


def format_work_hours_display(hours) -> str:
    if hours is None:
        return "—"
    try:
        h = int(hours)
        return f"{h}:00"
    except (TypeError, ValueError):
        return "—"


def compute_duration_days(task: dict) -> Optional[int]:
    start = task.get("start_date") or task.get("sla_started_at") or task.get("created_at")
    due = task.get("due_date")
    if isinstance(start, str):
        start = parse_dt(start)
    if isinstance(due, str):
        due = parse_dt(due)
    if not start or not due:
        return None
    try:
        return max(0, (due.date() - start.date()).days)
    except Exception:
        return None


def _task_info_defaults() -> dict:
    return {
        "associated_team": "",
        "start_date": None,
        "billing_type": "None",
        "fund_target_cr": None,
        "hardware_count": None,
        "funds_utilised_cr": None,
        "utilisation_pct": None,
        "fund_allocated_cr": None,
        "funds_released_cr": None,
        "high_court_name": "",
        "component": "",
        "recurrence": "None",
        "reminder": "None",
    }


async def enrich_task(db, task: dict, now: datetime) -> dict:
    task = {k: v for k, v in task.items() if k != "_id"}
    for k, v in _task_info_defaults().items():
        if k not in task:
            task[k] = v
    sla = compute_sla_status(task, now)
    task["sla_status"] = sla["sla_status"]
    task["sla_remaining_hours"] = sla["sla_remaining_hours"]
    task["sla_pct_consumed"] = sla["sla_pct_consumed"]
    task["status_label"] = STATUS_LABELS.get(task.get("status"), task.get("status"))
    ev_count = await db.tm_evidence.count_documents({"task_id": task["id"], "verification_status": {"$ne": "Rejected"}})
    task["evidence_count"] = ev_count
    verified = await db.tm_evidence.count_documents({"task_id": task["id"], "verification_status": "Verified"})
    if not task.get("evidence_required"):
        task["evidence_status"] = "Not Required"
    elif verified > 0:
        task["evidence_status"] = "Verified"
    elif ev_count > 0:
        task["evidence_status"] = "Pending Review"
    else:
        task["evidence_status"] = "Missing"
    task["team_lead"] = await get_user_brief(db, task.get("assigned_team_lead_id"))
    task["team_member"] = await get_user_brief(db, task.get("assigned_team_member_id"))
    task["created_by_user"] = await get_user_brief(db, task.get("created_by_id"))
    task["current_owner"] = await get_user_brief(db, task.get("current_owner_id"))
    task["work_hours_display"] = format_work_hours_display(task.get("sla_hours"))
    task["duration_days"] = compute_duration_days(task)
    if task.get("funds_utilised_cr") is not None and task.get("fund_allocated_cr"):
        try:
            task["utilisation_pct"] = round(
                float(task["funds_utilised_cr"]) / float(task["fund_allocated_cr"]) * 100, 2,
            )
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return task


def _require_access(task, user, db=None):
    """Sync check when task already loaded — use can_access_task async when needed."""
    pass


async def assert_task_access(db, user: dict, task: dict):
    if not await can_access_task(db, user, task):
        raise HTTPException(status_code=403, detail="Not authorized to access this task")


async def assert_not_readonly(task: dict, user: dict):
    if task.get("status") in ("CLOSED", "CANCELLED", "DUPLICATE"):
        perms = permissions_for(user)
        if not perms["canReopen"]:
            raise HTTPException(status_code=400, detail="Task is closed and read-only")


async def record_assignment(
    db, task_id, from_user, to_user_id, to_role, level, remarks=None, status="active",
):
    await db.tm_assignments.insert_one({
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "assigned_from_user_id": from_user["id"] if from_user else None,
        "assigned_from_role": resolve_task_role(from_user) if from_user else None,
        "assigned_to_user_id": to_user_id,
        "assigned_to_role": to_role,
        "assignment_level": level,
        "remarks": remarks,
        "assigned_at": datetime.now(timezone.utc),
        "accepted_at": None,
        "reassigned_at": None,
        "status": status,
    })


async def notify_task(db, notify_fn, emails: list, title: str, body: str, link: str, kind="info"):
    if notify_fn and emails:
        await notify_fn(list(set(emails)), title, body, kind=kind, link=link)


async def create_task(db, user: dict, data: dict, notify_fn=None, request=None) -> dict:
    role = resolve_task_role(user)
    perms = permissions_for(user)
    if not perms["canCreateTask"]:
        raise HTTPException(status_code=403, detail="Cannot create tasks")

    now = datetime.now(timezone.utc)
    task_id = str(uuid.uuid4())
    code = await next_task_code(db)
    priority = data.get("priority") or "Medium"
    if priority not in PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")

    evidence_required = bool(data.get("evidence_required"))
    approval_required = bool(data.get("approval_required", True))
    manager_final = bool(data.get("manager_final_approval_required")) or priority == "Critical"

    status = "DRAFT"
    current_owner_id = user["id"]
    assigned_tl = data.get("assigned_team_lead_id")
    assigned_tm = data.get("assigned_team_member_id")

    source_type = data.get("source_type") or "Manager Assigned"

    if role in ("manager", "admin") or user.get("role") == "Admin":
        if assigned_tl:
            status = "ASSIGNED_TO_TEAM_LEAD"
            current_owner_id = assigned_tl
        elif assigned_tm:
            status = "ASSIGNED_TO_TEAM_MEMBER"
            current_owner_id = assigned_tm
        else:
            status = "UNASSIGNED"
            current_owner_id = None
        source_type = data.get("source_type") or "Manager Assigned"
    elif role == "team_lead":
        if assigned_tm:
            tl_rec = await db.users.find_one({"_id": ObjectId(assigned_tm)})
            if tl_rec and tl_rec.get("team_lead_id") and tl_rec.get("team_lead_id") != user["id"]:
                raise HTTPException(status_code=403, detail="Cannot assign outside your team")
            status = "ASSIGNED_TO_TEAM_MEMBER"
            current_owner_id = assigned_tm
            assigned_tl = user["id"]
        else:
            status = "ASSIGNED_TO_TEAM_LEAD"
            current_owner_id = user["id"]
            assigned_tl = user["id"]
        source_type = data.get("source_type") or "Team Lead Assigned"
    elif role == "team_member":
        status = "PROPOSED_BY_MEMBER"
        tl_id = user.get("team_lead_id")
        if not tl_id:
            tl_user = await db.users.find_one({"task_role": "team_lead"})
            tl_id = str(tl_user["_id"]) if tl_user else None
        assigned_tl = tl_id
        current_owner_id = tl_id
        assigned_tm = None
        source_type = data.get("source_type") or "Member Proposed"
    else:
        raise HTTPException(status_code=403, detail="Role cannot create tasks")

    due_date = data.get("due_date")
    due_dt = parse_dt(due_date) if due_date else None
    sla_h = sla_hours_for(priority, data.get("sla_hours"))

    doc = {
        "id": task_id,
        "task_code": code,
        "title": data["title"].strip(),
        "description": (data.get("description") or "").strip(),
        "category": data.get("category") or DEFAULT_CATEGORIES[0],
        "module_name": data.get("module_name") or "",
        "sub_module_name": data.get("sub_module_name") or "",
        "department_name": data.get("department_name") or "",
        "project_name": data.get("project_name") or "",
        "priority": priority,
        "risk_level": data.get("risk_level") or priority,
        "status": status,
        "source_type": source_type,
        "source_reference_id": data.get("source_reference_id"),
        "created_by_id": user["id"],
        "created_by_email": user.get("email"),
        "created_by_role": role,
        "assigned_team_lead_id": assigned_tl,
        "assigned_team_member_id": assigned_tm,
        "current_owner_id": current_owner_id,
        "current_owner_role": "team_lead" if status.startswith("ASSIGNED_TO_TEAM") else role,
        "due_date": due_dt,
        "sla_hours": sla_h,
        "sla_status": "NOT_STARTED",
        "sla_started_at": now if status not in ("DRAFT", "UNASSIGNED", "PROPOSED_BY_MEMBER") else None,
        "sla_breached_at": None,
        "evidence_required": evidence_required,
        "approval_required": approval_required,
        "manager_final_approval_required": manager_final,
        "parent_task_id": data.get("parent_task_id"),
        "tags": data.get("tags") or [],
        "checklist": data.get("checklist") or [],
        "instructions": data.get("instructions") or "",
        "progress_pct": 0,
        "resolution_summary": "",
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
        "reopened_at": None,
        **_task_info_defaults(),
    }
    for key in (
        "associated_team", "start_date", "billing_type", "fund_target_cr", "hardware_count",
        "funds_utilised_cr", "utilisation_pct", "fund_allocated_cr", "funds_released_cr",
        "high_court_name", "component", "recurrence", "reminder",
    ):
        if data.get(key) is not None:
            doc[key] = data[key]
    if data.get("start_date"):
        doc["start_date"] = parse_dt(data["start_date"])
    elif doc["start_date"] is None and doc.get("sla_started_at"):
        doc["start_date"] = doc["sla_started_at"]

    await db.tm_tasks.insert_one(doc)
    await log_task_audit(db, task_id, user, "task_created", None, {"status": status, "title": doc["title"]}, request)

    if assigned_tl and status == "ASSIGNED_TO_TEAM_LEAD":
        await record_assignment(db, task_id, user, assigned_tl, "team_lead", "team_lead", data.get("assignment_remarks"))
        tl = await get_user_brief(db, assigned_tl)
        if tl and notify_fn:
            await notify_task(db, notify_fn, [tl["email"]], f"Task assigned: {code}", doc["title"], f"/task-management/tasks/{task_id}")

    if assigned_tm and status == "ASSIGNED_TO_TEAM_MEMBER":
        await record_assignment(db, task_id, user, assigned_tm, "team_member", "team_member", data.get("assignment_remarks"))
        tm = await get_user_brief(db, assigned_tm)
        if tm and notify_fn:
            await notify_task(db, notify_fn, [tm["email"]], f"Task assigned: {code}", doc["title"], f"/task-management/tasks/{task_id}")

    return await enrich_task(db, doc, now)


async def update_task_status(
    db, task_id, user, new_status, notify_fn=None, request=None, remarks=None, extra=None,
):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    await assert_not_readonly(task, user)

    old = task.get("status")
    now = datetime.now(timezone.utc)
    upd = {"status": new_status, "updated_at": now, **(extra or {})}
    if new_status == "SLA_BREACHED" and not task.get("sla_breached_at"):
        upd["sla_breached_at"] = now
    if new_status == "CLOSED":
        upd["closed_at"] = now
        sla = compute_sla_status({**task, **upd}, now)
        upd["sla_status"] = sla["sla_status"]
    if new_status in ("IN_PROGRESS", "ACCEPTED") and not task.get("sla_started_at"):
        upd["sla_started_at"] = now

    await db.tm_tasks.update_one({"id": task_id}, {"$set": upd})
    await log_task_audit(db, task_id, user, "status_changed", old, new_status, request)
    if remarks:
        await db.tm_comments.insert_one({
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "user_id": user["id"],
            "user_email": user.get("email"),
            "user_role": resolve_task_role(user),
            "comment_text": remarks,
            "comment_type": "status_change",
            "visibility": "all",
            "created_at": now,
        })
    return await enrich_task(db, {**task, **upd}, now)


async def assign_team_lead(db, task_id, user, team_lead_id, remarks=None, notify_fn=None, request=None):
    perms = permissions_for(user)
    if not perms["canAssignTeamLead"]:
        raise HTTPException(status_code=403, detail="Cannot assign team lead")
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_not_readonly(task, user)
    tl = await db.users.find_one({"_id": ObjectId(team_lead_id)})
    if not tl:
        raise HTTPException(status_code=404, detail="Team lead not found")

    now = datetime.now(timezone.utc)
    upd = {
        "assigned_team_lead_id": team_lead_id,
        "current_owner_id": team_lead_id,
        "current_owner_role": "team_lead",
        "status": "ASSIGNED_TO_TEAM_LEAD",
        "updated_at": now,
        "sla_started_at": task.get("sla_started_at") or now,
    }
    await db.tm_tasks.update_one({"id": task_id}, {"$set": upd})
    await record_assignment(db, task_id, user, team_lead_id, "team_lead", "team_lead", remarks)
    await log_task_audit(db, task_id, user, "assigned_team_lead", task.get("assigned_team_lead_id"), team_lead_id, request)
    if notify_fn and tl.get("email"):
        await notify_task(db, notify_fn, [tl["email"]], f"Task assigned: {task['task_code']}", task["title"], f"/task-management/tasks/{task_id}")
    return await enrich_task(db, {**task, **upd}, now)


async def assign_team_member(db, task_id, user, member_id, remarks=None, notify_fn=None, request=None):
    perms = permissions_for(user)
    if not perms["canAssignTeamMember"]:
        raise HTTPException(status_code=403, detail="Cannot assign team member")
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    await assert_not_readonly(task, user)

    role = resolve_task_role(user)
    member = await db.users.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    if role == "team_lead" and member.get("team_lead_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot assign outside your team")

    now = datetime.now(timezone.utc)
    tl_id = task.get("assigned_team_lead_id") or (user["id"] if role == "team_lead" else None)
    upd = {
        "assigned_team_member_id": member_id,
        "assigned_team_lead_id": tl_id,
        "current_owner_id": member_id,
        "current_owner_role": "team_member",
        "status": "ASSIGNED_TO_TEAM_MEMBER",
        "updated_at": now,
        "sla_started_at": task.get("sla_started_at") or now,
    }
    await db.tm_tasks.update_one({"id": task_id}, {"$set": upd})
    await record_assignment(db, task_id, user, member_id, "team_member", "team_member", remarks)
    await log_task_audit(db, task_id, user, "assigned_team_member", task.get("assigned_team_member_id"), member_id, request)
    if notify_fn and member.get("email"):
        await notify_task(db, notify_fn, [member["email"]], f"Task assigned: {task['task_code']}", task["title"], f"/task-management/tasks/{task_id}")
    return await enrich_task(db, {**task, **upd}, now)


async def accept_proposed(db, task_id, user, notify_fn=None, request=None):
    role = resolve_task_role(user)
    if role != "team_lead" and user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Only team lead can accept proposed tasks")
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task or task.get("status") != "PROPOSED_BY_MEMBER":
        raise HTTPException(status_code=400, detail="Task is not a proposed member task")
    member_id = task.get("created_by_id")
    return await assign_team_member(db, task_id, user, member_id, "Accepted proposed task", notify_fn, request)


async def reject_proposed(db, task_id, user, remarks, request=None):
    role = resolve_task_role(user)
    if role != "team_lead" and user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Only team lead can reject proposed tasks")
    if not remarks:
        raise HTTPException(status_code=400, detail="Rejection remarks required")
    return await update_task_status(db, task_id, user, "REJECTED", request=request, remarks=remarks)


async def accept_task(db, task_id, user, request=None):
    role = resolve_task_role(user)
    if role != "team_member":
        raise HTTPException(status_code=403, detail="Only team members accept tasks")
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task or task.get("assigned_team_member_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Task not assigned to you")
    now = datetime.now(timezone.utc)
    await db.tm_assignments.update_one(
        {"task_id": task_id, "assigned_to_user_id": user["id"], "status": "active"},
        {"$set": {"accepted_at": now}},
    )
    return await update_task_status(db, task_id, user, "ACCEPTED", request=request)


async def start_task(db, task_id, user, request=None):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    if task.get("assigned_team_member_id") != user["id"] and resolve_task_role(user) == "team_member":
        raise HTTPException(status_code=403, detail="Not task owner")
    return await update_task_status(db, task_id, user, "IN_PROGRESS", request=request, extra={"sla_started_at": datetime.now(timezone.utc)})


async def update_progress(db, task_id, user, progress_pct, resolution_summary=None, request=None):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    await assert_not_readonly(task, user)
    if task.get("assigned_team_member_id") != user["id"] and resolve_task_role(user) not in ("team_lead", "manager", "admin"):
        raise HTTPException(status_code=403, detail="Cannot update progress")
    extra = {"progress_pct": max(0, min(100, int(progress_pct)))}
    if resolution_summary is not None:
        extra["resolution_summary"] = resolution_summary
    status = task.get("status")
    if status in ("ACCEPTED", "ASSIGNED_TO_TEAM_MEMBER"):
        extra["status"] = "IN_PROGRESS"
    now = datetime.now(timezone.utc)
    await db.tm_tasks.update_one({"id": task_id}, {"$set": {**extra, "updated_at": now}})
    await log_task_audit(db, task_id, user, "progress_updated", task.get("progress_pct"), extra.get("progress_pct"), request)
    return await enrich_task(db, {**task, **extra, "updated_at": now}, now)


async def mark_blocked(db, task_id, user, reason, request=None):
    return await update_task_status(db, task_id, user, "BLOCKED", request=request, remarks=reason)


async def add_evidence(db, task_id, user, data: dict, request=None):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    await assert_not_readonly(task, user)
    perms = permissions_for(user)
    if not perms["canUploadEvidence"]:
        raise HTTPException(status_code=403, detail="Cannot upload evidence")

    version = await db.tm_evidence.count_documents({"task_id": task_id}) + 1
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "uploaded_by_id": user["id"],
        "uploaded_by_email": user.get("email"),
        "evidence_type": data.get("evidence_type") or "Document",
        "file_id": data.get("file_id"),
        "file_name": data.get("file_name") or "",
        "file_url": data.get("file_url") or "",
        "file_size": data.get("file_size"),
        "mime_type": data.get("mime_type"),
        "description": data.get("description") or "",
        "version": version,
        "verification_status": "Pending Review",
        "verified_by_id": None,
        "verified_at": None,
        "rejection_reason": None,
        "created_at": now,
    }
    await db.tm_evidence.insert_one(doc)
    await log_task_audit(db, task_id, user, "evidence_uploaded", None, {"version": version}, request)
    return doc


async def submit_for_approval(db, task_id, user, notify_fn=None, request=None):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("assigned_team_member_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Only assigned member can submit")
    if task.get("evidence_required"):
        ev = await db.tm_evidence.count_documents({"task_id": task_id})
        if ev == 0:
            raise HTTPException(status_code=400, detail="Evidence required before submission")
    result = await update_task_status(db, task_id, user, "SUBMITTED_FOR_APPROVAL", notify_fn=notify_fn, request=request, extra={"progress_pct": 100})
    tl = await get_user_brief(db, task.get("assigned_team_lead_id"))
    if notify_fn and tl:
        await notify_task(db, notify_fn, [tl["email"]], f"Approval required: {task['task_code']}", task["title"], f"/task-management/tasks/{task_id}")
    return result


async def verify_task(db, task_id, user, decision, remarks=None, checklist=None, notify_fn=None, request=None):
    perms = permissions_for(user)
    if not perms["canVerifyEvidence"]:
        raise HTTPException(status_code=403, detail="Cannot verify")
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("assigned_team_member_id") == user["id"]:
        raise HTTPException(status_code=403, detail="Cannot approve own task")

    now = datetime.now(timezone.utc)
    await db.tm_approvals.insert_one({
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "approval_level": "team_lead",
        "approver_id": user["id"],
        "approver_role": resolve_task_role(user),
        "decision": decision,
        "remarks": remarks,
        "checklist_result": checklist,
        "approved_at": now if decision == "Verified" else None,
        "rejected_at": now if decision in ("Rejected", "Need More Evidence", "Request Clarification") else None,
        "created_at": now,
    })

    if decision == "Verified":
        if task.get("manager_final_approval_required"):
            new_status = "MANAGER_APPROVAL_PENDING"
        else:
            new_status = "CLOSED"
        await db.tm_evidence.update_many({"task_id": task_id, "verification_status": "Pending Review"}, {"$set": {"verification_status": "Verified", "verified_by_id": user["id"], "verified_at": now}})
    elif decision == "Rejected":
        new_status = "REWORK_REQUIRED"
        await db.tm_evidence.update_many({"task_id": task_id, "verification_status": "Pending Review"}, {"$set": {"verification_status": "Rejected", "rejection_reason": remarks}})
    elif decision == "Need More Evidence":
        new_status = "REWORK_REQUIRED"
    else:
        new_status = "CLARIFICATION_REQUIRED"

    if not remarks and decision in ("Rejected", "Need More Evidence"):
        raise HTTPException(status_code=400, detail="Remarks required for rejection")

    result = await update_task_status(db, task_id, user, new_status, notify_fn=notify_fn, request=request, remarks=remarks)
    if new_status == "MANAGER_APPROVAL_PENDING" and notify_fn:
        admins = await db.users.find({"$or": [{"role": "Admin"}, {"task_role": "manager"}]}).to_list(50)
        emails = [a["email"] for a in admins if a.get("email")]
        await notify_task(db, notify_fn, emails, f"Manager approval: {task['task_code']}", task["title"], f"/task-management/tasks/{task_id}")
    return result


async def manager_approve_closure(db, task_id, user, remarks=None, notify_fn=None, request=None):
    perms = permissions_for(user)
    if not perms["canApproveClosure"]:
        raise HTTPException(status_code=403, detail="Manager approval required")
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") != "MANAGER_APPROVAL_PENDING":
        raise HTTPException(status_code=400, detail="Task not pending manager approval")
    now = datetime.now(timezone.utc)
    await db.tm_approvals.insert_one({
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "approval_level": "manager",
        "approver_id": user["id"],
        "approver_role": resolve_task_role(user),
        "decision": "Approved",
        "remarks": remarks,
        "created_at": now,
        "approved_at": now,
    })
    return await update_task_status(db, task_id, user, "CLOSED", notify_fn=notify_fn, request=request)


async def manager_reject_closure(db, task_id, user, remarks, request=None):
    perms = permissions_for(user)
    if not perms["canApproveClosure"]:
        raise HTTPException(status_code=403, detail="Manager approval required")
    if not remarks:
        raise HTTPException(status_code=400, detail="Rejection remarks required")
    now = datetime.now(timezone.utc)
    await db.tm_approvals.insert_one({
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "approval_level": "manager",
        "approver_id": user["id"],
        "approver_role": resolve_task_role(user),
        "decision": "Rejected Closure",
        "remarks": remarks,
        "created_at": now,
        "rejected_at": now,
    })
    return await update_task_status(db, task_id, user, "REWORK_REQUIRED", request=request, remarks=remarks)


async def escalate_task(db, task_id, user, reason, notify_fn=None, request=None):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    result = await update_task_status(db, task_id, user, "ESCALATED", request=request, remarks=reason)
    if notify_fn:
        admins = await db.users.find({"role": "Admin"}).to_list(20)
        emails = [a["email"] for a in admins if a.get("email")]
        await notify_task(db, notify_fn, emails, f"Escalated: {task['task_code']}", reason or task["title"], f"/task-management/tasks/{task_id}")
    return result


async def add_comment(db, task_id, user, text, comment_type="general", visibility="all", request=None):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "user_id": user["id"],
        "user_email": user.get("email"),
        "user_role": resolve_task_role(user),
        "comment_text": text.strip(),
        "comment_type": comment_type,
        "visibility": visibility,
        "created_at": now,
    }
    await db.tm_comments.insert_one(doc)
    await log_task_audit(db, task_id, user, "comment_added", None, {"comment_type": comment_type}, request)
    return doc


async def list_tasks_query(db, user, filters: dict, skip=0, limit=25, sort="-updated_at"):
    role = resolve_task_role(user)
    q = {}
    if role == "team_lead":
        q = await team_lead_visibility_filter(db, user)
    elif role == "team_member":
        q = {
            "$or": [
                {"assigned_team_member_id": user["id"]},
                {"created_by_id": user["id"]},
                {"current_owner_id": user["id"]},
            ]
        }
    elif role == "auditor" and user.get("role") != "Admin":
        pass  # all tasks read-only

    for key, val in filters.items():
        if val is None or val == "":
            continue
        if key == "status":
            q["status"] = val
        elif key == "priority":
            q["priority"] = val
        elif key == "module_name":
            q["module_name"] = val
        elif key == "department_name":
            q["department_name"] = val
        elif key == "project_name":
            q["project_name"] = val
        elif key == "assigned_team_lead_id":
            q["assigned_team_lead_id"] = val
        elif key == "assigned_team_member_id":
            q["assigned_team_member_id"] = val
        elif key == "sla_status":
            q["sla_status"] = val
        elif key == "evidence_required":
            q["evidence_required"] = val.lower() in ("true", "1", "yes")
        elif key == "created_by_id":
            q["created_by_id"] = val
        elif key == "source_type":
            q["source_type"] = val
        elif key == "high_court_name":
            q["high_court_name"] = val
        elif key == "search":
            q["$or"] = [
                {"title": {"$regex": val, "$options": "i"}},
                {"task_code": {"$regex": val, "$options": "i"}},
                {"description": {"$regex": val, "$options": "i"}},
            ]

    sort_field = sort.lstrip("-")
    direction = -1 if sort.startswith("-") else 1
    total = await db.tm_tasks.count_documents(q)
    raw = await db.tm_tasks.find(q).sort(sort_field, direction).skip(skip).limit(limit).to_list(limit)
    now = datetime.now(timezone.utc)
    items = []
    for t in raw:
        items.append(await enrich_task(db, t, now))
    return {"items": items, "total": total, "skip": skip, "limit": limit}


async def dashboard_stats(db, user, scope="manager"):
    now = datetime.now(timezone.utc)
    role = resolve_task_role(user)
    if scope == "manager" or role in ("manager", "admin") or user.get("role") == "Admin":
        base_q = {}
    elif scope == "team_lead" or role == "team_lead":
        base_q = await team_lead_visibility_filter(db, user)
    else:
        base_q = {
            "$or": [
                {"assigned_team_member_id": user["id"]},
                {"created_by_id": user["id"]},
            ]
        }

    async def count(status=None, extra=None):
        q = dict(base_q)
        if status:
            if isinstance(status, list):
                q["status"] = {"$in": status}
            else:
                q["status"] = status
        if extra:
            q.update(extra)
        return await db.tm_tasks.count_documents(q)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return {
        "total": await count(),
        "unassigned": await count("UNASSIGNED"),
        "assigned_team_leads": await count("ASSIGNED_TO_TEAM_LEAD"),
        "in_progress": await count(["IN_PROGRESS", "ACCEPTED"]),
        "submitted_approval": await count("SUBMITTED_FOR_APPROVAL"),
        "sla_breached": await count(["SLA_BREACHED"]) + await count(extra={"sla_status": "BREACHED"}),
        "evidence_pending": await count(extra={"evidence_required": True, "status": {"$nin": ["CLOSED", "CANCELLED"]}}),
        "high_priority_open": await count(extra={"priority": {"$in": ["Critical", "High"]}, "status": {"$nin": ["CLOSED", "CANCELLED", "DUPLICATE"]}}),
        "closed_this_month": await count("CLOSED", {"closed_at": {"$gte": month_start}}),
        "tasks_received": await count(),
        "pending_distribution": await count(["ASSIGNED_TO_TEAM_LEAD", "UNASSIGNED"]),
        "assigned_members": await count("ASSIGNED_TO_TEAM_MEMBER"),
        "rework_required": await count("REWORK_REQUIRED"),
        "sla_risk": await count(extra={"sla_status": "AT_RISK"}),
        "my_open": await count(extra={"status": {"$nin": ["CLOSED", "CANCELLED", "DUPLICATE"]}}),
        "due_today": await count(extra={"due_date": {"$gte": now.replace(hour=0, minute=0, second=0), "$lt": now.replace(hour=23, minute=59, second=59)}}),
        "overdue": await count(extra={"due_date": {"$lt": now}, "status": {"$nin": ["CLOSED", "CANCELLED"]}}),
        "proposed_by_me": await count("PROPOSED_BY_MEMBER", {"created_by_id": user["id"]}),
        "manager_approval_pending": await count("MANAGER_APPROVAL_PENDING"),
        "escalated": await count("ESCALATED"),
        "by_status": await _group_by(db, base_q, "status"),
        "by_priority": await _group_by(db, base_q, "priority"),
        "by_module": await _group_by(db, base_q, "module_name"),
    }


async def _group_by(db, base_q, field):
    pipeline = [{"$match": base_q}, {"$group": {"_id": f"${field}", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    rows = await db.tm_tasks.aggregate(pipeline).to_list(50)
    return [{"key": r["_id"] or "Unknown", "count": r["count"]} for r in rows]


async def get_task_detail(db, task_id, user):
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    now = datetime.now(timezone.utc)
    task = await enrich_task(db, task, now)
    comments = await db.tm_comments.find({"task_id": task_id}).sort("created_at", 1).to_list(500)
    evidence = await db.tm_evidence.find({"task_id": task_id}).sort("version", -1).to_list(100)
    approvals = await db.tm_approvals.find({"task_id": task_id}).sort("created_at", -1).to_list(50)
    assignments = await db.tm_assignments.find({"task_id": task_id}).sort("assigned_at", -1).to_list(50)
    audit = await db.tm_audit_log.find({"task_id": task_id}).sort("performed_at", -1).to_list(200)
    subtasks_raw = await db.tm_tasks.find({"parent_task_id": task_id}).to_list(50)
    subtasks = [await enrich_task(db, st, now) for st in subtasks_raw]
    return {
        "task": task,
        "comments": comments,
        "evidence": evidence,
        "approvals": approvals,
        "assignments": assignments,
        "audit_log": audit,
        "subtasks": subtasks,
    }


async def bulk_assign_team_lead(db, user, task_ids, team_lead_id, remarks=None, notify_fn=None, request=None):
    perms = permissions_for(user)
    if not perms["canAssignTeamLead"]:
        raise HTTPException(status_code=403, detail="Cannot assign team lead")
    succeeded, failed = [], []
    for task_id in task_ids[:100]:
        try:
            await assign_team_lead(db, task_id, user, team_lead_id, remarks, notify_fn, request)
            succeeded.append(task_id)
        except HTTPException as exc:
            failed.append({"task_id": task_id, "detail": exc.detail})
    return {"succeeded": succeeded, "failed": failed, "total": len(task_ids)}


async def bulk_assign_team_member(db, user, task_ids, member_id, remarks=None, notify_fn=None, request=None):
    perms = permissions_for(user)
    if not perms["canAssignTeamMember"]:
        raise HTTPException(status_code=403, detail="Cannot assign team member")
    succeeded, failed = [], []
    for task_id in task_ids[:100]:
        try:
            await assign_team_member(db, task_id, user, member_id, remarks, notify_fn, request)
            succeeded.append(task_id)
        except HTTPException as exc:
            failed.append({"task_id": task_id, "detail": exc.detail})
    return {"succeeded": succeeded, "failed": failed, "total": len(task_ids)}


async def bulk_cancel_tasks(db, user, task_ids, remarks=None, notify_fn=None, request=None):
    perms = permissions_for(user)
    if not perms["canReassignAnyTask"]:
        raise HTTPException(status_code=403, detail="Cannot cancel tasks")
    if not remarks or not remarks.strip():
        raise HTTPException(status_code=400, detail="Cancellation reason required")
    succeeded, failed = [], []
    for task_id in task_ids[:100]:
        try:
            await update_task_status(
                db, task_id, user, "CANCELLED", notify_fn=notify_fn, request=request, remarks=remarks.strip(),
            )
            succeeded.append(task_id)
        except HTTPException as exc:
            failed.append({"task_id": task_id, "detail": exc.detail})
    return {"succeeded": succeeded, "failed": failed, "total": len(task_ids)}


async def update_task_info(db, task_id: str, user: dict, data: dict, request=None) -> dict:
    task = await db.tm_tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_access(db, user, task)
    await assert_not_readonly(task, user)
    perms = permissions_for(user)
    if not (perms["canCreateTask"] or perms["canAssignTeamLead"] or task.get("assigned_team_member_id") == user["id"]):
        raise HTTPException(status_code=403, detail="Cannot update task information")

    allowed = {
        "associated_team", "start_date", "billing_type", "fund_target_cr", "hardware_count",
        "funds_utilised_cr", "utilisation_pct", "fund_allocated_cr", "funds_released_cr",
        "high_court_name", "component", "recurrence", "reminder", "tags", "priority",
        "due_date", "module_name", "project_name", "department_name", "description", "title",
        "current_owner_id",
    }
    patch = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "title" in patch and not str(patch["title"]).strip():
        raise HTTPException(status_code=400, detail="Title required")
    if "priority" in patch and patch["priority"] not in PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")
    if "start_date" in patch:
        patch["start_date"] = parse_dt(patch["start_date"]) if patch["start_date"] else None
    if "due_date" in patch:
        patch["due_date"] = parse_dt(patch["due_date"]) if patch["due_date"] else None
    if "current_owner_id" in data:
        owner_id = (data.get("current_owner_id") or "").strip() or None
        if owner_id:
            try:
                ObjectId(owner_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid owner")
            owner_doc = await db.users.find_one({"_id": ObjectId(owner_id)})
            if not owner_doc:
                raise HTTPException(status_code=400, detail="Owner user not found")
            team_label = patch.get("associated_team") or task.get("associated_team") or ""
            member_ids = await get_team_member_ids_by_label(db, team_label)
            if team_label and owner_id not in member_ids:
                raise HTTPException(status_code=400, detail="Owner must be a member of the associated team")
            patch["current_owner_id"] = owner_id
            patch["current_owner_role"] = resolve_task_role(owner_doc)
        else:
            patch["current_owner_id"] = None
            patch["current_owner_role"] = None
    if not patch:
        now = datetime.now(timezone.utc)
        return await enrich_task(db, task, now)

    patch["updated_at"] = datetime.now(timezone.utc)
    await db.tm_tasks.update_one({"id": task_id}, {"$set": patch})
    await log_task_audit(db, task_id, user, "task_info_updated", None, patch, request)
    updated = await db.tm_tasks.find_one({"id": task_id})
    now = datetime.now(timezone.utc)
    return await enrich_task(db, updated, now)


async def get_assignable_users(db, user, role_filter=None):
    """Users available for assignment dropdowns."""
    role = resolve_task_role(user)
    q = {}
    if role_filter == "team_lead":
        q["$or"] = [{"task_role": "team_lead"}, {"role": "CPC"}, {"role": "Admin"}]
    elif role_filter == "team_member":
        if role == "team_lead":
            q["team_lead_id"] = user["id"]
        else:
            q["$or"] = [{"task_role": "team_member"}, {"team_lead_id": {"$exists": True}}]
    else:
        q = {}
    users = await db.users.find(q, {"password_hash": 0, "totp_secret": 0, "password_history": 0}).to_list(200)
    out = []
    for u in users:
        out.append({
            "id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role"),
            "task_role": resolve_task_role(u),
            "team_lead_id": u.get("team_lead_id"),
        })
    return out


async def get_associated_team_options(db) -> list[dict]:
    """Registered team + department pairs for Associated Team dropdown."""
    from datetime import datetime, timezone
    from team_service import ensure_default_teams

    await ensure_default_teams(db, lambda: datetime.now(timezone.utc))

    cfg = await db.tm_config.find_one({"_id": "default"}) or {}
    entries = cfg.get("associated_teams")
    if not entries:
        await db.tm_config.update_one(
            {"_id": "default"},
            {"$setOnInsert": {"associated_teams": DEFAULT_ASSOCIATED_TEAMS}},
            upsert=True,
        )
        entries = DEFAULT_ASSOCIATED_TEAMS

    team_by_label = {}
    async for tdoc in db.teams.find({}):
        label = format_associated_team_label(tdoc.get("name", ""), tdoc.get("department", ""))
        team_by_label[label] = tdoc

    options = []
    seen = set()
    for entry in entries:
        team = (entry.get("team") or "").strip()
        department = (entry.get("department") or "").strip()
        if not team or not department:
            continue
        label = format_associated_team_label(team, department)
        if label in seen:
            continue
        seen.add(label)
        members = []
        tdoc = team_by_label.get(label)
        for uid in (tdoc.get("member_ids") or []) if tdoc else []:
            brief = await get_user_brief(db, uid)
            if brief:
                members.append(brief)
        options.append({
            "value": label,
            "label": label,
            "team": team,
            "department": department,
            "team_id": str(tdoc["_id"]) if tdoc else None,
            "members": members,
        })
    options.sort(key=lambda o: (o["team"].lower(), o["department"].lower()))
    return options


async def get_team_member_ids_by_label(db, label: str) -> list[str]:
    if not label:
        return []
    parts = label.split(" — ", 1)
    if len(parts) != 2:
        return []
    name, department = parts[0].strip(), parts[1].strip()
    tdoc = await db.teams.find_one({"name": name, "department": department})
    if not tdoc:
        return []
    return list(tdoc.get("member_ids") or [])
