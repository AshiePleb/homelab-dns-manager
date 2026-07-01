# Install bundle

End users only need these two files — no clone required.

```bash
mkdir -p /opt/homelab-dns-manager && cd /opt/homelab-dns-manager

curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/.env.example

cp .env.example .env
chmod 600 .env

# Generate secrets — paste each line into .env
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
echo "ENCRYPTION_KEY=$(openssl rand -base64 32)"

nano .env   # Cloudflare token, ACME_EMAIL, etc.

docker compose pull
docker compose up -d
```

After new releases, merge any new keys from `.env.example` into your `.env`:

```bash
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/.env.example
curl -fsSLO https://raw.githubusercontent.com/AshiePleb/homelab-dns-manager/main/install/merge_env.py
python3 merge_env.py
```

See the [main README](../README.md) for full setup (Cloudflare token, port forwards, first login).
