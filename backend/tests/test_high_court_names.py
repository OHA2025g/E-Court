"""Dash-insensitive High Court name matching."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from high_court_names import (  # noqa: E402
    high_court_filter_value,
    high_court_name_variants,
    high_court_names_equal,
    normalize_high_court_dashes,
)


def test_gauhati_variants_include_ascii_and_en_dash():
    variants = high_court_name_variants("Gauhati - Assam")
    assert "Gauhati - Assam" in variants
    assert "Gauhati – Assam" in variants
    assert "Gauhati — Assam" in variants


def test_filter_value_uses_in_for_dashed_names():
    value = high_court_filter_value("Gauhati - Assam")
    assert isinstance(value, dict)
    assert "$in" in value
    assert "Gauhati – Assam" in value["$in"]
    assert "Gauhati - Assam" in value["$in"]


def test_plain_name_stays_exact():
    assert high_court_filter_value("Allahabad") == "Allahabad"
    assert high_court_name_variants("Allahabad") == ["Allahabad"]


def test_names_equal_ignores_dash_type():
    assert high_court_names_equal("Gauhati - Assam", "Gauhati – Assam")
    assert high_court_names_equal("Gauhati – Mizoram", "Gauhati - Mizoram")
    assert not high_court_names_equal("Gauhati - Assam", "Gauhati - Mizoram")


def test_normalize_prefers_en_dash():
    assert normalize_high_court_dashes("Gauhati - Assam") == "Gauhati – Assam"
