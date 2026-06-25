# HomeLab DNS Manager

[![Docker Hub](https://img.shields.io/docker/v/ashiepleb/homelab-dns-manager?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ashiepleb/homelab-dns-manager)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Self-hosted** dashboard for Cloudflare dynamic DNS (DDNS), homelab subdomain management, and a built-in **Caddy** reverse proxy with **Let's Encrypt / ZeroSSL** HTTPS.

| | |
|---|---|
| **Docker image** | [`ashiepleb/homelab-dns-manager`](https://hub.docker.com/r/ashiepleb/homelab-dns-manager) |
| **Quick install** | [`install/docker-compose.yml`](install/docker-compose.yml) + [`.env.example`](install/.env.example) |
| **Docker Hub overview** | [DOCKERHUB.md](DOCKERHUB.md) (copy for Hub listing) |

Add a service in one step — e.g. subdomain `git` + target `10.10.10.3:3000` → `git.example.com` with DDNS and HTTPS.

**Install path used in this guide:** `/opt/homelab-dns-manager`

---

## Quick install (Docker Hub — recommended)

You only need **two files**: `docker-compose.yml` and `.env`. No source code, no build step.

```bash
mkdir -p /opt/homelab-dns-manager && cd /opt/homelab-dns-manager

curl -fsSLO https://raw.githubusercontent.com/ashiepleb/homelab-dns-manager/main/install/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/ashiepleb/homelab-dns-manager/main/install/.env.example

cp .env.example .env
chmod 600 .env
nano .env   # secrets + Cloudflare token + ACME_EMAIL

docker compose pull
docker compose up -d
```

Open `http://YOUR_SERVER_IP:8000` — default login `admin` / `password`.

| Item | Default |
|------|---------|
| Docker image | `ashiepleb/homelab-dns-manager:latest` |
| Override image | Set `HOMELAB_DNS_IMAGE=...` in `.env` (Gitea registry, pinned version, etc.) |
| Update app | `docker compose pull && docker compose up -d` |

See [PUBLISHING.md](PUBLISHING.md) for publishing to Docker Hub, GitHub, and Gitea.

---

## What it does

| Feature | Description |
|---------|-------------|
| **Add Service** | Subdomain + `IP:port` → Cloudflare DNS, DDNS, and Caddy HTTPS in one step |
| **DNS Records** | App-managed records with public IP, internal target, port status, and SSL health |
| **Caddy Proxy** | View proxy hosts, container status, generated Caddyfile, and reload Caddy |
| **DDNS** | Auto-updates managed subdomain A records when your public IP changes |
| **Caddy + Let's Encrypt** | Terminates HTTPS on ports 80/443 and forwards to homelab services |
| **Apex protection** | Never auto-updates `example.com` / `www.example.com` — your main site stays safe |
| **Activity logs** | Full audit trail |
| **Notifications** | Discord webhooks and SMTP — IP changes, new services/records, CF failures, SSL expiry |
| **Settings** | Tabbed: Profile, General, Cloudflare, Notifications, Users (admin) |
| **Roles** | Admin, Operator, Viewer |

**Example:** `home` + `10.10.10.1:8080` → `home.example.com` with DDNS and HTTPS via Caddy.

---

## Architecture

```
Internet
   │
   ├─► home.example.com (DNS A → your public IP, DDNS managed)
   │
Router :80 / :443  ──►  10.10.10.1 (Caddy)
                           │
                           └─► 10.10.10.1:8080 (Home, etc.)

Dashboard :8000  ──►  homelab-dns-manager (LAN only recommended)
```

Two containers:

| Container | Purpose | Ports |
|-----------|---------|-------|
| `homelab-dns-manager` | Dashboard + API + DDNS scheduler | `8000` (configurable) |
| `homelab-caddy` | Reverse proxy + Let's Encrypt | `80`, `443` (host network) |

---

## How deployment works

**End users (production):** download `install/docker-compose.yml` + `.env` → `docker compose pull && docker compose up -d`. The app image is pulled from **Docker Hub**.

**Developers / maintainers:** clone the repo and either publish an image (`scripts/publish-image.sh`) or build locally:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

| On your Mac/PC (maintainer) | On the server (production) |
|-----------------------------|------------------------------|
| `scripts/publish-image.sh` → Docker Hub | `docker compose pull && docker compose up -d` |
| Or zip via `scripts/package.py` for source deploy | Only needs compose + `.env` (no zip required) |
| GitHub Actions on `v*` tags also publishes the image | Docker pulls the pre-built image |

`docker compose up -d` will:

1. Pull the **homelab-dns-manager** image (or build if using `docker-compose.build.yml`)
2. Pull and start **Caddy**
3. Run database migrations on first start
4. Start the dashboard on port `8000`

---

## What you need first

| Requirement | Notes |
|-------------|-------|
| Linux server with Docker + Compose | `docker --version` / `docker compose version` |
| Dynamic public IP (or static) | DDNS keeps subdomains pointed at your IP |
| Domain on Cloudflare | e.g. `example.com` |
| Cloudflare API token | **Zone → DNS → Edit** — [create token](https://dash.cloudflare.com/profile/api-tokens) |
| Router port forwards | **80** and **443** → your server IP (not app ports like 3100) |

> Use a real **API Token** from Cloudflare (template: **Edit zone DNS**). Global API keys and non-CF tokens will not work.

---

## Step-by-step deploy (first time)

### 1. Package on your computer

```bash
cd "/path/to/HomeLab DNS Manager"
python3 scripts/package.py
```

Creates `dist/homelab-dns-manager-YYYYMMDD-HHMMSS.zip`.

Custom output:

```bash
python3 scripts/package.py -o ~/Desktop/homelab-dns-manager.zip
```

**Included:** source, `Dockerfile`, `docker-compose.yml`, `.env.example`  
**Excluded:** `.venv`, `node_modules`, `.env`, `data/`, `frontend/dist/`, `.git`

### 2. Upload to your server

```bash
scp dist/homelab-dns-manager-*.zip user@YOUR_SERVER_IP:/tmp/
```

### 3. Unzip on the server

```bash
sudo mkdir -p /opt/homelab-dns-manager
sudo chown $USER:$USER /opt/homelab-dns-manager
unzip /tmp/homelab-dns-manager-*.zip -d /opt/homelab-dns-manager
cd /opt/homelab-dns-manager
ls docker-compose.yml Dockerfile .env.example backend/ frontend/
```

You should **not** see `node_modules` or `.venv` — that is correct.

### 4. Create `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

### 5. Generate random secrets

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
echo "ENCRYPTION_KEY=$(openssl rand -base64 32)"
```

Paste each line into `.env`, replacing the `CHANGE_ME` placeholders.

### 6. Fill in `.env`

| Variable | Required? | What to set |
|----------|-----------|-------------|
| `SECRET_KEY` | **Yes** | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | **Yes** | `openssl rand -base64 32` |
| `JWT_SECRET_KEY` | **Yes** | `openssl rand -hex 32` |
| `CLOUDFLARE_API_TOKEN` | **Yes** | Cloudflare API token (see below) |
| `ACME_EMAIL` | **Yes** | Your email for Let's Encrypt (e.g. `you@example.com`) |
| `LEGACY_DDNS_DOMAINS` | No | Leave **empty** — see [Protect your main site](#protect-your-main-site) |
| `ADMIN_USERNAME` | No | Default `admin` |
| `ADMIN_PASSWORD` | No | Default `password` (change on first login) |
| `ADMIN_EMAIL` | No | Default `admin@example.com` |
| `ADMIN_NAME` | No | Default `Admin User` |
| `PORT` | No | Dashboard port (default `8000`) |
| `HOMELAB_DNS_IMAGE` | No | Pre-built image (default `ashiepleb/homelab-dns-manager:latest`) |
| `DDNS_INTERVAL_MINUTES` | No | IP check interval (default `5`) |
| `DDNS_PROXIED_DEFAULT` | No | `false` recommended (grey cloud + Caddy LE) |
| `SESSION_EXPIRE_MINUTES` | No | Max session length (default `480` = 8 hours) |
| `SESSION_IDLE_MINUTES` | No | Idle sign-out (default `60` minutes) |

**Example `.env`:**

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

### 7. Cloudflare API token

1. [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens) → **Create Token**
2. Use **Edit zone DNS** template (or custom: `Zone` → `DNS` → `Edit` for your zone)
3. Copy into `CLOUDFLARE_API_TOKEN=` in `.env`

**`.env` vs Settings UI:** the token in `.env` is imported into the encrypted app database on first boot. Settings → Cloudflare is only for **rotating** the token without editing `.env`. Use **Test Connection** to verify — no Save needed if already configured.

### 8. Router port forwarding

Forward these to your **server IP** (e.g. `10.10.10.1`):

| External port | Forward to | Why |
|---------------|------------|-----|
| **80** | server:80 | HTTP redirects + LE certificate validation |
| **443** | server:443 | HTTPS for your subdomains |

**Do not** forward app ports (3100, 5055, etc.) — Caddy reaches those internally.

### 9. Pull and start

```bash
cd /opt/homelab-dns-manager
docker compose pull
docker compose up -d
```

First pull takes **1–3 minutes** (image already built on Docker Hub).

```bash
docker compose ps
docker compose logs -f homelab-dns
```

Wait until `homelab-dns-manager` shows **healthy**. Press `Ctrl+C` to leave logs.

> **Building from source** (no Docker Hub): use  
> `docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build`  
> First build takes **5–15 minutes**.

### 10. First login

```
http://YOUR_SERVER_IP:8000
```

| Field | Default |
|-------|---------|
| Username | `admin` |
| Password | `password` |

Complete the **account setup** screen (name, email, new password) — required before accessing the dashboard.

### 11. Initial dashboard setup

1. **Settings → General** → set **Default domain template** (e.g. `example.com`) → **Save General**
2. **Domains** → **Sync** (pulls zones from Cloudflare)
3. **Settings → Cloudflare** → **Test Connection** (should succeed if token is valid)

---

## Adding a homelab service

1. Go to **Add Service** in the sidebar
2. Fill in:
   - **Base domain** — e.g. `example.com`
   - **Subdomain** — e.g. `home`
   - **Internal target** — e.g. `10.10.10.1:8080`
3. Click **Test port** to verify the target is reachable
4. Click **Create service**

This creates:

- Cloudflare **A record** → your public IP (DDNS managed, grey cloud)
- **Caddy** reverse proxy with **Let's Encrypt** HTTPS
- Entry on **DNS Records** tab (hostname, internal target, IP, port status)

View and manage everything under **DNS Records**. Delete there removes both DNS and the Caddy proxy.

### Caddy Proxy tab

Open **Caddy Proxy** in the sidebar to:

- See if the `homelab-caddy` container is running
- List all proxy hosts with SSL status (Let's Encrypt) and backend port reachability
- View the generated **Caddyfile** (read-only)
- **Sync & reload Caddy** after manual fixes (operators/admins)

Caddy is reloaded automatically when you add or remove services. Use manual reload if HTTPS is stuck after a cert or DNS change.

---

## Dashboard overview

| Sidebar tab | Purpose |
|-------------|---------|
| **Dashboard** | Public IP, DDNS status, recent activity |
| **Add Service** | Provision subdomain + target (DNS + Caddy) |
| **Domains** | Sync Cloudflare zones |
| **DNS Records** | All app-managed records, SSL column, delete services |
| **Caddy Proxy** | Reverse proxy status, hosts, Caddyfile, reload |
| **Activity Logs** | Audit trail |
| **Settings** | Profile, General (timezone dropdown), Cloudflare, Notifications, Users |

### Settings tabs

- **Profile** — username, display name, email, password
- **General** — timezone (UTC, London, New York, etc.), DDNS interval, default domain
- **Cloudflare** — test connection, rotate API token
- **Notifications** — Discord webhook, optional SMTP, alert event toggles
- **Users** (admin) — add/edit users, roles, reset passwords

### Notification events

| Event | Default | When it fires |
|-------|---------|----------------|
| Public IP changed | On | DDNS updates your home IP |
| Cloudflare update failed | On | DNS sync/update fails |
| New service provisioned | On | Add Service completes |
| New DNS record | On | Record created in app |
| Service removed | Off | Caddy proxy deleted |
| DNS record removed | Off | Record deleted |
| SSL certificate expiring | On | Caddy LE cert nearing expiry |

Discord: paste a webhook URL from Server Settings → Integrations → Webhooks. The app POSTs JSON when events fire. SMTP is an optional backup channel.

---

## Protect your main site

If your main website (`example.com`) is hosted **elsewhere** (not this homelab):

- Leave `LEGACY_DDNS_DOMAINS=` **empty**
- **Never** add the apex via Add Service
- The app **never** auto-updates `example.com` or `www.example.com` DDNS

Only **subdomains** you add (e.g. `home.example.com`) are managed. Your apex DNS in Cloudflare stays under your control.

---

## Replacing favonia/cloudflare-ddns

Stop the old container before using this app:

```bash
docker stop cloudflare-ddns
docker rm cloudflare-ddns
```

| Old (favonia) | New (this app) |
|---------------|----------------|
| `DOMAINS=...` in compose | Leave `LEGACY_DDNS_DOMAINS` empty; use **Add Service** |
| `CLOUDFLARE_API_TOKEN_FILE` | `CLOUDFLARE_API_TOKEN` in `.env` |
| `@every 5m` | `DDNS_INTERVAL_MINUTES=5` |
| Manual reverse proxy (NPM, tunnel) | Built-in **Caddy** |

---

## Day-to-day commands

From `/opt/homelab-dns-manager`:

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Logs (dashboard)
docker compose logs -f homelab-dns

# Logs (Caddy / HTTPS)
docker compose logs -f caddy

# Rebuild after code update (source deploy only)
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build

# Update from Docker Hub (recommended)
docker compose pull && docker compose up -d

# Health check
curl http://localhost:8000/api/health
```

---

## Updating the app

### Docker Hub (recommended)

```bash
cd /opt/homelab-dns-manager
docker compose pull
docker compose up -d
```

Data persists in the Docker volume `homelab_data` (database, Caddy config, certificates).

### Zip / source deploy (alternative)

**On your computer:**

```bash
python3 scripts/package.py
scp dist/homelab-dns-manager-*.zip user@YOUR_SERVER:/tmp/
```

**On the server:**

```bash
cd /opt/homelab-dns-manager
unzip -o /tmp/homelab-dns-manager-*.zip
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

**Keep your existing `.env`** — do not overwrite it when unzipping.

### `.env` vs `.env.example`

Deploy updates **`.env.example`** only. Your live **`.env`** is never replaced automatically (so secrets stay safe).

After deploy, merge any **new keys** from the example into `.env` on the server:

```bash
cd /opt/homelab-dns-manager
python3 scripts/merge_env.py    # adds missing keys; keeps your existing values
docker compose up -d            # reload if env vars changed
```

Your secrets (`SECRET_KEY`, `CLOUDFLARE_API_TOKEN`, `ACME_EMAIL`, etc.) are preserved.  
Values you already set (e.g. `DDNS_PROXIED_DEFAULT=true`) are **not** overwritten — only missing keys are added.

---

## Troubleshooting

### Container won't start

```bash
docker compose logs homelab-dns
```

- `.env` missing → `cp .env.example .env` and fill in
- Invalid `CLOUDFLARE_API_TOKEN` → create a new token at Cloudflare
- Port 8000 in use → set `PORT=8001` in `.env`, then `docker compose up -d`

### Cloudflare "Not Configured" or Test fails

- Token must be a **Cloudflare API Token** (not global API key, not third-party `fut_` keys)
- Set `CLOUDFLARE_API_TOKEN` in `.env`, then `docker compose up -d`
- Or use **Settings → Cloudflare → Replace API token…**

### Subdomain works on LAN but not from outside

- Router must forward **80** and **443** to the server (not 3100, etc.)
- DNS should be **grey cloud** (DNS only) for Let's Encrypt mode
- Check Caddy: `docker compose logs caddy`
- Test: `curl -I https://home.example.com` from cellular data

### Caddy / HTTPS not working after adding a service

Caddy restarts automatically when you add a service. If HTTPS fails:

```bash
docker compose restart caddy
docker compose logs caddy --tail 50
```

### DDNS not updating

- Only **subdomain** records with **DDNS** badge are updated
- Apex/www are intentionally excluded
- **DNS Records** → lightning icon to force-update a record

### Can't log in

- First deploy: `admin` / `password`
- After onboarding: use the password you set
- Nuclear reset (deletes all data):

```bash
docker compose down -v
docker compose up -d --build
```

---

## File layout on the server

```
/opt/homelab-dns-manager/
├── .env                 ← secrets (create on server, never in zip)
├── .env.example
├── docker-compose.yml   ← homelab-dns + caddy
├── Dockerfile
├── scripts/package.py
├── backend/
├── frontend/
└── README.md
```

Persistent data (SQLite DB, Caddyfile, LE certs): Docker volume `homelab_data` → `/app/data` and `/data` in containers.

---

## Security notes

- `chmod 600 .env` — never commit secrets
- Change default `password` on first login (forced via onboarding)
- Keep dashboard on **LAN** or behind VPN — only expose **80/443** for public services
- Rotate Cloudflare token if exposed; revoke old tokens in Cloudflare dashboard

### Authentication & sessions

| Measure | Detail |
|---------|--------|
| **Password hashing** | Argon2id (bcrypt hashes still verified; upgraded on next login) |
| **Server-side sessions** | Each login creates a DB session; JWT includes session ID |
| **Session expiry** | Absolute limit (`SESSION_EXPIRE_MINUTES`, default 8h) |
| **Idle timeout** | Auto sign-out after inactivity (`SESSION_IDLE_MINUTES`, default 60m) |
| **Logout** | Revokes session server-side (Sign out button) |
| **Password change** | Revokes all other sessions for that user |
| **Login rate limit** | 10 attempts per minute per IP |

After deploying session support, **sign in again once** — old tokens without a session ID are rejected.

### Encrypted at rest (in app database)

| Data | Encryption |
|------|------------|
| Cloudflare API token | Fernet (`ENCRYPTION_KEY`) |
| Discord webhook URL | Fernet |
| SMTP password | Fernet |
| NPM password (legacy) | Fernet |
| User passwords | Argon2id hash (one-way, not reversible) |

Generate a strong `ENCRYPTION_KEY` with `openssl rand -base64 32` and never change it after data is stored, or encrypted secrets become unreadable.

---

## Development (optional)

### Backend (Python 3.12)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit values
mkdir -p ../data/caddy
alembic upgrade head
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev UI: `http://localhost:5173` (proxies API to port 8000).

### Production build without Docker

```bash
cd frontend && npm install && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## API overview

| Prefix | Description |
|--------|-------------|
| `/api/auth` | Login, profile, password, onboarding |
| `/api/services` | Add service, port check, provision |
| `/api/caddy` | Proxy status, hosts, Caddyfile, reload |
| `/api/domains` | Cloudflare zone sync |
| `/api/records` | App-managed DNS records (with proxy + SSL info) |
| `/api/ddns` | DDNS status and managed hostnames |
| `/api/dashboard` | Stats and activity |
| `/api/logs` | Activity logs |
| `/api/settings` | General, Cloudflare, notifications |
| `/api/notifications` | Test notification delivery |
| `/api/users` | User management (admin) |
| `/api/health` | Health check |

---

## License

MIT
