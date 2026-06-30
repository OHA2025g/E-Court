"""Email worker, iJuris ingest, and scheduled delivery tests."""
import uuid
from unittest.mock import patch

from conftest import _sync_db, auth_headers


def test_email_worker_status(client, admin_session):
    token = admin_session["token"]
    r = client.get("/api/admin/email-worker/status", headers=auth_headers(token))
    assert r.status_code == 200
    assert "smtp_configured" in r.json()


def test_email_drain_requires_smtp(client, admin_session):
    token = admin_session["token"]
    r = client.post("/api/admin/email-outbox/drain", headers=auth_headers(token))
    assert r.status_code == 503


def test_email_drain_sends_queued(client, admin_session):
    _sync_db.email_outbox.insert_one({
        "to": "test@example.com",
        "subject": "PMIS test",
        "body": "Hello",
        "ts": "2026-01-01T00:00:00+00:00",
        "status": "queued",
    })

    token = admin_session["token"]
    smtp_settings = {
        "host": "smtp.test", "port": 587, "user": "u", "password": "p",
        "from_addr": "noreply@test.gov.in", "use_tls": True,
    }
    with patch("email_worker.smtp_configured", return_value=True), \
         patch("email_worker._smtp_settings", return_value=smtp_settings), \
         patch("email_worker.send_smtp_message") as mock_send:
        r = client.post("/api/admin/email-outbox/drain", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["sent"] >= 1
        mock_send.assert_called()


def test_ijuris_ingest_stub_physical(client, admin_session):
    token = admin_session["token"]
    period = "2026-06"
    indicator = f"iJuris test indicator {uuid.uuid4().hex[:8]}"
    payload = {
        "high_court": "Allahabad",
        "component": "e-Sewa Kendras",
        "indicator": indicator,
        "reporting_period": period,
        "target": 1000,
        "achieved": 500,
    }
    try:
        r = client.post(
            "/api/ijuris/ingest",
            headers=auth_headers(token),
            json={"record_type": "physical", "payload": payload},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "accepted"
        assert "stub" in data["mode"]
    finally:
        _sync_db.physical_entries.delete_many({
            "high_court": payload["high_court"],
            "component": payload["component"],
            "indicator": indicator,
            "reporting_period": period,
        })


def test_scheduled_delivery_pdf(client, admin_session):
    token = admin_session["token"]
    headers = auth_headers(token)
    r = client.post("/api/admin/scheduled-deliveries/run-now", headers=headers)
    assert r.status_code == 200
    items = client.get("/api/admin/scheduled-deliveries", headers=headers).json()
    assert len(items) >= 1
    delivery_id = items[0]["id"]
    pdf = client.get(f"/api/admin/scheduled-deliveries/{delivery_id}/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
