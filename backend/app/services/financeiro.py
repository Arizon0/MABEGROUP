"""Serviço financeiro — Contas a Pagar/Receber (Prioridade 5).

Os recebíveis são lançados a cada importação de venda; os pagáveis a cada
aprovação de pedido de compra (ver ``services/compras.py``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.financeiro import CONTA_ABERTA, ContaPagar, ContaReceber
from app.models.venda import Venda
from app.parsers.common import STATUS_VALIDO

ZERO = Decimal("0")


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def gerar_contas_receber(db: Session, vendas: list[Venda]) -> int:
    """Cria um recebível por venda válida com líquido != 0.

    Evita duplicar: pula vendas cujo (canal, id_pedido_canal) já tem recebível.
    Retorna a quantidade de recebíveis criados.
    """
    existentes = {
        (c.canal, c.id_pedido_canal)
        for c in db.execute(select(ContaReceber)).scalars()
    }
    criadas = 0
    for v in vendas:
        if v.status_erp != STATUS_VALIDO or _d(v.liquido_recebido) == ZERO:
            continue
        chave = (v.canal, v.id_pedido_canal)
        if chave in existentes:
            continue
        db.add(
            ContaReceber(
                canal=v.canal,
                id_pedido_canal=v.id_pedido_canal,
                descricao=f"Venda {v.canal} {v.id_pedido_canal}",
                valor=_d(v.liquido_recebido),
                competencia=v.data_venda.date() if v.data_venda else None,
                status=CONTA_ABERTA,
            )
        )
        existentes.add(chave)
        criadas += 1
    db.flush()
    return criadas


@dataclass
class ResumoConta:
    total: Decimal = field(default_factory=lambda: ZERO)
    aberto: Decimal = field(default_factory=lambda: ZERO)
    liquidado: Decimal = field(default_factory=lambda: ZERO)
    quantidade: int = 0


@dataclass
class ResumoFinanceiro:
    a_pagar: ResumoConta
    a_receber: ResumoConta

    @property
    def saldo_projetado(self) -> Decimal:
        return self.a_receber.total - self.a_pagar.total

    def as_dict(self) -> dict:
        return {
            "a_pagar": {
                "total": str(self.a_pagar.total),
                "aberto": str(self.a_pagar.aberto),
                "liquidado": str(self.a_pagar.liquidado),
                "quantidade": self.a_pagar.quantidade,
            },
            "a_receber": {
                "total": str(self.a_receber.total),
                "aberto": str(self.a_receber.aberto),
                "liquidado": str(self.a_receber.liquidado),
                "quantidade": self.a_receber.quantidade,
            },
            "saldo_projetado": str(self.saldo_projetado),
        }


def resumo_financeiro(
    db: Session,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    canal: str | None = None,
) -> ResumoFinanceiro:
    """Totais de contas a pagar e a receber, com filtro de período e canal."""
    # A pagar (filtra por vencimento; canal não se aplica).
    pagar = ResumoConta()
    stmt_pagar = select(ContaPagar)
    if data_inicio:
        stmt_pagar = stmt_pagar.where(ContaPagar.vencimento >= data_inicio)
    if data_fim:
        stmt_pagar = stmt_pagar.where(ContaPagar.vencimento <= data_fim)
    for c in db.execute(stmt_pagar).scalars():
        valor = _d(c.valor)
        pagar.total += valor
        pagar.quantidade += 1
        if c.status == CONTA_ABERTA:
            pagar.aberto += valor
        else:
            pagar.liquidado += valor

    # A receber (filtra por competência e canal).
    receber = ResumoConta()
    stmt_receber = select(ContaReceber)
    if data_inicio:
        stmt_receber = stmt_receber.where(ContaReceber.competencia >= data_inicio)
    if data_fim:
        stmt_receber = stmt_receber.where(ContaReceber.competencia <= data_fim)
    if canal:
        stmt_receber = stmt_receber.where(ContaReceber.canal == canal)
    for c in db.execute(stmt_receber).scalars():
        valor = _d(c.valor)
        receber.total += valor
        receber.quantidade += 1
        if c.status == CONTA_ABERTA:
            receber.aberto += valor
        else:
            receber.liquidado += valor

    return ResumoFinanceiro(a_pagar=pagar, a_receber=receber)
