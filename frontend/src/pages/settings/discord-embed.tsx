import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/context/auth";
import { DiscordEmbedPreview } from "@/components/discord-embed-preview";
import {
  DiscordEmbed,
  NOTIFY_EVENT_LABELS,
  NotifyEventId,
  OPS_EVENTS,
  SECURITY_EVENTS,
} from "@/lib/discord-embed";

const ALL_EVENTS = [...OPS_EVENTS, ...SECURITY_EVENTS];

export function DiscordEmbedPreviewPage() {
  const { isAdmin } = useAuth();
  const [event, setEvent] = useState<NotifyEventId>("service_created");
  const [username, setUsername] = useState("HomeLab DNS");
  const [format, setFormat] = useState<"plain" | "embed">("embed");
  const [accent, setAccent] = useState("#5865F2");
  const [embed, setEmbed] = useState<DiscordEmbed | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAdmin) return;
    api.getNotificationSettings().then((v) => {
      setUsername(v.discord_username || "HomeLab DNS");
      setFormat(v.discord_format === "plain" ? "plain" : "embed");
      setAccent(v.discord_accent_color || "#5865F2");
    });
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return;
    setLoading(true);
    api
      .previewDiscordEmbed(event, accent)
      .then((prev) => setEmbed(prev.embed))
      .catch(() => setEmbed(null))
      .finally(() => setLoading(false));
  }, [event, accent, isAdmin]);

  if (!isAdmin) return <Navigate to="/settings" replace />;

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
          /{" "}
          <Link to="/settings/notifications/discord" className="text-primary hover:underline">
            Discord
          </Link>{" "}
          / Embed preview
        </p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight">Embed preview</h2>
        <p className="text-muted-foreground">
          Live view of built-in embeds. Colors and fields are fixed per event; tweak username and accent
          on the Discord settings page.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Event</CardTitle>
            <CardDescription>Pick a sample alert</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Label htmlFor="event">Notification event</Label>
            <select
              id="event"
              className="flex h-9 w-full rounded-md border border-input bg-secondary/50 px-3 text-sm"
              value={event}
              onChange={(e) => setEvent(e.target.value as NotifyEventId)}
            >
              {ALL_EVENTS.map((ev) => (
                <option key={ev} value={ev}>
                  {NOTIFY_EVENT_LABELS[ev]}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground pt-2">
              Format: <strong className="text-foreground">{format}</strong>
              <br />
              Accent: <strong className="text-foreground font-mono">{accent}</strong>
            </p>
            <Link to="/settings/notifications/discord" className="text-sm text-primary hover:underline">
              Edit Discord settings →
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{NOTIFY_EVENT_LABELS[event]}</CardTitle>
            <CardDescription>How this event appears in Discord with your current settings</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            ) : (
              <DiscordEmbedPreview
                username={username}
                format={format}
                embed={embed}
                plainContent={embed?.description || undefined}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
