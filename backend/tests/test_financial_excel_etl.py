"""Unit tests for financial Excel ETL transform."""
from financial_excel import (
    map_component,
    map_high_court,
    merge_released_into_seed_baseline,
    merge_utilised_into_seed_baseline,
    rupees_to_crore,
    transform_funds_released_rows,
    transform_funds_utilised_rows,
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
    assert map_component("eSewa Kendras (Porta Cabins+LAN Points)") == "e-Sewa Kendras"
    assert map_component("Addl. Hardware Components") == "Additional Hardware — Phase I & II"
    assert map_component("Handheld Devices/ NSTEP") == "NSTEP Expansion"
    assert map_component("Capacity Building /Training") == "ICT Training / Change Management"
    assert map_component("Software Development/ Technical Manpower") == "Software Development"
    assert map_component("Additional requirement (For North Eastern States)") == "ICT for Newly Set-Up Courts"
    assert map_component("High Courts") is None


def test_rupees_to_crore():
    assert rupees_to_crore(127256616) == 12.7257
    assert rupees_to_crore(0) == 0.0
    assert rupees_to_crore(None) is None


def test_transform_funds_released_rows():
    rows = [
        ("Sr. No.", "High Courts", "e-Sewa Kendras", "Paperless Courts"),
        (1, "Allahabad", 10_000_000, 20_000_000),
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
    assert allahabad_esk["fund_utilized"] is None


def test_transform_funds_utilised_rows():
    rows = [
        (
            "Sr. No.", "High Courts",
            "Digitization / Scanning (High Courts + Distt. Courts)",
            "eSewa Kendras (Porta Cabins+LAN Points)",
            "Addl. Hardware Components",
        ),
        (1, "Allahabad", 10_000_000, 20_000_000, 30_000_000),
        ("Total (In Cr.)", None, 0, 0, 0),
    ]
    result = transform_funds_utilised_rows(rows)
    assert result["stats"]["unknown_high_courts"] == 0
    assert result["stats"]["records"] == 3
    dig = next(
        r for r in result["records"]
        if r["component"] == "Digitisation of Court Records"
    )
    assert dig["fund_utilized"] == 1.0
    assert dig["fund_released"] is None


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


def test_merge_utilised_into_seed_baseline():
    baseline = [{
        "high_court": "Allahabad",
        "component": "Digitisation of Court Records",
        "fund_released": 143.6,
        "fund_utilized": 1.0,
    }]
    records = [{
        "high_court": "Allahabad",
        "component": "Digitisation of Court Records",
        "fund_utilized": 29.748,
        "remarks": "ETL utilised",
    }]
    merged, stats = merge_utilised_into_seed_baseline(baseline, records)
    assert stats["updated"] == 1
    assert merged[0]["fund_utilized"] == 29.748
    assert merged[0]["fund_released"] == 143.6
