import { useState } from "react";
import { useFornecedores } from "@/api/hooks";
import SearchInput from "@/components/SearchInput";
import Pagination from "@/components/Pagination";
import SortableHeader, { type SortDirection } from "@/components/SortableHeader";
import TableSkeleton from "@/components/TableSkeleton";
import {
  DataSourceStrip,
  EmptyState,
  PageHeader,
} from "@/components/PageChrome";
type CampoOrdenacaoFornecedores = "cpf_cnpj" | "nome" | "tipo";

export default function Fornecedores() {
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [ordenacao, setOrdenacao] = useState<{
    campo: CampoOrdenacaoFornecedores;
    direcao: SortDirection;
  }>({ campo: "nome", direcao: "asc" });

  const { data, isLoading } = useFornecedores({
    busca: busca || undefined,
    pagina,
    tamanho_pagina: 20,
    ordenar_por: ordenacao.campo,
    direcao: ordenacao.direcao,
  });

  const totalPaginas = data ? Math.ceil(data.total / 20) : 0;
  const alternarOrdenacao = (campo: CampoOrdenacaoFornecedores) => {
    setPagina(1);
    setOrdenacao((atual) => ({
      campo,
      direcao:
        atual.campo === campo && atual.direcao === "asc" ? "desc" : "asc",
    }));
  };

  return (
    <div className="space-y-6 animate-fade-up">
      <PageHeader
        eyebrow="PNCP"
        title="Fornecedores"
        description="Cadastro de pessoas físicas e jurídicas vinculadas aos contratos e contratações integrados."
        actions={
          <span className="badge badge-accent">
            {data ? data.total.toLocaleString("pt-BR") : "—"} fornecedores
          </span>
        }
      />

      <DataSourceStrip
        items={["PNCP", "CPF/CNPJ", "Fornecedores"]}
        note="Use a busca para localizar fornecedores e clique nos cabeçalhos para alternar a ordenação."
      />

      <SearchInput
        placeholder="Buscar por nome ou CNPJ…"
        ariaLabel="Buscar fornecedores por nome ou documento"
        value={busca}
        onChange={(v) => {
          setBusca(v);
          setPagina(1);
        }}
      />

      <div className="bg-surface-raised border border-border rounded-xl overflow-hidden">
        {isLoading ? (
          <TableSkeleton columns={3} rows={6} />
        ) : data?.dados.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="Nenhum fornecedor encontrado"
              description={
                busca
                  ? "A busca atual não retornou fornecedores. Tente parte do nome ou apenas números do documento."
                  : "Não há fornecedores carregados para exibição."
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <SortableHeader
                    column="cpf_cnpj"
                    label="CNPJ / CPF"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                  <SortableHeader
                    column="nome"
                    label="Nome"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                  <SortableHeader
                    column="tipo"
                    label="Tipo"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                </tr>
              </thead>
              <tbody>
                {data?.dados.map((f) => (
                  <tr key={f.id}>
                    <td className="font-mono text-xs text-text-secondary">
                      {f.cpf_cnpj}
                    </td>
                    <td className="text-text-primary">{f.nome}</td>
                    <td>
                      {f.tipo ? (
                        <span
                          className={`badge ${
                            f.tipo === "PJ" ? "badge-neutral" : "badge-accent"
                          }`}
                        >
                          {f.tipo}
                        </span>
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
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
