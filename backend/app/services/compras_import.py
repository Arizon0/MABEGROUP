"""Importação de compras a partir de uma planilha (entrada de estoque).

Cada linha é uma compra de um produto: SKU, quantidade, valor pago e frete.
Diferente da importação de estoque (que substitui o saldo), a compra **soma**
ao estoque e recalcula o custo médio ponderado, incluindo o frete rateado por
unidade (custo "landed"). Também atualiza o ``preco_compra`` do produto para o
custo mais recente.

Colunas aceitas (case-insensitive, match parcial):
- SKU: ``SKU`` / ``Código`` / ``Referência`` (ou ``Nome`` para derivar o SKU).
- Quantidade: ``Quantidade`` / ``Qtd`` / ``Unidades``.
- Valor pago: ``Valor pago`` / ``Valor unitário`` / ``Custo`` (custo por unidade).
  Se houver coluna de total (``Valor total`` / ``Total pago``), ela é dividida
  pela quantidade.
- Frete: ``Frete`` (total da linha; rateado por unidade). Opcional.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.sku_map import SkuMap
from app.parsers.common import to_decimal, to_str
from app.services.catalogo import _achar_coluna, extrair_sku
from app.services.estoque import _d, registrar_entrada
from app.services.estoque_import import _local_default, _resolver_produto

ZERO = Decimal("0")
CENT = Decimal("0.01")
Q_QTD = Decimal("0.001")
Q_CUSTO = Decimal("0.0001")

_COLS_SKU = ("sku base", "sku", "código", "codigo", "cod", "referência", "referencia", "ref")
_COLS_NOME = ("item", "nome", "produto", "descrição", "descricao")
_COLS_QTD = ("quantidade", "quantia", "qtd", "unidades", "qtde")
_COLS_VALOR_UNIT = (
    "valor pago", "valor unitário", "valor unitario", "custo unitário",
    "custo unitario", "preço unitário", "preco unitario", "valor und", "custo", "preço", "preco",
)
_COLS_VALOR_TOTAL = ("valor total", "total pago", "valor da compra", "total")
_COLS_FRETE = ("frete", "valor frete", "frete total", "envio")


@dataclass
class LinhaCompra:
    sku_texto: str
    qtd: Decimal
    valor: Decimal          # unitário ou total (ver valor_eh_total)
    frete: Decimal = ZERO   # total da linha
    valor_eh_total: bool = False


@dataclass
class ResultadoComprasImport:
    linhas: int = 0
    entradas: int = 0
    ignorados: int = 0
    unidades_total: Decimal = ZERO
    total_pago: Decimal = ZERO      # Σ valor pago pelos produtos
    total_frete: Decimal = ZERO
    custo_total: Decimal = ZERO     # total_pago + total_frete (custo landed)
    local: str = ""
    nao_encontrados: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "linhas": self.linhas,
            "entradas": self.entradas,
            "ignorados": self.ignorados,
            "unidades_total": str(self.unidades_total.quantize(Q_QTD)),
            "total_pago": str(self.total_pago.quantize(CENT)),
            "total_frete": str(self.total_frete.quantize(CENT)),
            "custo_total": str(self.custo_total.quantize(CENT)),
            "local": self.local,
            "nao_encontrados": self.nao_encontrados,
            "erros": self.erros,
        }


def parse_compras(registros: list[dict]) -> list[LinhaCompra]:
    """Converte as linhas da planilha de compras em ``LinhaCompra``."""
    if not registros:
        return []
    colunas = list(registros[0].keys())
    col_sku = _achar_coluna(colunas, _COLS_SKU)
    col_nome = _achar_coluna(colunas, _COLS_NOME)
    col_qtd = _achar_coluna(colunas, _COLS_QTD)
    col_total = _achar_coluna(colunas, _COLS_VALOR_TOTAL)
    ocupadas = {c for c in (col_total,) if c}
    col_unit = _achar_coluna([c for c in colunas if c not in ocupadas], _COLS_VALOR_UNIT)
    col_frete = _achar_coluna(colunas, _COLS_FRETE)

    if col_sku is None and col_nome is None:
        raise ValueError("Coluna de SKU não encontrada (esperado 'SKU' ou 'Nome').")
    if col_qtd is None:
        raise ValueError("Coluna de quantidade não encontrada (esperado 'Quantidade').")
    if col_unit is None and col_total is None:
        raise ValueError(
            "Coluna de valor não encontrada (esperado 'Valor pago' ou 'Valor total')."
        )

    usa_total = col_unit is None and col_total is not None
    col_valor = col_total if usa_total else col_unit

    linhas: list[LinhaCompra] = []
    for reg in registros:
        sku_texto = to_str(reg.get(col_sku)) if col_sku else ""
        if not sku_texto and col_nome:
            sku_texto = to_str(reg.get(col_nome))
        if not sku_texto:
            continue
        linhas.append(
            LinhaCompra(
                sku_texto=sku_texto,
                qtd=to_decimal(reg.get(col_qtd)),
                valor=to_decimal(reg.get(col_valor)),
                frete=to_decimal(reg.get(col_frete)) if col_frete else ZERO,
                valor_eh_total=usa_total,
            )
        )
    return linhas


def importar_compras(
    db: Session, linhas: list[LinhaCompra], *, local_id: int | None = None
) -> ResultadoComprasImport:
    """Dá entrada no estoque para cada linha de compra (custo médio ponderado).

    Custo unitário landed = valor pago por unidade + frete rateado por unidade.
    Atualiza o ``preco_compra`` do produto para esse custo. SKUs não encontrados
    vão para ``nao_encontrados`` sem bloquear a importação.
    """
    resultado = ResultadoComprasImport()
    cache_local: dict = {}
    local = _local_default(db, local_id, cache_local)
    resultado.local = local.nome

    por_sku: dict[str, Produto] = {}
    for p in db.execute(select(Produto)).scalars():
        if p.sku_base:
            por_sku[p.sku_base.strip().upper()] = p
    por_canal: dict[str, Produto] = {}
    for sm in db.execute(select(SkuMap)).scalars():
        if sm.sku_canal and sm.produto_id:
            produto = db.get(Produto, sm.produto_id)
            if produto is not None:
                por_canal[sm.sku_canal.strip().upper()] = produto

    for linha in linhas:
        resultado.linhas += 1
        produto = _resolver_produto(linha.sku_texto, por_sku, por_canal)
        if produto is None:
            resultado.ignorados += 1
            if linha.sku_texto not in resultado.nao_encontrados:
                resultado.nao_encontrados.append(linha.sku_texto)
            continue

        qtd = _d(linha.qtd)
        if qtd <= 0:
            resultado.ignorados += 1
            continue

        frete = _d(linha.frete)
        valor = _d(linha.valor)
        valor_unit = (valor / qtd) if linha.valor_eh_total else valor
        pago_produtos = valor if linha.valor_eh_total else valor * qtd
        custo_unit = (valor_unit + frete / qtd).quantize(Q_CUSTO)

        registrar_entrada(
            db, produto_id=produto.id, local_id=local.id, qtd=qtd,
            custo_unitario=custo_unit, origem="compra",
            referencia="Importação de compras",
        )
        produto.preco_compra = custo_unit.quantize(CENT)

        resultado.entradas += 1
        resultado.unidades_total += qtd
        resultado.total_pago += pago_produtos
        resultado.total_frete += frete
        resultado.custo_total += pago_produtos + frete

    db.flush()
    return resultado
