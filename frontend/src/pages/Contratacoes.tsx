import { useState } from "react";
import { useContratacoes } from "@/api/hooks";
import { formatBRL, formatDate } from "@/lib/format";
import SearchInput from "@/components/SearchInput";
import Pagination from "@/components/Pagination";
import SortableHeader, { type SortDirection } from "@/components/SortableHeader";
import TableSkeleton from "@/components/TableSkeleton";
import {
  DataSourceStrip,
  EmptyState,
  PageHeader,
} from "@/components/PageChrome";
type CampoOrdenacaoContratacoes =
  | "numero_processo"
  | "modalidade"
  | "objeto"
  | "valor_estimado"
  | "situacao"
  | "data_publicacao";

export default function Contratacoes() {
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [ordenacao, setOrdenacao] = useState<{
    campo: CampoOrdenacaoContratacoes;
    direcao: SortDirection;
  }>({ campo: "data_publicacao", direcao: "desc" });

  const { data, isLoading } = useContratacoes({
    busca: busca || undefined,
    pagina,
    tamanho_pagina: 20,
    ordenar_por: ordenacao.campo,
    direcao: ordenacao.direcao,
  });

  const totalPaginas = data ? Math.ceil(data.total / 20) : 0;
  const alternarOrdenacao = (campo: CampoOrdenacaoContratacoes) => {
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
        title="Contratações"
        description="Licitações, dispensas e inexigibilidades integradas do PNCP, com busca por objeto e paginação."
        actions={
          <span className="badge badge-accent">
            {data ? data.total.toLocaleString("pt-BR") : "—"} registros
          </span>
        }
      />

      <DataSourceStrip
        items={["PNCP", "Contratações públicas"]}
        note="Clique nos cabeçalhos para alternar entre ordem crescente e decrescente; valores exibidos são estimados quando disponíveis."
      />

      {/* Search */}
      <SearchInput
        placeholder="Buscar por objeto…"
        ariaLabel="Buscar contratações por objeto"
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
        ) : data?.dados.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="Nenhuma contratação encontrada"
              description={
                busca
                  ? "A busca atual não retornou contratações. Tente termos mais amplos do objeto."
                  : "Não há contratações carregadas para exibição."
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <SortableHeader
                    column="numero_processo"
                    label="Processo"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                  <SortableHeader
                    column="modalidade"
                    label="Modalidade"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                  <SortableHeader
                    column="objeto"
                    label="Objeto"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                  <SortableHeader
                    column="valor_estimado"
                    label="Valor est."
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                    align="right"
                  />
                  <SortableHeader
                    column="situacao"
                    label="Situação"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                  <SortableHeader
                    column="data_publicacao"
                    label="Publicação"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                    align="right"
                  />
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
                    <td
                      className="max-w-sm truncate text-text-primary"
                      title={c.objeto ?? undefined}
                    >
                      {c.objeto ?? "—"}
                    </td>
                    <td className="tbl-num text-data-contract">
                      {formatBRL(c.valor_estimado)}
                    </td>
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
