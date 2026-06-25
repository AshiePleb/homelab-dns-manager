import { useEffect, useState } from "react";
import { api, ActivityLog } from "@/lib/api";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";

const levels = ["all", "info", "warning", "error", "success"] as const;

const levelVariant = {
  info: "secondary" as const,
  warning: "warning" as const,
  error: "destructive" as const,
  success: "success" as const,
};

export function LogsPage() {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setLogs(await api.getLogs(filter === "all" ? undefined : filter, 200));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Activity Logs</h2>
          <p className="text-muted-foreground">Audit trail of all system events</p>
        </div>
        <div className="flex gap-1">
          {levels.map((l) => (
            <Button
              key={l}
              variant={filter === l ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(l)}
              className="capitalize"
            >
              {l}
            </Button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <DataTable
          columns={[
            { key: "level", label: "Level" },
            { key: "category", label: "Category" },
            { key: "message", label: "Message" },
            { key: "time", label: "Timestamp" },
          ]}
          isEmpty={logs.length === 0}
          emptyMessage="No activity logs yet"
        >
          {logs.map((log) => (
            <TableRow key={log.id}>
              <TableCell>
                <Badge variant={levelVariant[log.level]}>{log.level}</Badge>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground capitalize">{log.category}</TableCell>
              <TableCell className="text-sm">{log.message}</TableCell>
              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                {formatDate(log.created_at)}
              </TableCell>
            </TableRow>
          ))}
        </DataTable>
      )}
    </div>
  );
}
