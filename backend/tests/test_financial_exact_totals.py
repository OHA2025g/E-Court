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


def test_financial_exact_totals_pipeline_has_no_intermediate_group():
    stages = financial_exact_totals_stages({"reporting_period": "2026-03"})
    assert stages[0] == {"$match": {"reporting_period": "2026-03"}}
    group = stages[1]["$group"]
    assert group["_id"] is None
    assert "$sum" in group["released"]
    assert "$sum" in group["utilized"]
