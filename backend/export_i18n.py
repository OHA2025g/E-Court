"""Localized column headers for Excel/PDF exports (Accept-Language)."""

SUPPORTED = frozenset({"en", "hi", "ur", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"})

_COMMON = {
    "high_court": {
        "en": "High Court", "hi": "उच्च न्यायालय", "ur": "ہائیکورٹ", "bn": "হাই কোর্ট",
        "ta": "உயர் நீதிமன்றம்", "te": "హైకోర్టు", "mr": "उच्च न्यायालय", "gu": "હાઈકોર્ટ",
        "kn": "ಹೈಕೋರ್ಟ್", "ml": "ഹൈക്കോർട്ട്", "pa": "ਹਾਈ ਕੋਰਟ",
    },
    "district": {
        "en": "District", "hi": "जिला", "ur": "ضلع", "bn": "জেলা", "ta": "மாவட்டம்",
        "te": "జిల్లా", "mr": "जिल्हा", "gu": "જિલ્લો", "kn": "ಜಿಲ್ಲೆ", "ml": "ജില്ല", "pa": "ਜ਼ਿਲ੍ਹਾ",
    },
    "component": {
        "en": "Component", "hi": "घटक", "ur": "جز", "bn": "উপাদান", "ta": "கூறு",
        "te": "అంశం", "mr": "घटक", "gu": "ઘટક", "kn": "ಘಟಕ", "ml": "ഘടകം", "pa": "ਘਟਕ",
    },
    "sub_component": {
        "en": "Sub-Component", "hi": "उप-घटक", "ur": "ذیلی جز", "bn": "উপ-উপাদান", "ta": "துணை-கூறு",
        "te": "ఉప-అంశం", "mr": "उप-घटक", "gu": "ઉપ-ઘટક", "kn": "ಉಪ-ಘಟಕ", "ml": "ഉപ-ഘടകം", "pa": "ਉਪ-ਘਟਕ",
    },
    "period": {
        "en": "Period", "hi": "अवधि", "ur": "مدت", "bn": "সময়কাল", "ta": "காலம்",
        "te": "కాలం", "mr": "कालावधी", "gu": "સમયગાળો", "kn": "ಅವಧಿ", "ml": "കാലയളവ്", "pa": "ਅਵਧੀ",
    },
    "rag": {
        "en": "RAG", "hi": "RAG", "ur": "RAG", "bn": "RAG", "ta": "RAG", "te": "RAG",
        "mr": "RAG", "gu": "RAG", "kn": "RAG", "ml": "RAG", "pa": "RAG",
    },
    "remarks": {
        "en": "Remarks", "hi": "टिप्पणी", "ur": "ریمارکس", "bn": "মন্তব্য", "ta": "குறிப்புகள்",
        "te": "వ్యాఖ్యలు", "mr": "शेरा", "gu": "ટિપ્પણી", "kn": "ಟಿಪ್ಪಣಿಗಳು", "ml": "അഭിപ്രായങ്ങൾ", "pa": "ਟਿੱਪਣੀਆਂ",
    },
}


def resolve_export_lang(accept_language: str | None) -> str:
    if not accept_language:
        return "en"
    primary = accept_language.split(",")[0].strip().lower()
    code = primary.split("-")[0]
    return code if code in SUPPORTED else "en"


def _t(key: str, lang: str) -> str:
    return _COMMON.get(key, {}).get(lang) or _COMMON.get(key, {}).get("en", key)


def physical_headers(lang: str) -> list[str]:
    lang = lang if lang in SUPPORTED else "en"
    if lang == "en":
        return [
            "High Court", "District", "Component", "Sub-Component", "Period", "Target",
            "Achieved", "% Achieved", "RAG", "Remarks",
        ]
    return [
        _t("high_court", lang), _t("district", lang), _t("component", lang),
        _t("sub_component", lang),
        _t("period", lang), "Target", "Achieved", "% Achieved", _t("rag", lang), _t("remarks", lang),
    ]


def financial_headers(lang: str) -> list[str]:
    lang = lang if lang in SUPPORTED else "en"
    if lang == "en":
        return [
            "High Court", "District", "Component", "Period", "Target (Cr)", "Allocated (Cr)",
            "Released (Cr)", "Utilised (Cr)", "Utilisation %", "Variance (Cr)", "RAG", "Remarks",
        ]
    return [
        _t("high_court", lang), _t("district", lang), _t("component", lang), _t("period", lang),
        "Target (Cr)", "Allocated (Cr)", "Released (Cr)", "Utilised (Cr)",
        "Utilisation %", "Variance (Cr)", _t("rag", lang), _t("remarks", lang),
    ]


def outcome_headers(lang: str) -> list[str]:
    lang = lang if lang in SUPPORTED else "en"
    if lang == "en":
        return [
            "High Court", "Component", "Sub-Component", "Granularity", "District", "Subject", "KPI ID", "KPI",
            "Type", "Periodicity", "Baseline", "Value", "Computed %", "Period", "Remarks",
        ]
    return [
        _t("high_court", lang), _t("component", lang), "Sub-Component", "Granularity", _t("district", lang),
        "Subject", "KPI ID", "KPI",
        "Type", "Periodicity", "Baseline", "Value", "Computed %", _t("period", lang), _t("remarks", lang),
    ]


def sla_headers(lang: str) -> list[str]:
    lang = lang if lang in SUPPORTED else "en"
    if lang == "en":
        return ["High Court", "Period", "Status", "Days Remaining", "Delinquent"]
    return [_t("high_court", lang), _t("period", lang), "Status", "Days Remaining", "Delinquent"]
