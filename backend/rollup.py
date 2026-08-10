"""Roll up district-level tracker rows to HC/component aggregates for dashboards and reports."""
from __future__ import annotations

from typing import Optional

from seed_constants import (
    CLOUD_COMPUTING_COMPONENT,
    DEFAULT_STORAGE_TYPE,
    STORAGE_TYPE_OPTIONS,
)

# e-Sewa stores dual targets (DPR / CPC); dashboards use Target & Achieved as per CPC.
ESEWA_COMPONENT = "e-Sewa Kendras"


def resolve_storage_type(component: str, storage_type: Optional[str] = None) -> Optional[str]:
    """Return storage_type for Cloud Computing rows; None for all other components."""
    if component != CLOUD_COMPUTING_COMPONENT:
        return None
    st = (storage_type or "").strip()
    if not st:
        return DEFAULT_STORAGE_TYPE
    if st not in STORAGE_TYPE_OPTIONS:
        raise ValueError(
            f"Invalid Type of Storage: {storage_type!r}. "
            f"Allowed: {', '.join(STORAGE_TYPE_OPTIONS)}"
        )
    return st


def _esewa_cpc_as_target_achieved_stage() -> dict:
    """Map e-Sewa Kendras CPC fields onto target/achieved for dashboard rollups.

    Tracker keeps Target DPR / Achieved eCommittee / Target CPC / Achieved CPC
    separately with main target/achieved often null; national/component views use
    Target as per CPC and Achieved as per CPC (fall back to main fields if CPC unset).
    """
    return {
        "$addFields": {
            "target": {
                "$cond": [
                    {"$eq": ["$component", ESEWA_COMPONENT]},
                    {"$ifNull": ["$target_cpc", "$target"]},
                    "$target",
                ]
            },
            "achieved": {
                "$cond": [
                    {"$eq": ["$component", ESEWA_COMPONENT]},
                    {"$ifNull": ["$achieved_cpc", "$achieved"]},
                    "$achieved",
                ]
            },
        }
    }


def sum_nullable(values) -> Optional[float]:
    """Sum numeric values; return None when every input is missing (preserve explicit 0)."""
    nums = [float(v) for v in values if v is not None and v != ""]
    if not nums:
        return None
    return sum(nums)


def _non_null_count(field: str) -> dict:
    """Count documents where field is present and not null."""
    return {"$sum": {"$cond": [{"$eq": [f"${field}", None]}, 0, 1]}}


def _sum_or_zero(field: str) -> dict:
    return {"$sum": {"$ifNull": [f"${field}", 0]}}


def _nullable_from_sum_n(sum_field: str, n_field: str) -> dict:
    """Project null when no non-null inputs contributed to the sum."""
    return {
        "$cond": [
            {"$eq": [f"${n_field}", 0]},
            None,
            f"${sum_field}",
        ]
    }


def _group_nullable_field(src_field: str, as_name: str) -> dict:
    return {
        f"_{as_name}_sum": _sum_or_zero(src_field),
        f"_{as_name}_n": _non_null_count(src_field),
    }


def _project_nullable_field(as_name: str) -> dict:
    return {as_name: _nullable_from_sum_n(f"_{as_name}_sum", f"_{as_name}_n")}


def physical_rollup_stages(extra_match: dict | None = None) -> list:
    """Pipeline stages: match → roll up by HC+component+indicator+period (ignore district)."""
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.append(_esewa_cpc_as_target_achieved_stage())
    stages.extend([
        {"$group": {
            "_id": {
                "high_court": "$high_court",
                "component": "$component",
                "indicator": "$indicator",
                "reporting_period": "$reporting_period",
            },
            **_group_nullable_field("target", "target"),
            **_group_nullable_field("achieved", "achieved"),
        }},
        {"$project": {
            "_id": 0,
            "high_court": "$_id.high_court",
            "component": "$_id.component",
            "indicator": "$_id.indicator",
            "reporting_period": "$_id.reporting_period",
            **_project_nullable_field("target"),
            **_project_nullable_field("achieved"),
        }},
    ])
    return stages


def financial_rollup_stages(extra_match: dict | None = None) -> list:
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.extend([
        {"$group": {
            "_id": {
                "high_court": "$high_court",
                "component": "$component",
                "reporting_period": "$reporting_period",
            },
            **_group_nullable_field("fund_target", "fund_target"),
            **_group_nullable_field("fund_allocated", "fund_allocated"),
            **_group_nullable_field("fund_released", "fund_released"),
            **_group_nullable_field("fund_utilized", "fund_utilized"),
        }},
        {"$project": {
            "_id": 0,
            "high_court": "$_id.high_court",
            "component": "$_id.component",
            "reporting_period": "$_id.reporting_period",
            **_project_nullable_field("fund_target"),
            **_project_nullable_field("fund_allocated"),
            **_project_nullable_field("fund_released"),
            **_project_nullable_field("fund_utilized"),
        }},
    ])
    return stages


def physical_hc_rollup_stages(extra_match: dict | None = None) -> list:
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.append(_esewa_cpc_as_target_achieved_stage())
    stages.extend([
        {"$group": {
            "_id": "$high_court",
            **_group_nullable_field("target", "t"),
            **_group_nullable_field("achieved", "a"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("t"),
            **_project_nullable_field("a"),
        }},
    ])
    return stages


def financial_hc_rollup_stages(extra_match: dict | None = None) -> list:
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.extend([
        {"$group": {
            "_id": "$high_court",
            **_group_nullable_field("fund_released", "r"),
            **_group_nullable_field("fund_utilized", "u"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("r"),
            **_project_nullable_field("u"),
        }},
    ])
    return stages


def physical_national_totals_stages(extra_match: dict | None = None) -> list:
    """Roll up districts, then sum target/achieved nationally."""
    return physical_rollup_stages(extra_match) + [
        {"$group": {
            "_id": None,
            **_group_nullable_field("target", "target"),
            **_group_nullable_field("achieved", "achieved"),
            "count": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0,
            "count": 1,
            **_project_nullable_field("target"),
            **_project_nullable_field("achieved"),
        }},
    ]


def financial_national_totals_stages(extra_match: dict | None = None) -> list:
    return financial_rollup_stages(extra_match) + [
        {"$group": {
            "_id": None,
            **_group_nullable_field("fund_released", "released"),
            **_group_nullable_field("fund_utilized", "utilized"),
            **_group_nullable_field("fund_target", "target"),
            "count": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0,
            "count": 1,
            **_project_nullable_field("released"),
            **_project_nullable_field("utilized"),
            **_project_nullable_field("target"),
        }},
    ]


def _has_money_expr(crore_field: str, rupees_field: str) -> dict:
    return {
        "$or": [
            {"$ne": [{"$ifNull": [f"${rupees_field}", None]}, None]},
            {"$ne": [{"$ifNull": [f"${crore_field}", None]}, None]},
        ]
    }


def _amount_as_rupees_expr(crore_field: str, rupees_field: str) -> dict:
    """Prefer exact *_rupees; else treat values ≥1000 as ₹, otherwise ₹ crore → ₹.

    Returns null when both crore and rupees fields are missing (so callers can
    distinguish unset from explicit 0).
    """
    return {
        "$cond": [
            {"$not": [_has_money_expr(crore_field, rupees_field)]},
            None,
            {
                "$cond": [
                    {"$ne": [{"$ifNull": [f"${rupees_field}", None]}, None]},
                    {"$toDouble": f"${rupees_field}"},
                    {
                        "$cond": [
                            {"$gte": [{"$abs": {"$ifNull": [f"${crore_field}", 0]}}, 1000]},
                            {"$toDouble": f"${crore_field}"},
                            {"$multiply": [{"$toDouble": f"${crore_field}"}, 10_000_000]},
                        ]
                    },
                ]
            },
        ]
    }


def _exact_money_group_fields(crore_field: str, rupees_field: str, as_name: str) -> dict:
    return {
        f"{as_name}_rupees": {"$sum": {"$ifNull": [_amount_as_rupees_expr(crore_field, rupees_field), 0]}},
        f"{as_name}_n": {"$sum": {"$cond": [_has_money_expr(crore_field, rupees_field), 1, 0]}},
    }


def _exact_money_project_crore(as_name: str) -> dict:
    return {
        as_name: {
            "$cond": [
                {"$eq": [f"${as_name}_n", 0]},
                None,
                {"$divide": [f"${as_name}_rupees", 10_000_000]},
            ]
        }
    }


def financial_exact_totals_stages(extra_match: dict | None = None) -> list:
    """Sum money in absolute ₹ first, then convert once to ₹ crore.

    Avoids round-then-sum drift from per-row crore truncation (e.g. 4dp).
    Missing funds stay null (UI shows NA); explicit 0 stays 0.
    """
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.append({
        "$group": {
            "_id": None,
            **_exact_money_group_fields("fund_target", "fund_target_rupees", "target"),
            **_exact_money_group_fields("fund_allocated", "fund_allocated_rupees", "allocated"),
            **_exact_money_group_fields("fund_released", "fund_released_rupees", "released"),
            **_exact_money_group_fields("fund_utilized", "fund_utilized_rupees", "utilized"),
            "count": {"$sum": 1},
        },
    })
    stages.append({
        "$project": {
            "_id": 0,
            "count": 1,
            **_exact_money_project_crore("target"),
            **_exact_money_project_crore("allocated"),
            **_exact_money_project_crore("released"),
            **_exact_money_project_crore("utilized"),
        },
    })
    return stages


def physical_period_totals_stages(extra_match: dict | None = None) -> list:
    return physical_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$reporting_period",
            **_group_nullable_field("target", "target"),
            **_group_nullable_field("achieved", "achieved"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("target"),
            **_project_nullable_field("achieved"),
        }},
        {"$sort": {"_id": 1}},
    ]


def financial_period_totals_stages(extra_match: dict | None = None) -> list:
    return financial_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$reporting_period",
            **_group_nullable_field("fund_released", "released"),
            **_group_nullable_field("fund_utilized", "utilized"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("released"),
            **_project_nullable_field("utilized"),
        }},
        {"$sort": {"_id": 1}},
    ]


def physical_component_hc_stages(extra_match: dict | None = None) -> list:
    return physical_rollup_stages(extra_match) + [
        {"$group": {
            "_id": {"component": "$component", "high_court": "$high_court"},
            **_group_nullable_field("target", "t"),
            **_group_nullable_field("achieved", "a"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("t"),
            **_project_nullable_field("a"),
        }},
    ]


def financial_component_hc_stages(extra_match: dict | None = None) -> list:
    return financial_rollup_stages(extra_match) + [
        {"$group": {
            "_id": {"component": "$component", "high_court": "$high_court"},
            **_group_nullable_field("fund_released", "r"),
            **_group_nullable_field("fund_utilized", "u"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("r"),
            **_project_nullable_field("u"),
        }},
    ]


def apply_district_filter(q: dict, district: str | None) -> dict:
    """Extend Mongo query with district filter."""
    if district is None or district == "":
        return q
    if district == "__hc__":
        q["district"] = None
        return q
    q["district"] = district
    return q


def entry_query_key_physical(body: dict) -> dict:
    q = {
        "high_court": body["high_court"],
        "component": body["component"],
        "indicator": body["indicator"],
        "reporting_period": body["reporting_period"],
        "district": body.get("district"),
        "storage_type": resolve_storage_type(body.get("component") or "", body.get("storage_type")),
    }
    return q


def entry_query_key_financial(body: dict) -> dict:
    return {
        "high_court": body["high_court"],
        "component": body["component"],
        "reporting_period": body["reporting_period"],
        "district": body.get("district"),
    }


def outcome_rollup_stages(extra_match: dict | None = None) -> list:
    """Roll up district-level outcome rows by KPI key (ignore district)."""
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.extend([
        {"$group": {
            "_id": {
                "high_court": "$high_court",
                "subject": "$subject",
                "kpi_id": "$kpi_id",
                "reporting_period": "$reporting_period",
                "granularity": "$granularity",
            },
            **_group_nullable_field("value", "value"),
            **_group_nullable_field("baseline", "baseline"),
        }},
        {"$project": {
            "_id": 0,
            "high_court": "$_id.high_court",
            "subject": "$_id.subject",
            "kpi_id": "$_id.kpi_id",
            "reporting_period": "$_id.reporting_period",
            "granularity": "$_id.granularity",
            **_project_nullable_field("value"),
            **_project_nullable_field("baseline"),
        }},
    ])
    return stages


def outcome_subject_hc_stages(extra_match: dict | None = None) -> list:
    """Roll up outcome rows to subject × high_court for heatmap."""
    return outcome_rollup_stages(extra_match) + [
        {"$group": {
            "_id": {"subject": "$subject", "high_court": "$high_court"},
            **_group_nullable_field("value", "value"),
            **_group_nullable_field("baseline", "baseline"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("value"),
            **_project_nullable_field("baseline"),
        }},
    ]


def outcome_period_totals_stages(extra_match: dict | None = None) -> list:
    """National outcome totals by reporting period (for trend)."""
    return outcome_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$reporting_period",
            **_group_nullable_field("value", "value"),
            **_group_nullable_field("baseline", "baseline"),
        }},
        {"$project": {
            "_id": 1,
            **_project_nullable_field("value"),
            **_project_nullable_field("baseline"),
        }},
        {"$sort": {"_id": 1}},
    ]


def outcome_period_reported_stages(extra_match: dict | None = None) -> list:
    """Outcome KPI reporting coverage by period (% with value populated)."""
    return outcome_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$reporting_period",
            "total": {"$sum": 1},
            "reported": {"$sum": {"$cond": [{"$ne": ["$value", None]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]


def outcome_hc_rollup_stages(extra_match: dict | None = None) -> list:
    """Roll up outcome KPIs to high_court reporting coverage %."""
    return outcome_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$high_court",
            "total": {"$sum": 1},
            "reported": {"$sum": {"$cond": [{"$ne": ["$value", None]}, 1, 0]}},
        }},
    ]
