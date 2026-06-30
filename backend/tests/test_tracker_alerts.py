"""Tracker RED / threshold alerts on create paths."""
import uuid

from conftest import _sync_db, auth_headers


def _seed_webhook():
    doc = {
        "name": "test-hook",
        "url": "https://example.com/webhook",
        "events": ["rag_change", "submission_status"],
        "active": True,
    }
    result = _sync_db.webhooks.insert_one(doc)
    return result.inserted_id


def test_physical_create_red_enqueues_webhook(client, admin_session):
    token = admin_session["token"]
    period = "2026-06"
    indicator = f"alert-test-{uuid.uuid4().hex[:8]}"
    hook_id = _seed_webhook()
    _sync_db.webhook_outbox.delete_many({"payload.indicator": indicator})
    try:
        r = client.post(
            "/api/physical",
            headers=auth_headers(token),
            json={
                "high_court": "Allahabad",
                "component": "e-Sewa Kendras",
                "indicator": indicator,
                "reporting_period": period,
                "target": 100,
                "achieved": 10,
            },
        )
        assert r.status_code == 200
        outbox = _sync_db.webhook_outbox.find_one({"payload.indicator": indicator})
        assert outbox is not None
        assert outbox["event"] == "rag_change"
        assert outbox["payload"]["tracker"] == "physical"
        assert outbox["payload"]["rag"] == "RED"
    finally:
        _sync_db.physical_entries.delete_many({"indicator": indicator})
        _sync_db.webhook_outbox.delete_many({"payload.indicator": indicator})
        _sync_db.webhooks.delete_one({"_id": hook_id})


def test_financial_create_red_enqueues_webhook(client, admin_session):
    token = admin_session["token"]
    period = "2026-06"
    component = f"Fin Alert {uuid.uuid4().hex[:6]}"
    hook_id = _seed_webhook()
    _sync_db.webhook_outbox.delete_many({"payload.component": component})
    try:
        r = client.post(
            "/api/financial",
            headers=auth_headers(token),
            json={
                "high_court": "Allahabad",
                "component": component,
                "reporting_period": period,
                "fund_released": 100,
                "fund_utilized": 10,
            },
        )
        assert r.status_code == 200
        outbox = _sync_db.webhook_outbox.find_one({"payload.component": component})
        assert outbox is not None
        assert outbox["event"] == "rag_change"
        assert outbox["payload"]["tracker"] == "financial"
    finally:
        _sync_db.financial_entries.delete_many({"component": component})
        _sync_db.webhook_outbox.delete_many({"payload.component": component})
        _sync_db.webhooks.delete_one({"_id": hook_id})


def test_outcome_create_threshold_enqueues_webhook(client, admin_session):
    token = admin_session["token"]
    period = "2026-06"
    kpi_id = f"KPI-{uuid.uuid4().hex[:6]}"
    hook_id = _seed_webhook()
    _sync_db.webhook_outbox.delete_many({"payload.kpi_id": kpi_id})
    try:
        r = client.post(
            "/api/outcome",
            headers=auth_headers(token),
            json={
                "high_court": "Allahabad",
                "granularity": "District",
                "district": "Lucknow",
                "subject": "Case Clearance",
                "kpi_id": kpi_id,
                "outcome_type": "Relative",
                "baseline": 100,
                "value": 50,
                "reporting_period": period,
            },
        )
        assert r.status_code == 200
        outbox = _sync_db.webhook_outbox.find_one({"payload.kpi_id": kpi_id})
        assert outbox is not None
        assert outbox["payload"]["tracker"] == "outcome"
        assert outbox["payload"]["computed_percent"] == 50.0
    finally:
        _sync_db.outcome_entries.delete_many({"kpi_id": kpi_id})
        _sync_db.webhook_outbox.delete_many({"payload.kpi_id": kpi_id})
        _sync_db.webhooks.delete_one({"_id": hook_id})
