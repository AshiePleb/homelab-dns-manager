import { useEffect, useState } from "react";
import { Plus, Trash2, History, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { api, DNSRecord, Domain } from "@/lib/api";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  none: "No proxy",
  active: "Working",
  pending: "Pending",
  warning: "Issue",
  error: "Error",
};

export function RecordsPage() {
  const [records, setRecords] = useState<DNSRecord[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [history, setHistory] = useState<{ old_content: string | null; new_content: string; change_reason: string; created_at: string }[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const { isOperator } = useAuth();

  const [form, setForm] = useState({
    domain_id: 0,
    hostname: "",
    record_type: "A",
    content: "",
    proxied: false,
    managed: true,
    ttl: 1,
  });

  const load = async () => {
    setLoading(true);
    try {
      const [r, d] = await Promise.all([api.getRecords(), api.getDomains()]);
      setRecords(r);
      setDomains(d);
      if (d.length && !form.domain_id) setForm((f) => ({ ...f, domain_id: d[0].id }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createRecord(form);
      setShowAdd(false);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed");
    }
  };

  const handleDelete = async (r: DNSRecord) => {
    const msg = r.proxy_id
      ? `Remove ${r.hostname}? This deletes the DNS record and Caddy proxy.`
      : `Delete DNS record ${r.hostname}?`;
    if (!confirm(msg)) return;
    try {
      await api.deleteRecord(r.id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed");
    }
  };

  const handleForceUpdate = async (id: number) => {
    try {
      const result = await api.forceUpdateRecord(id);
      alert(`Updated to IP: ${(result as { ip: string }).ip}`);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed");
    }
  };

  const showHistory = async (id: number) => {
    setHistoryId(id);
    setHistory(await api.getRecordHistory(id));
  };

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === records.length) setSelected(new Set());
    else setSelected(new Set(records.map((r) => r.id)));
  };

  const runBulk = async (action: string) => {
    if (!selected.size) return;
    const label = action.replace("_", " ");
    if (!confirm(`${label} on ${selected.size} record(s)?`)) return;
    setBulkBusy(true);
    try {
      const res = await api.bulkRecords([...selected], action);
      if (res.errors.length) alert(`${res.updated} updated.\n\n${res.errors.join("\n")}`);
      setSelected(new Set());
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Bulk action failed");
    } finally {
      setBulkBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">DNS Records</h2>
          <p className="text-muted-foreground">
            App-managed DNS and services (DDNS + Caddy).{" "}
            <Link to="/services" className="text-primary hover:underline">
              Add new service →
            </Link>
          </p>
        </div>
        {isOperator && (
          <Button variant="outline" onClick={() => setShowAdd(!showAdd)}>
            <Plus className="h-4 w-4 mr-2" /> DNS only (advanced)
          </Button>
        )}
      </div>

      {showAdd && isOperator && (
        <form onSubmit={handleCreate} className="rounded-lg border border-border bg-card p-6 space-y-4">
          <p className="text-sm text-muted-foreground">
            DNS-only record without Caddy proxy. For homelab apps use{" "}
            <Link to="/services" className="text-primary hover:underline">Add Service</Link> instead.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <Label>Domain</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-secondary/50 px-3 text-sm"
                value={form.domain_id}
                onChange={(e) => setForm({ ...form, domain_id: Number(e.target.value) })}
              >
                {domains.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Hostname</Label>
              <Input value={form.hostname} onChange={(e) => setForm({ ...form, hostname: e.target.value })} placeholder="app.example.com" required />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-secondary/50 px-3 text-sm"
                value={form.record_type}
                onChange={(e) => setForm({ ...form, record_type: e.target.value })}
              >
                <option value="A">A</option>
                <option value="AAAA">AAAA</option>
                <option value="CNAME">CNAME</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Target IP / Content</Label>
              <Input
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                placeholder={form.managed && form.record_type === "A" ? "Leave empty for current public IP" : "1.2.3.4"}
                required={!(form.managed && form.record_type === "A")}
              />
            </div>
            <div className="flex items-center gap-4 pt-6">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.managed} onChange={(e) => setForm({ ...form, managed: e.target.checked })} />
                DDNS Managed
              </label>
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="submit">Create Record</Button>
            <Button type="button" variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
          </div>
        </form>
      )}

      {isOperator && selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm">
          <span className="font-medium">{selected.size} selected</span>
          <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulk("enable_ddns")}>
            Enable DDNS
          </Button>
          <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulk("disable_ddns")}>
            Disable DDNS
          </Button>
          <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulk("force_update")}>
            Force update
          </Button>
          <Button size="sm" variant="destructive" disabled={bulkBusy} onClick={() => runBulk("delete")}>
            Delete
          </Button>
        </div>
      )}

      {historyId !== null && (
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="flex justify-between mb-4">
            <h3 className="font-semibold">Record History</h3>
            <Button variant="ghost" size="sm" onClick={() => setHistoryId(null)}>Close</Button>
          </div>
          {history.length === 0 ? (
            <p className="text-muted-foreground text-sm">No history</p>
          ) : (
            <div className="space-y-2">
              {history.map((h, i) => (
                <div key={i} className="text-sm border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">{h.old_content || "—"}</span>
                  {" → "}
                  <span className="font-mono">{h.new_content}</span>
                  <span className="ml-2 text-xs text-muted-foreground">({h.change_reason}) {formatDate(h.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <>
          {isOperator && records.length > 0 && (
            <label className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
              <input type="checkbox" checked={selected.size === records.length} onChange={toggleAll} />
              Select all
            </label>
          )}
          <DataTable
          columns={[
            ...(isOperator ? [{ key: "sel", label: "", className: "w-10" }] : []),
            { key: "hostname", label: "Hostname" },
            { key: "internal", label: "Internal target" },
            { key: "dns", label: "Public IP / DDNS" },
            { key: "ssl", label: "SSL" },
            { key: "port", label: "Port" },
            { key: "updated", label: "Updated" },
            { key: "actions", label: "", className: "text-right" },
          ]}
          isEmpty={records.length === 0}
          emptyMessage="No records yet. Add a service to get started."
        >
          {records.map((r) => (
            <TableRow key={r.id}>
              {isOperator && (
                <TableCell>
                  <input
                    type="checkbox"
                    checked={selected.has(r.id)}
                    onChange={() => toggleSelect(r.id)}
                    aria-label={`Select ${r.hostname}`}
                  />
                </TableCell>
              )}
              <TableCell className="font-mono text-sm text-primary">{r.hostname}</TableCell>
              <TableCell className="font-mono text-sm">
                {r.forward_host && r.forward_port != null ? (
                  <span>{r.forward_host}:{r.forward_port}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap items-center gap-1">
                  {r.managed && <Badge variant="success">DDNS</Badge>}
                  <span className="font-mono text-xs text-muted-foreground">{r.content}</span>
                </div>
              </TableCell>
              <TableCell>
                {r.ssl_status === "none" || !r.ssl_provider ? (
                  <span className="text-xs text-muted-foreground">DNS only</span>
                ) : (
                  <div className="space-y-1" title={r.ssl_message || undefined}>
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge variant={sslVariant[r.ssl_status || "pending"]}>
                        {sslStatusLabel[r.ssl_status || "pending"]}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{r.ssl_label}</p>
                    {r.ssl_message && r.ssl_status !== "active" && (
                      <p className="text-xs text-muted-foreground max-w-[200px] truncate">{r.ssl_message}</p>
                    )}
                  </div>
                )}
              </TableCell>
              <TableCell>
                {r.port_reachable == null ? (
                  <span className="text-xs text-muted-foreground">—</span>
                ) : (
                  <Badge variant={r.port_reachable ? "success" : "destructive"}>
                    {r.port_reachable ? "Open" : "Closed"}
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground text-sm">{formatDate(r.last_updated_at)}</TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" size="sm" onClick={() => showHistory(r.id)} title="History">
                    <History className="h-4 w-4" />
                  </Button>
                  {isOperator && r.managed && (
                    <Button variant="ghost" size="sm" onClick={() => handleForceUpdate(r.id)} title="Force DDNS update">
                      <Zap className="h-4 w-4" />
                    </Button>
                  )}
                  {isOperator && (
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(r)} title="Delete">
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </DataTable>
        </>
      )}
    </div>
  );
}
