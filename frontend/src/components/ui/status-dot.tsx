import { cn } from "@/lib/utils";

export function StatusDot({ status, className }: { status: string; className?: string }) {
  const color = {
    running: "bg-success",
    active: "bg-success",
    connected: "bg-success",
    healthy: "bg-success",
    success: "bg-success",
    exited: "bg-muted-foreground",
    stopped: "bg-muted-foreground",
    error: "bg-destructive",
    warning: "bg-warning",
    not_configured: "bg-warning",
  }[status.toLowerCase()] || "bg-muted-foreground";

  return (
    <span className={cn("inline-block h-2 w-2 rounded-full", color, className)} />
  );
}
