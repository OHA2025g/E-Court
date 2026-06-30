"""CPC financial tracker field restrictions."""
from conftest import auth_headers, clear_login_state, extract_token, login, _sync_db


def _cpc_token(client):
    clear_login_state("cpc.allahabad@pmis.gov.in")
    r = login(client, "cpc.allahabad@pmis.gov.in", "Cpc@PMIS2026")
    assert r.status_code == 200
    token = extract_token(r)
    assert token
    return token


def test_cpc_financial_update_utilized_and_remarks_only(client):
    token = _cpc_token(client)
    headers = auth_headers(token)
    period = "2026-06"
    component = "e-Sewa Kendras"
    q = {
        "high_court": "Allahabad",
        "component": component,
        "reporting_period": period,
        "district": None,
    }
    _sync_db.financial_entries.update_one(
        q,
        {"$set": {
            **q,
            "fund_target": 100.0,
            "fund_allocated": 90.0,
            "fund_released": 80.0,
            "fund_utilized": 40.0,
            "remarks": "baseline",
        }},
        upsert=True,
    )

    ok = client.post(
        "/api/financial",
        headers=headers,
        json={
            **q,
            "fund_target": 999.0,
            "fund_allocated": 888.0,
            "fund_released": 777.0,
            "fund_utilized": 55.0,
            "remarks": "updated by cpc",
        },
    )
    assert ok.status_code == 200
    row = _sync_db.financial_entries.find_one(q)
    assert row["fund_target"] == 100.0
    assert row["fund_allocated"] == 90.0
    assert row["fund_released"] == 80.0
    assert row["fund_utilized"] == 55.0
    assert row["remarks"] == "updated by cpc"


def test_cpc_financial_cannot_create_directly(client):
    token = _cpc_token(client)
    period = "2026-06"
    component = "CPC Create Block Test Component"
    q = {
        "high_court": "Allahabad",
        "component": component,
        "reporting_period": period,
        "district": None,
    }
    _sync_db.financial_entries.delete_one(q)
    r = client.post(
        "/api/financial",
        headers=auth_headers(token),
        json={
            **q,
            "fund_released": 10.0,
            "fund_utilized": 5.0,
            "remarks": "new",
        },
    )
    assert r.status_code == 403


def test_cpc_financial_bulk_blocked(client):
    token = _cpc_token(client)
    r = client.post(
        "/api/financial/bulk",
        headers=auth_headers(token),
        params={"reporting_period": "2026-06", "dry_run": True},
    )
    assert r.status_code == 403
