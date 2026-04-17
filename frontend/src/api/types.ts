export interface Orgao {
  id: string;
  cnpj: string;
  razao_social: string;
  esfera: string | null;
  uf: string | null;
  municipio: string | null;
  created_at: string;
}

export interface Fornecedor {
  id: string;
  cpf_cnpj: string;
  nome: string;
  tipo: string | null;
  created_at: string;
}

export interface Contratacao {
  id: string;
  pncp_id: string | null;
  numero_sequencial: number | null;
  ano: number | null;
  numero_processo: string | null;
  orgao_id: string | null;
  modalidade: string | null;
  tipo: string | null;
  objeto: string | null;
  valor_estimado: number | null;
  valor_homologado: number | null;
  situacao: string | null;
  data_publicacao: string | null;
  data_abertura: string | null;
  data_homologacao: string | null;
  fonte: string;
  ingerido_em: string;
  created_at: string;
}

export interface Contrato {
  id: string;
  pncp_id: string | null;
  numero_contrato: string | null;
  ano: number | null;
  contratacao_id: string | null;
  fornecedor_id: string | null;
  objeto: string | null;
  valor_inicial: number | null;
  valor_atual: number | null;
  valor_aditivos: number | null;
  data_assinatura: string | null;
  data_inicio_vigencia: string | null;
  data_fim_vigencia: string | null;
  situacao: string | null;
  categoria: string | null;
  subcategoria: string | null;
  fonte: string;
  ingerido_em: string;
  created_at: string;
  fornecedor?: Fornecedor | null;
  contratacao?: Contratacao | null;
}
