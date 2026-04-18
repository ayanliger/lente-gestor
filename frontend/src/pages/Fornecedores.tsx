import { useState } from "react";
import { useFornecedores } from "@/api/hooks";
import SearchInput from "@/components/SearchInput";
import Pagination from "@/components/Pagination";
import TableSkeleton from "@/components/TableSkeleton";

export default function Fornecedores() {
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);

  const { data, isLoading } = useFornecedores({
    busca: busca || undefined,
    pagina,
    tamanho_pagina: 20,
  });

  const totalPaginas = data ? Math.ceil(data.total / 20) : 0;

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="font-display text-4xl tracking-tight text-text-primary">
          Fornecedores
        </h1>
        <p className="text-text-secondary text-sm mt-2">
          {data ? (
            <>
              <span className="font-mono tabular-nums text-text-primary">
                {data.total.toLocaleString("pt-BR")}
              </span>{" "}
              empresas cadastradas
            </>
          ) : (
            "Carregando…"
          )}
        </p>
      </div>

      <SearchInput
        placeholder="Buscar por nome ou CNPJ…"
        value={busca}
        onChange={(v) => {
          setBusca(v);
          setPagina(1);
        }}
      />

      <div className="bg-surface-raised border border-border rounded-xl overflow-hidden">
        {isLoading ? (
          <TableSkeleton columns={3} rows={6} />
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>CNPJ / CPF</th>
                <th>Nome</th>
                <th>Tipo</th>
              </tr>
            </thead>
            <tbody>
              {data?.dados.map((f) => (
                <tr key={f.id}>
                  <td className="font-mono text-xs text-text-secondary">
                    {f.cpf_cnpj}
                  </td>
                  <td>{f.nome}</td>
                  <td>
                    {f.tipo && (
                      <span
                        className={`badge ${
                          f.tipo === "PJ" ? "badge-neutral" : "badge-accent"
                        }`}
                      >
                        {f.tipo}
                      </span>
                    )}
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
