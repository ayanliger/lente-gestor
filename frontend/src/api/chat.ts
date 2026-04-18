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

/**
 * Mutation para POST /api/v1/chat/.
 *
 * Stateless: cada chamada é independente. O histórico é mantido no
 * state local da página, não no servidor.
 */
export function useChat() {
  return useMutation<ChatResponse, Error, string>({
    mutationFn: async (pergunta) => {
      const { data } = await api.post<ChatResponse>("/chat/", { pergunta });
      return data;
    },
  });
}
