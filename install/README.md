# Install bundle

End users only need these two files — no clone required.

```bash
mkdir -p ~/homelab-dns-manager && cd ~/homelab-dns-manager

curl -fsSLO https://raw.githubusercontent.com/ashiepleb/homelab-dns-manager/main/install/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/ashiepleb/homelab-dns-manager/main/install/.env.example

cp .env.example .env
chmod 600 .env
nano .env

docker compose pull
docker compose up -d
```

See the [main README](../README.md) for full setup (secrets, Cloudflare token, port forwards).
