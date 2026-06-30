#!/bin/sh
# Run inside Easypanel → mongo → ecourtdb → Terminal (as root)
# Verifies credentials and pmis_ecourts database contents.

set -euo pipefail

URI="${MONGO_URI:?Set MONGO_URI, e.g. mongodb://mongo:PASSWORD@localhost:27017/pmis_ecourts?authSource=admin&tls=false}"

echo "Connecting to MongoDB..."
mongosh "$URI" --quiet --eval '
  const dbName = db.getName();
  print("Database: " + dbName);
  const cols = ["users", "high_courts", "components", "physical_entries", "financial_entries", "outcome_entries"];
  cols.forEach(c => {
    try {
      print(c + ": " + db.getCollection(c).countDocuments());
    } catch (e) {
      print(c + ": (missing)");
    }
  });
'

echo "Done. If counts are 0, run restore-mongo-in-container.sh or restart backend with MONGO_URL set."
