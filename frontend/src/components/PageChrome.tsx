import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: PageHeaderProps) {
  return (
    <header className="relative overflow-hidden rounded-2xl border border-border bg-surface-raised p-4 shadow-[0_18px_60px_rgba(15,23,42,0.08)] sm:p-5 md:p-7">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(720px 260px at 100% 0%, color-mix(in oklab, var(--color-accent-500) 11%, transparent), transparent 68%)",
        }}
        aria-hidden
      />
      <div className="relative flex flex-wrap items-start justify-between gap-5 sm:items-end">
        <div className="max-w-3xl">
          {eyebrow && (
            <p className="mb-2 text-[11px] font-mono uppercase tracking-[0.28em] text-accent-ink">
              {eyebrow}
            </p>
          )}
          <h1 className="font-display text-3xl tracking-tight text-text-primary leading-[1.05] sm:text-4xl md:text-5xl">
            {title}
          </h1>
          <p className="mt-3 text-sm leading-6 text-text-secondary">
            {description}
          </p>
        </div>
        {actions && <div className="w-full shrink-0 sm:w-auto">{actions}</div>}
      </div>
    </header>
  );
}

interface DataSourceStripProps {
  label?: string;
  items: string[];
  note?: ReactNode;
}

function dataSourceColor(item: string): string {
  if (item.includes("RREO")) return "#2f5f8f";
  if (item.includes("RGF") || item.includes("LRF")) return "#a66b1f";
  if (item.includes("IBGE")) return "#207a4f";
  if (item.includes("PNCP")) return "#7a4ea3";
  if (item.includes("SICONFI")) return "#1f7a8c";
  if (item.includes("STN")) return "#5f7666";
  if (item.includes("Município")) return "#b84242";
  return "#667085";
}

export function DataSourceStrip({
  label = "Dados integrados",
  items,
  note,
}: DataSourceStripProps) {
  return (
    <section
      className="rounded-xl border border-border bg-surface-raised/90 px-3.5 py-3 sm:px-4"
      aria-label={label}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-text-muted">
          {label}
        </p>
        <ul className="flex flex-wrap gap-1.5">
          {items.map((item) => {
            const color = dataSourceColor(item);
            return (
              <li key={item}>
                <span
                  className="badge gap-1.5"
                  style={{
                    background: `color-mix(in oklab, ${color} 14%, var(--color-surface-raised))`,
                    borderColor: `color-mix(in oklab, ${color} 55%, var(--color-border))`,
                    color: `color-mix(in oklab, ${color} 76%, var(--color-text-primary))`,
                    boxShadow: `0 5px 16px color-mix(in oklab, ${color} 10%, transparent)`,
                  }}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: color }}
                    aria-hidden
                  />
                  {item}
                </span>
              </li>
            );
          })}
        </ul>
        {note && <p className="w-full text-xs text-text-secondary lg:w-auto">{note}</p>}
      </div>
    </section>
  );
}

interface EmptyStateProps {
  title: string;
  description: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-surface-overlay/45 px-6 py-8 text-center">
      <p className="font-medium text-text-primary">{title}</p>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
