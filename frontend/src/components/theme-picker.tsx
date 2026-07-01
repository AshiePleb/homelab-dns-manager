import { cn } from "@/lib/utils";
import { usePreferences } from "@/context/theme";
import { THEMES, ThemeGroup, ThemeId } from "@/lib/themes";

const GROUP_LABELS: Record<ThemeGroup, string> = {
  dark: "Dark",
  light: "Light",
  accessibility: "Accessibility",
};

const GROUP_ORDER: ThemeGroup[] = ["dark", "light", "accessibility"];

interface ThemePickerProps {
  disabled?: boolean;
}

export function ThemePicker({ disabled }: ThemePickerProps) {
  const { preferences, setTheme } = usePreferences();
  const active = preferences.theme;

  const groups = GROUP_ORDER.map((group) => ({
    group,
    label: GROUP_LABELS[group],
    themes: THEMES.filter((t) => t.group === group),
  }));

  return (
    <div className="space-y-6">
      {groups.map(({ group, label, themes }) => (
        <div key={group}>
          <p className="text-sm font-medium mb-3">{label}</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {themes.map((t) => {
              const selected = active === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  disabled={disabled}
                  role="option"
                  aria-selected={selected}
                  aria-label={`${t.label} theme${t.description ? ` — ${t.description}` : ""}`}
                  onClick={() => setTheme(t.id as ThemeId)}
                  className={cn(
                    "group relative overflow-hidden rounded-lg border-2 p-3 text-left transition-all",
                    selected
                      ? "border-primary ring-2 ring-primary/30 shadow-sm"
                      : "border-border hover:border-primary/50",
                    disabled && "opacity-50 cursor-not-allowed"
                  )}
                >
                  <div
                    className="mb-3 h-14 w-full rounded-md border border-border/50 shadow-inner"
                    style={{
                      background: `linear-gradient(160deg, hsl(${t.preview.bg}) 0%, hsl(${t.preview.bg}) 55%, hsl(${t.preview.accent}) 100%)`,
                    }}
                    aria-hidden
                  />
                  <p className="text-sm font-semibold">{t.label}</p>
                  {t.description && (
                    <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{t.description}</p>
                  )}
                  {selected && (
                    <span className="absolute top-2 right-2 text-[10px] font-bold uppercase tracking-wide text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                      Active
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
