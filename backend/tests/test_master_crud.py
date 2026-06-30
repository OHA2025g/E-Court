"""Admin master-data CRUD regression tests."""
from conftest import _sync_db, auth_headers


def test_outcome_subject_create_update_delete(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    name = "Test Subject CRUD"
    renamed = "Test Subject Renamed"

    r = client.post("/api/master/outcome-subjects", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text

    r = client.put(f"/api/master/outcome-subjects/{name}", headers=headers, json={"name": renamed})
    assert r.status_code == 200, r.text
    subjects = client.get("/api/master/outcome-subjects", headers=headers).json()
    assert any(s["name"] == renamed for s in subjects)

    r = client.delete(f"/api/master/outcome-subjects/{renamed}", headers=headers)
    assert r.status_code == 200, r.text


def test_district_create_update_inactive_list(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    hc = "Allahabad"
    name = "Test District Alpha"

    r = client.post("/api/master/districts", headers=headers, json={
        "high_court": hc, "name": name, "active": True,
    })
    assert r.status_code == 200, r.text

    r = client.put("/api/master/districts", headers=headers, params={
        "high_court": hc, "name": name,
    }, json={"high_court": hc, "name": name, "active": False})
    assert r.status_code == 200, r.text

    active_only = client.get("/api/master/districts", headers=headers, params={"high_court": hc}).json()
    assert not any(d["name"] == name for d in active_only)

    all_districts = client.get("/api/master/districts", headers=headers, params={
        "high_court": hc, "include_inactive": True,
    }).json()
    assert any(d["name"] == name and d["active"] is False for d in all_districts)

    r = client.delete("/api/master/districts", headers=headers, params={"high_court": hc, "name": name})
    assert r.status_code == 200, r.text


def test_hc_delete_blocked_when_districts_exist(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    hc = "Test HC District Guard"
    client.post("/api/master/high-courts", headers=headers, json={"name": hc, "active": True})
    client.post("/api/master/districts", headers=headers, json={
        "high_court": hc, "name": "Test District", "active": True,
    })
    try:
        r = client.delete(f"/api/master/high-courts/{hc}", headers=headers)
        assert r.status_code == 400
        assert "districts" in r.json()["detail"].lower()
    finally:
        client.delete("/api/master/districts", headers=headers, params={"high_court": hc, "name": "Test District"})
        client.delete(f"/api/master/high-courts/{hc}", headers=headers)


def test_component_put_still_works(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    comps = client.get("/api/master/components", headers=headers).json()
    assert comps
    comp = comps[0]
    r = client.put(f"/api/master/components/{comp['code']}", headers=headers, json={
        "code": comp["code"], "name": comp["name"], "uom": comp.get("uom", "Count"),
    })
    assert r.status_code == 200, r.text
