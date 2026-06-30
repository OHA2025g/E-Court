#!/bin/sh
# Run inside Easypanel → mongo → ecourtdb → Terminal
# Restores full pmis_ecourts dump from GitHub (requires curl + mongorestore).

set -euo pipefail

URI="${MONGO_URI:?Set MONGO_URI, e.g. mongodb://mongo:PASSWORD@localhost:27017/?authSource=admin&tls=false}"
REPO="${GITHUB_REPO:-https://github.com/OHA2025g/E-Court/archive/refs/heads/main.tar.gz}"
WORKDIR="/tmp/ecourt-restore"

echo "Installing mongodb-database-tools if needed..."
if ! command -v mongorestore >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq curl ca-certificates mongodb-database-tools
fi

echo "Downloading database dump from GitHub..."
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
curl -fsSL "$REPO" | tar xz -C "$WORKDIR" --strip-components=1

DUMP="$WORKDIR/database/mongodump/pmis_ecourts"
if [ ! -d "$DUMP" ]; then
  echo "Dump not found at $DUMP"
  exit 1
fi

echo "Restoring into pmis_ecourts (this replaces existing data)..."
mongorestore --drop --uri="$URI" --db pmis_ecourts "$DUMP"

echo "Restore complete. Restart the backend service on Easypanel."
