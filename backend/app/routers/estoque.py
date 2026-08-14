"""Endpoints de Estoque Multi-local (GET /api/estoque e movimentações)."""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estoque import EstoqueSaldo, Local
from app.models.produto import Produto
from app.parsers.common import ler_linhas_csv, ler_linhas_xlsx
from app.schemas.estoque import (
    AlertaOut,
    LocalOut,
    MovimentoIn,
    RankingItemOut,
    RelatorioEstoqueOut,
    SaldoOut,
    SaldoSimplesOut,
)
from app.services import estoque as svc
from app.services.compras_import import importar_compras, parse_compras
from app.services.estoque_import import importar_estoque, parse_estoque

router = APIRouter(prefix="/api/estoque", tags=["estoque"])


@router.get("", response_model=list[SaldoOut])
def listar_saldos(
    produto_id: int | None = Query(None),
    local_id: int | None = Query(None),
    q: str | None = Query(None, description="Busca por sku_base ou nome"),
    db: Session = Depends(get_db),
):
    """Saldo por SKU × local (com valor total = disponível × custo médio)."""
    stmt = (
        select(EstoqueSaldo, Produto, Local)
        .join(Produto, EstoqueSaldo.produto_id == Produto.id)
        .join(Local, EstoqueSaldo.local_id == Local.id)
        .order_by(Produto.sku_base, Local.nome)
    )
    if produto_id:
        stmt = stmt.where(EstoqueSaldo.produto_id == produto_id)
    if local_id:
        stmt = stmt.where(EstoqueSaldo.local_id == local_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Produto.sku_base.ilike(like)) | (Produto.nome.ilike(like)))

    from decimal import Decimal

    resultado = []
    for saldo, produto, local in db.execute(stmt).all():
        disp = svc._d(saldo.qtd_disponivel)
        custo = svc._d(saldo.custo_medio)
        resultado.append(
            SaldoOut(
                produto_id=produto.id,
                sku_base=produto.sku_base,
                nome_produto=produto.nome,
                local_id=local.id,
                local_nome=local.nome,
                qtd_disponivel=disp,
                qtd_reservada=svc._d(saldo.qtd_reservada),
                custo_medio=custo,
                valor_total=(disp * custo).quantize(Decimal("0.01")),
            )
        )
    return resultado


@router.get("/locais", response_model=list[LocalOut])
def listar_locais(db: Session = Depends(get_db)):
    return list(db.execute(select(Local).order_by(Local.nome)).scalars())


@router.get("/alertas", response_model=list[AlertaOut])
def listar_alertas(db: Session = Depends(get_db)):
    """Produtos com disponível total <= estoque mínimo."""
    return [AlertaOut(**a.__dict__) for a in svc.alertas_estoque(db)]


@router.get("/relatorio", response_model=RelatorioEstoqueOut)
def relatorio(
    limite_ranking: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)
):
    """Valor total do estoque + alertas + ranking de SKUs mais vendidos."""
    alertas = svc.alertas_estoque(db)
    ranking = svc.ranking_skus_vendidos(db, limite=limite_ranking)
    return RelatorioEstoqueOut(
        valor_total_estoque=svc.valor_total_estoque(db),
        total_alertas=len(alertas),
        alertas=[AlertaOut(**a.__dict__) for a in alertas],
        ranking_skus=[RankingItemOut(**r.__dict__) for r in ranking],
    )


@router.post("/importar")
def importar_estoque_planilha(
    arquivo: UploadFile = File(...),
    local_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Importa o estoque atual via planilha (.xlsx/.csv).

    Colunas aceitas: SKU (ou Código/Referência/Nome) e Quantidade (ou Estoque),
    com Custo opcional. Ajusta o saldo disponível de cada SKU no local informado
    (default: galpão) e valoriza o estoque para entrar nos cálculos.
    """
    conteudo = arquivo.file.read()
    nome = (arquivo.filename or "").lower()
    try:
        if nome.endswith(".csv"):
            registros = ler_linhas_csv(conteudo)
        else:
            registros = ler_linhas_xlsx(io.BytesIO(conteudo))
    except Exception as exc:  # noqa: BLE001 — erro de leitura vira 422 legível
        raise HTTPException(422, f"Não foi possível ler a planilha: {exc}")

    try:
        linhas = parse_estoque(registros)
        resultado = importar_estoque(db, linhas, local_id=local_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    db.commit()
    return resultado.as_dict()


@router.delete("/saldos/{produto_id}/{local_id}", status_code=200)
def excluir_saldo(produto_id: int, local_id: int, db: Session = Depends(get_db)):
    """Apaga o saldo de um produto em um local (remove item do estoque)."""
    svc.excluir_saldo(db, produto_id, local_id)
    db.commit()
    return {"removido": True, "produto_id": produto_id, "local_id": local_id}


@router.post("/importar-compras")
def importar_compras_planilha(
    arquivo: UploadFile = File(...),
    local_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Importa uma planilha de compras (entrada de estoque).

    Colunas: SKU (ou Nome), Quantidade, Valor pago (custo unitário) e Frete
    (opcional, rateado por unidade). Cada linha dá entrada no estoque com o
    custo médio ponderado e atualiza o preço de compra do produto.
    """
    conteudo = arquivo.file.read()
    nome = (arquivo.filename or "").lower()
    try:
        if nome.endswith(".csv"):
            registros = ler_linhas_csv(conteudo)
        else:
            registros = ler_linhas_xlsx(io.BytesIO(conteudo))
    except Exception as exc:  # noqa: BLE001 — erro de leitura vira 422 legível
        raise HTTPException(422, f"Não foi possível ler a planilha: {exc}")

    try:
        linhas = parse_compras(registros)
        resultado = importar_compras(db, linhas, local_id=local_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    db.commit()
    return resultado.as_dict()


@router.post("/movimentos", response_model=SaldoSimplesOut, status_code=201)
def registrar_movimento(payload: MovimentoIn, db: Session = Depends(get_db)):
    """Registra entrada, saída, reserva ou liberação de reserva."""
    if db.get(Produto, payload.produto_id) is None:
        raise HTTPException(422, f"Produto id={payload.produto_id} não encontrado")
    if db.get(Local, payload.local_id) is None:
        raise HTTPException(422, f"Local id={payload.local_id} não encontrado")

    comum = dict(
        produto_id=payload.produto_id, local_id=payload.local_id,
        qtd=payload.qtd, referencia=payload.referencia,
    )
    if payload.tipo == "entrada":
        saldo = svc.registrar_entrada(db, custo_unitario=payload.custo_unitario, **comum)
    elif payload.tipo == "saida":
        saldo = svc.registrar_saida(db, **comum)
    elif payload.tipo == "reserva":
        saldo = svc.reservar(db, **comum)
    else:  # liberacao
        saldo = svc.liberar_reserva(db, **comum)

    db.commit()
    db.refresh(saldo)
    return saldo
