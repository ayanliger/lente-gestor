import { useContratacoes, useContratos, useContratosVencendo, useFornecedores } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";

function StatCard({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "default" | "warning";
}) {
  const toneClasses =
    tone === "warning"
      ? "bg-warning-500/[0.06] border-warning-500/25 hover:border-warning-500/50"
      : "bg-surface-raised/70 border-border hover:border-lente-500/40";
  const valueClasses =
    tone === "warning" ? "text-warning-500" : "text-text-primary";
  return (
    <div
      className={`card-accent border rounded-xl p-5 backdrop-blur-sm transition-colors ${toneClasses}`}
    >
      <p className="text-text-muted text-[10px] uppercase tracking-[0.15em] mb-2">
        {label}
      </p>
      <p
        className={`text-3xl font-semibold font-mono tabular-nums leading-none ${valueClasses}`}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-text-secondary mt-2">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const contratacoes = useContratacoes({ tamanho_pagina: 1 });
  const contratos = useContratos({ tamanho_pagina: 1 });
  const fornecedores = useFornecedores({ tamanho_pagina: 1 });
  const vencendo = useContratosVencendo(90);

  const isLoading = contratacoes.isLoading || contratos.isLoading;

  return (
    <div className="space-y-8 animate-fade-up">
      <div>
        <p className="text-[11px] font-mono uppercase tracking-[0.25em] text-accent-400/80 mb-2">
          Painel Municipal
        </p>
        <h1 className="font-display text-4xl md:text-5xl tracking-tight text-text-primary leading-[1.05]">
          Visão Geral
        </h1>
        <p className="text-text-secondary text-sm mt-3 max-w-2xl">
          Acompanhamento contínuo de contratações, contratos e fornecedores do
          município de Jequié (BA).
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Contratações"
          value={isLoading ? "—" : contratacoes.data?.total ?? 0}
          sub="registros no PNCP"
        />
        <StatCard
          label="Contratos"
          value={isLoading ? "—" : contratos.data?.total ?? 0}
          sub="contratos firmados"
        />
        <StatCard
          label="Fornecedores"
          value={isLoading ? "—" : fornecedores.data?.total ?? 0}
          sub="empresas cadastradas"
        />
        <StatCard
          label="Vencendo em 90 dias"
          value={isLoading ? "—" : vencendo.data?.total ?? 0}
          sub="contratos com vencimento próximo"
          tone="warning"
        />
      </div>

      {/* Contratos vencendo */}
      <div className="bg-surface-raised/60 border border-border rounded-xl overflow-hidden backdrop-blur-sm">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <h2 className="font-display text-lg text-text-primary">
            Contratos com vencimento próximo
          </h2>
          <span className="text-[11px] font-mono uppercase tracking-wider text-text-muted">
            próximos 90 dias
          </span>
        </div>
        {vencendo.isLoading ? (
          <p className="p-5 text-text-muted text-sm">Carregando...</p>
        ) : vencendo.data?.dados.length === 0 ? (
          <p className="p-5 text-text-muted text-sm">Nenhum contrato vencendo nos próximos 90 dias.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
                <th className="px-5 py-3">Contrato</th>
                <th className="px-5 py-3">Objeto</th>
                <th className="px-5 py-3 text-right">Valor</th>
                <th className="px-5 py-3 text-right">Vencimento</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {vencendo.data?.dados.slice(0, 10).map((c) => (
                <tr key={c.id} className="hover:bg-surface-overlay/30 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs text-text-secondary">
                    {c.numero_contrato ?? c.pncp_id?.slice(-12)}
                  </td>
                  <td className="px-5 py-3 max-w-md truncate">{c.objeto}</td>
                  <td className="px-5 py-3 text-right font-mono">
                    {formatBRL(c.valor_inicial)}
                  </td>
                  <td className="px-5 py-3 text-right text-warning-500 font-medium">
                    {formatDate(c.data_fim_vigencia)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
