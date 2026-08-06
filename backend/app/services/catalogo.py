"""Cadastro em massa de produtos a partir de uma planilha (catálogo).

Regra do SKU (definida no prompt do projeto): o SKU não é digitado, é
**extraído automaticamente** do nome do produto, usando a parte final da
descrição a partir do primeiro dígito, mantendo apenas letras e números.

Exemplos oficiais (todos passam por ``extrair_sku``):

    Retentor 5699              -> 5699
    Aneis 9200STD             -> 9200STD
    Anel 8126 STD             -> 8126STD
    Anel SDA7092              -> 7092
    Anel SDA6631 050          -> 6631050
    Jogo de Anel 7224-STD     -> 7224STD
    Jogo de Anel 7224 050     -> 7224050
    Bronzina De Biela SBB 1035-J 0,25 -> 1035J025
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.parsers.common import to_decimal, to_str

_PRIMEIRO_DIGITO = re.compile(r"\d")
_NAO_ALFANUM = re.compile(r"[^0-9A-Za-z]")


def extrair_sku(nome: str) -> str:
    """Deriva o SKU do nome do produto.

    Toma a substring a partir do primeiro dígito e remove tudo que não for
    letra ou número (espaços, hífens, barras, vírgulas, pontos). Retorna em
    maiúsculas. Se não houver dígito, cai para o nome inteiro sanitizado.
    """
    texto = (nome or "").strip()
    if not texto:
        return ""
    match = _PRIMEIRO_DIGITO.search(texto)
    trecho = texto[match.start():] if match else texto
    return _NAO_ALFANUM.sub("", trecho).upper()


def _categoria_por_nome(nome: str) -> str | None:
    n = (nome or "").strip().lower()
    if n.startswith(("anel", "aneis", "anéis", "jogo de anel", "jogo")):
        return "Anéis"
    if n.startswith("retentor"):
        return "Retentores"
    if n.startswith("bronzina"):
        return "Bronzinas"
    if n.startswith(("vedador", "vedadores")):
        return "Vedadores"
    return None


@dataclass
class LinhaCatalogo:
    nome: str
    custo: Decimal
    sku: str = ""


@dataclass
class ResultadoCatalogo:
    linhas: int = 0
    criados: int = 0
    atualizados: int = 0
    ignorados: int = 0
    erros: list[str] = field(default_factory=list)
    skus: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "linhas": self.linhas,
            "criados": self.criados,
            "atualizados": self.atualizados,
            "ignorados": self.ignorados,
            "erros": self.erros,
            "skus": self.skus,
        }


# Nomes de coluna aceitos (case-insensitive) para nome e custo.
_COLS_NOME = ("item", "nome", "produto", "descrição", "descricao", "item sku")
_COLS_CUSTO = (
    "valor de custo", "valor und", "custo", "preço de custo", "preco de custo",
    "valor unit", "valor unitário", "valor", "preço custo", "custo unitário",
)


def _achar_coluna(colunas: list[str], candidatos: tuple[str, ...]) -> str | None:
    normalizadas = {c.strip().lower(): c for c in colunas}
    for cand in candidatos:
        if cand in normalizadas:
            return normalizadas[cand]
    # match parcial (ex.: "Valor de Custo (R$)")
    for chave, original in normalizadas.items():
        if any(cand in chave for cand in candidatos):
            return original
    return None


def parse_catalogo(registros: list[dict]) -> list[LinhaCatalogo]:
    """Converte registros de planilha (dicts por linha) em ``LinhaCatalogo``.

    ``registros`` são as linhas já lidas (ex.: ``df.to_dict("records")``).
    """
    if not registros:
        return []
    colunas = list(registros[0].keys())
    col_nome = _achar_coluna(colunas, _COLS_NOME)
    col_custo = _achar_coluna(colunas, _COLS_CUSTO)
    if col_nome is None:
        raise ValueError(
            "Coluna de nome do produto não encontrada (esperado 'Item' ou 'Nome')."
        )

    linhas: list[LinhaCatalogo] = []
    for reg in registros:
        nome = to_str(reg.get(col_nome))
        if not nome:
            continue
        custo = to_decimal(reg.get(col_custo)) if col_custo else Decimal("0")
        linhas.append(LinhaCatalogo(nome=nome, custo=custo, sku=extrair_sku(nome)))
    return linhas


def importar_catalogo(db: Session, linhas: list[LinhaCatalogo]) -> ResultadoCatalogo:
    """Cria/atualiza produtos a partir das linhas do catálogo (upsert por SKU).

    Um SKU já existente tem apenas o preço de custo atualizado (o custo das
    vendas já importadas permanece congelado no momento da importação).
    """
    resultado = ResultadoCatalogo()
    existentes: dict[str, Produto] = {
        p.sku_base: p for p in db.execute(select(Produto)).scalars()
    }

    for linha in linhas:
        resultado.linhas += 1
        sku = linha.sku
        if not sku:
            resultado.ignorados += 1
            resultado.erros.append(f"Sem SKU extraível: '{linha.nome}'")
            continue

        produto = existentes.get(sku)
        if produto is None:
            produto = Produto(
                sku_base=sku,
                nome=linha.nome,
                categoria=_categoria_por_nome(linha.nome),
                preco_compra=linha.custo,
                ativo=True,
            )
            db.add(produto)
            existentes[sku] = produto
            resultado.criados += 1
        else:
            produto.preco_compra = linha.custo
            if not produto.nome:
                produto.nome = linha.nome
            resultado.atualizados += 1
        resultado.skus.append(sku)

    db.flush()
    return resultado
