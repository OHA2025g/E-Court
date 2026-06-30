"""Team registry and membership helpers."""
from bson import ObjectId

from task_constants import DEFAULT_ASSOCIATED_TEAMS, format_associated_team_label


async def ensure_default_teams(db, now_utc_fn):
    if await db.teams.count_documents({}) > 0:
        return
    now = now_utc_fn()
    docs = []
    seen = set()
    for entry in DEFAULT_ASSOCIATED_TEAMS:
        team = (entry.get("team") or "").strip()
        department = (entry.get("department") or "").strip()
        if not team or not department:
            continue
        key = (team, department)
        if key in seen:
            continue
        seen.add(key)
        docs.append({
            "name": team,
            "department": department,
            "member_ids": [],
            "team_lead_id": None,
            "created_at": now,
            "updated_at": now,
        })
    if docs:
        await db.teams.insert_many(docs)


async def register_associated_team_label(db, team: str, department: str):
    await db.tm_config.update_one(
        {"_id": "default"},
        {"$addToSet": {"associated_teams": {"team": team, "department": department}}},
        upsert=True,
    )


async def get_user_brief(db, user_id: str | None):
    if not user_id:
        return None
    try:
        doc = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"password_hash": 0, "totp_secret": 0, "password_history": 0},
        )
    except Exception:
        return None
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "email": doc.get("email"),
        "role": doc.get("role"),
        "task_role": doc.get("task_role"),
    }


async def serialize_team(db, team_doc: dict, serialize_fn):
    out = serialize_fn(team_doc)
    member_ids = team_doc.get("member_ids") or []
    members = []
    for uid in member_ids:
        brief = await get_user_brief(db, uid)
        if brief:
            members.append(brief)
    out["members"] = members
    out["member_count"] = len(members)
    lead = await get_user_brief(db, team_doc.get("team_lead_id"))
    out["team_lead"] = lead
    out["label"] = format_associated_team_label(team_doc.get("name", ""), team_doc.get("department", ""))
    return out


async def validate_user_ids(db, user_ids: list[str]) -> list[str]:
    unique = []
    seen = set()
    for uid in user_ids or []:
        uid = (uid or "").strip()
        if not uid or uid in seen:
            continue
        try:
            ObjectId(uid)
        except Exception:
            raise ValueError(f"Invalid user id: {uid}")
        doc = await db.users.find_one({"_id": ObjectId(uid)}, {"_id": 1})
        if not doc:
            raise ValueError(f"User not found: {uid}")
        seen.add(uid)
        unique.append(uid)
    return unique


async def sync_team_membership(db, team_id: str, member_ids: list[str], team_lead_id: str | None, now_utc_fn):
    """Keep user.team_id and team_lead_id aligned with team membership."""
    team_oid = ObjectId(team_id)
    previous = await db.users.find({"team_id": team_id}, {"_id": 1}).to_list(500)
    prev_ids = {str(u["_id"]) for u in previous}
    new_ids = set(member_ids)

    removed = prev_ids - new_ids
    added = new_ids - prev_ids

    for uid in added:
        await db.teams.update_many(
            {"member_ids": uid, "_id": {"$ne": team_oid}},
            {"$pull": {"member_ids": uid}, "$set": {"updated_at": now_utc_fn()}},
        )

    for uid in removed:
        await db.users.update_one(
            {"_id": ObjectId(uid)},
            {"$unset": {"team_id": ""}},
        )

    lead_update = {}
    if team_lead_id:
        lead_update["team_lead_id"] = team_lead_id

    for uid in new_ids:
        update = {"team_id": team_id, **lead_update}
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": update})

    if team_lead_id:
        for uid in new_ids - added:
            await db.users.update_one(
                {"_id": ObjectId(uid), "team_id": team_id},
                {"$set": {"team_lead_id": team_lead_id}},
            )

    await db.teams.update_one(
        {"_id": team_oid},
        {"$set": {"member_ids": member_ids, "team_lead_id": team_lead_id, "updated_at": now_utc_fn()}},
    )


async def remove_user_from_teams(db, user_id: str, now_utc_fn):
    await db.teams.update_many(
        {"member_ids": user_id},
        {"$pull": {"member_ids": user_id}, "$set": {"updated_at": now_utc_fn()}},
    )
    await db.teams.update_many(
        {"team_lead_id": user_id},
        {"$set": {"team_lead_id": None, "updated_at": now_utc_fn()}},
    )
