"""Latest-snapshot by-component rollups for DoJ component-wise report."""
from dashboard_agg import _rows_latest_snapshot


def test_rows_latest_snapshot_picks_newest_period_per_series():
    rows = [
        {"high_court": "Allahabad", "component": "e-Sewa Kendras", "indicator": "X", "reporting_period": "2026-03", "target": 1, "achieved": 1},
        {"high_court": "Allahabad", "component": "e-Sewa Kendras", "indicator": "X", "reporting_period": "2026-06", "target": 10, "achieved": 8},
        {"high_court": "Bombay", "component": "e-Sewa Kendras", "indicator": "X", "reporting_period": "2026-06", "target": 20, "achieved": 15},
        {"high_court": "Allahabad", "component": "Cloud Computing & Storage", "indicator": "Y", "reporting_period": "2026-03", "target": 5, "achieved": 2},
        {"high_court": "Allahabad", "component": "Cloud Computing & Storage", "indicator": "Y", "reporting_period": "2026-06", "target": 99, "achieved": 99},
    ]
    out = _rows_latest_snapshot(rows, ("high_court", "component", "indicator"))
    assert len(out) == 3
    by_key = {(r["high_court"], r["component"]): r for r in out}
    assert by_key[("Allahabad", "e-Sewa Kendras")]["reporting_period"] == "2026-06"
    assert by_key[("Allahabad", "e-Sewa Kendras")]["target"] == 10
    # Cloud has no 2026-06 row in production — here 2026-06 wins when present.
    assert by_key[("Allahabad", "Cloud Computing & Storage")]["reporting_period"] == "2026-06"


def test_rows_latest_snapshot_keeps_cloud_on_older_period_when_no_newer_row():
    rows = [
        {"high_court": "Allahabad", "component": "e-Sewa Kendras", "indicator": "X", "reporting_period": "2026-06", "target": 10, "achieved": 8},
        {"high_court": "Allahabad", "component": "Cloud Computing & Storage", "indicator": "Y", "reporting_period": "2026-03", "target": 5, "achieved": 2},
    ]
    out = _rows_latest_snapshot(rows, ("high_court", "component", "indicator"))
    cloud = next(r for r in out if r["component"] == "Cloud Computing & Storage")
    assert cloud["reporting_period"] == "2026-03"
    assert cloud["achieved"] == 2
