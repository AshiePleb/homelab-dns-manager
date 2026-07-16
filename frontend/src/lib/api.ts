const API_BASE = "/api";

class ApiClient {
  private token: string | null = localStorage.getItem("token");

  setToken(token: string | null) {
    this.token = token;
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
  }

  getToken() {
    return this.token;
  }

  private parseErrorMessage(detail: unknown, fallback: string): string {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ") || fallback;
    }
    return fallback;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      const message = this.parseErrorMessage(err.detail, res.statusText || "Request failed");

      if (res.status === 401 && path !== "/auth/login") {
        this.setToken(null);
        if (!window.location.pathname.startsWith("/login")) {
          window.location.href = "/login";
        }
      }

      throw new Error(message || "Request failed");
    }
    if (res.status === 204) return {} as T;
    return res.json();
  }

  login(username: string, password: string, totp_code?: string) {
    return this.request<{ access_token: string; expires_at?: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password, totp_code: totp_code || null }),
    });
  }

  logout() {
    return this.request("/auth/logout", { method: "POST" });
  }

  me() {
    return this.request<User>("/auth/me");
  }

  changePassword(current: string, newPass: string) {
    return this.request("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: current, new_password: newPass }),
    });
  }

  completeOnboarding(data: {
    name: string;
    email: string;
    current_password: string;
    new_password: string;
  }) {
    return this.request<User>("/auth/onboarding", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  updateProfile(data: {
    username?: string;
    name?: string;
    email?: string;
    current_password?: string;
  }) {
    return this.request<{ user: User; access_token?: string }>("/auth/profile", {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  getDashboardStats() {
    return this.request<DashboardStats>("/dashboard/stats");
  }

  getDashboardHealth() {
    return this.request<ServiceHealthRow[]>("/dashboard/health");
  }

  getHealthHistory(hostname?: string, hours = 24) {
    const params = new URLSearchParams({ hours: String(hours) });
    if (hostname) params.set("hostname", hostname);
    return this.request<HealthHistoryPoint[]>(`/dashboard/health/history?${params}`);
  }

  getPreferences() {
    return this.request<UserPreferences>("/auth/preferences");
  }

  updatePreferences(data: Partial<UserPreferences>) {
    return this.request<UserPreferences>("/auth/preferences", {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  setup2FA() {
    return this.request<{ secret: string; provisioning_uri: string }>("/auth/2fa/setup", {
      method: "POST",
    });
  }

  enable2FA(code: string) {
    return this.request("/auth/2fa/enable", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
  }

  disable2FA(code: string, password: string) {
    return this.request("/auth/2fa/disable", {
      method: "POST",
      body: JSON.stringify({ code, password }),
    });
  }

  async exportBackup(): Promise<Blob> {
    const headers: Record<string, string> = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const res = await fetch(`${API_BASE}/backup/export`, { headers });
    if (!res.ok) throw new Error("Backup export failed");
    return res.blob();
  }

  async importBackup(file: File) {
    const form = new FormData();
    form.append("file", file);
    const headers: Record<string, string> = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const res = await fetch(`${API_BASE}/backup/restore`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === "string" ? err.detail : "Restore failed");
    }
    return res.json() as Promise<{ message: string }>;
  }

  bulkRecords(record_ids: number[], action: string) {
    return this.request<{ updated: number; errors: string[] }>("/records/bulk", {
      method: "POST",
      body: JSON.stringify({ record_ids, action }),
    });
  }

  migrateDomain(
    record_ids: number[],
    target_domain: string,
    dry_run = false,
    mappings?: { record_id: number; subdomain: string }[]
  ) {
    return this.request<MigrateDomainResponse>("/records/migrate-domain", {
      method: "POST",
      body: JSON.stringify({ record_ids, target_domain, dry_run, mappings }),
    });
  }

  getVersionStatus() {
    return this.request<VersionStatus>("/system/version");
  }

  getRecentActivity(limit = 10) {
    return this.request<ActivityLog[]>(`/dashboard/activity?limit=${limit}`);
  }

  getDomains() {
    return this.request<Domain[]>("/domains");
  }

  syncDomains() {
    return this.request("/domains/sync", { method: "POST" });
  }

  syncDomain(id: number) {
    return this.request(`/domains/${id}/sync`, { method: "POST" });
  }

  deleteDomain(id: number) {
    return this.request(`/domains/${id}`, { method: "DELETE" });
  }

  getRecords(domainId?: number) {
    const q = domainId ? `?domain_id=${domainId}` : "";
    return this.request<DNSRecord[]>(`/records${q}`);
  }

  createRecord(data: DNSRecordCreate) {
    return this.request<DNSRecord>("/records", { method: "POST", body: JSON.stringify(data) });
  }

  updateRecord(id: number, data: Partial<DNSRecordCreate>) {
    return this.request<DNSRecord>(`/records/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  deleteRecord(id: number) {
    return this.request(`/records/${id}`, { method: "DELETE" });
  }

  forceUpdateRecord(id: number) {
    return this.request(`/records/${id}/force-update`, { method: "POST" });
  }

  getRecordHistory(id: number) {
    return this.request<RecordHistory[]>(`/records/${id}/history`);
  }

  getDDNSStatus() {
    return this.request<DDNSStatus>("/ddns/status");
  }

  getDDNSManaged() {
    return this.request<{ id: number; hostname: string; content: string; proxied: boolean }[]>("/ddns/managed");
  }

  runDDNSCheck() {
    return this.request("/ddns/check", { method: "POST" });
  }

  getIPHistory() {
    return this.request<IPChangeLog[]>("/ddns/history");
  }

  getNPMHosts() {
    return this.request<NPMHost[]>("/npm/hosts");
  }

  syncNPM() {
    return this.request("/npm/sync", { method: "POST" });
  }

  createNPMHost(data: NPMHostCreate) {
    return this.request<NPMHost>("/npm/hosts", { method: "POST", body: JSON.stringify(data) });
  }

  deleteNPMHost(id: number) {
    return this.request(`/npm/hosts/${id}`, { method: "DELETE" });
  }

  getContainers() {
    return this.request<Container[]>("/docker/containers");
  }

  containerAction(id: string, action: string) {
    return this.request(`/docker/containers/${id}/${action}`, { method: "POST" });
  }

  getContainerLogs(id: string, tail = 100) {
    return this.request<{ logs: string }>(`/docker/containers/${id}/logs?tail=${tail}`);
  }

  getContainerDetails(id: string) {
    return this.request(`/docker/containers/${id}`);
  }

  getLogs(level?: string, limit = 100) {
    const q = level ? `?level=${level}&limit=${limit}` : `?limit=${limit}`;
    return this.request<ActivityLog[]>(`/logs${q}`);
  }

  getSettings() {
    return this.request<AppSettings>("/settings");
  }

  getZoneNames() {
    return this.request<string[]>("/settings/zones");
  }

  getServiceTemplate() {
    return this.request<ServiceTemplate>("/services/template");
  }

  getServices() {
    return this.request<ServiceItem[]>("/services");
  }

  checkPort(host: string, port: number) {
    return this.request<PortCheckResult>(`/services/check-port?host=${encodeURIComponent(host)}&port=${port}`);
  }

  provisionService(data: ServiceProvisionRequest) {
    return this.request<ServiceProvisionResult>("/services/provision", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  updateService(
    id: number,
    data: { target?: string; forward_host?: string; forward_port?: number; skip_port_check?: boolean }
  ) {
    return this.request<{
      id: number;
      hostname: string;
      forward_host: string;
      forward_port: number;
      port_reachable: boolean | null;
      port_message: string;
      mapping: string;
      changed: boolean;
      caddy_reloaded: boolean;
    }>(`/services/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  deleteService(id: number) {
    return this.request(`/services/${id}`, { method: "DELETE" });
  }

  updateGeneral(data: GeneralSettings) {
    return this.request("/settings/general", { method: "PUT", body: JSON.stringify(data) });
  }

  updateCloudflare(data: { api_token?: string; account_id?: string }) {
    return this.request("/settings/cloudflare", { method: "PUT", body: JSON.stringify(data) });
  }

  updateNPM(data: { url?: string; username?: string; password?: string }) {
    return this.request("/settings/npm", { method: "PUT", body: JSON.stringify(data) });
  }

  getNotificationSettings() {
    return this.request<NotificationSettingsView>("/settings/notifications");
  }

  updateNotifications(data: NotificationSettings) {
    return this.request("/settings/notifications", { method: "PUT", body: JSON.stringify(data) });
  }

  testCloudflare() {
    return this.request("/cloudflare/test", { method: "POST" });
  }

  syncCloudflare() {
    return this.request("/cloudflare/sync", { method: "POST" });
  }

  testNotifications() {
    return this.request("/notifications/test", { method: "POST" });
  }

  getUsers() {
    return this.request<User[]>("/users");
  }

  createUser(data: { username: string; password: string; name?: string; email?: string; role: string }) {
    return this.request("/users", { method: "POST", body: JSON.stringify(data) });
  }

  updateUser(
    id: number,
    data: {
      username?: string;
      name?: string;
      email?: string;
      role?: string;
      is_active?: boolean;
      password?: string;
    }
  ) {
    return this.request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  deleteUser(id: number) {
    return this.request(`/users/${id}`, { method: "DELETE" });
  }

  getApiEndpoint() {
    return this.request<ApiEndpointInfo>("/api-keys/endpoint");
  }

  getApiKeys() {
    return this.request<ApiKey[]>("/api-keys");
  }

  createApiKey(data: { name: string; max_dns_records: number; max_services: number }) {
    return this.request<ApiKeyCreated>("/api-keys", { method: "POST", body: JSON.stringify(data) });
  }

  revokeApiKey(id: number) {
    return this.request(`/api-keys/${id}`, { method: "DELETE" });
  }

  getCaddyStatus() {
    return this.request<CaddyStatus>("/caddy/status");
  }

  getCaddyHosts() {
    return this.request<CaddyHost[]>("/caddy/hosts");
  }

  getCaddyConfig() {
    return this.request<{ content: string; path: string }>("/caddy/config");
  }

  reloadCaddy() {
    return this.request<{ reloaded: boolean; site_count: number }>("/caddy/reload", {
      method: "POST",
    });
  }
}

export const api = new ApiClient();

export interface User {
  id: number;
  username: string;
  name?: string;
  email?: string;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
  must_change_credentials: boolean;
  totp_enabled?: boolean;
  preferences?: UserPreferences;
  created_at: string;
}

export interface UserPreferences {
  theme: string;
  font_size: number;
  reduce_motion: boolean;
  colorblind_mode: boolean;
}

export interface HealthHistoryPoint {
  hostname: string;
  overall: string;
  dns_ok: boolean;
  port_ok: boolean;
  https_ok: boolean;
  ssl_days_remaining: number | null;
  checked_at: string;
}

export interface VersionStatus {
  version: string;
  build_time: string | null;
  image: string;
  docker_hub_repo: string;
  latest_tag: string;
  latest_version?: string | null;
  latest_published_at: string | null;
  update_available: boolean;
  check_ok: boolean;
  image_digest?: string | null;
  latest_digest?: string | null;
}

export interface DashboardStats {
  current_public_ip: string | null;
  last_ip_change: string | null;
  cloudflare_status: string;
  dns_records_managed: number;
  proxy_hosts: number;
  system_health: string;
}

export interface ActivityLog {
  id: number;
  level: "info" | "warning" | "error" | "success";
  category: string;
  message: string;
  details?: Record<string, unknown>;
  created_at: string;
}

export interface Domain {
  id: number;
  zone_id: string;
  name: string;
  status: string;
  record_count: number;
  last_synced_at: string | null;
  created_at: string;
}

export interface MigrateDomainItem {
  record_id: number;
  proxy_id: number | null;
  old_hostname: string;
  new_hostname: string;
  subdomain: string | null;
  migrated: boolean;
}

export interface MigrateDomainResponse {
  dry_run: boolean;
  target_domain: string;
  migrated: number;
  results: MigrateDomainItem[];
  errors: string[];
  caddy_reloaded: boolean;
}

export interface DNSRecord {
  id: number;
  domain_id: number;
  domain_name?: string;
  cloudflare_record_id?: string;
  hostname: string;
  record_type: string;
  content: string;
  proxied: boolean;
  managed: boolean;
  ttl: number;
  status: string;
  last_updated_at: string | null;
  created_at: string;
  proxy_id?: number | null;
  forward_host?: string | null;
  forward_port?: number | null;
  port_reachable?: boolean | null;
  ssl_provider?: string | null;
  ssl_mode?: string | null;
  ssl_status?: "none" | "active" | "pending" | "warning" | "error";
  ssl_label?: string | null;
  ssl_message?: string | null;
}

export interface DNSRecordCreate {
  domain_id: number;
  hostname: string;
  record_type: string;
  content: string;
  proxied: boolean;
  managed: boolean;
  ttl: number;
}

export interface RecordHistory {
  id: number;
  record_id: number;
  old_content: string | null;
  new_content: string;
  change_reason: string;
  created_at: string;
}

export interface DDNSStatus {
  current_ip: string | null;
  last_check: string | null;
  next_check: string | null;
  last_change: string | null;
  interval_minutes: number;
  is_running: boolean;
  managed_hostnames: string[];
  managed_count: number;
}

export interface ServiceHealthRow {
  id: number;
  hostname: string;
  forward_host: string;
  forward_port: number;
  enabled: boolean;
  dns_ok: boolean;
  dns_message: string;
  dns_addresses: string[];
  https_ok: boolean;
  https_message: string;
  port_ok: boolean;
  port_message: string;
  ssl_status: string;
  ssl_message: string;
  ssl_issuer: string | null;
  ssl_days_remaining: number | null;
  ssl_expires_at: string | null;
  ddns_managed: boolean;
  ddns_last_sync: string | null;
  overall: "healthy" | "degraded" | "down" | "inactive";
}

export interface IPChangeLog {
  id: number;
  old_ip: string | null;
  new_ip: string;
  affected_records?: Record<string, unknown>;
  created_at: string;
}

export interface NPMHost {
  id: number;
  npm_id?: number;
  domain_names: string[];
  forward_host: string;
  forward_port: number;
  ssl_enabled: boolean;
  mapping?: string;
  last_synced_at: string | null;
}

export interface NPMHostCreate {
  domain_names: string[];
  forward_host: string;
  forward_port: number;
  ssl_enabled: boolean;
  create_dns: boolean;
  dns_proxied: boolean;
}

export interface Container {
  id: string;
  name: string;
  image: string;
  status: string;
  state: string;
  ports: string[];
  uptime: string | null;
}

export interface GeneralSettings {
  timezone: string;
  refresh_interval: number;
  theme: string;
  default_zone?: string | null;
}

export interface ServiceTemplate {
  base_domain: string | null;
  available_zones: string[];
  example_subdomain: string;
  example_hostname: string;
  example_target: string;
}

export interface ServiceProvisionRequest {
  subdomain: string;
  target?: string;
  forward_host?: string;
  forward_port?: number;
  base_domain?: string;
  ssl_mode?: "cloudflare" | "letsencrypt";
  create_dns?: boolean;
  create_proxy?: boolean;
  skip_port_check?: boolean;
}

export interface ServiceProvisionResult {
  hostname: string;
  base_domain: string;
  mapping: string;
  public_ip: string | null;
  ssl_mode: string;
  port_reachable: boolean;
  port_message: string;
  dns_record_id: number | null;
  proxy_host_id: number | null;
}

export interface PortCheckResult {
  host: string;
  port: number;
  reachable: boolean;
  message: string;
}

export interface ServiceItem {
  id: number;
  hostname: string;
  forward_host: string;
  forward_port: number;
  ssl_mode: string;
  ssl_label: string;
  enabled: boolean;
  port_reachable: boolean | null;
  mapping: string;
  dns_managed: boolean;
  dns_proxied: boolean | null;
  public_ip: string | null;
}

export interface NotificationSettingsView {
  discord_webhook_configured: boolean;
  smtp_password_configured: boolean;
  smtp_host?: string | null;
  smtp_port: number;
  smtp_username?: string | null;
  smtp_from?: string | null;
  smtp_to?: string | null;
  notify_ip_change: boolean;
  notify_cf_failure: boolean;
  notify_service_created: boolean;
  notify_service_deleted: boolean;
  notify_record_created: boolean;
  notify_record_deleted: boolean;
  notify_ssl_expiry: boolean;
}

export interface NotificationSettings {
  discord_webhook?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_from?: string;
  smtp_to?: string;
  notify_ip_change?: boolean;
  notify_cf_failure?: boolean;
  notify_service_created?: boolean;
  notify_service_deleted?: boolean;
  notify_record_created?: boolean;
  notify_record_deleted?: boolean;
  notify_ssl_expiry?: boolean;
}

export interface AppSettings {
  general: GeneralSettings;
  cloudflare_configured: boolean;
  npm_configured: boolean;
  notifications_configured: boolean;
  default_zone?: string | null;
}

export interface CaddyStatus {
  container_name: string;
  container_running: boolean;
  container_status: string;
  container_message?: string | null;
  caddyfile_present: boolean;
  site_count: number;
  total_hosts: number;
  acme_email?: string | null;
}

export interface CaddyHost {
  id: number;
  hostname: string;
  forward_host: string;
  forward_port: number;
  ssl_mode: string;
  enabled: boolean;
  port_reachable: boolean | null;
  mapping: string;
  ssl_status: "none" | "active" | "pending" | "warning" | "error";
  ssl_label: string;
  ssl_message: string;
  has_cert: boolean;
  updated_at: string;
}

export interface ApiKeyUsage {
  dns_records: number;
  services: number;
}

export interface ApiKey {
  id: number;
  name: string;
  key_prefix: string;
  max_dns_records: number;
  max_services: number;
  is_active: boolean;
  usage: ApiKeyUsage;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  api_key: string;
}

export interface ApiEndpointInfo {
  api_base: string;
  auth_header: string;
  docs_note: string;
}
