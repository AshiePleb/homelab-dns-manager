import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, VersionStatus } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export function VersionSettings() {
  const [version, setVersion] = useState<VersionStatus | null>(null);
  const [checking, setChecking] = useState(false);

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

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>App version</CardTitle>
          <CardDescription>
            Compared against the <code className="text-xs">latest</code> tag on Docker Hub.
          </CardDescription>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadVersion()} disabled={checking}>
          <RefreshCw className={`h-4 w-4 mr-2 ${checking ? "animate-spin" : ""}`} />
          Check
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {version ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span>
                Running <strong>v{version.version}</strong>
              </span>
              {version.update_available ? (
                <Badge variant="warning">Update available</Badge>
              ) : version.check_ok ? (
                <Badge variant="success">Up to date</Badge>
              ) : (
                <Badge variant="secondary">Could not verify</Badge>
              )}
            </div>
            {version.build_time && (
              <p className="text-muted-foreground">Built {formatDate(version.build_time)}</p>
            )}
            {version.latest_published_at && (
              <p className="text-muted-foreground">
                Docker Hub <code className="text-xs">{version.latest_tag}</code> published{" "}
                {formatDate(version.latest_published_at)}
              </p>
            )}
            {version.update_available && (
              <pre className="rounded-md bg-muted p-3 text-xs overflow-x-auto">
                {`cd /opt/homelab-dns-manager\ndocker compose pull\ndocker compose up -d`}
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
