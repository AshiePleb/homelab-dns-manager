import { RefreshCw } from "lucide-react";
import { ServiceHealthRow } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDateOnly, cn } from "@/lib/utils";

const sslExpiryVariant = (days: number | null) => {
  if (days === null) return "secondary" as const;
  if (days <= 7) return "destructive" as const;
  if (days <= 14) return "warning" as const;
  return "success" as const;
};

interface SslCertificatesTableProps {
  rows: ServiceHealthRow[];
  loading?: boolean;
  onRefresh?: () => void;
  compact?: boolean;
}

export function SslCertificatesTable({
  rows,
  loading,
  onRefresh,
  compact,
}: SslCertificatesTableProps) {
  const sslRows = [...rows]
    .filter((r) => r.enabled)
    .sort((a, b) => {
      if (a.ssl_days_remaining == null && b.ssl_days_remaining == null) return 0;
      if (a.ssl_days_remaining == null) return 1;
      if (b.ssl_days_remaining == null) return -1;
      return a.ssl_days_remaining - b.ssl_days_remaining;
    });

  const expiringSoon = sslRows.filter(
    (r) => r.ssl_days_remaining != null && r.ssl_days_remaining <= 14
  ).length;

  if (loading && sslRows.length === 0) {
    return (
      <div className="flex items-center justify-center py-10">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (sslRows.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground text-sm">
        No proxy services with SSL yet. Add a service to get started.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {!compact && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 pt-2">
          <p className="text-xs text-muted-foreground">
            {expiringSoon > 0
              ? `${expiringSoon} certificate(s) expiring within 14 days — alerts are sent automatically`
              : "All certificates valid — expiry alerts fire at 14 days remaining"}
          </p>
          {onRefresh && (
            <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading} className="gap-2">
              <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
              Refresh
            </Button>
          )}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30 text-left text-xs text-muted-foreground">
              <th className="px-6 py-3 font-medium">Hostname</th>
              <th className="px-4 py-3 font-medium">Provider</th>
              <th className="px-4 py-3 font-medium">Expires</th>
              <th className="px-4 py-3 font-medium">Days left</th>
              <th className="px-6 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {sslRows.map((row) => (
              <tr key={row.id} className="hover:bg-muted/20">
                <td className="px-6 py-3 font-mono text-xs">{row.hostname}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {row.ssl_issuer ? `Caddy · ${row.ssl_issuer}` : row.ssl_status === "none" ? "—" : "Caddy"}
                </td>
                <td className="px-4 py-3 text-xs">
                  {row.ssl_expires_at ? formatDateOnly(row.ssl_expires_at) : "—"}
                </td>
                <td className="px-4 py-3">
                  {row.ssl_days_remaining != null ? (
                    <span
                      className={cn(
                        "text-xs font-medium",
                        row.ssl_days_remaining <= 7 && "text-destructive",
                        row.ssl_days_remaining > 7 && row.ssl_days_remaining <= 14 && "text-warning",
                        row.ssl_days_remaining > 14 && "text-success"
                      )}
                    >
                      {row.ssl_days_remaining}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-6 py-3">
                  {row.ssl_days_remaining != null ? (
                    <Badge variant={sslExpiryVariant(row.ssl_days_remaining)}>
                      {row.ssl_days_remaining <= 14 ? "Expiring soon" : "Valid"}
                    </Badge>
                  ) : (
                    <Badge variant="secondary">{row.ssl_status}</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
