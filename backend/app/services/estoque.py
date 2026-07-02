"""Serviço de Estoque Multi-local (Prioridade 3).

Centraliza movimentações (entrada/saída/reserva), valorização por **custo médio
ponderado** e os relatórios de saldo/alerta/ranking. Tudo em ``Decimal``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.estoque import (
    LOCAL_FULFILLMENT,
    MOV_ENTRADA,
    MOV_LIBERACAO,
    MOV_RESERVA,
    MOV_SAIDA,
    EstoqueSaldo,
    Local,
    MovimentoEstoque,
)
from app.models.produto import Produto
from app.models.venda import Venda
from app.parsers.common import STATUS_VALIDO

ZERO = Decimal("0")
Q_CUSTO = Decimal("0.0001")
Q_QTD = Decimal("0.001")


def _d(valor) -> Decimal:
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


def obter_ou_criar_saldo(db: Session, produto_id: int, local_id: int) -> EstoqueSaldo:
    saldo = db.execute(
        select(EstoqueSaldo).where(
            EstoqueSaldo.produto_id == produto_id,
            EstoqueSaldo.local_id == local_id,
        )
    ).scalar_one_or_none()
    if saldo is None:
        saldo = EstoqueSaldo(
            produto_id=produto_id, local_id=local_id,
            qtd_disponivel=ZERO, qtd_reservada=ZERO, custo_medio=ZERO,
        )
        db.add(saldo)
        db.flush()
    return saldo


def _registrar_movimento(
    db: Session, *, produto_id: int, local_id: int, tipo: str, qtd: Decimal,
    custo_unitario: Decimal | None = None, origem: str | None = None,
    referencia: str | None = None, observacao: str | None = None,
) -> MovimentoEstoque:
    mov = MovimentoEstoque(
        produto_id=produto_id, local_id=local_id, tipo=tipo, qtd=qtd,
        custo_unitario=custo_unitario, origem=origem, referencia=referencia,
        observacao=observacao,
    )
    db.add(mov)
    return mov


def registrar_entrada(
    db: Session, *, produto_id: int, local_id: int, qtd: Decimal,
    custo_unitario: Decimal | None = None, origem: str = "compra",
    referencia: str | None = None,
) -> EstoqueSaldo:
    """Recebimento de compra: soma ao disponível e atualiza o custo médio."""
    qtd = _d(qtd)
    if qtd <= 0:
        raise HTTPException(422, "Quantidade de entrada deve ser positiva")

    saldo = obter_ou_criar_saldo(db, produto_id, local_id)
    custo_unitario = _d(custo_unitario) if custo_unitario is not None else saldo.custo_medio

    disp_atual = _d(saldo.qtd_disponivel)
    nova_qtd = disp_atual + qtd
    if nova_qtd > 0:
        total = disp_atual * _d(saldo.custo_medio) + qtd * custo_unitario
        saldo.custo_medio = (total / nova_qtd).quantize(Q_CUSTO)
    saldo.qtd_disponivel = nova_qtd

    _registrar_movimento(
        db, produto_id=produto_id, local_id=local_id, tipo=MOV_ENTRADA,
        qtd=qtd, custo_unitario=custo_unitario, origem=origem, referencia=referencia,
    )
    db.flush()
    return saldo


def registrar_saida(
    db: Session, *, produto_id: int, local_id: int, qtd: Decimal,
    origem: str = "venda", referencia: str | None = None,
    permitir_negativo: bool = False,
) -> EstoqueSaldo:
    """Venda/baixa: subtrai do disponível (não altera o custo médio)."""
    qtd = _d(qtd)
    if qtd <= 0:
        raise HTTPException(422, "Quantidade de saída deve ser positiva")

    saldo = obter_ou_criar_saldo(db, produto_id, local_id)
    disp = _d(saldo.qtd_disponivel)
    if not permitir_negativo and disp < qtd:
        raise HTTPException(
            422,
            f"Estoque insuficiente (disponível {disp}, solicitado {qtd})",
        )
    saldo.qtd_disponivel = disp - qtd

    _registrar_movimento(
        db, produto_id=produto_id, local_id=local_id, tipo=MOV_SAIDA,
        qtd=qtd, origem=origem, referencia=referencia,
    )
    db.flush()
    return saldo


def reservar(
    db: Session, *, produto_id: int, local_id: int, qtd: Decimal,
    referencia: str | None = None,
) -> EstoqueSaldo:
    """Move disponível -> reservada. Bloqueia se disponível <= 0 ou insuficiente."""
    qtd = _d(qtd)
    if qtd <= 0:
        raise HTTPException(422, "Quantidade de reserva deve ser positiva")

    saldo = obter_ou_criar_saldo(db, produto_id, local_id)
    disp = _d(saldo.qtd_disponivel)
    if disp <= 0 or disp < qtd:
        raise HTTPException(422, f"Sem disponível para reservar (disponível {disp})")

    saldo.qtd_disponivel = disp - qtd
    saldo.qtd_reservada = _d(saldo.qtd_reservada) + qtd
    _registrar_movimento(
        db, produto_id=produto_id, local_id=local_id, tipo=MOV_RESERVA,
        qtd=qtd, origem="reserva", referencia=referencia,
    )
    db.flush()
    return saldo


def liberar_reserva(
    db: Session, *, produto_id: int, local_id: int, qtd: Decimal,
    referencia: str | None = None,
) -> EstoqueSaldo:
    """Move reservada -> disponível."""
    qtd = _d(qtd)
    saldo = obter_ou_criar_saldo(db, produto_id, local_id)
    reserv = _d(saldo.qtd_reservada)
    if qtd <= 0 or reserv < qtd:
        raise HTTPException(422, f"Reserva insuficiente (reservado {reserv})")

    saldo.qtd_reservada = reserv - qtd
    saldo.qtd_disponivel = _d(saldo.qtd_disponivel) + qtd
    _registrar_movimento(
        db, produto_id=produto_id, local_id=local_id, tipo=MOV_LIBERACAO,
        qtd=qtd, origem="reserva", referencia=referencia,
    )
    db.flush()
    return saldo


# --------------------------------------------------------------------------- #
# Integração com vendas importadas                                              #
# --------------------------------------------------------------------------- #


def local_para_canal_logistico(db: Session, canal_logistico: str) -> Local | None:
    """Mapeia o canal logístico da venda para o local de estoque.

    ``ML Full`` -> local de fulfillment; demais -> primeiro galpão ativo.
    """
    if "Full" in (canal_logistico or ""):
        local = db.execute(
            select(Local).where(Local.tipo == LOCAL_FULFILLMENT)
        ).scalars().first()
        if local is not None:
            return local
    return db.execute(
        select(Local).where(Local.tipo == "galpao").order_by(Local.id)
    ).scalars().first()


def baixar_estoque_venda(
    db: Session, *, produto_id: int, canal_logistico: str, qtd: Decimal,
    referencia: str | None = None,
) -> EstoqueSaldo | None:
    """Baixa de estoque para uma venda válida. Não bloqueia (histórico pode
    ficar negativo). Retorna None se não houver local configurado."""
    local = local_para_canal_logistico(db, canal_logistico)
    if local is None:
        return None
    return registrar_saida(
        db, produto_id=produto_id, local_id=local.id, qtd=qtd,
        origem="importacao", referencia=referencia, permitir_negativo=True,
    )


class BaixaEstoqueBatch:
    """Baixa de estoque em lote para importação de planilhas.

    Carrega locais e saldos **uma única vez** em memória e acumula os
    movimentos, evitando uma query + flush por linha (que inviabilizava a
    importação de milhares de linhas em ambiente serverless). Chame ``baixar``
    por venda válida e faça um ``db.flush()`` único ao final da importação.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._ful = db.execute(
            select(Local).where(Local.tipo == LOCAL_FULFILLMENT).order_by(Local.id)
        ).scalars().first()
        self._galpao = db.execute(
            select(Local).where(Local.tipo == "galpao").order_by(Local.id)
        ).scalars().first()
        self._saldos: dict[tuple[int, int], EstoqueSaldo] = {
            (s.produto_id, s.local_id): s
            for s in db.execute(select(EstoqueSaldo)).scalars()
        }

    def _local_para(self, canal_logistico: str) -> Local | None:
        if "Full" in (canal_logistico or "") and self._ful is not None:
            return self._ful
        return self._galpao

    def baixar(
        self, *, produto_id: int, canal_logistico: str, qtd: Decimal,
        referencia: str | None = None,
    ) -> bool:
        """Registra a saída em memória. Retorna True se houve baixa."""
        local = self._local_para(canal_logistico)
        if local is None:
            return False
        qtd = _d(qtd)
        if qtd <= 0:
            return False

        chave = (produto_id, local.id)
        saldo = self._saldos.get(chave)
        if saldo is None:
            saldo = EstoqueSaldo(
                produto_id=produto_id, local_id=local.id,
                qtd_disponivel=ZERO, qtd_reservada=ZERO, custo_medio=ZERO,
            )
            self.db.add(saldo)
            self._saldos[chave] = saldo
        saldo.qtd_disponivel = _d(saldo.qtd_disponivel) - qtd

        self.db.add(
            MovimentoEstoque(
                produto_id=produto_id, local_id=local.id, tipo=MOV_SAIDA,
                qtd=qtd, origem="importacao", referencia=referencia,
            )
        )
        return True


# --------------------------------------------------------------------------- #
# Relatórios                                                                     #
# --------------------------------------------------------------------------- #


@dataclass
class AlertaEstoque:
    produto_id: int
    sku_base: str
    nome: str
    disponivel_total: Decimal
    estoque_minimo: Decimal


@dataclass
class RankingItem:
    sku_base: str | None
    unidades: Decimal
    liquido: Decimal


def valor_total_estoque(db: Session) -> Decimal:
    total = ZERO
    for saldo in db.execute(select(EstoqueSaldo)).scalars():
        total += _d(saldo.qtd_disponivel) * _d(saldo.custo_medio)
    return total.quantize(Decimal("0.01"))


def alertas_estoque(db: Session) -> list[AlertaEstoque]:
    """Produtos cujo disponível total (somando locais) <= estoque_minimo."""
    disp_por_produto: dict[int, Decimal] = {}
    for saldo in db.execute(select(EstoqueSaldo)).scalars():
        disp_por_produto[saldo.produto_id] = (
            disp_por_produto.get(saldo.produto_id, ZERO) + _d(saldo.qtd_disponivel)
        )

    alertas: list[AlertaEstoque] = []
    for produto in db.execute(select(Produto)).scalars():
        minimo = _d(produto.estoque_minimo)
        if minimo <= 0:
            continue  # sem mínimo definido -> não alerta
        disp = disp_por_produto.get(produto.id, ZERO)
        if disp <= minimo:
            alertas.append(
                AlertaEstoque(
                    produto_id=produto.id, sku_base=produto.sku_base,
                    nome=produto.nome, disponivel_total=disp, estoque_minimo=minimo,
                )
            )
    return alertas


def ranking_skus_vendidos(db: Session, limite: int = 10) -> list[RankingItem]:
    """Ranking de SKUs por unidades vendidas (vendas válidas)."""
    rows = db.execute(
        select(
            Venda.sku_base,
            func.sum(Venda.qtd).label("unidades"),
            func.sum(Venda.liquido_recebido).label("liquido"),
        )
        .where(Venda.status_erp == STATUS_VALIDO, Venda.sku_base.is_not(None))
        .group_by(Venda.sku_base)
        .order_by(func.sum(Venda.qtd).desc())
        .limit(limite)
    ).all()
    return [
        RankingItem(sku_base=r[0], unidades=_d(r[1]), liquido=_d(r[2]))
        for r in rows
    ]
