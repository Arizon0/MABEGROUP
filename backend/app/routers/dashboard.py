"""Endpoint do Dashboard principal (GET /api/dashboard)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    custos_operacionais: Decimal | None = Query(None),
    db: Session = Depends(get_db),
):
    """Faturamento, líquido por canal, lucro estimado e projeções."""
    return analytics.dashboard(
        db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        custos_operacionais=custos_operacionais,
    )
