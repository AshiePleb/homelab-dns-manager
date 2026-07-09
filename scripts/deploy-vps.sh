#!/usr/bin/env bash
# Pull and restart HomeLab DNS Manager on the VPS.
# Usage: ./scripts/deploy-vps.sh
# Env: VPS_HOST, VPS_USER, VPS_PATH, VPS_PASS (optional, uses sshpass)

set -euo pipefail

VPS_HOST="${VPS_HOST:-10.10.10.3}"
VPS_USER="${VPS_USER:-root}"
VPS_PATH="${VPS_PATH:-/opt/homelab-dns-manager}"

REMOTE_CMD="cd ${VPS_PATH} && docker compose pull && docker compose up -d && sleep 12 && docker inspect --format '{{.State.Health.Status}}' homelab-dns-manager"

echo "→ Deploying to ${VPS_USER}@${VPS_HOST}:${VPS_PATH}"

if [[ -n "${VPS_PASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
  sshpass -p "${VPS_PASS}" ssh -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_HOST}" "${REMOTE_CMD}"
else
  ssh -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_HOST}" "${REMOTE_CMD}"
fi

echo "✓ VPS deploy complete"
