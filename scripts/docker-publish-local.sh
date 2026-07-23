#!/usr/bin/env bash
# Build and push to Docker Hub locally (when GitHub Actions secrets are not set).
# Requires: docker login -u ashiepleb  (use a Hub access token as password)
#
# Usage: ./scripts/docker-publish-local.sh [v1.1.0]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${DOCKER_IMAGE:-ashiepleb/homelab-dns-manager}"
TAG="${1:-v$(tr -d '[:space:]' < "${ROOT}/VERSION")}"
TAG="${TAG#v}"
TAG="v${TAG}"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop first." >&2
  exit 1
fi

# Verify Docker Hub credentials are actually present (stub auths entries are common)
HAS_CREDS=0
if command -v docker-credential-desktop >/dev/null 2>&1; then
  if printf 'https://index.docker.io/v1/\n' | docker-credential-desktop get 2>/dev/null | grep -q '"Username"'; then
    HAS_CREDS=1
  fi
fi
if [[ "$HAS_CREDS" -eq 0 ]]; then
  echo "Not logged in to Docker Hub (no credentials in Docker Desktop)." >&2
  echo "Run: ./scripts/setup-publish-auth.sh" >&2
  exit 1
fi

echo "→ Building ${IMAGE}:${TAG} and :latest (linux/amd64)"
docker buildx build --platform linux/amd64 \
  --build-arg "APP_VERSION=${TAG}" \
  --build-arg "BUILD_TIME=${BUILD_TIME}" \
  --build-arg "DOCKER_IMAGE_REPO=${IMAGE}" \
  -t "${IMAGE}:${TAG}" \
  -t "${IMAGE}:latest" \
  --push \
  "${ROOT}"

echo "✓ Pushed ${IMAGE}:${TAG} and ${IMAGE}:latest"
