"""Variance / outlier detection (>3σ from rolling trend)."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends

from rollup import financial_rollup_stages, outcome_rollup_stages, physical_rollup_stages


def _sigma_flags(history: dict, current_period: str, build_flag) -> list:
    flags = []
    for key, vals in history.items():
        if len(vals) < 3:
            continue
        cur = vals[-1]
        prior = vals[:-1]
        mean = sum(prior) / len(prior)
        var = sum((x - mean) ** 2 for x in prior) / len(prior)
        std = var ** 0.5
        if std > 0 and abs(cur - mean) > 3 * std:
            flags.append(build_flag(key, cur, mean, std, current_period))
    return flags


async def _period_window(db, collection: str, reporting_period: str) -> list:
    periods = await getattr(db, collection).distinct("reporting_period")
    periods = sorted(p for p in periods if p <= reporting_period)[-7:]
    if reporting_period not in periods:
        periods.append(reporting_period)
    return periods


async def detect_physical_anomalies(db, reporting_period: str, extra_match: Optional[dict] = None) -> list:
    periods = await _period_window(db, "physical_entries", reporting_period)
    history: dict[tuple, list[float]] = {}
    for p in periods:
        match = {"reporting_period": p}
        if extra_match:
            from period_policy import merge_match
            match = merge_match(match, extra_match)
        rows = await db.physical_entries.aggregate(physical_rollup_stages(match)).to_list(50000)
        for r in rows:
            key = (r.get("high_court"), r.get("component"), r.get("indicator"))
            t, a = r.get("target") or 0, r.get("achieved") or 0
            pct = (a / t * 100) if t else None
            if pct is not None:
                history.setdefault(key, []).append(pct)
    return _sigma_flags(
        history,
        reporting_period,
        lambda key, cur, mean, std, period: {
            "tracker": "physical",
            "high_court": key[0],
            "component": key[1],
            "indicator": key[2],
            "current_percent": cur,
            "mean_percent": round(mean, 2),
            "std": round(std, 2),
            "reporting_period": period,
        },
    )


async def detect_financial_anomalies(db, reporting_period: str, extra_match: Optional[dict] = None) -> list:
    periods = await _period_window(db, "financial_entries", reporting_period)
    history: dict[tuple, list[float]] = {}
    for p in periods:
        match = {"reporting_period": p}
        if extra_match:
            from period_policy import merge_match
            match = merge_match(match, extra_match)
        rows = await db.financial_entries.aggregate(financial_rollup_stages(match)).to_list(50000)
        for r in rows:
            key = (r.get("high_court"), r.get("component"))
            released, utilized = r.get("fund_released") or 0, r.get("fund_utilized") or 0
            pct = (utilized / released * 100) if released else None
            if pct is not None:
                history.setdefault(key, []).append(pct)
    return _sigma_flags(
        history,
        reporting_period,
        lambda key, cur, mean, std, period: {
            "tracker": "financial",
            "high_court": key[0],
            "component": key[1],
            "current_percent": cur,
            "mean_percent": round(mean, 2),
            "std": round(std, 2),
            "reporting_period": period,
        },
    )


async def detect_outcome_anomalies(db, reporting_period: str, extra_match: Optional[dict] = None) -> list:
    periods = await _period_window(db, "outcome_entries", reporting_period)
    history: dict[tuple, list[float]] = {}
    for p in periods:
        match = {"reporting_period": p}
        if extra_match:
            from period_policy import merge_match
            match = merge_match(match, extra_match)
        rows = await db.outcome_entries.aggregate(outcome_rollup_stages(match)).to_list(50000)
        for r in rows:
            key = (r.get("high_court"), r.get("subject"), r.get("kpi_id"))
            baseline, value = r.get("baseline") or 0, r.get("value")
            if value is None:
                continue
            metric = (value / baseline * 100) if baseline else float(value)
            history.setdefault(key, []).append(metric)
    return _sigma_flags(
        history,
        reporting_period,
        lambda key, cur, mean, std, period: {
            "tracker": "outcome",
            "high_court": key[0],
            "subject": key[1],
            "kpi_id": key[2],
            "current_value": cur,
            "mean_value": round(mean, 2),
            "std": round(std, 2),
            "reporting_period": period,
        },
    )


def register_anomaly_routes(api, db, require_fully_authenticated, scope_filter_fn):
    from period_policy import approved_match_filter

    _DETECTORS = {
        "physical": detect_physical_anomalies,
        "financial": detect_financial_anomalies,
        "outcome": detect_outcome_anomalies,
    }

    @api.get("/anomalies")
    async def list_anomalies(
        reporting_period: str,
        tracker: Literal["physical", "financial", "outcome", "all"] = "all",
        user: dict = Depends(require_fully_authenticated),
    ):
        extra = await approved_match_filter(db, reporting_period, False, user)
        trackers = list(_DETECTORS.keys()) if tracker == "all" else [tracker]
        flags = []
        for name in trackers:
            flags.extend(await _DETECTORS[name](db, reporting_period, extra))
        if user.get("role") == "CPC" and user.get("high_court"):
            flags = [f for f in flags if f.get("high_court") == user["high_court"]]
        return {"reporting_period": reporting_period, "tracker": tracker, "flags": flags}
