"""Public progress uses latest tracker snapshot (not approval-gated open periods)."""
from dashboard_agg import (
    _financial_totals_from_rows,
    _hc_percent_physical_from_rows,
    _rows_latest_snapshot,
    physical_absolute_totals,
    physical_kpi_achievement_percent,
)


def _safe_div(a, b):
    if a is None or b is None or not b:
        return None
    return round((float(a) / float(b)) * 100, 2)


def test_latest_snapshot_picks_2026_06_over_older_cloud_window():
    rows = [
        {
            "high_court": "Delhi",
            "component": "e-Sewa Kendras",
            "indicator": "No of sites prepared (in Absolute Count)",
            "reporting_period": "2026-03",
            "target": 10,
            "achieved": 5,
        },
        {
            "high_court": "Delhi",
            "component": "e-Sewa Kendras",
            "indicator": "No of sites prepared (in Absolute Count)",
            "reporting_period": "2026-06",
            "target": 100,
            "achieved": 80,
        },
    ]
    latest = _rows_latest_snapshot(rows, ("high_court", "component", "indicator"))
    assert len(latest) == 1
    assert latest[0]["reporting_period"] == "2026-06"
    totals = physical_absolute_totals(latest)
    assert physical_kpi_achievement_percent(latest, totals, _safe_div) == 80.0


def test_financial_totals_from_snapshot_rows():
    rows = [
        {"high_court": "Delhi", "component": "Cloud", "reporting_period": "2026-06", "fund_released": 10, "fund_utilized": 4},
        {"high_court": "Delhi", "component": "Digitisation", "reporting_period": "2026-06", "fund_released": 20, "fund_utilized": 10},
    ]
    totals = _financial_totals_from_rows(rows)
    assert totals["released"] == 30
    assert totals["utilized"] == 14


def test_hc_percent_from_snapshot_rows():
    rows = [
        {"high_court": "Delhi", "component": "A", "indicator": "i1", "reporting_period": "2026-06", "target": 10, "achieved": 8},
        {"high_court": "Delhi", "component": "B", "indicator": "i2", "reporting_period": "2026-06", "target": 10, "achieved": 6},
    ]
    hc = _hc_percent_physical_from_rows(rows, _safe_div)
    assert hc["Delhi"] == 70.0
