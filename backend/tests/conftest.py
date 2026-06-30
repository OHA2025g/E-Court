import os
import sys
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("MONGO_URL", os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
os.environ.setdefault("DB_NAME", os.environ.get("DB_NAME", "pmis_ecourts"))
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-32-chars-min!!")
os.environ.setdefault("ADMIN_EMAIL", "admin@pmis.gov.in")
os.environ.setdefault("ADMIN_PASSWORD", "Admin@PMIS2026")
os.environ.setdefault("VIEWER_DEMO_EMAIL", "viewer@pmis.gov.in")
os.environ.setdefault("VIEWER_DEMO_PASSWORD", "View@PMIS2026")
os.environ.setdefault("CPC_DEMO_EMAIL", "cpc.allahabad@pmis.gov.in")
os.environ.setdefault("CPC_DEMO_PASSWORD", "Cpc@PMIS2026")
os.environ.setdefault("DASHBOARD_REQUIRE_APPROVAL", "false")
os.environ.setdefault("LOGIN_IP_RATE_LIMIT", "100000")
os.environ.setdefault("PUBLIC_IP_RATE_LIMIT", "100000")

ADMIN_TOTP_SECRET = "JBSWY3DPEHPK3PXP"

from server import app  # noqa: E402

_sync_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email, password, totp_code=None, captcha_id=None, captcha_answer=None):
    payload = {"email": email, "password": password}
    if totp_code:
        payload["totp_code"] = totp_code
    if captcha_id:
        payload["captcha_id"] = captcha_id
        payload["captcha_answer"] = captcha_answer
    return client.post("/api/auth/login", json=payload)


def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def extract_token(response):
    token = response.cookies.get("access_token")
    if token:
        return token
    data = response.json() if response.content else {}
    return data.get("access_token")


def clear_login_state(email):
    email = email.lower()
    _sync_db.login_attempts.delete_many({"email": email})
    _sync_db.login_locks.delete_one({"email": email})


def set_user(email, unset_fields=None, **fields):
    update = {}
    if fields:
        update["$set"] = fields
    if unset_fields:
        update["$unset"] = {field: "" for field in unset_fields}
    _sync_db.users.update_one({"email": email.lower()}, update)


def set_allowlist(enabled, cidrs=None):
    _sync_db.settings.update_one(
        {"key": "admin_ip_allowlist"},
        {"$set": {"value": {"enabled": enabled, "cidrs": cidrs or []}}},
        upsert=True,
    )


def get_captcha_answer(captcha_id):
    doc = _sync_db.login_challenges.find_one({"id": captcha_id})
    return doc["answer"] if doc else None


def delete_user(email):
    _sync_db.users.delete_one({"email": email.lower()})


def insert_user(doc):
    _sync_db.users.insert_one(doc)


@pytest.fixture
def viewer_credentials():
    return os.environ["VIEWER_DEMO_EMAIL"], os.environ["VIEWER_DEMO_PASSWORD"]


@pytest.fixture
def admin_credentials():
    return os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def viewer_session(client, viewer_credentials):
    email, password = viewer_credentials
    clear_login_state(email)
    set_user(email, must_change_password=False, totp_enabled=False, unset_fields=["totp_secret"])
    r = login(client, email, password)
    assert r.status_code == 200, r.text
    token = extract_token(r)
    assert token, r.json()
    yield {"email": email, "token": token, "client": client}
    set_user(email, must_change_password=False)


@pytest.fixture
def admin_session(client, admin_credentials):
    email, password = admin_credentials
    clear_login_state(email)
    set_user(email, must_change_password=False, totp_enabled=True, totp_secret=ADMIN_TOTP_SECRET)
    totp_code = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
    r = login(client, email, password, totp_code=totp_code)
    assert r.status_code == 200, r.text
    token = extract_token(r)
    assert token, r.json()
    yield {"email": email, "token": token, "client": client}
    set_user(email, must_change_password=False, totp_enabled=True, totp_secret=ADMIN_TOTP_SECRET)
