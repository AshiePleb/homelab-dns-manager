from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "HomeLab DNS Manager"
    secret_key: str = "change-me"
    encryption_key: str = "change-me-32-byte-base64-key!!"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite+aiosqlite:////app/data/homelab_dns.db"

    jwt_secret_key: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # legacy; sessions use session_expire_minutes
    session_expire_minutes: int = 480  # absolute session lifetime (8 hours)
    session_idle_minutes: int = 60  # log out after inactivity

    ddns_interval_minutes: int = 5
    public_ip_check_url: str = "https://api.ipify.org"

    docker_socket: str = "/var/run/docker.sock"

    admin_username: str = "admin"
    admin_password: str = "password"
    admin_email: str = "admin@example.com"
    admin_name: str = "Admin User"

    # Cloudflare — token from .env (CLOUDFLARE_API_TOKEN); optional file fallback
    cloudflare_api_token: str | None = None
    cloudflare_api_token_file: str | None = None

    # One-time import from favonia DOMAINS= list (comma-separated FQDNs)
    legacy_ddns_domains: str | None = None
    ddns_proxied_default: bool = True

    # Let's Encrypt contact email (used by built-in Caddy reverse proxy)
    acme_email: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
