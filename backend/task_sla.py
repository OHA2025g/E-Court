"""Task Management — SLA calculation helpers."""
from datetime import datetime, timezone
from typing import Optional

from task_constants import DEFAULT_SLA_HOURS


def parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def sla_hours_for(priority: str, custom: Optional[int] = None) -> int:
    if custom and custom > 0:
        return int(custom)
    return DEFAULT_SLA_HOURS.get(priority, DEFAULT_SLA_HOURS["Medium"])


def compute_sla_status(task: dict, now: datetime) -> dict:
    """Return sla_status, sla_remaining_hours, sla_pct_consumed."""
    status = task.get("status", "")
    if status in ("CLOSED", "CANCELLED", "DUPLICATE"):
        breached = task.get("sla_breached_at") is not None
        return {
            "sla_status": "CLOSED_AFTER_SLA" if breached else "CLOSED_WITHIN_SLA",
            "sla_remaining_hours": 0,
            "sla_pct_consumed": 100,
        }

    started = parse_dt(task.get("sla_started_at")) or parse_dt(task.get("created_at"))
    due = parse_dt(task.get("due_date"))
    hours = task.get("sla_hours") or sla_hours_for(task.get("priority", "Medium"))

    if not started:
        return {"sla_status": "NOT_STARTED", "sla_remaining_hours": hours, "sla_pct_consumed": 0}

    if due:
        end = due
    else:
        from datetime import timedelta
        end = started + timedelta(hours=hours)

    total_seconds = max((end - started).total_seconds(), 1)
    elapsed = max((now - started).total_seconds(), 0)
    pct = min(100, round(elapsed / total_seconds * 100, 1))
    remaining_h = max(0, round((end - now).total_seconds() / 3600, 1))

    if now >= end or task.get("status") == "SLA_BREACHED":
        sla_status = "BREACHED"
    elif pct >= 90:
        sla_status = "AT_RISK"
    elif pct >= 75:
        sla_status = "AT_RISK"
    else:
        sla_status = "ON_TRACK"

    return {
        "sla_status": sla_status,
        "sla_remaining_hours": remaining_h,
        "sla_pct_consumed": pct,
    }
