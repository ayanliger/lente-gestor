"""
Conector para o Portal da Transparência "Município Online".

URL base: `municipioonline.com.br/<slug>/cidadao/receita`
Stack do portal: ASP.NET Web Forms + AngularJS + DataTables.

Fluxo de consumo:

1. GET da página → extrair os hidden fields do Web Forms
   (`__VIEWSTATE`, `__EVENTVALIDATION`, `__VIEWSTATEGENERATOR`).
2. POST form-urlencoded na mesma URL, disparando o evento
   `ctl00$body$btnFiltrarRS` com `hfAnoR` + `hfMesR` para obter o HTML
   da listagem filtrada por mês/ano.
3. Para detalhamento por banco, POST `application/json` em
   `?o=R` com a chave da linha (`NuCnpj, DtAno, DtAnoMes, DtPeriodo,
   FlCovid19, CdItemReceita`). Resposta é
   `[{DsReceitaDetalhe: "...html..."}]` com os recolhimentos individuais.

O portal não expõe API REST formal; por isso o parsing de HTML fica
encapsulado aqui. Mudanças na estrutura de IDs/classes do portal
quebram o conector — há logging estruturado em todas as etapas
para facilitar diagnóstico.
"""

import json
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


# Campos ocultos do ASP.NET Web Forms que precisam ser ecoados no POST.
_HIDDEN_FIELDS = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")

# Evento que o portal dispara ao clicar em "Filtrar" na aba de receitas.
_EVENT_TARGET_RECEITAS = "ctl00$body$btnFiltrarRS"


class MunicipioOnlineClient:
    """Cliente para as páginas de receita do portal Município Online."""

    def __init__(
        self,
        base_url: str | None = None,
        slug: str | None = None,
        cnpj: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.municipio_online_base_url).rstrip("/")
        self.slug = (slug or settings.municipio_online_slug_jequie).strip("/")
        self.cnpj = cnpj or settings.pncp_cnpj_jequie
        self._client: httpx.AsyncClient | None = None

    @property
    def url_receitas(self) -> str:
        return f"{self.base_url}/{self.slug}/cidadao/receita"

    async def __aenter__(self) -> "MunicipioOnlineClient":
        self._client = httpx.AsyncClient(
            timeout=90.0,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "pt-BR,pt;q=0.9",
                "User-Agent": "LenteGestor/0.1 (+https://lente-gestor.web.app)",
            },
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "Use 'async with MunicipioOnlineClient() as client:' para inicializar."
            )
        return self._client

    # ──────────────────────────────────────────
    # Protocolo ASP.NET — listagem agregada
    # ──────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _obter_estado_form(self) -> dict[str, str]:
        """GET inicial para capturar tokens do Web Forms (`__VIEWSTATE` etc.)."""
        response = await self.client.get(self.url_receitas)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        estado: dict[str, str] = {}
        for nome in _HIDDEN_FIELDS:
            node = soup.find("input", {"name": nome})
            if node is None or not node.get("value"):
                logger.warning("municipio_online.campo_ausente", campo=nome)
                continue
            estado[nome] = node["value"]

        if "__VIEWSTATE" not in estado:
            raise RuntimeError(
                "Falha ao obter __VIEWSTATE do portal Município Online; "
                "layout da página pode ter mudado."
            )
        return estado

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def listar_receitas(self, ano: int, mes: int) -> list[dict]:
        """
        Lista os itens de receita arrecadados em (ano, mes) de Jequié.

        Retorna uma linha por (item de receita × fonte de recursos),
        incluindo uma linha agregada se o item não tiver fontes
        discriminadas. Campos:
        - keys (dict com NuCnpj, DtAno, DtAnoMes, DtPeriodo, FlCovid19,
          CdItemReceita) — necessários para o drill-down
        - poder, orgao, categoria
        - cod_item_receita, descricao_receita
        - data_emissao (string dd/mm/yyyy)
        - cod_fonte_recurso, descricao_fonte_recurso
        - valor_previsto, valor_atualizado, valor_arrecadado_periodo,
          valor_arrecadado_acumulado (strings com formato "R$ 1.234,56")
        """
        estado = await self._obter_estado_form()

        form = {
            **estado,
            "__EVENTTARGET": _EVENT_TARGET_RECEITAS,
            "__EVENTARGUMENT": "",
            "ctl00$body$hfAnoR": str(ano),
            "ctl00$body$hfMesR": f"{mes:02d}",
        }

        logger.info("municipio_online.listar_receitas.request", ano=ano, mes=mes)
        response = await self.client.post(
            self.url_receitas,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()

        registros = _parse_receitas_html(response.text)
        logger.info(
            "municipio_online.listar_receitas.parsed",
            ano=ano,
            mes=mes,
            total=len(registros),
        )
        return registros

    # ──────────────────────────────────────────
    # Drill-down — recolhimentos individuais
    # ──────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def obter_recolhimentos(self, keys: dict) -> list[dict]:
        """
        Drill-down de uma linha agregada: retorna os recolhimentos
        individuais com data de emissão, banco, valor, processo e histórico.

        Parâmetro `keys`: dict vindo do `data-key` do HTML agregado, com
        `NuCnpj`, `DtAno`, `DtAnoMes`, `DtPeriodo`, `FlCovid19`,
        `CdItemReceita`. Portal aceita os mesmos campos no body JSON.
        """
        uri = f"{self.url_receitas}?o=R"
        logger.debug("municipio_online.obter_recolhimentos.request", keys=keys)
        response = await self.client.post(
            uri,
            content=json.dumps(keys),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            logger.warning(
                "municipio_online.obter_recolhimentos.json_invalido",
                status=response.status_code,
            )
            return []

        if not isinstance(payload, list) or not payload:
            return []

        html = (payload[0] or {}).get("DsReceitaDetalhe") or ""
        if not html:
            return []

        recolhimentos = _parse_drill_down_html(html)
        logger.debug(
            "municipio_online.obter_recolhimentos.parsed",
            cod_item=keys.get("CdItemReceita"),
            total=len(recolhimentos),
        )
        return recolhimentos


# ──────────────────────────────────────────
# Parsers de HTML (puros, testáveis isoladamente)
# ──────────────────────────────────────────


# Estrutura real observada no portal (inspeção em 04/2026):
#
#   Linha principal (com `data-key`) — 13 células:
#     0  <td width="6px">        — célula de controle (vazia)
#     1  Poder                    — "Executivo"
#     2  Órgão                    — `serigyitem="orgaoReceita"`
#     3  Categoria                — "Obrigatória"/"Voluntária"
#     4  Código da receita        — "132101110102"
#     5  Descrição                — nome completo
#     6  Data de emissão
#     7  Valor previsto           — `serigyitem="valorPrevistoReceita"`
#     8  Valor atualizado
#     9  Arrecadado no período
#    10  Arrecadado acumulado
#    11  % realização
#    12  CNPJ (oculto)
#
#   Sub-linha (sem `data-key`, uma por fonte de recursos) — 13 células:
#     0–6  TDs vazios/ocultos (display:none) para manter alinhamento
#     7    Descrição da fonte (colspan="7") — "15000000 - Recursos..."
#     8    Valor previsto da fonte
#     9    Valor atualizado da fonte
#    10    Arrecadado no período (fonte)
#    11    Arrecadado acumulado (fonte)
#    12    %  (vazio)
#
# Cada fonte é uma TR separada; descrição e valores virão 1-para-1.
# No-op para linhas com menos células (variam entre réguas de total
# e linhas de rodapé).

_COL_CONTROLE = 0
_COL_PODER = 1
_COL_ORGAO = 2
_COL_CATEGORIA = 3
_COL_COD = 4
_COL_DESCRICAO = 5
_COL_DATA = 6
_COL_PREVISTO = 7
_COL_ATUALIZADO = 8
_COL_PERIODO = 9
_COL_ACUMULADO = 10

_SUB_COL_DESCRICAO = 7
_SUB_COL_PREVISTO = 8
_SUB_COL_ATUALIZADO = 9
_SUB_COL_PERIODO = 10
_SUB_COL_ACUMULADO = 11


def _parse_receitas_html(html: str) -> list[dict]:
    """
    Parse da listagem agregada. Emite uma linha por fonte de recursos;
    se um item não tiver fontes discriminadas, emite uma linha única
    com `cod_fonte_recurso=None`. Ver comentário no topo do módulo para
    a ordem real das colunas do portal.
    """
    soup = BeautifulSoup(html, "lxml")
    registros: list[dict] = []
    trs = soup.find_all("tr")

    for i, row in enumerate(trs):
        data_key_attr = row.get("data-key")
        if not data_key_attr:
            continue
        try:
            keys = json.loads(data_key_attr)
        except (ValueError, TypeError):
            logger.warning("municipio_online.data_key_invalido", valor=data_key_attr)
            continue
        cells = row.find_all("td")
        if len(cells) <= _COL_ACUMULADO:
            logger.debug("municipio_online.linha_curta", n_cells=len(cells))
            continue

        base = {
            "keys": keys,
            "poder": cells[_COL_PODER].get_text(strip=True),
            "orgao": cells[_COL_ORGAO].get_text(strip=True),
            "categoria": cells[_COL_CATEGORIA].get_text(strip=True),
            "cod_item_receita": cells[_COL_COD].get_text(strip=True)
            or str(keys.get("CdItemReceita", "")),
            "descricao_receita": cells[_COL_DESCRICAO].get_text(strip=True),
            "data_emissao": cells[_COL_DATA].get_text(strip=True),
            "valor_previsto_total": cells[_COL_PREVISTO].get_text(strip=True),
            "valor_atualizado_total": cells[_COL_ATUALIZADO].get_text(strip=True),
            "valor_arrecadado_periodo_total": cells[_COL_PERIODO].get_text(strip=True),
            "valor_arrecadado_acumulado_total": cells[_COL_ACUMULADO].get_text(
                strip=True
            ),
        }

        # Sub-linhas de fontes de recursos (sem data-key) até a próxima linha principal.
        fontes = _coletar_fontes_recursos(trs, i + 1)

        if not fontes:
            registros.append(
                {
                    **base,
                    "cod_fonte_recurso": None,
                    "descricao_fonte_recurso": None,
                    "valor_previsto": base["valor_previsto_total"],
                    "valor_atualizado": base["valor_atualizado_total"],
                    "valor_arrecadado_periodo": base["valor_arrecadado_periodo_total"],
                    "valor_arrecadado_acumulado": base[
                        "valor_arrecadado_acumulado_total"
                    ],
                }
            )
        else:
            for fonte in fontes:
                registros.append({**base, **fonte})

    return registros


def _coletar_fontes_recursos(trs: list, inicio: int) -> list[dict]:
    """
    Extrai as fontes de recursos de sub-linhas (sem data-key) até
    encontrar a próxima linha principal ou acabar a tabela.

    Cada sub-linha é uma TR com 7 TDs ocultos para alinhar seguido
    de 4 colunas de valores. Uma linha = uma fonte.
    """
    fontes: list[dict] = []
    for next_row in trs[inicio:]:
        if next_row.get("data-key"):
            break
        next_cells = next_row.find_all("td")
        if len(next_cells) <= _SUB_COL_ACUMULADO:
            continue

        descricoes = list(next_cells[_SUB_COL_DESCRICAO].stripped_strings)
        if not descricoes:
            continue
        previstos = list(next_cells[_SUB_COL_PREVISTO].stripped_strings)
        atualizados = list(next_cells[_SUB_COL_ATUALIZADO].stripped_strings)
        periodos = list(next_cells[_SUB_COL_PERIODO].stripped_strings)
        acumulados = list(next_cells[_SUB_COL_ACUMULADO].stripped_strings)

        for j, desc_fonte in enumerate(descricoes):
            partes = desc_fonte.split(" - ", 1)
            cod_fonte = partes[0].strip() if partes else None
            descricao_fonte = partes[1].strip() if len(partes) > 1 else None
            fontes.append(
                {
                    "cod_fonte_recurso": cod_fonte,
                    "descricao_fonte_recurso": descricao_fonte,
                    "valor_previsto": previstos[j] if j < len(previstos) else None,
                    "valor_atualizado": atualizados[j]
                    if j < len(atualizados)
                    else None,
                    "valor_arrecadado_periodo": periodos[j]
                    if j < len(periodos)
                    else None,
                    "valor_arrecadado_acumulado": acumulados[j]
                    if j < len(acumulados)
                    else None,
                }
            )
    return fontes


def _parse_drill_down_html(html: str) -> list[dict]:
    """
    Parse do HTML do drill-down (`DsReceitaDetalhe`).

    O Receita.js do portal popula um template (`ReceitaDetalhe.htm`)
    mapeando campos para classes CSS:
        DtEmissao       → .dt_emissao
        NuProcesso      → .nu_processo
        DsContaBanco    → .ds_contaBanco
        VlRecolhimento  → .vl_realizado
        DsHistorico     → .ds_observacao

    Cada repetição do template vira um wrapper (geralmente `<tr>`)
    contendo esses 5 campos. Estratégia: localizar todos os
    `.dt_emissao` e, para cada um, descer no ancestral mais próximo
    que contenha os outros campos.
    """
    soup = BeautifulSoup(html, "lxml")
    recolhimentos: list[dict] = []

    for dt_node in soup.select(".dt_emissao"):
        wrapper = dt_node.find_parent(["tr", "div", "li", "article"]) or dt_node.parent
        if wrapper is None:
            continue

        def _text(selector: str) -> str | None:
            node = wrapper.select_one(selector)
            return node.get_text(strip=True) if node else None

        recolhimentos.append(
            {
                "DtEmissao": dt_node.get_text(strip=True),
                "NuProcesso": _text(".nu_processo"),
                "DsContaBanco": _text(".ds_contaBanco"),
                "VlRecolhimento": _text(".vl_realizado"),
                "DsHistorico": _text(".ds_observacao"),
            }
        )
    return recolhimentos
