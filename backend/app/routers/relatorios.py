"""Relatórios (GET /api/relatorios/{tipo}) — JSON, Excel ou PDF.

Tipos: ``dre``, ``ranking``, ``giro``, ``fluxo-caixa``.
Todos aceitam filtro de período (data_inicio, data_fim) e canal (regra 7).
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics
from app.services.export import to_excel, to_pdf

router = APIRouter(prefix="/api/relatorios", tags=["relatorios"])

TITULOS = {
    "dre": "DRE Simplificado",
    "ranking": "Ranking de SKUs por Receita Líquida",
    "giro": "Giro de Estoque por SKU",
    "fluxo-caixa": "Fluxo de Caixa Mensal",
}


def _gerar(
    tipo: str, db: Session, data_inicio: date | None, data_fim: date | None, canal: str | None
):
    """Retorna (payload_json, linhas_para_export, colunas)."""
    if tipo == "dre":
        dados = analytics.dre(db, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
        linhas = [{"conta": k, "valor": v} for k, v in dados.items()]
        return dados, linhas, ["conta", "valor"]
    if tipo == "ranking":
        dados = analytics.ranking_receita(db, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
        return dados, dados, ["sku_base", "unidades", "liquido"]
    if tipo == "giro":
        dados = analytics.giro_estoque(db, data_inicio=data_inicio, data_fim=data_fim)
        return dados, dados, [
            "sku_base", "unidades_vendidas", "custo_mercadorias_vendidas",
            "estoque_medio", "giro",
        ]
    if tipo == "fluxo-caixa":
        dados = analytics.fluxo_caixa(db, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
        return dados, dados, ["mes", "liquido_recebido"]
    raise HTTPException(404, f"Relatório '{tipo}' não existe. Tipos: {list(TITULOS)}")


@router.get("/{tipo}")
def relatorio(
    tipo: str,
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    canal: str | None = Query(None),
    formato: str = Query("json", pattern="^(json|excel|pdf)$"),
    db: Session = Depends(get_db),
):
    payload, linhas, colunas = _gerar(tipo, db, data_inicio, data_fim, canal)
    titulo = TITULOS[tipo]

    if formato == "json":
        return payload

    if formato == "excel":
        conteudo = to_excel(titulo, colunas, linhas)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:  # pdf
        conteudo = to_pdf(titulo, colunas, linhas)
        media = "application/pdf"
        ext = "pdf"

    return Response(
        content=conteudo,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{tipo}.{ext}"'},
    )
