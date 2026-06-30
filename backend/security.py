"""Security helpers: password policy, IP allowlist, upload validation, CAPTCHA."""
import html
import ipaddress
import os
import random
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException, Request

try:
    import magic
except ImportError:
    magic = None

PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", "12"))
PASSWORD_HISTORY_COUNT = int(os.environ.get("PASSWORD_HISTORY_COUNT", "5"))
PASSWORD_MAX_AGE_DAYS = int(os.environ.get("PASSWORD_MAX_AGE_DAYS", "90"))
LOCKOUT_CAPTCHA_AFTER = int(os.environ.get("LOCKOUT_CAPTCHA_AFTER", "3"))

SPECIAL_CHARS = re.compile(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;/`~]")

EXT_MIME_MAP = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "webp": {"image/webp"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "csv": {"text/csv", "text/plain", "application/csv", "application/vnd.ms-excel"},
    "txt": {"text/plain"},
}


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trust_headers = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes")
    if not trust_headers or peer == "unknown":
        return peer
    if not _peer_is_trusted_proxy(peer):
        return peer
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return peer


def _peer_is_trusted_proxy(peer: str) -> bool:
    raw = os.environ.get("TRUSTED_PROXY_CIDRS", "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")
    cidrs = [c.strip() for c in raw.split(",") if c.strip()]
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for entry in cidrs:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def validate_password_policy(password: str, user_record: Optional[dict] = None, verify_fn=None) -> None:
    """Raise HTTPException if password fails policy."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {PASSWORD_MIN_LENGTH} characters",
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must include an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must include a lowercase letter")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must include a digit")
    if not SPECIAL_CHARS.search(password):
        raise HTTPException(status_code=400, detail="Password must include a special character")

    if user_record and verify_fn:
        current_hash = user_record.get("password_hash")
        if current_hash and verify_fn(password, current_hash):
            raise HTTPException(status_code=400, detail="New password must differ from current password")
        for old_hash in (user_record.get("password_history") or [])[:PASSWORD_HISTORY_COUNT]:
            if verify_fn(password, old_hash):
                raise HTTPException(
                    status_code=400,
                    detail=f"Password cannot match any of your last {PASSWORD_HISTORY_COUNT} passwords",
                )


def password_expired(user_record: dict, now_fn) -> bool:
    changed = user_record.get("password_changed_at")
    if not changed:
        return False
    if isinstance(changed, str):
        changed = datetime.fromisoformat(changed.replace("Z", "+00:00"))
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=timezone.utc)
    return changed + timedelta(days=PASSWORD_MAX_AGE_DAYS) < now_fn()


def build_password_history_update(user_record: dict, new_hash: str, hash_fn) -> dict:
    history = list(user_record.get("password_history") or [])
    old = user_record.get("password_hash")
    if old:
        history.insert(0, old)
    history = history[:PASSWORD_HISTORY_COUNT]
    return {
        "password_hash": new_hash,
        "password_history": history,
        "password_changed_at": datetime.now(timezone.utc),
        "must_change_password": False,
    }


async def get_admin_ip_allowlist(db) -> dict:
    doc = await db.settings.find_one({"key": "admin_ip_allowlist"})
    if doc and doc.get("value"):
        return doc["value"]
    env_enabled = os.environ.get("ADMIN_IP_ALLOWLIST_ENABLED", "false").lower() == "true"
    env_cidrs = [c.strip() for c in os.environ.get("ADMIN_IP_ALLOWLIST", "").split(",") if c.strip()]
    return {"enabled": env_enabled, "cidrs": env_cidrs}


async def check_admin_ip_allowed(db, request: Request) -> None:
    cfg = await get_admin_ip_allowlist(db)
    if not cfg.get("enabled"):
        return
    cidrs = cfg.get("cidrs") or []
    if not cidrs:
        return
    ip = client_ip(request)
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=403, detail="Admin access denied from this network")
    for entry in cidrs:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return
            elif addr == ipaddress.ip_address(entry):
                return
        except ValueError:
            continue
    raise HTTPException(status_code=403, detail="Admin access denied from this network")


def detect_mime(raw: bytes) -> str:
    if magic is None:
        return "application/octet-stream"
    try:
        return magic.from_buffer(raw, mime=True) or "application/octet-stream"
    except Exception:
        return "application/octet-stream"


def validate_upload_bytes(raw: bytes, ext: str) -> None:
    ext = ext.lower()
    allowed = EXT_MIME_MAP.get(ext)
    if not allowed:
        raise HTTPException(status_code=400, detail=f"File type '.{ext}' not allowed")
    detected = detect_mime(raw)
    if detected == "application/octet-stream" and ext in ("txt", "csv"):
        return
    if detected not in allowed:
        # OOXML zips are sometimes detected as application/zip
        if ext in ("docx", "xlsx") and detected == "application/zip":
            return
        raise HTTPException(
            status_code=400,
            detail=f"File content does not match extension '.{ext}' (detected {detected})",
        )


def generate_captcha_svg(question: str) -> str:
    safe_question = html.escape(question, quote=True)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="60" viewBox="0 0 220 60">'
        f'<rect width="220" height="60" fill="#f1f5f9"/>'
        f'<text x="20" y="38" font-family="monospace" font-size="22" fill="#0f172a">{safe_question}</text>'
        f"</svg>"
    )


async def create_login_captcha(db, now_fn) -> tuple[str, str]:
    a, b = random.randint(2, 9), random.randint(1, 9)
    answer = str(a + b)
    captcha_id = str(uuid.uuid4())
    question = f"{a} + {b} = ?"
    await db.login_challenges.insert_one({
        "id": captcha_id,
        "answer": answer,
        "created_at": now_fn(),
    })
    return captcha_id, generate_captcha_svg(question)


async def verify_login_captcha(db, captcha_id: Optional[str], captcha_answer: Optional[str], now_fn) -> bool:
    if not captcha_id or captcha_answer is None:
        return False
    doc = await db.login_challenges.find_one({"id": captcha_id})
    if not doc:
        return False
    ok = str(captcha_answer).strip() == str(doc.get("answer", "")).strip()
    await db.login_challenges.delete_one({"id": captcha_id})
    return ok


def gen_password(n: int = 12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789@#$%"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(n))
        try:
            validate_password_policy(pw)
            return pw
        except HTTPException:
            continue
