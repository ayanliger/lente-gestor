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
import {
  DataSourceStrip,
  EmptyState,
  PageHeader,
} from "@/components/PageChrome";
import { formatBRL } from "@/lib/format";
import { useChartTokens, type ChartTokens } from "@/lib/theme-core";

// Paleta para a composição de despesa — derivada dos tokens do tema:
// ciano (acento), neutro escuro, semânticos e variações neutras. Todas
// trocam automaticamente entre light/dark via `useChartTokens`.
function paletaDespesa(t: ChartTokens): string[] {
  return [
    t.accent, // destaque #1 — ciano
    t.neutral, // neutro de alto contraste
    t.success, // verde semântico
    t.warning, // laranja semântico
    t.textSecondary, // cinza médio
    t.textMuted, // cinza suave
  ];
}

const BIMESTRES = [1, 2, 3, 4, 5, 6];
const SEMESTRES = [
  { valor: 1, periodo: 3, label: "1º semestre" },
  { valor: 2, periodo: 6, label: "2º semestre" },
] as const;

type VisaoPeriodo = "anual" | "semestral" | "bimestral";

function periodoConsulta(
  visao: VisaoPeriodo,
  bimestre: number | undefined,
  semestre: 1 | 2,
): number | undefined {
  if (visao === "bimestral") return bimestre;
  if (visao === "semestral") return semestre === 1 ? 3 : 6;
  return undefined;
}

function rotuloPeriodo(
  visao: VisaoPeriodo,
  bimestre: number | undefined,
  semestre: 1 | 2,
): string {
  if (visao === "anual") return "anual acumulado";
  if (visao === "semestral") {
    const periodo = semestre === 1 ? 3 : 6;
    return `${semestre}º semestre · até B${periodo}`;
  }
  return bimestre ? `Bimestre ${bimestre}` : "bimestre mais recente";
}

function formatCompactBRL(valor: number | null | undefined): string {
  if (valor == null) return "—";
  if (valor >= 1_000_000_000) return `R$ ${(valor / 1_000_000_000).toFixed(2)} bi`;
  if (valor >= 1_000_000) return `R$ ${(valor / 1_000_000).toFixed(1)} mi`;
  if (valor >= 1_000) return `R$ ${(valor / 1_000).toFixed(1)} mil`;
  return formatBRL(valor);
}
function indicadorEhMonetario(ind: IndicadorFiscal): boolean {
  return ind.unidade === "MONETARIO";
}

function indicadorUsaPiso(ind: IndicadorFiscal): boolean {
  return indicadorEhMonetario(ind) || ind.codigo.startsWith("APLIC_MIN");
}

function formatIndicadorValor(ind: IndicadorFiscal): string {
  if (ind.valor == null) return "—";
  if (indicadorEhMonetario(ind)) return formatCompactBRL(ind.valor);
  return `${ind.valor.toFixed(1)}%`;
}

function formatIndicadorLimite(ind: IndicadorFiscal): string | null {
  if (ind.limite_legal == null) return null;
  const rotulo = indicadorUsaPiso(ind) ? "piso" : "limite";
  const valor = indicadorEhMonetario(ind)
    ? formatCompactBRL(ind.limite_legal)
    : `${ind.limite_legal.toFixed(1)}%`;
  return `${rotulo} ${valor}`;
}

function formatIndicadorRazaoLimite(ind: IndicadorFiscal): string | null {
  if (ind.valor == null || ind.limite_legal == null || ind.limite_legal <= 0) {
    return null;
  }
  const pct = (ind.valor / ind.limite_legal) * 100;
  return `${pct.toFixed(0)}% do ${indicadorUsaPiso(ind) ? "mínimo" : "teto"}`;
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
        detail: `Valor apurado ${formatIndicadorValor(ind)} contra ${formatIndicadorLimite(ind) ?? "limite —"}.`,
        key: `excedido-${ind.id}`,
      });
    } else if (ind.situacao === "ABAIXO_MINIMO") {
      lista.push({
        tone: "danger",
        title: `${ind.descricao}: abaixo do mínimo constitucional`,
        detail: `Valor apurado ${formatIndicadorValor(ind)} (${formatIndicadorLimite(ind) ?? "piso —"}).`,
        key: `abaixo-${ind.id}`,
      });
    } else if (ind.situacao === "ALERTA") {
      lista.push({
        tone: "warning",
        title: `${ind.descricao}: próximo do limite`,
        detail: `Valor ${formatIndicadorValor(ind)} — monitorar para evitar extrapolação.`,
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
  const [visaoPeriodo, setVisaoPeriodo] = useState<VisaoPeriodo>("anual");
  const [periodo, setPeriodo] = useState<number | undefined>(undefined);
  const [semestre, setSemestre] = useState<1 | 2>(2);

  const anoSelecionado = exercicio ?? exerciciosDisponiveis[0];
  const periodoSelecionado = periodoConsulta(
    visaoPeriodo,
    periodo,
    semestre,
  );
  const rotuloPeriodoSelecionado = rotuloPeriodo(
    visaoPeriodo,
    periodo,
    semestre,
  );

  // Orçamento é a fonte primária.
  const resumo = useResumoFuncao(anoSelecionado ?? 0, periodoSelecionado);
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

    const ordenadas = [...dados]
      .filter((d) => (d.empenhado ?? 0) > 0)
      .sort((a, b) => (b.empenhado ?? 0) - (a.empenhado ?? 0));
    const composicao = ordenadas.map((d, i) => ({
      label: d.funcao,
      valor: d.empenhado ?? 0,
      color: paleta[i % paleta.length],
    }));

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
  }, [resumo.data, paleta]);

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

  return (
    <div className="space-y-10 animate-fade-up">
      <PageHeader
        eyebrow="Painel Municipal"
        title="Visão Geral"
        description={
          <>
            Execução orçamentária, indicadores fiscais e contratos de{" "}
            {dadosMun?.nome_municipio ?? "Jequié"} ({dadosMun?.uf ?? "BA"})
            {anoSelecionado ? (
              <>
                <span className="text-text-muted"> · </span>
                <span className="font-mono text-text-primary">
                  {anoSelecionado ?? "—"}
                </span>
                <span className="text-text-muted">
                  {" "}
                  · {rotuloPeriodoSelecionado}
                </span>
              </>
            ) : null}
            .
          </>
        }
        actions={
          <div className="flex flex-wrap items-center justify-end gap-3">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
                Exercício
              </span>
              <select
                value={anoSelecionado ?? ""}
                onChange={(e) => {
                  setExercicio(Number(e.target.value));
                  setPeriodo(undefined);
                  setSemestre(2);
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
                Visão
              </span>
              <select
                value={visaoPeriodo}
                onChange={(e) => setVisaoPeriodo(e.target.value as VisaoPeriodo)}
                className="field-select"
              >
                <option value="anual">Anual</option>
                <option value="semestral">Semestral</option>
                <option value="bimestral">Bimestral</option>
              </select>
            </label>
            {visaoPeriodo === "semestral" && (
              <label className="flex items-center gap-2 text-sm">
                <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
                  Semestre
                </span>
                <select
                  value={semestre}
                  onChange={(e) => setSemestre(Number(e.target.value) as 1 | 2)}
                  className="field-select"
                >
                  {SEMESTRES.map((s) => (
                    <option key={s.valor} value={s.valor}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {visaoPeriodo === "bimestral" && (
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
            )}
          </div>
        }
      />

      <DataSourceStrip
        items={["RREO", "RGF/LRF", "IBGE", "PNCP"]}
        note="Valores do RREO são acumulados até o período selecionado; a visão semestral usa B3/B6 e a anual usa o acumulado mais recente."
      />

      {/* Hero KPIs */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <HeroKpi
          label="Dotação atualizada"
          value={loadingOrcamento ? "—" : formatCompactBRL(totais.dotacao)}
          sub={`Orçamento aprovado · ${rotuloPeriodoSelecionado}`}
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
                Empenhado por função de governo · funções oficiais
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
            <EmptyState
              title="Sem execução registrada"
              description={
                <>
                  Não há valores de execução para {anoSelecionado ?? "—"}
                  {` · ${rotuloPeriodoSelecionado}`}. Ajuste os filtros ou
                  confirme a ingestão do RREO no backend.
                </>
              }
            />
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
            <EmptyState
              title="Sem indicadores derivados"
              description={`Nenhum indicador fiscal foi encontrado para ${anoSelecionado ?? "—"}. Quando a ingestão RGF/RREO estiver disponível, os limites aparecem aqui.`}
            />
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
                  formatIndicadorRazaoLimite(ind);
                const limite = formatIndicadorLimite(ind);
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
                        {formatIndicadorValor(ind)}
                      </span>
                    </div>
                    {limite != null && (
                      <p className="text-[10.5px] text-text-muted mt-1 font-mono">
                        {limite}
                        {pctLimite != null ? ` · ${pctLimite}` : ""}
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
