"""Smoke tests for extracted route modules."""
from conftest import auth_headers, extract_token, login


def test_public_sso_status(client):
    r = client.get("/api/public/sso")
    assert r.status_code == 200
    assert "enabled" in r.json()


def test_pmu_tasks_list(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/pmu-tasks", headers=auth_headers(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_dpr_list(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dpr", headers=auth_headers(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_ijuris_config(client, admin_session):
    token = admin_session["token"]
    r = client.get("/api/ijuris/config", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert "live_enabled" in data


def test_scheduled_jobs(client, admin_session):
    token = admin_session["token"]
    r = client.get("/api/admin/scheduled-jobs", headers=auth_headers(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_public_trend(client):
    r = client.get("/api/public/trend")
    assert r.status_code == 200
    assert "periods" in r.json()


def test_public_heatmap(client):
    r = client.get("/api/public/heatmap", params={"metric": "financial"})
    assert r.status_code == 200
    assert r.json()["metric"] == "financial"


def test_public_pareto_financial(client):
    r = client.get("/api/public/pareto-red-flags", params={"metric": "financial"})
    assert r.status_code == 200
    assert r.json()["metric"] == "financial"


def test_public_rag_delta(client):
    r = client.get("/api/public/rag-delta", params={"reporting_period": "2026-06"})
    assert r.status_code == 200
    assert "turned_green" in r.json()


def test_pareto_financial_dashboard(client, viewer_session):
    token = viewer_session["token"]
    r = client.get("/api/dashboard/pareto-red-flags", headers=auth_headers(token), params={"metric": "financial"})
    assert r.status_code == 200
    assert r.json()["metric"] == "financial"
