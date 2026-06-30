"""Security and auth regression tests."""
from datetime import datetime, timezone

import pytest

from auth import hash_password, verify_password
from conftest import (
    auth_headers,
    clear_login_state,
    delete_user,
    extract_token,
    get_captcha_answer,
    insert_user,
    login,
    set_allowlist,
    set_user,
)
from security import (
    password_expired,
    validate_password_policy,
    validate_upload_bytes,
)


def test_password_policy_min_length():
    with pytest.raises(Exception) as exc:
        validate_password_policy("Short1!")
    assert "12" in str(exc.value.detail)


def test_password_policy_complexity():
    with pytest.raises(Exception):
        validate_password_policy("longpasswordonly")


def test_password_history_rejection():
    old_pw = "OldPassword1!"
    new_pw = "NewPassword2@"
    user_record = {
        "password_hash": hash_password(old_pw),
        "password_history": [hash_password(new_pw)],
    }
    with pytest.raises(Exception) as exc:
        validate_password_policy(new_pw, user_record, verify_password)
    assert "last 5" in str(exc.value.detail)


def test_password_expired_after_90_days():
    from datetime import timedelta

    changed = datetime.now(timezone.utc) - timedelta(days=91)
    user = {"password_changed_at": changed}
    assert password_expired(user, lambda: datetime.now(timezone.utc)) is True


def test_upload_rejects_spoofed_pdf():
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    with pytest.raises(Exception) as exc:
        validate_upload_bytes(png_bytes, "pdf")
    detail = str(exc.value.detail)
    assert "does not match" in detail or "detected" in detail


def test_login_captcha_endpoint(client):
    r = client.get("/api/auth/captcha")
    assert r.status_code == 200
    data = r.json()
    assert data.get("captcha_id")
    assert "svg" in data.get("image_svg", "")


def test_unauthenticated_me(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_admin_blocked_without_2fa_setup(client, admin_credentials):
    email, password = admin_credentials
    set_user(email, totp_enabled=False, unset_fields=["totp_secret"])
    try:
        r = login(client, email, password)
        assert r.status_code == 200
        token = extract_token(r)
        assert token
        me = client.get("/api/auth/me", headers=auth_headers(token))
        assert me.status_code == 200
        assert me.json().get("requires_2fa_setup") is True
        blocked = client.get("/api/master/high-courts", headers=auth_headers(token))
        assert blocked.status_code == 403
        assert blocked.json()["detail"]["code"] == "requires_2fa_setup"
    finally:
        set_user(email, totp_enabled=False, unset_fields=["totp_secret"])


def test_must_change_password_blocks_routes(viewer_session):
    client = viewer_session["client"]
    token = viewer_session["token"]
    email = viewer_session["email"]
    set_user(email, must_change_password=True)
    try:
        me = client.get("/api/auth/me", headers=auth_headers(token))
        assert me.status_code == 200
        blocked = client.get("/api/dashboard/summary", headers=auth_headers(token))
        assert blocked.status_code == 403
        assert blocked.json()["detail"]["code"] == "must_change_password"
    finally:
        set_user(email, must_change_password=False)


def test_session_list_revoke_and_refresh(client, viewer_credentials):
    email, password = viewer_credentials
    clear_login_state(email)
    set_user(email, must_change_password=False)

    r1 = login(client, email, password)
    token1 = extract_token(r1)
    assert token1
    sessions = client.get("/api/auth/sessions", headers=auth_headers(token1))
    assert sessions.status_code == 200
    sid = next(s for s in sessions.json() if s.get("is_current"))["id"]

    client.cookies.clear()
    r2 = login(client, email, password)
    token2 = extract_token(r2)
    assert token2
    revoked = client.delete(f"/api/auth/sessions/{sid}", headers=auth_headers(token2))
    assert revoked.status_code == 200

    client.cookies.clear()
    stale = client.get("/api/dashboard/summary", headers=auth_headers(token1))
    assert stale.status_code == 401


def test_viewer_cannot_include_unapproved(client, viewer_credentials):
    email, password = viewer_credentials
    clear_login_state(email)
    set_user(email, must_change_password=False, totp_enabled=False, unset_fields=["totp_secret"])
    r = login(client, email, password)
    assert r.status_code == 200
    token = extract_token(r)
    blocked = client.get(
        "/api/dashboard/summary",
        params={"include_unapproved": "true"},
        headers=auth_headers(token),
    )
    assert blocked.status_code == 403


def test_admin_blocked_from_non_allowlisted_ip(client, admin_credentials):
    email, password = admin_credentials
    set_user(email, totp_enabled=False, unset_fields=["totp_secret"])
    set_allowlist(True, ["203.0.113.0/24"])
    try:
        r = login(client, email, password)
        assert r.status_code == 403
        assert "network" in r.json()["detail"].lower()
    finally:
        set_allowlist(False, [])


def test_third_failure_requires_captcha(client):
    email = "captcha-test@pmis.gov.in"
    password = "WrongPass1!"
    clear_login_state(email)
    delete_user(email)
    insert_user({
        "email": email,
        "name": "Captcha Test",
        "role": "Viewer",
        "password_hash": hash_password("ViewerTest1!@"),
        "password_history": [],
        "password_changed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    })
    try:
        for _ in range(2):
            r = login(client, email, password)
            assert r.status_code == 401
            detail = r.json().get("detail")
            assert not (isinstance(detail, dict) and detail.get("code") == "requires_captcha")

        r3 = login(client, email, password)
        assert r3.status_code == 401
        detail = r3.json()["detail"]
        assert detail["code"] == "requires_captcha"
        assert detail.get("captcha_id")
    finally:
        clear_login_state(email)
        delete_user(email)


def test_fifth_failure_locks_account(client):
    email = "lockout-test@pmis.gov.in"
    password = "WrongPass1!"
    clear_login_state(email)
    delete_user(email)
    insert_user({
        "email": email,
        "name": "Lockout Test",
        "role": "Viewer",
        "password_hash": hash_password("ViewerTest1!@"),
        "password_history": [],
        "password_changed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    })

    def fail_once(captcha_id=None, captcha_answer=None):
        r = login(client, email, password, captcha_id=captcha_id, captcha_answer=captcha_answer)
        detail = r.json().get("detail")
        if isinstance(detail, dict) and detail.get("code") == "requires_captcha":
            cid = detail["captcha_id"]
            ans = get_captcha_answer(cid)
            return login(client, email, password, captcha_id=cid, captcha_answer=ans)
        return r

    try:
        for _ in range(3):
            assert fail_once().status_code == 401
        locked = fail_once()
        assert locked.status_code == 423, locked.text
        assert "locked" in locked.json()["detail"].lower()
    finally:
        clear_login_state(email)
        delete_user(email)
