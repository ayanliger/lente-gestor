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

// Chart palette — hex form (recharts v3 renders SVG <rect fill>; modern
// space-separated rgb() syntax is not universally honored in SVG paint
// attributes, which is why "Empenhado" previously rendered black).
const COR_DOTACAO = "#4a7fbe"; // lente-400
const COR_EMPENHADO = "#e6a817"; // accent-500
const COR_EIXO = "#6f85a3";
const COR_TICK = "#cbd5e1";
const COR_GRID = "#1f3658";

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
      className={`card-accent rounded-xl p-5 border backdrop-blur-sm transition-colors ${
        accent
          ? "bg-accent-500/[0.07] border-accent-500/30 hover:border-accent-500/50"
          : "bg-surface-raised/70 border-border hover:border-lente-500/40"
      }`}
    >
      <p className="text-text-muted text-[10px] uppercase tracking-[0.15em] mb-2">
        {label}
      </p>
      <p
        className={`text-2xl font-semibold font-mono tabular-nums ${
          accent ? "text-accent-400" : "text-text-primary"
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
            <span className="text-text-muted">Exercício</span>
            <select
              value={exercicio}
              onChange={(e) => {
                setExercicio(Number(e.target.value));
                setPeriodo(undefined);
              }}
              className="bg-surface-raised border border-border rounded-lg px-3 py-1.5 font-mono text-sm focus:border-accent-500 focus:outline-none"
            >
              {[2024, 2023].map((ano) => (
                <option key={ano} value={ano}>
                  {ano}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-sm">
            <span className="text-text-muted">Bimestre</span>
            <select
              value={periodo ?? ""}
              onChange={(e) =>
                setPeriodo(e.target.value === "" ? undefined : Number(e.target.value))
              }
              className="bg-surface-raised border border-border rounded-lg px-3 py-1.5 font-mono text-sm focus:border-accent-500 focus:outline-none"
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
      <section className="card-accent bg-surface-raised/60 border border-border rounded-xl p-6 backdrop-blur-sm">
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
                style={{ background: COR_DOTACAO, opacity: 0.85 }}
              />
              Dotação
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: COR_EMPENHADO }}
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
                stroke={COR_GRID}
                horizontal={false}
              />
              <XAxis
                type="number"
                tickFormatter={(v) => formatCompact(v).replace("R$ ", "")}
                stroke={COR_EIXO}
                tick={{ fill: COR_TICK, fontSize: 11, fontFamily: "JetBrains Mono" }}
              />
              <YAxis
                dataKey="funcao"
                type="category"
                stroke={COR_EIXO}
                width={130}
                tick={{ fill: COR_TICK, fontSize: 12 }}
              />
              <Tooltip
                cursor={{ fill: "rgba(45, 98, 163, 0.12)" }}
                contentStyle={{
                  background: "#0b1322",
                  border: "1px solid #1f3658",
                  borderRadius: 10,
                  fontSize: 12,
                  boxShadow: "0 12px 32px rgba(0,0,0,0.45)",
                  padding: "10px 14px",
                }}
                labelStyle={{
                  color: "#f1f5f9",
                  fontWeight: 600,
                  marginBottom: 4,
                }}
                itemStyle={{ color: "#cbd5e1" }}
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
                  color: "#cbd5e1",
                  paddingTop: 12,
                }}
                iconType="square"
                iconSize={10}
              />
              <Bar
                dataKey="dotacao"
                name="Dotação atualizada"
                fill={COR_DOTACAO}
                fillOpacity={0.75}
                radius={[0, 4, 4, 0]}
              />
              <Bar
                dataKey="empenhado"
                name="Empenhado"
                fill={COR_EMPENHADO}
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Tabela detalhada */}
      {(resumo.data ?? []).length > 0 && (
        <section className="bg-surface-raised/60 border border-border rounded-xl overflow-hidden backdrop-blur-sm">
          <div className="px-6 py-4 border-b border-border">
            <h2 className="font-display text-lg text-text-primary">
              Detalhamento por função
            </h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
                <th className="px-6 py-3">Função</th>
                <th className="px-6 py-3 text-right">Dotação inicial</th>
                <th className="px-6 py-3 text-right">Dotação atualizada</th>
                <th className="px-6 py-3 text-right">Empenhado</th>
                <th className="px-6 py-3 text-right">Liquidado</th>
                <th className="px-6 py-3 text-right">% Exec.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono text-xs">
              {resumo.data!.map((d) => {
                const pct =
                  d.dotacao_atualizada && d.empenhado
                    ? (d.empenhado / d.dotacao_atualizada) * 100
                    : null;
                return (
                  <tr
                    key={d.funcao}
                    className="hover:bg-surface-overlay/30 transition-colors"
                  >
                    <td className="px-6 py-3 text-text-primary font-sans">
                      {d.funcao}
                    </td>
                    <td className="px-6 py-3 text-right text-text-secondary">
                      {formatBRL(d.dotacao_inicial)}
                    </td>
                    <td className="px-6 py-3 text-right">
                      {formatBRL(d.dotacao_atualizada)}
                    </td>
                    <td className="px-6 py-3 text-right text-accent-400">
                      {formatBRL(d.empenhado)}
                    </td>
                    <td className="px-6 py-3 text-right text-text-secondary">
                      {formatBRL(d.liquidado)}
                    </td>
                    <td className="px-6 py-3 text-right">
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
