"""Admin backup and restore routes."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel


BACKUP_COLLECTIONS = [
    "users", "high_courts", "components", "indicators", "outcome_subjects",
    "kpis", "reporting_periods", "districts", "settings",
    "physical_entries", "financial_entries", "outcome_entries",
    "pmu_tasks", "dpr_deliverables",
]


class RestoreRequest(BaseModel):
    collections: dict
    mode: Literal["merge", "replace"] = "merge"


def register_admin_routes(
    api: APIRouter,
    db,
    require_role,
    audit_fn,
    serialize_fn,
    now_utc_fn,
):
    @api.get("/admin/backup")
    async def admin_backup(user: dict = Depends(require_role("Admin"))):
        out = {
            "version": 1,
            "exported_at": now_utc_fn().isoformat(),
            "exported_by": user["email"],
            "collections": {},
        }
        for coll in BACKUP_COLLECTIONS:
            if coll == "users":
                docs = await db[coll].find({}, {"password_hash": 0, "totp_secret": 0}).to_list(10000)
            else:
                docs = await db[coll].find({}).to_list(50000)
            out["collections"][coll] = serialize_fn(docs)
        out["count"] = {k: len(v) for k, v in out["collections"].items()}
        return Response(
            content=json.dumps(out, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename=pmis-backup-{now_utc_fn().strftime("%Y%m%d-%H%M%S")}.json'},
        )

    @api.post("/admin/restore")
    async def admin_restore(body: RestoreRequest, user: dict = Depends(require_role("Admin"))):
        safe = set(BACKUP_COLLECTIONS) - {"users", "settings"}
        result = {}
        for coll, rows in body.collections.items():
            if coll not in safe or not isinstance(rows, list):
                result[coll] = "skipped (not a safe collection)"
                continue
            if body.mode == "replace":
                await db[coll].delete_many({})
            inserted = 0
            updated = 0
            for r in rows:
                if not isinstance(r, dict):
                    continue
                r.pop("id", None)
                r.pop("_id", None)
                key = None
                if coll == "high_courts":
                    key = {"name": r.get("name")}
                elif coll == "components":
                    key = {"code": r.get("code")}
                elif coll == "indicators":
                    key = {"component": r.get("component"), "indicator": r.get("indicator")}
                elif coll == "kpis":
                    key = {"subject": r.get("subject"), "kpi_id": r.get("kpi_id")}
                elif coll == "outcome_subjects":
                    key = {"name": r.get("name")}
                elif coll == "reporting_periods":
                    key = {"period": r.get("period")}
                elif coll == "districts":
                    key = {"high_court": r.get("high_court"), "name": r.get("name")}
                elif coll == "physical_entries":
                    key = {
                        "high_court": r.get("high_court"),
                        "component": r.get("component"),
                        "indicator": r.get("indicator"),
                        "reporting_period": r.get("reporting_period"),
                    }
                elif coll == "financial_entries":
                    key = {
                        "high_court": r.get("high_court"),
                        "component": r.get("component"),
                        "reporting_period": r.get("reporting_period"),
                    }
                elif coll == "outcome_entries":
                    key = {
                        "high_court": r.get("high_court"),
                        "subject": r.get("subject"),
                        "kpi_id": r.get("kpi_id"),
                        "reporting_period": r.get("reporting_period"),
                    }
                if key and body.mode == "merge":
                    res = await db[coll].update_one(key, {"$set": r}, upsert=True)
                    if res.upserted_id:
                        inserted += 1
                    else:
                        updated += res.modified_count
                else:
                    await db[coll].insert_one(r)
                    inserted += 1
            result[coll] = {"inserted": inserted, "updated": updated}
        await audit_fn(user, "admin", "restore", "backup", [{"field": "restore", "old": None, "new": result}])
        return {"ok": True, "mode": body.mode, "result": result}
