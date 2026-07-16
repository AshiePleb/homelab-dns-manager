import { useEffect, useState, type MouseEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowUpCircle } from "lucide-react";
import { api, VersionStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/auth";

function formatVersionTag(version: string) {
  if (!version || version === "dev") return "dev";
  if (version === "latest") return "latest";
  return version.startsWith("v") ? version : `v${version}`;
}

async function waitForAppBack(timeoutMs = 120_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      if (res.ok) return true;
    } catch {
      // still down
    }
  }
  return false;
}

export function VersionBadge() {
  const { isAdmin } = useAuth();
  const [status, setStatus] = useState<VersionStatus | null>(null);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    api.getVersionStatus().then(setStatus).catch(() => {});
  }, []);

  if (!status) return null;

  const latest = status.latest_version || status.latest_tag;

  const handleUpdate = async (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isAdmin || updating) return;
    if (
      !confirm(
        `Update to ${formatVersionTag(latest || "latest")} now?\n\nThe app will restart briefly. Your data is kept.`
      )
    ) {
      return;
    }
    setUpdating(true);
    try {
      await api.updateApp(false);
    } catch {
      // may abort when container stops
    }
    const ok = await waitForAppBack();
    if (ok) window.location.reload();
    else {
      alert("Update is taking longer than expected. Refresh the page in a minute.");
      setUpdating(false);
    }
  };

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground hidden sm:inline" title={status.image}>
        {formatVersionTag(status.version)}
      </span>
      {status.update_available && (
        isAdmin ? (
          <button
            type="button"
            onClick={handleUpdate}
            disabled={updating}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium",
              "bg-warning/15 text-warning hover:bg-warning/25 disabled:opacity-60"
            )}
            title={`Update to ${formatVersionTag(latest || "")}`}
          >
            <ArrowUpCircle className={cn("h-3.5 w-3.5", updating && "animate-pulse")} aria-hidden />
            {updating ? "Updating…" : `Update ${formatVersionTag(latest || "")}`}
          </button>
        ) : (
          <Link
            to="/settings"
            state={{ tab: "system" }}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium",
              "bg-warning/15 text-warning hover:bg-warning/25"
            )}
            title={
              status.latest_version
                ? `Update to ${status.latest_version}`
                : "A newer image is on Docker Hub"
            }
          >
            <ArrowUpCircle className="h-3.5 w-3.5" aria-hidden />
            {status.latest_version ? `→ ${status.latest_version}` : "Update"}
          </Link>
        )
      )}
    </div>
  );
}
