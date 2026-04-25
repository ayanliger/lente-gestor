import { useEffect, useState } from "react";
import type { SituacaoIndicador } from "@/api/types";
import { formatBRL } from "@/lib/format";

interface TermometroProps {
  valor: number | null;
  limite: number | null;
  tipoLimite: "MAXIMO" | "MINIMO";
  situacao: SituacaoIndicador;
  unidade?: "PERCENTUAL" | "MONETARIO";
}

function formatCompactBRL(valor: number): string {
  const abs = Math.abs(valor);
  const sign = valor < 0 ? "-" : "";
  if (abs >= 1_000_000_000)
    return `${sign}R$ ${(abs / 1_000_000_000).toFixed(2)} bi`;
  if (abs >= 1_000_000) return `${sign}R$ ${(abs / 1_000_000).toFixed(2)} mi`;
  if (abs >= 1_000) return `${sign}R$ ${(abs / 1_000).toFixed(1)} mil`;
  return formatBRL(valor);
}

type Tone = {
  fillFrom: string;
  fillTo: string;
  text: string;
  glow: string;
};

const TONES: Record<SituacaoIndicador, Tone> = {
  OK: {
    fillFrom: "#207a4f",
    fillTo: "#4fb178",
    text: "text-success-500",
    glow: "rgba(32,122,79,0.32)",
  },
  ALERTA: {
    fillFrom: "#a66b1f",
    fillTo: "#d39a3a",
    text: "text-warning-500",
    glow: "rgba(166,107,31,0.32)",
  },
  EXCEDIDO: {
    fillFrom: "#b84242",
    fillTo: "#e06a6a",
    text: "text-danger-500",
    glow: "rgba(184,66,66,0.36)",
  },
  ABAIXO_MINIMO: {
    fillFrom: "#b84242",
    fillTo: "#e06a6a",
    text: "text-danger-500",
    glow: "rgba(184,66,66,0.36)",
  },
  SEM_DADO: {
    fillFrom: "#667085",
    fillTo: "#98a2b3",
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

// Dispatcher puro: sem hooks, apenas roteia para o sub-componente certo
// com base na unidade. Evita violar as Rules of Hooks ao
// executar hooks depois de um early return.
export default function Termometro({
  valor,
  limite,
  tipoLimite,
  situacao,
  unidade = "PERCENTUAL",
}: TermometroProps) {
  const tone = TONES[situacao];
  const label = LABEL[situacao];

  if (unidade === "MONETARIO") {
    return (
      <MonetaryTermometro
        valor={valor}
        situacao={situacao}
        tone={tone}
        label={label}
      />
    );
  }

  return (
    <PercentualTermometro
      valor={valor}
      limite={limite}
      tipoLimite={tipoLimite}
      tone={tone}
      label={label}
    />
  );
}

// Variante percentual clássica (MAXIMO com alerta a 90% do limite,
// MINIMO com meta 100%). Fillbar valor/limite clássica.
function PercentualTermometro({
  valor,
  limite,
  tipoLimite,
  tone,
  label,
}: {
  valor: number | null;
  limite: number | null;
  tipoLimite: "MAXIMO" | "MINIMO";
  tone: Tone;
  label: string;
}) {
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
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-surface-overlay border border-border"
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
                "repeating-linear-gradient(135deg, rgba(184,66,66,0.68) 0 3px, rgba(184,66,66,0.28) 3px 6px)",
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

// ---- Variante MONETARIO ----

function MonetaryTermometro({
  valor,
  situacao,
  tone,
  label,
}: {
  valor: number | null;
  situacao: SituacaoIndicador;
  tone: Tone;
  label: string;
}) {
  // Polaridade à esquerda do zero para déficit, à direita para superávit.
  // Normalizamos por |valor| limitado a 100% para evitar barras quilómetricas
  // — o módulo já comunica a magnitude via número exibido acima.
  const [animatedPct, setAnimatedPct] = useState(0);
  const alvo = valor == null ? 0 : Math.min(Math.abs(valor) / 1_000_000, 100);
  useEffect(() => {
    const id = requestAnimationFrame(() => setAnimatedPct(alvo));
    return () => cancelAnimationFrame(id);
  }, [alvo]);

  const positivo = valor != null && valor >= 0;

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] text-text-muted uppercase tracking-[0.18em]">
            {positivo ? "Superávit / suficiência" : "Déficit / insuficiência"}
          </p>
          <p
            className={`font-mono tabular-nums text-2xl font-semibold mt-0.5 ${tone.text}`}
          >
            {valor != null ? formatCompactBRL(valor) : "—"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-text-muted uppercase tracking-[0.18em]">
            {label}
          </p>
          <p className="font-mono tabular-nums text-xs text-text-secondary mt-0.5">
            {situacao === "ABAIXO_MINIMO" ? "abaixo do piso" : "acima do piso"}
          </p>
        </div>
      </div>

      {/* Barra bipolar com marcador central a 0 */}
      <div
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-surface-overlay border border-border"
        role="meter"
        aria-valuenow={valor ?? undefined}
      >
        {/* marcador zero (centro) */}
        <div
          className="absolute top-0 bottom-0 w-px bg-text-muted/50 z-10"
          style={{ left: "50%" }}
          aria-hidden
        />
        {/* preenchimento a partir do centro */}
        <div
          className="absolute top-0 h-full transition-[width] duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{
            left: positivo ? "50%" : `${50 - animatedPct / 2}%`,
            width: `${animatedPct / 2}%`,
            background: `linear-gradient(90deg, ${tone.fillFrom} 0%, ${tone.fillTo} 100%)`,
            boxShadow: `0 0 14px ${tone.glow}`,
          }}
        />
      </div>

      <div className="flex items-center justify-between text-[11px] text-text-secondary font-mono">
        <span>
          Piso legal:{" "}
          <span className="text-text-primary">R$ 0,00</span>
        </span>
        <span className="text-text-muted">0 = equilíbrio</span>
      </div>
    </div>
  );
}
