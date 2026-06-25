#!/usr/bin/env bash
# Build and push the HomeLab DNS Manager image to Docker Hub (or any registry).
#
# Prerequisites:
#   - Docker Desktop on Mac (or Docker with buildx)
#   - docker login   (Docker Hub: docker login -u YOUR_USER)
#
# Usage:
#   ./scripts/publish-image.sh              # push ashiepleb/homelab-dns-manager:latest
#   ./scripts/publish-image.sh v1.0.0       # push :v1.0.0 and :latest
#   DOCKER_IMAGE=myregistry/homelab-dns ./scripts/publish-image.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE="${DOCKER_IMAGE:-ashiepleb/homelab-dns-manager}"
TAG="${1:-latest}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and try again." >&2
  exit 1
fi

echo "Building and pushing ${IMAGE}:${TAG} (linux/amd64, linux/arm64)..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t "${IMAGE}:${TAG}" \
  --push \
  .

if [[ "${TAG}" != "latest" ]]; then
  echo "Also tagging ${IMAGE}:latest..."
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t "${IMAGE}:latest" \
    --push \
    .
fi

echo ""
echo "Done. Users can deploy with:"
echo "  HOMELAB_DNS_IMAGE=${IMAGE}:${TAG} docker compose pull && docker compose up -d"
echo ""
echo "Default (no env override): ${IMAGE}:latest"
