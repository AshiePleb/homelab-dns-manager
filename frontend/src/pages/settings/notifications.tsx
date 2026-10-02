import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ArrowRight, MessageSquare } from "lucide-react";
import { api, NotificationSettingsView } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/context/auth";
import {
  NOTIFY_EVENT_LABELS,
  OPS_EVENTS,
  SECURITY_EVENTS,
  NotifyEventId,
} from "@/lib/discord-embed";

type ToggleKey = `notify_${NotifyEventId}`;

const EVENT_DESCRIPTIONS: Partial<Record<NotifyEventId, string>> = {
  ip_change: "DDNS detects your public IP changed and updates records.",
  cf_failure: "A Cloudflare DNS sync or record update failed.",
  service_created: "A new service (DNS + Caddy) was provisioned.",
  service_deleted: "A Caddy proxy / service was removed.",
  service_updated: "A service upstream target was changed.",
  record_created: "A DNS record was created in the app.",
  record_deleted: "A DNS record was deleted.",
  record_updated: "A DNS record was updated.",
  ssl_expiry: "A certificate is within the expiry alert window.",
  ssl_renewed: "A certificate renew was requested.",
  app_update: "An in-app Docker update was started.",
  zone_synced: "Cloudflare zones were synced.",
  domain_migrated: "Services were migrated to another domain.",
  login_failed: "Someone failed to sign in.",
  user_changed: "A user account was created, updated, or deleted.",
  api_key_changed: "An API key was created, updated, or revoked.",
  settings_changed: "App settings were changed.",
  backup_restored: "A backup was restored.",
};

function emptyToggles(): Record<ToggleKey, boolean> {
  const all = [...OPS_EVENTS, ...SECURITY_EVENTS];
  return Object.fromEntries(all.map((e) => [`notify_${e}`, false])) as Record<ToggleKey, boolean>;
}

export function NotificationsSettingsPage() {
  const { isAdmin } = useAuth();
  const [view, setView] = useState<NotificationSettingsView | null>(null);
  const [smtp, setSmtp] = useState({
    smtp_host: "",
    smtp_port: 587,
    smtp_username: "",
    smtp_password: "",
    smtp_from: "",
    smtp_to: "",
  });
  const [toggles, setToggles] = useState(emptyToggles());
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const load = async () => {
    const v = await api.getNotificationSettings();
    setView(v);
    setSmtp({
      smtp_host: v.smtp_host || "",
      smtp_port: v.smtp_port,
      smtp_username: v.smtp_username || "",
      smtp_password: "",
      smtp_from: v.smtp_from || "",
      smtp_to: v.smtp_to || "",
    });
    const next = emptyToggles();
    for (const e of [...OPS_EVENTS, ...SECURITY_EVENTS]) {
      const key = `notify_${e}` as ToggleKey;
      next[key] = Boolean(v[key as keyof NotificationSettingsView]);
    }
    setToggles(next);
  };

  useEffect(() => {
    if (isAdmin) void load();
  }, [isAdmin]);

  if (!isAdmin) return <Navigate to="/settings" replace />;

  const showMsg = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 5000);
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        ...smtp,
        smtp_host: smtp.smtp_host || null,
        smtp_username: smtp.smtp_username || null,
        smtp_from: smtp.smtp_from || null,
        smtp_to: smtp.smtp_to || null,
        ...toggles,
      };
      if (!smtp.smtp_password.trim()) delete payload.smtp_password;
      await api.updateNotifications(payload);
      await load();
      showMsg("Notification settings saved");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const renderGroup = (title: string, events: NotifyEventId[]) => (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>Toggle which events send Discord / email alerts</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {events.map((ev) => {
          const key = `notify_${ev}` as ToggleKey;
          return (
            <label
              key={ev}
              className="flex cursor-pointer items-start gap-3 rounded-md border border-border px-4 py-3 hover:bg-secondary/30"
            >
              <input
                type="checkbox"
                className="mt-1"
                checked={toggles[key]}
                onChange={(e) => setToggles({ ...toggles, [key]: e.target.checked })}
              />
              <div>
                <p className="text-sm font-medium">{NOTIFY_EVENT_LABELS[ev]}</p>
                <p className="text-xs text-muted-foreground">{EVENT_DESCRIPTIONS[ev]}</p>
              </div>
            </label>
          );
        })}
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link to="/settings" className="text-primary hover:underline">
            Settings
          </Link>{" "}
          / Notifications
        </p>
        <h2 className="text-2xl font-bold tracking-tight mt-1">Notifications</h2>
        <p className="text-muted-foreground">
          Choose alert events and email delivery. Configure Discord on its own page.
        </p>
      </div>

      {message && (
        <div className="rounded-md border border-primary/20 bg-primary/10 px-4 py-2 text-sm text-primary">
          {message}
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-primary" />
                Discord
              </CardTitle>
              <CardDescription>Webhook, plain vs embed, username, and live preview</CardDescription>
            </div>
            <Badge variant={view?.discord_webhook_configured ? "success" : "secondary"}>
              {view?.discord_webhook_configured ? "Configured" : "Not set"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link to="/settings/notifications/discord">
              Open Discord settings
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Email (SMTP)</CardTitle>
          <CardDescription>Optional backup channel — STARTTLS on the port you set</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>SMTP host</Label>
            <Input
              value={smtp.smtp_host}
              onChange={(e) => setSmtp({ ...smtp, smtp_host: e.target.value })}
              placeholder="smtp.gmail.com"
            />
          </div>
          <div className="space-y-2">
            <Label>SMTP port</Label>
            <Input
              type="number"
              value={smtp.smtp_port}
              onChange={(e) => setSmtp({ ...smtp, smtp_port: Number(e.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>Username</Label>
            <Input
              value={smtp.smtp_username}
              onChange={(e) => setSmtp({ ...smtp, smtp_username: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>Password</Label>
            <Input
              type="password"
              placeholder={view?.smtp_password_configured ? "Saved — enter to replace" : "App password"}
              value={smtp.smtp_password}
              onChange={(e) => setSmtp({ ...smtp, smtp_password: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>From</Label>
            <Input value={smtp.smtp_from} onChange={(e) => setSmtp({ ...smtp, smtp_from: e.target.value })} />
          </div>
          <div className="space-y-2">
            <Label>To</Label>
            <Input value={smtp.smtp_to} onChange={(e) => setSmtp({ ...smtp, smtp_to: e.target.value })} />
          </div>
        </CardContent>
      </Card>

      {renderGroup("Ops alerts", OPS_EVENTS)}
      {renderGroup("Security & admin", SECURITY_EVENTS)}

      <Button onClick={save} disabled={saving}>
        {saving ? "Saving…" : "Save notification settings"}
      </Button>
    </div>
  );
}
