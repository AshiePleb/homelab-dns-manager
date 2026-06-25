import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { api, AppSettings, NotificationSettingsView, User } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { cn, formatDate } from "@/lib/utils";
import { useAuth } from "@/context/auth";
import { useTheme } from "@/context/theme";
import { ThemePicker } from "@/components/theme-picker";
import { ThemeId, normalizeThemeId, applyThemeClass } from "@/lib/themes";

type TabId = "profile" | "general" | "cloudflare" | "notifications" | "users";

const TIMEZONES = [
  { value: "UTC", label: "UTC" },
  { value: "Europe/London", label: "London (GMT/BST)" },
  { value: "Europe/Paris", label: "Paris / Berlin (CET)" },
  { value: "Europe/Amsterdam", label: "Amsterdam" },
  { value: "America/New_York", label: "New York (Eastern)" },
  { value: "America/Chicago", label: "Chicago (Central)" },
  { value: "America/Denver", label: "Denver (Mountain)" },
  { value: "America/Los_Angeles", label: "Los Angeles (Pacific)" },
  { value: "Asia/Tokyo", label: "Tokyo" },
  { value: "Asia/Singapore", label: "Singapore" },
  { value: "Australia/Sydney", label: "Sydney" },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin — full access",
  operator: "Operator — manage DNS & services",
  viewer: "Viewer — read only",
};

const NOTIFICATION_EVENTS = [
  {
    key: "notify_ip_change" as const,
    title: "Public IP changed",
    description: "When DDNS detects your home IP has changed and updates records.",
  },
  {
    key: "notify_cf_failure" as const,
    title: "Cloudflare update failed",
    description: "When a DNS sync or record update to Cloudflare fails.",
  },
  {
    key: "notify_service_created" as const,
    title: "New service provisioned",
    description: "When you add a service (DNS + Caddy proxy) via Add Service.",
  },
  {
    key: "notify_record_created" as const,
    title: "New DNS record",
    description: "When a DNS record is created in the app (manual or via provisioning).",
  },
  {
    key: "notify_service_deleted" as const,
    title: "Service removed",
    description: "When a Caddy proxy / homelab service is deleted.",
  },
  {
    key: "notify_record_deleted" as const,
    title: "DNS record removed",
    description: "When a DNS record is deleted from the app.",
  },
  {
    key: "notify_ssl_expiry" as const,
    title: "SSL certificate expiring",
    description: "When a Let's Encrypt certificate managed by Caddy is close to expiry.",
  },
];

const selectClass =
  "flex h-9 w-full rounded-md border border-input bg-secondary/50 px-3 text-sm disabled:opacity-50";

export function SettingsPage() {
  const { isAdmin, user, refreshUser } = useAuth();
  const { setTheme } = useTheme();
  const [tab, setTab] = useState<TabId>("profile");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState<string | null>(null);

  const [general, setGeneral] = useState({
    timezone: "UTC",
    refresh_interval: 5,
    theme: "midnight" as ThemeId,
    default_zone: "" as string | null,
  });
  const [zoneNames, setZoneNames] = useState<string[]>([]);
  const [cloudflare, setCloudflare] = useState({ api_token: "" });
  const [showCfTokenRotate, setShowCfTokenRotate] = useState(false);
  const [profile, setProfile] = useState({ username: "", name: "", email: "", current_password: "" });
  const [notifyView, setNotifyView] = useState<NotificationSettingsView | null>(null);
  const [notify, setNotify] = useState({
    discord_webhook: "",
    smtp_host: "",
    smtp_port: 587,
    smtp_username: "",
    smtp_password: "",
    smtp_from: "",
    smtp_to: "",
    notify_ip_change: true,
    notify_cf_failure: true,
    notify_service_created: true,
    notify_service_deleted: false,
    notify_record_created: true,
    notify_record_deleted: false,
    notify_ssl_expiry: true,
  });
  const [passwords, setPasswords] = useState({ current: "", new: "" });

  const [userPanel, setUserPanel] = useState<"closed" | "create" | "edit">("closed");
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [userForm, setUserForm] = useState({
    username: "",
    name: "",
    email: "",
    password: "",
    role: "viewer",
    is_active: true,
  });

  const tabs: { id: TabId; label: string; adminOnly?: boolean }[] = [
    { id: "profile", label: "Profile" },
    { id: "general", label: "General" },
    { id: "cloudflare", label: "Cloudflare" },
    { id: "notifications", label: "Notifications", adminOnly: true },
    { id: "users", label: "Users", adminOnly: true },
  ];

  const visibleTabs = tabs.filter((t) => !t.adminOnly || isAdmin);

  const showMsg = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 5000);
  };

  const loadNotifications = async () => {
    const view = await api.getNotificationSettings();
    setNotifyView(view);
    setNotify((n) => ({
      ...n,
      discord_webhook: "",
      smtp_host: view.smtp_host || "",
      smtp_port: view.smtp_port,
      smtp_username: view.smtp_username || "",
      smtp_password: "",
      smtp_from: view.smtp_from || "",
      smtp_to: view.smtp_to || "",
      notify_ip_change: view.notify_ip_change,
      notify_cf_failure: view.notify_cf_failure,
      notify_service_created: view.notify_service_created,
      notify_service_deleted: view.notify_service_deleted,
      notify_record_created: view.notify_record_created,
      notify_record_deleted: view.notify_record_deleted,
      notify_ssl_expiry: view.notify_ssl_expiry,
    }));
  };

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      setGeneral({
        ...s.general,
        theme: normalizeThemeId(s.general.theme),
        default_zone: s.general.default_zone || s.default_zone || "",
      });
    });
    api.getZoneNames().then(setZoneNames).catch(() => {});
    if (isAdmin) {
      api.getUsers().then(setUsers);
      loadNotifications().catch(() => {});
    }
  }, [isAdmin]);

  useEffect(() => {
    if (user) {
      setProfile({
        username: user.username,
        name: user.name || "",
        email: user.email || "",
        current_password: "",
      });
    }
  }, [user]);

  const saveGeneral = async () => {
    setSaving("general");
    try {
      const themeId = normalizeThemeId(general.theme);
      applyThemeClass(themeId);
      await api.updateGeneral({ ...general, theme: themeId });
      setTheme(themeId);
      showMsg("General settings saved");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Failed to save general settings");
    } finally {
      setSaving(null);
    }
  };

  const saveCloudflare = async () => {
    if (!cloudflare.api_token.trim()) {
      showMsg("Paste a new API token in the field above first");
      return;
    }
    setSaving("cloudflare");
    try {
      await api.updateCloudflare({ api_token: cloudflare.api_token });
      showMsg("Cloudflare API token updated");
      setCloudflare({ api_token: "" });
      setShowCfTokenRotate(false);
      setSettings(await api.getSettings());
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Failed to save Cloudflare settings");
    } finally {
      setSaving(null);
    }
  };

  const testCloudflare = async () => {
    setSaving("cf-test");
    try {
      await api.testCloudflare();
      showMsg("Cloudflare connection successful");
      setSettings(await api.getSettings());
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Cloudflare test failed");
    } finally {
      setSaving(null);
    }
  };

  const saveProfile = async () => {
    try {
      const payload: {
        username?: string;
        name?: string;
        email?: string;
        current_password?: string;
      } = {
        name: profile.name || undefined,
        email: profile.email || undefined,
      };
      if (profile.username !== user?.username) {
        payload.username = profile.username;
        payload.current_password = profile.current_password;
      }
      const result = await api.updateProfile(payload);
      if (result.access_token) api.setToken(result.access_token);
      await refreshUser();
      setProfile((p) => ({ ...p, current_password: "" }));
      showMsg("Profile updated");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Failed");
    }
  };

  const saveNotify = async () => {
    setSaving("notify");
    try {
      const payload: Record<string, unknown> = {
        smtp_host: notify.smtp_host || null,
        smtp_port: notify.smtp_port,
        smtp_username: notify.smtp_username || null,
        smtp_from: notify.smtp_from || null,
        smtp_to: notify.smtp_to || null,
        notify_ip_change: notify.notify_ip_change,
        notify_cf_failure: notify.notify_cf_failure,
        notify_service_created: notify.notify_service_created,
        notify_service_deleted: notify.notify_service_deleted,
        notify_record_created: notify.notify_record_created,
        notify_record_deleted: notify.notify_record_deleted,
        notify_ssl_expiry: notify.notify_ssl_expiry,
      };
      if (notify.discord_webhook.trim()) payload.discord_webhook = notify.discord_webhook.trim();
      if (notify.smtp_password.trim()) payload.smtp_password = notify.smtp_password.trim();
      await api.updateNotifications(payload);
      await loadNotifications();
      showMsg("Notification settings saved");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Failed to save notifications");
    } finally {
      setSaving(null);
    }
  };

  const testNotify = async () => {
    setSaving("notify-test");
    try {
      const result = await api.testNotifications();
      const parts = (result as { results: { channel: string; status: string; message?: string }[] }).results.map(
        (r: { channel: string; status: string; message?: string }) =>
          `${r.channel}: ${r.status}${r.message ? ` (${r.message})` : ""}`
      );
      showMsg(parts.length ? parts.join(" · ") : "No channels configured — add a Discord webhook or SMTP first");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Test failed");
    } finally {
      setSaving(null);
    }
  };

  const changePassword = async () => {
    setSaving("password");
    try {
      await api.changePassword(passwords.current, passwords.new);
      setPasswords({ current: "", new: "" });
      showMsg("Password changed");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Failed");
    } finally {
      setSaving(null);
    }
  };

  const openCreateUser = () => {
    setEditingUser(null);
    setUserForm({
      username: "",
      name: "",
      email: "",
      password: "",
      role: "viewer",
      is_active: true,
    });
    setUserPanel("create");
  };

  const openEditUser = (u: User) => {
    setEditingUser(u);
    setUserForm({
      username: u.username,
      name: u.name || "",
      email: u.email || "",
      password: "",
      role: u.role,
      is_active: u.is_active,
    });
    setUserPanel("edit");
  };

  const closeUserPanel = () => {
    setUserPanel("closed");
    setEditingUser(null);
  };

  const saveUser = async () => {
    setSaving("user");
    try {
      if (userPanel === "create") {
        if (!userForm.username.trim() || !userForm.password.trim()) {
          showMsg("Username and password are required");
          return;
        }
        await api.createUser({
          username: userForm.username.trim(),
          password: userForm.password,
          name: userForm.name.trim() || undefined,
          email: userForm.email || undefined,
          role: userForm.role,
        });
        showMsg("User created");
      } else if (editingUser) {
        const payload: {
          username?: string;
          name?: string;
          email?: string;
          role?: string;
          is_active?: boolean;
          password?: string;
        } = {
          username: userForm.username !== editingUser.username ? userForm.username : undefined,
          name: userForm.name,
          email: userForm.email || undefined,
          role: userForm.role,
          is_active: userForm.is_active,
        };
        if (userForm.password.trim()) payload.password = userForm.password;
        await api.updateUser(editingUser.id, payload);
        showMsg("User updated");
      }
      setUsers(await api.getUsers());
      closeUserPanel();
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Failed");
    } finally {
      setSaving(null);
    }
  };

  const deleteUser = async (u: User) => {
    if (!confirm(`Delete user ${u.username}?`)) return;
    try {
      await api.deleteUser(u.id);
      setUsers(await api.getUsers());
      if (editingUser?.id === u.id) closeUserPanel();
      showMsg("User deleted");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Failed to delete user");
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">Profile, integrations, alerts, and user management</p>
      </div>

      {message && (
        <div className="rounded-md bg-primary/10 border border-primary/20 px-4 py-2 text-sm text-primary">
          {message}
        </div>
      )}

      <div className="flex flex-wrap gap-1 border-b border-border pb-px">
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded-t-md px-4 py-2 text-sm font-medium transition-colors -mb-px border-b-2",
              tab === t.id
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground hover:bg-secondary/40"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "profile" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Your profile</CardTitle>
              <CardDescription>Display name, email, and login username</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Username</Label>
                  <Input
                    value={profile.username}
                    onChange={(e) => setProfile({ ...profile, username: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Display name</Label>
                  <Input
                    value={profile.name}
                    onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={profile.email}
                    onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                  />
                </div>
                {profile.username !== user?.username && (
                  <div className="space-y-2 sm:col-span-2">
                    <Label>Current password (required to change username)</Label>
                    <Input
                      type="password"
                      value={profile.current_password}
                      onChange={(e) => setProfile({ ...profile, current_password: e.target.value })}
                    />
                  </div>
                )}
              </div>
              <Button onClick={saveProfile}>Save profile</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Change password</CardTitle>
              <CardDescription>Update your login password</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Current password</Label>
                  <Input
                    type="password"
                    value={passwords.current}
                    onChange={(e) => setPasswords({ ...passwords, current: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>New password</Label>
                  <Input
                    type="password"
                    value={passwords.new}
                    onChange={(e) => setPasswords({ ...passwords, new: e.target.value })}
                  />
                </div>
              </div>
              <Button onClick={changePassword} disabled={saving === "password"}>
                {saving === "password" ? "Updating…" : "Update password"}
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "general" && (
        <Card>
          <CardHeader>
            <CardTitle>General</CardTitle>
            <CardDescription>Timezone, theme, DDNS interval, and default domain for new services</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Timezone</Label>
                <select
                  className={selectClass}
                  value={general.timezone}
                  onChange={(e) => setGeneral({ ...general, timezone: e.target.value })}
                  disabled={!isAdmin}
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>
                      {tz.label}
                    </option>
                  ))}
                  {!TIMEZONES.some((tz) => tz.value === general.timezone) && general.timezone && (
                    <option value={general.timezone}>{general.timezone}</option>
                  )}
                </select>
                <p className="text-xs text-muted-foreground">Used for timestamps across the dashboard</p>
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label>Theme</Label>
                <ThemePicker
                  variant="settings"
                  value={normalizeThemeId(general.theme)}
                  onChange={(id) => {
                    setGeneral({ ...general, theme: id });
                    setTheme(id);
                  }}
                  disabled={!isAdmin}
                />
                <p className="text-xs text-muted-foreground">
                  Also change from the palette icon in the header. Saves for all users when you&apos;re admin.
                </p>
              </div>
              <div className="space-y-2">
                <Label>DDNS interval (minutes)</Label>
                <Input
                  type="number"
                  min={1}
                  value={general.refresh_interval}
                  onChange={(e) => setGeneral({ ...general, refresh_interval: Number(e.target.value) })}
                  disabled={!isAdmin}
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label>Default domain template</Label>
                <p className="text-xs text-muted-foreground mb-1">
                  Used when adding services — enter subdomain only (e.g. home → home.example.com)
                </p>
                <select
                  className={selectClass}
                  value={general.default_zone || ""}
                  onChange={(e) => setGeneral({ ...general, default_zone: e.target.value })}
                  disabled={!isAdmin}
                >
                  <option value="">Select zone…</option>
                  {zoneNames.map((z) => (
                    <option key={z} value={z}>
                      {z}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {isAdmin && (
              <Button type="button" onClick={saveGeneral} disabled={saving === "general"}>
                {saving === "general" ? "Saving…" : "Save general"}
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "cloudflare" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <div>
                <CardTitle>Cloudflare</CardTitle>
                <CardDescription>
                  API token for DNS sync. Can also be set via CLOUDFLARE_API_TOKEN in .env on first boot.
                </CardDescription>
              </div>
              <Badge variant={settings?.cloudflare_configured ? "success" : "warning"}>
                {settings?.cloudflare_configured ? "Configured" : "Not configured"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {settings?.cloudflare_configured ? (
              <p className="text-sm text-muted-foreground">
                Token is stored encrypted. Use <strong>Test connection</strong> to verify — only replace when
                rotating the token.
              </p>
            ) : (
              <p className="text-sm text-amber-500/90">
                No token configured. Add CLOUDFLARE_API_TOKEN to .env and restart, or paste one below.
              </p>
            )}

            {isAdmin && (
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={testCloudflare} disabled={saving === "cf-test"}>
                  {saving === "cf-test" ? "Testing…" : "Test connection"}
                </Button>
                {!showCfTokenRotate && (
                  <Button type="button" variant="ghost" onClick={() => setShowCfTokenRotate(true)}>
                    Replace API token…
                  </Button>
                )}
              </div>
            )}

            {isAdmin && showCfTokenRotate && (
              <div className="space-y-3 rounded-md border border-border bg-secondary/20 p-4">
                <p className="text-xs text-muted-foreground">
                  Only use when rotating your Cloudflare token.
                </p>
                <div className="space-y-2">
                  <Label>New API token</Label>
                  <Input
                    type="text"
                    autoComplete="off"
                    placeholder="Paste token from Cloudflare dashboard"
                    value={cloudflare.api_token}
                    onChange={(e) => setCloudflare({ api_token: e.target.value })}
                    className="font-mono text-sm"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    onClick={saveCloudflare}
                    disabled={saving === "cloudflare" || !cloudflare.api_token.trim()}
                  >
                    {saving === "cloudflare" ? "Saving…" : "Save new token"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setShowCfTokenRotate(false);
                      setCloudflare({ api_token: "" });
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "notifications" && isAdmin && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>How notifications work</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                When something important happens (IP change, new service, Cloudflare error, etc.), the app
                sends a message to every channel you configure below. At least one channel is required for
                alerts to go out.
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>
                  <strong className="text-foreground">Discord webhook</strong> — In Discord: Server Settings →
                  Integrations → Webhooks → New Webhook. Copy the URL and paste it here. The app POSTs a JSON
                  payload to that URL (no bot needed).
                </li>
                <li>
                  <strong className="text-foreground">Email (SMTP)</strong> — Optional backup. Uses STARTTLS on
                  the port you set (587 by default).
                </li>
              </ul>
              <p>
                Use <strong>Send test</strong> after saving to confirm delivery. Toggle each event type
                independently.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <CardTitle>Channels</CardTitle>
                  <CardDescription>Discord webhook and optional SMTP email</CardDescription>
                </div>
                <Badge variant={notifyView?.discord_webhook_configured ? "success" : "secondary"}>
                  Discord {notifyView?.discord_webhook_configured ? "on" : "off"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Discord webhook URL</Label>
                <Input
                  type="password"
                  placeholder={
                    notifyView?.discord_webhook_configured
                      ? "Webhook saved — paste new URL to replace"
                      : "https://discord.com/api/webhooks/…"
                  }
                  value={notify.discord_webhook}
                  onChange={(e) => setNotify({ ...notify, discord_webhook: e.target.value })}
                />
                {notifyView?.discord_webhook_configured && !notify.discord_webhook && (
                  <p className="text-xs text-muted-foreground">Leave blank to keep the existing webhook</p>
                )}
              </div>

              <div className="border-t border-border pt-4">
                <p className="text-sm font-medium mb-3">SMTP email (optional)</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>SMTP host</Label>
                    <Input
                      value={notify.smtp_host}
                      onChange={(e) => setNotify({ ...notify, smtp_host: e.target.value })}
                      placeholder="smtp.gmail.com"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>SMTP port</Label>
                    <Input
                      type="number"
                      value={notify.smtp_port}
                      onChange={(e) => setNotify({ ...notify, smtp_port: Number(e.target.value) })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>SMTP username</Label>
                    <Input
                      value={notify.smtp_username}
                      onChange={(e) => setNotify({ ...notify, smtp_username: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>SMTP password</Label>
                    <Input
                      type="password"
                      placeholder={
                        notifyView?.smtp_password_configured ? "Saved — enter to replace" : "App password"
                      }
                      value={notify.smtp_password}
                      onChange={(e) => setNotify({ ...notify, smtp_password: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>From address</Label>
                    <Input
                      value={notify.smtp_from}
                      onChange={(e) => setNotify({ ...notify, smtp_from: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>To address</Label>
                    <Input
                      value={notify.smtp_to}
                      onChange={(e) => setNotify({ ...notify, smtp_to: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Alert events</CardTitle>
              <CardDescription>Choose which events trigger notifications</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {NOTIFICATION_EVENTS.map((ev) => (
                <label
                  key={ev.key}
                  className="flex items-start gap-3 rounded-md border border-border px-4 py-3 cursor-pointer hover:bg-secondary/30"
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={notify[ev.key]}
                    onChange={(e) => setNotify({ ...notify, [ev.key]: e.target.checked })}
                  />
                  <div>
                    <p className="text-sm font-medium">{ev.title}</p>
                    <p className="text-xs text-muted-foreground">{ev.description}</p>
                  </div>
                </label>
              ))}
              <div className="flex gap-2 pt-2">
                <Button onClick={saveNotify} disabled={saving === "notify"}>
                  {saving === "notify" ? "Saving…" : "Save notifications"}
                </Button>
                <Button variant="outline" onClick={testNotify} disabled={saving === "notify-test"}>
                  {saving === "notify-test" ? "Sending…" : "Send test"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "users" && isAdmin && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">Users</h3>
              <p className="text-sm text-muted-foreground">Manage accounts and roles</p>
            </div>
            <Button onClick={openCreateUser}>
              <Plus className="h-4 w-4 mr-1" />
              Add user
            </Button>
          </div>

          <DataTable
            columns={[
              { key: "user", label: "User" },
              { key: "role", label: "Role" },
              { key: "status", label: "Status" },
              { key: "created", label: "Created" },
              { key: "actions", label: "", className: "text-right" },
            ]}
            isEmpty={users.length === 0}
            emptyMessage="No users yet"
          >
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <div>
                    <p className="font-medium">{u.name || u.username}</p>
                    <p className="text-xs text-muted-foreground">
                      @{u.username}
                      {u.email ? ` · ${u.email}` : ""}
                    </p>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="capitalize">
                    {u.role}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={u.is_active ? "success" : "secondary"}>
                    {u.is_active ? "Active" : "Disabled"}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground text-xs">{formatDate(u.created_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="sm" onClick={() => openEditUser(u)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    {u.id !== user?.id && (
                      <Button variant="ghost" size="sm" onClick={() => deleteUser(u)}>
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </DataTable>
        </div>
      )}

      {userPanel !== "closed" && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={closeUserPanel} />
          <div className="relative flex h-full w-full max-w-md flex-col border-l border-border bg-background shadow-xl">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div>
                <h3 className="font-semibold">{userPanel === "create" ? "Add user" : "Edit user"}</h3>
                {editingUser && (
                  <p className="text-xs text-muted-foreground">ID {editingUser.id}</p>
                )}
              </div>
              <Button variant="ghost" size="icon" onClick={closeUserPanel}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div className="space-y-2">
                <Label>Username</Label>
                <Input
                  value={userForm.username}
                  onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
                  disabled={userPanel === "edit" && editingUser?.id === user?.id}
                />
              </div>
              <div className="space-y-2">
                <Label>Display name</Label>
                <Input
                  value={userForm.name}
                  onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={userForm.email}
                  onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>{userPanel === "create" ? "Password" : "New password"}</Label>
                <Input
                  type="password"
                  value={userForm.password}
                  onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                  placeholder={userPanel === "edit" ? "Leave blank to keep current" : "Min. 8 characters"}
                />
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <select
                  className={selectClass}
                  value={userForm.role}
                  onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
                  disabled={editingUser?.id === user?.id}
                >
                  <option value="admin">Admin</option>
                  <option value="operator">Operator</option>
                  <option value="viewer">Viewer</option>
                </select>
                <p className="text-xs text-muted-foreground">{ROLE_LABELS[userForm.role]}</p>
              </div>
              {userPanel === "edit" && editingUser?.id !== user?.id && (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={userForm.is_active}
                    onChange={(e) => setUserForm({ ...userForm, is_active: e.target.checked })}
                  />
                  Account active
                </label>
              )}
            </div>

            <div className="border-t border-border p-5 flex gap-2">
              <Button className="flex-1" onClick={saveUser} disabled={saving === "user"}>
                {saving === "user" ? "Saving…" : userPanel === "create" ? "Create user" : "Save changes"}
              </Button>
              <Button variant="outline" onClick={closeUserPanel}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
