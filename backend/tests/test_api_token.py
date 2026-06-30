"""API token read-only access tests."""
import hashlib
import uuid

from conftest import _sync_db


def _insert_token(name: str, raw: str, scopes=None):
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    _sync_db.api_tokens.insert_one({
        "name": name,
        "scopes": scopes or ["public"],
        "token_hash": token_hash,
        "active": True,
    })
    return token_hash


def test_api_token_public_progress(client):
    raw = f"test-token-public-{uuid.uuid4().hex}"
    token_hash = _insert_token("test-public", raw)
    try:
        r = client.get(
            "/api/public/progress",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 200
        assert isinstance(r.json(), dict)
    finally:
        _sync_db.api_tokens.delete_one({"token_hash": token_hash})


def test_api_token_scope_blocks_financial(client):
    raw = f"test-token-scope-{uuid.uuid4().hex}"
    token_hash = _insert_token("scope-public-only", raw, scopes=["public"])
    try:
        r = client.get(
            "/api/financial",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 401
    finally:
        _sync_db.api_tokens.delete_one({"token_hash": token_hash})


def test_api_token_dashboard_scope(client):
    raw = f"test-token-dashboard-{uuid.uuid4().hex}"
    token_hash = _insert_token("scope-dashboard", raw, scopes=["dashboard:read"])
    try:
        r = client.get(
            "/api/dashboard/summary",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 200
    finally:
        _sync_db.api_tokens.delete_one({"token_hash": token_hash})


def test_api_token_rejected_on_write(client):
    raw = f"test-token-no-write-{uuid.uuid4().hex}"
    token_hash = _insert_token("read-only", raw)
    try:
        r = client.post(
            "/api/physical",
            headers={"Authorization": f"Bearer {raw}"},
            json={
                "high_court": "Allahabad",
                "component": "e-Sewa Kendras",
                "indicator": "No of sites prepared (in Absolute Count)",
                "reporting_period": "2025-01",
                "achieved": 1,
            },
        )
        assert r.status_code == 401
    finally:
        _sync_db.api_tokens.delete_one({"token_hash": token_hash})
