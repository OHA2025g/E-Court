#!/usr/bin/env python3
"""Restore Cloud financial rows from create-audit absolute ₹ via the live API."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import http.cookiejar

import os

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "PMIS_API_BASE", "https://ecourt.demoapi.agrayianailabs.com/api"
)
EMAIL = os.environ.get("PMIS_ADMIN_EMAIL", "admin@pmis.gov.in")
PASSWORD = os.environ["PMIS_ADMIN_PASSWORD"]
CLOUD = "Cloud Computing & Storage"
PERIOD = os.environ.get("PMIS_CLOUD_PERIOD", "2026-03")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(method: str, path: str, data=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with opener.open(req, timeout=120) as resp:
        return json.load(resp)


def main() -> int:
    call("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
    audits = call("GET", "/audit?limit=5000")
    by_hc: dict[str, tuple[float, float, str | None]] = {}
    for a in sorted(audits, key=lambda x: x.get("timestamp") or ""):
        if a.get("tracker") != "financial" or a.get("action") != "create":
            continue
        for c in a.get("changes") or []:
            if c.get("field") != "entry" or not isinstance(c.get("new"), dict):
                continue
            n = c["new"]
            if n.get("component") != CLOUD:
                continue
            hc = n.get("high_court")
            if not hc or hc in by_hc:
                continue
            released = n.get("fund_released")
            utilized = n.get("fund_utilized") or 0
            if not isinstance(released, (int, float)):
                continue
            if abs(float(released)) < 1000 and abs(float(utilized)) < 1000:
                continue
            by_hc[hc] = (float(released), float(utilized), n.get("remarks"))

    print(f"create-audit HCs with ₹ amounts: {len(by_hc)}")
    fin = call("GET", f"/financial?reporting_period={PERIOD}&page=1&page_size=100")
    items = fin.get("items") or []
    updated = 0
    for row in items:
        if row.get("component") != CLOUD:
            continue
        hc = row.get("high_court")
        if hc not in by_hc:
            print(f"skip (no audit): {hc}")
            continue
        rel_r, util_r, remarks = by_hc[hc]
        payload = {
            "high_court": hc,
            "component": CLOUD,
            "reporting_period": PERIOD,
            "district": row.get("district"),
            "fund_released": rel_r,  # absolute ₹ → API converts + stores *_rupees
            "fund_utilized": util_r,
            "fund_target": row.get("fund_target"),
            "fund_allocated": row.get("fund_allocated"),
            "remarks": remarks or row.get("remarks"),
            "description": row.get("description"),
        }
        try:
            call("POST", "/financial", payload)
            updated += 1
            print(f"restored {hc}: ₹{rel_r} / ₹{util_r}")
        except urllib.error.HTTPError as exc:
            print(f"FAIL {hc}: {exc.read().decode()[:300]}")
            return 1

    summary = call("GET", f"/dashboard/summary?reporting_period={PERIOD}")
    f = summary.get("financial") or {}
    print(
        "summary after repair:",
        "released=", f.get("released"),
        "utilized=", f.get("utilized"),
        "count=", f.get("component_count"),
        "updated=", updated,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
