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
    <header className="relative overflow-hidden rounded-2xl border border-border bg-surface-raised p-6 md:p-7 shadow-[0_18px_60px_rgba(7,24,38,0.07)]">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(720px 260px at 100% 0%, rgba(34,168,213,0.13), transparent 68%)",
        }}
        aria-hidden
      />
      <div className="relative flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-3xl">
          {eyebrow && (
            <p className="mb-2 text-[11px] font-mono uppercase tracking-[0.28em] text-accent-ink">
              {eyebrow}
            </p>
          )}
          <h1 className="font-display text-4xl md:text-5xl tracking-tight text-text-primary leading-[1.05]">
            {title}
          </h1>
          <p className="mt-3 text-sm leading-6 text-text-secondary">
            {description}
          </p>
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
    </header>
  );
}

interface DataSourceStripProps {
  label?: string;
  items: string[];
  note?: ReactNode;
}

export function DataSourceStrip({
  label = "Dados integrados",
  items,
  note,
}: DataSourceStripProps) {
  return (
    <section
      className="rounded-xl border border-border bg-surface-raised/90 px-4 py-3"
      aria-label={label}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-text-muted">
          {label}
        </p>
        <ul className="flex flex-wrap gap-1.5">
          {items.map((item) => (
            <li key={item}>
              <span className="badge badge-accent">{item}</span>
            </li>
          ))}
        </ul>
        {note && <p className="text-xs text-text-secondary">{note}</p>}
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
