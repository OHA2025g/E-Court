"""High Court name helpers — dash-insensitive matching.

Master lists and tracker rows historically mixed ASCII hyphen (-) with
Unicode en-dash (–) / em-dash (—) for Gauhati state benches. Filters must
match all variants so dashboard KPIs are not empty for valid entries.
"""
from __future__ import annotations

import re
from itertools import product
from typing import Any

_DASH_RE = re.compile(r"[-–—]")
_DASH_CHARS = ("-", "–", "—")


def high_court_name_variants(name: str | None) -> list[str]:
    """Return all dash-character variants of a High Court name."""
    if not name:
        return []
    text = str(name).strip()
    if not text:
        return []
    parts = _DASH_RE.split(text)
    if len(parts) == 1:
        return [text]
    variants: set[str] = {text}
    gaps = len(parts) - 1
    for dashes in product(_DASH_CHARS, repeat=gaps):
        built = parts[0]
        for dash, part in zip(dashes, parts[1:]):
            built += dash + part
        variants.add(built)
    return sorted(variants)


def high_court_filter_value(name: str | None) -> Any:
    """Mongo filter value for high_court: exact string or `$in` of dash variants."""
    variants = high_court_name_variants(name)
    if not variants:
        return name
    if len(variants) == 1:
        return variants[0]
    return {"$in": variants}


def normalize_high_court_dashes(name: str | None, prefer: str = "–") -> str | None:
    """Rewrite dash characters to a preferred dash (default en-dash)."""
    if name is None:
        return None
    text = str(name).strip()
    if not text:
        return text
    return _DASH_RE.sub(prefer, text)


def high_court_names_equal(a: str | None, b: str | None) -> bool:
    """True when names match ignoring hyphen / en-dash / em-dash differences."""
    if a is None or b is None:
        return a == b
    return normalize_high_court_dashes(a, "-") == normalize_high_court_dashes(b, "-")
