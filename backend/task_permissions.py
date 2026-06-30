"""Task Management — role resolution and permission checks."""
from typing import Optional

from task_constants import READONLY_STATUSES

PMIS_ROLE_DEFAULT_TASK_ROLE = {
    "Admin": "manager",
    "CPC": "team_lead",
    "Viewer": "auditor",
}


def resolve_task_role(user: dict) -> str:
    """Map PMIS user to task-management role."""
    explicit = (user.get("task_role") or "").strip().lower()
    if explicit in ("manager", "team_lead", "team_member", "auditor", "admin"):
        return explicit
    pmis = user.get("role", "")
    if pmis == "Admin":
        return "manager"
    return PMIS_ROLE_DEFAULT_TASK_ROLE.get(pmis, "team_member")


def is_task_admin(user: dict) -> bool:
    return user.get("role") == "Admin" or resolve_task_role(user) in ("admin", "manager")


def permissions_for(user: dict) -> dict:
    role = resolve_task_role(user)
    pmis_admin = user.get("role") == "Admin"
    return {
        "task_role": role,
        "canViewAllTasks": role in ("manager", "admin") or pmis_admin,
        "canCreateTask": role in ("manager", "team_lead", "team_member", "admin") or pmis_admin,
        "canAssignTeamLead": role in ("manager", "admin") or pmis_admin,
        "canAssignTeamMember": role in ("manager", "team_lead", "admin") or pmis_admin,
        "canReassignAnyTask": role in ("manager", "admin") or pmis_admin,
        "canVerifyEvidence": role in ("team_lead", "manager", "admin") or pmis_admin,
        "canApproveClosure": role in ("manager", "admin") or pmis_admin,
        "canRejectResolution": role in ("team_lead", "manager", "admin") or pmis_admin,
        "canEscalateTask": role in ("team_lead", "team_member", "manager", "admin"),
        "canViewAuditAndEvidence": role in ("manager", "team_lead", "auditor", "admin") or pmis_admin,
        "canManageConfig": pmis_admin,
        "canReadOnly": role == "auditor" and not pmis_admin,
        "canAcceptTask": role == "team_member",
        "canUpdateProgress": role == "team_member",
        "canUploadEvidence": role in ("team_member", "team_lead", "manager", "admin"),
        "canSubmitForApproval": role == "team_member",
        "canReopen": role in ("manager", "admin") or pmis_admin,
    }


def visibility_filter(user: dict) -> dict:
    """MongoDB filter fragment for tasks visible to user."""
    role = resolve_task_role(user)
    uid = user["id"]
    if role in ("manager", "admin") or user.get("role") == "Admin":
        return {}
    if role == "auditor":
        return {}
    if role == "team_lead":
        return {
            "$or": [
                {"assigned_team_lead_id": uid},
                {"created_by_id": uid},
                {"current_owner_id": uid},
                {"assigned_team_member_id": {"$in": [None, ""]}},  # noqa — handled below
            ]
        }
    # team_member
    return {
        "$or": [
            {"assigned_team_member_id": uid},
            {"created_by_id": uid},
            {"current_owner_id": uid},
        ]
    }


async def team_lead_visibility_filter(db, user: dict) -> dict:
    """Team lead sees own tasks + tasks assigned to their team members."""
    uid = user["id"]
    members = await db.users.find({"team_lead_id": uid}, {"_id": 1}).to_list(500)
    member_ids = [str(m["_id"]) for m in members]
    clauses = [
        {"assigned_team_lead_id": uid},
        {"created_by_id": uid},
        {"current_owner_id": uid},
    ]
    if member_ids:
        clauses.append({"assigned_team_member_id": {"$in": member_ids}})
    return {"$or": clauses}


async def can_access_task(db, user: dict, task: dict) -> bool:
    if not task:
        return False
    role = resolve_task_role(user)
    if role in ("manager", "admin", "auditor") or user.get("role") == "Admin":
        return True
    uid = user["id"]
    if task.get("assigned_team_lead_id") == uid:
        return True
    if task.get("assigned_team_member_id") == uid:
        return True
    if task.get("created_by_id") == uid:
        return True
    if task.get("current_owner_id") == uid:
        return True
    if role == "team_lead":
        member_id = task.get("assigned_team_member_id")
        if member_id:
            m = await db.users.find_one({"_id": __import__("bson").ObjectId(member_id)})
            if m and m.get("team_lead_id") == uid:
                return True
    return False


def task_is_readonly(task: dict, user: dict) -> bool:
    perms = permissions_for(user)
    if perms["canReopen"]:
        return False
    return task.get("status") in READONLY_STATUSES
