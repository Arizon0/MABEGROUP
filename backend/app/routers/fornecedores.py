"""Endpoints do cadastro de Fornecedores (GET/POST/PUT /api/fornecedores)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.anexo import OWNER_FORNECEDOR
from app.models.fornecedor import ContatoFornecedor, Fornecedor
from app.schemas.anexo import AnexoOut
from app.schemas.fornecedor import (
    FornecedorCreate,
    FornecedorOut,
    FornecedorUpdate,
)
from app.services.anexos import adicionar_anexo, listar_anexos

router = APIRouter(prefix="/api/fornecedores", tags=["fornecedores"])


@router.get("", response_model=list[FornecedorOut])
def listar_fornecedores(
    q: str | None = Query(None, description="Busca por razão social, fantasia ou CNPJ"),
    db: Session = Depends(get_db),
):
    stmt = select(Fornecedor).order_by(Fornecedor.razao_social)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Fornecedor.razao_social.ilike(like)
            | Fornecedor.nome_fantasia.ilike(like)
            | Fornecedor.cnpj.ilike(like)
        )
    return list(db.execute(stmt).scalars())


@router.get("/{fornecedor_id}", response_model=FornecedorOut)
def obter_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if fornecedor is None:
        raise HTTPException(404, "Fornecedor não encontrado")
    return fornecedor


@router.post("", response_model=FornecedorOut, status_code=201)
def criar_fornecedor(payload: FornecedorCreate, db: Session = Depends(get_db)):
    # CNPJ já validado/normalizado pelo schema.
    if db.execute(
        select(Fornecedor).where(Fornecedor.cnpj == payload.cnpj)
    ).scalar_one_or_none():
        raise HTTPException(409, f"Já existe fornecedor com CNPJ {payload.cnpj}")

    dados = payload.model_dump(exclude={"contatos"})
    fornecedor = Fornecedor(**dados)
    fornecedor.contatos = [
        ContatoFornecedor(**c.model_dump()) for c in payload.contatos
    ]
    db.add(fornecedor)
    db.commit()
    db.refresh(fornecedor)
    return fornecedor


@router.put("/{fornecedor_id}", response_model=FornecedorOut)
def atualizar_fornecedor(
    fornecedor_id: int, payload: FornecedorUpdate, db: Session = Depends(get_db)
):
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if fornecedor is None:
        raise HTTPException(404, "Fornecedor não encontrado")

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(fornecedor, campo, valor)
    db.commit()
    db.refresh(fornecedor)
    return fornecedor


@router.get("/{fornecedor_id}/anexos", response_model=list[AnexoOut])
def listar_anexos_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    if db.get(Fornecedor, fornecedor_id) is None:
        raise HTTPException(404, "Fornecedor não encontrado")
    return listar_anexos(db, OWNER_FORNECEDOR, fornecedor_id)


@router.post("/{fornecedor_id}/anexos", response_model=AnexoOut, status_code=201)
def anexar_fornecedor(
    fornecedor_id: int,
    arquivo: UploadFile = File(...),
    categoria: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if db.get(Fornecedor, fornecedor_id) is None:
        raise HTTPException(404, "Fornecedor não encontrado")
    anexo = adicionar_anexo(
        db,
        owner_tipo=OWNER_FORNECEDOR,
        owner_id=fornecedor_id,
        nome_arquivo=arquivo.filename or "arquivo",
        conteudo=arquivo.file.read(),
        content_type=arquivo.content_type,
        categoria=categoria,
    )
    db.commit()
    db.refresh(anexo)
    return anexo
