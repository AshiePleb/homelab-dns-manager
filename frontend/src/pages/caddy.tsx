import { useEffect, useState } from "react";
import { RefreshCw, ExternalLink, ChevronDown, ChevronUp, Shield, Pencil, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api, CaddyHost, CaddyStatus, ServiceHealthRow } from "@/lib/api";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SslCertificatesTable } from "@/components/ssl-certificates-table";
import { formatDate } from "@/lib/utils";
import { useAuth } from "@/context/auth";

const sslVariant = {
  none: "secondary" as const,
  active: "success" as const,
  pending: "warning" as const,
  warning: "warning" as const,
  error: "destructive" as const,
};

const sslStatusLabel = {
  none: "No SSL",
  active: "Working",
  pending: "Pending",
  warning: "Issue",
  error: "Error",
};

function StatSkeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-secondary/80 ${className || "h-6 w-24"}`} />;
}

export function CaddyPage() {
  const { isOperator } = useAuth();
  const [status, setStatus] = useState<CaddyStatus | null>(null);
  const [hosts, setHosts] = useState<CaddyHost[]>([]);
  const [config, setConfig] = useState("");
  const [configPath, setConfigPath] = useState("");
  const [showConfig, setShowConfig] = useState(false);
  const [sslHealth, setSslHealth] = useState<ServiceHealthRow[]>([]);
  const [sslLoading, setSslLoading] = useState(true);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [message, setMessage] = useState("");
  const [editHost, setEditHost] = useState<CaddyHost | null>(null);
  const [editTarget, setEditTarget] = useState("");
  const [editSkipPort, setEditSkipPort] = useState(false);
  const [editSaving, setEditSaving] = useState(false);

  const load = async () => {
    const isRefresh = status !== null;
    if (isRefresh) setRefreshing(true);
    setSslLoading(true);
    try {
      const [s, h, c, health] = await Promise.all([
        api.getCaddyStatus(),
        api.getCaddyHosts(),
        api.getCaddyConfig(),
        api.getDashboardHealth(),
      ]);
      setStatus(s);
      setHosts(h);
      setConfig(c.content);
      setConfigPath(c.path);
      setSslHealth(health);
    } finally {
      setInitialLoading(false);
      setRefreshing(false);
      setSslLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleReload = async () => {
    setRestarting(true);
    setMessage("");
    try {
      const result = await api.reloadCaddy();
      setMessage(
        result.reloaded
          ? `Caddy reloaded — ${result.site_count} site(s) active`
          : "Reload failed — check Docker socket and homelab-caddy container"
      );
      // Container is briefly down while restarting — wait before re-checking status
      await new Promise((r) => setTimeout(r, 2500));
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Reload failed");
    } finally {
      setRestarting(false);
    }
  };

  const openEdit = (h: CaddyHost) => {
    setEditHost(h);
    setEditTarget(`${h.forward_host}:${h.forward_port}`);
    setEditSkipPort(false);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editHost || editSaving) return;
    setEditSaving(true);
    setMessage("");
    try {
      const result = await api.updateService(editHost.id, {
        target: editTarget.trim(),
        skip_port_check: editSkipPort,
      });
      setEditHost(null);
      setMessage(
        result.changed
          ? `Updated ${result.hostname} → ${result.forward_host}:${result.forward_port}`
          : "No change — target already matches"
      );
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to update target");
    } finally {
      setEditSaving(false);
    }
  };

  const busy = initialLoading || refreshing || restarting;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Caddy Proxy</h2>
          <p className="text-muted-foreground">
            Built-in reverse proxy and automatic HTTPS (Let&apos;s Encrypt / ZeroSSL). Add services via{" "}
            <Link to="/services" className="text-primary hover:underline">
              Add Service
            </Link>
            .
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={load} disabled={busy}>
            <RefreshCw className={`h-4 w-4 mr-2 ${busy ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          {isOperator && (
            <Button onClick={handleReload} disabled={busy}>
              {restarting ? "Reloading…" : "Sync & reload Caddy"}
            </Button>
          )}
        </div>
      </div>

      {message && (
        <div className="rounded-md bg-primary/10 border border-primary/20 px-4 py-2 text-sm text-primary">
          {message}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Container</CardDescription>
            <CardTitle className="text-lg">{status?.container_name || "homelab-caddy"}</CardTitle>
          </CardHeader>
          <CardContent>
            {restarting ? (
              <Badge variant="warning">Restarting…</Badge>
            ) : !status ? (
              <StatSkeleton className="h-6 w-20" />
            ) : (
              <Badge variant={status.container_running ? "success" : "destructive"}>
                {status.container_running ? "Running" : status.container_status}
              </Badge>
            )}
            {status?.container_message && !status.container_running && !restarting && (
              <p className="text-xs text-muted-foreground mt-2">{status.container_message}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active sites</CardDescription>
            <CardTitle className="text-lg">
              {!status ? <StatSkeleton className="h-7 w-8 inline-block" /> : status.site_count}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {!status ? (
                <StatSkeleton className="h-4 w-40" />
              ) : (
                `${status.total_hosts} total proxy host(s) in database`
              )}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>HTTPS</CardDescription>
            <CardTitle className="text-lg">ACME / TLS</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground truncate" title={status?.acme_email || undefined}>
              ACME email: {status?.acme_email || "Not set (ACME_EMAIL in .env)"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Caddyfile</CardDescription>
            <CardTitle className="text-lg">
              {!status ? <StatSkeleton className="h-7 w-28 inline-block" /> : status.caddyfile_present ? "Present" : "Missing"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground font-mono">{configPath || "/data/caddy/Caddyfile"}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Proxy hosts</CardTitle>
          <CardDescription>
            Each site terminates HTTPS on ports 80/443 and forwards to your internal target
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={[
              { key: "hostname", label: "Hostname" },
              { key: "upstream", label: "Upstream" },
              { key: "ssl", label: "SSL" },
              { key: "port", label: "Backend port" },
              { key: "status", label: "Enabled" },
              { key: "updated", label: "Updated" },
              { key: "actions", label: "", className: "text-right" },
            ]}
            isEmpty={!initialLoading && hosts.length === 0}
            emptyMessage="No Caddy proxy hosts yet — add a service to get started"
          >
            {initialLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                  <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                </TableCell>
              </TableRow>
            ) : (
              hosts.map((h) => (
              <TableRow key={h.id}>
                <TableCell className="font-medium">{h.hostname}</TableCell>
                <TableCell className="font-mono text-xs">
                  {h.forward_host}:{h.forward_port}
                </TableCell>
                <TableCell>
                  <div className="space-y-1" title={h.ssl_message}>
                    <Badge variant={sslVariant[h.ssl_status] || "secondary"}>
                      {sslStatusLabel[h.ssl_status] || h.ssl_status}
                    </Badge>
                    <p className="text-xs text-muted-foreground">{h.ssl_label}</p>
                  </div>
                </TableCell>
                <TableCell>
                  {h.port_reachable == null ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    <Badge variant={h.port_reachable ? "success" : "destructive"}>
                      {h.port_reachable ? "Reachable" : "Unreachable"}
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={h.enabled ? "success" : "secondary"}>
                    {h.enabled ? "Yes" : "Disabled"}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">{formatDate(h.updated_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    {isOperator && (
                      <Button variant="ghost" size="sm" onClick={() => openEdit(h)} title="Edit upstream">
                        <Pencil className="h-4 w-4" />
                      </Button>
                    )}
                    <a
                      href={`https://${h.hostname}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center justify-center h-8 w-8 text-primary hover:opacity-80"
                      title="Open in browser"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                </TableCell>
              </TableRow>
            ))
            )}
          </DataTable>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            SSL Certificates
          </CardTitle>
          <CardDescription>
            Certificate expiry from Caddy on-disk store — automatic alerts at 14 days remaining
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0 pb-0">
          <SslCertificatesTable
            rows={sslHealth}
            loading={sslLoading || initialLoading}
            onRefresh={load}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="cursor-pointer" onClick={() => setShowConfig(!showConfig)}>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Caddyfile</CardTitle>
              <CardDescription>Generated config — read-only; managed by the app</CardDescription>
            </div>
            {showConfig ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
          </div>
        </CardHeader>
        {showConfig && (
          <CardContent>
            <pre className="overflow-x-auto rounded-md border border-border bg-secondary/30 p-4 text-xs font-mono whitespace-pre-wrap">
              {config || "# No Caddyfile generated yet"}
            </pre>
          </CardContent>
        )}
      </Card>

      <p className="text-xs text-muted-foreground">
        Router must forward <strong>80</strong> and <strong>443</strong> to this server. DNS records should be
        grey-cloud (DNS only) so Caddy can obtain certificates. Manage services on{" "}
        <Link to="/records" className="text-primary hover:underline">
          DNS Records
        </Link>
        .
      </p>

      {editHost && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => !editSaving && setEditHost(null)} />
          <div className="relative w-full max-w-md rounded-lg border border-border bg-background p-5 shadow-xl space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">Edit upstream</h3>
                <p className="text-xs text-muted-foreground font-mono mt-1">{editHost.hostname}</p>
              </div>
              <Button variant="ghost" size="icon" disabled={editSaving} onClick={() => setEditHost(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div className="space-y-2">
                <Label>IP:port</Label>
                <Input
                  className="font-mono"
                  value={editTarget}
                  onChange={(e) => setEditTarget(e.target.value)}
                  placeholder="10.10.10.4:8932"
                  required
                  disabled={editSaving}
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={editSkipPort}
                  onChange={(e) => setEditSkipPort(e.target.checked)}
                  disabled={editSaving}
                />
                Skip port check
              </label>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="ghost" disabled={editSaving} onClick={() => setEditHost(null)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={editSaving || !editTarget.trim()}>
                  {editSaving ? "Saving…" : "Save & reload Caddy"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
