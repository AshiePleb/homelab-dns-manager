import { useEffect, useRef, useState } from "react";
import { Palette } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useTheme } from "@/context/theme";
import { THEMES, ThemeGroup, ThemeId } from "@/lib/themes";

interface ThemePickerProps {
  variant?: "header" | "settings";
  disabled?: boolean;
  value?: ThemeId;
  onChange?: (theme: ThemeId) => void;
}

const GROUP_LABELS: Record<ThemeGroup, string> = {
  dark: "Dark",
  light: "Light",
  accessibility: "Accessibility",
};

const GROUP_ORDER: ThemeGroup[] = ["dark", "light", "accessibility"];

export function ThemePicker({ variant = "header", disabled, value, onChange }: ThemePickerProps) {
  const { theme, setTheme } = useTheme();
  const active = value ?? theme;
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  const pick = (id: ThemeId) => {
    if (onChange) onChange(id);
    else setTheme(id);
    setOpen(false);
  };

  const groups = GROUP_ORDER.map((group) => ({
    group,
    label: GROUP_LABELS[group],
    themes: THEMES.filter((t) => t.group === group),
  }));

  if (variant === "settings") {
    return (
      <div className="space-y-5">
        {groups.map(({ group, label, themes }) => (
          <ThemeGroup key={group} label={label} themes={themes} active={active} onPick={pick} disabled={disabled} />
        ))}
      </div>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(!open)}
        title="Choose theme"
        type="button"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <Palette className="h-4 w-4" />
      </Button>
      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-2 w-72 max-h-[min(70vh,28rem)] overflow-y-auto rounded-lg border border-border bg-card p-3 shadow-lg scrollbar-thin"
          role="listbox"
          aria-label="Theme options"
        >
          <p className="text-xs font-medium text-muted-foreground mb-2 px-1">Theme</p>
          {groups.map(({ group, label, themes }) => (
            <ThemeGroup key={group} label={label} themes={themes} active={active} onPick={pick} compact />
          ))}
        </div>
      )}
    </div>
  );
}

function ThemeGroup({
  label,
  themes,
  active,
  onPick,
  disabled,
  compact,
}: {
  label: string;
  themes: typeof THEMES;
  active: ThemeId;
  onPick: (id: ThemeId) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={cn(compact ? "mb-3 last:mb-0" : "mb-4 last:mb-0")}>
      <p className="text-xs text-muted-foreground mb-2">{label}</p>
      <div className={cn("grid gap-2", compact ? "grid-cols-1" : "grid-cols-2 sm:grid-cols-3")}>
        {themes.map((t) => (
          <button
            key={t.id}
            type="button"
            disabled={disabled}
            role="option"
            aria-selected={active === t.id}
            onClick={(e) => {
              e.stopPropagation();
              onPick(t.id);
            }}
            className={cn(
              "flex items-center gap-2 rounded-md border-2 px-2 py-2 text-left text-xs transition-colors",
              active === t.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/40",
              disabled && "opacity-50 cursor-not-allowed"
            )}
          >
            <span
              className="h-5 w-5 shrink-0 rounded-full border border-border"
              style={{
                background: `linear-gradient(135deg, hsl(${t.preview.bg}) 50%, hsl(${t.preview.accent}) 50%)`,
              }}
              aria-hidden
            />
            <span className="min-w-0">
              <span className="font-medium block truncate">{t.label}</span>
              {t.description && !compact && (
                <span className="text-[10px] text-muted-foreground line-clamp-2">{t.description}</span>
              )}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
