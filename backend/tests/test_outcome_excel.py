"""Tests for Phase-4 outcome Excel parsing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from outcome_excel import parse_outcome_excel_rows


def test_parse_outcome_excel_uses_sub_component_as_subject():
    rows = [
        (
            "High Court", "Components", "Sub-Component", "KPID", "KPI",
            "Description", "Periodicity", "Granularity",
            "OUTCOME (Period Sep 2023 – May 2026)",
        ),
        ("Allahabad", "eFiling", "eFiling", 1.01, "KPI A", "Desc", "Monthly", "District", 43),
        ("Allahabad", None, None, 1.02, "KPI B", "Desc", "Monthly", "District", 39),
        (
            "Allahabad", "Paperless Courts (miscellaneous)", "Automated eMail", 2.1,
            "Email KPI", "Desc", "Monthly", "State", 68,
        ),
        ("Allahabad", None, "SMS", 3.1, "SMS KPI", "Desc", "Monthly", "State", 100),
    ]
    parsed = parse_outcome_excel_rows(rows)
    assert len(parsed) == 4
    assert parsed[0]["subject"] == "eFiling"
    assert parsed[0]["component"] == "eFiling"
    assert parsed[0]["sub_component"] == "eFiling"
    assert parsed[0]["kpi_id"] == "1.01"
    assert parsed[2]["subject"] == "Automated eMail"
    assert parsed[2]["component"] == "Paperless Courts"
    assert parsed[2]["sub_component"] == "Automated eMail"
    assert parsed[2]["kpi_id"] == "2.1"
    assert parsed[2]["kpi"] == "Email KPI"
    assert parsed[3]["subject"] == "SMS"
    assert parsed[3]["kpi_id"] == "3.1"
    assert parsed[3]["kpi"] == "SMS KPI"
