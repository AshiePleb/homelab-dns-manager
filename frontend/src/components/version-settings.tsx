import { useEffect, useState } from "react";
import { ArrowUpCircle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, VersionStatus } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuth } from "@/context/auth";

function formatVersionTag(version: string) {
  if (!version || version === "dev") return "dev build";
  if (version === "latest") return "latest";
  return version.startsWith("v") ? version : `v${version}`;
}

async function waitForAppBack(timeoutMs = 120_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      if (res.ok) return true;
    } catch {
      // still restarting
    }
  }
  return false;
}

export function VersionSettings() {
  const { isAdmin } = useAuth();
  const [version, setVersion] = useState<VersionStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [updateMsg, setUpdateMsg] = useState("");

  const loadVersion = async () => {
    setChecking(true);
    try {
      setVersion(await api.getVersionStatus());
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    void loadVersion();
  }, []);

  const latestLabel = version?.latest_version || version?.latest_tag;

  const handleUpdate = async () => {
    if (!isAdmin || updating) return;
    const target = latestLabel ? formatVersionTag(latestLabel) : "latest";
    if (
      !confirm(
        `Update to ${target} now?\n\nThe app will pull the new Docker image and restart briefly (about 15–60 seconds). Your data is kept.`
      )
    ) {
      return;
    }
    setUpdating(true);
    setUpdateMsg("Pulling image…");
    try {
      const result = await api.updateApp(false);
      setUpdateMsg(result.message || "Restarting… waiting for the app to come back");
      const ok = await waitForAppBack();
      if (ok) {
        setUpdateMsg("Update complete — reloading…");
        window.location.reload();
      } else {
        setUpdateMsg("Restart is taking longer than expected. Refresh the page in a minute.");
        setUpdating(false);
      }
    } catch (e) {
      // Request may fail if the container dies before the response finishes — still wait for health
      const msg = e instanceof Error ? e.message : "";
      if (/failed to fetch|network|abort/i.test(msg) || !msg) {
        setUpdateMsg("Restarting… waiting for the app to come back");
        const ok = await waitForAppBack();
        if (ok) {
          window.location.reload();
          return;
        }
      }
      setUpdateMsg(msg || "Update failed");
      setUpdating(false);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>App version</CardTitle>
          <CardDescription>
            Compares this server&apos;s version with the newest semver tag on Docker Hub (e.g.{" "}
            <code className="text-xs">v1.1.0</code>).
          </CardDescription>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadVersion()} disabled={checking || updating}>
          <RefreshCw className={`h-4 w-4 mr-2 ${checking ? "animate-spin" : ""}`} />
          Check
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {version ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span>
                Running <strong>{formatVersionTag(version.version)}</strong>
              </span>
              {version.update_available ? (
                <Badge variant="warning">
                  Update to {formatVersionTag(latestLabel || "")}
                </Badge>
              ) : version.check_ok ? (
                <Badge variant="success">Up to date</Badge>
              ) : (
                <Badge variant="secondary">Could not verify</Badge>
              )}
            </div>
            {latestLabel && (
              <p className="text-muted-foreground">
                Latest on Docker Hub: <strong>{formatVersionTag(latestLabel)}</strong>
              </p>
            )}
            {version.build_time && (
              <p className="text-muted-foreground">Built {formatDate(version.build_time)}</p>
            )}
            {version.latest_published_at && (
              <p className="text-muted-foreground">
                Published {formatDate(version.latest_published_at)}
              </p>
            )}

            {isAdmin && version.update_available && (
              <div className="pt-1">
                <Button type="button" onClick={() => void handleUpdate()} disabled={updating}>
                  <ArrowUpCircle className={`h-4 w-4 mr-2 ${updating ? "animate-pulse" : ""}`} />
                  {updating ? "Updating…" : `Update to ${formatVersionTag(latestLabel || "latest")}`}
                </Button>
                <p className="text-xs text-muted-foreground mt-2">
                  Pulls the new image and restarts this container. Data and settings are kept on the volume.
                </p>
              </div>
            )}

            {updateMsg && (
              <p className={`text-sm ${updating ? "text-warning" : "text-muted-foreground"}`}>{updateMsg}</p>
            )}

            {!version.update_available && (
              <pre className="rounded-md bg-muted p-3 text-xs overflow-x-auto opacity-70">
                {`# Manual update (SSH)\ncd /opt/homelab-dns-manager\ndocker compose pull\ndocker compose up -d`}
              </pre>
            )}
          </>
        ) : (
          <p className="text-muted-foreground">{checking ? "Checking…" : "—"}</p>
        )}
      </CardContent>
    </Card>
  );
}
