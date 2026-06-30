"""Cabinet brief PDF generation tests."""


def test_cabinet_brief_export_pdf(client, viewer_session):
    from conftest import auth_headers
    token = viewer_session["token"]
    r = client.get("/api/export/cabinet-brief", headers=auth_headers(token), params={"reporting_period": "2026-06"})
    assert r.status_code == 200
    assert "pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"
    # AI Executive Brief + KPI tables produce a multi-section brief (compressed streams in PDF body).
    assert len(r.content) > 5000
