"""Admin narrative review workflow."""
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field


class NarrativeApproveIn(BaseModel):
    reporting_period: Optional[str] = None
    text: Optional[str] = Field(None, max_length=4000)


class NarrativeRegenerateIn(BaseModel):
    reporting_period: Optional[str] = None


def register_narrative_routes(
    api,
    db,
    require_role,
    require_fully_authenticated,
    scope_filter_fn,
    compute_rag_fn,
    safe_div_fn,
    compute_dashboard_summary_fn,
):
    @api.post("/admin/narrative/approve")
    async def approve_narrative_route(body: NarrativeApproveIn, user: dict = Depends(require_role("Admin"))):
        from narrative import approve_narrative, get_narrative_record, period_key

        rec = await get_narrative_record(db, body.reporting_period)
        if not rec or not rec.get("draft_text"):
            raise HTTPException(status_code=404, detail="No draft narrative to approve — regenerate first")
        text = (body.text or rec.get("draft_text") or "").strip()
        if len(text) < 20:
            raise HTTPException(status_code=400, detail="Narrative text too short")
        updated = await approve_narrative(db, body.reporting_period, text, user["email"])
        return {
            "ok": True,
            "reporting_period": body.reporting_period,
            "review_status": "approved",
            "narrative": updated.get("approved_text"),
            "reviewed_by": user["email"],
        }

    @api.post("/admin/narrative/regenerate")
    async def regenerate_narrative_route(body: NarrativeRegenerateIn, user: dict = Depends(require_role("Admin"))):
        from narrative import refresh_draft, period_key

        extra = {}
        summary = await compute_dashboard_summary_fn(
            db, scope_filter_fn, compute_rag_fn, safe_div_fn, user, body.reporting_period, extra,
        )
        text, rec = await refresh_draft(db, summary, body.reporting_period, actor=user["email"])
        return {
            "ok": True,
            "reporting_period": body.reporting_period,
            "review_status": rec.get("status", "draft"),
            "narrative": text,
            "period_key": period_key(body.reporting_period),
        }
