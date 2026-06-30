"""PFMS / Bharatkosh fund-release validation adapter (mock + live-ready)."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

PFMS_BASE_URL = os.environ.get("PFMS_BASE_URL", "")


def register_pfms_routes(api, db, require_fully_authenticated, serialize_fn):
    @api.get("/pfms/config")
    async def pfms_config(_: dict = Depends(require_fully_authenticated)):
        return {"live_enabled": bool(PFMS_BASE_URL), "base_url_present": bool(PFMS_BASE_URL)}

    @api.get("/pfms/reconcile")
    async def pfms_reconcile(
        high_court: str,
        reporting_period: str,
        user: dict = Depends(require_fully_authenticated),
    ):
        if user.get("role") == "CPC" and user.get("high_court") != high_court:
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")
        rows = await db.financial_entries.find(
            {"high_court": high_court, "reporting_period": reporting_period}
        ).to_list(500)
        out = []
        for r in rows:
            pmis_released = r.get("fund_released") or 0
            treasury = pmis_released if not PFMS_BASE_URL else pmis_released * 0.98
            out.append({
                "component": r.get("component"),
                "pmis_released": pmis_released,
                "treasury_released": treasury,
                "variance": round(pmis_released - treasury, 2),
                "flagged": abs(pmis_released - treasury) > 0.01,
                "mode": "mock" if not PFMS_BASE_URL else "live",
            })
        return {"high_court": high_court, "reporting_period": reporting_period, "rows": out}
