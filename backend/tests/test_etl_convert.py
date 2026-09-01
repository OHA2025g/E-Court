"""Unit tests for ETL convert service (no DB)."""
from pathlib import Path

import pytest

from etl_convert_service import convert_tracker, public_convert_payload

REPO = Path(__file__).resolve().parents[2]
PHYS = REPO / "Physicial_Tracker_Data_for_Achieved_till_Sep-2025.xlsx"
FIN_REL = REPO / "Financial_Tracker_Data_for_Released_Fund_2024-2027.xlsx"
FIN_UTIL = REPO / "Financial_Tracker_Data_for_Utilised_Fund_2023-2024.xlsx"


@pytest.mark.skipif(not PHYS.exists(), reason="sample physical excel missing")
def test_convert_physical_wide():
    r = convert_tracker("physical", PHYS.read_bytes())
    pub = public_convert_payload(r)
    assert pub["format_detected"] == "wide_doj_physical"
    assert pub["row_mappings_total"] > 0
    assert pub["column_mappings"]
    assert r["bulk_bytes"].startswith(b"PK")  # xlsx zip
    assert "High Court" in pub["desired_headers"]


@pytest.mark.skipif(not FIN_REL.exists(), reason="sample released excel missing")
def test_convert_financial_released():
    r = convert_tracker("financial", FIN_REL.read_bytes(), mode="released")
    pub = public_convert_payload(r)
    assert "released" in pub["format_detected"]
    assert pub["row_mappings_total"] > 0
    sample = pub["row_mappings"][0]
    assert "High Court" in sample["target"]
    assert sample["target"].get("Fund Released") is not None or sample["status"] == "error"


@pytest.mark.skipif(not FIN_UTIL.exists(), reason="sample utilised excel missing")
def test_convert_financial_utilised():
    r = convert_tracker("financial", FIN_UTIL.read_bytes(), mode="utilised")
    pub = public_convert_payload(r)
    assert "utilised" in pub["format_detected"]
    assert pub["row_mappings_total"] > 0


CONSOL = REPO / "Physical_Financial_Tracker_Consolidated_2_Sheets_SrNo_First.xlsx"


@pytest.mark.skipif(not CONSOL.exists(), reason="consolidated excel missing")
def test_convert_consolidated_physical():
    r = convert_tracker("physical", CONSOL.read_bytes(), sheet="Physical Tracker")
    pub = public_convert_payload(r)
    assert pub["format_detected"] == "consolidated_long_physical"
    assert pub["row_mappings_total"] > 100
    assert r["bulk_bytes"].startswith(b"PK")


@pytest.mark.skipif(not CONSOL.exists(), reason="consolidated excel missing")
def test_convert_consolidated_financial():
    r = convert_tracker("financial", CONSOL.read_bytes(), sheet="Financial Tracker")
    pub = public_convert_payload(r)
    assert pub["format_detected"] == "consolidated_long_financial"
    assert pub["row_mappings_total"] > 100
    sample = next(m for m in pub["row_mappings"] if m.get("status") == "ok")
    assert sample["target"].get("Fund Released") is not None or sample["target"].get("Fund Utilized") is not None
