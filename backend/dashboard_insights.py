"""Mistral AI dashboard insights — insights, recommendations, action items, action plan."""
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("pmis")

INSIGHTS_ENABLED = os.environ.get("DASHBOARD_INSIGHTS_ENABLED", "false").lower() in ("1", "true", "yes")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_API_URL = os.environ.get("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")


def period_key(reporting_period: Optional[str]) -> str:
    return reporting_period or "__latest__"


def scope_key(user: dict) -> str:
    role = user.get("role", "Viewer")
    hc = user.get("high_court") or "_all"
    return f"{role}:{hc}"


def cache_key(reporting_period: Optional[str], user: dict) -> str:
    return f"{period_key(reporting_period)}:{scope_key(user)}"


def _rag_label(pct: Optional[float]) -> str:
    if pct is None:
        return "NA"
    if pct >= 80:
        return "GREEN"
    if pct >= 65:
        return "AMBER"
    return "RED"


def _top_bottom(rows: list, key: str, n: int = 5) -> tuple[list, list]:
    valid = [r for r in rows if r.get(key) is not None]
    asc = sorted(valid, key=lambda r: r[key])
    desc = list(reversed(asc))
    return desc[:n], asc[:n]


def build_context(
    summary: dict,
    by_component: list,
    by_hc: list,
    rag_delta: Optional[dict],
    pareto: Optional[dict],
    reporting_period: Optional[str],
    user: dict,
) -> dict:
    period_label = reporting_period or "Latest (all periods)"
    phys = summary.get("physical") or {}
    fin = summary.get("financial") or {}
    outcome = summary.get("outcome") or {}
    rag = summary.get("rag_physical") or {}

    best_comp, worst_comp = _top_bottom(by_component, "phys_percent")
    best_hc, worst_hc = _top_bottom(by_hc, "phys_percent")

    ctx = {
        "reporting_period": period_label,
        "viewer_scope": scope_key(user),
        "national_summary": {
            "physical_percent": phys.get("percent"),
            "physical_target": phys.get("target"),
            "physical_achieved": phys.get("achieved"),
            "indicator_count": phys.get("indicator_count"),
            "financial_released_cr": fin.get("released"),
            "financial_utilized_cr": fin.get("utilized"),
            "financial_utilisation_percent": fin.get("utilisation_percent"),
            "financial_variance_cr": fin.get("variance"),
            "outcome_kpi_count": outcome.get("kpi_count"),
            "rag_physical": rag,
        },
        "top_components_by_physical_pct": [
            {
                "component": r.get("component"),
                "phys_percent": r.get("phys_percent"),
                "fin_percent": r.get("fin_percent"),
                "rag": _rag_label(r.get("phys_percent")),
            }
            for r in best_comp
        ],
        "bottom_components_by_physical_pct": [
            {
                "component": r.get("component"),
                "phys_percent": r.get("phys_percent"),
                "fin_percent": r.get("fin_percent"),
                "rag": _rag_label(r.get("phys_percent")),
            }
            for r in worst_comp
        ],
        "top_high_courts_by_physical_pct": [
            {
                "high_court": r.get("high_court"),
                "phys_percent": r.get("phys_percent"),
                "fin_percent": r.get("fin_percent"),
            }
            for r in best_hc
        ],
        "bottom_high_courts_by_physical_pct": [
            {
                "high_court": r.get("high_court"),
                "phys_percent": r.get("phys_percent"),
                "fin_percent": r.get("fin_percent"),
            }
            for r in worst_hc
        ],
    }
    if rag_delta:
        ctx["rag_delta_vs_prior_period"] = {
            "metric": rag_delta.get("metric"),
            "current_period": rag_delta.get("current_period"),
            "prior_period": rag_delta.get("prior_period"),
            "delta_green": rag_delta.get("delta", {}).get("GREEN"),
            "delta_amber": rag_delta.get("delta", {}).get("AMBER"),
            "delta_red": rag_delta.get("delta", {}).get("RED"),
        }
    if pareto and pareto.get("items"):
        ctx["pareto_red_flags"] = pareto["items"][:8]
    return ctx


def _template_insights(context: dict) -> dict:
    ns = context.get("national_summary") or {}
    phys_pct = ns.get("physical_percent") or 0
    fin_pct = ns.get("financial_utilisation_percent") or 0
    rag = ns.get("rag_physical") or {}
    period = context.get("reporting_period", "Latest")
    worst = context.get("bottom_components_by_physical_pct") or []
    worst_hc = context.get("bottom_high_courts_by_physical_pct") or []

    insights = [
        f"For {period}, national physical achievement is {phys_pct:.1f}% across "
        f"{ns.get('indicator_count', 0)} indicators.",
        f"Financial utilisation stands at {fin_pct:.1f}% "
        f"(₹{ns.get('financial_utilized_cr', 0):,.0f} Cr of ₹{ns.get('financial_released_cr', 0):,.0f} Cr released).",
        f"RAG distribution (physical): GREEN {rag.get('GREEN', 0)}, AMBER {rag.get('AMBER', 0)}, "
        f"RED {rag.get('RED', 0)}.",
    ]
    if worst:
        names = ", ".join(f"{w['component']} ({w['phys_percent']:.1f}%)" for w in worst[:3] if w.get("component"))
        insights.append(f"Lowest-performing components: {names}.")
    if worst_hc:
        names = ", ".join(f"{w['high_court']} ({w['phys_percent']:.1f}%)" for w in worst_hc[:3] if w.get("high_court"))
        insights.append(f"High courts needing attention: {names}.")

    recommendations = [
        "Prioritise field verification and CPC follow-up on RED and AMBER indicators before the next reporting cycle.",
        "Align fund release pacing with physical milestones for components with high release but low utilisation.",
        "Share best practices from top-performing High Courts with laggard jurisdictions via PMU workshops.",
    ]
    if fin_pct < 65:
        recommendations.append(
            "Escalate low national utilisation to Financial Tracker owners with component-wise utilisation targets."
        )

    action_items = []
    for w in worst[:3]:
        if w.get("component"):
            action_items.append(
                f"Conduct CPC review for {w['component']} (physical {w.get('phys_percent', 0):.1f}%)."
            )
    for w in worst_hc[:3]:
        if w.get("high_court"):
            action_items.append(
                f"Schedule PMU check-in with {w['high_court']} on physical and financial gaps."
            )
    action_items.extend([
        "Validate submitted tracker entries against approved submissions before Cabinet Brief.",
        "Update RAG thresholds in Master Data if persistent AMBER bands reflect data quality issues.",
    ])

    action_plan = [
        {
            "phase": "Immediate (0–30 days)",
            "actions": action_items[:3] or ["Review RED indicators and confirm data with CPC officers."],
        },
        {
            "phase": "Short-term (1–3 months)",
            "actions": [
                "Close gaps on bottom-quartile components through targeted PMU site visits.",
                "Reconcile financial utilisation with PFMS / release schedules where variance exceeds tolerance.",
            ],
        },
        {
            "phase": "Medium-term (3–6 months)",
            "actions": [
                "Institutionalise monthly RAG delta reviews with e-Committee and DoJ nodal officers.",
                "Publish anonymised best-practice playbooks from GREEN-performing High Courts.",
            ],
        },
    ]

    return {
        "insights": insights[:6],
        "recommendations": recommendations[:6],
        "action_items": action_items[:8],
        "action_plan": action_plan,
    }


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    for key in ("insights", "recommendations", "action_items", "action_plan"):
        if key not in data:
            raise ValueError(f"Missing key: {key}")
    return {
        "insights": [str(x) for x in data["insights"]][:8],
        "recommendations": [str(x) for x in data["recommendations"]][:8],
        "action_items": [str(x) for x in data["action_items"]][:10],
        "action_plan": [
            {
                "phase": str(p.get("phase", "Phase")),
                "actions": [str(a) for a in (p.get("actions") or [])][:6],
            }
            for p in data["action_plan"]
        ][:4],
    }


async def call_mistral(context: dict) -> dict:
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY not configured")

    system = (
        "You are a senior PMIS analyst for India's eCourts Phase III program. "
        "Analyse ONLY the JSON data provided. Do not invent figures, courts, or components. "
        "Respond with valid JSON only."
    )
    user_prompt = (
        "Using ONLY the PMIS dashboard data below, produce executive analysis as JSON with exactly these keys:\n"
        '- "insights": array of 4–6 concise observation strings\n'
        '- "recommendations": array of 4–6 strategic recommendation strings\n'
        '- "action_items": array of 5–8 specific actionable tasks (who/what, referencing data)\n'
        '- "action_plan": array of 3 objects, each with "phase" (string) and "actions" (array of strings) '
        "for Immediate (0–30 days), Short-term (1–3 months), and Medium-term (3–6 months).\n\n"
        "Use Indian English suitable for DoJ / PMU leadership. Reference specific percentages and names from the data.\n\n"
        f"DATA:\n{json.dumps(context, indent=2, default=str)}"
    )

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            MISTRAL_API_URL,
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MISTRAL_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.25,
                "max_tokens": 2500,
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return _parse_llm_json(content)


async def get_cached(db, key: str) -> Optional[dict]:
    return await db.dashboard_ai_insights.find_one({"cache_key": key})


async def save_cache(db, key: str, reporting_period: Optional[str], user: dict, result: dict, source: str) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "cache_key": key,
        "reporting_period": period_key(reporting_period),
        "scope_key": scope_key(user),
        **result,
        "source": source,
        "model": MISTRAL_MODEL if source == "mistral" else None,
        "generated_at": now,
    }
    await db.dashboard_ai_insights.update_one({"cache_key": key}, {"$set": doc}, upsert=True)
    return doc


async def generate_insights_payload(
    db,
    summary: dict,
    by_component: list,
    by_hc: list,
    rag_delta: Optional[dict],
    pareto: Optional[dict],
    reporting_period: Optional[str],
    user: dict,
    refresh: bool = False,
) -> dict:
    key = cache_key(reporting_period, user)
    if not refresh:
        cached = await get_cached(db, key)
        if cached:
            return _serialize_payload(cached, cached=True)

    context = build_context(summary, by_component, by_hc, rag_delta, pareto, reporting_period, user)
    source = "template"
    sections = _template_insights(context)

    if INSIGHTS_ENABLED and MISTRAL_API_KEY:
        try:
            sections = await call_mistral(context)
            source = "mistral"
        except Exception as exc:
            logger.warning("Mistral insights failed, using template fallback: %s", exc)

    doc = await save_cache(db, key, reporting_period, user, sections, source)
    return _serialize_payload(doc, cached=False)


def _serialize_payload(doc: dict, cached: bool) -> dict:
    generated = doc.get("generated_at")
    return {
        "reporting_period": doc.get("reporting_period"),
        "period_label": doc.get("reporting_period", "").replace("__latest__", "Latest"),
        "insights": doc.get("insights") or [],
        "recommendations": doc.get("recommendations") or [],
        "action_items": doc.get("action_items") or [],
        "action_plan": doc.get("action_plan") or [],
        "source": doc.get("source", "template"),
        "model": doc.get("model"),
        "mistral_enabled": bool(MISTRAL_API_KEY and INSIGHTS_ENABLED),
        "generated_at": generated.isoformat() if hasattr(generated, "isoformat") else generated,
        "cached": cached,
    }
