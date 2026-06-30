"""Optional Redis cache layer for dashboard endpoints."""
import json
import os
from typing import Optional

_redis = None
TTL = 60


def get_redis():
    global _redis
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    if _redis is None:
        try:
            import redis
            _redis = redis.from_url(url, decode_responses=True)
        except Exception:
            _redis = False
    return _redis if _redis is not False else None


def cache_get(key: str) -> Optional[dict]:
    r = get_redis()
    if not r:
        return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: dict, ttl: int = TTL):
    r = get_redis()
    if not r:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_invalidate_prefix(prefix: str):
    r = get_redis()
    if not r:
        return
    try:
        for k in r.scan_iter(f"{prefix}*"):
            r.delete(k)
    except Exception:
        pass
