interface TableSkeletonProps {
  columns?: number;
  rows?: number;
}

/**
 * Table loading shimmer. Mimics the `.tbl` layout so heights are stable
 * between loading → loaded transitions (avoids jitter).
 *
 * Widths are pseudo-random but deterministic per column index, so rows
 * look natural rather than uniform.
 */
export default function TableSkeleton({
  columns = 4,
  rows = 5,
}: TableSkeletonProps) {
  const columnWidths = Array.from({ length: columns }, (_, i) => {
    // varied widths: wider on first & last, medium in middle
    if (i === 0) return "w-28";
    if (i === columns - 1) return "w-20";
    if (i % 3 === 0) return "w-40";
    if (i % 3 === 1) return "w-24";
    return "w-32";
  });

  return (
    <div
      className="overflow-x-auto"
      aria-busy
      aria-live="polite"
      aria-label="Carregando"
    >
      {/* Header shimmer */}
      <div className="flex min-w-[44rem] gap-6 border-b border-border bg-surface-overlay/60 px-5 py-3">
        {columnWidths.map((w, i) => (
          <div key={i} className={`skeleton h-2.5 ${w}`} />
        ))}
      </div>
      {/* Row shimmer */}
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="flex min-w-[44rem] gap-6 px-5 py-4 border-b border-border/50 last:border-b-0"
          style={{ opacity: 1 - r * 0.08 }}
        >
          {columnWidths.map((w, c) => (
            <div key={c} className={`skeleton h-3.5 ${w}`} />
          ))}
        </div>
      ))}
    </div>
  );
}
