import { useEffect, useState } from "react";
import { Play, Square, RotateCcw, FileText } from "lucide-react";
import { api, Container } from "@/lib/api";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusDot } from "@/components/ui/status-dot";
import { useAuth } from "@/context/auth";

export function ContainersPage() {
  const [containers, setContainers] = useState<Container[]>([]);
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<{ id: string; text: string } | null>(null);
  const { isOperator } = useAuth();

  const load = async () => {
    try {
      setContainers(await api.getContainers());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (id: string, action: string) => {
    try {
      await api.containerAction(id, action);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Action failed");
    }
  };

  const viewLogs = async (id: string) => {
    try {
      const result = await api.getContainerLogs(id);
      setLogs({ id, text: result.logs });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to fetch logs");
    }
  };

  const statusVariant = (status: string) => {
    if (status === "running") return "success";
    if (status === "exited") return "secondary";
    return "warning";
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Containers</h2>
        <p className="text-muted-foreground">Docker container status and management</p>
      </div>

      {logs && (
        <div className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <span className="text-sm font-medium">Logs: {logs.id}</span>
            <Button variant="ghost" size="sm" onClick={() => setLogs(null)}>Close</Button>
          </div>
          <pre className="max-h-96 overflow-auto p-4 text-xs font-mono text-muted-foreground scrollbar-thin">
            {logs.text}
          </pre>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <DataTable
          columns={[
            { key: "name", label: "Container Name" },
            { key: "image", label: "Image" },
            { key: "status", label: "Status" },
            { key: "ports", label: "Ports" },
            { key: "uptime", label: "Uptime" },
            { key: "actions", label: "Actions", className: "text-right" },
          ]}
          isEmpty={containers.length === 0}
          emptyMessage="No containers found. Ensure Docker socket is mounted."
        >
          {containers.map((c) => (
            <TableRow key={c.id}>
              <TableCell>
                <div className="flex items-center gap-2 font-medium">{c.name}</div>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">{c.image}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <StatusDot status={c.status} />
                  <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
                </div>
              </TableCell>
              <TableCell className="text-xs font-mono text-muted-foreground">
                {c.ports.length ? c.ports.join(", ") : "—"}
              </TableCell>
              <TableCell className="text-sm">{c.uptime || "—"}</TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" size="sm" onClick={() => viewLogs(c.id)} title="Logs">
                    <FileText className="h-4 w-4" />
                  </Button>
                  {isOperator && c.status !== "running" && (
                    <Button variant="ghost" size="sm" onClick={() => handleAction(c.id, "start")} title="Start">
                      <Play className="h-4 w-4 text-success" />
                    </Button>
                  )}
                  {isOperator && c.status === "running" && (
                    <Button variant="ghost" size="sm" onClick={() => handleAction(c.id, "stop")} title="Stop">
                      <Square className="h-4 w-4" />
                    </Button>
                  )}
                  {isOperator && (
                    <Button variant="ghost" size="sm" onClick={() => handleAction(c.id, "restart")} title="Restart">
                      <RotateCcw className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </DataTable>
      )}
    </div>
  );
}
