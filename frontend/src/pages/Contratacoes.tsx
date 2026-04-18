import { useState } from "react";
import { useContratacoes } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";
import SearchInput from "@/components/SearchInput";
import Pagination from "@/components/Pagination";
import TableSkeleton from "@/components/TableSkeleton";

export default function Contratacoes() {
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);

  const { data, isLoading } = useContratacoes({
    busca: busca || undefined,
    pagina,
    tamanho_pagina: 20,
  });

  const totalPaginas = data ? Math.ceil(data.total / 20) : 0;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-4xl tracking-tight text-text-primary">
            Contratações
          </h1>
          <p className="text-text-secondary text-sm mt-2">
            {data ? (
              <>
                <span className="font-mono tabular-nums text-text-primary">
                  {data.total.toLocaleString("pt-BR")}
                </span>{" "}
                registros
              </>
            ) : (
              "Carregando…"
            )}
          </p>
        </div>
      </div>

      {/* Search */}
      <SearchInput
        placeholder="Buscar por objeto…"
        value={busca}
        onChange={(v) => {
          setBusca(v);
          setPagina(1);
        }}
      />

      {/* Table */}
      <div className="bg-surface-raised border border-border rounded-xl overflow-hidden">
        {isLoading ? (
          <TableSkeleton columns={6} rows={6} />
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Processo</th>
                <th>Modalidade</th>
                <th>Objeto</th>
                <th className="text-right">Valor est.</th>
                <th>Situação</th>
                <th className="text-right">Publicação</th>
              </tr>
            </thead>
            <tbody>
              {data?.dados.map((c) => (
                <tr key={c.id}>
                  <td className="font-mono text-xs text-text-secondary">
                    {c.numero_processo ?? "—"}
                  </td>
                  <td>
                    {c.modalidade ? (
                      <span className="badge badge-neutral">{c.modalidade}</span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className="max-w-sm truncate">{c.objeto}</td>
                  <td className="tbl-num">{formatBRL(c.valor_estimado)}</td>
                  <td className="text-xs">
                    {c.situacao ? (
                      <span className="text-text-secondary">{c.situacao}</span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className="text-right text-text-secondary font-mono tabular-nums">
                    {formatDate(c.data_publicacao)}
                  </td>
                </tr>
              ))}
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
