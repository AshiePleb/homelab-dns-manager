import { useEffect, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { api, Domain } from "@/lib/api";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusDot } from "@/components/ui/status-dot";
import { formatDate } from "@/lib/utils";
import { useAuth } from "@/context/auth";

export function DomainsPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const { isOperator } = useAuth();

  const load = async () => {
    setLoading(true);
    try {
      setDomains(await api.getDomains());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await api.syncDomains();
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleSync = async (id: number) => {
    try {
      await api.syncDomain(id);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Sync failed");
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete domain ${name} from local database?`)) return;
    try {
      await api.deleteDomain(id);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Domains</h2>
          <p className="text-muted-foreground">Cloudflare zones managed by this application</p>
        </div>
        {isOperator && (
          <Button onClick={handleSyncAll} disabled={syncing}>
            <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? "animate-spin" : ""}`} />
            Sync from Cloudflare
          </Button>
        )}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <DataTable
          columns={[
            { key: "domain", label: "Domain" },
            { key: "status", label: "Status" },
            { key: "records", label: "DNS Records" },
            { key: "updated", label: "Last Updated" },
            { key: "actions", label: "Actions", className: "text-right" },
          ]}
          isEmpty={domains.length === 0}
          emptyMessage="No domains synced. Configure Cloudflare and sync zones."
        >
          {domains.map((d) => (
            <TableRow key={d.id}>
              <TableCell>
                <div className="flex items-center gap-2 font-medium">{d.name}</div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <StatusDot status={d.status} />
                  <Badge variant="outline">{d.status}</Badge>
                </div>
              </TableCell>
              <TableCell>{d.record_count}</TableCell>
              <TableCell className="text-muted-foreground">{formatDate(d.last_synced_at)}</TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  {isOperator && (
                    <Button variant="ghost" size="sm" onClick={() => handleSync(d.id)} title="Sync">
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  )}
                  {isOperator && (
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(d.id, d.name)} title="Delete">
                      <Trash2 className="h-4 w-4 text-destructive" />
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
