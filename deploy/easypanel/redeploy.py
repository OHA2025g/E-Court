#!/usr/bin/env python3
"""Reliable Easypanel redeploy for eCourts PMIS.

Fixes the failure modes we hit in production:
  - Double-trigger (webhook + deployService) overloaded the Docker builder (429 / hangs)
  - Parallel frontend+backend deploys competed for the same builder
  - Stale deploy tokens returned "Deploying..." without pulling latest main
  - Script exited before verifying the new commit SHA was live

Usage:
  export EASYPANEL_EMAIL='...'
  export EASYPANEL_PASSWORD='...'
  ./deploy/easypanel/redeploy.py                # both, wait for SHA
  ./deploy/easypanel/redeploy.py frontend
  ./deploy/easypanel/redeploy.py backend
  ./deploy/easypanel/redeploy.py both --no-wait
  ./deploy/easypanel/redeploy.py status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional

PANEL_URL = os.environ.get("EASYPANEL_URL", "http://31.97.207.166:3000").rstrip("/")
PROJECT = os.environ.get("EASYPANEL_PROJECT", "ecourt")
OWNER = "OHA2025g"
REPO = "E-Court"
REF = "main"

SERVICES = {
    "frontend": {"path": "/frontend/", "cachebust": True},
    "backend": {"path": "/backend/", "cachebust": False},
}


class PanelError(RuntimeError):
    pass


def _request(
    method: str,
    path: str,
    *,
    token: Optional[str] = None,
    payload: Any = None,
    timeout: float = 45,
) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        PANEL_URL + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            if not raw.strip():
                return {}
            return json.loads(raw, strict=False)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:800]
        raise PanelError(f"{method} {path} → HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise PanelError(f"{method} {path} → {exc}") from exc


def login(email: str, password: str) -> str:
    # Prefer OpenAPI /login, fall back to rpc shape used by the panel UI.
    try:
        data = _request(
            "POST",
            "/api/rpc/auth/login",
            payload={"json": {"email": email, "password": password}},
        )
        return data["json"]["token"]
    except PanelError:
        data = _request(
            "POST",
            "/api/login",
            payload={"email": email, "password": password},
        )
        if isinstance(data, dict) and "token" in data:
            return data["token"]
        if isinstance(data, dict) and "json" in data:
            return data["json"]["token"]
        raise PanelError(f"Unexpected login response: {data!r}")


def github_main_sha() -> str:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/commits/{REF}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ecourts-redeploy"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["sha"]


def inspect(token: str, service: str) -> dict:
    data = _request(
        "POST",
        "/api/rpc/services/app/inspectService",
        token=token,
        payload={"json": {"projectName": PROJECT, "serviceName": service}},
    )
    return data["json"]


def list_actions(token: str, service: Optional[str] = None) -> list:
    # Avoid `limit` query param — OpenAPI marks it as number and the panel
    # rejects stringified query values with HTTP 400.
    qs = f"projectName={PROJECT}"
    if service:
        qs += f"&serviceName={service}"
    try:
        data = _request("GET", f"/api/listActions?{qs}", token=token, timeout=30)
    except PanelError as exc:
        print(f"  actions list warn: {exc}")
        return []
    if isinstance(data, dict):
        for key in ("json", "actions", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        return []
    return data if isinstance(data, list) else []


def kill_stale_actions(token: str, service: str) -> int:
    """Stop pending/running deploy actions for this service so a new one can start."""
    killed = 0
    for action in list_actions(token, service):
        if not isinstance(action, dict):
            continue
        status = str(action.get("status") or action.get("state") or "").lower()
        if status not in {"pending", "running", "in_progress", "queued", "active"}:
            continue
        blob = json.dumps(action).lower()
        if "deploy" not in blob and "build" not in blob:
            # Still kill start/build-like pending work for this service filter.
            if status not in {"pending", "running", "queued"}:
                continue
        action_id = action.get("id") or action.get("actionId")
        if not action_id:
            continue
        try:
            _request("POST", "/api/killAction", token=token, payload={"id": action_id}, timeout=20)
            print(f"  killed stale action {action_id} ({status})")
            killed += 1
        except PanelError as exc:
            print(f"  warn: could not kill {action_id}: {exc}")
    return killed


def ensure_source(token: str, service: str, path: str) -> None:
    info = inspect(token, service)
    source = info.get("source") or {}
    needs = (
        source.get("type") != "github"
        or source.get("owner") != OWNER
        or source.get("repo") != REPO
        or source.get("ref") != REF
        or source.get("path") != path
    )
    if needs:
        _request(
            "POST",
            "/api/rpc/services/app/updateSourceGithub",
            token=token,
            payload={
                "json": {
                    "projectName": PROJECT,
                    "serviceName": service,
                    "owner": OWNER,
                    "repo": REPO,
                    "ref": REF,
                    "path": path,
                }
            },
        )
        print(f"  source → github {OWNER}/{REPO}@{REF} ({path})")
    else:
        print(f"  source ok ({path})")

    # Keep auto-deploy OFF unless explicitly requested.
    enable = os.environ.get("EASYPANEL_ENABLE_AUTODEPLOY", "").strip().lower() in {
        "1", "true", "yes",
    }
    try:
        if enable:
            _request(
                "POST",
                "/api/rpc/services/app/enableGithubDeploy",
                token=token,
                payload={"json": {"projectName": PROJECT, "serviceName": service}},
            )
            print("  autoDeploy on")
        else:
            _request(
                "POST",
                "/api/rpc/services/app/disableGithubDeploy",
                token=token,
                payload={"json": {"projectName": PROJECT, "serviceName": service}},
            )
            print("  autoDeploy off")
    except PanelError as exc:
        print(f"  autoDeploy warn: {exc}")


def bump_cachebust(token: str, service: str) -> None:
    """Force a fresh frontend image layer even when Dockerfile is unchanged."""
    info = inspect(token, service)
    env = info.get("env") or ""
    lines = [ln for ln in env.splitlines() if ln.strip() and not ln.startswith("CACHEBUST=")]
    lines.append(f"CACHEBUST={int(time.time())}")
    new_env = "\n".join(lines) + "\n"
    try:
        _request(
            "POST",
            "/api/rpc/services/app/updateEnv",
            token=token,
            payload={"json": {"projectName": PROJECT, "serviceName": service, "env": new_env}},
        )
    except PanelError:
        _request(
            "POST",
            "/api/updateAppEnv",
            token=token,
            payload={"projectName": PROJECT, "serviceName": service, "env": new_env},
        )
    print("  CACHEBUST bumped")


def refresh_deploy_token(token: str, service: str) -> str:
    try:
        _request(
            "POST",
            "/api/refreshAppDeployToken",
            token=token,
            payload={"projectName": PROJECT, "serviceName": service},
        )
    except PanelError:
        try:
            _request(
                "POST",
                "/api/rpc/services/app/refreshDeployToken",
                token=token,
                payload={"json": {"projectName": PROJECT, "serviceName": service}},
            )
        except PanelError as exc:
            print(f"  token refresh warn: {exc}")
    return inspect(token, service)["token"]


def trigger_webhook(deploy_token: str) -> str:
    data = _request("GET", f"/api/deploy/{deploy_token}", timeout=30)
    if isinstance(data, dict):
        return json.dumps(data)[:200]
    return str(data)[:200]


def deploy_service(token: str, service: str, *, wanted_sha: str, wait: bool, timeout_s: int) -> bool:
    cfg = SERVICES[service]
    print(f"\n=== {service} ===")
    ensure_source(token, service, cfg["path"])
    kill_stale_actions(token, service)
    if cfg.get("cachebust"):
        bump_cachebust(token, service)

    before = (inspect(token, service).get("commit") or {}).get("sha", "")
    print(f"  current SHA {before[:12] or '?'}")
    print(f"  target SHA  {wanted_sha[:12]}")

    dtoken = refresh_deploy_token(token, service)
    # Single trigger only — do NOT also call deployService (causes builder overload).
    body = trigger_webhook(dtoken)
    print(f"  webhook → {body or 'Deploying...'}")

    if not wait:
        return True

    deadline = time.time() + timeout_s
    last = before
    while time.time() < deadline:
        time.sleep(12)
        try:
            info = inspect(token, service)
        except PanelError as exc:
            print(f"  poll warn: {exc}")
            continue
        sha = (info.get("commit") or {}).get("sha", "")
        if sha != last:
            print(f"  SHA {sha[:12]}")
            last = sha
        if sha.startswith(wanted_sha[:7]) or wanted_sha.startswith(sha[:7]):
            print(f"  ✓ {service} deployed {sha[:12]}")
            return True
    print(f"  ✗ timed out waiting for {service} → {wanted_sha[:12]} (last {last[:12]})")
    return False


def print_status(token: str) -> None:
    wanted = github_main_sha()
    print(f"GitHub {REF}: {wanted[:12]}")
    for service in SERVICES:
        info = inspect(token, service)
        sha = (info.get("commit") or {}).get("sha", "")
        mark = "✓" if sha.startswith(wanted[:7]) else "✗"
        print(f"  {mark} {service:8} {sha[:12]}  autoDeploy={bool((info.get('source') or {}).get('autoDeploy'))}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Redeploy eCourts on Easypanel")
    parser.add_argument(
        "target",
        nargs="?",
        default="both",
        choices=["frontend", "backend", "both", "status", "fe", "be", "all"],
    )
    parser.add_argument("--no-wait", action="store_true", help="Trigger only; do not poll SHA")
    parser.add_argument("--timeout", type=int, default=900, help="Per-service wait seconds (default 900)")
    args = parser.parse_args()

    email = os.environ.get("EASYPANEL_EMAIL")
    password = os.environ.get("EASYPANEL_PASSWORD")
    if not email or not password:
        print("Set EASYPANEL_EMAIL and EASYPANEL_PASSWORD", file=sys.stderr)
        return 2

    print(f"Logging into {PANEL_URL} …")
    token = login(email, password)
    wanted = github_main_sha()
    print(f"GitHub {OWNER}/{REPO}@{REF} = {wanted[:12]}")

    target = {"fe": "frontend", "be": "backend", "all": "both"}.get(args.target, args.target)
    if target == "status":
        print_status(token)
        return 0

    services = ["frontend", "backend"] if target == "both" else [target]
    # Sequential only — parallel builds overload the single Docker builder.
    ok = True
    for service in services:
        if not deploy_service(
            token,
            service,
            wanted_sha=wanted,
            wait=not args.no_wait,
            timeout_s=args.timeout,
        ):
            ok = False
        if len(services) > 1 and service != services[-1]:
            print("  cooling down builder …")
            time.sleep(20)

    print("\nDone.")
    print("  Frontend: https://ecourt.demo.agrayianailabs.com")
    print("  Backend:  https://ecourt.demoapi.agrayianailabs.com/api/health")
    print_status(token)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
