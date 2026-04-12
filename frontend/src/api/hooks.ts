import { useQuery } from "@tanstack/react-query";
import { api, type PaginatedResponse } from "./client";
import type { Contratacao, Contrato, Fornecedor } from "./types";

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
