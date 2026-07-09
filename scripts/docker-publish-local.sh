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

if ! docker pull hello-world >/dev/null 2>&1; then
  :
fi

# Quick auth check — push will fail with a clear message if not logged in
if [[ -f "$HOME/.docker/config.json" ]] && ! grep -q '"index.docker.io"' "$HOME/.docker/config.json" 2>/dev/null; then
  if ! grep -q '"https://index.docker.io/v1/"' "$HOME/.docker/config.json" 2>/dev/null; then
    echo "Not logged in to Docker Hub. Run:" >&2
    echo "  docker login -u ashiepleb" >&2
    echo "Password = access token from https://hub.docker.com/settings/security" >&2
    exit 1
  fi
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
