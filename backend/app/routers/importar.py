"""Endpoints de importação de planilhas (POST /api/importar/ml e /shopee)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.parsers.common import CANAL_ML, CANAL_SHOPEE
from app.parsers.mercadolivre import parse_ml
from app.parsers.shopee import parse_shopee
from app.parsers.simples import parse_simples
from app.services.importacao import importar_vendas

router = APIRouter(prefix="/api/importar", tags=["importar"])


def _salvar_temp(arquivo: UploadFile) -> Path:
    sufixo = Path(arquivo.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo)
    tmp.write(arquivo.file.read())
    tmp.close()
    return Path(tmp.name)


@router.post("/ml")
def importar_ml(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa o relatório de vendas do Mercado Livre."""
    caminho = _salvar_temp(arquivo)
    try:
        vendas = parse_ml(caminho)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    finally:
        caminho.unlink(missing_ok=True)

    resultado = importar_vendas(
        db, vendas, CANAL_ML, baixar_estoque=True, gerar_financeiro=True
    )
    db.commit()
    return resultado.as_dict()


@router.post("/shopee")
def importar_shopee(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa o relatório de pedidos da Shopee."""
    caminho = _salvar_temp(arquivo)
    try:
        vendas = parse_shopee(caminho)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    finally:
        caminho.unlink(missing_ok=True)

    resultado = importar_vendas(
        db, vendas, CANAL_SHOPEE, baixar_estoque=True, gerar_financeiro=True
    )
    db.commit()
    return resultado.as_dict()


@router.post("/vendas")
def importar_vendas_simples(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa a planilha simples da DRE (SKU, Preço, Quantidade, Marketplace, Data).

    O SKU já é o ``sku_base`` do cadastro; a receita é ``qtd × preço`` e o CMV é
    congelado a partir do custo do produto. SKUs não cadastrados vêm em
    ``skus_nao_cadastrados`` para cadastro prévio antes de consolidar a DRE.
    Cada marketplace da planilha é persistido no seu próprio canal.
    """
    caminho = _salvar_temp(arquivo)
    try:
        vendas = parse_simples(caminho)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    finally:
        caminho.unlink(missing_ok=True)

    # Persiste por canal para respeitar a detecção de duplicados por canal.
    canais = sorted({v.canal for v in vendas})
    agregado: dict | None = None
    for canal in canais:
        parte = [v for v in vendas if v.canal == canal]
        resultado = importar_vendas(
            db, parte, canal, baixar_estoque=True, resolver_direto=True
        )
        agregado = _merge_resultado(agregado, resultado.as_dict())
    db.commit()
    return agregado or {"linhas_arquivo": 0, "vendas_inseridas": 0, "skus_nao_cadastrados": []}


def _merge_resultado(acc: dict | None, novo: dict) -> dict:
    if acc is None:
        return novo
    somar = (
        "linhas_arquivo", "vendas_inseridas", "pedidos_duplicados",
        "skus_resolvidos", "baixas_estoque",
    )
    for chave in somar:
        acc[chave] = acc.get(chave, 0) + novo.get(chave, 0)
    faltantes = set(acc.get("skus_nao_cadastrados", [])) | set(novo.get("skus_nao_cadastrados", []))
    acc["skus_nao_cadastrados"] = sorted(faltantes)
    acc["canal"] = "Vários"
    return acc
