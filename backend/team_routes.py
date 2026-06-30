"""Admin team registry: create teams and manage member assignments."""
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from team_service import (
    ensure_default_teams,
    register_associated_team_label,
    remove_user_from_teams,
    serialize_team,
    sync_team_membership,
    validate_user_ids,
)


class TeamCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    department: str = Field(min_length=1, max_length=160)
    team_lead_id: Optional[str] = None
    member_ids: List[str] = Field(default_factory=list)


class TeamUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    department: Optional[str] = Field(default=None, min_length=1, max_length=160)
    team_lead_id: Optional[str] = None
    member_ids: Optional[List[str]] = None


class TeamMembersIn(BaseModel):
    user_ids: List[str] = Field(min_length=1)


def register_team_routes(api: APIRouter, db, require_role, audit_fn, serialize_fn, now_utc_fn):
    @api.get("/teams")
    async def list_teams(_: dict = Depends(require_role("Admin"))):
        await ensure_default_teams(db, now_utc_fn)
        docs = await db.teams.find({}).sort([("name", 1), ("department", 1)]).to_list(500)
        out = []
        for doc in docs:
            out.append(await serialize_team(db, doc, serialize_fn))
        return out

    @api.get("/teams/{team_id}")
    async def get_team(team_id: str, _: dict = Depends(require_role("Admin"))):
        doc = await db.teams.find_one({"_id": ObjectId(team_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Team not found")
        return await serialize_team(db, doc, serialize_fn)

    @api.post("/teams")
    async def create_team(body: TeamCreateIn, user: dict = Depends(require_role("Admin"))):
        name = body.name.strip()
        department = body.department.strip()
        if not name or not department:
            raise HTTPException(status_code=400, detail="Team name and department are required")
        if await db.teams.find_one({"name": name, "department": department}):
            raise HTTPException(status_code=400, detail="Team with this name and department already exists")

        try:
            member_ids = await validate_user_ids(db, body.member_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        team_lead_id = (body.team_lead_id or "").strip() or None
        if team_lead_id:
            try:
                await validate_user_ids(db, [team_lead_id])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if team_lead_id not in member_ids:
                member_ids.append(team_lead_id)

        now = now_utc_fn()
        doc = {
            "name": name,
            "department": department,
            "member_ids": member_ids,
            "team_lead_id": team_lead_id,
            "created_at": now,
            "updated_at": now,
            "created_by": user.get("email"),
        }
        result = await db.teams.insert_one(doc)
        team_id = str(result.inserted_id)
        await sync_team_membership(db, team_id, member_ids, team_lead_id, now_utc_fn)
        await register_associated_team_label(db, name, department)
        await audit_fn(
            user,
            "teams",
            "create",
            team_id,
            [{"field": "team", "old": None, "new": {"name": name, "department": department, "members": len(member_ids)}}],
        )
        created = await db.teams.find_one({"_id": result.inserted_id})
        return await serialize_team(db, created, serialize_fn)

    @api.put("/teams/{team_id}")
    async def update_team(team_id: str, body: TeamUpdateIn, user: dict = Depends(require_role("Admin"))):
        existing = await db.teams.find_one({"_id": ObjectId(team_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Team not found")

        name = body.name.strip() if body.name is not None else existing.get("name", "")
        department = body.department.strip() if body.department is not None else existing.get("department", "")
        if not name or not department:
            raise HTTPException(status_code=400, detail="Team name and department are required")

        duplicate = await db.teams.find_one({
            "name": name,
            "department": department,
            "_id": {"$ne": ObjectId(team_id)},
        })
        if duplicate:
            raise HTTPException(status_code=400, detail="Team with this name and department already exists")

        member_ids = existing.get("member_ids") or []
        if body.member_ids is not None:
            try:
                member_ids = await validate_user_ids(db, body.member_ids)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        team_lead_id = existing.get("team_lead_id")
        if body.team_lead_id is not None:
            team_lead_id = body.team_lead_id.strip() or None
        if team_lead_id:
            try:
                await validate_user_ids(db, [team_lead_id])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if team_lead_id not in member_ids:
                member_ids.append(team_lead_id)

        await sync_team_membership(db, team_id, member_ids, team_lead_id, now_utc_fn)
        await db.teams.update_one(
            {"_id": ObjectId(team_id)},
            {"$set": {"name": name, "department": department, "updated_at": now_utc_fn()}},
        )
        await register_associated_team_label(db, name, department)
        await audit_fn(
            user,
            "teams",
            "update",
            team_id,
            [{
                "field": "team",
                "old": {"name": existing.get("name"), "department": existing.get("department")},
                "new": {"name": name, "department": department, "members": len(member_ids)},
            }],
        )
        updated = await db.teams.find_one({"_id": ObjectId(team_id)})
        return await serialize_team(db, updated, serialize_fn)

    @api.delete("/teams/{team_id}")
    async def delete_team(team_id: str, user: dict = Depends(require_role("Admin"))):
        existing = await db.teams.find_one({"_id": ObjectId(team_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Team not found")

        for uid in existing.get("member_ids") or []:
            await db.users.update_one(
                {"_id": ObjectId(uid), "team_id": team_id},
                {"$unset": {"team_id": ""}},
            )
        await db.teams.delete_one({"_id": ObjectId(team_id)})
        await audit_fn(user, "teams", "delete", team_id, [])
        return {"ok": True}

    @api.post("/teams/{team_id}/members")
    async def add_team_members(team_id: str, body: TeamMembersIn, user: dict = Depends(require_role("Admin"))):
        existing = await db.teams.find_one({"_id": ObjectId(team_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Team not found")
        try:
            new_ids = await validate_user_ids(db, body.user_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        member_ids = list(dict.fromkeys((existing.get("member_ids") or []) + new_ids))
        team_lead_id = existing.get("team_lead_id")
        await sync_team_membership(db, team_id, member_ids, team_lead_id, now_utc_fn)
        await audit_fn(
            user,
            "teams",
            "add_members",
            team_id,
            [{"field": "member_ids", "old": existing.get("member_ids"), "new": member_ids}],
        )
        updated = await db.teams.find_one({"_id": ObjectId(team_id)})
        return await serialize_team(db, updated, serialize_fn)

    @api.delete("/teams/{team_id}/members/{user_id}")
    async def remove_team_member(team_id: str, user_id: str, user: dict = Depends(require_role("Admin"))):
        existing = await db.teams.find_one({"_id": ObjectId(team_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Team not found")

        member_ids = [uid for uid in (existing.get("member_ids") or []) if uid != user_id]
        team_lead_id = existing.get("team_lead_id")
        if team_lead_id == user_id:
            team_lead_id = None
        await sync_team_membership(db, team_id, member_ids, team_lead_id, now_utc_fn)
        await audit_fn(
            user,
            "teams",
            "remove_member",
            team_id,
            [{"field": "member_ids", "old": existing.get("member_ids"), "new": member_ids}],
        )
        updated = await db.teams.find_one({"_id": ObjectId(team_id)})
        return await serialize_team(db, updated, serialize_fn)
