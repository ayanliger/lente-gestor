import { useMemo, useState } from "react";
import { useContratos } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";
import SearchInput from "@/components/SearchInput";
import Pagination from "@/components/Pagination";
import TableSkeleton from "@/components/TableSkeleton";
import {
  DataSourceStrip,
  EmptyState,
  PageHeader,
} from "@/components/PageChrome";

// Threshold para destacar contratos vencendo em 90 dias. Calculado uma
// única vez por montagem para atender a regra de pureza do React.
const MS_90_DIAS = 90 * 86400000;

export default function Contratos() {
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);

  const { data, isLoading } = useContratos({
    busca: busca || undefined,
    pagina,
    tamanho_pagina: 20,
  });

  const totalPaginas = data ? Math.ceil(data.total / 20) : 0;

  const hoje = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);
  const limiteVencendo = useMemo(
    () => new Date(hoje.getTime() + MS_90_DIAS),
    [hoje],
  );

  return (
    <div className="space-y-6 animate-fade-up">
      <PageHeader
        eyebrow="PNCP"
        title="Contratos"
        description="Contratos firmados com vigência, categoria, valor e destaque para vencimentos nos próximos 90 dias."
        actions={
          <span className="badge badge-accent">
            {data ? data.total.toLocaleString("pt-BR") : "—"} contratos
          </span>
        }
      />

      <DataSourceStrip
        items={["PNCP", "Contratos", "Vigência"]}
        note="A lista é ordenada pelo fim de vigência mais próximo para priorizar revisão operacional."
      />

      <SearchInput
        placeholder="Buscar por objeto…"
        ariaLabel="Buscar contratos por objeto"
        value={busca}
        onChange={(v) => {
          setBusca(v);
          setPagina(1);
        }}
      />

      <div className="bg-surface-raised border border-border rounded-xl overflow-hidden">
        {isLoading ? (
          <TableSkeleton columns={5} rows={6} />
        ) : data?.dados.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="Nenhum contrato encontrado"
              description={
                busca
                  ? "A busca atual não retornou contratos. Tente outro termo do objeto."
                  : "Não há contratos carregados para exibição."
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Contrato</th>
                  <th>Objeto</th>
                  <th>Categoria</th>
                  <th className="text-right">Valor</th>
                  <th className="text-right">Vigência</th>
                </tr>
              </thead>
              <tbody>
                {data?.dados.map((c) => {
                  const fimVigencia = c.data_fim_vigencia
                    ? new Date(c.data_fim_vigencia)
                    : null;
                  const vencendo =
                    fimVigencia != null &&
                    fimVigencia >= hoje &&
                    fimVigencia <= limiteVencendo;

                  return (
                    <tr key={c.id}>
                      <td className="font-mono text-xs text-text-secondary">
                        {c.numero_contrato ?? c.pncp_id?.slice(-12) ?? "—"}
                      </td>
                      <td
                        className="max-w-sm truncate text-text-primary"
                        title={c.objeto ?? undefined}
                      >
                        {c.objeto ?? "—"}
                      </td>
                      <td>
                        {c.categoria ? (
                          <span className="badge badge-neutral">
                            {c.categoria}
                          </span>
                        ) : (
                          <span className="text-text-muted">—</span>
                        )}
                      </td>
                      <td className="tbl-num text-data-contract">
                        {formatBRL(c.valor_inicial)}
                      </td>
                      <td
                        className={`text-right font-mono tabular-nums ${
                          vencendo
                            ? "text-warning-500 font-medium"
                            : "text-text-secondary"
                        }`}
                        title={vencendo ? "Vencendo em até 90 dias" : undefined}
                      >
                        {formatDate(c.data_fim_vigencia)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Pagination
        pagina={pagina}
        totalPaginas={totalPaginas}
        onChange={setPagina}
      />
    </div>
  );
}
