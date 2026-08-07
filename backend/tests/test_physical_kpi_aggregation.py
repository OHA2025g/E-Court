"""Physical KPI aggregation must not mix incompatible UOMs into one sum/sum %."""
from dashboard_agg import (
    mean_achievement_percent,
    physical_absolute_totals,
    relative_achieved_percent_by_hc,
)


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


def test_mixed_uom_shows_count_absolute_totals():
    """National KPI cards show Count totals instead of dashes when UOMs are mixed."""
    rows = [
        {"component": "e-Sewa Kendras", "target": 100, "achieved": 50},
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 1000},
        {"component": "Digitisation of Court Records", "target": 10, "achieved": 2},
    ]
    totals = physical_absolute_totals(rows)
    assert totals["mixed_uom"] is True
    assert totals["uom"] == "Count"
    assert totals["absolute_scope"] == "Count"
    assert totals["target"] == 100
    assert totals["achieved"] == 50


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
    assert _safe_div(totals["achieved"], totals["target"]) == 70.0


def test_cloud_only_shows_storage_totals():
    rows = [
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 1900},
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 400},
    ]
    totals = physical_absolute_totals(rows)
    assert totals["mixed_uom"] is False
    assert totals["uom"] == "GB / TB / PB"
    assert totals["achieved"] == 2300


def test_hc_style_mean_not_inflated_by_cloud_gb():
    """Mirrors High Court drill-down rows that previously showed 50,000%+ Achieved %."""
    rows = [
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 1900},
        {"component": "Digitisation of Court Records", "target": 3.5889, "achieved": 0},
    ]
    assert _safe_div(
        sum(r["achieved"] for r in rows),
        sum(r["target"] for r in rows),
    ) > 1000
    assert mean_achievement_percent(rows, _safe_div) == 0.0

    rows2 = [
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 7700},
        {"component": "Digitisation of Court Records", "target": 277.3673, "achieved": 204.5787},
        {"component": "e-Sewa Kendras", "target": 353, "achieved": 111},
    ]
    pct = mean_achievement_percent(rows2, _safe_div)
    assert pct is not None and pct < 100
    expected = round(
        ((204.5787 / 277.3673) * 100 + (111 / 353) * 100) / 2,
        2,
    )
    assert pct == expected


def test_relative_achieved_percent_by_hc_for_cloud_without_targets():
    by_hc = {
        "Allahabad": [{"achieved": 7700, "target": None}],
        "Bombay": [{"achieved": 19700, "target": None}],
        "Empty": [{"achieved": 0, "target": None}],
    }
    out = relative_achieved_percent_by_hc(by_hc)
    assert out["Bombay"] == 100.0
    assert out["Allahabad"] == round(7700 / 19700 * 100, 2)
    assert "Empty" not in out
