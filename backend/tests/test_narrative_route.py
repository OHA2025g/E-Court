"""Dashboard narrative API tests."""
import pyotp

from conftest import auth_headers, extract_token, login

ADMIN_TOTP = "JBSWY3DPEHPK3PXP"


def test_dashboard_narrative(client):
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
    assert "narrative" in data
    assert len(data["narrative"]) > 20
    assert "physical" in data["narrative"].lower() or "Physical" in data["narrative"] or "%" in data["narrative"]
