"""Optional non-Admin 2FA and Scope Charter sign-off tests."""
import pyotp
import pytest

from conftest import auth_headers, clear_login_state, extract_token, login, set_user, _sync_db


def clear_scope_charter_signoffs():
    _sync_db.scope_charter_signoffs.delete_many({})
    _sync_db.settings.delete_one({"key": "scope_charter_status"})


@pytest.fixture(autouse=True)
def _clean_scope_charter():
    clear_scope_charter_signoffs()
    yield
    clear_scope_charter_signoffs()


def test_viewer_optional_2fa_enroll_and_login(client, viewer_credentials):
    email, password = viewer_credentials
    clear_login_state(email)
    set_user(email, must_change_password=False, totp_enabled=False, unset_fields=["totp_secret"])
    try:
        r = login(client, email, password)
        assert r.status_code == 200
        token = extract_token(r)
        assert token

        setup = client.post("/api/auth/2fa/setup", json={"password": password}, headers=auth_headers(token))
        assert setup.status_code == 200
        secret = setup.json()["secret"]
        code = pyotp.TOTP(secret).now()

        verified = client.post("/api/auth/2fa/verify", json={"code": code}, headers=auth_headers(token))
        assert verified.status_code == 200

        client.cookies.clear()
        step1 = login(client, email, password)
        assert step1.status_code == 200
        assert step1.json().get("requires_2fa") is True

        step2 = login(client, email, password, totp_code=pyotp.TOTP(secret).now())
        assert step2.status_code == 200
        assert extract_token(step2)
    finally:
        set_user(email, must_change_password=False, totp_enabled=False, unset_fields=["totp_secret"])


def test_viewer_can_disable_optional_2fa(client, viewer_credentials):
    email, password = viewer_credentials
    secret = pyotp.random_base32()
    clear_login_state(email)
    set_user(email, must_change_password=False, totp_enabled=True, totp_secret=secret)
    try:
        r = login(client, email, password, totp_code=pyotp.TOTP(secret).now())
        token = extract_token(r)
        code = pyotp.TOTP(secret).now()
        disabled = client.post("/api/auth/2fa/disable", json={"code": code}, headers=auth_headers(token))
        assert disabled.status_code == 200
    finally:
        set_user(email, must_change_password=False, totp_enabled=False, unset_fields=["totp_secret"])


def test_twofa_policy_lists_optional_roles(client, viewer_session):
    r = viewer_session["client"].get("/api/auth/2fa/policy", headers=auth_headers(viewer_session["token"]))
    assert r.status_code == 200
    data = r.json()
    assert "Admin" in data["required_roles"]
    assert "Viewer" in data["optional_enrollment_roles"]


def test_scope_charter_signoff_flow(client, admin_session, viewer_session):
    admin = admin_session["client"]
    admin_token = admin_session["token"]
    admin.cookies.clear()

    me = admin.get("/api/auth/me", headers=auth_headers(admin_token))
    assert me.json().get("role") == "Admin"

    charter = admin.get("/api/scope-charter", headers=auth_headers(admin_token))
    assert charter.status_code == 200
    data = charter.json()
    assert data["fully_signed"] is False
    assert data["required_count"] == 4
    assert "markdown" in data

    sign = admin.post(
        "/api/scope-charter/sign",
        json={"slot_id": "doj_nodal", "signer_name": "DoJ Nodal Officer", "affirm": True},
        headers=auth_headers(admin_token),
    )
    assert sign.status_code == 200, sign.text
    assert sign.json()["fully_signed"] is False

    dup = admin.post(
        "/api/scope-charter/sign",
        json={"slot_id": "doj_nodal", "signer_name": "Duplicate", "affirm": True},
        headers=auth_headers(admin_token),
    )
    assert dup.status_code == 409

    viewer = viewer_session["client"]
    viewer.cookies.clear()
    viewer_sign = viewer.post(
        "/api/scope-charter/sign",
        json={"slot_id": "ecommittee_secretariat", "signer_name": "e-Committee Rep", "affirm": True},
        headers=auth_headers(viewer_session["token"]),
    )
    assert viewer_sign.status_code == 200
