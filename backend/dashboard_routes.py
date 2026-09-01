"""Dashboard routes - updated to pass approval gating."""
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dashboard_agg import (
    compute_dashboard_by_component,
    compute_dashboard_by_hc,
    compute_dashboard_summary,
    compute_financial_status_yoy,
    compute_financial_tracker_dashboard,
    compute_heatmap,
    compute_pareto_red_flags,
    compute_public_progress,
    compute_rag_delta,
    compute_states_rag,
    compute_trend_with_milestones,
)
from period_policy import approved_match_filter, merge_match
from cache_layer import cache_get, cache_set
from security import client_ip
from high_court_names import high_court_filter_value

_public_cache: dict = {}
_PUBLIC_CACHE_TTL = 60


def _enforce_public_rate_limit(request: Request):
    from api_rate_limit import enforce_public_ip_rate_limit
    enforce_public_ip_rate_limit(client_ip(request))


def _dimension_match(
    user: dict,
    high_court: Optional[str] = None,
    component: Optional[str] = None,
) -> dict:
    """Optional High Court / Component filters for national dashboard views."""
    if user and user.get("role") == "CPC" and user.get("high_court"):
        high_court = user["high_court"]
    match: dict = {}
    if high_court:
        match["high_court"] = high_court_filter_value(high_court)
    if component:
        match["component"] = component
    return match


# Bump when dashboard aggregation semantics change so Redis does not serve stale KPIs.
_DASHBOARD_CACHE_VER = "v28-fin-yoy-latest-snapshot"


def _dashboard_cache_key(route: str, user: dict, reporting_period: Optional[str], include_unapproved: bool, **extra) -> str:
    role = user.get("role", "Viewer")
    hc = user.get("high_court") or "_all"
    period_key = reporting_period or "__all__"
    parts = [
        f"dashboard:{_DASHBOARD_CACHE_VER}:{route}:{period_key}",
        f"{role}:{hc}",
        f"ua{int(include_unapproved)}",
    ]
    for k in sorted(extra):
        parts.append(f"{k}={extra[k]}")
    return ":".join(parts)


async def _cached_dashboard(route: str, user: dict, reporting_period: Optional[str], include_unapproved: bool, compute_fn, **extra):
    cache_key = _dashboard_cache_key(route, user, reporting_period, include_unapproved, **extra)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    data = await compute_fn()
    cache_set(cache_key, data)
    return data


def register_dashboard_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    scope_filter_fn,
    compute_rag_fn,
    safe_div_fn,
    state_to_hc: dict,
):
    async def _extra(
        user,
        reporting_period=None,
        include_unapproved=False,
        high_court=None,
        component=None,
    ):
        return merge_match(
            await approved_match_filter(db, reporting_period, include_unapproved, user),
            _dimension_match(user, high_court, component),
        )

    def _cache_dims(high_court=None, component=None):
        return {
            "fhc": high_court or "_all",
            "fcomp": component or "_all",
        }

    @api.get("/dashboard/summary")
    async def dashboard_summary(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        return await _cached_dashboard(
            "summary", user, reporting_period, include_unapproved,
            lambda: compute_dashboard_summary(
                db, scope_filter_fn, compute_rag_fn, safe_div_fn, user, reporting_period, extra,
            ),
            **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/by-component")
    async def dashboard_by_component(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        snapshot: Optional[str] = Query(
            None,
            description="When 'latest', each component uses its newest loaded reporting month "
            "(avoids double-counting cumulative tracker values across periods).",
        ),
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        snapshot_mode = snapshot if snapshot == "latest" else None
        cache_period = "__latest__" if snapshot_mode else reporting_period
        return await _cached_dashboard(
            "by-component", user, cache_period, include_unapproved,
            lambda: compute_dashboard_by_component(
                db, scope_filter_fn, safe_div_fn, user, reporting_period, extra,
                snapshot_mode=snapshot_mode,
            ),
            **_cache_dims(high_court, component),
            snapshot=snapshot_mode or "period",
        )

    @api.get("/dashboard/financial-status-yoy")
    async def dashboard_financial_status_yoy(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        snapshot: Optional[str] = Query(
            None,
            description="When 'latest', each component uses its newest loaded reporting month "
            "(recommended default; avoids double-counting cumulative fund fields).",
        ),
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        snapshot_mode = snapshot if snapshot == "latest" else None
        cache_period = "__latest__" if snapshot_mode else (reporting_period or "__all__")
        return await _cached_dashboard(
            "financial-status-yoy", user, cache_period, include_unapproved,
            lambda: compute_financial_status_yoy(
                db, scope_filter_fn, safe_div_fn, user, reporting_period, extra,
                snapshot_mode=snapshot_mode,
            ),
            **_cache_dims(high_court, component),
            snapshot=snapshot_mode or "period",
        )

    @api.get("/dashboard/by-high-court")
    async def dashboard_by_hc(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        return await _cached_dashboard(
            "by-high-court", user, reporting_period, include_unapproved,
            lambda: compute_dashboard_by_hc(
                db, scope_filter_fn, safe_div_fn, user, reporting_period, extra,
            ),
            **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/financial-tracker")
    async def dashboard_financial_tracker(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        return await _cached_dashboard(
            "financial-tracker", user, reporting_period, include_unapproved,
            lambda: compute_financial_tracker_dashboard(
                db, scope_filter_fn, safe_div_fn, user, reporting_period, extra,
            ),
            **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/trend")
    async def dashboard_trend(
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, None, include_unapproved, high_court, component)
        return await _cached_dashboard(
            "trend", user, None, include_unapproved,
            lambda: compute_trend_with_milestones(db, scope_filter_fn, safe_div_fn, user, extra),
            **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/rag-delta")
    async def dashboard_rag_delta(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        metric: Literal["physical", "financial", "outcome"] = "physical",
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)

        async def _compute():
            result = await compute_rag_delta(
                db, scope_filter_fn, compute_rag_fn, safe_div_fn, user, reporting_period, metric, extra,
            )
            if not result:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to compute delta - select a reporting period with a prior period",
                )
            return result

        return await _cached_dashboard(
            "rag-delta", user, reporting_period, include_unapproved, _compute,
            metric=metric, **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/heatmap")
    async def dashboard_heatmap(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        metric: Literal["physical", "financial", "outcome"] = "physical",
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        return await _cached_dashboard(
            "heatmap", user, reporting_period, include_unapproved,
            lambda: compute_heatmap(
                db, scope_filter_fn, compute_rag_fn, user, reporting_period, metric, extra,
            ),
            metric=metric, **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/pareto-red-flags")
    async def dashboard_pareto(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        metric: Literal["physical", "financial", "outcome"] = "physical",
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        return await _cached_dashboard(
            "pareto", user, reporting_period, include_unapproved,
            lambda: compute_pareto_red_flags(
                db, scope_filter_fn, compute_rag_fn, user, reporting_period, metric, extra,
            ),
            metric=metric, **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/states-rag")
    async def states_rag(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        metric: Literal["physical", "financial", "outcome"] = "physical",
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        return await _cached_dashboard(
            "states-rag", user, reporting_period, include_unapproved,
            lambda: compute_states_rag(
                db, state_to_hc, scope_filter_fn, compute_rag_fn,
                user, reporting_period, metric, extra,
            ),
            metric=metric, **_cache_dims(high_court, component),
        )

    @api.get("/dashboard/narrative")
    async def dashboard_narrative(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        from narrative import narrative_dashboard_payload

        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        summary = await compute_dashboard_summary(
            db, scope_filter_fn, compute_rag_fn, safe_div_fn, user, reporting_period, extra,
        )
        return await narrative_dashboard_payload(db, summary, reporting_period)

    @api.get("/dashboard/ai-insights")
    async def dashboard_ai_insights(
        reporting_period: Optional[str] = None,
        high_court: Optional[str] = None,
        component: Optional[str] = None,
        include_unapproved: bool = False,
        refresh: bool = False,
        user: dict = Depends(require_fully_authenticated),
    ):
        from dashboard_insights import generate_insights_payload

        extra = await _extra(user, reporting_period, include_unapproved, high_court, component)
        summary = await compute_dashboard_summary(
            db, scope_filter_fn, compute_rag_fn, safe_div_fn, user, reporting_period, extra,
        )
        by_component = await compute_dashboard_by_component(
            db, scope_filter_fn, safe_div_fn, user, reporting_period, extra,
        )
        by_hc = await compute_dashboard_by_hc(
            db, scope_filter_fn, safe_div_fn, user, reporting_period, extra,
        )
        rag_delta = None
        try:
            rag_delta = await compute_rag_delta(
                db, scope_filter_fn, compute_rag_fn, safe_div_fn, user, reporting_period, "physical", extra,
            )
        except Exception:
            pass
        pareto = await compute_pareto_red_flags(
            db, scope_filter_fn, compute_rag_fn, user, reporting_period, "physical", extra,
        )
        if refresh and user.get("role") != "Admin":
            refresh = False
        return await generate_insights_payload(
            db, summary, by_component, by_hc, rag_delta, pareto, reporting_period, user, refresh=refresh,
        )

    @api.get("/public/progress")
    async def public_progress(request: Request, reporting_period: Optional[str] = None):
        _enforce_public_rate_limit(request)
        from auth import enforce_api_token_rate_limit_for_request
        await enforce_api_token_rate_limit_for_request(request)
        cache_key = f"public:progress:v4-latest-snapshot:{reporting_period or '__all__'}"
        redis_cached = cache_get(cache_key)
        if redis_cached:
            return redis_cached
        mem_key = reporting_period or "__all__"
        now = time.time()
        cached = _public_cache.get(mem_key)
        if cached and now - cached["ts"] < _PUBLIC_CACHE_TTL:
            return cached["data"]
        # Citizen dashboard: latest loaded tracker snapshot, not approval-gated open periods.
        data = await compute_public_progress(
            db, compute_rag_fn, safe_div_fn, reporting_period, state_to_hc, {},
            use_latest_snapshot=not reporting_period,
        )
        _public_cache[mem_key] = {"ts": now, "data": data}
        cache_set(cache_key, data)
        return data

    _public_user = {"role": "Viewer"}

    async def _public_extra(period=None):
        return await approved_match_filter(db, period, False, None)

    @api.get("/public/trend")
    async def public_trend(request: Request):
        _enforce_public_rate_limit(request)
        extra = await _public_extra()
        return await compute_trend_with_milestones(
            db, lambda u: {}, safe_div_fn, _public_user, extra,
        )

    @api.get("/public/heatmap")
    async def public_heatmap(
        request: Request,
        reporting_period: Optional[str] = None,
        metric: Literal["physical", "financial", "outcome"] = "physical",
    ):
        _enforce_public_rate_limit(request)
        extra = await _public_extra(reporting_period)
        return await compute_heatmap(
            db, lambda u: {}, compute_rag_fn, _public_user, reporting_period, metric, extra,
        )

    @api.get("/public/pareto-red-flags")
    async def public_pareto(
        request: Request,
        reporting_period: Optional[str] = None,
        metric: Literal["physical", "financial", "outcome"] = "physical",
    ):
        _enforce_public_rate_limit(request)
        extra = await _public_extra(reporting_period)
        return await compute_pareto_red_flags(
            db, lambda u: {}, compute_rag_fn, _public_user, reporting_period, metric, extra,
        )

    @api.get("/public/rag-delta")
    async def public_rag_delta(
        request: Request,
        reporting_period: Optional[str] = None,
        metric: Literal["physical", "financial", "outcome"] = "physical",
    ):
        _enforce_public_rate_limit(request)
        extra = await _public_extra(reporting_period)
        result = await compute_rag_delta(
            db, lambda u: {}, compute_rag_fn, safe_div_fn, _public_user, reporting_period, metric, extra,
        )
        if not result:
            raise HTTPException(status_code=400, detail="Unable to compute delta - no prior reporting period")
        return result
