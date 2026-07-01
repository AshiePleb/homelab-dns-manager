export type ThemeId =
  | "midnight"
  | "slate"
  | "ocean"
  | "rose"
  | "forest"
  | "amber"
  | "light"
  | "cream"
  | "frost"
  | "paper"
  | "mint"
  | "contrast-dark"
  | "contrast-light"
  | "readable";

export type ThemeGroup = "dark" | "light" | "accessibility";

export interface ThemeOption {
  id: ThemeId;
  label: string;
  description?: string;
  group: ThemeGroup;
  /** Preview swatch: background / accent for picker UI */
  preview: { bg: string; accent: string };
}

export const THEMES: ThemeOption[] = [
  { id: "midnight", label: "Midnight", group: "dark", preview: { bg: "222 47% 8%", accent: "199 89% 48%" } },
  { id: "slate", label: "Slate", group: "dark", preview: { bg: "220 15% 10%", accent: "210 40% 55%" } },
  { id: "ocean", label: "Ocean", group: "dark", preview: { bg: "215 40% 8%", accent: "200 90% 50%" } },
  { id: "rose", label: "Rose", group: "dark", preview: { bg: "350 30% 8%", accent: "350 75% 55%" } },
  { id: "forest", label: "Forest", group: "dark", preview: { bg: "150 25% 7%", accent: "142 65% 42%" } },
  { id: "amber", label: "Amber", group: "dark", preview: { bg: "30 20% 8%", accent: "38 92% 50%" } },
  { id: "light", label: "Light", group: "light", preview: { bg: "0 0% 100%", accent: "199 89% 40%" } },
  { id: "cream", label: "Cream", group: "light", preview: { bg: "40 30% 97%", accent: "25 80% 45%" } },
  { id: "frost", label: "Frost", group: "light", preview: { bg: "210 25% 98%", accent: "215 60% 45%" } },
  { id: "paper", label: "Paper", group: "light", preview: { bg: "45 20% 99%", accent: "220 50% 40%" } },
  { id: "mint", label: "Mint", group: "light", preview: { bg: "150 20% 97%", accent: "155 50% 38%" } },
  {
    id: "contrast-dark",
    label: "High contrast dark",
    description: "Black background, white text — WCAG AAA",
    group: "accessibility",
    preview: { bg: "0 0% 0%", accent: "55 100% 50%" },
  },
  {
    id: "contrast-light",
    label: "High contrast light",
    description: "White background, black text — WCAG AAA",
    group: "accessibility",
    preview: { bg: "0 0% 100%", accent: "240 100% 40%" },
  },
  {
    id: "readable",
    label: "Readable",
    description: "Larger text and spacing for low vision",
    group: "accessibility",
    preview: { bg: "45 15% 96%", accent: "215 70% 35%" },
  },
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
