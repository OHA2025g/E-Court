"""Physical KPI aggregation must not mix incompatible UOMs into one sum/sum %."""
from dashboard_agg import mean_achievement_percent, physical_absolute_totals


def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return round((a / b) * 100, 2)


def test_mean_achievement_skips_zero_target_cloud_gb():
    rows = [
        {"component": "e-Sewa Kendras", "target": 4199, "achieved": 2236},
        {"component": "Digitisation of Court Records", "target": 3108.77, "achieved": 579.54},
        # Cloud GB with no target previously inflated national % to 2400%+
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 172900},
    ]
    pct = mean_achievement_percent(rows, _safe_div)
    expected = round(((2236 / 4199) * 100 + (579.54 / 3108.77) * 100) / 2, 2)
    assert pct == expected


def test_mixed_uom_hides_absolute_totals():
    rows = [
        {"component": "e-Sewa Kendras", "target": 100, "achieved": 50},
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 1000},
        {"component": "Digitisation of Court Records", "target": 10, "achieved": 2},
    ]
    totals = physical_absolute_totals(rows)
    assert totals["mixed_uom"] is True
    assert totals["target"] is None
    assert totals["achieved"] is None


def test_single_uom_keeps_absolute_totals():
    rows = [
        {"component": "e-Sewa Kendras", "target": 40, "achieved": 30},
        {"component": "Paperless Courts", "target": 60, "achieved": 40},
    ]
    totals = physical_absolute_totals(rows)
    assert totals["mixed_uom"] is False
    assert totals["target"] == 100
    assert totals["achieved"] == 70
    assert totals["uom"] == "Count"
    # Homogeneous UOM uses ratio-of-sums (not distorted by zero-target outliers).
    assert _safe_div(totals["achieved"], totals["target"]) == 70.0
