#!/usr/bin/env bash
# Redeploy eCourts frontend and/or backend on Easypanel via deploy webhooks.
#
# Why not deployService RPC?
#   The panel's /api/rpc/services/app/deployService often hangs or returns an
#   empty reply. The service webhook GET /api/deploy/<token> is reliable.
#
# Usage:
#   export EASYPANEL_EMAIL='...'
#   export EASYPANEL_PASSWORD='...'
#   ./deploy/easypanel/redeploy.sh              # both
#   ./deploy/easypanel/redeploy.sh frontend
#   ./deploy/easypanel/redeploy.sh backend
#
set -euo pipefail

PANEL_URL="${EASYPANEL_URL:-http://31.97.207.166:3000}"
EMAIL="${EASYPANEL_EMAIL:?Set EASYPANEL_EMAIL}"
PASSWORD="${EASYPANEL_PASSWORD:?Set EASYPANEL_PASSWORD}"
PROJECT="${EASYPANEL_PROJECT:-ecourt}"
TARGET="${1:-both}"

export PANEL_URL EMAIL PASSWORD PROJECT

login() {
  python3 - <<'PY'
import json, os, urllib.request
req = urllib.request.Request(
    os.environ["PANEL_URL"] + "/api/rpc/auth/login",
    data=json.dumps({"json": {"email": os.environ["EMAIL"], "password": os.environ["PASSWORD"]}}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    print(json.load(resp)["json"]["token"])
PY
}

deploy_token() {
  local svc="$1" token="$2"
  PANEL_TOKEN="$token" SERVICE="$svc" python3 - <<'PY'
import json, os, urllib.request
payload = {"json": {"projectName": os.environ["PROJECT"], "serviceName": os.environ["SERVICE"]}}
req = urllib.request.Request(
    os.environ["PANEL_URL"] + "/api/rpc/services/app/inspectService",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["PANEL_TOKEN"],
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    raw = resp.read().decode("utf-8", "replace")
    print(json.loads(raw, strict=False)["json"]["token"])
PY
}

ensure_main() {
  local svc="$1" panel_token="$2" path="$3"
  PANEL_TOKEN="$panel_token" SERVICE="$svc" SRC_PATH="$path" python3 - <<'PY'
import json, os, urllib.request

def post(path, payload):
    req = urllib.request.Request(
        os.environ["PANEL_URL"] + path,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ["PANEL_TOKEN"],
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

post("/api/rpc/services/app/updateSourceGithub", {
    "json": {
        "projectName": os.environ["PROJECT"],
        "serviceName": os.environ["SERVICE"],
        "owner": "OHA2025g",
        "repo": "E-Court",
        "ref": "main",
        "path": os.environ["SRC_PATH"],
    }
})
# updateSourceGithub clears autoDeploy — turn it back on
post("/api/rpc/services/app/enableGithubDeploy", {
    "json": {
        "projectName": os.environ["PROJECT"],
        "serviceName": os.environ["SERVICE"],
    }
})
print(f"  source {os.environ['SERVICE']} → main ({os.environ['SRC_PATH']}) + autoDeploy")
PY
}

trigger() {
  local svc="$1" panel_token="$2"
  local dtoken
  dtoken="$(deploy_token "$svc" "$panel_token")"
  echo "→ Deploying $svc …"
  curl -sS -m 30 "$PANEL_URL/api/deploy/$dtoken" || true
  echo
}

echo "Logging into Easypanel…"
PANEL_TOKEN="$(login)"

case "$TARGET" in
  frontend|front|fe)
    ensure_main frontend "$PANEL_TOKEN" "/frontend/"
    trigger frontend "$PANEL_TOKEN"
    ;;
  backend|back|be|api)
    ensure_main backend "$PANEL_TOKEN" "/backend/"
    trigger backend "$PANEL_TOKEN"
    ;;
  both|all)
    ensure_main frontend "$PANEL_TOKEN" "/frontend/"
    ensure_main backend "$PANEL_TOKEN" "/backend/"
    trigger frontend "$PANEL_TOKEN"
    trigger backend "$PANEL_TOKEN"
    ;;
  *)
    echo "Unknown target: $TARGET (use frontend|backend|both)" >&2
    exit 1
    ;;
esac

echo "Done. Builds usually finish in 3–5 minutes."
echo "  Frontend: https://ecourt.demo.agrayianailabs.com"
echo "  Backend:  https://ecourt.demoapi.agrayianailabs.com/api/health"
