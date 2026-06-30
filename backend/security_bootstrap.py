"""Startup security checks and shared outbound URL validation."""
import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

logger = logging.getLogger("pmis")

KNOWN_WEAK_JWT_SECRETS = frozenset({
    "docker-dev-jwt-secret-change-in-prod!!",
    "change-me-to-a-random-32-byte-hex-secret",
    "test-jwt-secret-key-32-chars-min!!",
})

KNOWN_WEAK_PASSWORDS = frozenset({
    "Admin@PMIS2026",
    "Cpc@PMIS2026",
    "View@PMIS2026",
    "Member@PMIS2026",
})

COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
JWT_STRICT = os.environ.get("JWT_STRICT", "false").lower() in ("1", "true", "yes")
APP_ENV = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "development")).lower()
REQUIRE_REDIS = os.environ.get("REQUIRE_REDIS", "false").lower() in ("1", "true", "yes")
WEBHOOK_HTTPS_ONLY = os.environ.get("WEBHOOK_HTTPS_ONLY", "false").lower() in ("1", "true", "yes") or APP_ENV == "production"

_PRIVATE_NETS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

_BLOCKED_HOSTS = frozenset({
    "localhost",
    "mongo",
    "redis",
    "backend",
    "web",
    "metadata.google.internal",
})


def validate_jwt_secret(secret: str) -> None:
    """Fail fast when a weak or short JWT secret is used in strict/production mode."""
    if len(secret) < 32:
        msg = "JWT_SECRET must be at least 32 characters"
        if JWT_STRICT or APP_ENV == "production":
            raise RuntimeError(msg)
        logger.warning("SECURITY: %s (set JWT_STRICT=true in production)", msg)
        return
    if secret in KNOWN_WEAK_JWT_SECRETS:
        msg = "JWT_SECRET is a known default — generate a unique secret for this deployment"
        if JWT_STRICT or APP_ENV == "production":
            raise RuntimeError(msg)
        logger.warning("SECURITY: %s", msg)


def validate_demo_passwords() -> None:
    """Warn or fail when seeded demo passwords are still in use."""
    checks = (
        ("ADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", "")),
        ("CPC_DEMO_PASSWORD", os.environ.get("CPC_DEMO_PASSWORD", "")),
        ("VIEWER_DEMO_PASSWORD", os.environ.get("VIEWER_DEMO_PASSWORD", "")),
        ("TASK_MEMBER_PASSWORD", os.environ.get("TASK_MEMBER_PASSWORD", "")),
    )
    weak = [name for name, value in checks if value in KNOWN_WEAK_PASSWORDS]
    if not weak:
        return
    msg = f"Demo passwords still configured for: {', '.join(weak)}"
    if JWT_STRICT or APP_ENV == "production":
        raise RuntimeError(msg)
    logger.warning("SECURITY: %s", msg)


def validate_production_settings() -> None:
    """Fail fast on unsafe production configuration."""
    if APP_ENV != "production" and not JWT_STRICT:
        return
    cors = os.environ.get("CORS_ORIGINS", "").strip()
    if cors in ("", "*"):
        raise RuntimeError("CORS_ORIGINS must list explicit origins in production")
    if REQUIRE_REDIS and not os.environ.get("REDIS_URL"):
        raise RuntimeError("REDIS_URL is required when REQUIRE_REDIS=true")
    validate_demo_passwords()


def _host_resolves_to_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="URL host could not be resolved") from exc
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            addr = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        for net in _PRIVATE_NETS:
            if addr in net:
                return True
    return False


def validate_outbound_url(url: str, *, https_only: bool = False) -> str:
    """Reject outbound URLs that target private networks or internal service names."""
    https_only = https_only or WEBHOOK_HTTPS_ONLY
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    allowed_schemes = ("https",) if https_only else ("http", "https")
    if scheme not in allowed_schemes:
        raise HTTPException(
            status_code=400,
            detail=f"URL must use {' or '.join(allowed_schemes)}",
        )
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        raise HTTPException(status_code=400, detail="Invalid URL — missing host")
    if host in _BLOCKED_HOSTS:
        raise HTTPException(status_code=400, detail="URL host is not allowed")
    try:
        addr = ipaddress.ip_address(host)
        for net in _PRIVATE_NETS:
            if addr in net:
                raise HTTPException(status_code=400, detail="URL must not target private or link-local addresses")
    except ValueError:
        if _host_resolves_to_private(host):
            raise HTTPException(status_code=400, detail="URL resolves to a private or link-local address")
    return url.strip()
