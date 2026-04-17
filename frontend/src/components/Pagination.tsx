interface PaginationProps {
  pagina: number;
  totalPaginas: number;
  onChange: (pagina: number) => void;
}

const ArrowLeft = () => (
  <svg
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="h-3.5 w-3.5"
    aria-hidden
  >
    <path d="M10 12 6 8l4-4" />
  </svg>
);

const ArrowRight = () => (
  <svg
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="h-3.5 w-3.5"
    aria-hidden
  >
    <path d="m6 4 4 4-4 4" />
  </svg>
);

export default function Pagination({
  pagina,
  totalPaginas,
  onChange,
}: PaginationProps) {
  if (totalPaginas <= 1) return null;

  return (
    <nav
      className="flex items-center justify-center gap-2"
      aria-label="Paginação"
    >
      <button
        onClick={() => onChange(Math.max(1, pagina - 1))}
        disabled={pagina === 1}
        className="btn-paginate"
        aria-label="Página anterior"
      >
        <ArrowLeft />
        <span className="hidden sm:inline">Anterior</span>
      </button>
      <span className="px-3 py-1.5 rounded-lg bg-surface-overlay/30 border border-border text-text-muted text-xs font-mono tabular-nums tracking-wider">
        <span className="text-text-primary">{pagina}</span>
        <span className="mx-1.5 text-text-muted/50">/</span>
        <span>{totalPaginas}</span>
      </span>
      <button
        onClick={() => onChange(Math.min(totalPaginas, pagina + 1))}
        disabled={pagina >= totalPaginas}
        className="btn-paginate"
        aria-label="Próxima página"
      >
        <span className="hidden sm:inline">Próximo</span>
        <ArrowRight />
      </button>
    </nav>
  );
}
