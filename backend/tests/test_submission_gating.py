"""Tests for period policy, edit locks, and approved-only dashboard gating."""
from conftest import auth_headers, login, extract_token, _sync_db
import pyotp

ADMIN_TOTP = "JBSWY3DPEHPK3PXP"


def _admin_token(client):
    r = login(client, "admin@pmis.gov.in", "Admin@PMIS2026", totp_code=pyotp.TOTP(ADMIN_TOTP).now())
    assert r.status_code == 200
    return extract_token(r)


def _cpc_token(client):
    r = login(client, "cpc.allahabad@pmis.gov.in", "Cpc@PMIS2026")
    assert r.status_code == 200
    return extract_token(r)


def test_period_status_open(client):
    token = _cpc_token(client)
    r = client.get(
        "/api/workflow/period-status",
        params={"high_court": "Allahabad", "reporting_period": "2025-03"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert "editable" in data
    assert "reason" in data


def test_submit_locks_edits(client):
    token = _cpc_token(client)
    period = "2025-04"
    _sync_db.submissions.delete_many({"high_court": "Allahabad", "reporting_period": period})
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
            "achieved": 10,
            "target": 100,
        }},
        upsert=True,
    )
    r = client.post(
        "/api/submissions/submit",
        json={"high_court": "Allahabad", "reporting_period": period},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    r2 = client.post(
        "/api/physical",
        json={
            "high_court": "Allahabad",
            "component": "e-Sewa Kendras",
            "indicator": "No of sites prepared (in Absolute Count)",
            "reporting_period": period,
            "achieved": 1,
        },
        headers=auth_headers(token),
    )
    assert r2.status_code == 403


def test_approved_match_filter_excludes_unapproved(client):
    _sync_db.settings.update_one(
        {"key": "workflow_settings"},
        {"$set": {"value": {"dashboard_require_approval": True, "submission_grace_days": 7, "sla_due_day": 10}}},
        upsert=True,
    )
    period = "2025-05"
    _sync_db.submissions.delete_many({"reporting_period": period})
    token = _admin_token(client)
    r = client.get(
        "/api/dashboard/summary",
        params={"reporting_period": period},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    summary = r.json()
    assert summary.get("physical_total_target", 0) == 0 or summary.get("entry_count", 0) == 0

    _sync_db.submissions.insert_one({
        "high_court": "Allahabad",
        "reporting_period": period,
        "status": "Approved",
    })
    r2 = client.get(
        "/api/dashboard/summary",
        params={"reporting_period": period, "include_unapproved": False},
        headers=auth_headers(token),
    )
    assert r2.status_code == 200


def test_admin_period_override(client):
    token = _admin_token(client)
    period = "2025-06"
    _sync_db.submissions.update_one(
        {"high_court": "Allahabad", "reporting_period": period},
        {"$set": {"status": "Submitted"}},
        upsert=True,
    )
    r = client.post(
        "/api/admin/periods/override",
        json={
            "high_court": "Allahabad",
            "reporting_period": period,
            "reason": "Correction needed",
            "hours": 2,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    assert "edit_override_until" in r.json()
