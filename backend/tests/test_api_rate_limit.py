"""API token rate limiting tests."""
import hashlib
import uuid
from unittest.mock import patch

import pytest
from bson import ObjectId
from fastapi import HTTPException

from conftest import _sync_db
from api_rate_limit import enforce_api_token_rate_limit, reset_api_token_rate_limit


def test_api_token_rate_limit_enforced(client):
    raw = f"rate-limit-test-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token_id = str(_sync_db.api_tokens.insert_one({
        "name": "rate-test",
        "scopes": ["public"],
        "token_hash": token_hash,
        "active": True,
    }).inserted_id)
    reset_api_token_rate_limit(token_id)
    try:
        with patch("api_rate_limit.get_redis", return_value=None), patch("api_rate_limit.API_TOKEN_RATE_LIMIT", 2):
            reset_api_token_rate_limit(token_id)
            url = "/api/public/progress"
            assert client.get(url, headers={"Authorization": f"Bearer {raw}"}).status_code == 200
            assert client.get(url, headers={"Authorization": f"Bearer {raw}"}).status_code == 200
            blocked = client.get(url, headers={"Authorization": f"Bearer {raw}"})
            assert blocked.status_code == 429
    finally:
        _sync_db.api_tokens.delete_one({"_id": ObjectId(token_id)})
        reset_api_token_rate_limit(token_id)


def test_enforce_helper_raises():
    tid = f"unit-{uuid.uuid4().hex}"
    reset_api_token_rate_limit(tid)
    with patch("api_rate_limit.get_redis", return_value=None), patch("api_rate_limit.API_TOKEN_RATE_LIMIT", 1):
        reset_api_token_rate_limit(tid)
        enforce_api_token_rate_limit(tid)
        with pytest.raises(HTTPException) as exc:
            enforce_api_token_rate_limit(tid)
        assert exc.value.status_code == 429
    reset_api_token_rate_limit(tid)
