import { useQuery } from "@tanstack/react-query";
import { api, type PaginatedResponse } from "./client";
import type {
  AgregacaoBanco,
  AgregacaoEspecie,
  AnoEspecie,
  Contratacao,
  Contrato,
  DadosMunicipio,
  Fornecedor,
  IndicadorFiscal,
  MesAnoArrecadacao,
  PorReceitaContabil,
  ResumoArrecadacao,
  ResumoFuncao,
  SerieAnualArrecadacao,
  SerieMensalArrecadacao,
  TopTributo,
} from "./types";

interface PaginationParams {
  pagina?: number;
  tamanho_pagina?: number;
  busca?: string;
}

export function useContratacoes(
  params: PaginationParams & {
    ano?: number;
    modalidade?: string;
    situacao?: string;
  } = {}
) {
  return useQuery({
    queryKey: ["contratacoes", params],
    queryFn: () =>
      api
        .get<PaginatedResponse<Contratacao>>("/contratacoes/", { params })
        .then((r) => r.data),
  });
}

export function useContratos(
  params: PaginationParams & {
    fornecedor_id?: string;
    situacao?: string;
    categoria?: string;
    ano?: number;
  } = {}
) {
  return useQuery({
    queryKey: ["contratos", params],
    queryFn: () =>
      api
        .get<PaginatedResponse<Contrato>>("/contratos/", { params })
        .then((r) => r.data),
  });
}

export function useContratosVencendo(dias = 90) {
  return useQuery({
    queryKey: ["contratos", "vencendo", dias],
    queryFn: () =>
      api
        .get<PaginatedResponse<Contrato>>("/contratos/vencendo", {
          params: { dias },
        })
        .then((r) => r.data),
  });
}

export function useFornecedores(params: PaginationParams = {}) {
  return useQuery({
    queryKey: ["fornecedores", params],
    queryFn: () =>
      api
        .get<PaginatedResponse<Fornecedor>>("/fornecedores/", { params })
        .then((r) => r.data),
  });
}

// ───────────────────────────────────────
// Orçamento (RREO/RGF + indicadores) — Fase 4
// ───────────────────────────────────────

export function useExerciciosOrcamento(tipoRelatorio?: "RREO" | "RGF") {
  return useQuery({
    queryKey: ["orcamento", "exercicios", tipoRelatorio],
    queryFn: () =>
      api
        .get<number[]>("/orcamento/exercicios", {
          params: tipoRelatorio ? { tipo_relatorio: tipoRelatorio } : undefined,
        })
        .then((r) => r.data),
  });
}

export function useResumoFuncao(exercicio: number, periodo?: number) {
  return useQuery({
    queryKey: ["resumo-por-funcao", exercicio, periodo],
    queryFn: () =>
      api
        .get<ResumoFuncao[]>("/orcamento/resumo-por-funcao", {
          params: { exercicio, ...(periodo != null ? { periodo } : {}) },
        })
        .then((r) => r.data),
    enabled: Number.isFinite(exercicio) && exercicio > 0,
  });
}

export function useIndicadoresFiscais(params: {
  exercicio?: number;
  periodo?: number;
  codigo?: string;
  situacao?: string;
} = {}) {
  return useQuery({
    queryKey: ["indicadores-fiscais", params],
    queryFn: () =>
      api
        .get<IndicadorFiscal[]>("/orcamento/indicadores", { params })
        .then((r) => r.data),
  });
}

export function useDadosMunicipioSerie() {
  return useQuery({
    queryKey: ["municipio-serie"],
    queryFn: () =>
      api
        .get<DadosMunicipio[]>("/municipio/dados")
        .then((r) => r.data),
  });
}

export function useDadosMunicipio(exercicio: number) {
  return useQuery({
    queryKey: ["municipio", exercicio],
    queryFn: () =>
      api
        .get<DadosMunicipio[]>("/municipio/dados", {
          params: { exercicio },
        })
        .then((r) => r.data[0] ?? null),
    enabled: Number.isFinite(exercicio) && exercicio > 0,
  });
}

// ─────────────────────────────────────
// Arrecadação tributária (Município Online)
// ─────────────────────────────────────

export function useResumoArrecadacao(exercicio: number) {
  return useQuery({
    queryKey: ["arrecadacao", "resumo", exercicio],
    queryFn: () =>
      api
        .get<ResumoArrecadacao>("/arrecadacao/resumo", {
          params: { exercicio },
        })
        .then((r) => r.data),
    enabled: Number.isFinite(exercicio) && exercicio > 0,
  });
}

export function useArrecadacaoPorExercicio() {
  return useQuery({
    queryKey: ["arrecadacao", "por-exercicio"],
    queryFn: () =>
      api
        .get<SerieAnualArrecadacao[]>("/arrecadacao/por-exercicio")
        .then((r) => r.data),
  });
}

export function useArrecadacaoPorMes(exercicio: number) {
  return useQuery({
    queryKey: ["arrecadacao", "por-mes", exercicio],
    queryFn: () =>
      api
        .get<SerieMensalArrecadacao[]>("/arrecadacao/por-mes", {
          params: { exercicio },
        })
        .then((r) => r.data),
    enabled: Number.isFinite(exercicio) && exercicio > 0,
  });
}

export function useArrecadacaoPorEspecie(exercicio: number) {
  return useQuery({
    queryKey: ["arrecadacao", "por-especie", exercicio],
    queryFn: () =>
      api
        .get<AgregacaoEspecie[]>("/arrecadacao/por-especie", {
          params: { exercicio },
        })
        .then((r) => r.data),
    enabled: Number.isFinite(exercicio) && exercicio > 0,
  });
}

export function useTopTributos(exercicio: number, limite = 20) {
  return useQuery({
    queryKey: ["arrecadacao", "top-tributos", exercicio, limite],
    queryFn: () =>
      api
        .get<TopTributo[]>("/arrecadacao/top-tributos", {
          params: { exercicio, limite },
        })
        .then((r) => r.data),
    enabled: Number.isFinite(exercicio) && exercicio > 0,
  });
}

export function useArrecadacaoAnoEspecie() {
  return useQuery({
    queryKey: ["arrecadacao", "ano-x-especie"],
    queryFn: () =>
      api.get<AnoEspecie[]>("/arrecadacao/ano-x-especie").then((r) => r.data),
  });
}

export function useArrecadacaoPorBanco(exercicio: number, mes?: number) {
  return useQuery({
    queryKey: ["arrecadacao", "por-banco", exercicio, mes],
    queryFn: () =>
      api
        .get<AgregacaoBanco[]>("/arrecadacao/por-banco", {
          params: { exercicio, ...(mes != null ? { mes } : {}) },
        })
        .then((r) => r.data),
    enabled: Number.isFinite(exercicio) && exercicio > 0,
  });
}

// ─────────────────────────────────────
// Arrecadação — visão histórica plurianual (2º painel do sócio)
// ─────────────────────────────────────

export function useArrecadacaoPorReceita(
  anoInicio: number,
  anoFim: number,
  limite = 30,
) {
  return useQuery({
    queryKey: ["arrecadacao", "historico", "por-receita", anoInicio, anoFim, limite],
    queryFn: () =>
      api
        .get<PorReceitaContabil[]>("/arrecadacao/historico/por-receita", {
          params: { ano_inicio: anoInicio, ano_fim: anoFim, limite },
        })
        .then((r) => r.data),
    enabled:
      Number.isFinite(anoInicio) &&
      Number.isFinite(anoFim) &&
      anoInicio > 0 &&
      anoFim > 0,
  });
}

export function useArrecadacaoMesXAno(anoInicio: number, anoFim: number) {
  return useQuery({
    queryKey: ["arrecadacao", "historico", "mes-x-ano", anoInicio, anoFim],
    queryFn: () =>
      api
        .get<MesAnoArrecadacao[]>("/arrecadacao/historico/mes-x-ano", {
          params: { ano_inicio: anoInicio, ano_fim: anoFim },
        })
        .then((r) => r.data),
    enabled:
      Number.isFinite(anoInicio) &&
      Number.isFinite(anoFim) &&
      anoInicio > 0 &&
      anoFim > 0,
  });
}
