# HomeLab DNS Manager

[![Docker Hub](https://img.shields.io/docker/v/ashiepleb/homelab-dns-manager?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ashiepleb/homelab-dns-manager)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Self-hosted dashboard for **Cloudflare DDNS**, homelab subdomain management, and a built-in **Caddy** reverse proxy with **Let's Encrypt** HTTPS.

| | |
|---|---|
| **GitHub** | [AshiePleb/homelab-dns-manager](https://github.com/AshiePleb/homelab-dns-manager) |
| **Docker image** | [`ashiepleb/homelab-dns-manager`](https://hub.docker.com/r/ashiepleb/homelab-dns-manager) |
| **Install files** | [`install/docker-compose.yml`](install/docker-compose.yml) + [`.env.example`](install/.env.example) |

Add a service in one step — subdomain `home` + target `10.10.10.1:8080` → `home.example.com` with DDNS and HTTPS.

---

## Quick install

You only need **two files** on your server: `docker-compose.yml` and `.env`.

```bash
mkdir -p /opt/homelab-dns-manager && cd /opt/homelab-dns-manager

curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/.env.example

cp .env.example .env
chmod 600 .env
```

**Generate secrets** and paste each value into `.env` (replace the `CHANGE_ME` placeholders):

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
echo "ENCRYPTION_KEY=$(openssl rand -base64 32)"
```

Edit `.env` — at minimum set `CLOUDFLARE_API_TOKEN` and `ACME_EMAIL`:

```bash
nano .env
```

Start the stack:

```bash
docker compose pull
docker compose up -d
```

Open `http://YOUR_SERVER_IP:8000` — default login `admin` / `password` (you will be prompted to change this on first login).

| Item | Default |
|------|---------|
| Docker image | `ashiepleb/homelab-dns-manager:latest` |
| Dashboard port | `8000` (set `PORT` in `.env`) |
| Update app | `docker compose pull && docker compose up -d` |

The UI also checks Docker Hub for updates (**Settings → System → App version**).

---

## What you need first

| Requirement | Notes |
|-------------|-------|
| Linux server with Docker + Compose | `docker compose version` |
| Domain on Cloudflare | e.g. `example.com` |
| Cloudflare API token | **Zone → DNS → Edit** — [create token](https://dash.cloudflare.com/profile/api-tokens) |
| Router port forwards | **80** and **443** → your server IP |

> Use a real **API Token** from Cloudflare (template: **Edit zone DNS**). Global API keys will not work.

---

## First-time setup

### 1. Configure `.env`

| Variable | Required? | What to set |
|----------|-----------|-------------|
| `SECRET_KEY` | **Yes** | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | **Yes** | `openssl rand -base64 32` |
| `JWT_SECRET_KEY` | **Yes** | `openssl rand -hex 32` |
| `CLOUDFLARE_API_TOKEN` | **Yes** | Cloudflare API token |
| `ACME_EMAIL` | **Yes** | Email for Let's Encrypt |
| `LEGACY_DDNS_DOMAINS` | No | Leave **empty** unless migrating old DDNS subdomains |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | No | Default `admin` / `password` |
| `PORT` | No | Dashboard port (default `8000`) |
| `DDNS_INTERVAL_MINUTES` | No | IP check interval (default `5`) |
| `DDNS_PROXIED_DEFAULT` | No | `false` recommended (grey cloud + Caddy LE) |

Example `.env`:

```env
SECRET_KEY=...
ENCRYPTION_KEY=...
JWT_SECRET_KEY=...
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token_here
ACME_EMAIL=you@example.com
LEGACY_DDNS_DOMAINS=
PORT=8000
DDNS_INTERVAL_MINUTES=5
DDNS_PROXIED_DEFAULT=false
```

The token in `.env` is imported into the encrypted app database on first boot. **Settings → Cloudflare** is for rotating the token later.

### 2. Router port forwarding

Forward to your **server IP** (not individual app ports):

| External | Forward to | Why |
|----------|------------|-----|
| **80** | server:80 | HTTP redirects + certificate validation |
| **443** | server:443 | HTTPS for your subdomains |

### 3. First login & dashboard

1. Open `http://YOUR_SERVER_IP:8000` and complete account setup (name, email, new password).
2. **Settings → General** → set default domain template → **Save**.
3. **Domains** → **Sync** (pulls zones from Cloudflare).
4. **Settings → Cloudflare** → **Test Connection**.

### 4. Add a homelab service

1. **Add Service** → base domain, subdomain (e.g. `home`), internal target (e.g. `10.10.10.1:8080`).
2. **Test port** → **Create service**.

This creates a Cloudflare A record (DDNS managed), Caddy reverse proxy with HTTPS, and a row on **DNS Records**.

---

## Features

| Feature | Description |
|---------|-------------|
| **Add Service** | Subdomain + `IP:port` → DNS, DDNS, and Caddy HTTPS in one step |
| **DNS Records** | Managed records with public IP, internal target, port status, SSL health, bulk actions |
| **Caddy Proxy** | Proxy hosts, container status, Caddyfile view, manual reload |
| **DDNS** | Auto-updates subdomain A records when your public IP changes |
| **Health history** | Service health snapshots on the dashboard (DNS, port, HTTPS, SSL expiry) |
| **Activity logs** | Full audit trail |
| **Notifications** | Discord webhooks and SMTP — IP changes, provisioning, CF failures, SSL expiry |
| **Appearance** | Per-user themes (14 options), font size, reduce motion, color-blind mode |
| **2FA** | TOTP two-factor authentication (Settings → Profile) |
| **Backup & restore** | Export/import database, Caddy config, and certificates (admin) |
| **Version check** | Compares running image vs Docker Hub `latest` |
| **Roles** | Admin, Operator, Viewer |
| **Apex protection** | Never auto-updates `example.com` / `www.example.com` |

---

## Architecture

```
Internet
   │
   ├─► home.example.com (DNS A → your public IP, DDNS managed)
   │
Router :80 / :443  ──►  your-server (Caddy)
                           │
                           └─► 10.10.10.1:8080 (Home, etc.)

Dashboard :8000  ──►  homelab-dns-manager (LAN only recommended)
```

| Container | Purpose | Ports |
|-----------|---------|-------|
| `homelab-dns-manager` | Dashboard + API + DDNS scheduler | `8000` |
| `homelab-caddy` | Reverse proxy + Let's Encrypt | `80`, `443` (host network) |

Persistent data lives in the Docker volume `homelab_data` (SQLite DB, Caddyfile, certificates).

---

## Dashboard overview

| Tab | Purpose |
|-----|---------|
| **Dashboard** | Public IP, DDNS status, health history, recent activity |
| **Add Service** | Provision subdomain + target |
| **Domains** | Sync Cloudflare zones |
| **DNS Records** | All managed records; bulk enable/disable DDNS, force update, delete |
| **Caddy Proxy** | Reverse proxy status, hosts, Caddyfile, reload |
| **Activity Logs** | Audit trail |
| **Settings** | Profile, Appearance, General, Cloudflare, Notifications, Users, System |

### Settings tabs

- **Profile** — username, display name, email, password, two-factor authentication
- **Appearance** — theme and accessibility options
- **System** (admin) — app version / updates, backup and restore
- **General** — timezone, DDNS interval, default domain
- **Cloudflare** — test connection, rotate API token
- **Notifications** — Discord webhook, SMTP, alert toggles
- **Users** (admin) — manage users and roles

---

## Protect your main site

If your main website (`example.com`) is hosted **elsewhere**:

- Leave `LEGACY_DDNS_DOMAINS=` **empty**
- **Never** add the apex via Add Service
- The app **never** auto-updates `example.com` or `www.example.com`

Only subdomains you add (e.g. `home.example.com`) are managed.

---

## Updating

```bash
cd /opt/homelab-dns-manager
docker compose pull
docker compose up -d
```

Data persists in `homelab_data`. The dashboard header shows an **Update** badge when a newer image is on Docker Hub.

After upgrades, merge new keys from `.env.example` into your `.env`:

```bash
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/.env.example
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/merge_env.py
python3 merge_env.py
docker compose up -d
```

---

## Day-to-day commands

```bash
docker compose up -d              # start
docker compose down               # stop
docker compose logs -f homelab-dns
docker compose logs -f caddy
curl http://localhost:8000/api/health
```

---

## Troubleshooting

**Container won't start** — `docker compose logs homelab-dns`. Check `.env` exists and secrets are set.

**Cloudflare test fails** — token must be a Cloudflare API Token with DNS edit permission. Set in `.env` or **Settings → Cloudflare**.

**Subdomain works on LAN but not outside** — forward **80** and **443** on your router; DNS should be grey cloud (DNS only).

**HTTPS stuck** — `docker compose restart caddy` then check `docker compose logs caddy --tail 50`.

**DDNS not updating** — only records with the DDNS badge update; use the lightning icon to force-update.

**Can't log in** — first deploy uses `admin` / `password`. Nuclear reset (deletes all data): `docker compose down -v && docker compose up -d`.

---

## Development

Clone the repo and build locally:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

**Backend:**

```bash
cd backend && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
alembic upgrade head
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend && npm install && npm run dev
```

Dev UI: `http://localhost:5173` (proxies API to port 8000).

---

## Security

- `chmod 600 .env` — never commit secrets
- Keep the dashboard on **LAN** or VPN — only expose **80/443** for public services
- Argon2id passwords, server-side sessions, idle timeout, login rate limiting
- Cloudflare token, Discord webhook, and SMTP password encrypted at rest (Fernet)
- Optional TOTP 2FA per user

---

## License

MIT
