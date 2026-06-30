"""Task Management module tests."""
from conftest import _sync_db, clear_login_state, login, auth_headers, extract_token


def test_tasks_meta(client, admin_session):
    h = auth_headers(admin_session["token"])
    r = client.get("/api/tasks/meta", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["task_role"] == "manager"
    assert "permissions" in data
    assert "Critical" in data["priorities"]
    assert len(data.get("associated_teams", [])) >= 1
    assert "team" in data["associated_teams"][0]
    assert "members" in data["associated_teams"][0]


def test_manager_create_and_list(client, admin_session):
    h = auth_headers(admin_session["token"])
    r = client.post("/api/tasks", headers=h, json={
        "title": "Test integration task",
        "description": "Automated test task",
        "priority": "High",
        "evidence_required": False,
    })
    assert r.status_code == 200
    task = r.json()
    assert task["task_code"].startswith("TASK-")
    assert task["status"] in ("UNASSIGNED", "ASSIGNED_TO_TEAM_LEAD")

    listing = client.get("/api/tasks", headers=h)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1


def test_member_cannot_view_unassigned_manager_task(client, admin_session):
    from auth import hash_password
    from datetime import datetime, timezone

    email = "isolated-member@pmis.gov.in"
    if not _sync_db.users.find_one({"email": email}):
        _sync_db.users.insert_one({
            "email": email,
            "name": "Isolated Member",
            "role": "Viewer",
            "task_role": "team_member",
            "password_hash": hash_password("Member@PMIS2026"),
            "password_history": [],
            "password_changed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "created_by": "test",
        })

    h = auth_headers(admin_session["token"])
    create = client.post("/api/tasks", headers=h, json={
        "title": "Private manager task",
        "description": "Should not leak",
        "priority": "Low",
    })
    task_id = create.json()["id"]

    clear_login_state(email)
    member_login = login(client, email, "Member@PMIS2026")
    assert member_login.status_code == 200
    member_h = auth_headers(extract_token(member_login))

    detail = client.get(f"/api/tasks/{task_id}", headers=member_h)
    assert detail.status_code == 403


def test_manager_dashboard(client, admin_session):
    h = auth_headers(admin_session["token"])
    r = client.get("/api/tasks/manager/dashboard", headers=h)
    assert r.status_code == 200
    assert "stats" in r.json()


def test_team_lead_dashboard(client):
    email = "cpc.allahabad@pmis.gov.in"
    clear_login_state(email)
    r = login(client, email, "Cpc@PMIS2026")
    assert r.status_code == 200
    h = auth_headers(extract_token(r))
    resp = client.get("/api/tasks/team-lead/dashboard", headers=h)
    assert resp.status_code == 200
    assert "stats" in resp.json()


def test_assign_member_submit_verify_flow(client, admin_session):
    """Full workflow: assign lead/member → accept → start → submit → team lead verify → closed."""
    h = auth_headers(admin_session["token"])
    lead = _sync_db.users.find_one({"email": "cpc.allahabad@pmis.gov.in"})
    member = _sync_db.users.find_one({"email": "member@pmis.gov.in"})
    assert lead and member, "Seed users required for workflow test"

    create = client.post("/api/tasks", headers=h, json={
        "title": "Workflow integration task",
        "description": "Assignment through closure",
        "priority": "Medium",
        "evidence_required": False,
        "manager_final_approval_required": False,
    })
    assert create.status_code == 200
    task_id = create.json()["id"]

    r = client.post(f"/api/tasks/{task_id}/assign-team-lead", headers=h, json={
        "user_id": str(lead["_id"]),
        "remarks": "Assign lead for workflow test",
    })
    assert r.status_code == 200

    r = client.post(f"/api/tasks/{task_id}/assign-member", headers=h, json={
        "user_id": str(member["_id"]),
        "remarks": "Assign member for workflow test",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "ASSIGNED_TO_TEAM_MEMBER"

    member_email = "member@pmis.gov.in"
    clear_login_state(member_email)
    member_login = login(client, member_email, "Member@PMIS2026")
    assert member_login.status_code == 200
    mh = auth_headers(extract_token(member_login))

    r = client.post(f"/api/tasks/{task_id}/accept", headers=mh)
    assert r.status_code == 200
    assert r.json()["status"] == "ACCEPTED"

    r = client.post(f"/api/tasks/{task_id}/start", headers=mh)
    assert r.status_code == 200
    assert r.json()["status"] == "IN_PROGRESS"

    r = client.post(f"/api/tasks/{task_id}/submit-approval", headers=mh)
    assert r.status_code == 200
    assert r.json()["status"] == "SUBMITTED_FOR_APPROVAL"

    lead_email = "cpc.allahabad@pmis.gov.in"
    clear_login_state(lead_email)
    lead_login = login(client, lead_email, "Cpc@PMIS2026")
    assert lead_login.status_code == 200
    lh = auth_headers(extract_token(lead_login))

    r = client.post(f"/api/tasks/{task_id}/verify", headers=lh, json={
        "decision": "Verified",
        "remarks": "Workflow test verified",
        "checklist": {
            "resolution_matches": True,
            "evidence_uploaded": True,
            "evidence_relevant": True,
            "no_dependency_pending": True,
            "sla_checked": True,
        },
    })
    assert r.status_code == 200
    assert r.json()["status"] == "CLOSED"


def test_team_lead_reject_sends_rework(client, admin_session):
    """Submitted task rejected by team lead returns to REWORK_REQUIRED."""
    h = auth_headers(admin_session["token"])
    lead = _sync_db.users.find_one({"email": "cpc.allahabad@pmis.gov.in"})
    member = _sync_db.users.find_one({"email": "member@pmis.gov.in"})
    assert lead and member

    create = client.post("/api/tasks", headers=h, json={
        "title": "Reject workflow task",
        "description": "Rework path",
        "priority": "Medium",
        "evidence_required": False,
        "manager_final_approval_required": False,
    })
    task_id = create.json()["id"]

    client.post(f"/api/tasks/{task_id}/assign-team-lead", headers=h, json={"user_id": str(lead["_id"])})
    client.post(f"/api/tasks/{task_id}/assign-member", headers=h, json={"user_id": str(member["_id"])})

    clear_login_state("member@pmis.gov.in")
    mh = auth_headers(extract_token(login(client, "member@pmis.gov.in", "Member@PMIS2026")))
    client.post(f"/api/tasks/{task_id}/accept", headers=mh)
    client.post(f"/api/tasks/{task_id}/start", headers=mh)
    client.post(f"/api/tasks/{task_id}/submit-approval", headers=mh)

    clear_login_state("cpc.allahabad@pmis.gov.in")
    lh = auth_headers(extract_token(login(client, "cpc.allahabad@pmis.gov.in", "Cpc@PMIS2026")))
    r = client.post(f"/api/tasks/{task_id}/verify", headers=lh, json={
        "decision": "Rejected",
        "remarks": "Needs more detail",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "REWORK_REQUIRED"


def test_team_lead_escalates_task(client, admin_session):
    h = auth_headers(admin_session["token"])
    lead = _sync_db.users.find_one({"email": "cpc.allahabad@pmis.gov.in"})
    create = client.post("/api/tasks", headers=h, json={
        "title": "Escalation test task",
        "description": "Escalate to manager",
        "priority": "High",
        "evidence_required": False,
    })
    task_id = create.json()["id"]
    client.post(f"/api/tasks/{task_id}/assign-team-lead", headers=h, json={"user_id": str(lead["_id"])})

    clear_login_state("cpc.allahabad@pmis.gov.in")
    lh = auth_headers(extract_token(login(client, "cpc.allahabad@pmis.gov.in", "Cpc@PMIS2026")))
    r = client.post(f"/api/tasks/{task_id}/escalate", headers=lh, json={"reason": "Blocked on vendor"})
    assert r.status_code == 200
    assert r.json()["status"] == "ESCALATED"


def test_member_marks_task_blocked(client, admin_session):
    h = auth_headers(admin_session["token"])
    lead = _sync_db.users.find_one({"email": "cpc.allahabad@pmis.gov.in"})
    member = _sync_db.users.find_one({"email": "member@pmis.gov.in"})
    create = client.post("/api/tasks", headers=h, json={
        "title": "Blocked workflow task",
        "description": "Member marks blocked",
        "priority": "Medium",
        "evidence_required": False,
    })
    task_id = create.json()["id"]
    client.post(f"/api/tasks/{task_id}/assign-team-lead", headers=h, json={"user_id": str(lead["_id"])})
    client.post(f"/api/tasks/{task_id}/assign-member", headers=h, json={"user_id": str(member["_id"])})

    clear_login_state("member@pmis.gov.in")
    mh = auth_headers(extract_token(login(client, "member@pmis.gov.in", "Member@PMIS2026")))
    client.post(f"/api/tasks/{task_id}/accept", headers=mh)
    client.post(f"/api/tasks/{task_id}/start", headers=mh)
    r = client.post(f"/api/tasks/{task_id}/mark-blocked", headers=mh, json={"reason": "Waiting on vendor"})
    assert r.status_code == 200
    assert r.json()["status"] == "BLOCKED"


def test_tasks_export_csv_xlsx_pdf(client, admin_session):
    h = auth_headers(admin_session["token"])
    client.post("/api/tasks", headers=h, json={
        "title": "Export format task",
        "description": "For export tests",
        "priority": "Low",
        "evidence_required": False,
    })

    csv_r = client.get("/api/tasks/export", headers=h, params={"format": "csv"})
    assert csv_r.status_code == 200
    assert "text/csv" in csv_r.headers.get("content-type", "")
    assert b"Task Code" in csv_r.content

    xlsx_r = client.get("/api/tasks/export", headers=h, params={"format": "xlsx"})
    assert xlsx_r.status_code == 200
    assert "spreadsheetml" in xlsx_r.headers.get("content-type", "")
    assert xlsx_r.content[:2] == b"PK"

    pdf_r = client.get("/api/tasks/export", headers=h, params={"format": "pdf"})
    assert pdf_r.status_code == 200
    assert "pdf" in pdf_r.headers.get("content-type", "")
    assert pdf_r.content[:4] == b"%PDF"
    assert len(pdf_r.content) > 500


def test_bulk_assign_team_lead_and_cancel(client, admin_session):
    h = auth_headers(admin_session["token"])
    lead = _sync_db.users.find_one({"email": "cpc.allahabad@pmis.gov.in"})
    task_ids = []
    for i in range(2):
        r = client.post("/api/tasks", headers=h, json={
            "title": f"Bulk test task {i}",
            "description": "Bulk assign test",
            "priority": "Medium",
            "evidence_required": False,
        })
        assert r.status_code == 200
        task_ids.append(r.json()["id"])

    bulk_lead = client.post("/api/tasks/bulk/assign-team-lead", headers=h, json={
        "task_ids": task_ids,
        "user_id": str(lead["_id"]),
        "remarks": "Bulk lead assignment",
    })
    assert bulk_lead.status_code == 200
    body = bulk_lead.json()
    assert len(body["succeeded"]) == 2
    assert body["failed"] == []

    for tid in task_ids:
        doc = _sync_db.tm_tasks.find_one({"id": tid})
        assert doc["assigned_team_lead_id"] == str(lead["_id"])
        assert doc["status"] == "ASSIGNED_TO_TEAM_LEAD"

    bulk_cancel = client.post("/api/tasks/bulk/cancel", headers=h, json={
        "task_ids": task_ids,
        "remarks": "No longer needed",
    })
    assert bulk_cancel.status_code == 200
    assert len(bulk_cancel.json()["succeeded"]) == 2
    for tid in task_ids:
        assert _sync_db.tm_tasks.find_one({"id": tid})["status"] == "CANCELLED"
