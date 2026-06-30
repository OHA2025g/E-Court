"""PowerPoint dashboard export tests."""
import pyotp

from conftest import auth_headers, extract_token, login

ADMIN_TOTP = "JBSWY3DPEHPK3PXP"


def test_export_dashboard_pptx(client):
    r = login(client, "admin@pmis.gov.in", "Admin@PMIS2026", totp_code=pyotp.TOTP(ADMIN_TOTP).now())
    assert r.status_code == 200
    token = extract_token(r)
    resp = client.get(
        "/api/export/dashboard",
        headers=auth_headers(token),
        params={"reporting_period": "2025-03"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    assert resp.content[:2] == b"PK"
    assert len(resp.content) > 5000
