import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "@/lib/theme";

type NavIcon = (props: { className?: string }) => React.ReactElement;

const IconSun: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </svg>
);

const IconMoon: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
  </svg>
);

const IconChat: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z" />
    <path d="M8 11h.01M12 11h.01M16 11h.01" />
  </svg>
);

const IconOverview: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </svg>
);

const IconBudget: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M4 20V10" />
    <path d="M10 20V4" />
    <path d="M16 20v-8" />
    <path d="M22 20H2" />
  </svg>
);

const IconLRF: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M14 14.76V4a2 2 0 1 0-4 0v10.76a5 5 0 1 0 4 0Z" />
    <circle cx="12" cy="17" r="1.6" fill="currentColor" stroke="none" />
  </svg>
);

const IconProcurement: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M8 3h9l3 4v13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
    <path d="M4 7v13a1 1 0 0 0 1 1h2" />
    <path d="M10 11h7" />
    <path d="M10 15h7" />
    <path d="M10 19h4" />
  </svg>
);

const IconContract: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M7 3h7l5 5v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6" />
    <path d="M9 17h4" />
  </svg>
);

const IconSupplier: NavIcon = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M3 21V7l6-4 6 4v14" />
    <path d="M15 10h6v11H3" />
    <path d="M8 11h2" />
    <path d="M8 15h2" />
    <path d="M8 19h2" />
    <path d="M18 14h.01" />
    <path d="M18 18h.01" />
  </svg>
);

type NavLinkDef = { to: string; label: string; Icon: NavIcon };

// Navegação organizada em dois grupos: Orçamento é o foco principal da
// ferramenta; contratos/fornecedores são dados complementares.
const navGroups: { heading: string; tone: "primary" | "secondary"; links: NavLinkDef[] }[] = [
  {
    heading: "Orçamento",
    tone: "primary",
    links: [
      { to: "/", label: "Visão Geral", Icon: IconOverview },
      { to: "/assistente", label: "Assistente", Icon: IconChat },
      { to: "/orcamento", label: "Execução", Icon: IconBudget },
      { to: "/lrf", label: "Indicadores LRF", Icon: IconLRF },
    ],
  },
  {
    heading: "Contratos & Aquisições",
    tone: "secondary",
    links: [
      { to: "/contratacoes", label: "Contratações", Icon: IconProcurement },
      { to: "/contratos", label: "Contratos", Icon: IconContract },
      { to: "/fornecedores", label: "Fornecedores", Icon: IconSupplier },
    ],
  },
];

export default function Layout() {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 bg-surface-raised border-r border-border flex flex-col relative">
        {/* acento ambiente — aura âmbar muito sutil no canto superior */}
        <div
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            backgroundImage:
              "radial-gradient(540px 260px at 0% 0%, rgba(230,168,23,0.08), transparent 70%)",
          }}
          aria-hidden
        />

        <div className="relative p-6 border-b border-border">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-3xl leading-none text-accent-ink">
              Lente
            </span>
            <span
              className="h-1.5 w-1.5 rounded-full bg-accent-500"
              aria-hidden
            />
          </div>
          <p className="text-[11px] text-text-muted mt-2 uppercase tracking-[0.2em] font-mono">
            Gestor Municipal
          </p>
        </div>

        <nav className="relative flex-1 p-3 overflow-y-auto">
          {navGroups.map((group, groupIdx) => {
            const isSecondary = group.tone === "secondary";
            return (
              <div
                key={group.heading}
                className={groupIdx > 0 ? "mt-6 pt-5 border-t border-border" : ""}
              >
                <p
                  className={`px-4 mb-2 text-[10px] font-mono uppercase tracking-[0.22em] ${
                    isSecondary ? "text-text-muted" : "text-accent-ink"
                  }`}
                >
                  {group.heading}
                </p>
                <ul className="space-y-0.5">
                  {group.links.map(({ to, label, Icon }) => (
                    <li key={to}>
                      <NavLink
                        to={to}
                        end={to === "/"}
                        className={({ isActive }) =>
                          `group relative flex items-center gap-3 pl-4 pr-3 rounded-lg transition-colors ${
                            isSecondary ? "py-2 text-[13px]" : "py-2.5 text-sm"
                          } ${
                            isActive
                              ? "bg-surface-overlay text-text-primary font-medium"
                              : "text-text-secondary hover:bg-surface-overlay hover:text-text-primary"
                          }`
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <span
                              className={`absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r-full transition-colors ${
                                isActive
                                  ? "bg-accent-500 shadow-[0_0_10px_rgba(230,168,23,0.45)]"
                                  : "bg-transparent group-hover:bg-accent-500/50"
                              }`}
                              aria-hidden
                            />
                            <Icon
                              className={`shrink-0 transition-colors ${
                                isSecondary ? "h-3.5 w-3.5" : "h-4 w-4"
                              } ${
                                isActive
                                  ? "text-accent-500"
                                  : "text-text-muted group-hover:text-text-secondary"
                              }`}
                            />
                            <span className="truncate">{label}</span>
                          </>
                        )}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className="relative p-4 border-t border-border space-y-3">
          <div>
            <p className="text-[10px] text-text-muted uppercase tracking-[0.2em] font-mono">
              Município
            </p>
            <p className="text-sm text-text-primary font-medium">
              Jequié <span className="text-text-muted font-normal">· BA</span>
            </p>
          </div>
          <button
            type="button"
            onClick={toggle}
            aria-label={isDark ? "Mudar para tema claro" : "Mudar para tema escuro"}
            aria-pressed={isDark}
            className="group w-full flex items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-[11px] font-mono uppercase tracking-[0.18em] text-text-muted transition-colors hover:border-accent-500/40 hover:text-text-primary"
          >
            <span className="flex items-center gap-2">
              {isDark ? (
                <IconMoon className="h-3.5 w-3.5 text-accent-500" />
              ) : (
                <IconSun className="h-3.5 w-3.5 text-accent-500" />
              )}
              <span>{isDark ? "escuro" : "claro"}</span>
            </span>
            <span
              className="text-text-muted group-hover:text-accent-ink transition-colors"
              aria-hidden
            >
              {isDark ? "→ claro" : "→ escuro"}
            </span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-8 lg:p-10">
        <Outlet />
      </main>
    </div>
  );
}
