"""eCourts Phase III PMIS — main FastAPI application."""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bson import ObjectId
from fastapi import APIRouter, FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from seed_constants import DEFAULT_RAG_THRESHOLDS
from auth import (
    init_auth,
    register_auth_routes,
    require_fully_authenticated,
    require_role,
)
from cabinet_brief import build_cabinet_brief_pdf
from startup import create_lifespan
from admin_routes import register_admin_routes
from audit_routes import register_audit_routes
from submissions_routes import register_submissions_routes
from dashboard_routes import register_dashboard_routes
from dashboard_agg import compute_dashboard_summary
from dashboard_prefs import register_dashboard_pref_routes
from bulk_routes import register_bulk_routes
from export_routes import register_export_routes
from master_routes import register_master_routes
from pmu_routes import register_pmu_routes
from ijuris_routes import register_ijuris_routes
from scheduler_routes import register_scheduler_routes
from file_routes import register_file_routes
from tracker_routes import register_tracker_routes
from email_worker import drain_email_outbox, register_email_worker_routes
from workflow_routes import register_workflow_routes
from webhook_routes import register_webhook_routes
from api_token_routes import register_api_token_routes
from report_views_routes import register_report_views_routes
from comments_routes import register_comments_routes
from pfms_routes import register_pfms_routes
from sso_routes import register_sso_routes
from esign_routes import register_esign_routes
from anomaly_routes import register_anomaly_routes
from narrative_routes import register_narrative_routes
from scope_charter_routes import register_scope_charter_routes
from task_routes import register_task_routes
from team_routes import register_team_routes

# -------------------------------------------------------------------- setup
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

APP_NAME = os.environ.get("APP_NAME", "ecourts-pmis")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
CABINET_BRIEF_RECIPIENTS = [e.strip() for e in os.environ.get("CABINET_BRIEF_RECIPIENTS", "").split(",") if e.strip()]
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

# State → High Court mapping for the India choropleth
STATE_TO_HC = {
    "Uttar Pradesh": "Allahabad", "Andhra Pradesh": "Andhra Pradesh",
    "Maharashtra": "Bombay", "Goa": "Bombay",
    "Dadra and Nagar Haveli and Daman and Diu": "Bombay",
    "West Bengal": "Calcutta", "Andaman & Nicobar": "Calcutta",
    "Chhattisgarh": "Chhattisgarh", "Delhi": "Delhi",
    "Nagaland": "Gauhati - Nagaland", "Arunachal Pradesh": "Gauhati – Arunachal Pradesh",
    "Assam": "Gauhati – Assam", "Mizoram": "Gauhati – Mizoram",
    "Gujarat": "Gujarat", "Himachal Pradesh": "Himachal Pradesh",
    "Jammu & Kashmir": "Jammu & Kashmir", "Ladakh": "Jammu & Kashmir",
    "Jharkhand": "Jharkhand", "Karnataka": "Karnataka", "Kerala": "Kerala",
    "Lakshadweep": "Kerala", "Madhya Pradesh": "Madhya Pradesh",
    "Tamil Nadu": "Madras", "Puducherry": "Madras",
    "Manipur": "Manipur", "Meghalaya": "Meghalaya", "Odisha": "Odisha",
    "Bihar": "Patna", "Punjab": "Punjab & Haryana", "Haryana": "Punjab & Haryana",
    "Chandigarh": "Punjab & Haryana", "Rajasthan": "Rajasthan", "Sikkim": "Sikkim",
    "Telangana": "Telangana", "Tripura": "Tripura", "Uttarakhand": "Uttarakhand",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pmis")

api = APIRouter(prefix="/api")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def serialize(doc: Any) -> Any:
    """Recursively convert ObjectId and datetime in mongo docs to JSON-safe."""
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            if k == "_id":
                out["id"] = str(v)
            elif isinstance(v, ObjectId):
                out[k] = str(v)
            elif isinstance(v, datetime):
                out[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                out[k] = serialize(v)
            else:
                out[k] = v
        return out
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc

def compute_rag(percent: Optional[float], thresholds: dict = DEFAULT_RAG_THRESHOLDS) -> str:
    if percent is None:
        return "NA"
    if percent >= thresholds["green_min"]:
        return "GREEN"
    if percent >= thresholds["amber_min"]:
        return "AMBER"
    return "RED"

def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round((a / b) * 100, 2)

def scope_filter(user: dict, high_court_field: str = "high_court") -> dict:
    """Return mongo filter ensuring CPC users only see their HC."""
    if user["role"] == "CPC" and user.get("high_court"):
        return {high_court_field: user["high_court"]}
    return {}

async def audit(user: dict, tracker: str, action: str, ref_id: Optional[str],
                changes: list, high_court: Optional[str] = None,
                reporting_period: Optional[str] = None):
    await db.audit_logs.insert_one({
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "role": user.get("role"),
        "tracker": tracker,
        "action": action,
        "ref_id": ref_id,
        "changes": changes,
        "high_court": high_court,
        "reporting_period": reporting_period,
        "timestamp": now_utc(),
    })

async def notify(user_emails: list, title: str, body: str, kind: str = "info",
                 link: Optional[str] = None, meta: Optional[dict] = None,
                 also_email: bool = False,
                 email_attachment_base64: Optional[str] = None,
                 email_attachment_filename: Optional[str] = None):
    """Create an in-app notification for each email. If also_email=True, also queue
    in db.email_outbox (which would be drained by a real SMTP worker)."""
    if not user_emails:
        return
    rows = [{
        "to_email": e, "title": title, "body": body, "kind": kind,
        "link": link, "meta": meta or {}, "is_read": False, "ts": now_utc(),
    } for e in user_emails]
    if rows:
        await db.notifications.insert_many(rows)
    if also_email:
        outbox_rows = []
        for e in user_emails:
            row = {"to": e, "subject": title, "body": body, "ts": now_utc(), "status": "queued"}
            if email_attachment_base64:
                row["attachment_base64"] = email_attachment_base64
                row["attachment_filename"] = email_attachment_filename or "attachment.pdf"
            outbox_rows.append(row)
        await db.email_outbox.insert_many(outbox_rows)

async def _admin_emails() -> list:
    docs = await db.users.find({"role": "Admin"}, {"email": 1}).to_list(50)
    return [d["email"] for d in docs]

async def _hc_cpc_emails(high_court: str) -> list:
    docs = await db.users.find({"role": "CPC", "high_court": high_court}, {"email": 1}).to_list(50)
    return [d["email"] for d in docs]

init_auth(db, audit, serialize, now_utc)
register_auth_routes(api)
register_dashboard_routes(api, db, require_fully_authenticated, scope_filter, compute_rag, safe_div, STATE_TO_HC)
register_dashboard_pref_routes(api, db, require_fully_authenticated, now_utc)
register_bulk_routes(
    api, db, require_fully_authenticated, audit, compute_rag, safe_div, serialize, now_utc, DEFAULT_RAG_THRESHOLDS,
)
register_master_routes(
    api, db, require_fully_authenticated, require_role, audit, DEFAULT_RAG_THRESHOLDS,
)
register_export_routes(
    api, db, require_fully_authenticated, require_role, audit,
    scope_filter, serialize, compute_rag, safe_div, now_utc, DEFAULT_RAG_THRESHOLDS,
)
tracker_upserts = register_tracker_routes(
    api, db, require_fully_authenticated, scope_filter, audit, notify, _admin_emails,
    compute_rag, safe_div, serialize, now_utc, DEFAULT_RAG_THRESHOLDS,
)
register_audit_routes(api, db, require_fully_authenticated, serialize)
register_submissions_routes(
    api, db, require_fully_authenticated, require_role, audit, serialize, now_utc,
    notify, _admin_emails, _hc_cpc_emails,
)
register_admin_routes(api, db, require_role, audit, serialize, now_utc)
register_pmu_routes(
    api, db, require_fully_authenticated, require_role, audit, serialize, now_utc,
)
register_ijuris_routes(
    api, db, require_role, serialize,
    tracker_upserts["upsert_physical"],
    tracker_upserts["upsert_financial"],
    tracker_upserts["upsert_outcome"],
    now_utc,
)
_run_weekly_cabinet_brief = register_scheduler_routes(
    api, db, scheduler, require_role, serialize, now_utc,
    notify, _admin_emails, CABINET_BRIEF_RECIPIENTS,
    build_cabinet_brief_pdf, compute_rag, safe_div, DEFAULT_RAG_THRESHOLDS,
)
_init_storage = register_file_routes(
    api, db, require_fully_authenticated, serialize, now_utc, APP_NAME, EMERGENT_LLM_KEY,
)
register_email_worker_routes(api, db, require_role, now_utc)
register_workflow_routes(
    api, db, require_fully_authenticated, require_role, audit, serialize, now_utc,
    notify, _admin_emails, _hc_cpc_emails,
)
register_webhook_routes(api, db, require_role, serialize, now_utc)
register_api_token_routes(api, db, require_role, serialize, now_utc)
register_report_views_routes(api, db, require_fully_authenticated, serialize, now_utc)
register_comments_routes(api, db, require_fully_authenticated, serialize, now_utc, notify)
register_pfms_routes(api, db, require_fully_authenticated, serialize)
register_sso_routes(api, db, require_role, serialize)
register_esign_routes(api, db, require_fully_authenticated, serialize, now_utc)
register_anomaly_routes(api, db, require_fully_authenticated, scope_filter)
register_narrative_routes(
    api, db, require_role, require_fully_authenticated, scope_filter, compute_rag, safe_div,
    compute_dashboard_summary,
)
register_task_routes(
    api, db, require_fully_authenticated, require_role, serialize, notify,
)
register_team_routes(api, db, require_role, audit, serialize, now_utc)
register_scope_charter_routes(
    api, db, require_fully_authenticated, audit, serialize, now_utc,
)


async def _drain_email_outbox_job():
    await drain_email_outbox(db, now_utc)


def _register_extra_jobs(sched):
    from notification_jobs import (
        notify_anomaly_digest,
        notify_overdue_submissions,
        notify_period_open,
        remind_laggards,
        run_auto_lock,
    )
    from task_sla_jobs import notify_task_sla_warnings
    from webhook_routes import drain_webhook_outbox

    async def _period_open():
        await notify_period_open(db, now_utc, notify, _admin_emails)

    async def _overdue():
        await notify_overdue_submissions(db, now_utc, notify, _admin_emails, _hc_cpc_emails)

    async def _laggards():
        await remind_laggards(db, now_utc, notify, _admin_emails, _hc_cpc_emails)

    async def _anomaly_digest():
        await notify_anomaly_digest(db, now_utc, notify, _admin_emails)

    async def _auto_lock():
        await run_auto_lock(db, now_utc)

    async def _webhooks():
        await drain_webhook_outbox(db, now_utc)

    async def _task_sla():
        await notify_task_sla_warnings(db, now_utc, notify)

    sched.add_job(_period_open, CronTrigger(day=1, hour=8, minute=0, timezone="Asia/Kolkata"),
                  id="period_open_notify", replace_existing=True)
    sched.add_job(_overdue, CronTrigger(hour=9, minute=30, timezone="Asia/Kolkata"),
                  id="overdue_notify", replace_existing=True)
    sched.add_job(_laggards, CronTrigger(day_of_week="wed", hour=10, minute=0, timezone="Asia/Kolkata"),
                  id="laggard_reminder", replace_existing=True)
    sched.add_job(_anomaly_digest, CronTrigger(day_of_week="fri", hour=11, minute=0, timezone="Asia/Kolkata"),
                  id="anomaly_digest", replace_existing=True)
    sched.add_job(_auto_lock, CronTrigger(hour=2, minute=0, timezone="Asia/Kolkata"),
                  id="auto_lock_periods", replace_existing=True)
    sched.add_job(_webhooks, "interval", minutes=2, id="webhook_drain", replace_existing=True)
    sched.add_job(_task_sla, "interval", minutes=30, id="task_sla_warnings", replace_existing=True)

@api.get("/")
async def root():
    return {"service": "eCourts Phase III PMIS", "status": "ok"}


@api.get("/health")
async def health():
    return {"ok": True, "ts": now_utc().isoformat()}


from security_bootstrap import APP_ENV

_disable_openapi = APP_ENV == "production" or os.environ.get("DISABLE_OPENAPI", "false").lower() in ("1", "true", "yes")

app = FastAPI(
    title="eCourts Phase III PMIS",
    lifespan=create_lifespan(
        db, client, scheduler, _init_storage, _run_weekly_cabinet_brief,
        now_utc, compute_rag, safe_div, _drain_email_outbox_job, _register_extra_jobs,
    ),
    docs_url=None if _disable_openapi else "/docs",
    redoc_url=None if _disable_openapi else "/redoc",
    openapi_url=None if _disable_openapi else "/openapi.json",
)
app.include_router(api)

_cors_raw = os.environ.get("CORS_ORIGINS", "").strip()
if _cors_raw == "*" or not _cors_raw:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
