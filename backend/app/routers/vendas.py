"""Análise venda-a-venda e os custos que ela precisa (imposto e publicidade).

- ``GET /api/vendas/analise``      — a tabela pedido a pedido, com recorte,
  ordenação, busca e paginação.
- ``GET /api/vendas/analise/export`` — a mesma consulta em Excel ou PDF.
- ``/api/vendas/aliquotas``        — alíquota efetiva por competência.
- ``/api/vendas/ads``              — investimento em publicidade por escopo.
- ``PUT /api/vendas/nf``           — número da NF quando o canal não o exporta.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.custos_venda import AdsInvestimento, AliquotaImposto
from app.models.venda import Venda
from app.schemas.venda_analise import (
    AdsOut,
    AdsUpsert,
    AliquotaOut,
    AliquotaUpsert,
    NotaFiscalUpsert,
)
from app.services import vendas_analise
from app.services.export import to_excel, to_pdf

router = APIRouter(prefix="/api/vendas", tags=["vendas"])

# Colunas da exportação, na mesma ordem da tela.
COLUNAS_EXPORT = [
    "numero_nf", "id_pedido_canal", "data_venda", "canal", "titulo", "skus",
    "qtd", "margem_pct", "margem_valor", "total", "custo", "frete", "comissao",
    "ads", "acos_pct", "tacos_pct", "imposto", "liquido_recebido", "alertas",
]


@router.get("/analise")
def analise(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    canal: str | None = Query(None),
    recorte: str = Query(vendas_analise.RECORTE_TODOS),
    ordem: str = Query(vendas_analise.ORDEM_DATA),
    busca: str | None = Query(None, max_length=120),
    pagina: int = Query(1, ge=1),
    tamanho: int = Query(vendas_analise.TAMANHO_PAGINA_PADRAO, ge=1, le=vendas_analise.TAMANHO_PAGINA_MAX),
    incluir_canceladas: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Margem real de cada pedido: líquido − CMV − Ads − Imposto."""
    return vendas_analise.analisar(
        db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        canal=canal,
        recorte=recorte,
        ordem=ordem,
        busca=busca,
        pagina=pagina,
        tamanho=tamanho,
        apenas_validas=not incluir_canceladas,
    )


@router.get("/analise/opcoes")
def opcoes():
    """Recortes e ordenações aceitos — a tela monta os chips a partir daqui."""
    return {
        "recortes": list(vendas_analise.RECORTES),
        "ordenacoes": list(vendas_analise.ORDENACOES),
        "alertas": [
            vendas_analise.ALERTA_SEM_SKU,
            vendas_analise.ALERTA_SEM_CUSTO,
            vendas_analise.ALERTA_SEM_COMISSAO,
            vendas_analise.ALERTA_RECEBER_NAO_BATE,
        ],
    }


@router.get("/analise/export")
def exportar_analise(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    canal: str | None = Query(None),
    recorte: str = Query(vendas_analise.RECORTE_TODOS),
    ordem: str = Query(vendas_analise.ORDEM_DATA),
    busca: str | None = Query(None, max_length=120),
    formato: str = Query("excel", pattern="^(excel|pdf)$"),
    incluir_canceladas: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Exporta a análise inteira (não só a página aberta) em Excel ou PDF."""
    dados = vendas_analise.analisar(
        db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        canal=canal,
        recorte=recorte,
        ordem=ordem,
        busca=busca,
        pagina=1,
        tamanho=vendas_analise.TAMANHO_PAGINA_MAX,
        apenas_validas=not incluir_canceladas,
    )
    linhas = [
        {
            **{c: p.get(c) for c in COLUNAS_EXPORT},
            "skus": ", ".join(p["skus"]),
            "alertas": ", ".join(p["alertas"]),
        }
        for p in dados["pedidos"]
    ]
    titulo = "Análise de Vendas — margem por pedido"

    if formato == "excel":
        conteudo = to_excel(titulo, COLUNAS_EXPORT, linhas)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        conteudo = to_pdf(titulo, COLUNAS_EXPORT, linhas)
        media = "application/pdf"
        ext = "pdf"

    return Response(
        content=conteudo,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="analise-vendas.{ext}"'},
    )


# --------------------------------------------------------------------------- #
# Alíquota de imposto                                                           #
# --------------------------------------------------------------------------- #


@router.get("/aliquotas", response_model=list[AliquotaOut])
def listar_aliquotas(db: Session = Depends(get_db)):
    """Alíquotas cadastradas, da competência mais recente para a mais antiga."""
    linhas = db.execute(select(AliquotaImposto)).scalars().all()
    return sorted(linhas, key=lambda a: (a.ano, a.mes), reverse=True)


@router.put("/aliquotas", response_model=AliquotaOut)
def salvar_aliquota(payload: AliquotaUpsert, db: Session = Depends(get_db)):
    """Cria ou atualiza a alíquota de uma competência (idempotente pela chave)."""
    existente = db.execute(
        select(AliquotaImposto).where(
            AliquotaImposto.ano == payload.ano, AliquotaImposto.mes == payload.mes
        )
    ).scalar_one_or_none()
    if existente is None:
        existente = AliquotaImposto(ano=payload.ano, mes=payload.mes)
        db.add(existente)
    existente.aliquota_pct = payload.aliquota_pct
    existente.observacao = payload.observacao
    db.commit()
    db.refresh(existente)
    return existente


@router.delete("/aliquotas/{aliquota_id}", status_code=204)
def excluir_aliquota(aliquota_id: int, db: Session = Depends(get_db)):
    """Remove a alíquota. As vendas da competência voltam a ficar sem imposto."""
    alvo = db.get(AliquotaImposto, aliquota_id)
    if alvo is None:
        raise HTTPException(404, "Alíquota não encontrada.")
    db.delete(alvo)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Investimento em publicidade                                                   #
# --------------------------------------------------------------------------- #


@router.get("/ads", response_model=list[AdsOut])
def listar_ads(
    ano: int | None = Query(None, ge=2000, le=2100),
    mes: int | None = Query(None, ge=1, le=12),
    canal: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Lançamentos de publicidade, opcionalmente filtrados por competência."""
    stmt = select(AdsInvestimento)
    if ano is not None:
        stmt = stmt.where(AdsInvestimento.ano == ano)
    if mes is not None:
        stmt = stmt.where(AdsInvestimento.mes == mes)
    if canal:
        stmt = stmt.where(AdsInvestimento.canal == canal)
    linhas = db.execute(stmt).scalars().all()
    return sorted(
        linhas, key=lambda a: (a.ano, a.mes, a.canal, a.escopo, a.referencia), reverse=True
    )


@router.put("/ads", response_model=AdsOut)
def salvar_ads(payload: AdsUpsert, db: Session = Depends(get_db)):
    """Cria ou atualiza um lançamento de publicidade (idempotente pela chave)."""
    existente = db.execute(
        select(AdsInvestimento).where(
            AdsInvestimento.canal == payload.canal,
            AdsInvestimento.ano == payload.ano,
            AdsInvestimento.mes == payload.mes,
            AdsInvestimento.escopo == payload.escopo,
            AdsInvestimento.referencia == payload.referencia,
        )
    ).scalar_one_or_none()
    if existente is None:
        existente = AdsInvestimento(
            canal=payload.canal,
            ano=payload.ano,
            mes=payload.mes,
            escopo=payload.escopo,
            referencia=payload.referencia,
        )
        db.add(existente)
    existente.valor = payload.valor
    existente.receita_ads = payload.receita_ads
    db.commit()
    db.refresh(existente)
    return existente


@router.delete("/ads/{ads_id}", status_code=204)
def excluir_ads(ads_id: int, db: Session = Depends(get_db)):
    """Remove o lançamento. Os pedidos que ele cobria deixam de ter Ads."""
    alvo = db.get(AdsInvestimento, ads_id)
    if alvo is None:
        raise HTTPException(404, "Lançamento de Ads não encontrado.")
    db.delete(alvo)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Nota fiscal                                                                   #
# --------------------------------------------------------------------------- #


@router.put("/nf")
def salvar_nf(payload: NotaFiscalUpsert, db: Session = Depends(get_db)):
    """Grava a NF em todas as linhas do pedido (o pacote é uma NF só)."""
    resultado = db.execute(
        update(Venda)
        .where(
            Venda.canal == payload.canal,
            Venda.id_pedido_canal == payload.id_pedido_canal,
        )
        .values(numero_nf=payload.numero_nf)
    )
    if resultado.rowcount == 0:
        raise HTTPException(404, "Pedido não encontrado.")
    db.commit()
    return {
        "canal": payload.canal,
        "id_pedido_canal": payload.id_pedido_canal,
        "numero_nf": payload.numero_nf,
        "linhas_atualizadas": resultado.rowcount,
    }
