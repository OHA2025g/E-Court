"""Tracker export endpoints must honour file_format / format query params."""
from conftest import auth_headers


def test_tracker_exports_respect_file_format(admin_session, monkeypatch):
    # Avoid export rate-limit flakiness across consecutive downloads in one test.
    monkeypatch.setattr("api_rate_limit.enforce_user_export_rate_limit", lambda _uid: None)

    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])

    xlsx = client.get("/api/export/physical", headers=headers, params={"file_format": "xlsx"})
    assert xlsx.status_code == 200
    assert "spreadsheetml" in xlsx.headers.get("content-type", "")
    assert xlsx.content[:2] == b"PK"
    assert ".xlsx" in xlsx.headers.get("content-disposition", "")
    assert "no-store" in xlsx.headers.get("cache-control", "")

    pdf = client.get("/api/export/physical", headers=headers, params={"format": "pdf"})
    assert pdf.status_code == 200
    assert "application/pdf" in pdf.headers.get("content-type", "")
    assert pdf.content[:4] == b"%PDF"
    assert ".pdf" in pdf.headers.get("content-disposition", "")

    fin = client.get("/api/export/financial", headers=headers, params={"file_format": "xlsx"})
    assert fin.status_code == 200
    assert fin.content[:2] == b"PK"

    out = client.get("/api/export/outcome", headers=headers, params={"file_format": "xlsx"})
    assert out.status_code == 200
    assert out.content[:2] == b"PK"
