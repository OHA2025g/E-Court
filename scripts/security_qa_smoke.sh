#!/usr/bin/env bash
# Security smoke checks against a running PMIS stack (Docker or local).
# Usage: ./scripts/security_qa_smoke.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://localhost:5182}"
API="${BASE%/}/api"

pass=0
fail=0

ok() { echo "  OK  $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; fail=$((fail + 1)); }

echo "PMIS security smoke — ${API}"
echo

# Health
code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/health")
[[ "$code" == "200" ]] && ok "GET /health" || bad "GET /health (HTTP ${code})"

# Unauthenticated /auth/me
code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/auth/me")
[[ "$code" == "401" ]] && ok "GET /auth/me unauthenticated → 401" || bad "GET /auth/me expected 401 got ${code}"

# CAPTCHA endpoint
body=$(curl -s "${API}/auth/captcha")
echo "$body" | grep -q '"captcha_id"' && ok "GET /auth/captcha returns captcha_id" || bad "GET /auth/captcha"

# Wrong login (no lockout on first try)
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@pmis.gov.in","password":"wrong-password-here"}')
[[ "$code" == "401" ]] && ok "POST /auth/login bad password → 401" || bad "POST /auth/login bad password (HTTP ${code})"

# Valid viewer login
login=$(curl -s -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@pmis.gov.in","password":"View@PMIS2026"}')
token=$(echo "$login" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)
if [[ -n "$token" ]]; then
  ok "POST /auth/login viewer → access_token"
  code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/auth/sessions" -H "Authorization: Bearer ${token}")
  [[ "$code" == "200" ]] && ok "GET /auth/sessions authenticated" || bad "GET /auth/sessions (HTTP ${code})"

  for ep in dashboard/heatmap dashboard/pareto-red-flags dashboard/trend dashboard/layout dashboard/states-rag; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/${ep}" -H "Authorization: Bearer ${token}")
    [[ "$code" == "200" ]] && ok "GET /${ep}" || bad "GET /${ep} (HTTP ${code})"
  done
  code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/dashboard/rag-delta?reporting_period=2026-07" -H "Authorization: Bearer ${token}")
  [[ "$code" == "200" ]] && ok "GET /dashboard/rag-delta" || bad "GET /dashboard/rag-delta (HTTP ${code})"
else
  bad "POST /auth/login viewer (no token — check demo credentials / DB seed)"
fi

# Public progress (citizen transparency)
code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/public/progress")
[[ "$code" == "200" ]] && ok "GET /public/progress" || bad "GET /public/progress (HTTP ${code})"
body=$(curl -s "${API}/public/progress")
echo "$body" | grep -q '"physical"' && ok "Public progress includes physical KPI" || bad "Public progress payload"
echo "$body" | grep -q '"hc_rag_counts"' && ok "Public progress includes hc_rag_counts" || bad "Public progress missing hc_rag_counts"
echo "$body" | grep -q '"states"' && ok "Public progress includes states map data" || bad "Public progress missing states"
echo "$body" | grep -q '"outcome"' && ok "Public progress includes outcome rollup" || bad "Public progress missing outcome"

admin_login=$(curl -s -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pmis.gov.in","password":"Admin@PMIS2026"}')
if echo "$admin_login" | grep -q '"requires_2fa":true'; then
  ADMIN_TOTP_SECRET="${ADMIN_TOTP_SECRET:-JBSWY3DPEHPK3PXP}"
  totp_code=""
  if python3 -c "import pyotp" 2>/dev/null; then
    totp_code=$(python3 -c "import pyotp; print(pyotp.TOTP('${ADMIN_TOTP_SECRET}').now())" 2>/dev/null || true)
  elif command -v docker >/dev/null 2>&1; then
    totp_code=$(docker compose exec -T backend python -c "import pyotp; print(pyotp.TOTP('${ADMIN_TOTP_SECRET}').now())" 2>/dev/null | tr -d '\r\n' || true)
  fi
  if [[ -n "$totp_code" ]]; then
    admin_login=$(curl -s -X POST "${API}/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"email\":\"admin@pmis.gov.in\",\"password\":\"Admin@PMIS2026\",\"totp_code\":\"${totp_code}\"}")
  fi
fi
admin_token=$(echo "$admin_login" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)
if [[ -n "$admin_token" ]]; then
  me=$(curl -s "${API}/auth/me" -H "Authorization: Bearer ${admin_token}")
  if echo "$me" | grep -q '"requires_2fa_setup":true'; then
    ok "/auth/me Admin flags requires_2fa_setup"
    code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/master/high-courts" -H "Authorization: Bearer ${admin_token}")
    [[ "$code" == "403" ]] && ok "Protected route blocked until 2FA setup" || bad "Expected 403 without 2FA got ${code}"
  else
    echo "  SKIP Admin 2FA gate (2FA already enabled on this Admin account)"
  fi
else
  echo "  SKIP Admin login (2FA challenge failed or credentials changed)"
fi

# Data entry: master PUT + bulk dry-run (viewer blocked, admin when 2FA ready)
if [[ -n "$token" ]]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API}/physical/bulk?reporting_period=2026-07&dry_run=true" \
    -H "Authorization: Bearer ${token}" \
    -F "file=@/dev/null;filename=test.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
  [[ "$code" == "403" ]] && ok "Viewer bulk dry-run blocked (403)" || bad "Viewer bulk dry-run expected 403 got ${code}"
fi

if [[ -n "$admin_token" ]]; then
  me=$(curl -s "${API}/auth/me" -H "Authorization: Bearer ${admin_token}")
  if ! echo "$me" | grep -q '"requires_2fa_setup":true'; then
    code=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "${API}/master/districts?high_court=Allahabad&name=Prayagraj" \
      -H "Authorization: Bearer ${admin_token}" \
      -H "Content-Type: application/json" \
      -d '{"high_court":"Allahabad","name":"Prayagraj","active":true}')
    [[ "$code" == "200" ]] && ok "PUT /master/districts" || bad "PUT /master/districts (HTTP ${code})"
    tmpl=$(curl -s -o /dev/null -w "%{http_code}" "${API}/financial/bulk-template" -H "Authorization: Bearer ${admin_token}")
    [[ "$tmpl" == "200" ]] && ok "GET /financial/bulk-template" || bad "GET /financial/bulk-template (HTTP ${tmpl})"

    BULK_PERIOD=$(date +%Y-%m)
    PREVIEW_XLSX=$(mktemp /tmp/pmis-bulk.XXXXXX.xlsx)
    python3 - "$PREVIEW_XLSX" <<'PY'
import io, sys
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["High Court", "Component", "Indicator", "District", "Target", "Achieved", "Remarks"])
ws.append(["Allahabad", "e-Sewa Kendras", "No of sites prepared (in Absolute Count)", "Prayagraj", 10, 5, "smoke"])
buf = io.BytesIO()
wb.save(buf)
open(sys.argv[1], "wb").write(buf.getvalue())
PY
    preview=$(curl -s -X POST "${API}/physical/bulk?reporting_period=${BULK_PERIOD}&dry_run=true" \
      -H "Authorization: Bearer ${admin_token}" \
      -F "file=@${PREVIEW_XLSX};type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    token=$(echo "$preview" | python3 -c "import sys,json; print(json.load(sys.stdin).get('preview_token',''))" 2>/dev/null || true)
    if [[ -n "$token" ]]; then
      ok "POST /physical/bulk dry_run returns preview_token"
      commit_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        "${API}/physical/bulk?reporting_period=${BULK_PERIOD}&dry_run=false&preview_token=${token}" \
        -H "Authorization: Bearer ${admin_token}")
      [[ "$commit_code" == "200" ]] && ok "POST /physical/bulk commit via preview_token" || bad "preview_token commit (HTTP ${commit_code})"
    else
      bad "POST /physical/bulk dry_run missing preview_token"
    fi
    rm -f "$PREVIEW_XLSX"

    summary=$(curl -s "${API}/dashboard/summary?reporting_period=${BULK_PERIOD}" -H "Authorization: Bearer ${admin_token}")
    echo "$summary" | grep -q '"outcome"' && ok "GET /dashboard/summary includes outcome rollup count" || bad "dashboard/summary missing outcome"
  fi
fi

echo
echo "Result: ${pass} passed, ${fail} failed"
[[ "$fail" -eq 0 ]]
