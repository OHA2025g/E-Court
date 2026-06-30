"""Dashboard AI insights API tests."""
from conftest import auth_headers, extract_token, login


def test_dashboard_ai_insights(client):
    token = extract_token(login(client, "viewer@pmis.gov.in", "View@PMIS2026"))
    r = client.get(
        "/api/dashboard/ai-insights",
        headers=auth_headers(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data.get("insights"), list)
    assert isinstance(data.get("recommendations"), list)
    assert isinstance(data.get("action_items"), list)
    assert isinstance(data.get("action_plan"), list)
    assert len(data["insights"]) >= 1
    assert data.get("source") in ("mistral", "template")
