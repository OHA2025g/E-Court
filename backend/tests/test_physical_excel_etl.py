"""Unit tests for physical Excel ETL transform."""
from physical_excel import (
    pages_to_crore,
    transform_physical_achieved_sep2025_rows,
    merge_into_physical_baseline,
)


def test_pages_to_crore():
    assert pages_to_crore(2773672624) == 277.3673
    assert pages_to_crore(0) == 0.0
    assert pages_to_crore(None) is None


def test_transform_physical_achieved_sep2025_rows():
    rows = [
        ("Sr. No.", "High Courts", "Digitization", None, None, "eSewa Kendras", None, None, None, None, None),
        (None, None, "Target Pgs", "Achieved Pgs", "%", "Target DPR", "Ach eC", "%", "Target CPC", "Ach CPC", "%"),
        (1, "Allahabad", 10_000_000, 20_000_000, 2.0, 353, 3, 0.01, 173, 111, 0.64),
        (2, "Orissa", 5_000_000, 0, 0, 181, 75, 0.4, 197, 197, 1),
        (3, "Gauhati (Assam)", 1_000_000, 500_000, 0.5, None, None, None, None, None, None),
    ]
    result = transform_physical_achieved_sep2025_rows(rows)
    assert result["stats"]["unknown_high_courts"] == 0
    # Allahabad dig + esk, Orissa dig + esk, Assam dig only = 5
    assert result["stats"]["records"] == 5
    dig = next(
        r for r in result["records"]
        if r["high_court"] == "Allahabad" and r["component"] == "Digitisation of Court Records"
    )
    assert dig["target"] == 1.0
    assert dig["achieved"] == 2.0
    assert dig["indicator"] == "No of pages digitized (in Cr.)"
    esk = next(
        r for r in result["records"]
        if r["high_court"] == "Odisha" and r["component"] == "e-Sewa Kendras"
    )
    assert esk["target"] is None
    assert esk["achieved"] is None
    assert esk["target_dpr"] == 181.0
    assert esk["achieved_ecommittee"] == 75.0
    assert esk["target_cpc"] == 197.0
    assert esk["achieved_cpc"] == 197.0


def test_merge_into_physical_baseline():
    baseline = [{
        "high_court": "Allahabad",
        "component": "Digitisation of Court Records",
        "indicator": "No of pages digitized (in Cr.)",
        "target": 100.0,
        "achieved": 50.0,
    }]
    records = [{
        "high_court": "Allahabad",
        "component": "Digitisation of Court Records",
        "indicator": "No of pages digitized (in Cr.)",
        "target": 277.3673,
        "achieved": 204.5787,
    }]
    merged, stats = merge_into_physical_baseline(baseline, records)
    assert stats["updated"] == 1
    assert merged[0]["achieved"] == 204.5787
    assert merged[0]["target"] == 277.3673
