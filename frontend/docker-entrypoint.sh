#!/bin/sh
set -e

# When frontend and API are on different origins, allow API fetch in CSP.
# Set CSP_API_ORIGIN or REACT_APP_BACKEND_URL (same origin, no trailing slash).
CSP_CONNECT_SRC="${CSP_API_ORIGIN:-${REACT_APP_BACKEND_URL:-}}"
export CSP_CONNECT_SRC

# Proxy /api/* for same-origin public page + optional split-domain deploy.
# Docker Compose: internal backend service. Easypanel: external API host from REACT_APP_BACKEND_URL.
if [ -z "${API_PROXY_UPSTREAM:-}" ]; then
  case "${REACT_APP_BACKEND_URL:-}" in
    http://localhost:*|https://localhost:*|"")
      API_PROXY_UPSTREAM="http://backend:8001"
      ;;
    *)
      API_PROXY_UPSTREAM="${REACT_APP_BACKEND_URL}"
      ;;
  esac
fi
export API_PROXY_UPSTREAM

envsubst '${CSP_CONNECT_SRC} ${API_PROXY_UPSTREAM}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
