"""Physical KPI aggregation must not mix incompatible UOMs into one sum/sum %."""
from dashboard_agg import (
    mean_achievement_percent,
    mean_relative_achieved_percent,
    physical_absolute_totals,
    physical_kpi_achievement_percent,
    physical_percent_with_relative_fallback,
    relative_achieved_percent_by_hc,
)


def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return round((a / b) * 100, 2)


def test_sum_nullable_preserves_explicit_zero():
    from rollup import sum_nullable
    assert sum_nullable([]) is None
    assert sum_nullable([None, None]) is None
    assert sum_nullable([0, None]) == 0
    assert sum_nullable([0]) == 0
    assert sum_nullable([10, None, 5]) == 15


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


def test_empty_absolute_totals_are_null():
    totals = physical_absolute_totals([])
    assert totals["target"] is None
    assert totals["achieved"] is None
    assert totals["uom"] is None


def test_all_null_rows_absolute_totals_are_null():
    totals = physical_absolute_totals([
        {"component": "e-Sewa Kendras", "target": None, "achieved": None},
        {"component": "Paperless Courts", "target": None, "achieved": None},
    ])
    assert totals["target"] is None
    assert totals["achieved"] is None


def test_explicit_zeros_kept_in_absolute_totals():
    totals = physical_absolute_totals([
        {"component": "e-Sewa Kendras", "target": 0, "achieved": 0},
    ])
    assert totals["target"] == 0
    assert totals["achieved"] == 0
    assert totals["uom"] == "Count"


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


def test_component_phys_percent_is_na_when_cloud_has_no_targets():
    """Without a real target, Physical % must be NA — not a relative-vs-max ranking."""
    rows = [
        {"high_court": "Allahabad", "target": 0, "achieved": 7700},
        {"high_court": "Bombay", "target": 0, "achieved": 19700},
        {"high_court": "Calcutta", "target": 0, "achieved": 9850},
    ]
    assert _safe_div(sum(r["achieved"] for r in rows), 0) is None
    assert physical_percent_with_relative_fallback(rows, _safe_div, sum_ratio=True) is None
    # Opt-in ranking remains available for non-KPI uses.
    pct = physical_percent_with_relative_fallback(
        rows, _safe_div, sum_ratio=True, allow_relative=True,
    )
    assert pct == mean_relative_achieved_percent(rows)
    assert pct is not None and 0 < pct <= 100


def test_hc_comparison_percent_is_na_when_target_missing():
    """High Court Comparison must not turn Target NA into a ranking % vs the top court."""
    madras = [{"high_court": "Madras", "target": None, "achieved": 8202.24}]
    leader = [{"high_court": "Leader", "target": None, "achieved": 24700}]
    by_hc = {"Madras": madras, "Leader": leader}
    ranking = relative_achieved_percent_by_hc(by_hc)
    assert ranking["Madras"] == round(8202.24 / 24700 * 100, 2)
    assert mean_achievement_percent(madras, _safe_div) is None
    assert physical_percent_with_relative_fallback(madras, _safe_div) is None


def test_sum_ratio_still_used_when_targets_exist():
    rows = [
        {"high_court": "A", "target": 100, "achieved": 40},
        {"high_court": "B", "target": 100, "achieved": 60},
    ]
    assert physical_percent_with_relative_fallback(rows, _safe_div, sum_ratio=True) == 50.0


def test_mixed_uom_kpi_percent_matches_count_scope():
    """When KPI cards show Count totals, Avg % must not average unrelated UOM rows."""
    rows = [
        {"component": "e-Sewa Kendras", "target": 100, "achieved": 50},
        {"component": "Cloud Computing & Storage", "target": 0, "achieved": 1000},
        {"component": "Digitisation of Court Records", "target": 10, "achieved": 100609525},
    ]
    totals = physical_absolute_totals(rows)
    assert totals["mixed_uom"] is True
    pct = physical_kpi_achievement_percent(rows, totals, _safe_div)
    assert pct == 50.0


def test_mean_skips_absurd_unit_mismatch_percent():
    rows = [
        {"component": "e-Sewa Kendras", "target": 100, "achieved": 50},
        {"component": "Digitisation of Court Records", "target": 30, "achieved": 100609525},
    ]
    assert mean_achievement_percent(rows, _safe_div) == 50.0


def test_financial_variance_null_safe():
    """Released/utilised nulls must not raise when building dashboard summary financial block."""
    released, utilized = 0.0, None
    variance = (
        round(float(released) - float(utilized), 2)
        if released is not None and utilized is not None
        else None
    )
    assert variance is None
    released, utilized = 10.5, 4.25
    variance = (
        round(float(released) - float(utilized), 2)
        if released is not None and utilized is not None
        else None
    )
    assert variance == 6.25
