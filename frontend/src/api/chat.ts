import { useMutation } from "@tanstack/react-query";
import { api } from "./client";

export interface FonteCitada {
  indice: number;
  doc_id: string;
  fonte: string;
  referencia_tipo: string;
  referencia_id: string | null;
  chave_unica: string;
  titulo: string;
  metadados: Record<string, unknown>;
  score: number;
}

export interface ChatResponse {
  texto: string;
  fontes: FonteCitada[];
  recusou: boolean;
  latencia_ms: number;
}
export interface ChatHistoricoItem {
  autor: "usuario" | "assistente";
  texto: string;
  fontes: string[];
}

export interface ChatPayload {
  pergunta: string;
  historico: ChatHistoricoItem[];
}

/**
 * Mutation para POST /api/v1/chat/.
 *
 * O histórico é enviado de forma compacta pelo cliente e não é persistido no
 * servidor.
 */
export function useChat() {
  return useMutation<ChatResponse, Error, ChatPayload>({
    mutationFn: async (payload) => {
      const { data } = await api.post<ChatResponse>("/chat/", payload);
      return data;
    },
  });
}
