"""Non-admin roles cannot create tracker entries, bulk upload, or init-period."""
from conftest import auth_headers, clear_login_state, extract_token, login, _sync_db


def _cpc_token(client):
    clear_login_state("cpc.allahabad@pmis.gov.in")
    r = login(client, "cpc.allahabad@pmis.gov.in", "Cpc@PMIS2026")
    assert r.status_code == 200
    token = extract_token(r)
    assert token
    return token


PERIOD = "2026-06"
HC = "Allahabad"


def test_cpc_physical_cannot_create(client):
    token = _cpc_token(client)
    q = {
        "high_court": HC,
        "component": "CPC Physical Create Block",
        "indicator": "Test Indicator",
        "reporting_period": PERIOD,
        "district": None,
    }
    _sync_db.physical_entries.delete_one(q)
    r = client.post("/api/physical", headers=auth_headers(token), json={**q, "achieved": 1.0})
    assert r.status_code == 403


def test_cpc_outcome_cannot_create(client):
    token = _cpc_token(client)
    q = {
        "high_court": HC,
        "component": "CPC Outcome Create Block",
        "subject": "CPC Outcome Create Block",
        "kpi_id": "CPC_OUTCOME_CREATE_BLOCK",
        "reporting_period": PERIOD,
        "granularity": "State",
        "district": None,
    }
    _sync_db.outcome_entries.delete_one(q)
    r = client.post(
        "/api/outcome",
        headers=auth_headers(token),
        json={**q, "outcome_type": "Absolute", "value_type": "Count", "value": 10.0},
    )
    assert r.status_code == 403


def test_cpc_init_period_blocked(client):
    token = _cpc_token(client)
    for path in ("/api/physical/init-period", "/api/financial/init-period", "/api/outcome/init-period"):
        r = client.post(
            path,
            headers=auth_headers(token),
            json={"high_court": HC, "reporting_period": PERIOD},
        )
        assert r.status_code == 403, path


def test_cpc_physical_bulk_blocked(client):
    token = _cpc_token(client)
    r = client.post(
        "/api/physical/bulk",
        headers=auth_headers(token),
        params={"reporting_period": PERIOD, "dry_run": True},
    )
    assert r.status_code == 403


def test_cpc_outcome_bulk_blocked(client):
    token = _cpc_token(client)
    r = client.post(
        "/api/outcome/bulk",
        headers=auth_headers(token),
        params={"reporting_period": PERIOD, "dry_run": True},
    )
    assert r.status_code == 403
