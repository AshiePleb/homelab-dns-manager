import { useEffect, useState } from "react";
import { Plus, RefreshCw, Trash2, Shield } from "lucide-react";
import { api, NPMHost } from "@/lib/api";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate } from "@/lib/utils";
import { useAuth } from "@/context/auth";

export function NPMPage() {
  const [hosts, setHosts] = useState<NPMHost[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const { isOperator } = useAuth();

  const [form, setForm] = useState({
    domain_names: "",
    forward_host: "",
    forward_port: 80,
    ssl_enabled: false,
    create_dns: false,
    dns_proxied: true,
  });

  const load = async () => {
    setLoading(true);
    try {
      setHosts(await api.getNPMHosts());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncNPM();
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createNPMHost({
        domain_names: form.domain_names.split(",").map((s) => s.trim()).filter(Boolean),
        forward_host: form.forward_host,
        forward_port: form.forward_port,
        ssl_enabled: form.ssl_enabled,
        create_dns: form.create_dns,
        dns_proxied: form.dns_proxied,
      });
      setShowAdd(false);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this proxy host?")) return;
    try {
      await api.deleteNPMHost(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Nginx Proxy Manager</h2>
          <p className="text-muted-foreground">Manage reverse proxy hosts and SSL certificates</p>
        </div>
        <div className="flex gap-2">
          {isOperator && (
            <Button variant="outline" onClick={handleSync} disabled={syncing}>
              <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? "animate-spin" : ""}`} />
              Sync
            </Button>
          )}
          {isOperator && (
            <Button onClick={() => setShowAdd(!showAdd)}>
              <Plus className="h-4 w-4 mr-2" /> Add Host
            </Button>
          )}
        </div>
      </div>

      {showAdd && isOperator && (
        <form onSubmit={handleCreate} className="rounded-lg border border-border bg-card p-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Domain Names (comma-separated)</Label>
              <Input value={form.domain_names} onChange={(e) => setForm({ ...form, domain_names: e.target.value })} placeholder="home.example.com" required />
            </div>
            <div className="space-y-2">
              <Label>Forward Host</Label>
              <Input value={form.forward_host} onChange={(e) => setForm({ ...form, forward_host: e.target.value })} placeholder="10.10.10.1" required />
            </div>
            <div className="space-y-2">
              <Label>Forward Port</Label>
              <Input type="number" value={form.forward_port} onChange={(e) => setForm({ ...form, forward_port: Number(e.target.value) })} />
            </div>
            <div className="flex flex-col gap-2 pt-6">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.ssl_enabled} onChange={(e) => setForm({ ...form, ssl_enabled: e.target.checked })} />
                Enable SSL
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.create_dns} onChange={(e) => setForm({ ...form, create_dns: e.target.checked })} />
                Create DNS record
              </label>
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="submit">Create Host</Button>
            <Button type="button" variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <DataTable
          columns={[
            { key: "domains", label: "Domains" },
            { key: "mapping", label: "Mapping" },
            { key: "ssl", label: "SSL" },
            { key: "synced", label: "Last Synced" },
            { key: "actions", label: "Actions", className: "text-right" },
          ]}
          isEmpty={hosts.length === 0}
          emptyMessage="No proxy hosts. Configure NPM in Settings and sync."
        >
          {hosts.map((h) => (
            <TableRow key={h.id}>
              <TableCell>
                <div className="space-y-1">
                  {h.domain_names.map((d) => (
                    <div key={d} className="font-mono text-sm">{d}</div>
                  ))}
                </div>
              </TableCell>
              <TableCell className="font-mono text-sm text-primary">
                {h.mapping || `${h.forward_host}:${h.forward_port}`}
              </TableCell>
              <TableCell>
                <Badge variant={h.ssl_enabled ? "success" : "secondary"}>
                  <Shield className="h-3 w-3 mr-1 inline" />
                  {h.ssl_enabled ? "SSL" : "No SSL"}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground text-sm">{formatDate(h.last_synced_at)}</TableCell>
              <TableCell className="text-right">
                {isOperator && (
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(h.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </DataTable>
      )}
    </div>
  );
}
