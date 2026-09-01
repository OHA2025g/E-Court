#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP="$ROOT/database/mongodump/pmis_ecourts"
DB_NAME="${DB_NAME:-pmis_ecourts}"

if [[ ! -d "$DUMP" ]]; then
  echo "Missing dump at $DUMP"
  exit 1
fi

detect_container() {
  if [[ -n "${MONGO_CONTAINER:-}" ]]; then
    echo "$MONGO_CONTAINER"
    return
  fi
  local names
  names="$(docker ps --format '{{.Names}}')"
  for candidate in \
    ecourts-pmis-demo-data-v1-mongo-1 \
    ecourts-pmisv1-mongo-1 \
    ecourts-pmis-mongo-1
  do
    if echo "$names" | grep -qx "$candidate"; then
      echo "$candidate"
      return
    fi
  done
  echo "$names" | grep -E 'mongo' | head -n 1
}

CONTAINER="$(detect_container)"
if [[ -z "$CONTAINER" ]] || ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Mongo container is not running. Start with: docker compose up -d"
  echo "Or set MONGO_CONTAINER to the container name."
  exit 1
fi
echo "Using Mongo container: $CONTAINER"

echo "Restoring $DB_NAME into $CONTAINER ..."
docker cp "$DUMP" "$CONTAINER:/tmp/restore"
docker exec "$CONTAINER" mongorestore --drop --db "$DB_NAME" /tmp/restore
docker exec "$CONTAINER" rm -rf /tmp/restore
echo "Done."
