import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

export interface PaginatedResponse<T> {
  total: number;
  pagina: number;
  tamanho_pagina: number;
  dados: T[];
}
