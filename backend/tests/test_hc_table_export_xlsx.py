"""Exact-value workbook builder used by High Court Table download."""
import io
import sys
from pathlib import Path

import openpyxl

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from export_routes import build_multi_sheet_xlsx  # noqa: E402


def test_hc_table_workbook_keeps_exact_numeric_values():
    data = build_multi_sheet_xlsx([
        {
            "name": "HC_Summary",
            "columns": ["high_court", "fin_released", "fin_utilized", "fin_percent"],
            "headers": ["High Court", "Funds Released(Cr)", "Funds Utilized(Cr)", "Util %"],
            "rows": [{
                "high_court": "Manipur",
                "fin_released": 11.9,
                "fin_utilized": 14.13,
                "fin_percent": 118.73949579831933,
            }],
        },
        {
            "name": "Financial_Exact",
            "columns": ["high_court", "component", "fund_released", "fund_utilized"],
            "headers": ["High Court", "Component", "Released (Cr)", "Utilised (Cr)"],
            "rows": [{
                "high_court": "Manipur",
                "component": "Digitisation",
                "fund_released": 5.123456789,
                "fund_utilized": 7.987654321,
            }],
        },
        {
            "name": "Physical_Exact",
            "columns": ["high_court", "indicator", "target", "achieved"],
            "headers": ["High Court", "Indicator", "Target", "Achieved"],
            "rows": [{
                "high_court": "Manipur",
                "indicator": "eSewa Kendras",
                "target": 12,
                "achieved": 9,
            }],
        },
    ])
    assert data[:2] == b"PK"
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert wb.sheetnames == ["HC_Summary", "Financial_Exact", "Physical_Exact"]
    fin = wb["Financial_Exact"]
    assert fin["C2"].value == 5.123456789
    assert fin["D2"].value == 7.987654321
    phys = wb["Physical_Exact"]
    assert phys["C2"].value == 12
    assert phys["D2"].value == 9
