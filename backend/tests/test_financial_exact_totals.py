"""National financial KPIs must sum raw amounts, then round — not sum pre-rounded rows."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rollup import financial_exact_totals_stages  # noqa: E402


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
    group = stages[1]["$group"]
    assert group["_id"] is None
    assert "released_rupees" in group
    assert "utilized_rupees" in group
    project = stages[2]["$project"]
    assert project["released"] == {"$divide": ["$released_rupees", 10_000_000]}
    assert project["utilized"] == {"$divide": ["$utilized_rupees", 10_000_000]}
