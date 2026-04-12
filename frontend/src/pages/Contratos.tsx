import { useState } from "react";
import { useContratos } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";

export default function Contratos() {
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);

  const { data, isLoading } = useContratos({
    busca: busca || undefined,
    pagina,
    tamanho_pagina: 20,
  });

  const totalPaginas = data ? Math.ceil(data.total / 20) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Contratos</h1>
        <p className="text-text-secondary text-sm mt-1">
          {data ? `${data.total} contratos firmados` : "Carregando..."}
        </p>
      </div>

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

      <div className="bg-surface-raised border border-border rounded-xl overflow-hidden">
        {isLoading ? (
          <p className="p-5 text-text-muted text-sm">Carregando...</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
                <th className="px-5 py-3">Contrato</th>
                <th className="px-5 py-3">Objeto</th>
                <th className="px-5 py-3">Categoria</th>
                <th className="px-5 py-3 text-right">Valor</th>
                <th className="px-5 py-3 text-right">Vigência</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data?.dados.map((c) => {
                const vencendo =
                  c.data_fim_vigencia &&
                  new Date(c.data_fim_vigencia) <
                    new Date(Date.now() + 90 * 86400000);

                return (
                  <tr
                    key={c.id}
                    className="hover:bg-surface-overlay/30 transition-colors"
                  >
                    <td className="px-5 py-3 font-mono text-xs text-text-secondary">
                      {c.numero_contrato ?? c.pncp_id?.slice(-12)}
                    </td>
                    <td className="px-5 py-3 max-w-sm truncate">{c.objeto}</td>
                    <td className="px-5 py-3">
                      {c.categoria && (
                        <span className="inline-block px-2 py-0.5 rounded text-xs bg-lente-800 text-lente-200">
                          {c.categoria}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right font-mono">
                      {formatBRL(c.valor_inicial)}
                    </td>
                    <td
                      className={`px-5 py-3 text-right ${
                        vencendo ? "text-warning-500 font-medium" : "text-text-secondary"
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
