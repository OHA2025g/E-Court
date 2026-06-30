"""Export header localization tests."""
from export_i18n import financial_headers, physical_headers, resolve_export_lang


def test_resolve_export_lang():
    assert resolve_export_lang(None) == "en"
    assert resolve_export_lang("hi-IN,en") == "hi"
    assert resolve_export_lang("ur-PK") == "ur"
    assert resolve_export_lang("fr-FR") == "en"


def test_physical_headers_hindi():
    headers = physical_headers("hi")
    assert headers[0] == "उच्च न्यायालय"
    assert headers[1] == "जिला"


def test_financial_headers_english():
    headers = financial_headers("en")
    assert headers[0] == "High Court"
    assert len(headers) == 12
