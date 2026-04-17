import { useEffect, useState } from "react";
import type { SituacaoIndicador } from "@/api/types";

interface TermometroProps {
  valor: number | null;
  limite: number | null;
  tipoLimite: "MAXIMO" | "MINIMO";
  situacao: SituacaoIndicador;
}

type Tone = {
  fillFrom: string;
  fillTo: string;
  text: string;
  glow: string;
};

const TONES: Record<SituacaoIndicador, Tone> = {
  OK: {
    fillFrom: "#16a34a",
    fillTo: "#4ade80",
    text: "text-success-500",
    glow: "rgba(22,163,74,0.4)",
  },
  ALERTA: {
    fillFrom: "#d97706",
    fillTo: "#fbbf24",
    text: "text-warning-500",
    glow: "rgba(217,119,6,0.4)",
  },
  EXCEDIDO: {
    fillFrom: "#b91c1c",
    fillTo: "#f87171",
    text: "text-danger-500",
    glow: "rgba(220,38,38,0.45)",
  },
  ABAIXO_MINIMO: {
    fillFrom: "#b91c1c",
    fillTo: "#f87171",
    text: "text-danger-500",
    glow: "rgba(220,38,38,0.45)",
  },
  SEM_DADO: {
    fillFrom: "#334155",
    fillTo: "#475569",
    text: "text-text-muted",
    glow: "transparent",
  },
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
  // Percentual bruto valor/limite. Clampado a 115% para visualizar excesso.
  const pctReal =
    valor != null && limite != null && limite > 0
      ? Math.min((valor / limite) * 100, 115)
      : 0;

  // Progresso animado para efeito de preenchimento ao montar.
  const [animatedPct, setAnimatedPct] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setAnimatedPct(pctReal));
    return () => cancelAnimationFrame(id);
  }, [pctReal]);

  const tone = TONES[situacao];
  const label = LABEL[situacao];

  // Razao em relacao ao limite (para o % de destaque).
  const razao =
    valor != null && limite != null && limite > 0 ? valor / limite : null;

  // Marcador de alerta a 90% para MAXIMO, 100% para MINIMO.
  const marcador = tipoLimite === "MAXIMO" ? 90 : 100;

  const excedeu = animatedPct > 100;

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] text-text-muted uppercase tracking-[0.18em]">
            {tipoLimite === "MAXIMO" ? "Limite máximo" : "Mínimo constitucional"}
          </p>
          <p
            className={`font-mono tabular-nums text-2xl font-semibold mt-0.5 ${tone.text}`}
          >
            {valor != null ? `${valor.toFixed(2)}%` : "—"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-text-muted uppercase tracking-[0.18em]">
            {label}
          </p>
          <p className="font-mono tabular-nums text-xs text-text-secondary mt-0.5">
            {razao != null ? `${(razao * 100).toFixed(0)}% do limite` : "—"}
          </p>
        </div>
      </div>

      {/* Barra */}
      <div
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-lente-900/60 border border-border/60"
        role="meter"
        aria-valuenow={valor ?? undefined}
        aria-valuemin={0}
        aria-valuemax={limite ?? undefined}
      >
        {/* marcador a 90%/100% */}
        <div
          className="absolute top-0 bottom-0 w-px bg-text-muted/50 z-10"
          style={{ left: `${Math.min(marcador, 100)}%` }}
          aria-hidden
        />
        {/* preenchimento principal com gradiente */}
        <div
          className="h-full origin-left transition-[width] duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{
            width: `${Math.min(animatedPct, 100)}%`,
            background: `linear-gradient(90deg, ${tone.fillFrom} 0%, ${tone.fillTo} 100%)`,
            boxShadow: `0 0 14px ${tone.glow}`,
          }}
        />
        {/* indicador de excesso: pequena faixa listrada além de 100% */}
        {excedeu && (
          <div
            className="absolute top-0 h-full transition-[width] duration-[900ms] delay-[200ms]"
            style={{
              left: "100%",
              width: `${Math.min(animatedPct - 100, 15)}%`,
              transform: "translateX(-100%)",
              backgroundImage:
                "repeating-linear-gradient(135deg, rgba(220,38,38,0.7) 0 3px, rgba(220,38,38,0.3) 3px 6px)",
              borderLeft: "1px solid rgba(255,255,255,0.4)",
            }}
            aria-hidden
          />
        )}
      </div>

      <div className="flex items-center justify-between text-[11px] text-text-secondary font-mono">
        <span>
          Limite legal:{" "}
          <span className="text-text-primary">
            {limite != null ? `${limite.toFixed(2)}%` : "—"}
          </span>
        </span>
        <span className="text-text-muted">
          {tipoLimite === "MAXIMO" ? "alerta ≥90%" : "meta 100%"}
        </span>
      </div>
    </div>
  );
}
