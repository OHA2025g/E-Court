"""Period workflow policy: locks, approval gating, and edit permissions."""
import os
from calendar import monthrange
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from seed_constants import REPORTING_PERIODS

DEFAULT_GRACE_DAYS = 7
DEFAULT_SLA_DUE_DAY = 10


async def get_workflow_settings(db) -> dict:
    doc = await db.settings.find_one({"key": "workflow_settings"})
    defaults = {
        "submission_grace_days": DEFAULT_GRACE_DAYS,
        "sla_due_day": DEFAULT_SLA_DUE_DAY,
        "dashboard_require_approval": os.environ.get("DASHBOARD_REQUIRE_APPROVAL", "true").lower()
        in ("1", "true", "yes"),
    }
    if not doc:
        return defaults
    return {**defaults, **(doc.get("value") or {})}


async def save_workflow_settings(db, value: dict) -> dict:
    merged = {**(await get_workflow_settings(db)), **value}
    await db.settings.update_one(
        {"key": "workflow_settings"},
        {"$set": {"key": "workflow_settings", "value": merged}},
        upsert=True,
    )
    return merged


def baseline_periods() -> set[str]:
    return {p["period"] for p in REPORTING_PERIODS if p.get("is_baseline")}


def period_end_date(period: str) -> datetime:
    """Last moment of reporting month (UTC)."""
    y, m = map(int, period.split("-"))
    last_day = monthrange(y, m)[1]
    return datetime(y, m, last_day, 23, 59, 59, tzinfo=timezone.utc)


def grace_deadline(period: str, grace_days: int) -> datetime:
    end = period_end_date(period)
    from datetime import timedelta
    return end + timedelta(days=grace_days)


async def get_submission(db, high_court: str, reporting_period: str) -> Optional[dict]:
    return await db.submissions.find_one({"high_court": high_court, "reporting_period": reporting_period})


async def is_period_baseline(db, reporting_period: str) -> bool:
    doc = await db.reporting_periods.find_one({"period": reporting_period})
    if doc:
        return bool(doc.get("is_baseline"))
    return reporting_period in baseline_periods()


async def is_editable(
    db,
    high_court: str,
    reporting_period: str,
    user: dict,
    now_fn,
) -> tuple[bool, str]:
    """Return (editable, reason). Admin can always edit unless auto-locked without override."""
    if user.get("role") == "Admin":
        return True, "admin"

    sub = await get_submission(db, high_court, reporting_period)
    if sub and sub.get("reopen_until"):
        ru = sub["reopen_until"]
        if isinstance(ru, str):
            ru = datetime.fromisoformat(ru.replace("Z", "+00:00"))
        if ru.tzinfo is None:
            ru = ru.replace(tzinfo=timezone.utc)
        if now_fn() <= ru:
            return True, "reopen_window"

    if sub and sub.get("edit_override_until"):
        eu = sub["edit_override_until"]
        if isinstance(eu, str):
            eu = datetime.fromisoformat(eu.replace("Z", "+00:00"))
        if eu.tzinfo is None:
            eu = eu.replace(tzinfo=timezone.utc)
        if now_fn() <= eu:
            return True, "admin_override"

    status = sub.get("status") if sub else None
    if status in ("Submitted", "Approved"):
        return False, f"period_{status.lower()}"

    settings = await get_workflow_settings(db)
    grace = settings.get("submission_grace_days", DEFAULT_GRACE_DAYS)
    if now_fn() > grace_deadline(reporting_period, grace):
        if sub and sub.get("auto_locked"):
            return False, "auto_locked"
        if not sub or status not in ("Returned",):
            return False, "grace_period_expired"

    return True, "open"


async def assert_editable(db, high_court: str, reporting_period: str, user: dict, now_fn):
    ok, reason = await is_editable(db, high_court, reporting_period, user, now_fn)
    if not ok:
        messages = {
            "period_submitted": "Period submitted for review — edits locked until returned or re-opened",
            "period_approved": "Period approved — request Admin return or re-open to edit",
            "auto_locked": "Reporting period auto-locked after grace period",
            "grace_period_expired": "Grace period for data entry has expired",
        }
        raise HTTPException(status_code=403, detail=messages.get(reason, f"Period not editable ({reason})"))


async def approved_hc_period_pairs(db, reporting_period: Optional[str] = None) -> set[tuple[str, str]]:
    q: dict = {"status": "Approved"}
    if reporting_period:
        q["reporting_period"] = reporting_period
    subs = await db.submissions.find(q, {"high_court": 1, "reporting_period": 1}).to_list(5000)
    return {(s["high_court"], s["reporting_period"]) for s in subs}


async def approved_match_filter(
    db,
    reporting_period: Optional[str] = None,
    include_unapproved: bool = False,
    user: Optional[dict] = None,
) -> dict:
    """Mongo match fragment: only approved HC+period rows (baseline periods always included)."""
    if include_unapproved:
        if not user or user.get("role") != "Admin":
            raise HTTPException(
                status_code=403,
                detail="Only administrators may include unapproved submissions",
            )
        return {}
    # CPC officers monitor their own HC on the dashboard — scope_filter restricts HC;
    # do not require national approval gating for their jurisdiction.
    if user and user.get("role") == "CPC" and user.get("high_court"):
        return {}
    settings = await get_workflow_settings(db)
    if user and user.get("role") == "Admin" and not settings.get("dashboard_require_approval"):
        return {}

    if not settings.get("dashboard_require_approval", True):
        return {}

    pairs = await approved_hc_period_pairs(db, reporting_period)
    bl = baseline_periods()
    or_clauses = []
    for hc, period in pairs:
        or_clauses.append({"high_court": hc, "reporting_period": period})
    if reporting_period and reporting_period in bl:
        or_clauses.append({"reporting_period": reporting_period})
    elif not reporting_period:
        for bp in bl:
            or_clauses.append({"reporting_period": bp})

    if not or_clauses:
        return {"high_court": "__none__"}  # match nothing
    return {"$or": or_clauses}


def merge_match(base: dict, extra: dict) -> dict:
    if not extra:
        return base
    if not base:
        return extra
    return {"$and": [base, extra]}
