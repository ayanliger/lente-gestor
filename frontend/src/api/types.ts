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

export interface ExecucaoOrcamentaria {
  id: string;
  exercicio: number;
  periodo: number | null;
  periodicidade: string | null;
  tipo_relatorio: string;
  anexo: string;
  rotulo: string | null;
  coluna: string;
  cod_conta: string;
  conta: string;
  valor: number | null;
  orgao_id: string;
  cod_ibge: string;
  fonte: string;
  ingerido_em: string;
}

export interface ResumoFuncao {
  funcao: string;
  dotacao_inicial: number | null;
  dotacao_atualizada: number | null;
  empenhado: number | null;
  liquidado: number | null;
  saldo: number | null;
}

export type SituacaoIndicador =
  | "OK"
  | "ALERTA"
  | "EXCEDIDO"
  | "ABAIXO_MINIMO"
  | "SEM_DADO";

export interface IndicadorFiscal {
  id: string;
  exercicio: number;
  periodo: number | null;
  codigo: string;
  descricao: string;
  unidade: string;
  valor: number | null;
  limite_legal: number | null;
  situacao: SituacaoIndicador;
  fonte_relatorio: string;
  fonte_exercicio: number | null;
  fonte_periodo: number | null;
  calculado_em: string;
}

export interface DadosMunicipio {
  id: string;
  codigo_ibge: string;
  exercicio: number;
  nome_municipio: string | null;
  uf: string | null;
  populacao: number | null;
  pib_corrente: number | null;
  pib_per_capita: number | null;
  fonte: string;
  ingerido_em: string;
}

// ─────────────────────────────────────
// Arrecadação tributária
// ─────────────────────────────────────

export interface Arrecadacao {
  id: string;
  orgao_id: string;
  cod_ibge: string;
  exercicio: number;
  mes: number;
  data_emissao: string | null;
  cod_item_receita: string;
  descricao_receita: string;
  poder: string | null;
  categoria: string | null;
  cod_fonte_recurso: string | null;
  descricao_fonte_recurso: string | null;
  valor_previsto: number | null;
  valor_atualizado: number | null;
  valor_arrecadado_periodo: number | null;
  valor_arrecadado_acumulado: number | null;
  fonte: string;
  ingerido_em: string;
}

export interface RecolhimentoDetalhe {
  id: string;
  arrecadacao_id: string;
  orgao_id: string;
  exercicio: number;
  mes: number;
  data_emissao: string | null;
  numero_processo: string | null;
  banco: string;
  historico: string | null;
  valor: number | null;
  ingerido_em: string;
}

export interface SerieAnualArrecadacao {
  exercicio: number;
  valor: number;
}

export interface SerieMensalArrecadacao {
  mes: number;
  valor: number;
}

export interface AgregacaoEspecie {
  especie: string;
  valor: number;
  pct: number;
}

export interface TopTributo {
  cod_item_receita: string;
  descricao_receita: string;
  valor: number;
  pct: number;
}

export interface AnoEspecie {
  exercicio: number;
  especie: string;
  valor: number;
}

export interface AgregacaoBanco {
  banco: string;
  valor: number;
  pct: number;
}

export interface ResumoArrecadacao {
  exercicio: number;
  total_arrecadado: number;
  total_previsto: number | null;
  pct_realizacao: number | null;
  delta_yoy: number | null;
  n_tributos: number;
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
