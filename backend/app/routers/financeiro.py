"""Endpoints do Financeiro (GET /api/financeiro + listagens de contas)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.financeiro import ContaPagar, ContaReceber
from app.services import financeiro as svc

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("")
def resumo(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    canal: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Resumo de contas a pagar e a receber (filtro por período e canal)."""
    return svc.resumo_financeiro(
        db, data_inicio=data_inicio, data_fim=data_fim, canal=canal
    ).as_dict()


@router.get("/contas-pagar")
def contas_pagar(status: str | None = Query(None), db: Session = Depends(get_db)):
    stmt = select(ContaPagar).order_by(ContaPagar.vencimento)
    if status:
        stmt = stmt.where(ContaPagar.status == status)
    return [
        {
            "id": c.id,
            "fornecedor_id": c.fornecedor_id,
            "pedido_compra_id": c.pedido_compra_id,
            "descricao": c.descricao,
            "valor": str(c.valor),
            "vencimento": c.vencimento.isoformat() if c.vencimento else None,
            "status": c.status,
        }
        for c in db.execute(stmt).scalars()
    ]


@router.get("/contas-receber")
def contas_receber(
    canal: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(ContaReceber).order_by(ContaReceber.competencia)
    if canal:
        stmt = stmt.where(ContaReceber.canal == canal)
    if status:
        stmt = stmt.where(ContaReceber.status == status)
    return [
        {
            "id": c.id,
            "canal": c.canal,
            "id_pedido_canal": c.id_pedido_canal,
            "descricao": c.descricao,
            "valor": str(c.valor),
            "competencia": c.competencia.isoformat() if c.competencia else None,
            "status": c.status,
        }
        for c in db.execute(stmt).scalars()
    ]
