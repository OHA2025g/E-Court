"""Narrative review workflow tests."""
import pyotp

from conftest import auth_headers, extract_token, login

ADMIN_TOTP = "JBSWY3DPEHPK3PXP"


def test_dashboard_narrative_includes_review_status(client):
    r = login(client, "admin@pmis.gov.in", "Admin@PMIS2026", totp_code=pyotp.TOTP(ADMIN_TOTP).now())
    assert r.status_code == 200
    token = extract_token(r)
    resp = client.get(
        "/api/dashboard/narrative",
        headers=auth_headers(token),
        params={"reporting_period": "2025-03"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "review_status" in data
    assert data["review_status"] in ("draft", "approved")
    assert "requires_review" in data
    assert len(data.get("narrative", "")) > 20


def test_admin_approve_narrative(client):
    r = login(client, "admin@pmis.gov.in", "Admin@PMIS2026", totp_code=pyotp.TOTP(ADMIN_TOTP).now())
    token = extract_token(r)
    headers = auth_headers(token)

    regen = client.post(
        "/api/admin/narrative/regenerate",
        headers=headers,
        json={"reporting_period": "2025-03"},
    )
    assert regen.status_code == 200

    approve = client.post(
        "/api/admin/narrative/approve",
        headers=headers,
        json={"reporting_period": "2025-03"},
    )
    assert approve.status_code == 200
    body = approve.json()
    assert body["review_status"] == "approved"
    assert body.get("narrative")

    dash = client.get(
        "/api/dashboard/narrative",
        headers=headers,
        params={"reporting_period": "2025-03"},
    )
    assert dash.json()["review_status"] == "approved"
