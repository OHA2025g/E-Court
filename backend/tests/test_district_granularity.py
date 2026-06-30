"""District-level tracker rows and HC rollup aggregation tests."""
from datetime import datetime, timezone

from conftest import _sync_db, auth_headers
from rollup import physical_rollup_stages


HC = "Allahabad"
COMPONENT = "e-Sewa Kendras"
INDICATOR = "No of sites prepared (in Absolute Count)"
PERIOD = datetime.now(timezone.utc).strftime("%Y-%m")
DIST_A = "Prayagraj"
DIST_B = "Lucknow"


def _cleanup():
    _sync_db.physical_entries.delete_many({
        "high_court": HC,
        "component": COMPONENT,
        "reporting_period": PERIOD,
    })


def test_district_unique_key_prevents_duplicate(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    _cleanup()
    body = {
        "high_court": HC, "component": COMPONENT, "indicator": INDICATOR,
        "reporting_period": PERIOD, "district": DIST_A,
        "target": 100, "achieved": 50, "remarks": "first",
    }
    r1 = client.post("/api/physical", headers=headers, json=body)
    assert r1.status_code == 200, r1.text
    body["achieved"] = 60
    r2 = client.post("/api/physical", headers=headers, json=body)
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]
    _cleanup()


def test_two_district_rows_roll_up_to_hc_percent(admin_session):
    _cleanup()
    now = datetime.now(timezone.utc)
    base = {
        "high_court": HC, "component": COMPONENT, "indicator": INDICATOR,
        "reporting_period": PERIOD, "percent": None, "rag": "NA", "remarks": None,
        "created_by": "test", "created_at": now, "updated_by": "test", "updated_at": now,
    }
    _sync_db.physical_entries.insert_many([
        {**base, "district": DIST_A, "target": 50, "achieved": 40},
        {**base, "district": DIST_B, "target": 50, "achieved": 30},
    ])
    try:
        rows = _sync_db.physical_entries.aggregate(
            physical_rollup_stages({"high_court": HC, "reporting_period": PERIOD})
        )
        rolled = list(rows)
        assert len(rolled) == 1
        row = rolled[0]
        assert row["target"] == 100
        assert row["achieved"] == 70
    finally:
        _cleanup()


def test_physical_list_district_filter(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    _cleanup()
    now = datetime.now(timezone.utc)
    base = {
        "high_court": HC, "component": COMPONENT, "indicator": INDICATOR,
        "reporting_period": PERIOD, "target": 10, "achieved": 5,
        "percent": 50, "rag": "RED", "remarks": None,
        "created_by": "test", "created_at": now, "updated_by": "test", "updated_at": now,
    }
    _sync_db.physical_entries.insert_many([
        {**base, "district": None},
        {**base, "district": DIST_A},
    ])
    try:
        hc_only = client.get("/api/physical", headers=headers, params={
            "high_court": HC, "reporting_period": PERIOD, "district": "__hc__",
        }).json()
        hc_items = hc_only.get("items", hc_only)
        assert all(r.get("district") is None for r in hc_items)

        dist_rows = client.get("/api/physical", headers=headers, params={
            "high_court": HC, "reporting_period": PERIOD, "district": DIST_A,
        }).json()
        dist_items = dist_rows.get("items", dist_rows)
        assert len(dist_items) == 1
        assert dist_items[0]["district"] == DIST_A
    finally:
        _cleanup()
