import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Tema claro ("light") ou escuro ("dark"). Light é o default institucional.
 *
 * A preferência é persistida em localStorage sob a chave `lente:theme`. Se
 * nada estiver salvo, respeita `prefers-color-scheme` do sistema. O atributo
 * `data-theme` é escrito diretamente em <html> para que o CSS resolva os
 * tokens semânticos correspondentes (ver index.css).
 */
export type Theme = "light" | "dark";

const STORAGE_KEY = "lente:theme";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  const prefersDark = window.matchMedia?.(
    "(prefers-color-scheme: dark)",
  ).matches;
  return prefersDark ? "dark" : "light";
}

function applyThemeAttribute(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") {
    root.setAttribute("data-theme", "dark");
  } else {
    root.removeAttribute("data-theme");
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(resolveInitialTheme);

  // Aplica o atributo no <html> assim que o tema muda.
  useEffect(() => {
    applyThemeAttribute(theme);
  }, [theme]);

  // Se o usuário não tem preferência explícita salva, acompanha mudanças do
  // sistema ao vivo (ex. auto-switch ao entardecer no macOS).
  useEffect(() => {
    if (window.localStorage.getItem(STORAGE_KEY)) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      setThemeState(e.matches ? "dark" : "light");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
  }, []);

  const toggle = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      window.localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ theme, setTheme, toggle }),
    [theme, setTheme, toggle],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme precisa estar dentro de <ThemeProvider>.");
  }
  return ctx;
}

/**
 * Tokens cromáticos para uso em gráficos e outros contextos que não aceitam
 * classes Tailwind (ex. Recharts, SVGs inline). Lê as variáveis CSS atuais
 * diretamente de `document.documentElement`, recalculando apenas quando o
 * tema muda. Os fallbacks garantem um render sensato durante SSR/hidratação.
 */
export interface ChartTokens {
  accent: string;
  accentSoft: string;
  neutral: string;
  axis: string;
  tick: string;
  grid: string;
  surface: string;
  surfaceRaised: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  success: string;
  warning: string;
  danger: string;
}

const LIGHT_FALLBACK: ChartTokens = {
  accent: "#e6a817",
  accentSoft: "#b37a0a",
  neutral: "#3a3630",
  axis: "#7a7468",
  tick: "#3a3630",
  grid: "#e0d9c8",
  surface: "#faf8f2",
  surfaceRaised: "#ffffff",
  textPrimary: "#0a0a08",
  textSecondary: "#3a3630",
  textMuted: "#7a7468",
  success: "#167a3c",
  warning: "#a86a13",
  danger: "#c12a2a",
};

const DARK_FALLBACK: ChartTokens = {
  accent: "#e6a817",
  accentSoft: "#f5d26e",
  neutral: "#d4cec0",
  axis: "#7a7468",
  tick: "#c4beb0",
  grid: "#2b2722",
  surface: "#0a0a08",
  surfaceRaised: "#141210",
  textPrimary: "#f5f0e3",
  textSecondary: "#c4beb0",
  textMuted: "#857f73",
  success: "#38a55c",
  warning: "#e6a817",
  danger: "#e04545",
};

export function useChartTokens(): ChartTokens {
  const { theme } = useTheme();
  return useMemo(() => {
    const fallback = theme === "dark" ? DARK_FALLBACK : LIGHT_FALLBACK;
    if (typeof window === "undefined") return fallback;
    const s = getComputedStyle(document.documentElement);
    const read = (v: string, f: string) =>
      s.getPropertyValue(v).trim() || f;
    return {
      accent: read("--color-accent-500", fallback.accent),
      accentSoft: read("--color-accent-ink", fallback.accentSoft),
      neutral: read("--color-chart-neutral", fallback.neutral),
      axis: read("--color-text-muted", fallback.axis),
      tick: read("--color-text-secondary", fallback.tick),
      grid: read("--color-border", fallback.grid),
      surface: read("--color-surface", fallback.surface),
      surfaceRaised: read("--color-surface-raised", fallback.surfaceRaised),
      textPrimary: read("--color-text-primary", fallback.textPrimary),
      textSecondary: read("--color-text-secondary", fallback.textSecondary),
      textMuted: read("--color-text-muted", fallback.textMuted),
      success: read("--color-success-500", fallback.success),
      warning: read("--color-warning-500", fallback.warning),
      danger: read("--color-danger-500", fallback.danger),
    };
  }, [theme]);
}
