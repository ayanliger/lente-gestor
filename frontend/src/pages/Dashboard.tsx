import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  useContratos,
  useContratosVencendo,
  useDadosMunicipio,
  useExerciciosOrcamento,
  useFornecedores,
  useIndicadoresFiscais,
  useResumoFuncao,
} from "@/api/hooks";
import type { IndicadorFiscal } from "@/api/types";
import ComposicaoBar from "@/components/ComposicaoBar";
import { formatBRL } from "@/lib/format";
import { useChartTokens, type ChartTokens } from "@/lib/theme";

// Paleta para a composição de despesa — derivada dos tokens do tema:
// âmbar (acento), neutro escuro, semânticos e variações neutras. Todas
// trocam automaticamente entre light/dark via `useChartTokens`.
function paletaDespesa(t: ChartTokens): string[] {
  return [
    t.accent, // destaque #1 — âmbar
    t.neutral, // neutro de alto contraste
    t.success, // verde semântico
    t.warning, // laranja semântico
    t.textSecondary, // cinza médio
    t.textMuted, // cinza suave
  ];
}

const BIMESTRES = [1, 2, 3, 4, 5, 6];

function formatCompactBRL(valor: number | null | undefined): string {
  if (valor == null) return "—";
  if (valor >= 1_000_000_000) return `R$ ${(valor / 1_000_000_000).toFixed(2)} bi`;
  if (valor >= 1_000_000) return `R$ ${(valor / 1_000_000).toFixed(1)} mi`;
  if (valor >= 1_000) return `R$ ${(valor / 1_000).toFixed(1)} mil`;
  return formatBRL(valor);
}

function HeroKpi({
  label,
  value,
  sub,
  accentColor,
  valueTone,
}: {
  label: string;
  value: string;
  sub?: string;
  accentColor: string;
  valueTone?: string;
}) {
  return (
    <div
      className="relative rounded-xl p-6 border bg-surface-raised border-border overflow-hidden transition-colors hover:border-accent-500/40"
    >
      {/* barra superior colorida identificando a métrica */}
      <span
        className="absolute inset-x-0 top-0 h-[2px]"
        style={{
          background: `linear-gradient(90deg, transparent 0%, ${accentColor} 50%, transparent 100%)`,
        }}
        aria-hidden
      />
      <p className="text-text-muted text-[10px] uppercase tracking-[0.18em] mb-3">
        {label}
      </p>
      <p
        className={`font-mono tabular-nums text-[2.4rem] leading-none font-semibold ${
          valueTone ?? "text-text-primary"
        }`}
      >
        {value}
      </p>
      {sub && (
        <p className="text-xs text-text-secondary mt-3 leading-snug">
          {sub}
        </p>
      )}
    </div>
  );
}

function AlertRow({
  tone,
  title,
  detail,
}: {
  tone: "danger" | "warning";
  title: string;
  detail: string;
}) {
  const classes =
    tone === "danger"
      ? "border-danger-500/30 bg-danger-500/[0.06]"
      : "border-warning-500/30 bg-warning-500/[0.06]";
  const dot =
    tone === "danger" ? "bg-danger-500" : "bg-warning-500";
  const titleColor =
    tone === "danger" ? "text-danger-500" : "text-warning-500";

  return (
    <div
      className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${classes}`}
    >
      <span
        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot}`}
        aria-hidden
      />
      <div className="min-w-0">
        <p className={`text-sm font-medium ${titleColor}`}>{title}</p>
        <p className="text-[12.5px] text-text-secondary mt-0.5 leading-snug">
          {detail}
        </p>
      </div>
    </div>
  );
}

interface AlertaItem {
  tone: "danger" | "warning";
  title: string;
  detail: string;
  key: string;
}

function derivarAlertas(
  indicadores: IndicadorFiscal[] | undefined,
  vencendo: number,
): AlertaItem[] {
  const lista: AlertaItem[] = [];
  for (const ind of indicadores ?? []) {
    if (ind.situacao === "EXCEDIDO") {
      lista.push({
        tone: "danger",
        title: `${ind.descricao}: limite ultrapassado`,
        detail: `Valor apurado ${ind.valor?.toFixed(2) ?? "—"}% contra limite de ${ind.limite_legal?.toFixed(2) ?? "—"}%.`,
        key: `excedido-${ind.id}`,
      });
    } else if (ind.situacao === "ABAIXO_MINIMO") {
      lista.push({
        tone: "danger",
        title: `${ind.descricao}: abaixo do mínimo constitucional`,
        detail: `Aplicação em ${ind.valor?.toFixed(2) ?? "—"}% (mínimo ${ind.limite_legal?.toFixed(2) ?? "—"}%).`,
        key: `abaixo-${ind.id}`,
      });
    } else if (ind.situacao === "ALERTA") {
      lista.push({
        tone: "warning",
        title: `${ind.descricao}: próximo do limite`,
        detail: `Valor ${ind.valor?.toFixed(2) ?? "—"}% — monitorar para evitar extrapolação.`,
        key: `alerta-${ind.id}`,
      });
    }
  }
  if (vencendo > 0) {
    lista.push({
      tone: "warning",
      title: `${vencendo} contrato(s) vencendo em 90 dias`,
      detail: "Avalie prorrogação, substituição ou encerramento antes do fim da vigência.",
      key: "vencendo",
    });
  }
  return lista;
}

function StatTileLink({
  to,
  label,
  value,
  hint,
}: {
  to: string;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Link
      to={to}
      className="group flex flex-col justify-between gap-3 rounded-lg border border-border bg-surface-raised px-4 py-4 transition-colors hover:border-accent-500/40 hover:bg-surface-overlay"
    >
      <div>
        <p className="text-text-muted text-[10px] uppercase tracking-[0.18em]">
          {label}
        </p>
        <p className="mt-2 font-mono tabular-nums text-2xl text-text-primary">
          {value}
        </p>
      </div>
      <p className="text-[11.5px] text-text-secondary flex items-center gap-1 group-hover:text-text-primary transition-colors">
        {hint}
        <span
          className="transition-transform group-hover:translate-x-0.5"
          aria-hidden
        >
          →
        </span>
      </p>
    </Link>
  );
}

export default function Dashboard() {
  const exerciciosQuery = useExerciciosOrcamento();
  const exerciciosDisponiveis = exerciciosQuery.data ?? [];
  const [exercicio, setExercicio] = useState<number | undefined>(undefined);
  const [periodo, setPeriodo] = useState<number | undefined>(undefined);

  const anoSelecionado = exercicio ?? exerciciosDisponiveis[0];

  // Orçamento é a fonte primária.
  const resumo = useResumoFuncao(anoSelecionado ?? 0, periodo);
  const indicadores = useIndicadoresFiscais({ exercicio: anoSelecionado });
  const municipio = useDadosMunicipio(anoSelecionado ?? 0);

  // Contratos entram como painel secundário.
  const contratos = useContratos({ tamanho_pagina: 1 });
  const fornecedores = useFornecedores({ tamanho_pagina: 1 });
  const vencendo = useContratosVencendo(90);

  const tokens = useChartTokens();
  const paleta = useMemo(() => paletaDespesa(tokens), [tokens]);

  const { totais, composicao } = useMemo(() => {
    const dados = resumo.data ?? [];
    const totalDotacao = dados.reduce(
      (acc, d) => acc + (d.dotacao_atualizada ?? 0),
      0,
    );
    const totalEmpenhado = dados.reduce(
      (acc, d) => acc + (d.empenhado ?? 0),
      0,
    );
    const totalLiquidado = dados.reduce(
      (acc, d) => acc + (d.liquidado ?? 0),
      0,
    );

    // Top 6 por empenhado + "Outros" agregado.
    const ordenadas = [...dados]
      .filter((d) => (d.empenhado ?? 0) > 0)
      .sort((a, b) => (b.empenhado ?? 0) - (a.empenhado ?? 0));
    const top = ordenadas.slice(0, 6);
    const outros = ordenadas.slice(6);
    const totalOutros = outros.reduce(
      (acc, d) => acc + (d.empenhado ?? 0),
      0,
    );

    const composicao = top.map((d, i) => ({
      label: d.funcao,
      valor: d.empenhado ?? 0,
      color: paleta[i % paleta.length],
    }));
    if (totalOutros > 0) {
      composicao.push({
        label: `Outros (${outros.length})`,
        valor: totalOutros,
        color: tokens.textMuted,
      });
    }

    return {
      totais: {
        dotacao: totalDotacao,
        empenhado: totalEmpenhado,
        liquidado: totalLiquidado,
        saldo: totalDotacao - totalEmpenhado,
        pctExecucao: totalDotacao > 0 ? (totalEmpenhado / totalDotacao) * 100 : 0,
      },
      composicao,
    };
  }, [resumo.data, paleta, tokens]);

  const alertas = useMemo(
    () => derivarAlertas(indicadores.data, vencendo.data?.total ?? 0),
    [indicadores.data, vencendo.data?.total],
  );

  const execTone =
    totais.pctExecucao === 0
      ? "text-text-muted"
      : totais.pctExecucao > 100
        ? "text-danger-500"
        : totais.pctExecucao >= 90
          ? "text-warning-500"
          : totais.pctExecucao >= 60
            ? "text-success-500"
            : "text-accent-ink";

  const totalComposicao = composicao.reduce((a, b) => a + b.valor, 0);
  const loadingOrcamento = resumo.isLoading;

  const dadosMun = municipio.data;
  const periodoLabel = periodo
    ? `Bimestre ${periodo}`
    : resumo.data?.length
      ? "bimestre mais recente"
      : null;

  return (
    <div className="space-y-10 animate-fade-up">
      {/* Header + filtros */}
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-accent-ink mb-2">
            Painel Municipal
          </p>
          <h1 className="font-display text-4xl md:text-5xl tracking-tight text-text-primary leading-[1.05]">
            Visão Geral
          </h1>
          <p className="text-text-secondary text-sm mt-3 max-w-2xl">
            Execução orçamentária, indicadores fiscais e contratos de{" "}
            {dadosMun?.nome_municipio ?? "Jequié"} ({dadosMun?.uf ?? "BA"})
            {periodoLabel ? (
              <>
                <span className="text-text-muted"> · </span>
                <span className="font-mono text-text-primary">
                  {anoSelecionado ?? "—"}
                </span>
                <span className="text-text-muted"> · {periodoLabel}</span>
              </>
            ) : null}
            .
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
              Exercício
            </span>
            <select
              value={anoSelecionado ?? ""}
              onChange={(e) => {
                setExercicio(Number(e.target.value));
                setPeriodo(undefined);
              }}
              className="field-select"
              disabled={exerciciosDisponiveis.length === 0}
            >
              {exerciciosDisponiveis.length === 0 && (
                <option value="">—</option>
              )}
              {exerciciosDisponiveis.map((ano) => (
                <option key={ano} value={ano}>
                  {ano}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
              Bimestre
            </span>
            <select
              value={periodo ?? ""}
              onChange={(e) =>
                setPeriodo(
                  e.target.value === "" ? undefined : Number(e.target.value),
                )
              }
              className="field-select"
            >
              <option value="">Mais recente</option>
              {BIMESTRES.map((b) => (
                <option key={b} value={b}>
                  B{b}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {/* Hero KPIs */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <HeroKpi
          label="Dotação atualizada"
          value={loadingOrcamento ? "—" : formatCompactBRL(totais.dotacao)}
          sub="Orçamento aprovado até o bimestre"
          accentColor={tokens.neutral}
        />
        <HeroKpi
          label="Empenhado"
          value={loadingOrcamento ? "—" : formatCompactBRL(totais.empenhado)}
          sub={
            loadingOrcamento
              ? "—"
              : `Liquidado: ${formatCompactBRL(totais.liquidado)}`
          }
          accentColor={tokens.accent}
          valueTone="text-accent-ink"
        />
        <HeroKpi
          label="Execução orçamentária"
          value={
            loadingOrcamento || totais.dotacao === 0
              ? "—"
              : `${totais.pctExecucao.toFixed(1)}%`
          }
          sub={
            loadingOrcamento
              ? "—"
              : `Saldo a executar: ${formatCompactBRL(totais.saldo)}`
          }
          accentColor={tokens.success}
          valueTone={execTone}
        />
      </section>

      {/* Composição da Despesa + LRF strip em duas colunas no desktop */}
      <section className="grid grid-cols-1 xl:grid-cols-[1.6fr_1fr] gap-5">
        {/* Composição da despesa por função */}
        <div className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <div className="flex items-baseline justify-between mb-4">
            <div>
              <h2 className="font-display text-xl text-text-primary leading-none">
                Composição da despesa
              </h2>
              <p className="text-xs text-text-muted mt-1.5">
                Empenhado por função de governo · top 6 + agregado
              </p>
            </div>
            <Link
              to="/orcamento"
              className="text-[11px] font-mono uppercase tracking-wider text-text-secondary hover:text-accent-ink transition-colors"
            >
              ver detalhado →
            </Link>
          </div>

          {loadingOrcamento ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : composicao.length === 0 ? (
            <p className="text-text-muted text-sm py-8">
              Sem execução registrada para {anoSelecionado ?? "—"}
              {periodo ? ` · B${periodo}` : ""}.
            </p>
          ) : (
            <div className="divide-y divide-border/40">
              {composicao.map((linha, i) => {
                const pct =
                  totalComposicao > 0
                    ? (linha.valor / totalComposicao) * 100
                    : 0;
                return (
                  <ComposicaoBar
                    key={linha.label}
                    label={linha.label}
                    valor={linha.valor}
                    pct={pct}
                    valorFormatado={formatCompactBRL(linha.valor)}
                    color={linha.color}
                    delayMs={i * 70}
                  />
                );
              })}
            </div>
          )}
        </div>

        {/* Indicadores LRF resumidos */}
        <div className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <div className="flex items-baseline justify-between mb-4">
            <div>
              <h2 className="font-display text-xl text-text-primary leading-none">
                Situação fiscal
              </h2>
              <p className="text-xs text-text-muted mt-1.5">
                Indicadores LRF · aplicação constitucional
              </p>
            </div>
            <Link
              to="/lrf"
              className="text-[11px] font-mono uppercase tracking-wider text-text-secondary hover:text-accent-ink transition-colors"
            >
              abrir →
            </Link>
          </div>

          {indicadores.isLoading ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : (indicadores.data ?? []).length === 0 ? (
            <p className="text-text-muted text-sm py-8">
              Sem indicadores derivados para {anoSelecionado ?? "—"}.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {indicadores.data!.map((ind) => {
                const tone =
                  ind.situacao === "OK"
                    ? { bg: "bg-success-500/10", border: "border-success-500/30", text: "text-success-500" }
                    : ind.situacao === "ALERTA"
                      ? { bg: "bg-warning-500/10", border: "border-warning-500/30", text: "text-warning-500" }
                      : ind.situacao === "EXCEDIDO" || ind.situacao === "ABAIXO_MINIMO"
                        ? { bg: "bg-danger-500/10", border: "border-danger-500/30", text: "text-danger-500" }
                        : { bg: "bg-surface-overlay", border: "border-border", text: "text-text-muted" };
                const pctLimite =
                  ind.valor != null && ind.limite_legal && ind.limite_legal > 0
                    ? (ind.valor / ind.limite_legal) * 100
                    : null;
                return (
                  <li
                    key={ind.id}
                    className={`rounded-lg border px-3.5 py-2.5 ${tone.bg} ${tone.border}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-[13px] text-text-primary leading-tight">
                        {ind.descricao}
                      </p>
                      <span
                        className={`font-mono tabular-nums text-sm font-semibold shrink-0 ${tone.text}`}
                      >
                        {ind.valor != null ? `${ind.valor.toFixed(1)}%` : "—"}
                      </span>
                    </div>
                    {ind.limite_legal != null && (
                      <p className="text-[10.5px] text-text-muted mt-1 font-mono">
                        limite {ind.limite_legal.toFixed(1)}%
                        {pctLimite != null
                          ? ` · ${pctLimite.toFixed(0)}% do teto`
                          : ""}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      {/* Alertas */}
      {alertas.length > 0 && (
        <section className="rounded-xl border border-danger-500/25 bg-danger-500/[0.05] p-6">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="font-display text-xl text-text-primary leading-none flex items-center gap-3">
              <span
                className="inline-block h-2 w-2 rounded-full bg-danger-500 shadow-[0_0_10px_rgba(220,38,38,0.6)]"
                aria-hidden
              />
              Alertas
            </h2>
            <span className="text-[11px] font-mono uppercase tracking-wider text-text-muted">
              {alertas.length} item(ns)
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {alertas.map((a) => (
              <AlertRow
                key={a.key}
                tone={a.tone}
                title={a.title}
                detail={a.detail}
              />
            ))}
          </div>
        </section>
      )}

      {/* Contratos & aquisições — secundário */}
      <section>
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-display text-lg text-text-secondary">
            Contratos &amp; aquisições
          </h2>
          <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-text-muted">
            Fonte: PNCP
          </span>
        </div>
        <div className="divider-engraved mb-4" />
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <StatTileLink
            to="/contratos"
            label="Contratos firmados"
            value={contratos.data ? contratos.data.total.toLocaleString("pt-BR") : "—"}
            hint="abrir lista"
          />
          <StatTileLink
            to="/fornecedores"
            label="Fornecedores"
            value={
              fornecedores.data
                ? fornecedores.data.total.toLocaleString("pt-BR")
                : "—"
            }
            hint="abrir cadastro"
          />
          <StatTileLink
            to="/contratos"
            label="Vencendo em 90 dias"
            value={
              vencendo.data ? vencendo.data.total.toLocaleString("pt-BR") : "—"
            }
            hint="revisar vigências"
          />
        </div>
      </section>
    </div>
  );
}
