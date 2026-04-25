import { createContext, useContext, useMemo } from "react";

export type Theme = "light" | "dark";

export const STORAGE_KEY = "lente:theme";

export interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  const prefersDark = window.matchMedia?.(
    "(prefers-color-scheme: dark)",
  ).matches;
  return prefersDark ? "dark" : "light";
}

export function applyThemeAttribute(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") {
    root.setAttribute("data-theme", "dark");
  } else {
    root.removeAttribute("data-theme");
  }
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme precisa estar dentro de <ThemeProvider>.");
  }
  return ctx;
}

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
  accent: "#22a8d5",
  accentSoft: "#075b7d",
  neutral: "#3f3f46",
  axis: "#71717a",
  tick: "#3f3f46",
  grid: "#d7d7dc",
  surface: "#f7f7f8",
  surfaceRaised: "#ffffff",
  textPrimary: "#111111",
  textSecondary: "#3f3f46",
  textMuted: "#71717a",
  success: "#16844a",
  warning: "#b97316",
  danger: "#c83737",
};

const DARK_FALLBACK: ChartTokens = {
  accent: "#22a8d5",
  accentSoft: "#8be4fb",
  neutral: "#e5e5e5",
  axis: "#a3a3a3",
  tick: "#d4d4d4",
  grid: "#303030",
  surface: "#050505",
  surfaceRaised: "#111111",
  textPrimary: "#f5f5f5",
  textSecondary: "#d4d4d4",
  textMuted: "#a3a3a3",
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
