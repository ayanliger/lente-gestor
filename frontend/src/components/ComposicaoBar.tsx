import { useEffect, useState } from "react";

/**
 * Linha de composição orçamentária — label à esquerda, barra com gradiente
 * que revela o percentual da fatia, valor nominal e % à direita.
 *
 * Projetado para listas de até ~8 itens em colunas verticais. Cor é passada
 * pelo chamador para permitir paletas temáticas (despesa vs receita, etc.).
 */
interface ComposicaoBarProps {
  label: string;
  valor: number;
  pct: number; // 0-100, percentual da fatia sobre o total
  valorFormatado: string;
  color: string; // hex da barra
  delayMs?: number;
}

export default function ComposicaoBar({
  label,
  valor,
  pct,
  valorFormatado,
  color,
  delayMs = 0,
}: ComposicaoBarProps) {
  // Preenchimento animado em duas etapas para efeito de cascata.
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const id = window.setTimeout(() => setWidth(pct), delayMs);
    return () => window.clearTimeout(id);
  }, [pct, delayMs]);

  return (
    <div className="group grid grid-cols-[minmax(9rem,14rem)_1fr_auto] items-center gap-4 py-2.5">
      {/* Label */}
      <div className="min-w-0">
        <p className="text-[13px] text-text-secondary truncate group-hover:text-text-primary transition-colors">
          {label}
        </p>
      </div>

      {/* Track + fill */}
      <div
        className="relative h-2 w-full rounded-full bg-surface-overlay/40 overflow-hidden"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${label}: ${valorFormatado} (${pct.toFixed(1)}%)`}
      >
        {/* barra principal com gradiente: saturado -> transparente */}
        <div
          className="h-full origin-left rounded-full transition-[width] duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{
            width: `${Math.min(width, 100)}%`,
            background: `linear-gradient(90deg, ${color} 0%, ${color}99 70%, ${color}55 100%)`,
            boxShadow: `0 0 12px ${color}44`,
          }}
        />
        {/* brilho sutil deslizando no hover */}
        <div
          className="pointer-events-none absolute inset-y-0 left-0 w-full opacity-0 group-hover:opacity-100 transition-opacity"
          style={{
            background: `linear-gradient(90deg, transparent 0%, ${color}22 50%, transparent 100%)`,
            mixBlendMode: "screen",
          }}
          aria-hidden
        />
      </div>

      {/* Values */}
      <div className="flex items-baseline gap-2 font-mono tabular-nums text-right whitespace-nowrap">
        <span className="text-text-primary text-sm font-medium">
          {valorFormatado}
        </span>
        <span
          className="text-[11px] text-text-muted"
          style={{ minWidth: "3.2rem" }}
        >
          ({pct.toFixed(1)}%)
        </span>
      </div>

      <span className="sr-only">
        {/* fallback to assistive tech; redundant but explicit */}
        valor: {valor}
      </span>
    </div>
  );
}
