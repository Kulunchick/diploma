#!/bin/sh
set -eu

# Generate runtime config from ConfigMap env vars.
# This file is served at /config.js with Cache-Control: no-store.
: "${APP_API_BASE_URL:=/api}"
: "${APP_USE_TEMPORAL_API:=true}"

cat > /usr/share/nginx/html/config.js << EOF
window.__APP_CONFIG__ = {
  "apiBaseUrl": "${APP_API_BASE_URL}",
  "useTemporalApi": ${APP_USE_TEMPORAL_API}
};
EOF

exec "$@"
