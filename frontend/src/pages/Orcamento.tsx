import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  useDadosMunicipio,
  useIndicadoresFiscais,
  useResumoFuncao,
} from "@/api/hooks";
import { formatBRL } from "@/lib/format";
import { useChartTokens } from "@/lib/theme";

// As cores do gráfico vêm de `useChartTokens` para trocar automaticamente
// entre light/dark. Recharts v3 renderiza SVG <rect fill>, que só aceita
// notação hex tradicional — por isso lemos os hexes finais já resolvidos
// a partir das variáveis CSS.

const BIMESTRES = [1, 2, 3, 4, 5, 6];

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
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`card-accent rounded-xl p-5 border transition-colors ${
        accent
          ? "bg-accent-500/[0.08] border-accent-500/30 hover:border-accent-500/55"
          : "bg-surface-raised border-border hover:border-accent-500/30"
      }`}
    >
      <p className="text-text-muted text-[10px] uppercase tracking-[0.15em] mb-2">
        {label}
      </p>
      <p
        className={`text-2xl font-semibold font-mono tabular-nums ${
          accent ? "text-accent-ink" : "text-text-primary"
        }`}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-text-secondary mt-1.5">{sub}</p>}
    </div>
  );
}

export default function Orcamento() {
  const [exercicio, setExercicio] = useState(2024);
  const [periodo, setPeriodo] = useState<number | undefined>(undefined);

  const resumo = useResumoFuncao(exercicio, periodo);
  const municipio = useDadosMunicipio(exercicio);
  const indicadores = useIndicadoresFiscais({ exercicio });

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
      }));
  }, [resumo.data]);

  const totalEmpenhado = useMemo(() => {
    return (resumo.data ?? []).reduce(
      (acc, d) => acc + (d.empenhado ?? 0),
      0,
    );
  }, [resumo.data]);

  const situacaoLRF = useMemo(() => {
    const dados = indicadores.data ?? [];
    const excedidos = dados.filter(
      (i) => i.situacao === "EXCEDIDO" || i.situacao === "ABAIXO_MINIMO",
    ).length;
    const alertas = dados.filter((i) => i.situacao === "ALERTA").length;
    if (excedidos > 0) return { label: `${excedidos} limite(s) excedido(s)`, tom: "text-danger-500" };
    if (alertas > 0) return { label: `${alertas} em alerta`, tom: "text-warning-500" };
    if (dados.length > 0) return { label: "Tudo em conformidade", tom: "text-success-500" };
    return null;
  }, [indicadores.data]);

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Header + filtros */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl tracking-tight text-text-primary">
            Orçamento
          </h1>
          <p className="text-text-secondary text-sm mt-2">
            Execução orçamentária · {dadosMun?.nome_municipio ?? "Jequié"} ({dadosMun?.uf ?? "BA"})
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
              Exercício
            </span>
            <select
              value={exercicio}
              onChange={(e) => {
                setExercicio(Number(e.target.value));
                setPeriodo(undefined);
              }}
              className="field-select"
            >
              {[2024, 2023].map((ano) => (
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
                setPeriodo(e.target.value === "" ? undefined : Number(e.target.value))
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
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Empenhado (top funções)"
          value={formatCompact(totalEmpenhado)}
          sub={`${(resumo.data ?? []).length} funções`}
          accent
        />
        <KpiCard
          label="PIB Municipal"
          value={formatCompact(dadosMun?.pib_corrente ?? null)}
          sub={dadosMun ? `PIB ${dadosMun.exercicio}` : "IBGE"}
        />
        <KpiCard
          label="PIB per capita"
          value={formatCompact(dadosMun?.pib_per_capita ?? null)}
          sub={dadosMun?.populacao ? `${dadosMun.populacao.toLocaleString("pt-BR")} habitantes` : ""}
        />
        <KpiCard
          label="Indicadores LRF"
          value={situacaoLRF?.label ?? "—"}
          sub={`${indicadores.data?.length ?? 0} acompanhados`}
        />
      </div>

      {/* Gráfico de execução por função */}
      <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="font-display text-xl text-text-primary">
              Execução por função
            </h2>
            <p className="text-xs text-text-muted mt-1">
              Top 10 por valor empenhado. Comparativo com dotação atualizada.
            </p>
          </div>
          <div className="hidden sm:flex items-center gap-4 text-[11px] font-mono uppercase tracking-wider text-text-muted">
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: tokens.neutral, opacity: 0.85 }}
              />
              Dotação
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: tokens.accent }}
              />
              Empenhado
            </span>
          </div>
        </div>

        {resumo.isLoading ? (
          <p className="text-text-muted text-sm py-8">Carregando…</p>
        ) : top10.length === 0 ? (
          <p className="text-text-muted text-sm py-8">
            Sem dados para {exercicio}
            {periodo ? ` · B${periodo}` : ""}.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={440}>
            <BarChart
              data={top10}
              layout="vertical"
              margin={{ top: 10, right: 40, left: 100, bottom: 10 }}
              barCategoryGap={12}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={tokens.grid}
                horizontal={false}
              />
              <XAxis
                type="number"
                tickFormatter={(v) => formatCompact(v).replace("R$ ", "")}
                stroke={tokens.axis}
                tick={{
                  fill: tokens.tick,
                  fontSize: 11,
                  fontFamily: "JetBrains Mono",
                }}
              />
              <YAxis
                dataKey="funcao"
                type="category"
                stroke={tokens.axis}
                width={130}
                tick={{ fill: tokens.tick, fontSize: 12 }}
              />
              <Tooltip
                cursor={{ fill: `${tokens.accent}1f` }}
                contentStyle={{
                  background: tokens.surfaceRaised,
                  border: `1px solid ${tokens.grid}`,
                  borderRadius: 10,
                  fontSize: 12,
                  boxShadow: "0 12px 32px rgba(0,0,0,0.12)",
                  padding: "10px 14px",
                }}
                labelStyle={{
                  color: tokens.textPrimary,
                  fontWeight: 600,
                  marginBottom: 4,
                }}
                itemStyle={{ color: tokens.textSecondary }}
                formatter={(value, name) => [
                  formatBRL(typeof value === "number" ? value : Number(value)),
                  String(name),
                ]}
                labelFormatter={(_, payload) =>
                  payload?.[0]?.payload?.funcaoCompleta ?? ""
                }
              />
              <Legend
                wrapperStyle={{
                  fontSize: 12,
                  color: tokens.textSecondary,
                  paddingTop: 12,
                }}
                iconType="square"
                iconSize={10}
              />
              <Bar
                dataKey="dotacao"
                name="Dotação atualizada"
                fill={tokens.neutral}
                fillOpacity={0.75}
                radius={[0, 4, 4, 0]}
              />
              <Bar
                dataKey="empenhado"
                name="Empenhado"
                fill={tokens.accent}
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Tabela detalhada */}
      {(resumo.data ?? []).length > 0 && (
        <section className="bg-surface-raised border border-border rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-border">
            <h2 className="font-display text-lg text-text-primary">
              Detalhamento por função
            </h2>
          </div>
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
                    : pct >= 90
                      ? "text-success-500"
                      : pct >= 60
                        ? "text-accent-ink"
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
                    <td className="tbl-num text-accent-ink">
                      {formatBRL(d.empenhado)}
                    </td>
                    <td className="tbl-num text-text-secondary">
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
        </section>
      )}
    </div>
  );
}
