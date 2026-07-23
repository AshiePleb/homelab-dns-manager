import { useEffect, useState, useCallback } from "react";
import {
  Globe,
  FileText,
  Layers,
  Activity,
  Wifi,
  RefreshCw,
  CheckCircle2,
  XCircle,
  MinusCircle,
  Clock,
  Server,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api, DashboardStats, ActivityLog, DDNSStatus, ServiceHealthRow, HealthHistoryPoint } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, formatRelative, cn } from "@/lib/utils";
import { useWebSocket } from "@/hooks/use-websocket";
import { useAuth } from "@/context/auth";

const levelVariant = {
  info: "secondary" as const,
  warning: "warning" as const,
  error: "destructive" as const,
  success: "success" as const,
};

const overallVariant = {
  healthy: "success" as const,
  degraded: "warning" as const,
  down: "destructive" as const,
  inactive: "secondary" as const,
};

function CheckCell({ ok, message }: { ok: boolean; message: string }) {
  return (
    <div className="flex items-center gap-2" title={message}>
      {ok ? (
        <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
      ) : (
        <XCircle className="h-4 w-4 text-destructive shrink-0" />
      )}
      <span className="text-xs text-muted-foreground truncate max-w-[140px]">{message}</span>
    </div>
  );
}

export function DashboardPage() {
  const { isOperator } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [ddns, setDdns] = useState<DDNSStatus | null>(null);
  const [health, setHealth] = useState<ServiceHealthRow[]>([]);
  const [healthHistory, setHealthHistory] = useState<HealthHistoryPoint[]>([]);
  const [activity, setActivity] = useState<ActivityLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [healthLoading, setHealthLoading] = useState(true);
  const [ddnsChecking, setDdnsChecking] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, a, d] = await Promise.all([
        api.getDashboardStats(),
        api.getRecentActivity(8),
        api.getDDNSStatus(),
      ]);
      setStats(s);
      setActivity(a);
      setDdns(d);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const [rows, history] = await Promise.all([
        api.getDashboardHealth(),
        api.getHealthHistory(undefined, 24),
      ]);
      setHealth(rows);
      setHealthHistory(history);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadHealth();
    const interval = setInterval(() => {
      load();
      loadHealth();
    }, 60000);
    return () => clearInterval(interval);
  }, [load, loadHealth]);

  useWebSocket((event) => {
    if (event === "ip_changed") load();
  });

  const runDdnsCheck = async () => {
    setDdnsChecking(true);
    try {
      await api.runDDNSCheck();
      await load();
    } finally {
      setDdnsChecking(false);
    }
  };

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const healthyCount = health.filter((r) => r.overall === "healthy").length;
  const degradedCount = health.filter((r) => r.overall === "degraded" || r.overall === "down").length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">Overview of your homelab DNS and services</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Current Public IP"
          value={stats?.current_public_ip || "—"}
          icon={<Wifi className="h-5 w-5" />}
        />
        <StatCard
          title="Last IP Change"
          value={formatRelative(stats?.last_ip_change)}
          subtitle={formatDate(stats?.last_ip_change)}
        />
        <StatCard
          title="Cloudflare"
          value={stats?.cloudflare_status === "connected" ? "Connected" : "Not configured"}
          status={stats?.cloudflare_status === "connected" ? "connected" : "not_configured"}
          icon={<Globe className="h-5 w-5" />}
        />
        <StatCard
          title="System Health"
          value={stats?.system_health === "healthy" ? "Healthy" : "Degraded"}
          status={stats?.system_health}
          icon={<Activity className="h-5 w-5" />}
        />
        <StatCard
          title="DNS Records"
          value={stats?.dns_records_managed ?? 0}
          subtitle="App-managed"
          icon={<FileText className="h-5 w-5" />}
        />
        <StatCard
          title="Proxy Services"
          value={stats?.proxy_hosts ?? 0}
          icon={<Layers className="h-5 w-5" />}
        />
        <StatCard
          title="DDNS Hostnames"
          value={ddns?.managed_count ?? 0}
          subtitle={`Every ${ddns?.interval_minutes ?? "—"} min`}
          icon={<Server className="h-5 w-5" />}
        />
        <StatCard
          title="Next DDNS Check"
          value={formatRelative(ddns?.next_check)}
          subtitle={formatDate(ddns?.next_check)}
          icon={<Clock className="h-5 w-5" />}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3 rounded-lg border border-border bg-card">
          <div className="border-b border-border px-6 py-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className="font-semibold">DDNS Scheduler</h3>
              <p className="text-xs text-muted-foreground mt-1">
                Stored IP {ddns?.current_ip || "—"} · last check {formatRelative(ddns?.last_check)}
              </p>
            </div>
            {isOperator && (
              <Button onClick={runDdnsCheck} disabled={ddnsChecking} className="gap-2">
                <RefreshCw className={cn("h-4 w-4", ddnsChecking && "animate-spin")} />
                {ddnsChecking ? "Checking…" : "Check now"}
              </Button>
            )}
          </div>
          {(ddns?.managed_hostnames?.length ?? 0) > 0 ? (
            <div className="px-6 py-4">
              <div className="flex flex-wrap gap-2">
                {ddns!.managed_hostnames.map((host) => (
                  <span
                    key={host}
                    className="rounded-md bg-primary/10 px-2.5 py-1 font-mono text-xs text-primary"
                  >
                    {host}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <p className="px-6 py-6 text-sm text-muted-foreground">
              No managed hostnames yet. Add services under Add Service.
            </p>
          )}
        </div>

        <div className="lg:col-span-2 rounded-lg border border-border bg-card flex flex-col">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold">Recent Activity</h3>
          </div>
          <div className="divide-y divide-border/50 flex-1 overflow-y-auto max-h-64 lg:max-h-none">
            {activity.length === 0 ? (
              <p className="px-6 py-8 text-center text-muted-foreground text-sm">No recent activity</p>
            ) : (
              activity.map((log) => (
                <div key={log.id} className="flex items-start gap-3 px-6 py-3">
                  <Badge variant={levelVariant[log.level]} className="shrink-0 mt-0.5">
                    {log.level}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm leading-snug line-clamp-2">{log.message}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatRelative(log.created_at)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="border-b border-border px-6 py-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="font-semibold">Service Health</h3>
            <p className="text-xs text-muted-foreground mt-1">
              {healthLoading
                ? "Checking services…"
                : health.length
                  ? `${healthyCount} healthy · ${degradedCount} need attention · SSL details on `
                  : "DNS, HTTPS, and backend connectivity · SSL on "}
              <Link to="/caddy" className="text-primary hover:underline">
                Caddy Proxy
              </Link>
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={loadHealth} disabled={healthLoading} className="gap-2">
            <RefreshCw className={cn("h-3.5 w-3.5", healthLoading && "animate-spin")} />
            Refresh
          </Button>
        </div>
        {healthLoading && health.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : health.length === 0 ? (
          <p className="px-6 py-8 text-center text-muted-foreground text-sm">
            No proxy services yet. Add one under Add Service.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-left text-xs text-muted-foreground">
                  <th className="px-6 py-3 font-medium">Service</th>
                  <th className="px-4 py-3 font-medium">DNS</th>
                  <th className="px-4 py-3 font-medium">HTTPS</th>
                  <th className="px-4 py-3 font-medium">Backend</th>
                  <th className="px-4 py-3 font-medium">DDNS sync</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {health.map((row) => (
                  <tr key={row.id} className="hover:bg-muted/20">
                    <td className="px-6 py-3">
                      <p className="font-mono text-xs font-medium">{row.hostname}</p>
                      <p className="text-xs text-muted-foreground">
                        {row.forward_host}:{row.forward_port}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <CheckCell ok={row.dns_ok} message={row.dns_message} />
                    </td>
                    <td className="px-4 py-3">
                      <CheckCell ok={row.https_ok} message={row.https_message} />
                    </td>
                    <td className="px-4 py-3">
                      <CheckCell ok={row.port_ok} message={row.port_message} />
                    </td>
                    <td className="px-4 py-3">
                      {row.ddns_managed ? (
                        <CheckCell
                          ok={!!row.ddns_last_sync}
                          message={row.ddns_last_sync ? formatRelative(row.ddns_last_sync) : "Never synced"}
                        />
                      ) : (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <MinusCircle className="h-4 w-4 shrink-0" />
                          Not managed
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      <Badge variant={overallVariant[row.overall]}>{row.overall}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {healthHistory.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold">Health history (24h)</h3>
            <p className="text-xs text-muted-foreground mt-1">Snapshots every 15 minutes — retained 30 days</p>
          </div>
          <div className="overflow-x-auto max-h-56 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-left text-xs text-muted-foreground">
                  <th className="px-6 py-2 font-medium">Time</th>
                  <th className="px-4 py-2 font-medium">Service</th>
                  <th className="px-4 py-2 font-medium">DNS</th>
                  <th className="px-4 py-2 font-medium">HTTPS</th>
                  <th className="px-4 py-2 font-medium">Port</th>
                  <th className="px-6 py-2 font-medium">Overall</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {[...healthHistory].reverse().slice(0, 40).map((h, i) => (
                  <tr key={`${h.hostname}-${h.checked_at}-${i}`}>
                    <td className="px-6 py-2 text-xs text-muted-foreground">{formatRelative(h.checked_at)}</td>
                    <td className="px-4 py-2 font-mono text-xs">{h.hostname}</td>
                    <td className="px-4 py-2">{h.dns_ok ? "✓" : "✗"}</td>
                    <td className="px-4 py-2">{h.https_ok ? "✓" : "✗"}</td>
                    <td className="px-4 py-2">{h.port_ok ? "✓" : "✗"}</td>
                    <td className="px-6 py-2">
                      <Badge variant={overallVariant[h.overall as keyof typeof overallVariant] || "secondary"}>
                        {h.overall}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
