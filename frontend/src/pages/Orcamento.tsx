import { useMemo, useState } from "react";
import {
  useDadosMunicipio,
  useExerciciosOrcamento,
  useIndicadoresFiscais,
  useResumoFuncao,
} from "@/api/hooks";
import {
  DataSourceStrip,
  EmptyState,
  PageHeader,
} from "@/components/PageChrome";
import { formatBRL } from "@/lib/format";
import { useChartTokens } from "@/lib/theme-core";

// As cores do gráfico vêm de `useChartTokens` para trocar automaticamente
// entre light/dark a partir das variáveis CSS semânticas.

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

function formatCompact(valor: number | null | undefined): string {
  if (valor == null) return "—";
  if (valor >= 1_000_000_000) return `R$ ${(valor / 1_000_000_000).toFixed(2)} bi`;
  if (valor >= 1_000_000) return `R$ ${(valor / 1_000_000).toFixed(2)} mi`;
  if (valor >= 1_000) return `R$ ${(valor / 1_000).toFixed(1)} mil`;
  return formatBRL(valor);
}

function KpiCard({
  label,
  value,
  sub,
  accentColor,
  valueTone,
}: {
  label: string;
  value: string;
  sub?: string;
  accentColor?: string;
  valueTone?: string;
}) {
  return (
    <div
      className="relative overflow-hidden rounded-xl border border-border bg-surface-raised p-4 transition-colors hover:border-accent-500/30 sm:p-5"
    >
      {accentColor && (
        <span
          className="absolute inset-x-0 top-0 h-[2px]"
          style={{
            background: `linear-gradient(90deg, transparent 0%, ${accentColor} 50%, transparent 100%)`,
          }}
          aria-hidden
        />
      )}
      <p className="text-text-muted text-[10px] uppercase tracking-[0.15em] mb-2">
        {label}
      </p>
      <p
        className={`text-2xl font-semibold font-mono tabular-nums ${
          valueTone ?? "text-text-primary"
        }`}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-text-secondary mt-1.5">{sub}</p>}
    </div>
  );
}

export default function Orcamento() {
  const exerciciosQuery = useExerciciosOrcamento();
  const exerciciosDisponiveis = exerciciosQuery.data ?? [];
  const [exercicio, setExercicio] = useState<number | undefined>(undefined);
  const [visaoPeriodo, setVisaoPeriodo] = useState<VisaoPeriodo>("anual");
  const [periodo, setPeriodo] = useState<number | undefined>(undefined);
  const [semestre, setSemestre] = useState<1 | 2>(2);

  // Seleciona o mais recente enquanto o usuário não escolhe manualmente.
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

  const resumo = useResumoFuncao(anoSelecionado ?? 0, periodoSelecionado);
  const municipio = useDadosMunicipio(anoSelecionado ?? 0);
  const indicadores = useIndicadoresFiscais({ exercicio: anoSelecionado });

  const tokens = useChartTokens();

  // RCL vem dos indicadores (fonte RGF): não há indicador próprio de RCL,
  // mas inferimos usando o valor absoluto quando disponível em DESPESA_PESSOAL.
  // Como aproximação, usamos DESPESA_PESSOAL_PCT_RCL * 100 / 54 (limite) só
  // para confirmar existência; o card principal usa apenas metadados.
  const dadosMun = municipio.data;

  const top10 = useMemo(() => {
    const dados = resumo.data ?? [];
    return dados
      .filter((d) => d.empenhado != null)
      .slice(0, 10)
      .map((d) => ({
        funcao: d.funcao.length > 22 ? d.funcao.slice(0, 20) + "…" : d.funcao,
        funcaoCompleta: d.funcao,
        dotacao: d.dotacao_atualizada ?? 0,
        empenhado: d.empenhado ?? 0,
        liquidado: d.liquidado ?? 0,
      }));
  }, [resumo.data]);

  const totalEmpenhado = useMemo(() => {
    return (resumo.data ?? []).reduce(
      (acc, d) => acc + (d.empenhado ?? 0),
      0,
    );
  }, [resumo.data]);

  const maxExecucao = useMemo(() => {
    return Math.max(
      1,
      ...top10.flatMap((d) => [d.dotacao, d.empenhado, d.liquidado]),
    );
  }, [top10]);

  const situacaoLRF = useMemo(() => {
    const dados = indicadores.data ?? [];
    const excedidos = dados.filter(
      (i) => i.situacao === "EXCEDIDO" || i.situacao === "ABAIXO_MINIMO",
    ).length;
    const alertas = dados.filter((i) => i.situacao === "ALERTA").length;
    if (excedidos > 0) return { label: `${excedidos} limite(s) excedido(s)`, tom: "text-danger-500", color: tokens.danger };
    if (alertas > 0) return { label: `${alertas} em alerta`, tom: "text-warning-500", color: tokens.warning };
    if (dados.length > 0) return { label: "Tudo em conformidade", tom: "text-success-500", color: tokens.success };
    return null;
  }, [indicadores.data, tokens]);

  return (
    <div className="space-y-6 animate-fade-up sm:space-y-8">
      <PageHeader
        eyebrow="Execução orçamentária"
        title="Orçamento"
        description={
          <>
            Execução por função de governo em{" "}
            {dadosMun?.nome_municipio ?? "Jequié"} ({dadosMun?.uf ?? "BA"}),
            com comparação entre dotação atualizada, empenho e liquidação
            {anoSelecionado ? (
              <>
                <span className="text-text-muted"> · </span>
                <span className="font-mono text-text-primary">
                  {anoSelecionado}
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
          <div className="flex flex-wrap items-center justify-start gap-3 sm:justify-end">
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
        items={["RREO Anexo 02", "RGF/LRF", "IBGE"]}
        note="Valores do RREO são acumulados até o período selecionado; a visão semestral usa B3/B6 e a anual usa o acumulado mais recente."
      />

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Empenhado (top funções)"
          value={formatCompact(totalEmpenhado)}
          sub={`${(resumo.data ?? []).length} funções · ${rotuloPeriodoSelecionado}`}
          accentColor={tokens.expense}
          valueTone="text-data-expense"
        />
        <KpiCard
          label="PIB Municipal"
          value={formatCompact(dadosMun?.pib_corrente ?? null)}
          sub={dadosMun ? `PIB ${dadosMun.exercicio}` : "IBGE"}
          accentColor={tokens.contract}
        />
        <KpiCard
          label="PIB per capita"
          value={formatCompact(dadosMun?.pib_per_capita ?? null)}
          sub={dadosMun?.populacao ? `${dadosMun.populacao.toLocaleString("pt-BR")} habitantes` : ""}
          accentColor={tokens.planned}
        />
        <KpiCard
          label="Indicadores LRF"
          value={situacaoLRF?.label ?? "—"}
          sub={`${indicadores.data?.length ?? 0} acompanhados`}
          accentColor={situacaoLRF?.color}
          valueTone={situacaoLRF?.tom}
        />
      </div>

      {/* Gráfico de execução por função */}
      <section className="card-accent rounded-xl border border-border bg-surface-raised p-4 sm:p-6">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-xl text-text-primary">
              Execução por função
            </h2>
            <p className="text-xs text-text-muted mt-1">
              Top 10 por valor empenhado · {rotuloPeriodoSelecionado}.
            </p>
          </div>
          <div className="hidden sm:flex items-center gap-4 text-[11px] font-mono uppercase tracking-wider text-text-muted">
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: tokens.planned, opacity: 0.85 }}
              />
              Dotação
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="chart-expense-bar inline-block h-2.5 w-2.5 rounded-sm"
              />
              Empenhado
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: tokens.liquidated }}
              />
              Liquidado
            </span>
          </div>
        </div>

        {resumo.isLoading ? (
          <p className="text-text-muted text-sm py-8">Carregando…</p>
        ) : top10.length === 0 ? (
          <EmptyState
            title="Sem execução por função"
            description={
              <>
                Não há linhas do RREO-Anexo 02 para {anoSelecionado ?? "—"}
                {` · ${rotuloPeriodoSelecionado}`}. Ajuste os filtros ou
                confirme a ingestão orçamentária.
              </>
            }
          />
        ) : (
          <div className="space-y-3">
            {top10.map((d) => {
              const dotacaoPct = Math.min((d.dotacao / maxExecucao) * 100, 100);
              const empenhadoPct = Math.min((d.empenhado / maxExecucao) * 100, 100);
              const liquidadoPct = Math.min((d.liquidado / maxExecucao) * 100, 100);
              const pctExecucao =
                d.dotacao > 0 ? (d.empenhado / d.dotacao) * 100 : null;
              const pctTone =
                pctExecucao == null
                  ? "text-text-muted"
                  : pctExecucao > 100
                    ? "text-danger-500"
                    : pctExecucao >= 90
                      ? "text-warning-500"
                      : pctExecucao >= 60
                        ? "text-success-500"
                        : "text-text-secondary";

              return (
                <div
                  key={d.funcaoCompleta}
                  className="grid gap-2 rounded-lg border border-transparent px-2 py-1.5 transition-colors hover:border-border hover:bg-surface-overlay/35 sm:grid-cols-[10rem_1fr_8.5rem] sm:items-center sm:gap-4"
                  title={`${d.funcaoCompleta}\nDotação: ${formatBRL(d.dotacao)}\nEmpenhado: ${formatBRL(d.empenhado)}\nLiquidado: ${formatBRL(d.liquidado)}`}
                >
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-text-primary">
                      {d.funcaoCompleta}
                    </p>
                    <p className={`mt-0.5 font-mono text-[10.5px] ${pctTone}`}>
                      {pctExecucao != null ? `${pctExecucao.toFixed(1)}% exec.` : "—"}
                    </p>
                  </div>

                  <div className="relative h-8 overflow-hidden rounded-lg border border-border bg-surface-overlay/45">
                    <div
                      className="absolute inset-y-1 left-0 rounded-r-md"
                      style={{
                        width: `${dotacaoPct}%`,
                        backgroundColor: tokens.planned,
                        opacity: 0.2,
                      }}
                      aria-hidden
                    />
                    <div
                      className="chart-expense-bar absolute inset-y-1.5 left-0 rounded-r-md"
                      style={{
                        width: `${empenhadoPct}%`,
                      }}
                      aria-hidden
                    />
                    <div
                      className="absolute bottom-1 left-0 h-1 rounded-full"
                      style={{
                        width: `${liquidadoPct}%`,
                        backgroundColor: tokens.liquidated,
                      }}
                      aria-hidden
                    />
                  </div>

                  <div className="font-mono text-xs tabular-nums text-data-expense sm:text-right">
                    {formatCompact(d.empenhado)}
                    <p className="mt-0.5 text-[10.5px] text-data-liquidated">
                      liq. {formatCompact(d.liquidado)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Tabela detalhada */}
      {(resumo.data ?? []).length > 0 && (
        <section className="overflow-hidden rounded-xl border border-border bg-surface-raised">
          <div className="border-b border-border px-4 py-4 sm:px-6">
            <h2 className="font-display text-lg text-text-primary">
              Detalhamento por função
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Função</th>
                  <th className="text-right">Dotação inicial</th>
                  <th className="text-right">Dotação atualizada</th>
                  <th className="text-right">Empenhado</th>
                  <th className="text-right">Liquidado</th>
                  <th className="text-right">% Exec.</th>
                </tr>
              </thead>
              <tbody>
                {resumo.data!.map((d) => {
                  const pct =
                    d.dotacao_atualizada && d.empenhado
                      ? (d.empenhado / d.dotacao_atualizada) * 100
                      : null;
                  const pctTone =
                    pct == null
                      ? "text-text-muted"
                      : pct > 100
                        ? "text-danger-500"
                        : pct >= 90
                          ? "text-warning-500"
                          : pct >= 60
                            ? "text-success-500"
                            : "text-text-secondary";
                  return (
                    <tr key={d.funcao}>
                      <td className="text-text-primary">{d.funcao}</td>
                      <td className="tbl-num text-text-secondary">
                        {formatBRL(d.dotacao_inicial)}
                      </td>
                      <td className="tbl-num">
                        {formatBRL(d.dotacao_atualizada)}
                      </td>
                      <td className="tbl-num text-data-expense">
                        {formatBRL(d.empenhado)}
                      </td>
                      <td className="tbl-num text-data-liquidated">
                        {formatBRL(d.liquidado)}
                      </td>
                      <td className={`tbl-num ${pctTone}`}>
                        {pct != null ? `${pct.toFixed(1)}%` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
