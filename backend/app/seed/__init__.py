"""Rotinas de seed (carga inicial de dados)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.sku_map import SkuMap

from .sku_map_seed import DE_PARA, iter_mapeamentos, nome_para


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
