#!/usr/bin/env bash
# Create the GitHub repo and push (run once after `gh auth login`).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DESC="Self-hosted Cloudflare DDNS + homelab dashboard with Caddy reverse proxy and Let's Encrypt HTTPS."
REPO_NAME="homelab-dns-manager"

if ! gh auth status >/dev/null 2>&1; then
  echo "Not logged in to GitHub. Run:"
  echo "  gh auth login"
  exit 1
fi

USER="$(gh api user -q .login)"
FULL="${USER}/${REPO_NAME}"

if git remote get-url origin >/dev/null 2>&1; then
  echo "Remote origin already set — pushing..."
  git push -u origin main
else
  echo "Creating https://github.com/${FULL} ..."
  gh repo create "$REPO_NAME" \
    --public \
    --description "$DESC" \
    --source=. \
    --remote=origin \
    --push
fi

gh repo edit "$FULL" \
  --description "$DESC" \
  --add-topic docker,homelab,cloudflare,ddns,caddy,reverse-proxy,self-hosted,letsencrypt,fastapi \
  --homepage "https://hub.docker.com/r/ashiepleb/homelab-dns-manager"

echo ""
echo "Repository: https://github.com/${FULL}"
echo ""
echo "Verify install URLs:"
echo "  curl -fsSL https://raw.githubusercontent.com/${FULL}/main/install/docker-compose.yml | head -5"
echo ""
echo "Optional — link Docker Hub to GitHub (Hub → Settings → GitHub):"
echo "  https://hub.docker.com/r/ashiepleb/homelab-dns-manager/settings"
