"""Per-token and per-IP rate limiting."""
import os
import time
from typing import Optional

from fastapi import HTTPException

from cache_layer import get_redis

API_TOKEN_RATE_LIMIT = int(os.environ.get("API_TOKEN_RATE_LIMIT", "120"))
API_TOKEN_RATE_WINDOW = int(os.environ.get("API_TOKEN_RATE_WINDOW", "60"))
LOGIN_IP_RATE_LIMIT = int(os.environ.get("LOGIN_IP_RATE_LIMIT", "30"))
LOGIN_IP_RATE_WINDOW = int(os.environ.get("LOGIN_IP_RATE_WINDOW", "300"))
PUBLIC_IP_RATE_LIMIT = int(os.environ.get("PUBLIC_IP_RATE_LIMIT", "120"))
PUBLIC_IP_RATE_WINDOW = int(os.environ.get("PUBLIC_IP_RATE_WINDOW", "60"))
EXPORT_USER_RATE_LIMIT = int(os.environ.get("EXPORT_USER_RATE_LIMIT", "10"))
EXPORT_USER_RATE_WINDOW = int(os.environ.get("EXPORT_USER_RATE_WINDOW", "300"))

_memory_buckets: dict[str, list[float]] = {}


def _redis_key(token_id: str) -> str:
    return f"api_token_rate:{token_id}"


def _trim_bucket(bucket: list[float], now: float) -> list[float]:
    cutoff = now - API_TOKEN_RATE_WINDOW
    return [t for t in bucket if t >= cutoff]


def check_api_token_rate_limit(token_id: str) -> bool:
    """Return True if request is allowed."""
    now = time.time()
    r = get_redis()
    if r:
        try:
            key = _redis_key(token_id)
            count = r.incr(key)
            if count == 1:
                r.expire(key, API_TOKEN_RATE_WINDOW)
            return count <= API_TOKEN_RATE_LIMIT
        except Exception:
            pass

    bucket = _trim_bucket(_memory_buckets.get(token_id, []), now)
    if len(bucket) >= API_TOKEN_RATE_LIMIT:
        _memory_buckets[token_id] = bucket
        return False
    bucket.append(now)
    _memory_buckets[token_id] = bucket
    return True


def enforce_api_token_rate_limit(token_id: str):
    if not check_api_token_rate_limit(token_id):
        raise HTTPException(
            status_code=429,
            detail=f"API token rate limit exceeded ({API_TOKEN_RATE_LIMIT} requests per {API_TOKEN_RATE_WINDOW}s)",
        )


def reset_api_token_rate_limit(token_id: Optional[str] = None):
    """Test helper — clear counters."""
    if token_id:
        _memory_buckets.pop(token_id, None)
        r = get_redis()
        if r:
            try:
                r.delete(_redis_key(token_id))
            except Exception:
                pass
    else:
        _memory_buckets.clear()


def _ip_key(prefix: str, ip: str) -> str:
    return f"{prefix}:{ip}"


def _check_rate_limit(key: str, limit: int, window: int) -> bool:
    now = time.time()
    r = get_redis()
    if r:
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, window)
            return count <= limit
        except Exception:
            pass
    bucket = _trim_bucket(_memory_buckets.get(key, []), now)
    if len(bucket) >= limit:
        _memory_buckets[key] = bucket
        return False
    bucket.append(now)
    _memory_buckets[key] = bucket
    return True


def enforce_login_ip_rate_limit(ip: str):
    _require_redis_for_rate_limit()
    key = _ip_key("login_ip_rate", ip)
    if not _check_rate_limit(key, LOGIN_IP_RATE_LIMIT, LOGIN_IP_RATE_WINDOW):
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts from this network. Try again later.",
        )


def enforce_public_ip_rate_limit(ip: str):
    _require_redis_for_rate_limit()
    key = _ip_key("public_ip_rate", ip)
    if not _check_rate_limit(key, PUBLIC_IP_RATE_LIMIT, PUBLIC_IP_RATE_WINDOW):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again later.",
        )


def reset_ip_rate_limits(ip: Optional[str] = None):
    """Test helper — clear IP counters."""
    if ip:
        keys = [
            _ip_key("login_ip_rate", ip),
            _ip_key("public_ip_rate", ip),
            f"export_user_rate:{ip}",
        ]
        for key in keys:
            _memory_buckets.pop(key, None)
            r = get_redis()
            if r:
                try:
                    r.delete(key)
                except Exception:
                    pass
    else:
        _memory_buckets.clear()


def _require_redis_for_rate_limit():
    from security_bootstrap import REQUIRE_REDIS
    if REQUIRE_REDIS and not get_redis():
        raise HTTPException(status_code=503, detail="Rate limiting service unavailable")


def enforce_user_export_rate_limit(user_id: str):
    _require_redis_for_rate_limit()
    key = f"export_user_rate:{user_id}"
    if not _check_rate_limit(key, EXPORT_USER_RATE_LIMIT, EXPORT_USER_RATE_WINDOW):
        raise HTTPException(
            status_code=429,
            detail=f"Export rate limit exceeded ({EXPORT_USER_RATE_LIMIT} exports per {EXPORT_USER_RATE_WINDOW}s)",
        )
