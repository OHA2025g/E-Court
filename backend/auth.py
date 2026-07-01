"""Authentication, sessions, 2FA, and auth API routes."""
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal, Callable, Any

import bcrypt
import jwt as pyjwt
import pyotp
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from security import (
    LOCKOUT_CAPTCHA_AFTER,
    PASSWORD_MAX_AGE_DAYS,
    build_password_history_update,
    check_admin_ip_allowed,
    client_ip,
    create_login_captcha,
    gen_password,
    password_expired,
    validate_password_policy,
    verify_login_captcha,
)
from security_bootstrap import COOKIE_SECURE, validate_jwt_secret, validate_demo_passwords, validate_production_settings

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]
validate_jwt_secret(JWT_SECRET)
validate_demo_passwords()
validate_production_settings()
LOCKOUT_MAX_FAILS = int(os.environ.get("LOCKOUT_MAX_FAILS", "5"))
LOCKOUT_DURATION_MIN = int(os.environ.get("LOCKOUT_DURATION_MIN", "15"))
ALL_ROLES = ("Admin", "CPC", "Viewer")


def is_2fa_disabled() -> bool:
    """Temporary bypass — set DISABLE_2FA=true to skip TOTP at login and mandatory setup."""
    return os.environ.get("DISABLE_2FA", "false").lower() in ("1", "true", "yes")


def get_require_2fa_roles() -> set[str]:
    if is_2fa_disabled():
        return set()
    raw = os.environ.get("REQUIRE_2FA_ROLES", "Admin")
    roles = {r.strip() for r in raw.split(",") if r.strip()}
    return roles or {"Admin"}


def role_requires_2fa(role: str) -> bool:
    if is_2fa_disabled():
        return False
    return role in get_require_2fa_roles()


def user_requires_2fa_setup(user_doc: dict) -> bool:
    if not user_doc:
        return False
    return role_requires_2fa(user_doc.get("role", "")) and not user_doc.get("totp_enabled")


def role_can_enroll_2fa(role: str) -> bool:
    return role in ALL_ROLES

db = None
audit_fn: Optional[Callable] = None
serialize_fn: Optional[Callable] = None
now_utc_fn: Optional[Callable] = None

SESSION_LAST_SEEN_INTERVAL = timedelta(minutes=5)

POLICY_EXEMPT_PREFIXES = (
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/change-password",
    "/api/auth/2fa/setup",
    "/api/auth/2fa/verify",
    "/api/auth/2fa/disable",
    "/api/auth/2fa/policy",
    "/api/auth/sessions",
)

API_TOKEN_READ_PREFIXES = (
    "/api/public/",
    "/api/dashboard/",
    "/api/physical",
    "/api/financial",
    "/api/outcome",
)

API_TOKEN_SCOPE_PREFIXES: dict[str, tuple[str, ...]] = {
    "public": ("/api/public/",),
    "dashboard": ("/api/dashboard/",),
    "dashboard:read": ("/api/dashboard/",),
    "physical": ("/api/physical",),
    "physical:read": ("/api/physical",),
    "financial": ("/api/financial",),
    "financial:read": ("/api/financial",),
    "outcome": ("/api/outcome",),
    "outcome:read": ("/api/outcome",),
}


def _api_token_read_allowed(path: str, method: str, scopes: Optional[list] = None) -> bool:
    if method != "GET":
        return False
    scope_list = scopes or []
    if scope_list:
        allowed_prefixes: set[str] = set()
        for scope in scope_list:
            for prefix in API_TOKEN_SCOPE_PREFIXES.get(scope, ()):
                allowed_prefixes.add(prefix)
        if not allowed_prefixes:
            return False
        return any(path == prefix or path.startswith(prefix) for prefix in allowed_prefixes)
    for prefix in API_TOKEN_READ_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    return False


def init_auth(database, audit, serialize, now_utc):
    global db, audit_fn, serialize_fn, now_utc_fn
    db = database
    audit_fn = audit
    serialize_fn = serialize
    now_utc_fn = now_utc


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def create_token(payload: dict, expires_minutes: int) -> str:
    data = payload.copy()
    data["exp"] = now_utc_fn() + timedelta(minutes=expires_minutes)
    return pyjwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _policy_exempt(request: Request) -> bool:
    path = request.url.path.rstrip("/") or request.url.path
    for prefix in POLICY_EXEMPT_PREFIXES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return True
    return False


async def _decode_access_token(request: Request) -> tuple[dict, str]:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        sid = payload.get("sid")
        if not sid:
            raise HTTPException(status_code=401, detail="Session expired — please sign in again")
        session = await db.sessions.find_one({"id": sid})
        if not session or session.get("revoked_at"):
            raise HTTPException(status_code=401, detail="Session revoked")
        return payload, sid
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def enforce_api_token_rate_limit_for_request(request: Request):
    """Apply rate limits when a valid API Bearer token is present (including optional-auth routes)."""
    doc = await resolve_api_token_for_request(request)
    if doc:
        from api_rate_limit import enforce_api_token_rate_limit
        enforce_api_token_rate_limit(str(doc["_id"]))


async def resolve_api_token_for_request(request: Request) -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bare = auth[7:].strip()
    if bare.count(".") >= 2:
        return None
    from api_token_routes import resolve_api_token
    return await resolve_api_token(db, request)


async def _user_from_api_token(request: Request) -> Optional[dict]:
    doc = await resolve_api_token_for_request(request)
    if not doc or not _api_token_read_allowed(request.url.path, request.method, doc.get("scopes")):
        return None
    from api_rate_limit import enforce_api_token_rate_limit
    enforce_api_token_rate_limit(str(doc["_id"]))
    return {
        "id": str(doc["_id"]),
        "email": f"api-token:{doc.get('name', 'token')}",
        "role": "Viewer",
        "name": doc.get("name", "API Token"),
        "api_token": True,
        "scopes": doc.get("scopes", []),
        "_session_id": None,
    }


async def get_current_user(request: Request) -> dict:
    api_user = await _user_from_api_token(request)
    if api_user:
        return api_user
    payload, sid = await _decode_access_token(request)
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user.pop("password_hash", None)
    user.pop("totp_secret", None)
    user.pop("password_history", None)
    out = serialize_fn(user)
    out["_session_id"] = sid
    await touch_session(sid)
    return out


async def require_fully_authenticated(request: Request, user: dict = Depends(get_current_user)) -> dict:
    if user.get("api_token"):
        return user
    full = await db.users.find_one({"_id": ObjectId(user["id"])})
    if not full:
        raise HTTPException(status_code=401, detail="User not found")

    exempt = _policy_exempt(request)

    if full.get("role") == "Admin":
        await check_admin_ip_allowed(db, request)

    if not exempt:
        if full.get("must_change_password") or password_expired(full, now_utc_fn):
            raise HTTPException(
                status_code=403,
                detail={"code": "must_change_password", "message": "You must change your password before continuing"},
            )
        if user_requires_2fa_setup(full):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "requires_2fa_setup",
                    "message": f"{full.get('role')} accounts must enable two-factor authentication",
                },
            )

    user["totp_enabled"] = bool(full.get("totp_enabled"))
    user["must_change_password"] = bool(full.get("must_change_password")) or password_expired(full, now_utc_fn)
    user["password_expired"] = password_expired(full, now_utc_fn)
    user["requires_2fa_setup"] = user_requires_2fa_setup(full)
    user["two_fa_mandatory"] = role_requires_2fa(full.get("role", ""))
    user["two_fa_optional_available"] = role_can_enroll_2fa(full.get("role", "")) and not role_requires_2fa(full.get("role", ""))
    user["task_role"] = full.get("task_role")
    user["team_lead_id"] = full.get("team_lead_id")
    try:
        from task_permissions import resolve_task_role
        user["resolved_task_role"] = resolve_task_role({**user, "task_role": full.get("task_role"), "role": full.get("role")})
    except Exception:
        user["resolved_task_role"] = full.get("task_role") or "team_member"
    return user


def require_role(*roles: str):
    async def _dep(user: dict = Depends(require_fully_authenticated)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden for this role")
        return user

    return _dep


async def create_session(user_id: str, request: Request) -> str:
    sid = secrets.token_urlsafe(32)
    doc = {
        "id": sid,
        "user_id": user_id,
        "created_at": now_utc_fn(),
        "last_seen_at": now_utc_fn(),
        "ip": client_ip(request),
        "user_agent": request.headers.get("user-agent", "")[:512],
        "revoked_at": None,
    }
    await db.sessions.insert_one(doc)
    return sid


async def touch_session(sid: str):
    session = await db.sessions.find_one({"id": sid})
    if not session or session.get("revoked_at"):
        return
    last = session.get("last_seen_at")
    if isinstance(last, str):
        last = datetime.fromisoformat(last.replace("Z", "+00:00"))
    if last and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last and now_utc_fn() - last < SESSION_LAST_SEEN_INTERVAL:
        return
    await db.sessions.update_one({"id": sid}, {"$set": {"last_seen_at": now_utc_fn()}})


async def revoke_session(sid: str):
    await db.sessions.update_one({"id": sid}, {"$set": {"revoked_at": now_utc_fn()}})


async def revoke_all_user_sessions(user_id: str, except_sid: Optional[str] = None):
    filt = {"user_id": user_id, "revoked_at": None}
    if except_sid:
        filt["id"] = {"$ne": except_sid}
    await db.sessions.update_many(filt, {"$set": {"revoked_at": now_utc_fn()}})


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie(
        "access_token", access, httponly=True, secure=COOKIE_SECURE, samesite="lax",
        max_age=60 * 60 * 8, path="/",
    )
    response.set_cookie(
        "refresh_token", refresh, httponly=True, secure=COOKIE_SECURE, samesite="strict",
        max_age=60 * 60 * 24 * 7, path="/",
    )


def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


async def issue_tokens(user: dict, request: Request, response: Response) -> dict:
    sid = await create_session(str(user["_id"]), request)
    email = user["email"]
    access = create_token(
        {"sub": str(user["_id"]), "email": email, "role": user["role"], "type": "access", "sid": sid},
        60 * 8,
    )
    refresh = create_token({"sub": str(user["_id"]), "type": "refresh", "sid": sid}, 60 * 24 * 7)
    set_auth_cookies(response, access, refresh)
    user.pop("password_hash", None)
    user.pop("totp_secret", None)
    user.pop("password_history", None)
    out = serialize_fn(user)
    out["totp_enabled"] = bool(user.get("totp_enabled"))
    out["must_change_password"] = bool(user.get("must_change_password"))
    out["requires_2fa_setup"] = user_requires_2fa_setup(user)
    out["two_fa_mandatory"] = role_requires_2fa(user.get("role", ""))
    out["two_fa_optional_available"] = role_can_enroll_2fa(user.get("role", "")) and not role_requires_2fa(user.get("role", ""))
    return {"user": out}


async def _is_locked(email: str) -> Optional[datetime]:
    lock = await db.login_locks.find_one({"email": email})
    if not lock:
        return None
    until = lock.get("locked_until")
    if until is None:
        return None
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if until > now_utc_fn():
        return until
    return None


async def _count_recent_failures(email: str) -> int:
    window_start = now_utc_fn() - timedelta(minutes=LOCKOUT_DURATION_MIN)
    return await db.login_attempts.count_documents(
        {"email": email, "success": False, "ts": {"$gte": window_start}}
    )


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None
    captcha_id: Optional[str] = None
    captcha_answer: Optional[str] = None


class Verify2FAIn(BaseModel):
    code: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class Setup2FAIn(BaseModel):
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    role: Literal["Admin", "CPC", "Viewer"]
    high_court: Optional[str] = None
    password: str
    task_role: Optional[Literal["manager", "team_lead", "team_member", "auditor", "admin"]] = None
    team_lead_id: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Literal["Admin", "CPC", "Viewer"]] = None
    high_court: Optional[str] = None
    password: Optional[str] = None
    task_role: Optional[Literal["manager", "team_lead", "team_member", "auditor", "admin"]] = None
    team_lead_id: Optional[str] = None


class IpAllowlistIn(BaseModel):
    enabled: bool
    cidrs: list[str] = []


def register_auth_routes(api: APIRouter):
    @api.post("/auth/login")
    async def login(body: LoginIn, request: Request, response: Response):
        from api_rate_limit import enforce_login_ip_rate_limit
        enforce_login_ip_rate_limit(client_ip(request))
        email = body.email.lower().strip()
        locked_until = await _is_locked(email)
        if locked_until:
            remaining = int((locked_until - now_utc_fn()).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=423,
                detail=f"Account locked due to repeated failed sign-ins. Try again in {remaining} minute(s).",
            )

        user = await db.users.find_one({"email": email})

        async def record_failure(reason: Optional[str] = None):
            doc = {"email": email, "ts": now_utc_fn(), "success": False}
            if reason:
                doc["reason"] = reason
            await db.login_attempts.insert_one(doc)
            fails = await _count_recent_failures(email)
            if fails >= LOCKOUT_MAX_FAILS:
                until = now_utc_fn() + timedelta(minutes=LOCKOUT_DURATION_MIN)
                await db.login_locks.update_one(
                    {"email": email}, {"$set": {"locked_until": until, "set_at": now_utc_fn()}}, upsert=True
                )
                raise HTTPException(
                    status_code=423,
                    detail=f"Account locked for {LOCKOUT_DURATION_MIN} minutes after {LOCKOUT_MAX_FAILS} failed attempts.",
                )
            if fails >= LOCKOUT_CAPTCHA_AFTER:
                if not await verify_login_captcha(db, body.captcha_id, body.captcha_answer, now_utc_fn):
                    captcha_id, image_svg = await create_login_captcha(db, now_utc_fn)
                    raise HTTPException(
                        status_code=401,
                        detail={
                            "code": "requires_captcha",
                            "message": "Please complete the security check",
                            "captcha_id": captcha_id,
                            "image_svg": image_svg,
                        },
                    )
            remaining_attempts = max(0, LOCKOUT_MAX_FAILS - fails)
            raise HTTPException(
                status_code=401,
                detail=f"Invalid email or password. {remaining_attempts} attempt(s) remaining before lockout.",
            )

        if not user or not verify_password(body.password, user.get("password_hash", "")):
            await record_failure()

        if user.get("role") == "Admin":
            await check_admin_ip_allowed(db, request)

        if password_expired(user, now_utc_fn):
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"must_change_password": True}})
            user["must_change_password"] = True

        if not is_2fa_disabled() and user.get("totp_enabled") and user.get("totp_secret"):
            if not body.totp_code:
                return {"requires_2fa": True, "email": email}
            totp = pyotp.TOTP(user["totp_secret"])
            if not totp.verify(body.totp_code, valid_window=1):
                await record_failure("bad_2fa")
                raise HTTPException(status_code=401, detail="Invalid 2FA code")

        await db.login_attempts.insert_one({"email": email, "ts": now_utc_fn(), "success": True})
        await db.login_locks.delete_one({"email": email})
        return await issue_tokens(user, request, response)

    @api.get("/auth/captcha")
    async def get_captcha():
        captcha_id, image_svg = await create_login_captcha(db, now_utc_fn)
        return {"captcha_id": captcha_id, "image_svg": image_svg}

    @api.post("/auth/logout")
    async def logout(request: Request, response: Response, user: dict = Depends(get_current_user)):
        sid = user.get("_session_id")
        if sid:
            await revoke_session(sid)
        clear_auth_cookies(response)
        return {"ok": True}

    @api.get("/auth/me")
    async def me(request: Request, user: dict = Depends(get_current_user)):
        sid = user.get("_session_id")
        if sid:
            await touch_session(sid)
        full = await db.users.find_one({"_id": ObjectId(user["id"])})
        user["totp_enabled"] = bool(full and full.get("totp_enabled"))
        user["must_change_password"] = bool(full and full.get("must_change_password")) or (
            full and password_expired(full, now_utc_fn)
        )
        user["password_expired"] = bool(full and password_expired(full, now_utc_fn))
        user["requires_2fa_setup"] = bool(full and user_requires_2fa_setup(full))
        user["two_fa_mandatory"] = bool(full and role_requires_2fa(full.get("role", "")))
        user["two_fa_optional_available"] = bool(
            full and role_can_enroll_2fa(full.get("role", "")) and not role_requires_2fa(full.get("role", ""))
        )
        user["task_role"] = full.get("task_role") if full else None
        user["team_lead_id"] = full.get("team_lead_id") if full else None
        try:
            from task_permissions import resolve_task_role
            user["resolved_task_role"] = resolve_task_role(user)
        except Exception:
            user["resolved_task_role"] = user.get("task_role")
        return user

    @api.post("/auth/change-password")
    async def change_password(body: ChangePasswordIn, request: Request, user: dict = Depends(get_current_user)):
        rec = await db.users.find_one({"_id": ObjectId(user["id"])})
        if not rec or not verify_password(body.current_password, rec.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        validate_password_policy(body.new_password, rec, verify_password)
        update = build_password_history_update(rec, hash_password(body.new_password), hash_password)
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": update})
        sid = user.get("_session_id")
        await revoke_all_user_sessions(user["id"], except_sid=sid)
        await audit_fn(user, "users", "change_password", user["id"],
                       [{"field": "password", "old": "***", "new": "***"}])
        return {"ok": True}

    @api.get("/auth/2fa/policy")
    async def twofa_policy(_: dict = Depends(get_current_user)):
        required = sorted(get_require_2fa_roles())
        return {
            "required_roles": required,
            "optional_enrollment_roles": [r for r in ALL_ROLES if r not in required],
            "admin_mandatory": "Admin" in required,
            "disabled": is_2fa_disabled(),
        }

    @api.post("/auth/2fa/setup")
    async def setup_2fa(body: Setup2FAIn, user: dict = Depends(get_current_user)):
        if not role_can_enroll_2fa(user.get("role", "")):
            raise HTTPException(status_code=403, detail="Two-factor authentication is not available for this account")
        rec = await db.users.find_one({"_id": ObjectId(user["id"])})
        if not rec or not verify_password(body.password, rec.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Password confirmation is required to set up 2FA")
        secret = pyotp.random_base32()
        await db.users.update_one(
            {"_id": ObjectId(user["id"])},
            {"$set": {"totp_secret": secret, "totp_enabled": False}},
        )
        uri = pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="eCourts PMIS")
        return {"secret": secret, "otpauth_uri": uri}

    @api.post("/auth/2fa/verify")
    async def verify_2fa(body: Verify2FAIn, user: dict = Depends(get_current_user)):
        if not role_can_enroll_2fa(user.get("role", "")):
            raise HTTPException(status_code=403, detail="Two-factor authentication is not available for this account")
        rec = await db.users.find_one({"_id": ObjectId(user["id"])})
        if not rec or not rec.get("totp_secret"):
            raise HTTPException(status_code=400, detail="Run /auth/2fa/setup first")
        if not pyotp.TOTP(rec["totp_secret"]).verify(body.code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid code")
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"totp_enabled": True}})
        await audit_fn(user, "users", "enable_2fa", user["id"],
                       [{"field": "totp_enabled", "old": False, "new": True}])
        return {"ok": True}

    @api.post("/auth/2fa/disable")
    async def disable_2fa(body: Verify2FAIn, user: dict = Depends(get_current_user)):
        if role_requires_2fa(user.get("role", "")):
            raise HTTPException(
                status_code=403,
                detail="Two-factor authentication cannot be disabled for accounts where it is mandatory",
            )
        rec = await db.users.find_one({"_id": ObjectId(user["id"])})
        if not rec or not rec.get("totp_enabled"):
            raise HTTPException(status_code=400, detail="2FA is not enabled")
        if not pyotp.TOTP(rec["totp_secret"]).verify(body.code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid code")
        await db.users.update_one(
            {"_id": ObjectId(user["id"])},
            {"$set": {"totp_enabled": False}, "$unset": {"totp_secret": ""}},
        )
        await audit_fn(user, "users", "disable_2fa", user["id"],
                       [{"field": "totp_enabled", "old": True, "new": False}])
        return {"ok": True}

    @api.post("/auth/refresh")
    async def refresh_token_route(request: Request, response: Response):
        token = request.cookies.get("refresh_token")
        if not token:
            raise HTTPException(status_code=401, detail="No refresh token")
        try:
            payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token")
            sid = payload.get("sid")
            if not sid:
                raise HTTPException(status_code=401, detail="Session expired — please sign in again")
            session = await db.sessions.find_one({"id": sid})
            if not session or session.get("revoked_at"):
                raise HTTPException(status_code=401, detail="Session revoked")
        except pyjwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        await revoke_session(sid)
        new_sid = await create_session(str(user["_id"]), request)
        access = create_token(
            {"sub": str(user["_id"]), "email": user["email"], "role": user["role"], "type": "access", "sid": new_sid},
            60 * 8,
        )
        refresh = create_token({"sub": str(user["_id"]), "type": "refresh", "sid": new_sid}, 60 * 24 * 7)
        set_auth_cookies(response, access, refresh)
        return {"ok": True}

    @api.get("/auth/sessions")
    async def list_sessions(user: dict = Depends(get_current_user)):
        current_sid = user.get("_session_id")
        docs = await db.sessions.find({"user_id": user["id"], "revoked_at": None}).sort("last_seen_at", -1).to_list(50)
        out = []
        for d in docs:
            row = serialize_fn(d)
            row["is_current"] = row["id"] == current_sid
            out.append(row)
        return out

    @api.delete("/auth/sessions/{session_id}")
    async def revoke_one_session(session_id: str, request: Request, response: Response,
                                 user: dict = Depends(get_current_user)):
        rec = await db.sessions.find_one({"id": session_id, "user_id": user["id"]})
        if not rec:
            raise HTTPException(status_code=404, detail="Session not found")
        await revoke_session(session_id)
        if session_id == user.get("_session_id"):
            clear_auth_cookies(response)
        return {"ok": True}

    @api.delete("/auth/sessions")
    async def revoke_other_sessions(user: dict = Depends(get_current_user)):
        await revoke_all_user_sessions(user["id"], except_sid=user.get("_session_id"))
        return {"ok": True}

    @api.get("/users")
    async def list_users(user: dict = Depends(require_role("Admin"))):
        users = await db.users.find({}, {"password_hash": 0, "totp_secret": 0, "password_history": 0}).to_list(500)
        team_ids = {u.get("team_id") for u in users if u.get("team_id")}
        team_map = {}
        if team_ids:
            from bson import ObjectId as _Oid
            oids = []
            for tid in team_ids:
                try:
                    oids.append(_Oid(tid))
                except Exception:
                    pass
            if oids:
                async for t in db.teams.find({"_id": {"$in": oids}}, {"name": 1, "department": 1}):
                    from task_constants import format_associated_team_label
                    tid = str(t["_id"])
                    team_map[tid] = format_associated_team_label(t.get("name", ""), t.get("department", ""))
        out = serialize_fn(users)
        if isinstance(out, list):
            for row in out:
                tid = row.get("team_id")
                if tid and tid in team_map:
                    row["team_label"] = team_map[tid]
        return out

    @api.post("/users")
    async def create_user(body: UserCreate, user: dict = Depends(require_role("Admin"))):
        email = body.email.lower().strip()
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="Email already exists")
        validate_password_policy(body.password)
        doc = {
            "email": email,
            "name": body.name,
            "role": body.role,
            "high_court": body.high_court if body.role == "CPC" else None,
            "task_role": body.task_role,
            "team_lead_id": body.team_lead_id,
            "password_hash": hash_password(body.password),
            "password_changed_at": now_utc_fn(),
            "password_history": [],
            "created_at": now_utc_fn(),
            "created_by": user["email"],
        }
        result = await db.users.insert_one(doc)
        await audit_fn(user, "users", "create", str(result.inserted_id),
                       [{"field": "user", "old": None, "new": {"email": email, "role": body.role}}])
        return {"id": str(result.inserted_id)}

    @api.put("/users/{user_id}")
    async def update_user(user_id: str, body: UserUpdate, user: dict = Depends(require_role("Admin"))):
        existing = await db.users.find_one({"_id": ObjectId(user_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")
        update = {}
        changes = []
        for f in ["name", "role", "high_court", "task_role", "team_lead_id"]:
            v = getattr(body, f)
            if v is not None and existing.get(f) != v:
                changes.append({"field": f, "old": existing.get(f), "new": v})
                update[f] = v
        if body.role is not None and body.role != "CPC":
            if existing.get("high_court") is not None:
                changes.append({"field": "high_court", "old": existing.get("high_court"), "new": None})
            update["high_court"] = None
        if body.password:
            validate_password_policy(body.password, existing, verify_password, skip_reuse_check=True)
            hist = build_password_history_update(existing, hash_password(body.password), hash_password)
            hist["must_change_password"] = False
            update.update(hist)
            changes.append({"field": "password", "old": "***", "new": "***"})
            await revoke_all_user_sessions(user_id)
        if update:
            await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update})
            await audit_fn(user, "users", "update", user_id, changes)
        return {"ok": True}

    @api.delete("/users/{user_id}")
    async def delete_user(user_id: str, user: dict = Depends(require_role("Admin"))):
        if user_id == user["id"]:
            raise HTTPException(status_code=400, detail="Cannot delete self")
        from team_service import remove_user_from_teams
        await remove_user_from_teams(db, user_id, now_utc_fn)
        await revoke_all_user_sessions(user_id)
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await audit_fn(user, "users", "delete", user_id, [])
        return {"ok": True}

    @api.post("/users/{user_id}/reset-password")
    async def reset_password(user_id: str, user: dict = Depends(require_role("Admin"))):
        target = await db.users.find_one({"_id": ObjectId(user_id)})
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        temp_password = gen_password(12)
        update = build_password_history_update(target, hash_password(temp_password), hash_password)
        update["must_change_password"] = True
        update["password_reset_at"] = now_utc_fn()
        update["password_reset_by"] = user["email"]
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update})
        await revoke_all_user_sessions(user_id)
        await db.login_locks.delete_one({"email": target["email"]})
        await audit_fn(user, "users", "password_reset", user_id,
                       [{"field": "password", "old": "***", "new": "*** (temporary)"}])
        await db.email_outbox.insert_one({
            "to": target["email"],
            "subject": "eCourts PMIS — temporary password",
            "body": (
                "Your PMIS account password was reset by an administrator.\n\n"
                f"Temporary password: {temp_password}\n\n"
                "Sign in and change your password immediately. Do not share this email."
            ),
            "status": "queued",
            "ts": now_utc_fn(),
        })
        return {
            "ok": True,
            "email": target["email"],
            "message": "Temporary password queued for email delivery. User must change it on next login.",
        }

    @api.get("/admin/security/ip-allowlist")
    async def get_ip_allowlist(_: dict = Depends(require_role("Admin"))):
        from security import get_admin_ip_allowlist
        return await get_admin_ip_allowlist(db)

    @api.put("/admin/security/ip-allowlist")
    async def put_ip_allowlist(body: IpAllowlistIn, user: dict = Depends(require_role("Admin"))):
        old = await db.settings.find_one({"key": "admin_ip_allowlist"})
        value = {"enabled": body.enabled, "cidrs": [c.strip() for c in body.cidrs if c.strip()]}
        await db.settings.update_one({"key": "admin_ip_allowlist"}, {"$set": {"value": value}}, upsert=True)
        await audit_fn(user, "admin", "ip_allowlist", "admin_ip_allowlist",
                       [{"field": "admin_ip_allowlist", "old": old.get("value") if old else None, "new": value}])
        return {"ok": True, "value": value}


async def ensure_auth_indexes(database):
    await database.sessions.create_index([("user_id", 1), ("created_at", -1)])
    await database.sessions.create_index("id", unique=True)
    await database.login_challenges.create_index("created_at", expireAfterSeconds=600)
