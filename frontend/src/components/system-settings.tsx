import { useRef, useState } from "react";
import { Download, Upload } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function SystemSettings({ onMessage }: { onMessage: (msg: string) => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"export" | "import" | null>(null);

  const exportBackup = async () => {
    setBusy("export");
    try {
      const blob = await api.exportBackup();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `homelab-dns-backup-${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      onMessage("Backup downloaded");
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(null);
    }
  };

  const importBackup = async (file: File) => {
    if (!confirm("Restore will overwrite data on the server. Continue?")) return;
    setBusy("import");
    try {
      const res = await api.importBackup(file);
      onMessage(res.message);
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Restore failed");
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backup & restore</CardTitle>
        <CardDescription>
          Export database, Caddy config, and certificates. Restore replaces server data.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        <Button type="button" onClick={exportBackup} disabled={busy !== null}>
          <Download className="h-4 w-4 mr-2" />
          {busy === "export" ? "Exporting…" : "Download backup"}
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept=".zip"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void importBackup(f);
          }}
        />
        <Button
          type="button"
          variant="outline"
          disabled={busy !== null}
          onClick={() => fileRef.current?.click()}
        >
          <Upload className="h-4 w-4 mr-2" />
          {busy === "import" ? "Restoring…" : "Restore from backup"}
        </Button>
      </CardContent>
    </Card>
  );
}
