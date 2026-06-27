"""Serviço de Pedidos de Compra (Prioridade 4).

Fluxo rascunho -> aprovado -> recebido, com:
- geração de conta a pagar na aprovação,
- entrada de estoque (custo médio ponderado) no recebimento,
- sugestão automática de quantidade a repor por SKU.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.compra import (
    PEDIDO_APROVADO,
    PEDIDO_RASCUNHO,
    PEDIDO_RECEBIDO,
    ItemPedidoCompra,
    PedidoCompra,
)
from app.models.estoque import LOCAL_GALPAO, EstoqueSaldo, Local
from app.models.financeiro import CONTA_ABERTA, ContaPagar
from app.models.fornecedor import Fornecedor
from app.models.produto import Produto
from app.models.venda import Venda
from app.parsers.common import STATUS_VALIDO
from app.services.estoque import registrar_entrada

ZERO = Decimal("0")


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def criar_pedido(
    db: Session, *, fornecedor_id: int, itens: list[dict],
    observacao: str | None = None, local_id: int | None = None,
) -> PedidoCompra:
    if db.get(Fornecedor, fornecedor_id) is None:
        raise HTTPException(422, f"Fornecedor id={fornecedor_id} não encontrado")
    if not itens:
        raise HTTPException(422, "Pedido precisa de ao menos um item")

    pedido = PedidoCompra(
        fornecedor_id=fornecedor_id, observacao=observacao,
        local_id=local_id, status=PEDIDO_RASCUNHO,
    )
    for item in itens:
        if db.get(Produto, item["produto_id"]) is None:
            raise HTTPException(422, f"Produto id={item['produto_id']} não encontrado")
        pedido.itens.append(
            ItemPedidoCompra(
                produto_id=item["produto_id"],
                qtd=_d(item["qtd"]),
                custo_unitario=_d(item.get("custo_unitario", 0)),
            )
        )
    db.add(pedido)
    db.flush()
    return pedido


def aprovar_pedido(db: Session, pedido_id: int) -> PedidoCompra:
    """Aprova o pedido e gera o lançamento em contas a pagar."""
    pedido = _obter(db, pedido_id)
    if pedido.status != PEDIDO_RASCUNHO:
        raise HTTPException(422, f"Só é possível aprovar pedidos em rascunho (atual: {pedido.status})")

    pedido.status = PEDIDO_APROVADO
    pedido.aprovado_em = datetime.utcnow()

    fornecedor = db.get(Fornecedor, pedido.fornecedor_id)
    dias = (fornecedor.condicoes_pagamento_dias or 0) if fornecedor else 0
    conta = ContaPagar(
        fornecedor_id=pedido.fornecedor_id,
        pedido_compra_id=pedido.id,
        descricao=f"Pedido de compra #{pedido.id}",
        valor=pedido.total,
        vencimento=date.today() + timedelta(days=dias),
        status=CONTA_ABERTA,
    )
    db.add(conta)
    db.flush()
    return pedido


def receber_pedido(db: Session, pedido_id: int, *, local_id: int | None = None) -> PedidoCompra:
    """Recebe o pedido: incrementa o estoque (custo médio) no local destino."""
    pedido = _obter(db, pedido_id)
    if pedido.status != PEDIDO_APROVADO:
        raise HTTPException(422, f"Só é possível receber pedidos aprovados (atual: {pedido.status})")

    destino = local_id or pedido.local_id or _galpao_padrao(db)
    if destino is None:
        raise HTTPException(422, "Nenhum local de estoque configurado para o recebimento")

    for item in pedido.itens:
        registrar_entrada(
            db, produto_id=item.produto_id, local_id=destino,
            qtd=_d(item.qtd), custo_unitario=_d(item.custo_unitario),
            origem="compra", referencia=f"PC#{pedido.id}",
        )

    pedido.status = PEDIDO_RECEBIDO
    pedido.recebido_em = datetime.utcnow()
    pedido.local_id = destino
    db.flush()
    return pedido


# --------------------------------------------------------------------------- #
# Sugestão automática de compra                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class SugestaoCompra:
    produto_id: int
    sku_base: str
    nome: str
    media_mensal: Decimal
    estoque_minimo: Decimal
    qtd_pendente: Decimal
    qtd_atual: Decimal
    qtd_sugerida: Decimal
    repor: bool


def sugestao_compra(db: Session, *, referencia: date | None = None) -> list[SugestaoCompra]:
    """Quantidade sugerida por SKU:

    ``qtd_sugerida = media_mensal + estoque_minimo + qtd_pendente - qtd_atual``

    - ``media_mensal``: unidades vendidas (válidas) nos últimos 30 dias.
    - ``qtd_pendente``: total reservado em estoque (pedidos de venda pendentes).
    - ``qtd_atual``: disponível somando os locais.
    """
    ref = referencia or date.today()
    corte = datetime(ref.year, ref.month, ref.day) - timedelta(days=30)

    # Vendas (válidas) por sku_base nos últimos 30 dias.
    vendas_rows = db.execute(
        select(Venda.sku_base, func.sum(Venda.qtd))
        .where(
            Venda.status_erp == STATUS_VALIDO,
            Venda.sku_base.is_not(None),
            Venda.data_venda >= corte,
        )
        .group_by(Venda.sku_base)
    ).all()
    vendas_por_sku = {r[0]: _d(r[1]) for r in vendas_rows}

    # Saldos (disponível e reservado) por produto.
    disp_por_produto: dict[int, Decimal] = {}
    reserv_por_produto: dict[int, Decimal] = {}
    for saldo in db.execute(select(EstoqueSaldo)).scalars():
        disp_por_produto[saldo.produto_id] = (
            disp_por_produto.get(saldo.produto_id, ZERO) + _d(saldo.qtd_disponivel)
        )
        reserv_por_produto[saldo.produto_id] = (
            reserv_por_produto.get(saldo.produto_id, ZERO) + _d(saldo.qtd_reservada)
        )

    sugestoes: list[SugestaoCompra] = []
    for produto in db.execute(select(Produto)).scalars():
        media_mensal = vendas_por_sku.get(produto.sku_base, ZERO)
        minimo = _d(produto.estoque_minimo)
        pendente = reserv_por_produto.get(produto.id, ZERO)
        atual = disp_por_produto.get(produto.id, ZERO)
        sugerida = media_mensal + minimo + pendente - atual

        # Só lista produtos com algum sinal de movimento ou mínimo definido.
        if media_mensal == 0 and minimo == 0 and atual == 0 and pendente == 0:
            continue

        sugestoes.append(
            SugestaoCompra(
                produto_id=produto.id, sku_base=produto.sku_base, nome=produto.nome,
                media_mensal=media_mensal, estoque_minimo=minimo,
                qtd_pendente=pendente, qtd_atual=atual,
                qtd_sugerida=sugerida, repor=sugerida > 0,
            )
        )
    sugestoes.sort(key=lambda s: s.qtd_sugerida, reverse=True)
    return sugestoes


# --------------------------------------------------------------------------- #
# Internos                                                                       #
# --------------------------------------------------------------------------- #


def _obter(db: Session, pedido_id: int) -> PedidoCompra:
    pedido = db.get(PedidoCompra, pedido_id)
    if pedido is None:
        raise HTTPException(404, "Pedido de compra não encontrado")
    return pedido


def _galpao_padrao(db: Session) -> int | None:
    local = db.execute(
        select(Local).where(Local.tipo == LOCAL_GALPAO).order_by(Local.id)
    ).scalars().first()
    return local.id if local else None
