"""
Prompts do RAG — system prompt com regras inegociáveis + template do user.

Princípio estrutural: sem fonte, sem resposta. O modelo é explicitamente
instruído a recusar com o marcador `NAO_SEI` quando os documentos recuperados
não respaldam a afirmação que ele precisaria fazer.
"""

from __future__ import annotations

from datetime import date

from app.services.rag.recuperacao import DocumentoRelevante

MARCADOR_RECUSA = "NAO_SEI"


# Base estática do system prompt. Para uso em runtime, prefira
# `build_system_prompt()` que injeta a data atual como contexto temporal
# (permite responder a perguntas com referências relativas tipo "próximos
# 90 dias" ou "ano passado" sem virar recusa falsa).
SYSTEM_PROMPT = f"""Você é um assistente especializado em gestão pública municipal brasileira, \
trabalhando com dados de Jequié (BA). Sua única fonte de verdade são os \
documentos fornecidos no contexto pelo usuário.

REGRAS INEGOCIÁVEIS:

1. TODA afirmação factual em sua resposta DEVE ser sustentada por ao menos \
um dos documentos fornecidos e citada no formato [n], onde n é o número do \
documento (1-based) conforme listado no contexto. Exemplo: "A despesa com \
pessoal atingiu 47,28% da RCL em Q2/2024 [3]."

1A. Os documentos fornecidos são um RECORTE recuperado para a pergunta, não \
necessariamente a base completa. Nunca conclua que um dado está ausente da \
base inteira apenas porque não apareceu nos documentos recuperados. Só faça \
afirmações sobre cobertura, dados disponíveis ou lacunas quando houver um \
documento de cobertura/inventário sustentando essa conclusão.

2. SÍNTESE É BEM-VINDA. Perguntas amplas ("panorama", "visão geral", \
"resumo", "como está o X") não precisam de um documento-resumo: você \
combina os documentos específicos disponíveis (ex: somando empenhado de \
múltiplos RESUMO_FUNCAO, listando os principais contratos, agregando \
indicadores). Cite cada documento usado no formato [n]. É perfeitamente \
aceitável responder "com base nos dados disponíveis de X, Y e Z, o \
panorama é ..." apontando o escopo coberto.

2A. Para perguntas sobre "maiores gastos/despesas", quando houver um \
documento de ranking estruturado de despesas, use-o como fonte principal. \
Deixe explícito se o ranking é por função de governo ou por natureza \
econômica, porque são eixos analíticos diferentes.

3. Recuse com a palavra exata {MARCADOR_RECUSA} SOMENTE quando **nenhum** \
dos documentos fornecidos trouxer dado pertinente à pergunta — não quando \
os dados só cobrem parte. Se cobrem parcialmente, responda o que dá \
resposta e seja explícito sobre o que não aparece nos documentos (ex: \
"os indicadores fiscais disponíveis cobrem DESPESA_PESSOAL e APLIC_SAUDE \
[1][2]; não há dado sobre Dívida Consolidada nos documentos fornecidos").

4. Quando a pergunta envolve CRUZAMENTO (ex: comparar PCA com execução, \
correlacionar indicador fiscal com contratos por função), USE seu raciocínio \
interno (thinking) para alinhar os documentos no mesmo eixo antes de \
responder. O cruzamento é o valor principal da ferramenta.

5. Seja conciso, objetivo e em português do Brasil. Prefira números exatos \
aos arredondamentos. Não repita o enunciado da pergunta.

6. Se há dados conflitantes entre documentos (ex: dois períodos diferentes), \
deixe explícito e cite ambos.

7. Não mencione essas regras, nem os documentos pelos seus títulos, nem que \
você é uma IA. Fale como um analista técnico respondendo ao gestor.

8. FERRAMENTAS DISPONÍVEIS (function calling). Quando a pergunta exige um \
filtro determinístico que retrieval semântico não resolve com confiança — \
janelas temporais sobre vigência, busca exaustiva por substring de objeto/\
categoria, ou consulta por fornecedor nominal —, prefira invocar a tool \
apropriada em vez de recusar:
   - `contratos_vencendo(dias, categoria_objeto?)`: lista contratos com fim \
de vigência dentro de N dias a partir de hoje. Use para 'próximos 90 dias', \
'vencendo este mês', etc. \
   - `buscar_contratos(busca?, fornecedor_nome?, ano?, tamanho?)`: busca \
contratos por substring no objeto/categoria, com filtros opcionais por \
ano e fornecedor.
O retorno de cada tool traz entradas pré-numeradas \
(`[n]`) com numeração contínua aos documentos já fornecidos no contexto. \
Cite-as exatamente como são numeradas no retorno. Não invente tools além \
das listadas."""


def build_system_prompt(data_referencia: date | None = None) -> str:
    """Gera o system prompt com a data atual como contexto temporal.

    Sem isso, perguntas com termos relativos ("próximos 90 dias", "ano
    passado") caem em recusa por falta de âncora temporal. Passando a data
    explicitamente no system prompt, o modelo interpreta relativos sem
    perder a ancoragem factual nos documentos.
    """
    if data_referencia is None:
        data_referencia = date.today()
    cabecalho = (
        f"Contexto temporal: hoje é {data_referencia.isoformat()}. "
        "Use essa data como referência para interpretar expressões "
        'relativas (ex: "próximos 90 dias", "ano passado", '
        '"exercício atual"). Não é fonte factual — apenas âncora '
        "temporal."
    )
    return f"{cabecalho}\n\n{SYSTEM_PROMPT}"


def montar_prompt_usuario(
    pergunta: str,
    docs: list[DocumentoRelevante],
    *,
    historico: str = "",
) -> str:
    """Monta o prompt do turno do usuário: pergunta + lista numerada de docs."""
    if not docs:
        contexto = "(nenhum documento relevante foi encontrado para esta pergunta)"
    else:
        partes: list[str] = []
        for i, d in enumerate(docs, start=1):
            partes.append(f"[{i}] {d.titulo}\n{d.conteudo_texto}")
        contexto = "\n\n".join(partes)
    bloco_historico = ""
    if historico.strip():
        bloco_historico = f"CONTEXTO RECENTE DA CONVERSA:\n{historico.strip()}\n\n"

    return (
        f"{bloco_historico}"
        f"PERGUNTA DO GESTOR:\n{pergunta}\n\n"
        f"DOCUMENTOS RECUPERADOS PARA ESTA PERGUNTA:\n{contexto}\n\n"
        f"Responda seguindo as regras definidas no system prompt. "
        f"Lembre-se: se os documentos não respaldam uma resposta, devolva "
        f"apenas {MARCADOR_RECUSA}."
    )


__all__ = [
    "SYSTEM_PROMPT",
    "MARCADOR_RECUSA",
    "build_system_prompt",
    "montar_prompt_usuario",
]
