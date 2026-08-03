#!/usr/bin/env bash
# Turn OFF GitHub auto-deploy for eCourts frontend + backend on Easypanel.
# After this, pushes to main will NOT rebuild production until you run redeploy.sh.
#
# Usage:
#   export EASYPANEL_EMAIL='...'
#   export EASYPANEL_PASSWORD='...'
#   ./deploy/easypanel/disconnect-autodeploy.sh
#
set -euo pipefail

PANEL_URL="${EASYPANEL_URL:-http://31.97.207.166:3000}"
EMAIL="${EASYPANEL_EMAIL:?Set EASYPANEL_EMAIL}"
PASSWORD="${EASYPANEL_PASSWORD:?Set EASYPANEL_PASSWORD}"
PROJECT="${EASYPANEL_PROJECT:-ecourt}"

export PANEL_URL EMAIL PASSWORD PROJECT

TOKEN="$(python3 - <<'PY'
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
)"

for svc in frontend backend; do
  echo "Disabling auto-deploy on $svc…"
  PANEL_TOKEN="$TOKEN" SERVICE="$svc" python3 - <<'PY'
import json, os, urllib.request
payload = {"json": {"projectName": os.environ["PROJECT"], "serviceName": os.environ["SERVICE"]}}
req = urllib.request.Request(
    os.environ["PANEL_URL"] + "/api/rpc/services/app/disableGithubDeploy",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["PANEL_TOKEN"],
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    resp.read()
print("  ok:", os.environ["SERVICE"])
PY
done

echo
echo "Verifying…"
PANEL_TOKEN="$TOKEN" python3 - <<'PY'
import json, os, urllib.request
req = urllib.request.Request(
    os.environ["PANEL_URL"] + "/api/rpc/projects/listProjectsAndServices",
    data=json.dumps({"json": None}).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["PANEL_TOKEN"],
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.load(resp)
for s in data["json"]["services"]:
    if s.get("projectName") == os.environ["PROJECT"] and s.get("name") in ("frontend", "backend"):
        auto = (s.get("source") or {}).get("autoDeploy")
        print(f"  {s['name']}: autoDeploy={auto}")
PY

echo
echo "Done. Local changes / git pushes will not update production."
echo "When ready to ship: ./deploy/easypanel/redeploy.sh both"
