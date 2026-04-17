import { useQuery } from "@tanstack/react-query";
import { api, type PaginatedResponse } from "./client";
import type {
  Contratacao,
  Contrato,
  DadosMunicipio,
  Fornecedor,
  IndicadorFiscal,
  ResumoFuncao,
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

// ────────────────────────────────────────
// Orçamento (RREO/RGF + indicadores) — Fase 4
// ────────────────────────────────────────

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
