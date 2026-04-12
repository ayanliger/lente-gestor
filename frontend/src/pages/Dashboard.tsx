import { useContratacoes, useContratos, useContratosVencendo, useFornecedores } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-surface-raised border border-border rounded-xl p-5">
      <p className="text-text-muted text-xs uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-text-primary">{value}</p>
      {sub && <p className="text-xs text-text-secondary mt-1">{sub}</p>}
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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Visão Geral</h1>
        <p className="text-text-secondary text-sm mt-1">
          Painel de acompanhamento — Município de Jequié
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Contratações"
          value={isLoading ? "..." : contratacoes.data?.total ?? 0}
          sub="registros no PNCP"
        />
        <StatCard
          label="Contratos"
          value={isLoading ? "..." : contratos.data?.total ?? 0}
          sub="contratos firmados"
        />
        <StatCard
          label="Fornecedores"
          value={isLoading ? "..." : fornecedores.data?.total ?? 0}
          sub="empresas cadastradas"
        />
        <StatCard
          label="Vencendo em 90 dias"
          value={isLoading ? "..." : vencendo.data?.total ?? 0}
          sub="contratos com vencimento próximo"
        />
      </div>

      {/* Contratos vencendo */}
      <div className="bg-surface-raised border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="font-semibold text-sm">Contratos com Vencimento Próximo</h2>
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
