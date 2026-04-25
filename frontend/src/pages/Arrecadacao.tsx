import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import {
  useArrecadacaoAnoEspecie,
  useArrecadacaoMesXAno,
  useArrecadacaoPorEspecie,
  useArrecadacaoPorExercicio,
  useArrecadacaoPorMes,
  useArrecadacaoPorReceita,
  useResumoArrecadacao,
  useTopTributos,
} from "@/api/hooks";
import {
  DataSourceStrip,
  EmptyState,
  PageHeader,
} from "@/components/PageChrome";
// `useArrecadacaoPorBanco` existe mas está oculto enquanto o drill-down
// estiver desabilitado na ingestão. Para reabilitar, reimporte e
// reintroduza a seção "Arrecadação por banco recebedor" (git histórico).
import { formatBRL } from "@/lib/format";
import { useChartTokens } from "@/lib/theme-core";

// Recharts precisa de cores hex resolvidas (SVG <rect fill>). Para séries
// categóricas, usamos uma escala próxima dos painéis BI do projeto: ciano,
// azul profundo, laranja, lima, magenta e violeta.
function useOrdinalScale(): string[] {
  const tokens = useChartTokens();
  return [
    tokens.accent,
    tokens.neutral,
    "#f29f3d",
    "#a8dc2f",
    "#d92fb5",
    "#5b8def",
    "#7c3aed",
    "#8edff0",
    "#497f99",
    "#c9e5ee",
  ];
}

const MESES_LABEL = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
];

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

function abreviar(texto: string, max: number): string {
  if (texto.length <= max) return texto;
  return texto.slice(0, max - 1) + "…";
}

export default function Arrecadacao() {
  const anoCorrente = new Date().getFullYear();
  const [exercicio, setExercicio] = useState<number | undefined>(undefined);

  // Intervalo default para a seção histórica: 2020 até o exercício atual.
  const [anoInicio, setAnoInicio] = useState(2020);
  const [anoFim, setAnoFim] = useState<number | undefined>(undefined);

  const porExercicio = useArrecadacaoPorExercicio();
  const anoEspecie = useArrecadacaoAnoEspecie();

  const tokens = useChartTokens();
  const escala = useOrdinalScale();

  // Exercícios disponíveis extraídos da série anual.
  const exerciciosDisponiveis = useMemo(() => {
    const anos = (porExercicio.data ?? []).map((d) => d.exercicio);
    if (anos.length === 0) return [anoCorrente];
    return Array.from(new Set(anos)).sort((a, b) => b - a);
  }, [porExercicio.data, anoCorrente]);

  const exercicioSelecionado =
    exercicio ?? exerciciosDisponiveis[0] ?? anoCorrente;
  const anoFimSelecionado = anoFim ?? exerciciosDisponiveis[0] ?? anoCorrente;
  const anoMaximoDisponivel = Math.max(
    anoCorrente,
    ...exerciciosDisponiveis,
  );

  const resumo = useResumoArrecadacao(exercicioSelecionado);
  const porMes = useArrecadacaoPorMes(exercicioSelecionado);
  const porEspecie = useArrecadacaoPorEspecie(exercicioSelecionado);
  const topTributos = useTopTributos(exercicioSelecionado, 10);
  const porReceitaHist = useArrecadacaoPorReceita(
    anoInicio,
    anoFimSelecionado,
    30,
  );
  const mesXAno = useArrecadacaoMesXAno(anoInicio, anoFimSelecionado);

  // Prepara dados de barras empilhadas ano × espécie.
  const barrasEmpilhadas = useMemo(() => {
    const dados = anoEspecie.data ?? [];
    const porAno = new Map<number, Record<string, number | string>>();
    const especies = new Set<string>();
    for (const row of dados) {
      especies.add(row.especie);
      const entry = porAno.get(row.exercicio) ?? { exercicio: row.exercicio };
      entry[row.especie] = row.valor;
      porAno.set(row.exercicio, entry);
    }
    return {
      series: [...especies],
      data: Array.from(porAno.values()).sort(
        (a, b) => Number(a.exercicio) - Number(b.exercicio),
      ),
    };
  }, [anoEspecie.data]);

  const serieMensal = useMemo(() => {
    const mapa = new Map<number, number>();
    for (const p of porMes.data ?? []) mapa.set(p.mes, p.valor);
    return MESES_LABEL.map((label, i) => ({
      mes: label,
      mesNum: i + 1,
      valor: mapa.get(i + 1) ?? 0,
    }));
  }, [porMes.data]);

  const treemapData = useMemo(
    () =>
      (topTributos.data ?? []).map((t) => ({
        name: abreviar(t.descricao_receita, 32),
        value: t.valor,
        descricaoCompleta: t.descricao_receita,
        cod: t.cod_item_receita,
        pct: t.pct,
      })),
    [topTributos.data],
  );

  // Seção histórica: anos cobertos pelo intervalo atual.
  const anosRange = useMemo(() => {
    const ini = Math.min(anoInicio, anoFimSelecionado);
    const fim = Math.max(anoInicio, anoFimSelecionado);
    const out: number[] = [];
    for (let a = ini; a <= fim; a++) out.push(a);
    return out;
  }, [anoInicio, anoFimSelecionado]);

  // Pivot mês × ano: um registro por mês com campos `${ano}` para cada barra.
  const barrasMesXAno = useMemo(() => {
    const mapa = new Map<number, Record<string, number | string>>();
    for (let m = 1; m <= 12; m++) {
      mapa.set(m, { mes: MESES_LABEL[m - 1] ?? String(m), mesNum: m });
    }
    for (const p of mesXAno.data ?? []) {
      const linha = mapa.get(p.mes);
      if (linha) linha[String(p.ano)] = p.valor;
    }
    return Array.from(mapa.values()).sort(
      (a, b) => Number(a.mesNum) - Number(b.mesNum),
    );
  }, [mesXAno.data]);

  return (
    <div className="space-y-8 animate-fade-up">
      <PageHeader
        eyebrow="Receita pública"
        title="Arrecadação"
        description={
          <>
            Receitas tributárias municipais por exercício, espécie, tributo e
            mês. A série mensal exclui DCA anual para evitar picos artificiais
            em dezembro.
          </>
        }
        actions={
          <label className="flex items-center gap-2 text-sm">
            <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
              Exercício
            </span>
            <select
              value={exercicioSelecionado}
              onChange={(e) => setExercicio(Number(e.target.value))}
              className="field-select"
            >
              {exerciciosDisponiveis.map((ano) => (
                <option key={ano} value={ano}>
                  {ano}
                </option>
              ))}
            </select>
          </label>
        }
      />

      <DataSourceStrip
        items={["Município Online", "SICONFI/DCA", "STN"]}
        note="Valores previstos são colapsados por item e fonte para evitar duplicidade mensal."
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Total arrecadado"
          value={formatCompact(resumo.data?.total_arrecadado ?? null)}
          sub={`${resumo.data?.n_tributos ?? 0} tributos`}
          accent
        />
        <KpiCard
          label="Previsto (LOA atualizada)"
          value={formatCompact(resumo.data?.total_previsto ?? null)}
          sub={
            resumo.data?.pct_realizacao != null
              ? `${resumo.data.pct_realizacao.toFixed(1)}% realizado`
              : ""
          }
        />
        <KpiCard
          label={`Δ vs. ${exercicioSelecionado - 1}`}
          value={
            resumo.data?.delta_yoy != null
              ? `${resumo.data.delta_yoy >= 0 ? "+" : ""}${resumo.data.delta_yoy.toFixed(1)}%`
              : "—"
          }
          sub="variação ano a ano"
        />
        <KpiCard
          label="Meses com registros"
          value={String((porMes.data ?? []).filter((m) => m.valor > 0).length)}
          sub={`de 12 (${exercicioSelecionado})`}
        />
      </div>

      {/* Grid 2x2: espécie, top-tributos, série anual, ano × espécie */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Donut por espécie */}
        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <h2 className="font-display text-xl text-text-primary">
            Por espécie tributária
          </h2>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Taxonomia derivada do código de Natureza da Receita do STN.
          </p>
          {porEspecie.isLoading ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : (porEspecie.data ?? []).length === 0 ? (
            <EmptyState
              title="Sem dados por espécie"
              description={`Não há arrecadação classificada para ${exercicioSelecionado}.`}
            />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie
                  data={porEspecie.data}
                  dataKey="valor"
                  nameKey="especie"
                  innerRadius={70}
                  outerRadius={120}
                  paddingAngle={1}
                >
                  {(porEspecie.data ?? []).map((_, idx) => (
                    <Cell
                      key={idx}
                      fill={escala[idx % escala.length]}
                      stroke={tokens.surfaceRaised}
                      strokeWidth={2}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: tokens.surfaceRaised,
                    border: `1px solid ${tokens.grid}`,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  formatter={(value: unknown, name: unknown) => [
                    formatBRL(Number(value)),
                    String(name),
                  ]}
                />
                <Legend
                  wrapperStyle={{
                    fontSize: 12,
                    color: tokens.textSecondary,
                  }}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* Top 10 tributos */}
        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <h2 className="font-display text-xl text-text-primary">
            Top 10 tributos
          </h2>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Maior arrecadação por item de receita.
          </p>
          {topTributos.isLoading ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : (topTributos.data ?? []).length === 0 ? (
            <EmptyState
              title="Sem ranking de tributos"
              description={`Nenhum item de receita foi encontrado para ${exercicioSelecionado}.`}
            />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart
                data={(topTributos.data ?? []).map((t) => ({
                  ...t,
                  label: abreviar(t.descricao_receita, 30),
                }))}
                layout="vertical"
                margin={{ top: 6, right: 24, left: 120, bottom: 6 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={tokens.grid}
                  horizontal={false}
                />
                <XAxis
                  type="number"
                  tickFormatter={(v) => formatCompact(Number(v)).replace("R$ ", "")}
                  stroke={tokens.axis}
                  tick={{ fill: tokens.tick, fontSize: 11 }}
                />
                <YAxis
                  dataKey="label"
                  type="category"
                  stroke={tokens.axis}
                  width={160}
                  tick={{ fill: tokens.tick, fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: tokens.surfaceRaised,
                    border: `1px solid ${tokens.grid}`,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  formatter={(value: unknown) => [
                    formatBRL(Number(value)),
                    "Arrecadado",
                  ]}
                  labelFormatter={(_, payload) =>
                    payload?.[0]?.payload?.descricao_receita ?? ""
                  }
                />
                <Bar
                  dataKey="valor"
                  fill={tokens.accent}
                  radius={[0, 4, 4, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* Série anual */}
        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <h2 className="font-display text-xl text-text-primary">
            Arrecadação por exercício
          </h2>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Série histórica anual da arrecadação total.
          </p>
          {porExercicio.isLoading ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : (porExercicio.data ?? []).length === 0 ? (
            <p className="text-text-muted text-sm py-8">Sem dados.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={porExercicio.data}>
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} vertical={false} />
                <XAxis
                  dataKey="exercicio"
                  stroke={tokens.axis}
                  tick={{ fill: tokens.tick, fontSize: 12, fontFamily: "JetBrains Mono" }}
                />
                <YAxis
                  stroke={tokens.axis}
                  tickFormatter={(v) => formatCompact(Number(v)).replace("R$ ", "")}
                  tick={{ fill: tokens.tick, fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: tokens.surfaceRaised,
                    border: `1px solid ${tokens.grid}`,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  formatter={(value: unknown) => [formatBRL(Number(value)), "Arrecadado"]}
                />
                <Bar dataKey="valor" fill={tokens.accent} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* Ano × espécie (empilhadas) */}
        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <h2 className="font-display text-xl text-text-primary">
            Ano × espécie
          </h2>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Composição da arrecadação por espécie em cada exercício.
          </p>
          {anoEspecie.isLoading ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : barrasEmpilhadas.data.length === 0 ? (
            <p className="text-text-muted text-sm py-8">Sem dados.</p>
          ) : (
            <div>
              <ResponsiveContainer width="100%" height={292}>
                <BarChart
                  data={barrasEmpilhadas.data}
                  margin={{ top: 8, right: 12, left: 0, bottom: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} vertical={false} />
                  <XAxis
                    dataKey="exercicio"
                    stroke={tokens.axis}
                    tick={{ fill: tokens.tick, fontSize: 12, fontFamily: "JetBrains Mono" }}
                  />
                  <YAxis
                    stroke={tokens.axis}
                    tickFormatter={(v) => formatCompact(Number(v)).replace("R$ ", "")}
                    tick={{ fill: tokens.tick, fontSize: 11 }}
                  />
                  <Tooltip
                    allowEscapeViewBox={{ y: true }}
                    position={{ y: -36 }}
                    contentStyle={{
                      background: tokens.surfaceRaised,
                      border: `1px solid ${tokens.grid}`,
                      borderRadius: 10,
                      fontSize: 12,
                    }}
                    wrapperStyle={{ zIndex: 20 }}
                    formatter={(value: unknown, name: unknown) => [
                      formatBRL(Number(value)),
                      String(name),
                    ]}
                  />
                  {barrasEmpilhadas.series.map((especie, idx) => (
                    <Bar
                      key={especie}
                      dataKey={especie}
                      stackId="especies"
                      fill={escala[idx % escala.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-2 text-[11px] text-text-secondary">
                {barrasEmpilhadas.series.map((especie, idx) => (
                  <span key={especie} className="inline-flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-sm"
                      style={{ backgroundColor: escala[idx % escala.length] }}
                    />
                    {especie}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Comparativo mensal + treemap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <h2 className="font-display text-xl text-text-primary">
            Arrecadação mensal — {exercicioSelecionado}
          </h2>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Evolução da arrecadação ao longo do ano.
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={serieMensal}>
              <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} vertical={false} />
              <XAxis
                dataKey="mes"
                stroke={tokens.axis}
                tick={{ fill: tokens.tick, fontSize: 11, fontFamily: "JetBrains Mono" }}
              />
              <YAxis
                stroke={tokens.axis}
                tickFormatter={(v) => formatCompact(Number(v)).replace("R$ ", "")}
                tick={{ fill: tokens.tick, fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  background: tokens.surfaceRaised,
                  border: `1px solid ${tokens.grid}`,
                  borderRadius: 10,
                  fontSize: 12,
                }}
                formatter={(value: unknown) => [formatBRL(Number(value)), "Arrecadado"]}
              />
              <Bar
                dataKey="valor"
                fill={tokens.accent}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <h2 className="font-display text-xl text-text-primary">
            Mapa de tributos
          </h2>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Top-10 por área de contribuição.
          </p>
          {treemapData.length === 0 ? (
            <EmptyState
              title="Sem mapa de tributos"
              description={`O top-10 por área de contribuição ainda não está disponível para ${exercicioSelecionado}.`}
            />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <Treemap
                data={treemapData}
                dataKey="value"
                stroke={tokens.surfaceRaised}
                fill={tokens.accent}
                aspectRatio={4 / 3}
              >
                <Tooltip
                  contentStyle={{
                    background: tokens.surfaceRaised,
                    border: `1px solid ${tokens.grid}`,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  formatter={(value: unknown, _name: unknown, item: unknown) => {
                    const payload = (item as { payload?: { descricaoCompleta?: string } })
                      ?.payload;
                    return [
                      formatBRL(Number(value)),
                      payload?.descricaoCompleta ?? "",
                    ];
                  }}
                />
              </Treemap>
            </ResponsiveContainer>
          )}
        </section>
      </div>

      {/* ────── Visão histórica plurianual (2º painel do sócio) ────── */}
      <div className="pt-4">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-4">
          <div>
            <h2 className="font-display text-2xl tracking-tight text-text-primary">
              Visão histórica
            </h2>
            <p className="text-text-secondary text-xs mt-1">
              Arrecadação por receita contábil ao longo dos anos.
            </p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <label className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
                De
              </span>
              <input
                type="number"
                min={2000}
                max={anoMaximoDisponivel}
                value={anoInicio}
                onChange={(e) => setAnoInicio(Number(e.target.value) || 2020)}
                className="field-input w-24 px-3 py-1.5 text-center font-mono"
              />
            </label>
            <label className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
                Até
              </span>
              <input
                type="number"
                min={2000}
                max={anoMaximoDisponivel}
                value={anoFimSelecionado}
                onChange={(e) =>
                  setAnoFim(Number(e.target.value) || anoMaximoDisponivel)
                }
                className="field-input w-24 px-3 py-1.5 text-center font-mono"
              />
            </label>
          </div>
        </div>

        {/* Tabela pivot por receita contábil */}
        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6 mb-6">
          <h3 className="font-display text-xl text-text-primary">
            Arrecadação discriminada por receita
          </h3>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Top-30 receitas no intervalo {Math.min(anoInicio, anoFimSelecionado)}–{Math.max(anoInicio, anoFimSelecionado)},
            ordenadas pelo total agregado.
          </p>
          {porReceitaHist.isLoading ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : (porReceitaHist.data ?? []).length === 0 ? (
            <p className="text-text-muted text-sm py-8">
              Sem dados no intervalo selecionado.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="py-2 pr-4 font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted font-normal">
                      Receita contábil
                    </th>
                    {anosRange.map((ano) => (
                      <th
                        key={ano}
                        className="py-2 px-3 font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted font-normal text-right"
                      >
                        {ano}
                      </th>
                    ))}
                    <th className="py-2 pl-3 font-mono text-[10px] uppercase tracking-[0.18em] text-accent-ink font-normal text-right">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(porReceitaHist.data ?? []).map((linha) => (
                    <tr
                      key={linha.cod_item_receita}
                      className="border-b border-border/40 hover:bg-accent-500/[0.04] transition-colors"
                    >
                      <td
                        className="py-2 pr-4 text-text-primary max-w-md truncate"
                        title={linha.descricao_receita}
                      >
                        {linha.descricao_receita || linha.cod_item_receita}
                      </td>
                      {anosRange.map((ano) => {
                        const valor = linha.por_ano[String(ano)];
                        return (
                          <td
                            key={ano}
                            className="py-2 px-3 text-right font-mono tabular-nums text-text-secondary"
                          >
                            {valor != null ? formatCompact(valor) : "—"}
                          </td>
                        );
                      })}
                      <td className="py-2 pl-3 text-right font-mono tabular-nums text-accent-ink font-semibold">
                        {formatCompact(linha.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Barras mensais empilhadas por ano */}
        <section className="card-accent bg-surface-raised border border-border rounded-xl p-6">
          <h3 className="font-display text-xl text-text-primary">
            Arrecadação mensal por ano
          </h3>
          <p className="text-xs text-text-muted mt-1 mb-4">
            Comparativo mês a mês, uma cor por exercício.
          </p>
          {mesXAno.isLoading ? (
            <p className="text-text-muted text-sm py-8">Carregando…</p>
          ) : (mesXAno.data ?? []).length === 0 ? (
            <p className="text-text-muted text-sm py-8">
              Sem dados no intervalo selecionado.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={barrasMesXAno}>
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} vertical={false} />
                <XAxis
                  dataKey="mes"
                  stroke={tokens.axis}
                  tick={{ fill: tokens.tick, fontSize: 11, fontFamily: "JetBrains Mono" }}
                />
                <YAxis
                  stroke={tokens.axis}
                  tickFormatter={(v) => formatCompact(Number(v)).replace("R$ ", "")}
                  tick={{ fill: tokens.tick, fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: tokens.surfaceRaised,
                    border: `1px solid ${tokens.grid}`,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  formatter={(value: unknown, name: unknown) => [
                    formatBRL(Number(value)),
                    String(name),
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: tokens.textSecondary }} />
                {anosRange.map((ano, idx) => (
                  <Bar
                    key={ano}
                    dataKey={String(ano)}
                    name={String(ano)}
                    fill={escala[idx % escala.length]}
                    radius={[3, 3, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>

      {/*
        Seção "Arrecadação por banco recebedor" oculta temporariamente.
        Os dados dependem do drill-down (`obter_recolhimentos`) no portal,
        que foi desabilitado por padrão na ingestão por ser caro (centenas
        de requests por mês). O endpoint `/arrecadacao/por-banco` continua
        disponível e o hook `useArrecadacaoPorBanco` também — basta rodar
        `make ingest-arrecadacao ano=AAAA` com `--com-detalhes` e
        reintroduzir a visualização aqui (git histórico preserva o markup).
      */}
    </div>
  );
}
