# Publishing guide (maintainers)

How to publish **HomeLab DNS Manager** so end users only need `docker-compose.yml` + `.env`.

---

## What users need

| File | Purpose |
|------|---------|
| `install/docker-compose.yml` | Pulls pre-built image — no source code |
| `install/.env.example` | Copy to `.env`, fill secrets |

They run:

```bash
mkdir -p ~/homelab-dns-manager && cd ~/homelab-dns-manager
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/.env.example
cp .env.example .env && nano .env
docker compose pull && docker compose up -d
```

Replace `AshiePleb/homelab-dns-manager` in the URLs if your GitHub username differs.

---

## Docker Hub (recommended)

### One-time setup

1. Create account at [hub.docker.com](https://hub.docker.com)
2. Create repository: `homelab-dns-manager` (public)
3. Create access token: Account Settings → Security → New Access Token

### Publish from your Mac

```bash
docker login -u YOUR_DOCKERHUB_USER
chmod +x scripts/publish-image.sh
./scripts/publish-image.sh           # latest
./scripts/publish-image.sh v1.0.0    # versioned + latest
```

Custom registry:

```bash
DOCKER_IMAGE=registry.example.com/you/homelab-dns-manager ./scripts/publish-image.sh v1.0.0
```

Users override in `.env`:

```env
HOMELAB_DNS_IMAGE=ashiepleb/homelab-dns-manager:v1.0.0
```

### GitHub Actions (automatic on tag)

1. Push repo to GitHub
2. Add repository secrets:
   - `DOCKERHUB_USERNAME`
   - `DOCKERHUB_TOKEN`
3. Tag a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Workflow `.github/workflows/docker-publish.yml` builds multi-arch (`amd64` + `arm64`) and pushes to Docker Hub.

Manual run: GitHub → Actions → **Publish Docker image** → Run workflow.

---

## GitHub

```bash
cd "/path/to/HomeLab DNS Manager"
git init   # if not already a repo
git add .
git commit -m "Initial release"
git remote add origin git@github.com:AshiePleb/homelab-dns-manager.git
git push -u origin main
```

After the first image is on Docker Hub, users can install without cloning the full repo (only `install/` files).

---

## Gitea (local mirror)

### Option A — mirror GitHub

In Gitea: **New Migration** → **GitHub** → source URL `https://github.com/AshiePleb/homelab-dns-manager`.

### Option B — push directly to Gitea

```bash
git remote add gitea https://git.ashiepleb.com/you/homelab-dns-manager.git
git push -u gitea main
git push gitea v1.0.0
```

### Gitea Container Registry (optional)

Instead of Docker Hub, push to Gitea:

```bash
docker login git.ashiepleb.com
DOCKER_IMAGE=git.ashiepleb.com/you/homelab-dns-manager ./scripts/publish-image.sh latest
```

Users set in `.env`:

```env
HOMELAB_DNS_IMAGE=git.ashiepleb.com/you/homelab-dns-manager:latest
```

---

## Develop from source (not for end users)

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

---

## Updating your production server

After publishing a new image:

```bash
cd /opt/homelab-dns-manager
docker compose pull
docker compose up -d
```

No rebuild, no zip upload — only pull the new image.

---

## Image name reference

| Variable | Default |
|----------|---------|
| `HOMELAB_DNS_IMAGE` | `ashiepleb/homelab-dns-manager:latest` |
| `DOCKER_IMAGE` (publish script) | `ashiepleb/homelab-dns-manager` |

Change `ashiepleb` to your Docker Hub username before the first publish.
