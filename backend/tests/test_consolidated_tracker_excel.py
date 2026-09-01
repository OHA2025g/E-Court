"""Unit tests for consolidated Physical/Financial tracker Excel ETL."""
from consolidated_tracker_excel import (
    financial_records_to_bulk_rows,
    parse_messy_quantity,
    transform_consolidated_financial_rows,
    transform_consolidated_physical_rows,
)


def test_parse_messy_quantity_basics():
    assert parse_messy_quantity(124) == (124.0, "")
    assert parse_messy_quantity("124 (at the time of demand of funds)")[0] == 124.0
    assert parse_messy_quantity("246 Cr.")[0] == 246.0
    assert parse_messy_quantity("207 Cr. Approximately")[0] == 207.0
    assert parse_messy_quantity("500000000 pages", prefer_crore_pages=True)[0] == 50.0
    assert parse_messy_quantity("14.81 Lakh", prefer_crore_pages=True)[0] == 0.1481
    assert parse_messy_quantity("47+35=82")[0] == 82.0
    assert parse_messy_quantity("90 Sites")[0] == 90.0
    assert parse_messy_quantity("NA")[0] is None
    assert parse_messy_quantity("1,36,98,953")[0] == 13698953.0
    assert parse_messy_quantity(100609525, prefer_crore_pages=True)[0] == 10.061
    assert parse_messy_quantity(30, prefer_crore_pages=True)[0] == 30.0
    assert parse_messy_quantity(6282627, prefer_crore_pages=True)[0] == 0.6283


def test_transform_consolidated_physical_rows():
    rows = [
        (
            "Sr. No.", "Court", "Component", "Description",
            "Start Period", "End Period", "Target", "Achieved", "Physical Tracker Remarks",
        ),
        (
            1, "Allahabad", "e-Sewa Kendras",
            "Number of e-sewa kendras in court complexes (in Absolute Count)",
            None, None, "124 (at the time of demand of funds)", 124, "ok",
        ),
        (
            2, "Orissa", "Digitization of entire court records",
            "Number of pages digitized (in Cr.)",
            None, None, "10 Cr.", "5 Cr.", None,
        ),
        (
            3, "Allahabad", "ICT in newly Steup Court Rooms [set up after 31.12.2019]",
            "Number of Courts (in Absolute Count)",
            None, None, "47+35=82", 47, None,
        ),
        (
            4, "Allahabad", "ICT in newly Steup Court Complex [set up after 31.12.2019]",
            "Number of Court Complex (in Absolute Count)",
            None, None, 10, 5, None,
        ),
    ]
    result = transform_consolidated_physical_rows(rows)
    assert result["stats"]["unknown_high_courts"] == 0
    assert result["stats"]["unknown_components"] == 0
    # eSewa + digitization + two ICT newly (rooms + complex) = 4
    assert result["stats"]["records"] == 4

    esk = next(r for r in result["records"] if r["component"] == "e-Sewa Kendras")
    assert esk["high_court"] == "Allahabad"
    assert esk["target"] is None
    assert esk["achieved"] is None
    assert esk["target_dpr"] == 124.0
    assert esk["achieved_cpc"] == 124.0

    dig = next(r for r in result["records"] if r["component"] == "Digitisation of Court Records")
    assert dig["high_court"] == "Odisha"
    assert dig["target"] == 10.0
    assert dig["achieved"] == 5.0

    nsc_rows = [r for r in result["records"] if r["component"] == "ICT for Newly Set-Up Courts"]
    assert len(nsc_rows) == 2
    rooms = next(r for r in nsc_rows if r["source_kind"] == "rooms")
    complex_row = next(r for r in nsc_rows if r["source_kind"] == "complex")
    assert rooms["indicator"] == "No of new Court Rooms covered (in Absolute Count)"
    assert rooms["achieved"] == 47.0
    assert rooms["target"] == 82.0
    assert complex_row["indicator"] == "No of new Court Complexes covered (in Absolute Count)"
    assert complex_row["achieved"] == 5.0
    assert complex_row["target"] == 10.0


def test_transform_consolidated_financial_rows_splits_rooms_complex():
    rows = [
        (
            "Sr. No.", "Court", "Component", "Description",
            "Start Period", "End Period", "Funds Released (₹)", "Funds Utilised (₹)",
            "Financial Tracker Remarks",
        ),
        (1, "Allahabad", "e-Sewa Kendras", "x", None, None, 10_000_000, 5_000_000, "a"),
        (
            2, "Allahabad", "ICT in newly Steup Court Rooms [set up after 31.12.2019]",
            "x", None, None, 20_000_000, 10_000_000, None,
        ),
        (
            3, "Allahabad", "ICT in newly Steup Court Complex [set up after 31.12.2019]",
            "x", None, None, 5_000_000, 2_000_000, None,
        ),
    ]
    result = transform_consolidated_financial_rows(rows)
    assert result["stats"]["records"] == 3
    rooms = next(
        r for r in result["records"]
        if r["component"] == "ICT for Newly Set-Up Courts (Court Rooms)"
    )
    complex_row = next(
        r for r in result["records"]
        if r["component"] == "ICT for Newly Set-Up Courts (Court Complex)"
    )
    assert rooms["fund_released"] == 2.0
    assert rooms["fund_utilized"] == 1.0
    assert complex_row["fund_released"] == 0.5
    assert complex_row["fund_utilized"] == 0.2
    esk = next(r for r in result["records"] if r["component"] == "e-Sewa Kendras")
    assert esk["fund_released"] == 1.0
    assert esk["fund_utilized"] == 0.5


def test_financial_bulk_rows_as_rupees():
    records = [{
        "high_court": "Allahabad",
        "component": "e-Sewa Kendras",
        "district": "",
        "fund_released": 13.7056616,
        "fund_utilized": 8.3854815,
        "fund_released_rupees": 137056616.0,
        "fund_utilized_rupees": 83854815.0,
        "source_rupees_released": 137056616.0,
        "source_rupees_utilized": 83854815.0,
        "remarks": "",
    }]
    rows = financial_records_to_bulk_rows(records, amounts_as_rupees=True)
    assert rows[1][3] == 137056616.0
    assert rows[1][4] == 83854815.0
