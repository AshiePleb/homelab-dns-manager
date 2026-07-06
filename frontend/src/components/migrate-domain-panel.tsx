import { useMemo, useState } from "react";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { api, Domain, DNSRecord } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function extractSubdomain(hostname: string, zone: string): string {
  const h = hostname.toLowerCase().replace(/\.$/, "");
  const z = zone.toLowerCase().replace(/\.$/, "");
  if (h === z) return "@";
  const suffix = `.${z}`;
  if (h.endsWith(suffix)) return h.slice(0, -suffix.length);
  return hostname.split(".")[0] ?? hostname;
}

function buildNewHostname(subdomain: string, targetZone: string): string {
  const sub = subdomain.trim().toLowerCase();
  const zone = targetZone.trim().toLowerCase().replace(/\.$/, "");
  if (!sub || sub === "@") return zone;
  if (sub.includes(".")) return sub;
  return `${sub}.${zone}`;
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
  const [subdomains, setSubdomains] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      selectedRecords.map((r) => [r.id, extractSubdomain(r.hostname, r.domain_name ?? "")])
    )
  );
  const [validated, setValidated] = useState(false);
  const [validateMsg, setValidateMsg] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState<"preview" | "migrate" | null>(null);

  const mappings = useMemo(
    () =>
      selectedRecords.map((r) => ({
        record_id: r.id,
        subdomain: subdomains[r.id] ?? extractSubdomain(r.hostname, r.domain_name ?? ""),
      })),
    [selectedRecords, subdomains]
  );

  const rows = selectedRecords.map((r) => {
    const sub = subdomains[r.id] ?? "";
    return {
      record_id: r.id,
      old_hostname: r.hostname,
      subdomain: sub,
      new_hostname: targetDomain ? buildNewHostname(sub, targetDomain) : "—",
    };
  });

  const setSubdomain = (recordId: number, value: string) => {
    setSubdomains((prev) => ({ ...prev, [recordId]: value }));
    setValidated(false);
    setValidateMsg(null);
    setErrors([]);
  };

  const runPreview = async () => {
    if (!targetDomain) return;
    setBusy("preview");
    setErrors([]);
    setValidateMsg(null);
    setValidated(false);
    try {
      const res = await api.migrateDomain(recordIds, targetDomain, true, mappings);
      if (res.errors.length) {
        setErrors(res.errors);
        setValidated(false);
      } else if (res.migrated > 0) {
        setValidated(true);
        setValidateMsg(`Ready to migrate ${res.migrated} service(s) to ${targetDomain}.`);
      } else {
        setErrors(["Nothing to migrate — check subdomain and target domain."]);
      }
    } catch (e) {
      setErrors([e instanceof Error ? e.message : "Validation failed"]);
      setValidated(false);
    } finally {
      setBusy(null);
    }
  };

  const runMigrate = async () => {
    if (!targetDomain) return;
    if (!validated) {
      setErrors(["Click Validate first to check Cloudflare and hostnames."]);
      return;
    }
    const summary = rows.map((r) => `  ${r.old_hostname} → ${r.new_hostname}`).join("\n");
    if (
      !confirm(
        `Migrate ${recordIds.length} service(s) to ${targetDomain}?\n\n${summary}\n\nOld SSL certs are removed; Caddy will request new ones.`
      )
    ) {
      return;
    }
    setBusy("migrate");
    setErrors([]);
    try {
      const res = await api.migrateDomain(recordIds, targetDomain, false, mappings);
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

  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle>Migrate to new domain</CardTitle>
        <CardDescription>
          Move selected services to another Cloudflare zone. Edit subdomains if needed. Record and
          proxy IDs stay the same — DNS and Caddy SSL are updated.
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
              setValidated(false);
              setValidateMsg(null);
              setErrors([]);
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
                  <th className="text-left p-2 font-medium text-muted-foreground">New subdomain</th>
                  <th className="p-2 w-8" />
                  <th className="text-left p-2 font-medium text-muted-foreground">New hostname</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.record_id} className="border-b border-border/50 last:border-0">
                    <td className="p-2 font-mono text-xs align-middle">{row.old_hostname}</td>
                    <td className="p-2 align-middle">
                      <div className="flex items-center gap-1">
                        <Input
                          className="h-8 font-mono text-xs max-w-[140px]"
                          value={subdomains[row.record_id] ?? ""}
                          onChange={(e) => setSubdomain(row.record_id, e.target.value)}
                          placeholder="home"
                          aria-label={`Subdomain for ${row.old_hostname}`}
                        />
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          .{targetDomain}
                        </span>
                      </div>
                    </td>
                    <td className="p-2 text-muted-foreground align-middle">
                      <ArrowRight className="h-4 w-4" />
                    </td>
                    <td className="p-2 font-mono text-xs text-primary align-middle">
                      {row.new_hostname}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          Use <code className="text-xs">@</code> for the zone apex. Leave subdomain as-is to keep the
          same name on the new domain.
        </p>

        {validateMsg && validated && (
          <div className="flex items-center gap-2 rounded-md bg-success/10 text-success text-sm p-3">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{validateMsg}</span>
            <Badge variant="success" className="ml-auto">
              Validated
            </Badge>
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
          <Button
            type="button"
            variant="outline"
            onClick={() => void runPreview()}
            disabled={busy !== null || !targetDomain}
          >
            {busy === "preview" ? "Checking…" : "Validate"}
          </Button>
          <Button
            type="button"
            onClick={() => void runMigrate()}
            disabled={busy !== null || !targetDomain || !validated}
            title={!validated ? "Validate first" : undefined}
          >
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
