import { CheckCircle2, XCircle, AlertTriangle, MinusCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_META: Record<string, { label: string; icon: typeof CheckCircle2; tone: string }> = {
  healthy: { label: "Healthy", icon: CheckCircle2, tone: "text-success" },
  running: { label: "Running", icon: CheckCircle2, tone: "text-success" },
  active: { label: "Active", icon: CheckCircle2, tone: "text-success" },
  connected: { label: "Connected", icon: CheckCircle2, tone: "text-success" },
  success: { label: "Success", icon: CheckCircle2, tone: "text-success" },
  degraded: { label: "Degraded", icon: AlertTriangle, tone: "text-warning" },
  warning: { label: "Warning", icon: AlertTriangle, tone: "text-warning" },
  pending: { label: "Pending", icon: AlertTriangle, tone: "text-warning" },
  not_configured: { label: "Not configured", icon: AlertTriangle, tone: "text-warning" },
  down: { label: "Down", icon: XCircle, tone: "text-destructive" },
  error: { label: "Error", icon: XCircle, tone: "text-destructive" },
  exited: { label: "Exited", icon: MinusCircle, tone: "text-muted-foreground" },
  stopped: { label: "Stopped", icon: MinusCircle, tone: "text-muted-foreground" },
  inactive: { label: "Inactive", icon: MinusCircle, tone: "text-muted-foreground" },
};

export function StatusIndicator({
  status,
  showLabel = false,
  className,
}: {
  status: string;
  showLabel?: boolean;
  className?: string;
}) {
  const key = status.toLowerCase();
  const meta = STATUS_META[key] || {
    label: status,
    icon: MinusCircle,
    tone: "text-muted-foreground",
  };
  const Icon = meta.icon;

  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      role="status"
      aria-label={`${meta.label}`}
    >
      <span
        className={cn(
          "status-indicator-dot inline-flex h-5 w-5 items-center justify-center rounded-full border border-border/60",
          meta.tone
        )}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden />
      </span>
      {showLabel && <span className="text-xs font-medium">{meta.label}</span>}
    </span>
  );
}

/** @deprecated use StatusIndicator */
export function StatusDot({ status, className }: { status: string; className?: string }) {
  return <StatusIndicator status={status} className={className} />;
}
