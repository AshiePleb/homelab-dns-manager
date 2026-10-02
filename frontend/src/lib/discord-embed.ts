/** Shared Discord embed types + sample data for the live preview (mirrors backend). */

export type DiscordEmbedField = {
  name: string;
  value: string;
  inline?: boolean;
};

export type DiscordEmbed = {
  title?: string;
  description?: string;
  color?: number;
  timestamp?: string;
  footer?: { text: string };
  fields?: DiscordEmbedField[];
};

export type NotifyEventId =
  | "ip_change"
  | "cf_failure"
  | "service_created"
  | "service_deleted"
  | "service_updated"
  | "record_created"
  | "record_deleted"
  | "record_updated"
  | "ssl_expiry"
  | "ssl_renewed"
  | "app_update"
  | "zone_synced"
  | "domain_migrated"
  | "login_failed"
  | "user_changed"
  | "api_key_changed"
  | "settings_changed"
  | "backup_restored";

export const NOTIFY_EVENT_LABELS: Record<NotifyEventId, string> = {
  ip_change: "Public IP changed",
  cf_failure: "Cloudflare failure",
  service_created: "Service created",
  service_deleted: "Service deleted",
  service_updated: "Service updated",
  record_created: "DNS record created",
  record_deleted: "DNS record deleted",
  record_updated: "DNS record updated",
  ssl_expiry: "SSL expiring",
  ssl_renewed: "SSL renew",
  app_update: "App update",
  zone_synced: "Zones synced",
  domain_migrated: "Domain migrated",
  login_failed: "Failed login",
  user_changed: "User changed",
  api_key_changed: "API key changed",
  settings_changed: "Settings changed",
  backup_restored: "Backup restored",
};

export const OPS_EVENTS: NotifyEventId[] = [
  "ip_change",
  "cf_failure",
  "service_created",
  "service_deleted",
  "service_updated",
  "record_created",
  "record_deleted",
  "record_updated",
  "ssl_expiry",
  "ssl_renewed",
  "app_update",
  "zone_synced",
  "domain_migrated",
];

export const SECURITY_EVENTS: NotifyEventId[] = [
  "login_failed",
  "user_changed",
  "api_key_changed",
  "settings_changed",
  "backup_restored",
];

export function colorToHex(color: number | undefined): string {
  if (color == null) return "#5865F2";
  return `#${color.toString(16).padStart(6, "0")}`;
}
