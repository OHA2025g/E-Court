"""Financial YoY report uses latest snapshot per HC×component (no double-count)."""
from dashboard_agg import _rows_latest_snapshot


def test_yoy_latest_snapshot_picks_newer_month_not_sum():
    rows = [
        {"high_court": "Allahabad", "component": "e-Sewa Kendras", "reporting_period": "2026-06",
         "fund_allocated": None, "fund_released": 304.63, "fund_utilized": 202.8},
        {"high_court": "Allahabad", "component": "e-Sewa Kendras", "reporting_period": "2026-07",
         "fund_allocated": None, "fund_released": 320.0, "fund_utilized": 210.0},
        {"high_court": "Allahabad", "component": "Cloud Computing & Storage", "reporting_period": "2026-03",
         "fund_allocated": 257.81, "fund_released": 185.63, "fund_utilized": 164.94},
    ]
    latest = _rows_latest_snapshot(rows, ("high_court", "component"))
    esk = next(r for r in latest if r["component"] == "e-Sewa Kendras")
    assert esk["reporting_period"] == "2026-07"
    assert esk["fund_released"] == 320.0
    cloud = next(r for r in latest if "Cloud" in r["component"])
    assert cloud["reporting_period"] == "2026-03"
