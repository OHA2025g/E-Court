"""Dashboard visualisation endpoint tests."""
from conftest import auth_headers, clear_login_state, extract_token, login
from dashboard_agg import resolve_period_pair


def test_resolve_period_pair():
    pair = resolve_period_pair("2026-07")
    assert pair is not None
    assert pair[0] == "2026-07"
    assert pair[1] == "2026-06"


def test_public_progress(client):
    r = client.get("/api/public/progress")
    assert r.status_code == 200
    data = r.json()
    assert "physical" in data
    assert "financial" in data
    assert "outcome" in data
    assert "reporting_percent" in data["outcome"]
    assert "top_outcome_high_courts" in data
    assert "viz" in data
    assert "trend" in data["viz"]
    assert "heatmap" in data["viz"]
    assert "pareto" in data["viz"]
    assert "rag_delta" in data["viz"]
    assert "comparison_period" in data
    assert "bottom_outcome_high_courts" in data
    assert "rag_physical" in data
    assert "hc_rag_counts" in data
    assert "states" in data
    assert isinstance(data["hc_rag_counts"], dict)


def test_heatmap(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/heatmap", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert len(data["components"]) == 17
    assert len(data["cells"]) >= 17


def test_heatmap_outcome(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/heatmap", headers=auth_headers(token), params={"metric": "outcome"})
    assert r.status_code == 200
    data = r.json()
    assert data["metric"] == "outcome"
    assert len(data["subjects"]) == 19
    assert data["row_field"] == "subject"


def test_pareto_outcome(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/pareto-red-flags", headers=auth_headers(token), params={"metric": "outcome"})
    assert r.status_code == 200
    assert r.json()["metric"] == "outcome"


def test_rag_delta_requires_period(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/rag-delta", headers=auth_headers(token),
                    params={"reporting_period": "2026-07"})
    assert r.status_code == 200
    data = r.json()
    assert "turned_green" in data
    assert "net_green" in data
    assert data.get("metric") == "physical"


def test_rag_delta_outcome(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/rag-delta", headers=auth_headers(token),
                    params={"reporting_period": "2026-07", "metric": "outcome"})
    assert r.status_code == 200
    data = r.json()
    assert data["metric"] == "outcome"
    assert data["unit"] == "KPIs"


def test_rag_delta_financial(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/rag-delta", headers=auth_headers(token),
                    params={"reporting_period": "2026-07", "metric": "financial"})
    assert r.status_code == 200
    data = r.json()
    assert data["metric"] == "financial"
    assert data["unit"] == "components"


def test_pareto_red_flags(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/pareto-red-flags", headers=auth_headers(token))
    assert r.status_code == 200
    assert "series" in r.json()


def test_trend_with_milestones(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/trend", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert "periods" in data
    assert "milestones" in data
    if data["periods"]:
        assert "outcome_reported_pct" in data["periods"][0]


def test_states_rag_metric(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/states-rag", headers=auth_headers(token), params={"metric": "financial"})
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_states_rag_outcome(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/states-rag", headers=auth_headers(token), params={"metric": "outcome"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert any(v.get("percent") is not None for v in data.values())


def test_dashboard_summary(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/summary", headers=auth_headers(token), params={"reporting_period": "2026-06"})
    assert r.status_code == 200
    data = r.json()
    assert "physical" in data
    assert "outcome" in data


def test_dashboard_layout(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/layout", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["dashboard_layout"]["widgets"]


def test_dashboard_layout_put(client, viewer_session):
    token = viewer_session["token"]
    headers = auth_headers(token)
    layout = {
        "version": 1,
        "widgets": [
            {"id": "filters", "visible": True, "x": 0, "y": 0, "w": 12, "h": 2, "static": True},
            {"id": "kpi-row", "visible": True, "x": 0, "y": 2, "w": 12, "h": 3},
        ],
    }
    r = client.put("/api/dashboard/layout", headers=headers, json={"dashboard_layout": layout})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    saved = client.get("/api/dashboard/layout", headers=headers).json()
    assert len(saved["dashboard_layout"]["widgets"]) == 2
    client.delete("/api/dashboard/layout", headers=headers)


def test_cpc_states_rag_scope(client):
    import os
    email = os.environ["CPC_DEMO_EMAIL"]
    password = os.environ["CPC_DEMO_PASSWORD"]
    r = login(client, email, password)
    token = extract_token(r)
    if not token:
        return
    resp = client.get("/api/dashboard/states-rag", headers=auth_headers(token))
    assert resp.status_code == 200
    out_scope = [v for v in resp.json().values() if v.get("in_scope") is False]
    assert len(out_scope) >= 1


def test_cpc_dashboard_summary_scoped_to_high_court(client):
    import os
    from conftest import _sync_db
    from cache_layer import cache_invalidate_prefix

    email = os.environ["CPC_DEMO_EMAIL"]
    password = os.environ["CPC_DEMO_PASSWORD"]
    clear_login_state(email)
    r = login(client, email, password)
    token = extract_token(r)
    assert token

    me = client.get("/api/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json().get("high_court") == "Allahabad"

    _sync_db.settings.update_one(
        {"key": "workflow_settings"},
        {"$set": {"value": {"dashboard_require_approval": True, "submission_grace_days": 7, "sla_due_day": 10}}},
        upsert=True,
    )
    cache_invalidate_prefix("dashboard:")

    period = "2026-06"
    _sync_db.physical_entries.update_one(
        {
            "high_court": "Allahabad",
            "component": "e-Sewa Kendras",
            "indicator": "No of sites prepared (in Absolute Count)",
            "reporting_period": period,
            "district": None,
        },
        {"$set": {
            "high_court": "Allahabad",
            "component": "e-Sewa Kendras",
            "indicator": "No of sites prepared (in Absolute Count)",
            "reporting_period": period,
            "target": 50,
            "achieved": 25,
        }},
        upsert=True,
    )
    _sync_db.submissions.delete_many({"high_court": "Allahabad", "reporting_period": period})

    cpc = client.get(
        "/api/dashboard/summary",
        headers=auth_headers(token),
        params={"reporting_period": period},
    )
    assert cpc.status_code == 200
    cpc_phys = cpc.json().get("physical") or {}
    assert cpc_phys.get("target", 0) >= 50

    vr = login(client, os.environ["VIEWER_DEMO_EMAIL"], os.environ["VIEWER_DEMO_PASSWORD"])
    vtoken = extract_token(vr)
    assert vtoken
    viewer = client.get(
        "/api/dashboard/summary",
        headers=auth_headers(vtoken),
        params={"reporting_period": period},
    )
    assert viewer.status_code == 200
    viewer_phys = viewer.json().get("physical") or {}
    assert viewer_phys.get("target", 0) == 0
