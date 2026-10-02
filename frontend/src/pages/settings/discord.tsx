import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { Eye, Send } from "lucide-react";
import { api, NotificationSettingsView } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/context/auth";
import { DiscordEmbedPreview } from "@/components/discord-embed-preview";
import { DiscordEmbed } from "@/lib/discord-embed";

export function DiscordSettingsPage() {
  const { isAdmin } = useAuth();
  const [view, setView] = useState<NotificationSettingsView | null>(null);
  const [webhook, setWebhook] = useState("");
  const [format, setFormat] = useState<"plain" | "embed">("embed");
  const [username, setUsername] = useState("");
  const [accent, setAccent] = useState("#5865F2");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [previewEmbed, setPreviewEmbed] = useState<DiscordEmbed | null>(null);
  const [previewPlain, setPreviewPlain] = useState("");

  const load = async () => {
    const v = await api.getNotificationSettings();
    setView(v);
    setFormat(v.discord_format === "plain" ? "plain" : "embed");
    setUsername(v.discord_username || "");
    setAccent(v.discord_accent_color || "#5865F2");
    const prev = await api.previewDiscordEmbed("service_created", v.discord_accent_color || undefined);
    setPreviewEmbed(prev.embed);
    setPreviewPlain(prev.embed?.description || "Test notification");
  };

  useEffect(() => {
    if (isAdmin) void load();
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return;
    const t = setTimeout(() => {
      api.previewDiscordEmbed("service_created", accent).then((prev) => {
        setPreviewEmbed(prev.embed);
        setPreviewPlain(prev.embed?.description || "");
      }).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [accent, isAdmin]);

  if (!isAdmin) return <Navigate to="/settings" replace />;

  const showMsg = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 6000);
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        discord_format: format,
        discord_username: username.trim() || null,
        discord_accent_color: accent || "#5865F2",
      };
      if (webhook.trim()) payload.discord_webhook = webhook.trim();
      await api.updateNotifications(payload);
      setWebhook("");
      await load();
      showMsg("Discord settings saved");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      await save();
      const result = await api.testNotifications("service_created");
      const parts = result.results.map(
        (r) => `${r.channel}: ${r.status}${r.message ? ` (${r.message})` : ""}`
      );
      showMsg(parts.join(" · ") || "No channels configured");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link to="/settings" className="text-primary hover:underline">
            Settings
          </Link>{" "}
          /{" "}
          <Link to="/settings/notifications" className="text-primary hover:underline">
            Notifications
          </Link>{" "}
          / Discord
        </p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight">Discord</h2>
        <p className="text-muted-foreground">
          Webhook delivery with plain text or built-in rich embeds.
        </p>
      </div>

      {message && (
        <div className="rounded-md border border-primary/20 bg-primary/10 px-4 py-2 text-sm text-primary">
          {message}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle>Webhook</CardTitle>
                  <CardDescription>
                    Server Settings → Integrations → Webhooks in Discord
                  </CardDescription>
                </div>
                <Badge variant={view?.discord_webhook_configured ? "success" : "secondary"}>
                  {view?.discord_webhook_configured ? "Saved" : "Missing"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Webhook URL</Label>
                <Input
                  type="password"
                  placeholder={
                    view?.discord_webhook_configured
                      ? "Webhook saved — paste new URL to replace"
                      : "https://discord.com/api/webhooks/…"
                  }
                  value={webhook}
                  onChange={(e) => setWebhook(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Bot display name</Label>
                <Input
                  placeholder="HomeLab DNS"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Message format</CardTitle>
              <CardDescription>Applies to all Discord alerts</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label
                  className={`cursor-pointer rounded-md border px-4 py-3 ${
                    format === "embed" ? "border-primary bg-primary/10" : "border-border"
                  }`}
                >
                  <input
                    type="radio"
                    className="mr-2"
                    checked={format === "embed"}
                    onChange={() => setFormat("embed")}
                  />
                  <span className="text-sm font-medium">Rich embed</span>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Built-in title, color, and fields per event
                  </p>
                </label>
                <label
                  className={`cursor-pointer rounded-md border px-4 py-3 ${
                    format === "plain" ? "border-primary bg-primary/10" : "border-border"
                  }`}
                >
                  <input
                    type="radio"
                    className="mr-2"
                    checked={format === "plain"}
                    onChange={() => setFormat("plain")}
                  />
                  <span className="text-sm font-medium">Plain text</span>
                  <p className="mt-1 text-xs text-muted-foreground">Simple emoji + message line</p>
                </label>
              </div>
              <div className="space-y-2">
                <Label>Accent color (informational embeds)</Label>
                <div className="flex gap-2">
                  <Input
                    type="color"
                    className="h-9 w-14 cursor-pointer p-1"
                    value={accent.match(/^#[0-9a-fA-F]{6}$/) ? accent : "#5865F2"}
                    onChange={(e) => setAccent(e.target.value)}
                  />
                  <Input value={accent} onChange={(e) => setAccent(e.target.value)} className="font-mono" />
                </div>
                <p className="text-xs text-muted-foreground">
                  Errors stay red and warnings amber; success stays green.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={save} disabled={saving}>
                  {saving ? "Saving…" : "Save"}
                </Button>
                <Button variant="outline" onClick={test} disabled={testing || saving}>
                  <Send className="mr-2 h-4 w-4" />
                  {testing ? "Sending…" : "Send test"}
                </Button>
                <Button variant="outline" asChild>
                  <Link to="/settings/notifications/discord/embed">
                    <Eye className="mr-2 h-4 w-4" />
                    Embed preview
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Live preview</CardTitle>
            <CardDescription>Sample “service created” with your current format</CardDescription>
          </CardHeader>
          <CardContent>
            <DiscordEmbedPreview
              username={username || "HomeLab DNS"}
              format={format}
              embed={
                previewEmbed
                  ? { ...previewEmbed, color: parseInt((accent || "#5865F2").replace("#", ""), 16) || previewEmbed.color }
                  : null
              }
              plainContent={previewPlain}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
