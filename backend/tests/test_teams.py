"""Team registry API tests."""
import os

from conftest import _sync_db, auth_headers


def test_list_teams_seeds_defaults(admin_session):
    client = admin_session["client"]
    token = admin_session["token"]
    r = client.get("/api/teams", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert "name" in data[0]
    assert "department" in data[0]
    assert "members" in data[0]


def test_create_team_and_manage_members(admin_session):
    client = admin_session["client"]
    token = admin_session["token"]
    viewer = _sync_db.users.find_one({"email": os.environ["VIEWER_DEMO_EMAIL"].lower()})
    assert viewer
    viewer_id = str(viewer["_id"])

    created = client.post(
        "/api/teams",
        headers=auth_headers(token),
        json={
            "name": "Test PMU",
            "department": "QA Unit",
            "member_ids": [viewer_id],
        },
    )
    assert created.status_code == 200, created.text
    team = created.json()
    assert team["member_count"] == 1
    assert team["members"][0]["id"] == viewer_id

    users_after = client.get("/api/users", headers=auth_headers(token)).json()
    viewer_row = next(u for u in users_after if u["id"] == viewer_id)
    assert viewer_row.get("team_id") == team["id"]
    assert "Test PMU" in (viewer_row.get("team_label") or "")

    updated = client.put(
        f"/api/teams/{team['id']}",
        headers=auth_headers(token),
        json={"member_ids": []},
    )
    assert updated.status_code == 200
    assert updated.json()["member_count"] == 0

    deleted = client.delete(f"/api/teams/{team['id']}", headers=auth_headers(token))
    assert deleted.status_code == 200


def test_teams_require_admin(viewer_session):
    client = viewer_session["client"]
    token = viewer_session["token"]
    r = client.get("/api/teams", headers=auth_headers(token))
    assert r.status_code == 403
