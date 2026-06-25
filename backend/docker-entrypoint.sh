#!/bin/sh
set -e
mkdir -p /app/data/caddy
if [ ! -f /app/data/caddy/Caddyfile ]; then
  printf '%s\n' ':80 {' '    respond "HomeLab DNS Manager — starting" 200' '}' > /app/data/caddy/Caddyfile
fi
cd /app/backend
alembic upgrade head
exec python -m app.main
