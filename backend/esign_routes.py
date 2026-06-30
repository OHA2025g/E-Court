"""eSign adapter stub for submitted monthly reports."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

ESIGN_PROVIDER_URL = os.environ.get("ESIGN_PROVIDER_URL", "")


class EsignInitIn(BaseModel):
    high_court: str
    reporting_period: str


def register_esign_routes(api, db, require_fully_authenticated, serialize_fn, now_utc_fn):
    @api.get("/esign/config")
    async def esign_config(_: dict = Depends(require_fully_authenticated)):
        return {"enabled": bool(ESIGN_PROVIDER_URL)}

    @api.post("/esign/init")
    async def esign_init(body: EsignInitIn, user: dict = Depends(require_fully_authenticated)):
        sub = await db.submissions.find_one(
            {"high_court": body.high_court, "reporting_period": body.reporting_period}
        )
        if not sub or sub.get("status") != "Submitted":
            raise HTTPException(status_code=400, detail="Submission must be in Submitted status")
        if not ESIGN_PROVIDER_URL:
            return {
                "mode": "stub",
                "message": "eSign provider not configured — set ESIGN_PROVIDER_URL",
                "transaction_id": f"stub-{body.high_court}-{body.reporting_period}",
            }
        return {"mode": "live", "redirect_url": f"{ESIGN_PROVIDER_URL}/sign?ref={sub['_id']}"}
