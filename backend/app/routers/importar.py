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
