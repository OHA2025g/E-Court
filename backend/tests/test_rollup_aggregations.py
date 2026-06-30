"""Rollup aggregation and init-period tests."""
from datetime import datetime, timezone

"""Rollup aggregation and init-period tests."""
import uuid
from datetime import datetime, timezone

from conftest import _sync_db, auth_headers
from rollup import physical_national_totals_stages

HC = "Allahabad"
COMPONENT = "e-Sewa Kendras"
INDICATOR = f"TEST Rollup Indicator {uuid.uuid4().hex[:8]}"


def _period():
    return datetime.now(timezone.utc).strftime("%Y-%m")


DIST_A = "Prayagraj"
DIST_B = "Lucknow"


def _cleanup_physical(period: str):
    _sync_db.physical_entries.delete_many({
        "high_court": HC,
        "component": COMPONENT,
        "indicator": INDICATOR,
        "reporting_period": period,
    })


def test_national_totals_rollup_sums_districts():
    period = _period()
    _cleanup_physical(period)
    now = datetime.now(timezone.utc)
    base = {
        "high_court": HC, "component": COMPONENT, "indicator": INDICATOR,
        "reporting_period": period, "percent": None, "rag": "NA", "remarks": None,
        "created_by": "test", "created_at": now, "updated_by": "test", "updated_at": now,
    }
    _sync_db.physical_entries.insert_many([
        {**base, "district": DIST_A, "target": 40, "achieved": 30},
        {**base, "district": DIST_B, "target": 60, "achieved": 40},
    ])
    try:
        rolled = list(_sync_db.physical_entries.aggregate(
            physical_national_totals_stages({"high_court": HC, "reporting_period": period})
        ))
        assert rolled[0]["target"] == 100
        assert rolled[0]["achieved"] == 70
        assert rolled[0]["count"] == 1
    finally:
        _cleanup_physical(period)


def test_public_progress_endpoint_still_ok(client):
    r = client.get("/api/public/progress")
    assert r.status_code == 200
    assert "physical" in r.json()


def test_physical_init_period(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    period = _period()
    r = client.post("/api/physical/init-period", headers=headers, json={
        "high_court": HC,
        "reporting_period": period,
        "component": COMPONENT,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] >= 0
    assert data["skipped"] >= 0
    r2 = client.post("/api/physical/init-period", headers=headers, json={
        "high_court": HC,
        "reporting_period": period,
        "component": COMPONENT,
    })
    assert r2.status_code == 200
    assert r2.json()["created"] == 0
    assert r2.json()["skipped"] >= data["created"]


def test_financial_init_period_idempotent(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    period = _period()
    body = {"high_court": HC, "reporting_period": period}
    r1 = client.post("/api/financial/init-period", headers=headers, json=body)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/financial/init-period", headers=headers, json=body)
    assert r2.status_code == 200, r2.text
    assert r2.json()["created"] == 0
