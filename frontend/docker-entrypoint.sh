#!/bin/sh
set -e

# When frontend and API are on different origins, allow API fetch in CSP.
# Set CSP_API_ORIGIN or REACT_APP_BACKEND_URL (same origin, no trailing slash).
CSP_CONNECT_SRC="${CSP_API_ORIGIN:-${REACT_APP_BACKEND_URL:-}}"
export CSP_CONNECT_SRC

envsubst '${CSP_CONNECT_SRC}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
