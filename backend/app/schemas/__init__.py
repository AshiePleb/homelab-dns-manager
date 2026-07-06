from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from app.models import UserRole, LogLevel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class UserBase(BaseModel):
    username: str
    email: EmailStr | None = None
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    name: str | None = Field(None, max_length=128)
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=64)
    name: str | None = Field(None, max_length=128)
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class OnboardingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    current_password: str
    new_password: str = Field(min_length=8)


class UserPreferences(BaseModel):
    theme: str = "midnight"
    font_size: int = Field(default=100, ge=90, le=130)
    reduce_motion: bool = False
    colorblind_mode: bool = False


class UserPreferencesUpdate(BaseModel):
    theme: str | None = None
    font_size: int | None = Field(default=None, ge=90, le=130)
    reduce_motion: bool | None = None
    colorblind_mode: bool | None = None


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TotpEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpDisableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    password: str


class UserResponse(UserBase):
    id: int
    name: str | None = None
    is_active: bool
    must_change_credentials: bool = False
    totp_enabled: bool = False
    preferences: UserPreferences | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    email: EmailStr | None = None
    current_password: str | None = None


class ProfileUpdateResponse(BaseModel):
    user: UserResponse
    access_token: str | None = None


class DomainResponse(BaseModel):
    id: int
    zone_id: str
    name: str
    status: str
    record_count: int = 0
    last_synced_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class DNSRecordCreate(BaseModel):
    domain_id: int
    hostname: str
    record_type: str = "A"
    content: str = ""
    proxied: bool = False
    managed: bool = True
    ttl: int = 1


class DNSRecordUpdate(BaseModel):
    hostname: str | None = None
    record_type: str | None = None
    content: str | None = None
    proxied: bool | None = None
    managed: bool | None = None
    ttl: int | None = None


class DNSRecordResponse(BaseModel):
    id: int
    domain_id: int
    domain_name: str | None = None
    cloudflare_record_id: str | None
    hostname: str
    record_type: str
    content: str
    proxied: bool
    managed: bool
    ttl: int
    status: str
    last_updated_at: datetime | None
    created_at: datetime
    # Linked Caddy reverse proxy (when created via Services)
    proxy_id: int | None = None
    forward_host: str | None = None
    forward_port: int | None = None
    port_reachable: bool | None = None
    ssl_provider: str | None = None
    ssl_mode: str | None = None
    ssl_status: str = "none"
    ssl_label: str | None = None
    ssl_message: str | None = None

    class Config:
        from_attributes = True


class DNSRecordHistoryResponse(BaseModel):
    id: int
    record_id: int
    old_content: str | None
    new_content: str
    change_reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    current_public_ip: str | None
    last_ip_change: datetime | None
    cloudflare_status: str
    dns_records_managed: int
    proxy_hosts: int
    system_health: str


class ServiceHealthRow(BaseModel):
    id: int
    hostname: str
    forward_host: str
    forward_port: int
    enabled: bool
    dns_ok: bool
    dns_message: str
    dns_addresses: list[str] = []
    https_ok: bool
    https_message: str
    port_ok: bool
    port_message: str
    ssl_status: str
    ssl_message: str
    ssl_issuer: str | None = None
    ssl_days_remaining: int | None = None
    ssl_expires_at: datetime | None = None
    ddns_managed: bool
    ddns_last_sync: datetime | None = None
    overall: str


class ActivityLogResponse(BaseModel):
    id: int
    level: LogLevel
    category: str
    message: str
    details: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class CloudflareSettings(BaseModel):
    api_token: str | None = None
    account_id: str | None = None


class NPMSettings(BaseModel):
    url: str | None = None
    username: str | None = None
    password: str | None = None


class NotificationSettings(BaseModel):
    discord_webhook: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_to: str | None = None
    notify_ip_change: bool = True
    notify_cf_failure: bool = True
    notify_service_created: bool = True
    notify_service_deleted: bool = False
    notify_record_created: bool = True
    notify_record_deleted: bool = False
    notify_ssl_expiry: bool = True


class NotificationSettingsView(BaseModel):
    discord_webhook_configured: bool = False
    smtp_password_configured: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_from: str | None = None
    smtp_to: str | None = None
    notify_ip_change: bool = True
    notify_cf_failure: bool = True
    notify_service_created: bool = True
    notify_service_deleted: bool = False
    notify_record_created: bool = True
    notify_record_deleted: bool = False
    notify_ssl_expiry: bool = True


class GeneralSettings(BaseModel):
    timezone: str = "UTC"
    refresh_interval: int = 30
    theme: str = "midnight"
    default_zone: str | None = None


class ServiceProvisionRequest(BaseModel):
    subdomain: str = Field(description="Subdomain label only, e.g. home")
    forward_host: str = ""
    forward_port: int = 80
    target: str | None = Field(
        default=None,
        description="Optional combined target e.g. 10.10.10.1:8080",
    )
    base_domain: str | None = None
    ssl_mode: str = Field(
        default="letsencrypt",
        description="Caddy obtains a Let's Encrypt certificate (DNS grey-cloud, ports 80/443)",
    )
    create_dns: bool = True
    create_proxy: bool = True
    skip_port_check: bool = False


class ServiceProvisionResponse(BaseModel):
    hostname: str
    base_domain: str
    subdomain: str
    forward_host: str
    forward_port: int
    public_ip: str | None
    proxied: bool
    ssl_mode: str
    dns_record_id: int | None
    proxy_host_id: int | None
    port_reachable: bool
    port_message: str
    mapping: str


class ServiceTemplateResponse(BaseModel):
    base_domain: str | None
    available_zones: list[str]
    example_subdomain: str
    example_hostname: str
    example_target: str


class ServiceListItem(BaseModel):
    id: int
    hostname: str
    forward_host: str
    forward_port: int
    ssl_mode: str
    ssl_label: str
    enabled: bool
    port_reachable: bool | None
    mapping: str
    dns_managed: bool
    dns_proxied: bool | None
    public_ip: str | None


class PortCheckResult(BaseModel):
    host: str
    port: int
    reachable: bool
    message: str


class SettingsResponse(BaseModel):
    general: GeneralSettings
    cloudflare_configured: bool
    npm_configured: bool
    notifications_configured: bool
    default_zone: str | None = None


class NPMProxyHostCreate(BaseModel):
    domain_names: list[str]
    forward_host: str
    forward_port: int
    ssl_enabled: bool = False
    create_dns: bool = False
    dns_proxied: bool = True


class NPMProxyHostResponse(BaseModel):
    id: int
    npm_id: int | None
    domain_names: list[str]
    forward_host: str
    forward_port: int
    ssl_enabled: bool
    mapping: str | None = None
    last_synced_at: datetime | None

    class Config:
        from_attributes = True


class ContainerResponse(BaseModel):
    id: str
    name: str
    image: str
    status: str
    state: str
    ports: list[str]
    uptime: str | None


class DDNSStatus(BaseModel):
    current_ip: str | None
    last_check: datetime | None
    next_check: datetime | None = None
    last_change: datetime | None
    interval_minutes: int
    is_running: bool
    managed_hostnames: list[str] = []
    managed_count: int = 0


class ManagedDDNSHost(BaseModel):
    id: int
    hostname: str
    content: str
    proxied: bool
    last_updated_at: str | None = None


class IPChangeLogResponse(BaseModel):
    id: int
    old_ip: str | None
    new_ip: str
    affected_records: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class CaddyStatusResponse(BaseModel):
    container_name: str
    container_running: bool
    container_status: str
    container_message: str | None = None
    caddyfile_present: bool
    site_count: int
    total_hosts: int
    acme_email: str | None = None


class CaddyHostResponse(BaseModel):
    id: int
    hostname: str
    forward_host: str
    forward_port: int
    ssl_mode: str
    enabled: bool
    port_reachable: bool | None
    mapping: str
    ssl_status: str
    ssl_label: str
    ssl_message: str
    has_cert: bool
    updated_at: datetime


class BulkRecordsRequest(BaseModel):
    record_ids: list[int] = Field(min_length=1)
    action: str = Field(description="enable_ddns | disable_ddns | force_update | delete")


class BulkRecordsResponse(BaseModel):
    updated: int
    errors: list[str] = []


class MigrateDomainRequest(BaseModel):
    record_ids: list[int] = Field(min_length=1)
    target_domain: str = Field(min_length=1)
    dry_run: bool = False


class MigrateDomainItem(BaseModel):
    record_id: int
    proxy_id: int | None = None
    old_hostname: str
    new_hostname: str
    migrated: bool


class MigrateDomainResponse(BaseModel):
    dry_run: bool
    target_domain: str
    migrated: int
    results: list[MigrateDomainItem]
    errors: list[str] = []
    caddy_reloaded: bool = False


class HealthHistoryPoint(BaseModel):
    hostname: str
    overall: str
    dns_ok: bool
    port_ok: bool
    https_ok: bool
    ssl_days_remaining: int | None
    checked_at: datetime


class VersionStatusResponse(BaseModel):
    version: str
    build_time: str | None = None
    image: str
    docker_hub_repo: str
    latest_tag: str = "latest"
    latest_published_at: str | None = None
    update_available: bool = False
    check_ok: bool = False
    image_digest: str | None = None
    latest_digest: str | None = None
