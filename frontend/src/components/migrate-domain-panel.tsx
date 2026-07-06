import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { api, Domain, DNSRecord, MigrateDomainItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function previewHostname(hostname: string, fromZone: string, toZone: string): string {
  const h = hostname.toLowerCase().replace(/\.$/, "");
  const from = fromZone.toLowerCase().replace(/\.$/, "");
  const to = toZone.toLowerCase().replace(/\.$/, "");
  if (h === from) return to;
  const suffix = `.${from}`;
  if (h.endsWith(suffix)) {
    return `${h.slice(0, -suffix.length)}.${to}`;
  }
  return hostname;
}

export function MigrateDomainPanel({
  recordIds,
  records,
  domains,
  onClose,
  onDone,
}: {
  recordIds: number[];
  records: DNSRecord[];
  domains: Domain[];
  onClose: () => void;
  onDone: () => void;
}) {
  const selectedRecords = records.filter((r) => recordIds.includes(r.id));
  const [targetDomain, setTargetDomain] = useState(domains[0]?.name ?? "");
  const [preview, setPreview] = useState<MigrateDomainItem[] | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState<"preview" | "migrate" | null>(null);

  const localPreview = targetDomain
    ? selectedRecords.map((r) => ({
        record_id: r.id,
        proxy_id: r.proxy_id ?? null,
        old_hostname: r.hostname,
        new_hostname: previewHostname(r.hostname, r.domain_name ?? "", targetDomain),
        migrated: false,
      }))
    : [];

  const runPreview = async () => {
    if (!targetDomain) return;
    setBusy("preview");
    setErrors([]);
    try {
      const res = await api.migrateDomain(recordIds, targetDomain, true);
      setPreview(res.results);
      setErrors(res.errors);
    } catch (e) {
      setErrors([e instanceof Error ? e.message : "Preview failed"]);
      setPreview(null);
    } finally {
      setBusy(null);
    }
  };

  const runMigrate = async () => {
    if (!targetDomain) return;
    if (
      !confirm(
        `Migrate ${recordIds.length} service(s) to ${targetDomain}?\n\nDNS, Caddy proxy, and SSL will move to the new hostnames. Old certificates are removed; Let's Encrypt will issue new ones.`
      )
    ) {
      return;
    }
    setBusy("migrate");
    setErrors([]);
    try {
      const res = await api.migrateDomain(recordIds, targetDomain, false);
      if (res.errors.length) {
        alert(
          `Migrated ${res.migrated} of ${recordIds.length}.\n\n${res.errors.join("\n")}${
            res.caddy_reloaded ? "\n\nCaddy reloaded — new SSL certs will be requested." : ""
          }`
        );
      }
      onDone();
    } catch (e) {
      setErrors([e instanceof Error ? e.message : "Migration failed"]);
    } finally {
      setBusy(null);
    }
  };

  const rows = preview ?? localPreview;

  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle>Migrate to new domain</CardTitle>
        <CardDescription>
          Move selected services to another Cloudflare zone. Record and proxy IDs stay the same — only
          hostnames, DNS, and Caddy SSL change.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2 max-w-md">
          <Label htmlFor="migrate-target">New base domain</Label>
          <select
            id="migrate-target"
            className="flex h-9 w-full rounded-md border border-input bg-secondary/50 px-3 text-sm"
            value={targetDomain}
            onChange={(e) => {
              setTargetDomain(e.target.value);
              setPreview(null);
            }}
          >
            {domains.map((d) => (
              <option key={d.id} value={d.name}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        {rows.length > 0 && (
          <div className="rounded-md border border-border overflow-hidden text-sm">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left p-2 font-medium text-muted-foreground">Current</th>
                  <th className="p-2 w-8" />
                  <th className="text-left p-2 font-medium text-muted-foreground">After</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.record_id} className="border-b border-border/50 last:border-0">
                    <td className="p-2 font-mono text-xs">{row.old_hostname}</td>
                    <td className="p-2 text-muted-foreground">
                      <ArrowRight className="h-4 w-4" />
                    </td>
                    <td className="p-2 font-mono text-xs text-primary">{row.new_hostname}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {errors.length > 0 && (
          <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3 space-y-1">
            {errors.map((e, i) => (
              <p key={i}>{e}</p>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => void runPreview()} disabled={busy !== null || !targetDomain}>
            {busy === "preview" ? "Checking…" : "Validate"}
          </Button>
          <Button type="button" onClick={() => void runMigrate()} disabled={busy !== null || !targetDomain}>
            {busy === "migrate" ? "Migrating…" : "Migrate"}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
