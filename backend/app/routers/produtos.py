"""Endpoints do cadastro de Produtos (GET/POST/PUT /api/produtos)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.anexo import OWNER_PRODUTO
from app.models.fornecedor import Fornecedor
from app.models.produto import Produto
from app.schemas.anexo import AnexoOut
from app.schemas.produto import ProdutoCreate, ProdutoOut, ProdutoUpdate
from app.services.anexos import adicionar_anexo, listar_anexos

router = APIRouter(prefix="/api/produtos", tags=["produtos"])


@router.get("", response_model=list[ProdutoOut])
def listar_produtos(
    q: str | None = Query(None, description="Busca por sku_base ou nome"),
    categoria: str | None = Query(None),
    apenas_pais: bool = Query(False, description="Excluir variantes (produto_pai_id != null)"),
    db: Session = Depends(get_db),
):
    stmt = select(Produto).order_by(Produto.sku_base)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Produto.sku_base.ilike(like)) | (Produto.nome.ilike(like)))
    if categoria:
        stmt = stmt.where(Produto.categoria == categoria)
    if apenas_pais:
        stmt = stmt.where(Produto.produto_pai_id.is_(None))
    return list(db.execute(stmt).scalars())


@router.get("/{produto_id}", response_model=ProdutoOut)
def obter_produto(produto_id: int, db: Session = Depends(get_db)):
    produto = db.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(404, "Produto não encontrado")
    return produto


@router.post("", response_model=ProdutoOut, status_code=201)
def criar_produto(payload: ProdutoCreate, db: Session = Depends(get_db)):
    if db.execute(
        select(Produto).where(Produto.sku_base == payload.sku_base)
    ).scalar_one_or_none():
        raise HTTPException(409, f"Já existe produto com sku_base '{payload.sku_base}'")

    _validar_relacionamentos(db, payload.fornecedor_padrao_id, payload.produto_pai_id)

    produto = Produto(**payload.model_dump())
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return produto


@router.put("/{produto_id}", response_model=ProdutoOut)
def atualizar_produto(
    produto_id: int, payload: ProdutoUpdate, db: Session = Depends(get_db)
):
    produto = db.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(404, "Produto não encontrado")

    dados = payload.model_dump(exclude_unset=True)
    if dados.get("produto_pai_id") == produto_id:
        raise HTTPException(422, "Um produto não pode ser variante de si mesmo")
    _validar_relacionamentos(
        db, dados.get("fornecedor_padrao_id"), dados.get("produto_pai_id")
    )

    for campo, valor in dados.items():
        setattr(produto, campo, valor)
    db.commit()
    db.refresh(produto)
    return produto


@router.get("/{produto_id}/anexos", response_model=list[AnexoOut])
def listar_anexos_produto(produto_id: int, db: Session = Depends(get_db)):
    if db.get(Produto, produto_id) is None:
        raise HTTPException(404, "Produto não encontrado")
    return listar_anexos(db, OWNER_PRODUTO, produto_id)


@router.post("/{produto_id}/anexos", response_model=AnexoOut, status_code=201)
def anexar_produto(
    produto_id: int,
    arquivo: UploadFile = File(...),
    categoria: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if db.get(Produto, produto_id) is None:
        raise HTTPException(404, "Produto não encontrado")
    anexo = adicionar_anexo(
        db,
        owner_tipo=OWNER_PRODUTO,
        owner_id=produto_id,
        nome_arquivo=arquivo.filename or "arquivo",
        conteudo=arquivo.file.read(),
        content_type=arquivo.content_type,
        categoria=categoria,
    )
    db.commit()
    db.refresh(anexo)
    return anexo


def _validar_relacionamentos(
    db: Session, fornecedor_id: int | None, produto_pai_id: int | None
) -> None:
    if fornecedor_id is not None and db.get(Fornecedor, fornecedor_id) is None:
        raise HTTPException(422, f"Fornecedor id={fornecedor_id} não encontrado")
    if produto_pai_id is not None and db.get(Produto, produto_pai_id) is None:
        raise HTTPException(422, f"Produto-pai id={produto_pai_id} não encontrado")
