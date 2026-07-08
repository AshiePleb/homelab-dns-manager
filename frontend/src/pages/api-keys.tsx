import { useEffect, useState } from "react";
import { Copy, Key, Plus, Trash2 } from "lucide-react";
import { Navigate } from "react-router-dom";
import { api, ApiKey, ApiKeyCreated, ApiEndpointInfo } from "@/lib/api";
import { useAuth } from "@/context/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, TableRow, TableCell } from "@/components/data-table";
import { formatDate } from "@/lib/utils";

export function ApiKeysPage() {
  const { isAdmin } = useAuth();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [endpoint, setEndpoint] = useState<ApiEndpointInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [form, setForm] = useState({ name: "", max_dns_records: 10, max_services: 10 });

  if (!isAdmin) return <Navigate to="/" replace />;

  const load = async () => {
    setLoading(true);
    try {
      const [endpointInfo, keyList] = await Promise.all([api.getApiEndpoint(), api.getApiKeys()]);
      setEndpoint(endpointInfo);
      setKeys(keyList);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load API keys");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setMessage("Copied to clipboard");
    setTimeout(() => setMessage(""), 2000);
  };

  const createKey = async () => {
    setError("");
    try {
      const created = await api.createApiKey(form);
      setCreatedKey(created);
      setShowCreate(false);
      setForm({ name: "", max_dns_records: 10, max_services: 10 });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create API key");
    }
  };

  const revokeKey = async (key: ApiKey) => {
    if (!confirm(`Revoke API key "${key.name}"? Integrations using it will stop working.`)) return;
    try {
      await api.revokeApiKey(key.id);
      await load();
      setMessage(`Revoked ${key.name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke key");
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">API Keys</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Connect HomeLab WebHost Manager and other apps to provision DDNS and Caddy SSL automatically.
        </p>
      </div>

      {message && (
        <div className="rounded-md border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {createdKey && (
        <Card className="border-primary/40 bg-primary/5">
          <CardHeader>
            <CardTitle className="text-base">API key created — copy it now</CardTitle>
            <CardDescription>This key is only shown once. Store it securely in WebHost Manager.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-md bg-background border border-border px-3 py-2 text-sm font-mono break-all">
                {createdKey.api_key}
              </code>
              <Button variant="outline" size="icon" onClick={() => copyText(createdKey.api_key)}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setCreatedKey(null)}>
              Dismiss
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Key className="h-4 w-4" />
            API endpoint
          </CardTitle>
          <CardDescription>Use this base URL in HomeLab WebHost Manager settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Base URL</Label>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-md bg-muted/40 border border-border px-3 py-2 text-sm font-mono">
                {endpoint?.api_base || `${window.location.origin}/api/v1`}
              </code>
              <Button
                variant="outline"
                size="icon"
                onClick={() => copyText(endpoint?.api_base || `${window.location.origin}/api/v1`)}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Auth header: <code className="font-mono">{endpoint?.auth_header || "Authorization: Bearer <api_key>"}</code>
          </p>
          <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground space-y-1">
            <p className="font-medium text-foreground">WebHost integration flow</p>
            <p>1. Create an API key below with limits for DNS records and services.</p>
            <p>2. In WebHost Manager, set the DNS Manager URL and paste the API key.</p>
            <p>3. When a site is published, WebHost calls <code className="font-mono">POST /services/provision</code> with the site&apos;s proxy target.</p>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Keys</h3>
          <p className="text-sm text-muted-foreground">Per-key limits control how many DNS records and services can be created.</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Create API key
        </Button>
      </div>

      <DataTable
        columns={[
          { key: "name", label: "Name" },
          { key: "prefix", label: "Key" },
          { key: "limits", label: "Limits" },
          { key: "usage", label: "Usage" },
          { key: "status", label: "Status" },
          { key: "last", label: "Last used" },
          { key: "actions", label: "", className: "text-right" },
        ]}
        isEmpty={!loading && keys.length === 0}
        emptyMessage="No API keys yet"
      >
        {keys.map((key) => (
          <TableRow key={key.id}>
            <TableCell className="font-medium">{key.name}</TableCell>
            <TableCell>
              <code className="text-xs font-mono">{key.key_prefix}…</code>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {key.max_dns_records} DNS · {key.max_services} services
            </TableCell>
            <TableCell className="text-sm">
              {key.usage.dns_records}/{key.max_dns_records} DNS · {key.usage.services}/{key.max_services} svc
            </TableCell>
            <TableCell>
              <Badge variant={key.is_active ? "success" : "secondary"}>
                {key.is_active ? "Active" : "Revoked"}
              </Badge>
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">
              {key.last_used_at ? formatDate(key.last_used_at) : "Never"}
            </TableCell>
            <TableCell className="text-right">
              {key.is_active && (
                <Button variant="ghost" size="sm" onClick={() => revokeKey(key)}>
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </DataTable>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowCreate(false)} />
          <div className="relative w-full max-w-md rounded-lg border border-border bg-background p-5 shadow-xl space-y-4">
            <h3 className="font-semibold">Create API key</h3>
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="HomeLab WebHost"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Max DNS records</Label>
                <Input
                  type="number"
                  min={1}
                  max={500}
                  value={form.max_dns_records}
                  onChange={(e) => setForm({ ...form, max_dns_records: Number(e.target.value) })}
                />
              </div>
              <div className="space-y-2">
                <Label>Max services</Label>
                <Input
                  type="number"
                  min={1}
                  max={500}
                  value={form.max_services}
                  onChange={(e) => setForm({ ...form, max_services: Number(e.target.value) })}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button onClick={createKey} disabled={!form.name.trim()}>
                Create
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
