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
  accent: "#4b5563",
  accentSoft: "#333946",
  neutral: "#4b5563",
  axis: "#7a808a",
  tick: "#474c55",
  grid: "#d9dde3",
  surface: "#f7f7f8",
  surfaceRaised: "#ffffff",
  textPrimary: "#15171a",
  textSecondary: "#474c55",
  textMuted: "#7a808a",
  success: "#207a4f",
  warning: "#a66b1f",
  danger: "#b84242",
};

const DARK_FALLBACK: ChartTokens = {
  accent: "#98a2b3",
  accentSoft: "#d1d5db",
  neutral: "#e5e7eb",
  axis: "#8f96a3",
  tick: "#c6cad0",
  grid: "#2a2f35",
  surface: "#060708",
  surfaceRaised: "#111316",
  textPrimary: "#f3f4f6",
  textSecondary: "#c6cad0",
  textMuted: "#8f96a3",
  success: "#4fb178",
  warning: "#d39a3a",
  danger: "#e06a6a",
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
