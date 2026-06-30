"""AI narrative summary with guardrails (template + structured facts)."""
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

NARRATIVE_ENABLED = os.environ.get("NARRATIVE_ENABLED", "false").lower() in ("1", "true", "yes")
NARRATIVE_REQUIRES_REVIEW = os.environ.get("NARRATIVE_REQUIRES_REVIEW", "true").lower() in ("1", "true", "yes")

PENDING_EXPORT_NOTE = (
    "Executive summary pending Admin review. "
    "Approve the narrative in PMIS Dashboard → Executive narrative before Cabinet distribution."
)


def period_key(reporting_period: Optional[str]) -> str:
    return reporting_period or "__latest__"


async def generate_narrative(db, summary: dict, reporting_period: str) -> str:
    """Build a factual narrative from dashboard summary — no LLM hallucination."""
    phys = summary.get("physical", {})
    fin = summary.get("financial", {})
    outcome = summary.get("outcome", {})
    rag = summary.get("rag_physical", {})
    phys_pct = phys.get("percent") or 0
    fin_pct = fin.get("utilisation_percent") or 0
    parts = [
        f"For reporting period {reporting_period}, national physical achievement stands at "
        f"{phys_pct:.1f}% across {phys.get('indicator_count', 0)} rolled-up indicators.",
        f"Financial utilisation is {fin_pct:.1f}% "
        f"(₹{fin.get('utilized', 0):,.0f} Cr utilised of ₹{fin.get('released', 0):,.0f} Cr released).",
        f"Outcome KPI reporting covers {outcome.get('kpi_count', 0)} KPIs in scope.",
        f"RAG distribution (physical): GREEN {rag.get('GREEN', 0)}, AMBER {rag.get('AMBER', 0)}, "
        f"RED {rag.get('RED', 0)}.",
    ]
    if NARRATIVE_ENABLED and os.environ.get("EMERGENT_LLM_KEY"):
        try:
            import litellm
            prompt = (
                "Summarise these PMIS facts in ≤200 words for a Cabinet brief. "
                "Use ONLY these facts:\n" + "\n".join(parts)
            )
            r = litellm.completion(
                model=os.environ.get("NARRATIVE_LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            return r.choices[0].message.content.strip()
        except Exception:
            pass
    return " ".join(parts)


async def get_narrative_record(db, reporting_period: Optional[str]) -> Optional[dict]:
    return await db.narrative_reviews.find_one({"reporting_period": period_key(reporting_period)})


async def upsert_draft(db, reporting_period: Optional[str], text: str, generated_by: str = "system") -> dict:
    key = period_key(reporting_period)
    now = datetime.now(timezone.utc)
    doc = {
        "reporting_period": key,
        "draft_text": text,
        "status": "draft",
        "generated_at": now,
        "generated_by": generated_by,
    }
    await db.narrative_reviews.update_one({"reporting_period": key}, {"$set": doc}, upsert=True)
    return doc


async def approve_narrative(db, reporting_period: Optional[str], text: str, reviewer: str) -> dict:
    key = period_key(reporting_period)
    now = datetime.now(timezone.utc)
    update = {
        "approved_text": text,
        "draft_text": text,
        "status": "approved",
        "reviewed_by": reviewer,
        "reviewed_at": now,
    }
    await db.narrative_reviews.update_one({"reporting_period": key}, {"$set": update}, upsert=True)
    rec = await get_narrative_record(db, reporting_period)
    return rec or update


async def refresh_draft(db, summary: dict, reporting_period: Optional[str], actor: str = "system") -> Tuple[str, dict]:
    label = reporting_period or "Latest"
    text = await generate_narrative(db, summary, label)
    doc = await upsert_draft(db, reporting_period, text, generated_by=actor)
    rec = await get_narrative_record(db, reporting_period)
    return text, rec or doc


async def narrative_dashboard_payload(db, summary: dict, reporting_period: Optional[str]) -> dict:
    """Return narrative text + review metadata for the dashboard widget."""
    label = reporting_period or "Latest"
    rec = await get_narrative_record(db, reporting_period)
    if not rec or not rec.get("draft_text"):
        text, rec = await refresh_draft(db, summary, reporting_period)
    else:
        text = rec.get("approved_text") if rec.get("status") == "approved" else rec.get("draft_text", "")
    status = rec.get("status", "draft") if rec else "draft"
    return {
        "reporting_period": reporting_period,
        "narrative": text,
        "draft_text": rec.get("draft_text") if rec else text,
        "approved_text": rec.get("approved_text"),
        "review_status": status,
        "requires_review": NARRATIVE_REQUIRES_REVIEW,
        "reviewed_by": rec.get("reviewed_by") if rec else None,
        "reviewed_at": rec.get("reviewed_at").isoformat() if rec and rec.get("reviewed_at") else None,
        "llm_enabled": NARRATIVE_ENABLED,
        "period_label": label,
    }


async def narrative_for_export(db, summary: dict, reporting_period: Optional[str]) -> str:
    """Cabinet Brief / scheduled email — approved text only when review is required."""
    rec = await get_narrative_record(db, reporting_period)
    if rec and rec.get("status") == "approved" and rec.get("approved_text"):
        return rec["approved_text"]
    if not NARRATIVE_REQUIRES_REVIEW:
        if rec and rec.get("draft_text"):
            return rec["draft_text"]
        label = reporting_period or "Latest"
        text = await generate_narrative(db, summary, label)
        await upsert_draft(db, reporting_period, text)
        return text
    return PENDING_EXPORT_NOTE
