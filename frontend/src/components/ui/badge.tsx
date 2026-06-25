import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "success" | "warning" | "destructive" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors",
        {
          default: "bg-primary/20 text-primary",
          secondary: "bg-secondary text-secondary-foreground",
          success: "bg-success/20 text-success",
          warning: "bg-warning/20 text-warning",
          destructive: "bg-destructive/20 text-destructive",
          outline: "border border-border text-foreground",
        }[variant],
        className
      )}
      {...props}
    />
  );
}
