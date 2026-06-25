# HomeLab DNS Manager

**Self-hosted** dashboard for Cloudflare dynamic DNS (DDNS), homelab subdomain management, and a built-in **Caddy** reverse proxy with **Let's Encrypt / ZeroSSL** HTTPS.

Add a service in one step — e.g. subdomain `home` + target `10.10.10.1:8080` → `home.example.com` with DDNS and HTTPS.

---

## Features

- **Add Service** — subdomain + `IP:port` → Cloudflare DNS, DDNS, and Caddy proxy
- **DDNS** — updates managed subdomain A records when your public IP changes
- **Caddy + TLS** — HTTPS on ports 80/443, forwards to internal services
- **DNS records** — public IP, internal targets, port checks, SSL status
- **Apex protection** — does not auto-update your main site (`example.com` / `www`)
- **Notifications** — Discord webhooks and SMTP (IP changes, SSL expiry, failures)
- **Roles** — Admin, Operator, Viewer
- **Themes** — multiple dark and light UI themes

---

## Quick start

You only need **docker-compose.yml** and **.env** — no source code or build step.

```bash
mkdir -p ~/homelab-dns-manager && cd ~/homelab-dns-manager

curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/.env.example

cp .env.example .env
chmod 600 .env
nano .env
```

**Required in `.env`:**

```bash
openssl rand -hex 32    # SECRET_KEY
openssl rand -hex 32    # JWT_SECRET_KEY
openssl rand -base64 32 # ENCRYPTION_KEY
```

Also set `CLOUDFLARE_API_TOKEN` and `ACME_EMAIL`.

```bash
docker compose pull
docker compose up -d
```

Open **`http://YOUR_SERVER_IP:8000`** — default login `admin` / `password` (change on first sign-in).

---

## Requirements

- Docker + Docker Compose
- Domain on **Cloudflare** with API token (**Zone → DNS → Edit**)
- Router port forwards: **80** and **443** → your server

---

## Stack

| Container | Image | Role |
|-----------|-------|------|
| `homelab-dns-manager` | `ashiepleb/homelab-dns-manager` | Dashboard + API + DDNS (port **8000**) |
| `homelab-caddy` | `caddy:2-alpine` | Reverse proxy + TLS (host network **80/443**) |

Data persists in the `homelab_data` volume (SQLite database, Caddy config, certificates).

---

## Update

```bash
cd ~/homelab-dns-manager
docker compose pull
docker compose up -d
```

Pin a version in `.env`:

```env
HOMELAB_DNS_IMAGE=ashiepleb/homelab-dns-manager:v1.0.0
```

---

## Links

- **Source:** https://github.com/AshiePleb/homelab-dns-manager
- **Image:** `docker pull ashiepleb/homelab-dns-manager:latest`

---

## Docker Hub settings (reference)

**Short description** (max 100 characters):

```
Self-hosted Cloudflare DDNS + homelab dashboard with Caddy reverse proxy and Let's Encrypt HTTPS.
```

**Categories:** Networking, Developer tools, Web servers
