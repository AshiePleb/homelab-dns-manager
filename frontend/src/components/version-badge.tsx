import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpCircle } from "lucide-react";
import { api, VersionStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

export function VersionBadge() {
  const [status, setStatus] = useState<VersionStatus | null>(null);

  useEffect(() => {
    api.getVersionStatus().then(setStatus).catch(() => {});
  }, []);

  if (!status) return null;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground hidden sm:inline" title={status.image}>
        {status.version === "latest" ? "latest" : status.version.startsWith("v") ? status.version : `v${status.version}`}
      </span>
      {status.update_available && (
        <Link
          to="/settings"
          state={{ tab: "system" }}
          className={cn(
            "inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium",
            "bg-warning/15 text-warning hover:bg-warning/25"
          )}
          title="A newer image is on Docker Hub"
        >
          <ArrowUpCircle className="h-3.5 w-3.5" aria-hidden />
          Update
        </Link>
      )}
    </div>
  );
}
