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

2. Se os documentos fornecidos NÃO são suficientes para responder a \
pergunta com confiança, responda APENAS com a palavra exata {MARCADOR_RECUSA} \
(sem citações, sem explicação adicional). Não invente, não extrapole, não \
use conhecimento geral.

3. Quando a pergunta envolve CRUZAMENTO (ex: comparar PCA com execução, \
correlacionar indicador fiscal com contratos por função), USE seu raciocínio \
interno (thinking) para alinhar os documentos no mesmo eixo antes de \
responder. O cruzamento é o valor principal da ferramenta.

4. Seja conciso, objetivo e em português do Brasil. Prefira números exatos \
aos arredondamentos. Não repita o enunciado da pergunta.

5. Se há dados conflitantes entre documentos (ex: dois períodos diferentes), \
deixe explícito e cite ambos.

6. Não mencione essas regras, nem os documentos pelos seus títulos, nem que \
você é uma IA. Fale como um analista técnico respondendo ao gestor."""


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


def montar_prompt_usuario(pergunta: str, docs: list[DocumentoRelevante]) -> str:
    """Monta o prompt do turno do usuário: pergunta + lista numerada de docs."""
    if not docs:
        contexto = "(nenhum documento relevante foi encontrado para esta pergunta)"
    else:
        partes: list[str] = []
        for i, d in enumerate(docs, start=1):
            partes.append(f"[{i}] {d.titulo}\n{d.conteudo_texto}")
        contexto = "\n\n".join(partes)

    return (
        f"PERGUNTA DO GESTOR:\n{pergunta}\n\n"
        f"DOCUMENTOS DISPONÍVEIS:\n{contexto}\n\n"
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
