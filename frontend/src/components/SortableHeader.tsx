export type SortDirection = "asc" | "desc";

interface SortableHeaderProps<T extends string> {
  column: T;
  label: string;
  sortBy: T;
  direction: SortDirection;
  onSort: (column: T) => void;
  align?: "left" | "right";
}

export default function SortableHeader<T extends string>({
  column,
  label,
  sortBy,
  direction,
  onSort,
  align = "left",
}: SortableHeaderProps<T>) {
  const active = sortBy === column;
  const nextDirection = active && direction === "asc" ? "desc" : "asc";

  return (
    <th
      className={align === "right" ? "text-right" : undefined}
      aria-sort={
        active ? (direction === "asc" ? "ascending" : "descending") : "none"
      }
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        className={`group inline-flex w-full items-center gap-1.5 transition-colors hover:text-text-primary ${
          align === "right" ? "justify-end" : "justify-start"
        } ${active ? "text-text-primary" : ""}`}
        title={`Ordenar ${label} em ordem ${nextDirection === "asc" ? "crescente" : "decrescente"}`}
      >
        <span>{label}</span>
        <span
          className={`font-mono text-[11px] transition-colors ${
            active ? "text-accent-ink" : "text-text-muted group-hover:text-text-secondary"
          }`}
          aria-hidden
        >
          {active ? (direction === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    </th>
  );
}
