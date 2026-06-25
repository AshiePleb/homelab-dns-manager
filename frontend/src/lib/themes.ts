export type ThemeId =
  | "midnight"
  | "light"
  | "cream"
  | "frost"
  | "rose"
  | "forest"
  | "amber";

export interface ThemeOption {
  id: ThemeId;
  label: string;
  group: "dark" | "light";
  /** Preview swatch: background / accent for picker UI */
  preview: { bg: string; accent: string };
}

export const THEMES: ThemeOption[] = [
  { id: "midnight", label: "Midnight", group: "dark", preview: { bg: "222 47% 8%", accent: "199 89% 48%" } },
  { id: "rose", label: "Rose", group: "dark", preview: { bg: "350 30% 8%", accent: "350 75% 55%" } },
  { id: "forest", label: "Forest", group: "dark", preview: { bg: "150 25% 7%", accent: "142 65% 42%" } },
  { id: "amber", label: "Amber", group: "dark", preview: { bg: "30 20% 8%", accent: "38 92% 50%" } },
  { id: "light", label: "Light", group: "light", preview: { bg: "0 0% 100%", accent: "199 89% 40%" } },
  { id: "cream", label: "Cream", group: "light", preview: { bg: "40 30% 97%", accent: "25 80% 45%" } },
  { id: "frost", label: "Frost", group: "light", preview: { bg: "210 25% 98%", accent: "215 60% 45%" } },
];

export const THEME_IDS = THEMES.map((t) => t.id);

export function normalizeThemeId(raw: string | null | undefined): ThemeId {
  if (!raw) return "midnight";
  if (raw === "dark") return "midnight";
  if (THEME_IDS.includes(raw as ThemeId)) return raw as ThemeId;
  if (raw === "light") return "light";
  return "midnight";
}

export function applyThemeClass(themeId: ThemeId) {
  const root = document.documentElement;
  THEME_IDS.forEach((id) => root.classList.remove(`theme-${id}`));
  root.classList.remove("dark", "light");
  root.className = `theme-${themeId}`;
  root.dataset.theme = themeId;
  localStorage.setItem("theme", themeId);
}
