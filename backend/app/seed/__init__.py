"""Rotinas de seed (carga inicial de dados)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ADMIN_EMAIL, ADMIN_NOME, ADMIN_SENHA
from app.models.estoque import (
    LOCAL_ESCRITORIO,
    LOCAL_FULFILLMENT,
    LOCAL_GALPAO,
    Local,
)
from app.models.produto import Produto
from app.models.sku_map import SkuMap
from app.models.usuario import Usuario
from app.services.auth import hash_senha

from .sku_map_seed import DE_PARA, iter_mapeamentos, nome_para

LOCAIS_PADRAO = [
    ("Galpão Central", LOCAL_GALPAO),
    ("ML Fulfillment", LOCAL_FULFILLMENT),
    ("Escritório", LOCAL_ESCRITORIO),
]


def seed_admin(db: Session) -> dict[str, int]:
    """Cria o usuário administrador inicial (idempotente).

    Credenciais vêm de ADMIN_EMAIL/ADMIN_SENHA (variáveis de ambiente).
    """
    email = ADMIN_EMAIL.strip().lower()
    existe = db.execute(
        select(Usuario).where(Usuario.email == email)
    ).scalar_one_or_none()
    if existe is not None:
        return {"usuarios_criados": 0}
    db.add(
        Usuario(
            email=email,
            nome=ADMIN_NOME,
            senha_hash=hash_senha(ADMIN_SENHA),
            perfil="admin",
            ativo=True,
        )
    )
    db.commit()
    return {"usuarios_criados": 1}


def seed_locais(db: Session) -> dict[str, int]:
    """Cria os locais de estoque padrão (idempotente)."""
    existentes = {l.nome for l in db.execute(select(Local)).scalars()}
    criados = 0
    for nome, tipo in LOCAIS_PADRAO:
        if nome not in existentes:
            db.add(Local(nome=nome, tipo=tipo))
            criados += 1
    db.commit()
    return {"locais_criados": criados}


def seed_sku_map(db: Session) -> dict[str, int]:
    """Cria produtos e o de-para de SKUs (idempotente)."""
    produtos_criados = 0
    maps_criados = 0

    # 1) Garantir um produto por sku_base.
    produtos: dict[str, Produto] = {
        p.sku_base: p for p in db.execute(select(Produto)).scalars()
    }
    for sku_base in DE_PARA:
        if sku_base not in produtos:
            p = Produto(sku_base=sku_base, nome=nome_para(sku_base), categoria="Autopeças")
            db.add(p)
            produtos[sku_base] = p
            produtos_criados += 1
    db.flush()

    # 2) Criar os mapeamentos (sku_canal, canal) -> produto.
    existentes = {
        (sm.sku_canal, sm.canal) for sm in db.execute(select(SkuMap)).scalars()
    }
    for sku_canal, canal, id_anuncio, sku_base in iter_mapeamentos():
        if (sku_canal, canal) in existentes:
            continue
        db.add(
            SkuMap(
                sku_canal=sku_canal,
                canal=canal,
                id_anuncio=id_anuncio,
                produto_id=produtos[sku_base].id,
                sku_base=sku_base,
            )
        )
        existentes.add((sku_canal, canal))
        maps_criados += 1

    db.commit()
    return {"produtos_criados": produtos_criados, "mapeamentos_criados": maps_criados}
