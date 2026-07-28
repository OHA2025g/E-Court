"""Unit tests for financial Excel ETL transform."""
from financial_excel import (
    map_component,
    map_high_court,
    merge_released_into_seed_baseline,
    rupees_to_crore,
    transform_funds_released_rows,
)


def test_map_high_court_aliases():
    assert map_high_court("Orissa") == "Odisha"
    assert map_high_court("Gauhati (Assam)") == "Gauhati – Assam"
    assert map_high_court("Gauhati (Nagaland)") == "Gauhati - Nagaland"
    assert map_high_court("Unknown HC") is None


def test_map_component_aliases():
    assert map_component("Digitization of entire court records") == "Digitisation of Court Records"
    assert map_component("Solar power for ICT infrastructure") == "Solar Power for ICT"
    assert map_component("Additional hardware (Phase I & II replacement)") == "Additional Hardware — Phase I & II"
    assert map_component("High Courts") is None


def test_rupees_to_crore():
    assert rupees_to_crore(127256616) == 12.7257
    assert rupees_to_crore(0) == 0.0
    assert rupees_to_crore(None) is None


def test_transform_funds_released_rows():
    rows = [
        ("Sr. No.", "High Courts", "e-Sewa Kendras", "Paperless Courts"),
        (1, "Allahabad", 10_000_000, 20_000_000),  # 1 Cr, 2 Cr
        (2, "Orissa", 5_000_000, 0),
    ]
    result = transform_funds_released_rows(rows)
    assert result["stats"]["records"] == 4
    assert result["stats"]["unique_high_courts"] == 2
    allahabad_esk = next(
        r for r in result["records"]
        if r["high_court"] == "Allahabad" and r["component"] == "e-Sewa Kendras"
    )
    assert allahabad_esk["fund_released"] == 1.0
    odisha = next(r for r in result["records"] if r["high_court"] == "Odisha")
    assert odisha["fund_released"] in (0.5, 0.0)


def test_merge_released_into_seed_baseline():
    baseline = [{
        "high_court": "Allahabad",
        "component": "e-Sewa Kendras",
        "fund_target": 10.0,
        "fund_allocated": 9.0,
        "fund_released": 1.0,
        "fund_utilized": 0.5,
    }]
    records = [{
        "high_court": "Allahabad",
        "component": "e-Sewa Kendras",
        "fund_released": 12.7257,
        "remarks": "ETL",
    }]
    merged, stats = merge_released_into_seed_baseline(baseline, records)
    assert stats["updated"] == 1
    assert merged[0]["fund_released"] == 12.7257
    assert merged[0]["fund_utilized"] == 0.5
    assert merged[0]["fund_target"] == 10.0
