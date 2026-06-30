#!/usr/bin/env python3
"""Merge missing Hindi PMIS locale keys into hi.json."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "locales"
GAPS = Path(__file__).resolve().parent / "hi_locale_gaps.flat.json"


def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def main():
    hi_path = ROOT / "hi.json"
    data = json.loads(hi_path.read_text(encoding="utf-8"))
    flat = json.loads(GAPS.read_text(encoding="utf-8"))
    for path, value in flat.items():
        set_path(data, path, value)
    hi_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Applied {len(flat)} Hindi gap translations")


if __name__ == "__main__":
    main()
