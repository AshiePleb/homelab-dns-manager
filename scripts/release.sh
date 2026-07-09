#!/usr/bin/env bash
# Release HomeLab DNS Manager with semver tagging.
#
# Updates VERSION + package.json, commits, tags vX.Y.Z, pushes to GitHub.
# GitHub Actions (.github/workflows/docker-publish.yml) builds and pushes to Docker Hub.
# Does NOT push Docker images directly — use git tags only.
#
# Usage:
#   ./scripts/release.sh              Release current VERSION file
#   ./scripts/release.sh patch          Bump patch, then release
#   ./scripts/release.sh minor          Bump minor, then release
#   ./scripts/release.sh major          Bump major, then release
#   ./scripts/release.sh v1.2.0         Set exact version, then release
#
# Options:
#   --vps / --yes-vps    Deploy to VPS after release (non-interactive)
#   --skip-vps           Do not prompt or deploy VPS
#   --dry-run            Show actions without committing/pushing
#
# Env:
#   VPS_HOST, VPS_USER, VPS_PATH, VPS_PASS  — see scripts/deploy-vps.sh
#
# Semver rules (standard):
#   PATCH — bugfixes
#   MINOR — new features (backward compatible)
#   MAJOR — breaking API / integration changes

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="${ROOT}/VERSION"
PKG_JSON="${ROOT}/frontend/package.json"

DEPLOY_VPS=0
SKIP_VPS=0
DRY_RUN=0
BUMP=""
TARGET_VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vps|--yes-vps)
      DEPLOY_VPS=1
      shift
      ;;
    --skip-vps)
      SKIP_VPS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    patch|minor|major)
      BUMP="$1"
      shift
      ;;
    v[0-9]*|[0-9]*.[0-9]*.[0-9]*)
      TARGET_VERSION="${1#v}"
      shift
      ;;
    -h|--help)
      sed -n '2,28p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

read_version() {
  tr -d '[:space:]' < "$VERSION_FILE"
}

write_version() {
  local ver="$1"
  echo "$ver" > "$VERSION_FILE"
  if command -v node >/dev/null 2>&1; then
    node -e "
      const fs = require('fs');
      const p = '${PKG_JSON}';
      const j = JSON.parse(fs.readFileSync(p, 'utf8'));
      j.version = '${ver}';
      fs.writeFileSync(p, JSON.stringify(j, null, 2) + '\n');
    "
  else
    sed -i.bak "s/\"version\": \"[^\"]*\"/\"version\": \"${ver}\"/" "$PKG_JSON" && rm -f "${PKG_JSON}.bak"
  fi
}

bump_version() {
  local current="$1"
  local kind="$2"
  IFS='.' read -r major minor patch <<< "$current"
  case "$kind" in
    patch) patch=$((patch + 1)) ;;
    minor) minor=$((minor + 1)); patch=0 ;;
    major) major=$((major + 1)); minor=0; patch=0 ;;
    *) echo "Invalid bump: $kind" >&2; exit 1 ;;
  esac
  echo "${major}.${minor}.${patch}"
}

if [[ ! -f "$VERSION_FILE" ]]; then
  echo "Missing VERSION file at $VERSION_FILE" >&2
  exit 1
fi

CURRENT="$(read_version)"
NEW_VERSION="$CURRENT"

if [[ -n "$TARGET_VERSION" ]]; then
  NEW_VERSION="$TARGET_VERSION"
elif [[ -n "$BUMP" ]]; then
  NEW_VERSION="$(bump_version "$CURRENT" "$BUMP")"
fi

TAG="v${NEW_VERSION}"

if [[ "$NEW_VERSION" == "$CURRENT" && -z "$BUMP" && -z "$TARGET_VERSION" ]]; then
  echo "Releasing current version: ${TAG}"
else
  echo "Version: ${CURRENT} → ${NEW_VERSION} (${TAG})"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] Would update VERSION, package.json, commit, tag ${TAG}, push"
  exit 0
fi

if ! git -C "$ROOT" diff --quiet || ! git -C "$ROOT" diff --cached --quiet; then
  echo "Working tree has uncommitted changes. Commit or stash first." >&2
  git -C "$ROOT" status --short
  exit 1
fi

write_version "$NEW_VERSION"

git -C "$ROOT" add VERSION frontend/package.json
if git -C "$ROOT" diff --cached --quiet; then
  echo "Version files already at ${NEW_VERSION}; tagging current commit"
else
  git -C "$ROOT" commit -m "Release ${TAG}."
fi

if git -C "$ROOT" rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag ${TAG} already exists" >&2
  exit 1
fi
git -C "$ROOT" tag -a "$TAG" -m "Release ${TAG}"

echo "→ Pushing main and tag ${TAG} to GitHub..."
git -C "$ROOT" push origin main
git -C "$ROOT" push origin "$TAG"

echo "→ Waiting for GitHub Actions to build Docker image..."
CI_OK=0
if command -v gh >/dev/null 2>&1; then
  sleep 5
  REPO_SLUG="$(git -C "$ROOT" remote get-url origin | sed -E 's#.*github.com[:/](.+)(\.git)?#\1#')"
  RUN_ID="$(gh run list --repo "$REPO_SLUG" --workflow=docker-publish.yml --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)"
  if [[ -n "$RUN_ID" && "$RUN_ID" != "null" ]]; then
    if gh run watch "$RUN_ID" --exit-status 2>/dev/null; then
      CI_OK=1
    else
      echo "⚠ GitHub Actions failed (often missing DOCKERHUB_USERNAME / DOCKERHUB_TOKEN secrets)." >&2
    fi
  else
    echo "  (no workflow run found)"
  fi
else
  echo "  Install 'gh' CLI to auto-wait for CI"
fi

if [[ "$CI_OK" -eq 0 ]]; then
  echo "→ Falling back to local Docker build/push..."
  if "${ROOT}/scripts/docker-publish-local.sh" "$TAG"; then
    CI_OK=1
  else
    echo "" >&2
    echo "Local push failed. Either:" >&2
    echo "  1. docker login -u ashiepleb   (token from hub.docker.com/settings/security)" >&2
    echo "  2. Set GitHub secrets and re-run CI:" >&2
    echo "       gh secret set DOCKERHUB_USERNAME -b ashiepleb" >&2
    echo "       gh secret set DOCKERHUB_TOKEN -b<your-token>" >&2
    echo "       gh run rerun --failed" >&2
    exit 1
  fi
fi

echo "✓ Released ${TAG} — Docker Hub: ashiepleb/homelab-dns-manager:${TAG} + :latest"

if [[ "$SKIP_VPS" -eq 1 ]]; then
  echo "Skipping VPS deploy (--skip-vps)"
  exit 0
fi

if [[ "$DEPLOY_VPS" -eq 0 ]]; then
  read -r -p "Deploy to VPS (${VPS_HOST:-10.10.10.3})? [y/N] " REPLY
  case "$REPLY" in
    y|Y|yes|Yes) DEPLOY_VPS=1 ;;
    *) echo "Skipped VPS deploy"; exit 0 ;;
  esac
fi

"${ROOT}/scripts/deploy-vps.sh"
