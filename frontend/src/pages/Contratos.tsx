import { useMemo, useState } from "react";
import { useContratos } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";
import SearchInput from "@/components/SearchInput";
import Pagination from "@/components/Pagination";
import TableSkeleton from "@/components/TableSkeleton";

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

  const limiteVencendo = useMemo(
    () => new Date(Date.now() + MS_90_DIAS),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data],
  );

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="font-display text-4xl tracking-tight text-text-primary">
          Contratos
        </h1>
        <p className="text-text-secondary text-sm mt-2">
          {data ? (
            <>
              <span className="font-mono tabular-nums text-text-primary">
                {data.total.toLocaleString("pt-BR")}
              </span>{" "}
              contratos firmados
            </>
          ) : (
            "Carregando…"
          )}
        </p>
      </div>

      <SearchInput
        placeholder="Buscar por objeto…"
        value={busca}
        onChange={(v) => {
          setBusca(v);
          setPagina(1);
        }}
      />

      <div className="bg-surface-raised/60 border border-border rounded-xl overflow-hidden backdrop-blur-sm">
        {isLoading ? (
          <TableSkeleton columns={5} rows={6} />
        ) : (
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
                const vencendo =
                  c.data_fim_vigencia &&
                  new Date(c.data_fim_vigencia) < limiteVencendo;

                return (
                  <tr key={c.id}>
                    <td className="font-mono text-xs text-text-secondary">
                      {c.numero_contrato ?? c.pncp_id?.slice(-12)}
                    </td>
                    <td className="max-w-sm truncate">{c.objeto}</td>
                    <td>
                      {c.categoria ? (
                        <span className="badge badge-neutral">
                          {c.categoria}
                        </span>
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </td>
                    <td className="tbl-num">{formatBRL(c.valor_inicial)}</td>
                    <td
                      className={`text-right font-mono tabular-nums ${
                        vencendo
                          ? "text-warning-500 font-medium"
                          : "text-text-secondary"
                      }`}
                    >
                      {formatDate(c.data_fim_vigencia)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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
