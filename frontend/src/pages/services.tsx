import { useEffect, useMemo, useState } from "react";
import { Plus, Globe, ArrowRight, Wifi } from "lucide-react";
import { Link } from "react-router-dom";
import { api, ServiceTemplate } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/context/auth";

export function ServicesPage() {
  const [template, setTemplate] = useState<ServiceTemplate | null>(null);
  const { isOperator } = useAuth();

  const [form, setForm] = useState({
    subdomain: "",
    base_domain: "",
    target: "",
    skip_port_check: false,
  });
  const [portStatus, setPortStatus] = useState<{ reachable: boolean; message: string } | null>(null);
  const [checkingPort, setCheckingPort] = useState(false);

  useEffect(() => {
    api.getServiceTemplate().then((tmpl) => {
      setTemplate(tmpl);
      if (tmpl.base_domain) {
        setForm((f) => ({ ...f, base_domain: tmpl.base_domain || "" }));
      }
    });
  }, []);

  const previewHostname = useMemo(() => {
    const base = form.base_domain || template?.base_domain || "example.com";
    const sub = form.subdomain.trim().toLowerCase();
    if (!sub) return `subdomain.${base}`;
    if (sub.includes(".")) return sub;
    return `${sub}.${base}`;
  }, [form.subdomain, form.base_domain, template]);

  const checkPort = async () => {
    if (!form.target.includes(":")) {
      setPortStatus({ reachable: false, message: "Enter IP:port to test" });
      return;
    }
    const [host, portStr] = form.target.split(":");
    const port = parseInt(portStr, 10);
    if (!host || !port) return;
    setCheckingPort(true);
    try {
      const result = await api.checkPort(host, port);
      setPortStatus(result);
    } catch (err) {
      setPortStatus({ reachable: false, message: err instanceof Error ? err.message : "Check failed" });
    } finally {
      setCheckingPort(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await api.provisionService({
        subdomain: form.subdomain,
        target: form.target,
        base_domain: form.base_domain || undefined,
        ssl_mode: "letsencrypt",
        create_dns: true,
        create_proxy: true,
        skip_port_check: form.skip_port_check,
      });
      alert(`Service ready: ${result.mapping}\n\nView it under DNS Records.`);
      setForm((f) => ({ ...f, subdomain: "", target: "" }));
      setPortStatus(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to provision service");
    }
  };

  const baseDomain = form.base_domain || template?.base_domain || "";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Add Service</h2>
        <p className="text-muted-foreground">
          Create a subdomain with DNS, DDNS, and Caddy HTTPS in one step.{" "}
          <Link to="/records" className="text-primary hover:underline">
            View all managed records →
          </Link>
        </p>
      </div>

      {isOperator && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              New service
            </CardTitle>
            <CardDescription>
              Example: <code className="text-primary">git</code> +{" "}
              <code className="text-primary">10.10.10.1:3100</code> →{" "}
              <code className="text-primary">git.{baseDomain || "example.com"}</code>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Base domain</Label>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-secondary/50 px-3 text-sm"
                    value={form.base_domain}
                    onChange={(e) => setForm({ ...form, base_domain: e.target.value })}
                    required
                  >
                    {(template?.available_zones?.length
                      ? template.available_zones
                      : baseDomain
                        ? [baseDomain]
                        : []
                    ).map((z) => (
                      <option key={z} value={z}>
                        {z}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Subdomain</Label>
                  <div className="flex">
                    <Input
                      value={form.subdomain}
                      onChange={(e) => setForm({ ...form, subdomain: e.target.value })}
                      placeholder="git"
                      className="rounded-r-none"
                      required
                    />
                    <span className="inline-flex items-center rounded-r-md border border-l-0 border-input bg-secondary/80 px-3 text-sm text-muted-foreground">
                      .{baseDomain || "…"}
                    </span>
                  </div>
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label>Internal target (IP:port)</Label>
                  <div className="flex gap-2">
                    <Input
                      value={form.target}
                      onChange={(e) => {
                        setForm({ ...form, target: e.target.value });
                        setPortStatus(null);
                      }}
                      placeholder="10.10.10.1:3100"
                      className="font-mono"
                      required
                    />
                    <Button type="button" variant="outline" onClick={checkPort} disabled={checkingPort}>
                      <Wifi className="h-4 w-4 mr-1" />
                      {checkingPort ? "…" : "Test port"}
                    </Button>
                  </div>
                  {portStatus && (
                    <p className={`text-xs ${portStatus.reachable ? "text-green-500" : "text-destructive"}`}>
                      {portStatus.message}
                    </p>
                  )}
                </div>
              </div>

              <p className="text-xs text-muted-foreground rounded-md border border-border bg-secondary/30 px-3 py-2">
                HTTPS via Caddy + Let's Encrypt. DNS A record → your public IP (DDNS). Router forwards{" "}
                <strong>80</strong> and <strong>443</strong> to this server.
              </p>

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.skip_port_check}
                  onChange={(e) => setForm({ ...form, skip_port_check: e.target.checked })}
                />
                Skip port check on create (not recommended)
              </label>

              <div className="rounded-md border border-primary/20 bg-primary/5 px-4 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2 font-mono">
                  <Globe className="h-4 w-4 text-primary shrink-0" />
                  <span className="text-primary">{previewHostname}</span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  <span>{form.target || "10.10.10.1:port"}</span>
                  <span className="text-muted-foreground">(via Caddy)</span>
                </div>
              </div>

              <Button type="submit">Create service</Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
