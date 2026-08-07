"""Importação do estoque atual a partir de uma planilha (contagem/inventário).

O usuário sobe uma planilha com o que tem fisicamente em estoque hoje. Cada
linha traz um SKU e a quantidade atual; opcionalmente um custo unitário. O
serviço faz um **ajuste de inventário**: define o saldo disponível do SKU no
local igual ao valor da planilha (idempotente — reimportar não duplica) e
registra o movimento da diferença no ledger com origem ``inventario``.

Com o estoque valorizado (quantidade × custo), os cálculos que dependem de
estoque passam a considerar esses saldos: valor total do estoque, giro por SKU
e alertas de estoque mínimo.

Regra de custo (para valorização):
- Se a planilha traz um custo > 0, ele vira o custo médio do saldo.
- Senão, usa o ``preco_compra`` cadastrado do produto (mesma base do CMV).
- Senão, mantém o custo médio já existente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.estoque import (
    LOCAL_GALPAO,
    MOV_ENTRADA,
    MOV_SAIDA,
    EstoqueSaldo,
    Local,
    MovimentoEstoque,
)
from app.models.produto import Produto
from app.models.sku_map import SkuMap
from app.parsers.common import to_decimal, to_str
from app.services.catalogo import _achar_coluna, extrair_sku
from app.services.estoque import _d, obter_ou_criar_saldo

ZERO = Decimal("0")
CENT = Decimal("0.01")
Q_QTD = Decimal("0.001")

# Nomes de coluna aceitos (case-insensitive), com match parcial.
_COLS_SKU = ("sku base", "sku", "código", "codigo", "cod", "referência", "referencia", "ref")
_COLS_NOME = ("item", "nome", "produto", "descrição", "descricao")
_COLS_QTD = (
    "quantidade em estoque", "estoque atual", "qtd disponível", "qtd disponivel",
    "quantidade atual", "quantidade", "estoque", "saldo", "qtd", "unidades",
)
_COLS_CUSTO = (
    "custo unitário", "custo unitario", "valor de custo", "preço de custo",
    "preco de custo", "custo", "valor und", "valor unitário", "valor unitario",
)


@dataclass
class LinhaEstoque:
    sku_texto: str
    qtd: Decimal
    custo: Decimal | None = None


@dataclass
class ResultadoEstoqueImport:
    local: str = ""
    linhas: int = 0
    atualizados: int = 0
    saldos_criados: int = 0
    ignorados: int = 0
    unidades_total: Decimal = ZERO
    valor_total: Decimal = ZERO
    nao_encontrados: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "local": self.local,
            "linhas": self.linhas,
            "atualizados": self.atualizados,
            "saldos_criados": self.saldos_criados,
            "ignorados": self.ignorados,
            "unidades_total": str(self.unidades_total.quantize(Q_QTD)),
            "valor_total": str(self.valor_total.quantize(CENT)),
            "nao_encontrados": self.nao_encontrados,
            "erros": self.erros,
        }


def parse_estoque(registros: list[dict]) -> list[LinhaEstoque]:
    """Converte as linhas da planilha em ``LinhaEstoque``.

    Aceita uma coluna de SKU (``SKU``, ``Código``, ``Referência``) ou, na
    ausência dela, deriva o SKU do nome do produto. A coluna de quantidade é
    obrigatória. Custo é opcional.
    """
    if not registros:
        return []
    colunas = list(registros[0].keys())
    col_sku = _achar_coluna(colunas, _COLS_SKU)
    col_nome = _achar_coluna(colunas, _COLS_NOME)
    col_qtd = _achar_coluna(colunas, _COLS_QTD)
    col_custo = _achar_coluna(colunas, _COLS_CUSTO)

    if col_sku is None and col_nome is None:
        raise ValueError(
            "Coluna de SKU não encontrada (esperado 'SKU', 'Código' ou 'Nome')."
        )
    if col_qtd is None:
        raise ValueError(
            "Coluna de quantidade não encontrada (esperado 'Quantidade' ou 'Estoque')."
        )

    linhas: list[LinhaEstoque] = []
    for reg in registros:
        sku_texto = to_str(reg.get(col_sku)) if col_sku else ""
        if not sku_texto and col_nome:
            sku_texto = to_str(reg.get(col_nome))
        if not sku_texto:
            continue
        custo = to_decimal(reg.get(col_custo)) if col_custo else None
        linhas.append(
            LinhaEstoque(sku_texto=sku_texto, qtd=to_decimal(reg.get(col_qtd)), custo=custo)
        )
    return linhas


def _local_destino(db: Session, local_id: int | None) -> Local:
    """Local onde o estoque será lançado. Default: 1º galpão (cria se faltar)."""
    if local_id is not None:
        local = db.get(Local, local_id)
        if local is None:
            raise ValueError(f"Local id={local_id} não encontrado")
        return local
    local = db.execute(
        select(Local).where(Local.tipo == LOCAL_GALPAO).order_by(Local.id)
    ).scalars().first()
    if local is None:
        local = db.execute(select(Local).order_by(Local.id)).scalars().first()
    if local is None:
        local = Local(nome="Galpão Central", tipo=LOCAL_GALPAO)
        db.add(local)
        db.flush()
    return local


def _resolver_produto(
    texto: str, por_sku: dict[str, Produto], por_canal: dict[str, Produto]
) -> Produto | None:
    """Resolve o texto da planilha para um produto (sku_base, SKU derivado ou de-para)."""
    chave = texto.strip().upper()
    if chave in por_sku:
        return por_sku[chave]
    derivado = extrair_sku(texto)
    if derivado and derivado in por_sku:
        return por_sku[derivado]
    if chave in por_canal:
        return por_canal[chave]
    return None


def importar_estoque(
    db: Session, linhas: list[LinhaEstoque], *, local_id: int | None = None
) -> ResultadoEstoqueImport:
    """Ajusta o saldo de estoque de cada SKU para o valor informado na planilha.

    Define ``qtd_disponivel`` igual à quantidade da planilha (ajuste de
    inventário, idempotente) e registra a diferença no ledger. Atualiza o custo
    médio para valorização. SKUs não encontrados vão para ``nao_encontrados``
    sem bloquear a importação.
    """
    resultado = ResultadoEstoqueImport()
    local = _local_destino(db, local_id)
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
            resultado.nao_encontrados.append(linha.sku_texto)
            continue

        qtd_nova = _d(linha.qtd)
        saldo = obter_ou_criar_saldo(db, produto.id, local.id)
        criado = _d(saldo.qtd_disponivel) == ZERO and _d(saldo.custo_medio) == ZERO
        qtd_atual = _d(saldo.qtd_disponivel)
        delta = qtd_nova - qtd_atual

        # Custo médio para valorização (planilha > preço de compra > existente).
        if linha.custo is not None and _d(linha.custo) > 0:
            saldo.custo_medio = _d(linha.custo).quantize(Decimal("0.0001"))
        elif produto.preco_compra is not None and _d(produto.preco_compra) > 0:
            saldo.custo_medio = _d(produto.preco_compra).quantize(Decimal("0.0001"))

        saldo.qtd_disponivel = qtd_nova

        if delta != ZERO:
            db.add(
                MovimentoEstoque(
                    produto_id=produto.id, local_id=local.id,
                    tipo=MOV_ENTRADA if delta > 0 else MOV_SAIDA,
                    qtd=abs(delta), custo_unitario=_d(saldo.custo_medio),
                    origem="inventario", referencia="Importação de estoque",
                )
            )

        resultado.atualizados += 1
        if criado:
            resultado.saldos_criados += 1
        resultado.unidades_total += qtd_nova
        resultado.valor_total += qtd_nova * _d(saldo.custo_medio)

    db.flush()
    return resultado
