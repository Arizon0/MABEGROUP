"""Endpoints do Mapa de SKUs (GET/POST /api/sku-map) e pendências."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.produto import Produto
from app.models.sku_map import SkuMap, SkuPendencia
from app.schemas.sku_map import (
    ProdutoOut,
    SkuMapCreate,
    SkuMapOut,
    SkuPendenciaOut,
)

router = APIRouter(prefix="/api/sku-map", tags=["sku-map"])


@router.get("", response_model=list[SkuMapOut])
def listar_sku_map(
    canal: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Lista os de-para configurados (opcionalmente filtrando por canal)."""
    stmt = select(SkuMap).order_by(SkuMap.sku_base, SkuMap.canal, SkuMap.sku_canal)
    if canal:
        stmt = stmt.where(SkuMap.canal == canal)
    return list(db.execute(stmt).scalars())


@router.get("/pendencias", response_model=list[SkuPendenciaOut])
def listar_pendencias(
    canal: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Lista os sku_canal sem mapeamento (pendências de importação)."""
    stmt = select(SkuPendencia).order_by(SkuPendencia.ocorrencias.desc())
    if canal:
        stmt = stmt.where(SkuPendencia.canal == canal)
    return list(db.execute(stmt).scalars())


@router.get("/produtos", response_model=list[ProdutoOut])
def buscar_produtos(
    q: str | None = Query(None, description="Busca por sku_base ou nome"),
    db: Session = Depends(get_db),
):
    """Busca produtos para preencher o de-para (campo de busca da tela)."""
    stmt = select(Produto).order_by(Produto.sku_base).limit(50)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Produto.sku_base.ilike(like)) | (Produto.nome.ilike(like)))
    return list(db.execute(stmt).scalars())


@router.post("", response_model=SkuMapOut)
def salvar_sku_map(payload: SkuMapCreate, db: Session = Depends(get_db)):
    """Cria ou atualiza um de-para e remove a pendência correspondente."""
    produto = _resolver_produto(db, payload)

    existente = db.execute(
        select(SkuMap).where(
            SkuMap.sku_canal == payload.sku_canal,
            SkuMap.canal == payload.canal,
        )
    ).scalar_one_or_none()

    if existente is not None:
        existente.produto_id = produto.id
        existente.sku_base = produto.sku_base
        existente.id_anuncio = payload.id_anuncio
        sku_map = existente
    else:
        sku_map = SkuMap(
            sku_canal=payload.sku_canal,
            canal=payload.canal,
            id_anuncio=payload.id_anuncio,
            produto_id=produto.id,
            sku_base=produto.sku_base,
        )
        db.add(sku_map)

    # Resolver a pendência, se existir.
    pendencia = db.execute(
        select(SkuPendencia).where(
            SkuPendencia.sku_canal == payload.sku_canal,
            SkuPendencia.canal == payload.canal,
        )
    ).scalar_one_or_none()
    if pendencia is not None:
        db.delete(pendencia)

    db.commit()
    db.refresh(sku_map)
    return sku_map


def _resolver_produto(db: Session, payload: SkuMapCreate) -> Produto:
    if payload.produto_id is not None:
        produto = db.get(Produto, payload.produto_id)
        if produto is None:
            raise HTTPException(404, f"Produto id={payload.produto_id} não encontrado")
        return produto

    if payload.sku_base:
        produto = db.execute(
            select(Produto).where(Produto.sku_base == payload.sku_base)
        ).scalar_one_or_none()
        if produto is None:
            # Cria o produto-base on-the-fly se ainda não existir.
            produto = Produto(sku_base=payload.sku_base, nome=f"Produto {payload.sku_base}")
            db.add(produto)
            db.flush()
        return produto

    raise HTTPException(422, "Informe produto_id ou sku_base")
