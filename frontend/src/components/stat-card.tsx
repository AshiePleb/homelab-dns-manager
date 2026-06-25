import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  status?: string;
  className?: string;
}

export function StatCard({ title, value, subtitle, icon, status, className }: StatCardProps) {
  return (
    <div className={cn("rounded-lg border border-border bg-card p-5", className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {icon && (
          <div className="rounded-md bg-primary/10 p-2 text-primary">{icon}</div>
        )}
      </div>
      {status && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          <span className={cn(
            "h-1.5 w-1.5 rounded-full",
            status === "healthy" || status === "connected" ? "bg-success" : "bg-warning"
          )} />
          <span className="text-muted-foreground capitalize">{status.replace("_", " ")}</span>
        </div>
      )}
    </div>
  );
}
