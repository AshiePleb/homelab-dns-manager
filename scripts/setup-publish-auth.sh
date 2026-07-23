#!/usr/bin/env bash
# Configure Docker Hub auth for GitHub Actions + local docker push.
#
# Creates a Hub Access Token at:
#   https://hub.docker.com/settings/security
# then run:
#   ./scripts/setup-publish-auth.sh
#
# Env (optional, skips prompts):
#   DOCKERHUB_USERNAME  (default: ashiepleb)
#   DOCKERHUB_TOKEN     (Hub Access Token — not your account password)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USERNAME="${DOCKERHUB_USERNAME:-ashiepleb}"
REPO_SLUG="$(git -C "$ROOT" remote get-url origin | sed -E 's#.*github.com[:/]##' | sed 's#\.git$##')"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI first: brew install gh && gh auth login" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Not logged in to GitHub CLI. Run: gh auth login" >&2
  exit 1
fi

if [[ -z "${DOCKERHUB_TOKEN:-}" ]]; then
  echo ""
  echo "1. Open https://hub.docker.com/settings/security"
  echo "2. New Access Token — Read, Write, Delete (or Read & Write)"
  echo "3. Paste the token below (input hidden)."
  echo ""
  read -r -s -p "Docker Hub token for ${USERNAME}: " DOCKERHUB_TOKEN
  echo ""
fi

if [[ -z "${DOCKERHUB_TOKEN}" ]]; then
  echo "Empty token — aborting." >&2
  exit 1
fi

echo "→ Setting GitHub Actions secrets on ${REPO_SLUG}..."
gh secret set DOCKERHUB_USERNAME --repo "$REPO_SLUG" --body "$USERNAME"
gh secret set DOCKERHUB_TOKEN --repo "$REPO_SLUG" --body "$DOCKERHUB_TOKEN"

echo "→ Logging Docker Desktop into Docker Hub..."
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop, then re-run this script." >&2
  exit 1
fi
echo "$DOCKERHUB_TOKEN" | docker login -u "$USERNAME" --password-stdin

echo "→ Verifying Hub push access..."
# Tiny no-op: inspect repo via Hub API with the token
HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
  -u "${USERNAME}:${DOCKERHUB_TOKEN}" \
  "https://hub.docker.com/v2/repositories/${USERNAME}/homelab-dns-manager/")
if [[ "$HTTP" != "200" ]]; then
  echo "Hub API returned HTTP ${HTTP} for ${USERNAME}/homelab-dns-manager" >&2
  echo "Check the username/token and that the repo exists." >&2
  exit 1
fi

echo ""
echo "✓ Publish auth configured:"
echo "  - GitHub secrets: DOCKERHUB_USERNAME, DOCKERHUB_TOKEN"
echo "  - Local: docker login as ${USERNAME}"
echo ""
echo "Next: publish the current tag via CI:"
echo "  gh workflow run docker-publish.yml -f tag=v\$(tr -d '[:space:]' < VERSION)"
echo "  # or: ./scripts/release.sh --skip-vps   (for a new version)"
