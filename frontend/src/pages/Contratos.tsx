import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useContratos } from "@/api/hooks";
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

const DIAS_ALERTA_VENCENDO = 90;
const MS_DIA = 86400000;
type CampoOrdenacaoContratos =
  | "numero_contrato"
  | "objeto"
  | "categoria"
  | "valor_inicial"
  | "data_fim_vigencia";
function formatDateParam(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export default function Contratos() {
  const [searchParams] = useSearchParams();
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [ordenacao, setOrdenacao] = useState<{
    campo: CampoOrdenacaoContratos;
    direcao: SortDirection;
  }>({ campo: "data_fim_vigencia", direcao: "asc" });
  const filtroVencendoDias = useMemo(() => {
    const valor = Number(searchParams.get("vencendo"));
    return Number.isInteger(valor) && valor > 0 ? valor : undefined;
  }, [searchParams]);

  const hoje = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);
  const diasDestaqueVencendo = filtroVencendoDias ?? DIAS_ALERTA_VENCENDO;
  const limiteVencendo = useMemo(
    () => new Date(hoje.getTime() + diasDestaqueVencendo * MS_DIA),
    [diasDestaqueVencendo, hoje],
  );
  const { data, isLoading } = useContratos({
    busca: busca || undefined,
    pagina,
    tamanho_pagina: 20,
    data_inicio: filtroVencendoDias ? formatDateParam(hoje) : undefined,
    data_fim: filtroVencendoDias ? formatDateParam(limiteVencendo) : undefined,
    ordenar_por: ordenacao.campo,
    direcao: ordenacao.direcao,
  });

  const totalPaginas = data ? Math.ceil(data.total / 20) : 0;
  const alternarOrdenacao = (campo: CampoOrdenacaoContratos) => {
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
        title="Contratos"
        description={
          filtroVencendoDias
            ? `Contratos com fim de vigência nos próximos ${filtroVencendoDias} dias.`
            : "Contratos firmados com vigência, categoria, valor e destaque para vencimentos nos próximos 90 dias."
        }
        actions={
          <span className="badge badge-accent">
            {data ? data.total.toLocaleString("pt-BR") : "—"}{" "}
            {filtroVencendoDias ? "vencendo" : "contratos"}
          </span>
        }
      />

      <DataSourceStrip
        items={["PNCP", "Contratos", "Vigência"]}
        note={
          filtroVencendoDias
            ? `Filtro ativo: vigências entre ${hoje.toLocaleDateString("pt-BR")} e ${limiteVencendo.toLocaleDateString("pt-BR")}.`
            : "Clique nos cabeçalhos para alternar entre ordem crescente e decrescente."
        }
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
                  : filtroVencendoDias
                    ? `Não há contratos vencendo nos próximos ${filtroVencendoDias} dias.`
                  : "Não há contratos carregados para exibição."
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <SortableHeader
                    column="numero_contrato"
                    label="Contrato"
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
                    column="categoria"
                    label="Categoria"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                  />
                  <SortableHeader
                    column="valor_inicial"
                    label="Valor"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                    align="right"
                  />
                  <SortableHeader
                    column="data_fim_vigencia"
                    label="Vigência"
                    sortBy={ordenacao.campo}
                    direction={ordenacao.direcao}
                    onSort={alternarOrdenacao}
                    align="right"
                  />
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
                        title={
                          vencendo
                            ? `Vencendo em até ${diasDestaqueVencendo} dias`
                            : undefined
                        }
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
