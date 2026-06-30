#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP="$ROOT/database/mongodump/pmis_ecourts"
CONTAINER="${MONGO_CONTAINER:-ecourts-pmisv1-mongo-1}"
DB_NAME="${DB_NAME:-pmis_ecourts}"

if [[ ! -d "$DUMP" ]]; then
  echo "Missing dump at $DUMP"
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Mongo container '$CONTAINER' is not running. Start with: docker compose up -d"
  exit 1
fi

echo "Restoring $DB_NAME into $CONTAINER ..."
docker cp "$DUMP" "$CONTAINER:/tmp/restore"
docker exec "$CONTAINER" mongorestore --drop --db "$DB_NAME" /tmp/restore
docker exec "$CONTAINER" rm -rf /tmp/restore
echo "Done."
