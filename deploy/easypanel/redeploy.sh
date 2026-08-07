#!/usr/bin/env bash
# Thin wrapper around redeploy.py — keeps the old CLI working.
#
# Usage:
#   export EASYPANEL_EMAIL='...'
#   export EASYPANEL_PASSWORD='...'
#   ./deploy/easypanel/redeploy.sh              # both (waits for SHA)
#   ./deploy/easypanel/redeploy.sh frontend
#   ./deploy/easypanel/redeploy.sh backend
#   ./deploy/easypanel/redeploy.sh status
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/deploy/easypanel/redeploy.py" "${1:-both}" "${@:2}"
