import type { SituacaoIndicador } from "@/api/types";

interface TermometroProps {
  valor: number | null;
  limite: number | null;
  tipoLimite: "MAXIMO" | "MINIMO";
  situacao: SituacaoIndicador;
}

const COR_FILL: Record<SituacaoIndicador, string> = {
  OK: "bg-success-500",
  ALERTA: "bg-warning-500",
  EXCEDIDO: "bg-danger-500",
  ABAIXO_MINIMO: "bg-danger-500",
  SEM_DADO: "bg-text-muted/40",
};

const COR_TEXT: Record<SituacaoIndicador, string> = {
  OK: "text-success-500",
  ALERTA: "text-warning-500",
  EXCEDIDO: "text-danger-500",
  ABAIXO_MINIMO: "text-danger-500",
  SEM_DADO: "text-text-muted",
};

const LABEL: Record<SituacaoIndicador, string> = {
  OK: "OK",
  ALERTA: "Alerta",
  EXCEDIDO: "Excedido",
  ABAIXO_MINIMO: "Abaixo do mínimo",
  SEM_DADO: "Sem dado",
};

export default function Termometro({
  valor,
  limite,
  tipoLimite,
  situacao,
}: TermometroProps) {
  // Percentual da barra baseado em valor/limite. Clampado entre 0 e 115%
  // (para destacar visualmente quando excedeu).
  const pct =
    valor != null && limite != null && limite > 0
      ? Math.min((valor / limite) * 100, 115)
      : 0;

  const fillClass = COR_FILL[situacao];
  const textClass = COR_TEXT[situacao];
  const label = LABEL[situacao];

  // Marcador de alerta a 90% para MAXIMO, a 100% para MINIMO.
  const marcador = tipoLimite === "MAXIMO" ? 90 : 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-muted uppercase tracking-wider">
          {tipoLimite === "MAXIMO" ? "Limite máximo" : "Mínimo constitucional"}
        </span>
        <span className={`${textClass} font-semibold`}>{label}</span>
      </div>

      {/* Barra */}
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-surface-overlay">
        {/* marcador 90%/100% */}
        <div
          className="absolute top-0 h-full w-px bg-text-muted/60"
          style={{ left: `${Math.min(marcador, 100)}%` }}
          aria-hidden
        />
        {/* preenchimento */}
        <div
          className={`h-full ${fillClass} transition-all duration-500`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-text-secondary font-mono">
        <span>
          Atual:{" "}
          <span className="text-text-primary">
            {valor != null ? `${valor.toFixed(2)}%` : "—"}
          </span>
        </span>
        <span>
          Limite:{" "}
          <span className="text-text-primary">
            {limite != null ? `${limite.toFixed(2)}%` : "—"}
          </span>
        </span>
      </div>
    </div>
  );
}
