"""Endpoints da DRE mensal (GET /api/dre, despesas e exportação)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dre import DespesaUpsert
from app.services import dre as dre_service
from app.services.export import to_excel, to_pdf

router = APIRouter(prefix="/api/dre", tags=["dre"])

_MESES = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


@router.get("")
def obter_dre(
    ano: int = Query(..., ge=2000, le=2100),
    mes: int = Query(..., ge=1, le=12),
    marketplace: str = Query(dre_service.MARKETPLACE_TODOS),
    db: Session = Depends(get_db),
):
    """DRE completa da competência (receitas, CMV, despesas, lucros, margens)."""
    return dre_service.calcular_dre(db, ano, mes, marketplace)


@router.get("/competencias")
def competencias(db: Session = Depends(get_db)):
    """Competências (ano/mês) que possuem vendas importadas."""
    return dre_service.competencias_disponiveis(db)


@router.get("/despesas")
def listar_despesas(
    ano: int = Query(..., ge=2000, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Despesas editáveis da competência, agrupadas com o template padrão."""
    agrupado = dre_service.listar_despesas(db, ano, mes)
    return {grupo: {cat: str(valor) for cat, valor in itens.items()} for grupo, itens in agrupado.items()}


@router.put("/despesas")
def salvar_despesa(payload: DespesaUpsert, db: Session = Depends(get_db)):
    """Cria/atualiza uma linha de despesa (upsert pela chave da competência)."""
    despesa = dre_service.upsert_despesa(
        db, payload.ano, payload.mes, payload.grupo, payload.categoria, payload.valor
    )
    db.commit()
    return {
        "ano": despesa.ano,
        "mes": despesa.mes,
        "grupo": despesa.grupo,
        "categoria": despesa.categoria,
        "valor": str(despesa.valor),
    }


def _linhas_export(dre: dict) -> list[dict]:
    """Achata a DRE em linhas [{conta, valor}] para Excel/PDF."""
    r = dre["receitas"]
    linhas: list[dict] = [
        {"conta": "RECEITAS", "valor": ""},
        {"conta": "Receita Mercado Livre", "valor": r["mercado_livre"]},
        {"conta": "Receita Shopee", "valor": r["shopee"]},
        {"conta": "Receita Bruta", "valor": r["receita_bruta"]},
    ]
    for cat, val in r["deducoes"]["itens"].items():
        linhas.append({"conta": f"(-) {cat}", "valor": val})
    linhas += [
        {"conta": "Receita Líquida", "valor": r["receita_liquida"]},
        {"conta": "(-) CMV", "valor": dre["cmv"]},
        {"conta": "Lucro Bruto", "valor": dre["lucro_bruto"]},
        {"conta": "DESPESAS OPERACIONAIS", "valor": ""},
    ]
    op = dre["despesas_operacionais"]
    for cat, val in op["mercado_livre"]["itens"].items():
        linhas.append({"conta": f"ML · {cat}", "valor": val})
    for cat, val in op["shopee"]["itens"].items():
        linhas.append({"conta": f"Shopee · {cat}", "valor": val})
    linhas += [
        {"conta": "Total Despesas Operacionais", "valor": op["total"]},
        {"conta": "Lucro Operacional", "valor": dre["lucro_operacional"]},
        {"conta": "DESPESAS GERAIS", "valor": ""},
    ]
    for cat, val in dre["despesas_gerais"]["itens"].items():
        linhas.append({"conta": cat, "valor": val})
    linhas += [
        {"conta": "Total Despesas Gerais", "valor": dre["despesas_gerais"]["total"]},
        {"conta": "Lucro Líquido", "valor": dre["lucro_liquido"]},
        {"conta": "EBITDA", "valor": dre["ebitda"]},
        {"conta": "Margem Bruta (%)", "valor": dre["margens"]["bruta"]},
        {"conta": "Margem Operacional (%)", "valor": dre["margens"]["operacional"]},
        {"conta": "Margem Líquida (%)", "valor": dre["margens"]["liquida"]},
    ]
    return linhas


@router.get("/export")
def exportar_dre(
    ano: int = Query(..., ge=2000, le=2100),
    mes: int = Query(..., ge=1, le=12),
    marketplace: str = Query(dre_service.MARKETPLACE_TODOS),
    formato: str = Query("excel", pattern="^(excel|pdf)$"),
    db: Session = Depends(get_db),
):
    """Exporta a DRE da competência em Excel (.xlsx) ou PDF."""
    dre = dre_service.calcular_dre(db, ano, mes, marketplace)
    titulo = f"DRE {_MESES[mes]} {ano}"
    linhas = _linhas_export(dre)
    colunas = ["conta", "valor"]

    if formato == "excel":
        conteudo = to_excel(titulo, colunas, linhas)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        conteudo = to_pdf(titulo, colunas, linhas)
        media = "application/pdf"
        ext = "pdf"

    return Response(
        content=conteudo,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="dre-{ano}-{mes:02d}.{ext}"'},
    )
