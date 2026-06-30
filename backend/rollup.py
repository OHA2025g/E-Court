"""Roll up district-level tracker rows to HC/component aggregates for dashboards and reports."""


def physical_rollup_stages(extra_match: dict | None = None) -> list:
    """Pipeline stages: match → roll up by HC+component+indicator+period (ignore district)."""
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.extend([
        {"$group": {
            "_id": {
                "high_court": "$high_court",
                "component": "$component",
                "indicator": "$indicator",
                "reporting_period": "$reporting_period",
            },
            "target": {"$sum": {"$ifNull": ["$target", 0]}},
            "achieved": {"$sum": {"$ifNull": ["$achieved", 0]}},
        }},
        {"$project": {
            "_id": 0,
            "high_court": "$_id.high_court",
            "component": "$_id.component",
            "indicator": "$_id.indicator",
            "reporting_period": "$_id.reporting_period",
            "target": 1,
            "achieved": 1,
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
            "fund_target": {"$sum": {"$ifNull": ["$fund_target", 0]}},
            "fund_allocated": {"$sum": {"$ifNull": ["$fund_allocated", 0]}},
            "fund_released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
            "fund_utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
        }},
        {"$project": {
            "_id": 0,
            "high_court": "$_id.high_court",
            "component": "$_id.component",
            "reporting_period": "$_id.reporting_period",
            "fund_target": 1,
            "fund_allocated": 1,
            "fund_released": 1,
            "fund_utilized": 1,
        }},
    ])
    return stages


def physical_hc_rollup_stages(extra_match: dict | None = None) -> list:
    stages = []
    if extra_match:
        stages.append({"$match": extra_match})
    stages.extend([
        {"$group": {
            "_id": "$high_court",
            "t": {"$sum": {"$ifNull": ["$target", 0]}},
            "a": {"$sum": {"$ifNull": ["$achieved", 0]}},
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
            "r": {"$sum": {"$ifNull": ["$fund_released", 0]}},
            "u": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
        }},
    ])
    return stages


def physical_national_totals_stages(extra_match: dict | None = None) -> list:
    """Roll up districts, then sum target/achieved nationally."""
    return physical_rollup_stages(extra_match) + [
        {"$group": {
            "_id": None,
            "target": {"$sum": {"$ifNull": ["$target", 0]}},
            "achieved": {"$sum": {"$ifNull": ["$achieved", 0]}},
            "count": {"$sum": 1},
        }},
    ]


def financial_national_totals_stages(extra_match: dict | None = None) -> list:
    return financial_rollup_stages(extra_match) + [
        {"$group": {
            "_id": None,
            "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
            "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
            "target": {"$sum": {"$ifNull": ["$fund_target", 0]}},
            "count": {"$sum": 1},
        }},
    ]


def physical_period_totals_stages(extra_match: dict | None = None) -> list:
    return physical_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$reporting_period",
            "target": {"$sum": {"$ifNull": ["$target", 0]}},
            "achieved": {"$sum": {"$ifNull": ["$achieved", 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]


def financial_period_totals_stages(extra_match: dict | None = None) -> list:
    return financial_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$reporting_period",
            "released": {"$sum": {"$ifNull": ["$fund_released", 0]}},
            "utilized": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]


def physical_component_hc_stages(extra_match: dict | None = None) -> list:
    return physical_rollup_stages(extra_match) + [
        {"$group": {
            "_id": {"component": "$component", "high_court": "$high_court"},
            "t": {"$sum": {"$ifNull": ["$target", 0]}},
            "a": {"$sum": {"$ifNull": ["$achieved", 0]}},
        }},
    ]


def financial_component_hc_stages(extra_match: dict | None = None) -> list:
    return financial_rollup_stages(extra_match) + [
        {"$group": {
            "_id": {"component": "$component", "high_court": "$high_court"},
            "r": {"$sum": {"$ifNull": ["$fund_released", 0]}},
            "u": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
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
    return {
        "high_court": body["high_court"],
        "component": body["component"],
        "indicator": body["indicator"],
        "reporting_period": body["reporting_period"],
        "district": body.get("district"),
    }


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
            "value": {"$sum": {"$ifNull": ["$value", 0]}},
            "baseline": {"$sum": {"$ifNull": ["$baseline", 0]}},
        }},
        {"$project": {
            "_id": 0,
            "high_court": "$_id.high_court",
            "subject": "$_id.subject",
            "kpi_id": "$_id.kpi_id",
            "reporting_period": "$_id.reporting_period",
            "granularity": "$_id.granularity",
            "value": 1,
            "baseline": 1,
        }},
    ])
    return stages


def outcome_subject_hc_stages(extra_match: dict | None = None) -> list:
    """Roll up outcome rows to subject × high_court for heatmap."""
    return outcome_rollup_stages(extra_match) + [
        {"$group": {
            "_id": {"subject": "$subject", "high_court": "$high_court"},
            "value": {"$sum": {"$ifNull": ["$value", 0]}},
            "baseline": {"$sum": {"$ifNull": ["$baseline", 0]}},
        }},
    ]


def outcome_period_totals_stages(extra_match: dict | None = None) -> list:
    """National outcome totals by reporting period (for trend)."""
    return outcome_rollup_stages(extra_match) + [
        {"$group": {
            "_id": "$reporting_period",
            "value": {"$sum": {"$ifNull": ["$value", 0]}},
            "baseline": {"$sum": {"$ifNull": ["$baseline", 0]}},
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
