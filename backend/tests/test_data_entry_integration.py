"""Integration tests for data-entry pending items (init-period, rollup, access)."""
import uuid
from datetime import datetime, timezone

from conftest import _sync_db, auth_headers, login, extract_token, clear_login_state
from rollup import outcome_rollup_stages
import os


HC = "Allahabad"
PERIOD = datetime.now(timezone.utc).strftime("%Y-%m")
DIST_A = "Prayagraj"
DIST_B = "Lucknow"


def _cleanup_outcome(subject: str, kpi_id: str):
    _sync_db.outcome_entries.delete_many({
        "high_court": HC,
        "subject": subject,
        "kpi_id": kpi_id,
        "reporting_period": PERIOD,
    })


def test_outcome_district_rollup_counts_one_kpi():
    subject = "eFiling"
    kpi_id = f"ROLLUP-{uuid.uuid4().hex[:8]}"
    _cleanup_outcome(subject, kpi_id)
    now = datetime.now(timezone.utc)
    base = {
        "high_court": HC, "subject": subject, "kpi_id": kpi_id,
        "reporting_period": PERIOD, "granularity": "District",
        "outcome_type": "Absolute", "value_type": "Count",
        "kpi": "Test KPI", "baseline": None, "computed_percent": None,
        "remarks": None, "created_by": "test", "created_at": now,
        "updated_by": "test", "updated_at": now,
    }
    _sync_db.outcome_entries.insert_many([
        {**base, "district": DIST_A, "value": 30},
        {**base, "district": DIST_B, "value": 20},
    ])
    try:
        rolled = list(_sync_db.outcome_entries.aggregate(
            outcome_rollup_stages({"high_court": HC, "reporting_period": PERIOD, "kpi_id": kpi_id})
        ))
        assert len(rolled) == 1
        assert rolled[0]["value"] == 50
    finally:
        _cleanup_outcome(subject, kpi_id)


def test_dashboard_summary_includes_outcome_count(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    r = client.get("/api/dashboard/summary", headers=headers, params={"reporting_period": PERIOD})
    assert r.status_code == 200, r.text
    assert "outcome" in r.json()
    assert "kpi_count" in r.json()["outcome"]


def test_financial_init_period(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    r = client.post("/api/financial/init-period", headers=headers, json={
        "high_court": HC,
        "reporting_period": PERIOD,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] >= 0
    assert data["skipped"] >= 0


def test_outcome_init_period(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    r = client.post("/api/outcome/init-period", headers=headers, json={
        "high_court": HC,
        "reporting_period": PERIOD,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] >= 0
    assert data["skipped"] >= 0


def test_public_progress_includes_outcome(client):
    r = client.get("/api/public/progress")
    assert r.status_code == 200
    data = r.json()
    assert "outcome" in data
    assert "kpi_count" in data["outcome"]
    assert "reported_count" in data["outcome"]


def test_cpc_cannot_create_district(client):
    email = os.environ["CPC_DEMO_EMAIL"]
    password = os.environ["CPC_DEMO_PASSWORD"]
    clear_login_state(email)
    r = login(client, email, password)
    assert r.status_code == 200, r.text
    token = extract_token(r)
    headers = auth_headers(token)
    code = client.post("/api/master/districts", headers=headers, json={
        "high_court": HC, "name": "SmokeTestDistrict", "active": True,
    }).status_code
    assert code == 403
    _sync_db.districts.delete_one({"high_court": HC, "name": "SmokeTestDistrict"})
