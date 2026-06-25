import {
  createContext,
  useCallback,
  useContext,
  useState,
  ReactNode,
} from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/auth";
import { ThemeId, normalizeThemeId, applyThemeClass } from "@/lib/themes";

interface ThemeContextType {
  theme: ThemeId;
  setTheme: (theme: ThemeId) => void;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { isAdmin } = useAuth();
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const initial = normalizeThemeId(localStorage.getItem("theme"));
    applyThemeClass(initial);
    return initial;
  });

  const setTheme = useCallback(
    (next: ThemeId) => {
      applyThemeClass(next);
      setThemeState(next);

      if (isAdmin) {
        api
          .getSettings()
          .then((s) => api.updateGeneral({ ...s.general, theme: next }))
          .catch(() => {});
      }
    },
    [isAdmin]
  );

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

export type { ThemeId };
