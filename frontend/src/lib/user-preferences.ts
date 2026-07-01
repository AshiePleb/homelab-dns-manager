import { ThemeId, applyThemeClass, normalizeThemeId } from "@/lib/themes";

export interface UserPreferences {
  theme: ThemeId;
  font_size: number;
  reduce_motion: boolean;
  colorblind_mode: boolean;
}

export const DEFAULT_PREFERENCES: UserPreferences = {
  theme: "midnight",
  font_size: 100,
  reduce_motion: false,
  colorblind_mode: false,
};

export function normalizePreferences(raw: Partial<UserPreferences> | null | undefined): UserPreferences {
  return {
    theme: normalizeThemeId(raw?.theme),
    font_size: Math.max(90, Math.min(130, Number(raw?.font_size ?? 100))),
    reduce_motion: Boolean(raw?.reduce_motion),
    colorblind_mode: Boolean(raw?.colorblind_mode),
  };
}

export function applyPreferences(prefs: UserPreferences) {
  const root = document.documentElement;
  applyThemeClass(prefs.theme);
  root.style.fontSize = `${prefs.font_size}%`;
  root.dataset.reduceMotion = prefs.reduce_motion ? "true" : "false";
  root.dataset.colorblind = prefs.colorblind_mode ? "true" : "false";
  localStorage.setItem("user_preferences", JSON.stringify(prefs));
}

export function loadStoredPreferences(): UserPreferences {
  try {
    const raw = localStorage.getItem("user_preferences");
    if (raw) return normalizePreferences(JSON.parse(raw));
  } catch {
    /* ignore */
  }
  const legacyTheme = localStorage.getItem("theme");
  return normalizePreferences({ theme: normalizeThemeId(legacyTheme) });
}
