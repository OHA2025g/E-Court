"""Task Management — HTTP API routes."""
import io
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from task_constants import DEFAULT_CATEGORIES, DEFAULT_SLA_HOURS, EVIDENCE_TYPES, PRIORITIES, SOURCE_TYPES, STATUS_LABELS
from task_export import export_tasks_csv, export_tasks_pdf, export_tasks_xlsx
from task_permissions import permissions_for, resolve_task_role
from task_service import (
    accept_proposed,
    accept_task,
    add_comment,
    add_evidence,
    assign_team_lead,
    assign_team_member,
    bulk_assign_team_lead,
    bulk_assign_team_member,
    bulk_cancel_tasks,
    create_task,
    dashboard_stats,
    get_assignable_users,
    get_associated_team_options,
    get_task_detail,
    list_tasks_query,
    manager_approve_closure,
    manager_reject_closure,
    mark_blocked,
    reject_proposed,
    start_task,
    submit_for_approval,
    update_progress,
    update_task_info,
    verify_task,
    escalate_task,
)
from seed_constants import COMPONENTS, HIGH_COURTS


class TaskCreateIn(BaseModel):
    title: str
    description: Optional[str] = ""
    category: Optional[str] = None
    module_name: Optional[str] = ""
    sub_module_name: Optional[str] = ""
    department_name: Optional[str] = ""
    project_name: Optional[str] = ""
    priority: Literal["Critical", "High", "Medium", "Low"] = "Medium"
    risk_level: Optional[str] = None
    due_date: Optional[str] = None
    sla_hours: Optional[int] = None
    evidence_required: bool = False
    approval_required: bool = True
    manager_final_approval_required: bool = False
    assigned_team_lead_id: Optional[str] = None
    assigned_team_member_id: Optional[str] = None
    source_type: Optional[str] = None
    source_reference_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    tags: Optional[List[str]] = None
    checklist: Optional[list] = None
    instructions: Optional[str] = ""
    assignment_remarks: Optional[str] = None
    associated_team: Optional[str] = None
    start_date: Optional[str] = None
    billing_type: Optional[str] = None
    fund_target_cr: Optional[float] = None
    hardware_count: Optional[int] = None
    funds_utilised_cr: Optional[float] = None
    utilisation_pct: Optional[float] = None
    fund_allocated_cr: Optional[float] = None
    funds_released_cr: Optional[float] = None
    high_court_name: Optional[str] = None
    component: Optional[str] = None
    recurrence: Optional[str] = None
    reminder: Optional[str] = None


class TaskInfoUpdateIn(BaseModel):
    associated_team: Optional[str] = None
    start_date: Optional[str] = None
    billing_type: Optional[str] = None
    fund_target_cr: Optional[float] = None
    hardware_count: Optional[int] = None
    funds_utilised_cr: Optional[float] = None
    utilisation_pct: Optional[float] = None
    fund_allocated_cr: Optional[float] = None
    funds_released_cr: Optional[float] = None
    high_court_name: Optional[str] = None
    component: Optional[str] = None
    recurrence: Optional[str] = None
    reminder: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[Literal["Critical", "High", "Medium", "Low"]] = None
    due_date: Optional[str] = None
    module_name: Optional[str] = None
    project_name: Optional[str] = None
    department_name: Optional[str] = None
    description: Optional[str] = None
    title: Optional[str] = None
    current_owner_id: Optional[str] = None


class AssignIn(BaseModel):
    user_id: str
    remarks: Optional[str] = None


class ProgressIn(BaseModel):
    progress_pct: int = Field(ge=0, le=100)
    resolution_summary: Optional[str] = None


class BlockIn(BaseModel):
    reason: str


class VerifyIn(BaseModel):
    decision: Literal["Verified", "Rejected", "Need More Evidence", "Request Clarification"]
    remarks: Optional[str] = None
    checklist: Optional[dict] = None


class RemarksIn(BaseModel):
    remarks: str


class CommentIn(BaseModel):
    comment_text: str
    comment_type: Optional[str] = "general"


class EvidenceIn(BaseModel):
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    evidence_type: Optional[str] = "Document"
    description: Optional[str] = ""


class SlaRuleIn(BaseModel):
    priority: str
    sla_hours: int


class CategoryIn(BaseModel):
    name: str


class AssociatedTeamIn(BaseModel):
    team: str
    department: str


class BulkAssignIn(BaseModel):
    task_ids: List[str] = Field(min_length=1, max_length=100)
    user_id: str
    remarks: Optional[str] = None


class BulkCancelIn(BaseModel):
    task_ids: List[str] = Field(min_length=1, max_length=100)
    remarks: str


def register_task_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    require_role,
    serialize_fn,
    notify_fn,
):
    @api.get("/tasks/meta")
    async def tasks_meta(user: dict = Depends(require_fully_authenticated)):
        associated_teams = await get_associated_team_options(db)
        return {
            "permissions": permissions_for(user),
            "task_role": resolve_task_role(user),
            "statuses": STATUS_LABELS,
            "priorities": PRIORITIES,
            "evidence_types": EVIDENCE_TYPES,
            "source_types": SOURCE_TYPES,
            "default_sla_hours": DEFAULT_SLA_HOURS,
            "categories": DEFAULT_CATEGORIES,
            "high_courts": HIGH_COURTS,
            "components": [c["name"] for c in COMPONENTS],
            "billing_types": ["None", "Billable", "Non-Billable", "Fixed Price", "Time & Material"],
            "recurrence_options": ["None", "Daily", "Weekly", "Monthly", "Quarterly", "Yearly"],
            "associated_teams": associated_teams,
        }

    @api.get("/tasks/config")
    async def get_config(_: dict = Depends(require_role("Admin"))):
        cfg = await db.tm_config.find_one({"_id": "default"}) or {}
        return serialize_fn(cfg) if cfg else {"categories": DEFAULT_CATEGORIES, "sla_rules": DEFAULT_SLA_HOURS}

    @api.post("/tasks/config/categories")
    async def add_category(body: CategoryIn, _: dict = Depends(require_role("Admin"))):
        await db.tm_config.update_one(
            {"_id": "default"},
            {"$addToSet": {"categories": body.name}},
            upsert=True,
        )
        return {"ok": True}

    @api.post("/tasks/config/associated-teams")
    async def add_associated_team(body: AssociatedTeamIn, _: dict = Depends(require_role("Admin"))):
        team = body.team.strip()
        department = body.department.strip()
        if not team or not department:
            raise HTTPException(status_code=400, detail="Team and department are required")
        entry = {"team": team, "department": department}
        await db.tm_config.update_one(
            {"_id": "default"},
            {"$addToSet": {"associated_teams": entry}},
            upsert=True,
        )
        return {"ok": True, "entry": entry}

    @api.post("/tasks/config/sla-rules")
    async def set_sla_rule(body: SlaRuleIn, _: dict = Depends(require_role("Admin"))):
        await db.tm_config.update_one(
            {"_id": "default"},
            {"$set": {f"sla_rules.{body.priority}": body.sla_hours}},
            upsert=True,
        )
        return {"ok": True}

    @api.get("/tasks/manager/dashboard")
    async def manager_dashboard(user: dict = Depends(require_fully_authenticated)):
        role = resolve_task_role(user)
        if role not in ("manager", "admin") and user.get("role") != "Admin":
            raise HTTPException(status_code=403, detail="Manager access required")
        stats = await dashboard_stats(db, user, "manager")
        pending = await list_tasks_query(db, user, {"status": "MANAGER_APPROVAL_PENDING"}, limit=10)
        unassigned = await list_tasks_query(db, user, {"status": "UNASSIGNED"}, limit=10)
        escalated = await list_tasks_query(db, user, {"status": "ESCALATED"}, limit=10)
        return serialize_fn({"stats": stats, "pending_approval": pending["items"], "unassigned": unassigned["items"], "escalated": escalated["items"]})

    @api.get("/tasks/team-lead/dashboard")
    async def team_lead_dashboard(user: dict = Depends(require_fully_authenticated)):
        role = resolve_task_role(user)
        if role not in ("team_lead", "manager", "admin") and user.get("role") not in ("Admin", "CPC"):
            raise HTTPException(status_code=403, detail="Team lead access required")
        stats = await dashboard_stats(db, user, "team_lead")
        submitted = await list_tasks_query(db, user, {"status": "SUBMITTED_FOR_APPROVAL"}, limit=10)
        proposed = await list_tasks_query(db, user, {"status": "PROPOSED_BY_MEMBER"}, limit=10)
        return serialize_fn({"stats": stats, "submitted": submitted["items"], "proposed": proposed["items"]})

    @api.get("/tasks/my/dashboard")
    async def member_dashboard(user: dict = Depends(require_fully_authenticated)):
        stats = await dashboard_stats(db, user, "member")
        mine = await list_tasks_query(db, user, {}, limit=10)
        return serialize_fn({"stats": stats, "recent": mine["items"]})

    @api.get("/tasks/manager/all")
    async def manager_all(
        user: dict = Depends(require_fully_authenticated),
        skip: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=200),
        status: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
    ):
        role = resolve_task_role(user)
        if role not in ("manager", "admin", "auditor") and user.get("role") != "Admin":
            raise HTTPException(status_code=403, detail="Not authorized")
        filters = {"status": status, "priority": priority, "search": search}
        return await list_tasks_query(db, user, filters, skip, limit)

    @api.get("/tasks/unassigned")
    async def unassigned_tasks(user: dict = Depends(require_fully_authenticated)):
        role = resolve_task_role(user)
        if role not in ("manager", "admin") and user.get("role") != "Admin":
            raise HTTPException(status_code=403, detail="Manager access required")
        return await list_tasks_query(db, user, {"status": "UNASSIGNED"}, limit=100)

    @api.get("/tasks/team-lead/assigned")
    async def team_lead_assigned(user: dict = Depends(require_fully_authenticated)):
        return await list_tasks_query(db, user, {}, limit=100)

    @api.get("/tasks/my")
    async def my_tasks(
        user: dict = Depends(require_fully_authenticated),
        skip: int = 0,
        limit: int = 25,
        status: Optional[str] = None,
    ):
        return await list_tasks_query(db, user, {"status": status}, skip, limit)

    @api.get("/tasks")
    async def list_tasks(
        user: dict = Depends(require_fully_authenticated),
        skip: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=200),
        status: Optional[str] = None,
        priority: Optional[str] = None,
        module_name: Optional[str] = None,
        department_name: Optional[str] = None,
        project_name: Optional[str] = None,
        assigned_team_lead_id: Optional[str] = None,
        assigned_team_member_id: Optional[str] = None,
        sla_status: Optional[str] = None,
        evidence_required: Optional[str] = None,
        created_by_id: Optional[str] = None,
        source_type: Optional[str] = None,
        high_court_name: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = "-updated_at",
    ):
        filters = {
            "status": status, "priority": priority, "module_name": module_name,
            "department_name": department_name, "project_name": project_name,
            "assigned_team_lead_id": assigned_team_lead_id,
            "assigned_team_member_id": assigned_team_member_id,
            "sla_status": sla_status, "evidence_required": evidence_required,
            "created_by_id": created_by_id, "source_type": source_type,
            "high_court_name": high_court_name, "search": search,
        }
        return serialize_fn(await list_tasks_query(db, user, filters, skip, limit, sort))

    @api.get("/tasks/filter")
    async def filter_tasks(
        user: dict = Depends(require_fully_authenticated),
        skip: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=200),
        status: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
    ):
        return serialize_fn(await list_tasks_query(db, user, {"status": status, "priority": priority, "search": search}, skip, limit))

    @api.get("/tasks/export")
    async def export_tasks(
        user: dict = Depends(require_fully_authenticated),
        format: Literal["csv", "xlsx", "pdf"] = Query("csv"),
        status: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        module_name: Optional[str] = None,
    ):
        filters = {
            "status": status,
            "priority": priority,
            "search": search,
            "module_name": module_name,
        }
        if format == "xlsx":
            data = await export_tasks_xlsx(db, user, filters)
            return StreamingResponse(
                io.BytesIO(data),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=tasks_export.xlsx"},
            )
        if format == "pdf":
            data = await export_tasks_pdf(db, user, filters)
            return StreamingResponse(
                io.BytesIO(data),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=tasks_export.pdf"},
            )
        csv_data = await export_tasks_csv(db, user, filters)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tasks_export.csv"},
        )

    @api.get("/tasks/assignable-users")
    async def assignable_users(
        user: dict = Depends(require_fully_authenticated),
        role: Optional[str] = Query(None),
    ):
        return await get_assignable_users(db, user, role)

    @api.get("/tasks/reports/summary")
    async def report_summary(user: dict = Depends(require_fully_authenticated)):
        return serialize_fn(await dashboard_stats(db, user, resolve_task_role(user)))

    @api.post("/tasks")
    async def post_task(body: TaskCreateIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await create_task(db, user, body.model_dump(), notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/bulk/assign-team-lead")
    async def bulk_assign_lead(
        body: BulkAssignIn,
        request: Request,
        user: dict = Depends(require_fully_authenticated),
    ):
        return serialize_fn(await bulk_assign_team_lead(
            db, user, body.task_ids, body.user_id, body.remarks, notify_fn, request,
        ))

    @api.post("/tasks/bulk/assign-member")
    async def bulk_assign_member(
        body: BulkAssignIn,
        request: Request,
        user: dict = Depends(require_fully_authenticated),
    ):
        return serialize_fn(await bulk_assign_team_member(
            db, user, body.task_ids, body.user_id, body.remarks, notify_fn, request,
        ))

    @api.post("/tasks/bulk/cancel")
    async def bulk_cancel(
        body: BulkCancelIn,
        request: Request,
        user: dict = Depends(require_fully_authenticated),
    ):
        return serialize_fn(await bulk_cancel_tasks(
            db, user, body.task_ids, body.remarks, notify_fn, request,
        ))

    @api.get("/tasks/{task_id}")
    async def get_task(task_id: str, user: dict = Depends(require_fully_authenticated)):
        detail = await get_task_detail(db, task_id, user)
        return serialize_fn(detail)

    @api.patch("/tasks/{task_id}/info")
    async def patch_task_info(
        task_id: str,
        body: TaskInfoUpdateIn,
        request: Request,
        user: dict = Depends(require_fully_authenticated),
    ):
        task = await update_task_info(db, task_id, user, body.model_dump(exclude_unset=True), request=request)
        return serialize_fn(task)

    @api.get("/tasks/{task_id}/comments")
    async def get_comments(task_id: str, user: dict = Depends(require_fully_authenticated)):
        await get_task_detail(db, task_id, user)
        items = await db.tm_comments.find({"task_id": task_id}).sort("created_at", 1).to_list(500)
        return serialize_fn(items)

    @api.post("/tasks/{task_id}/comments")
    async def post_comment(task_id: str, body: CommentIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        doc = await add_comment(db, task_id, user, body.comment_text, body.comment_type, request=request)
        return serialize_fn(doc)

    @api.get("/tasks/{task_id}/audit-log")
    async def get_audit(task_id: str, user: dict = Depends(require_fully_authenticated)):
        detail = await get_task_detail(db, task_id, user)
        perms = permissions_for(user)
        if not perms["canViewAuditAndEvidence"]:
            raise HTTPException(status_code=403, detail="Audit access denied")
        return serialize_fn(detail["audit_log"])

    @api.post("/tasks/{task_id}/assign-team-lead")
    async def post_assign_tl(task_id: str, body: AssignIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await assign_team_lead(db, task_id, user, body.user_id, body.remarks, notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/assign-member")
    async def post_assign_member(task_id: str, body: AssignIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await assign_team_member(db, task_id, user, body.user_id, body.remarks, notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/reassign")
    async def reassign_tl(task_id: str, body: AssignIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        return await post_assign_tl(task_id, body, request, user)

    @api.post("/tasks/{task_id}/reassign-member")
    async def reassign_member(task_id: str, body: AssignIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        return await post_assign_member(task_id, body, request, user)

    @api.post("/tasks/{task_id}/accept-proposed")
    async def accept_prop(task_id: str, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await accept_proposed(db, task_id, user, notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/reject-proposed")
    async def reject_prop(task_id: str, body: RemarksIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await reject_proposed(db, task_id, user, body.remarks, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/accept")
    async def post_accept(task_id: str, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await accept_task(db, task_id, user, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/start")
    async def post_start(task_id: str, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await start_task(db, task_id, user, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/update-progress")
    async def post_progress(task_id: str, body: ProgressIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await update_progress(db, task_id, user, body.progress_pct, body.resolution_summary, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/mark-blocked")
    async def post_blocked(task_id: str, body: BlockIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await mark_blocked(db, task_id, user, body.reason, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/upload-evidence")
    async def post_evidence(task_id: str, body: EvidenceIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        doc = await add_evidence(db, task_id, user, body.model_dump(), request)
        return serialize_fn(doc)

    @api.post("/tasks/{task_id}/submit-approval")
    async def post_submit(task_id: str, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await submit_for_approval(db, task_id, user, notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/verify")
    async def post_verify(task_id: str, body: VerifyIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await verify_task(db, task_id, user, body.decision, body.remarks, body.checklist, notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/reject")
    async def post_reject(task_id: str, body: VerifyIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        body.decision = "Rejected"
        return await post_verify(task_id, body, request, user)

    @api.post("/tasks/{task_id}/request-clarification")
    async def post_clarify(task_id: str, body: RemarksIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        v = VerifyIn(decision="Request Clarification", remarks=body.remarks)
        return await post_verify(task_id, v, request, user)

    @api.post("/tasks/{task_id}/approve-closure")
    async def post_approve_closure(task_id: str, body: RemarksIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await manager_approve_closure(db, task_id, user, body.remarks, notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/reject-closure")
    async def post_reject_closure(task_id: str, body: RemarksIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await manager_reject_closure(db, task_id, user, body.remarks, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/escalate")
    async def post_escalate(task_id: str, body: BlockIn, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await escalate_task(db, task_id, user, body.reason, notify_fn, request)
        return serialize_fn(task)

    @api.post("/tasks/{task_id}/respond-rework")
    async def respond_rework(task_id: str, request: Request, user: dict = Depends(require_fully_authenticated)):
        task = await start_task(db, task_id, user, request)
        return serialize_fn(task)

    @api.get("/tasks/{task_id}/evidence-pack")
    async def evidence_pack(task_id: str, user: dict = Depends(require_fully_authenticated)):
        detail = await get_task_detail(db, task_id, user)
        return serialize_fn({"task": detail["task"], "evidence": detail["evidence"], "comments": detail["comments"]})
