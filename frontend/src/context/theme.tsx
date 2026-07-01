import {
  createContext,
  useCallback,
  useContext,
  useState,
  ReactNode,
  useEffect,
} from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/auth";
import { ThemeId } from "@/lib/themes";
import {
  UserPreferences,
  DEFAULT_PREFERENCES,
  normalizePreferences,
  applyPreferences,
  loadStoredPreferences,
} from "@/lib/user-preferences";

interface PreferencesContextType {
  preferences: UserPreferences;
  theme: ThemeId;
  setTheme: (theme: ThemeId) => void;
  updatePreferences: (patch: Partial<UserPreferences>) => Promise<void>;
}

const PreferencesContext = createContext<PreferencesContextType | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [preferences, setPreferences] = useState<UserPreferences>(() => {
    const initial = loadStoredPreferences();
    applyPreferences(initial);
    return initial;
  });

  useEffect(() => {
    if (user?.preferences) {
      const next = normalizePreferences(user.preferences);
      setPreferences(next);
      applyPreferences(next);
    }
  }, [user?.id, user?.preferences]);

  const persist = useCallback(async (next: UserPreferences) => {
    setPreferences(next);
    applyPreferences(next);
    if (user) {
      await api.updatePreferences(next);
    }
  }, [user]);

  const setTheme = useCallback(
    (theme: ThemeId) => {
      void persist({ ...preferences, theme });
    },
    [preferences, persist]
  );

  const updatePreferences = useCallback(
    async (patch: Partial<UserPreferences>) => {
      await persist({ ...preferences, ...patch });
    },
    [preferences, persist]
  );

  return (
    <PreferencesContext.Provider
      value={{
        preferences,
        theme: preferences.theme,
        setTheme,
        updatePreferences,
      }}
    >
      {children}
    </PreferencesContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return { theme: ctx.theme, setTheme: ctx.setTheme };
}

export function usePreferences() {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error("usePreferences must be used within ThemeProvider");
  return ctx;
}

export type { ThemeId };
