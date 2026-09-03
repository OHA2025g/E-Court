"""National financial KPIs must sum raw amounts, then round — not sum pre-rounded rows."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rollup import (  # noqa: E402
    _financial_drop_duplicate_nsc_stages,
    financial_exact_totals_stages,
    financial_hc_rollup_stages,
    financial_rollup_stages,
)
from seed_constants import NSC_COMPONENT  # noqa: E402


def test_round_then_sum_differs_from_sum_then_round():
    # Classic float case: each 1.005 rounds to 1.00, but the true sum rounds to 3.01.
    values = [1.005, 1.005, 1.005]
    exact = sum(values)
    sum_then_round = round(exact, 2)
    round_then_sum = round(sum(round(v, 2) for v in values), 2)
    assert sum_then_round == 3.01
    assert round_then_sum == 3.0
    assert sum_then_round != round_then_sum


def test_rupee_sum_then_crore_beats_per_row_4dp():
    # Same shape as NICSI Cloud PI amounts (absolute ₹).
    rupees = [23_018_327.26, 15_962_926.72, 18_709_428.64]
    exact_crore = sum(rupees) / 1e7
    per_row_4dp = sum(round(r / 1e7, 4) for r in rupees)
    assert round(exact_crore, 4) != round(per_row_4dp, 4) or exact_crore != per_row_4dp
    assert round(exact_crore, 2) == round(sum(rupees) / 1e7, 2)


def test_financial_exact_totals_pipeline_sums_rupees_then_divides():
    stages = financial_exact_totals_stages({"reporting_period": "2026-03"})
    assert stages[0] == {"$match": {"reporting_period": "2026-03"}}
    assert any("$setWindowFields" in s for s in stages)
    group = next(s["$group"] for s in stages if "$group" in s)
    assert group["_id"] is None
    assert "released_rupees" in group
    assert "utilized_rupees" in group
    project = next(s["$project"] for s in stages if "$project" in s)
    assert project["released"]["$cond"][2] == {"$divide": ["$released_rupees", 10_000_000]}
    assert project["utilized"]["$cond"][2] == {"$divide": ["$utilized_rupees", 10_000_000]}


def test_financial_rollup_stages_use_exact_rupees_then_crore():
    """Component/HC rollups must not $sum pre-rounded crore fields."""
    stages = financial_rollup_stages({"reporting_period": "2026-06"})
    assert stages[0] == {"$match": {"reporting_period": "2026-06"}}
    group = next(s["$group"] for s in stages if "$group" in s)
    assert "fund_released_rupees" in group
    assert "fund_utilized_rupees" in group
    project = next(s["$project"] for s in stages if "$project" in s and "fund_released" in s["$project"])
    assert project["fund_released"]["$cond"][2] == {"$divide": ["$fund_released_rupees", 10_000_000]}


def test_financial_pipelines_drop_duplicate_nsc_before_grouping():
    drop = _financial_drop_duplicate_nsc_stages()
    assert drop[0]["$setWindowFields"]["output"]["_has_nsc_split"]
    match_expr = drop[1]["$match"]["$expr"]["$or"]
    assert {"$ne": ["$component", NSC_COMPONENT]} in match_expr

    for stages in (
        financial_exact_totals_stages({"reporting_period": "2026-06"}),
        financial_hc_rollup_stages({"reporting_period": "2026-06"}),
        financial_rollup_stages({"reporting_period": "2026-06"}),
    ):
        group_idx = next(i for i, s in enumerate(stages) if "$group" in s)
        assert any("$setWindowFields" in s for s in stages[:group_idx])
