#!/usr/bin/env python3
"""One-shot: convert Cloud fin ₹→crore and mirror Cloud tracker rows onto baseline."""
from __future__ import annotations

import argparse
import os
import sys

from pymongo import MongoClient

CLOUD = "Cloud Computing & Storage"
BASELINE = "2026-05"
RUPEE_FLOOR = 1000.0


def fix_db(uri: str, db_name: str = "pmis_ecourts") -> None:
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[db_name]

    fin_fixed = 0
    for row in db.financial_entries.find({"component": CLOUD}):
        updates = {}
        for field in ("fund_released", "fund_utilized", "fund_target", "fund_allocated"):
            val = row.get(field)
            if isinstance(val, (int, float)) and abs(val) >= RUPEE_FLOOR:
                rupees = float(val)
                updates[field] = rupees / 1e7
                updates[f"{field}_rupees"] = rupees
        if updates:
            released = updates.get("fund_released", row.get("fund_released"))
            utilized = updates.get("fund_utilized", row.get("fund_utilized"))
            if released not in (None, 0) and utilized is not None:
                updates["utilisation_percent"] = round(100.0 * float(utilized) / float(released), 2)
                updates["variance"] = float(released) - float(utilized)
            db.financial_entries.update_one({"_id": row["_id"]}, {"$set": updates})
            fin_fixed += 1

    phys_mirrored = 0
    for row in db.physical_entries.find({"component": CLOUD, "reporting_period": "2026-07"}):
        q = {
            "high_court": row.get("high_court"),
            "component": CLOUD,
            "indicator": row.get("indicator"),
            "reporting_period": BASELINE,
            "district": row.get("district"),
            "storage_type": row.get("storage_type") or "Block Storage",
        }
        payload = {k: v for k, v in row.items() if k != "_id"}
        payload.update(q)
        existing = db.physical_entries.find_one(q)
        if existing:
            db.physical_entries.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "target": payload.get("target"),
                    "achieved": payload.get("achieved"),
                    "percent": payload.get("percent"),
                    "rag": payload.get("rag"),
                    "remarks": payload.get("remarks"),
                    "uom": payload.get("uom"),
                }},
            )
        else:
            db.physical_entries.insert_one(payload)
        phys_mirrored += 1

    fin_mirrored = 0
    for row in db.financial_entries.find({"component": CLOUD, "reporting_period": "2026-07"}):
        q = {
            "high_court": row.get("high_court"),
            "component": CLOUD,
            "reporting_period": BASELINE,
            "district": row.get("district"),
        }
        payload = {k: v for k, v in row.items() if k != "_id"}
        payload.update(q)
        existing = db.financial_entries.find_one(q)
        if existing:
            db.financial_entries.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "fund_target": payload.get("fund_target"),
                    "fund_allocated": payload.get("fund_allocated"),
                    "fund_released": payload.get("fund_released"),
                    "fund_utilized": payload.get("fund_utilized"),
                    "utilisation_percent": payload.get("utilisation_percent"),
                    "variance": payload.get("variance"),
                    "rag": payload.get("rag"),
                    "remarks": payload.get("remarks"),
                    "description": payload.get("description"),
                }},
            )
        else:
            db.financial_entries.insert_one(payload)
        fin_mirrored += 1

    phys = list(db.physical_entries.aggregate([
        {"$match": {"component": CLOUD, "reporting_period": BASELINE}},
        {"$group": {"_id": None, "n": {"$sum": 1}, "a": {"$sum": {"$ifNull": ["$achieved", 0]}}}},
    ]))
    fin = list(db.financial_entries.aggregate([
        {"$match": {"component": CLOUD, "reporting_period": BASELINE}},
        {"$group": {
            "_id": None,
            "n": {"$sum": 1},
            "r": {"$sum": {"$ifNull": ["$fund_released", 0]}},
            "u": {"$sum": {"$ifNull": ["$fund_utilized", 0]}},
        }},
    ]))
    print(f"fin_fixed={fin_fixed} phys_mirrored={phys_mirrored} fin_mirrored={fin_mirrored}")
    print("baseline physical:", phys)
    print("baseline financial:", fin)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=os.environ.get("MONGO_URL"))
    parser.add_argument("--db", default="pmis_ecourts")
    args = parser.parse_args()
    if not args.uri:
        print("Set --uri or MONGO_URL", file=sys.stderr)
        return 1
    fix_db(args.uri, args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
