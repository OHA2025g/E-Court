#!/usr/bin/env python3
"""Apply native Task Management translations to regional locale files."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "locales"
PACKS = Path(__file__).resolve().parent / "task-packs"


def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def apply_flat(tasks_en, flat):
    out = copy.deepcopy(tasks_en)
    for path, value in flat.items():
        set_path(out, path, value)
    return out


def merge(code, tasks):
    path = ROOT / f"{code}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tasks"] = tasks
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    en_tasks = json.loads((ROOT / "en.json").read_text(encoding="utf-8"))["tasks"]
    for pack in sorted(PACKS.glob("*.flat.json")):
        code = pack.stem.replace(".flat", "")
        flat = json.loads(pack.read_text(encoding="utf-8"))
        merge(code, apply_flat(en_tasks, flat))
        print(f"Applied {code}: {len(flat)} keys")


if __name__ == "__main__":
    main()
