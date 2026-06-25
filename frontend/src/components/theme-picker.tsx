import { useEffect, useRef, useState } from "react";
import { Palette } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useTheme } from "@/context/theme";
import { THEMES, ThemeId } from "@/lib/themes";

interface ThemePickerProps {
  variant?: "header" | "settings";
  disabled?: boolean;
  value?: ThemeId;
  onChange?: (theme: ThemeId) => void;
}

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

  const darkThemes = THEMES.filter((t) => t.group === "dark");
  const lightThemes = THEMES.filter((t) => t.group === "light");

  if (variant === "settings") {
    return (
      <div className="space-y-4">
        <ThemeGroup label="Dark" themes={darkThemes} active={active} onPick={pick} disabled={disabled} />
        <ThemeGroup label="Light" themes={lightThemes} active={active} onPick={pick} disabled={disabled} />
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
      >
        <Palette className="h-4 w-4" />
      </Button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-64 rounded-lg border border-border bg-card p-3 shadow-lg">
          <p className="text-xs font-medium text-muted-foreground mb-2 px-1">Theme</p>
          <ThemeGroup label="Dark" themes={darkThemes} active={active} onPick={pick} compact />
          <ThemeGroup label="Light" themes={lightThemes} active={active} onPick={pick} compact />
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
    <div className={cn(compact ? "mb-2 last:mb-0" : "mb-4 last:mb-0")}>
      <p className="text-xs text-muted-foreground mb-2">{label}</p>
      <div className={cn("grid gap-2", compact ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4")}>
        {themes.map((t) => (
          <button
            key={t.id}
            type="button"
            disabled={disabled}
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
            />
            <span className="font-medium truncate">{t.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
