import { useState } from "react";
import { useContratacoes } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";

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
    <div className="space-y-6">
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
      <input
        type="text"
        placeholder="Buscar por objeto..."
        value={busca}
        onChange={(e) => {
          setBusca(e.target.value);
          setPagina(1);
        }}
        className="w-full max-w-md bg-surface-raised border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-lente-500"
      />

      {/* Table */}
      <div className="bg-surface-raised border border-border rounded-xl overflow-hidden">
        {isLoading ? (
          <p className="p-5 text-text-muted text-sm">Carregando...</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
                <th className="px-5 py-3">Processo</th>
                <th className="px-5 py-3">Modalidade</th>
                <th className="px-5 py-3">Objeto</th>
                <th className="px-5 py-3 text-right">Valor Est.</th>
                <th className="px-5 py-3">Situação</th>
                <th className="px-5 py-3 text-right">Publicação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data?.dados.map((c) => (
                <tr key={c.id} className="hover:bg-surface-overlay/30 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs text-text-secondary">
                    {c.numero_processo ?? "—"}
                  </td>
                  <td className="px-5 py-3">
                    <span className="inline-block px-2 py-0.5 rounded text-xs bg-lente-800 text-lente-200">
                      {c.modalidade ?? "—"}
                    </span>
                  </td>
                  <td className="px-5 py-3 max-w-sm truncate">{c.objeto}</td>
                  <td className="px-5 py-3 text-right font-mono">
                    {formatBRL(c.valor_estimado)}
                  </td>
                  <td className="px-5 py-3 text-xs">{c.situacao ?? "—"}</td>
                  <td className="px-5 py-3 text-right text-text-secondary">
                    {formatDate(c.data_publicacao)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPaginas > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setPagina((p) => Math.max(1, p - 1))}
            disabled={pagina === 1}
            className="px-3 py-1.5 rounded bg-surface-raised border border-border text-text-secondary hover:text-text-primary disabled:opacity-40"
          >
            Anterior
          </button>
          <span className="text-text-muted">
            {pagina} / {totalPaginas}
          </span>
          <button
            onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
            disabled={pagina >= totalPaginas}
            className="px-3 py-1.5 rounded bg-surface-raised border border-border text-text-secondary hover:text-text-primary disabled:opacity-40"
          >
            Próximo
          </button>
        </div>
      )}
    </div>
  );
}
