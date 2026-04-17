import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Visão Geral", icon: "◉" },
  { to: "/contratacoes", label: "Contratações", icon: "📋" },
  { to: "/contratos", label: "Contratos", icon: "📄" },
  { to: "/fornecedores", label: "Fornecedores", icon: "🏢" },
];

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 bg-lente-900 border-r border-border flex flex-col">
        <div className="p-6 border-b border-border">
          <h1 className="text-xl font-bold tracking-tight text-accent-400">
            Lente
          </h1>
          <p className="text-xs text-text-muted mt-1">Gestor Municipal</p>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {links.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-lente-700 text-text-primary font-medium"
                    : "text-text-secondary hover:bg-lente-800 hover:text-text-primary"
                }`
              }
            >
              <span className="text-base">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-border">
          <p className="text-xs text-text-muted">Jequié — BA</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-surface p-8">
        <Outlet />
      </main>
    </div>
  );
}
