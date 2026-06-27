"""Serviço de anexos: grava arquivo em disco e registra o ``Anexo`` (máx. 5)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import UPLOAD_DIR
from app.models.anexo import MAX_ANEXOS, Anexo


def contar_anexos(db: Session, owner_tipo: str, owner_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(Anexo)
        .where(Anexo.owner_tipo == owner_tipo, Anexo.owner_id == owner_id)
    ).scalar_one()


def listar_anexos(db: Session, owner_tipo: str, owner_id: int) -> list[Anexo]:
    return list(
        db.execute(
            select(Anexo)
            .where(Anexo.owner_tipo == owner_tipo, Anexo.owner_id == owner_id)
            .order_by(Anexo.criado_em)
        ).scalars()
    )


def adicionar_anexo(
    db: Session,
    *,
    owner_tipo: str,
    owner_id: int,
    nome_arquivo: str,
    conteudo: bytes,
    content_type: str | None = None,
    categoria: str | None = None,
) -> Anexo:
    """Grava o arquivo e cria o registro. Levanta 422 se exceder o limite."""
    if contar_anexos(db, owner_tipo, owner_id) >= MAX_ANEXOS:
        raise HTTPException(
            422, f"Limite de {MAX_ANEXOS} anexos por {owner_tipo} atingido"
        )

    destino_dir = Path(UPLOAD_DIR) / owner_tipo / str(owner_id)
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome_seguro = f"{uuid.uuid4().hex}_{Path(nome_arquivo).name}"
    caminho = destino_dir / nome_seguro
    caminho.write_bytes(conteudo)

    anexo = Anexo(
        owner_tipo=owner_tipo,
        owner_id=owner_id,
        nome_arquivo=nome_arquivo,
        categoria=categoria,
        content_type=content_type,
        caminho=str(caminho),
        tamanho_bytes=len(conteudo),
    )
    db.add(anexo)
    db.flush()
    return anexo
