"""Endpoints de Pedidos de Compra (GET/POST /api/compras + ações de fluxo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.anexo import OWNER_PEDIDO_COMPRA
from app.models.compra import PedidoCompra
from app.schemas.anexo import AnexoOut
from app.schemas.compra import (
    PedidoCompraCreate,
    PedidoCompraOut,
    ReceberIn,
    SugestaoCompraOut,
)
from app.services import compras as svc
from app.services.anexos import adicionar_anexo, listar_anexos

router = APIRouter(prefix="/api/compras", tags=["compras"])


@router.get("", response_model=list[PedidoCompraOut])
def listar_pedidos(
    status: str | None = Query(None),
    fornecedor_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(PedidoCompra).order_by(PedidoCompra.criado_em.desc())
    if status:
        stmt = stmt.where(PedidoCompra.status == status)
    if fornecedor_id:
        stmt = stmt.where(PedidoCompra.fornecedor_id == fornecedor_id)
    return list(db.execute(stmt).scalars())


@router.get("/sugestao", response_model=list[SugestaoCompraOut])
def sugestao(db: Session = Depends(get_db)):
    """Sugestão automática de quantidade a repor por SKU."""
    return [SugestaoCompraOut(**s.__dict__) for s in svc.sugestao_compra(db)]


@router.get("/{pedido_id}", response_model=PedidoCompraOut)
def obter_pedido(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.get(PedidoCompra, pedido_id)
    if pedido is None:
        raise HTTPException(404, "Pedido de compra não encontrado")
    return pedido


@router.post("", response_model=PedidoCompraOut, status_code=201)
def criar_pedido(payload: PedidoCompraCreate, db: Session = Depends(get_db)):
    pedido = svc.criar_pedido(
        db,
        fornecedor_id=payload.fornecedor_id,
        itens=[i.model_dump() for i in payload.itens],
        observacao=payload.observacao,
        local_id=payload.local_id,
    )
    db.commit()
    db.refresh(pedido)
    return pedido


@router.post("/{pedido_id}/aprovar", response_model=PedidoCompraOut)
def aprovar(pedido_id: int, db: Session = Depends(get_db)):
    pedido = svc.aprovar_pedido(db, pedido_id)
    db.commit()
    db.refresh(pedido)
    return pedido


@router.post("/{pedido_id}/receber", response_model=PedidoCompraOut)
def receber(pedido_id: int, payload: ReceberIn | None = None, db: Session = Depends(get_db)):
    pedido = svc.receber_pedido(
        db, pedido_id, local_id=payload.local_id if payload else None
    )
    db.commit()
    db.refresh(pedido)
    return pedido


@router.get("/{pedido_id}/anexos", response_model=list[AnexoOut])
def listar_anexos_pedido(pedido_id: int, db: Session = Depends(get_db)):
    if db.get(PedidoCompra, pedido_id) is None:
        raise HTTPException(404, "Pedido de compra não encontrado")
    return listar_anexos(db, OWNER_PEDIDO_COMPRA, pedido_id)


@router.post("/{pedido_id}/anexos", response_model=AnexoOut, status_code=201)
def anexar_nf(
    pedido_id: int,
    arquivo: UploadFile = File(...),
    categoria: str | None = Form("nota_fiscal"),
    db: Session = Depends(get_db),
):
    """Anexa a NF de entrada digitalizada ao pedido."""
    if db.get(PedidoCompra, pedido_id) is None:
        raise HTTPException(404, "Pedido de compra não encontrado")
    anexo = adicionar_anexo(
        db,
        owner_tipo=OWNER_PEDIDO_COMPRA,
        owner_id=pedido_id,
        nome_arquivo=arquivo.filename or "nf",
        conteudo=arquivo.file.read(),
        content_type=arquivo.content_type,
        categoria=categoria,
    )
    db.commit()
    db.refresh(anexo)
    return anexo
