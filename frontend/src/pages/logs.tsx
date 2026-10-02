import { Fragment, useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api, ActivityLog } from "@/lib/api";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";

const levels = ["all", "info", "warning", "error", "success"] as const;
const CATEGORIES = [
  "all",
  "auth",
  "users",
  "api_keys",
  "dns",
  "service",
  "ssl",
  "ddns",
  "cloudflare",
  "settings",
  "system",
  "backup",
  "npm",
  "docker",
] as const;

const levelVariant = {
  info: "secondary" as const,
  warning: "warning" as const,
  error: "destructive" as const,
  success: "success" as const,
};

const PAGE = 100;

export function LogsPage() {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [level, setLevel] = useState<string>("all");
  const [category, setCategory] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const load = async (offset = 0, append = false) => {
    if (offset === 0) setLoading(true);
    else setLoadingMore(true);
    try {
      const rows = await api.getLogs({
        level: level === "all" ? undefined : level,
        category: category === "all" ? undefined : category,
        limit: PAGE,
        offset,
      });
      setLogs((prev) => (append ? [...prev, ...rows] : rows));
      setHasMore(rows.length >= PAGE);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    setExpanded({});
    void load(0, false);
  }, [level, category]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Activity Logs</h2>
          <p className="text-muted-foreground">Audit trail of ops and security events</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex flex-wrap justify-end gap-1">
            {levels.map((l) => (
              <Button
                key={l}
                variant={level === l ? "default" : "outline"}
                size="sm"
                onClick={() => setLevel(l)}
                className="capitalize"
              >
                {l}
              </Button>
            ))}
          </div>
          <select
            className="flex h-8 rounded-md border border-input bg-secondary/50 px-3 text-xs"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c === "all" ? "All categories" : c}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <>
          <DataTable
            columns={[
              { key: "level", label: "Level" },
              { key: "category", label: "Category" },
              { key: "message", label: "Message" },
              { key: "actor", label: "Actor" },
              { key: "time", label: "Timestamp" },
            ]}
            isEmpty={logs.length === 0}
            emptyMessage="No activity logs yet"
          >
            {logs.map((log) => {
              const open = expanded[log.id];
              const hasDetails = Boolean(log.details && Object.keys(log.details).length);
              return (
                <Fragment key={log.id}>
                  <TableRow>
                    <TableCell>
                      <Badge variant={levelVariant[log.level]}>{log.level}</Badge>
                    </TableCell>
                    <TableCell className="text-sm capitalize text-muted-foreground">{log.category}</TableCell>
                    <TableCell className="text-sm">
                      <button
                        type="button"
                        className="flex items-start gap-1 text-left"
                        disabled={!hasDetails}
                        onClick={() => setExpanded((e) => ({ ...e, [log.id]: !e[log.id] }))}
                      >
                        {hasDetails ? (
                          open ? (
                            <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          )
                        ) : (
                          <span className="inline-block w-3.5" />
                        )}
                        <span>{log.message}</span>
                      </button>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {log.username || "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {formatDate(log.created_at)}
                    </TableCell>
                  </TableRow>
                  {open && hasDetails && (
                    <TableRow>
                      <TableCell colSpan={5} className="bg-secondary/20">
                        <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-muted-foreground">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
          </DataTable>
          {hasMore && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                disabled={loadingMore}
                onClick={() => void load(logs.length, true)}
              >
                {loadingMore ? "Loading…" : "Load more"}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
