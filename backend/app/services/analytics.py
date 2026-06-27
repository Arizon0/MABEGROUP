"""Dashboard e Relatórios (Prioridade 5).

Cálculos sobre a tabela ``vendas`` (válidas) com filtro de período e canal,
seguindo as fórmulas obrigatórias do CLAUDE.md. Tudo em ``Decimal``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.estoque import EstoqueSaldo
from app.models.produto import Produto
from app.models.venda import Venda
from app.parsers.common import CANAL_ML, CANAL_SHOPEE, STATUS_VALIDO

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def filtro_vendas(
    stmt: Select,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    canal: str | None = None,
    apenas_validas: bool = True,
) -> Select:
    """Aplica filtros de período (data_venda) e canal a uma query de vendas."""
    if apenas_validas:
        stmt = stmt.where(Venda.status_erp == STATUS_VALIDO)
    if data_inicio:
        stmt = stmt.where(Venda.data_venda >= datetime.combine(data_inicio, time.min))
    if data_fim:
        stmt = stmt.where(Venda.data_venda <= datetime.combine(data_fim, time.max))
    if canal:
        stmt = stmt.where(Venda.canal == canal)
    return stmt


def _mapa_preco_compra(db: Session) -> dict[str, Decimal]:
    return {
        p.sku_base: _d(p.preco_compra)
        for p in db.execute(select(Produto)).scalars()
    }


def _cmv(db: Session, *, data_inicio, data_fim, canal) -> Decimal:
    """Custo das mercadorias vendidas = Σ (unidades × preço de compra)."""
    precos = _mapa_preco_compra(db)
    stmt = filtro_vendas(
        select(Venda.sku_base, func.sum(Venda.qtd)),
        data_inicio=data_inicio, data_fim=data_fim, canal=canal,
    ).where(Venda.sku_base.is_not(None)).group_by(Venda.sku_base)
    total = ZERO
    for sku, unidades in db.execute(stmt).all():
        total += _d(unidades) * precos.get(sku, ZERO)
    return total.quantize(CENT)


def _soma(db: Session, coluna, *, data_inicio, data_fim, canal) -> Decimal:
    stmt = filtro_vendas(
        select(func.coalesce(func.sum(coluna), 0)),
        data_inicio=data_inicio, data_fim=data_fim, canal=canal,
    )
    return _d(db.execute(stmt).scalar_one())


def _soma_money(db: Session, coluna, *, data_inicio, data_fim, canal) -> Decimal:
    """Soma monetária sempre com 2 casas (R$)."""
    return _soma(db, coluna, data_inicio=data_inicio, data_fim=data_fim, canal=canal).quantize(CENT)


# --------------------------------------------------------------------------- #
# Dashboard                                                                     #
# --------------------------------------------------------------------------- #


def dashboard(
    db: Session,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    custos_operacionais: Decimal | None = None,
) -> dict:
    custos_operacionais = _d(custos_operacionais)

    faturamento_bruto = _soma_money(db, Venda.receita_bruta, data_inicio=data_inicio, data_fim=data_fim, canal=None)
    liquido_total = _soma_money(db, Venda.liquido_recebido, data_inicio=data_inicio, data_fim=data_fim, canal=None)
    unidades = _soma(db, Venda.qtd, data_inicio=data_inicio, data_fim=data_fim, canal=None)

    liquido_por_canal = {}
    for canal in (CANAL_ML, CANAL_SHOPEE):
        liquido_por_canal[canal] = str(
            _soma_money(db, Venda.liquido_recebido, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
        )

    cmv = _cmv(db, data_inicio=data_inicio, data_fim=data_fim, canal=None)
    lucro_estimado = (liquido_total - cmv - custos_operacionais).quantize(CENT)

    return {
        "faturamento_bruto": str(faturamento_bruto),
        "liquido_total": str(liquido_total),
        "liquido_por_canal": liquido_por_canal,
        "unidades_vendidas": str(unidades),
        "custo_produtos_vendidos": str(cmv),
        "custos_operacionais": str(custos_operacionais),
        "lucro_estimado": str(lucro_estimado),
        "projecoes": _projecoes(db),
    }


def _projecoes(db: Session, janela_dias: int = 30) -> dict:
    """Projeção de líquido por média móvel das vendas recentes."""
    hoje = date.today()
    corte = datetime.combine(hoje, time.min) - timedelta(days=janela_dias)
    stmt = filtro_vendas(
        select(func.coalesce(func.sum(Venda.liquido_recebido), 0)),
    ).where(Venda.data_venda >= corte)
    liquido_janela = _d(db.execute(stmt).scalar_one())
    media_diaria = (liquido_janela / Decimal(janela_dias)) if janela_dias else ZERO
    return {
        str(h): str((media_diaria * Decimal(h)).quantize(CENT))
        for h in (15, 30, 60, 90)
    }


# --------------------------------------------------------------------------- #
# Relatórios                                                                     #
# --------------------------------------------------------------------------- #


def dre(db: Session, *, data_inicio=None, data_fim=None, canal=None) -> dict:
    """DRE simplificado: receita, tarifas, frete, custo produto, margem."""
    receita = _soma_money(db, Venda.receita_bruta, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
    tarifas = _soma_money(db, Venda.tarifas_plataforma, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
    frete = _soma_money(db, Venda.frete_liquido, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
    descontos = _soma_money(db, Venda.descontos, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
    cancelamentos = _soma_money(db, Venda.cancelamentos, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
    liquido = _soma_money(db, Venda.liquido_recebido, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
    cmv = _cmv(db, data_inicio=data_inicio, data_fim=data_fim, canal=canal)
    margem = (liquido - cmv).quantize(CENT)
    return {
        "receita_bruta": str(receita),
        "tarifas_plataforma": str(tarifas),
        "frete_liquido": str(frete),
        "descontos": str(descontos),
        "cancelamentos": str(cancelamentos),
        "liquido_recebido": str(liquido),
        "custo_produtos_vendidos": str(cmv),
        "margem_bruta": str(margem),
    }


def ranking_receita(db: Session, *, data_inicio=None, data_fim=None, canal=None, limite=20) -> list[dict]:
    """Ranking de SKUs por receita líquida."""
    stmt = filtro_vendas(
        select(
            Venda.sku_base,
            func.sum(Venda.qtd).label("unidades"),
            func.sum(Venda.liquido_recebido).label("liquido"),
        ),
        data_inicio=data_inicio, data_fim=data_fim, canal=canal,
    ).where(Venda.sku_base.is_not(None)).group_by(Venda.sku_base).order_by(
        func.sum(Venda.liquido_recebido).desc()
    ).limit(limite)
    return [
        {"sku_base": r[0], "unidades": str(_d(r[1])), "liquido": str(_d(r[2]).quantize(CENT))}
        for r in db.execute(stmt).all()
    ]


def giro_estoque(db: Session, *, data_inicio=None, data_fim=None) -> list[dict]:
    """Giro por SKU = CMV / estoque médio (usa disponível atual como proxy)."""
    precos = _mapa_preco_compra(db)

    # Unidades vendidas por sku (válidas) no período.
    stmt = filtro_vendas(
        select(Venda.sku_base, func.sum(Venda.qtd)),
        data_inicio=data_inicio, data_fim=data_fim, canal=None,
    ).where(Venda.sku_base.is_not(None)).group_by(Venda.sku_base)
    unidades_por_sku = {r[0]: _d(r[1]) for r in db.execute(stmt).all()}

    # Estoque disponível atual por sku_base.
    disp_por_sku: dict[str, Decimal] = {}
    rows = db.execute(
        select(Produto.sku_base, func.coalesce(func.sum(EstoqueSaldo.qtd_disponivel), 0))
        .join(EstoqueSaldo, EstoqueSaldo.produto_id == Produto.id)
        .group_by(Produto.sku_base)
    ).all()
    for sku, disp in rows:
        disp_por_sku[sku] = _d(disp)

    resultado = []
    for sku, unidades in sorted(unidades_por_sku.items(), key=lambda x: x[1], reverse=True):
        cmv = (unidades * precos.get(sku, ZERO)).quantize(CENT)
        estoque_medio = disp_por_sku.get(sku, ZERO)
        giro = (cmv / estoque_medio).quantize(Decimal("0.001")) if estoque_medio > 0 else None
        resultado.append({
            "sku_base": sku,
            "unidades_vendidas": str(unidades),
            "custo_mercadorias_vendidas": str(cmv),
            "estoque_medio": str(estoque_medio),
            "giro": str(giro) if giro is not None else None,
        })
    return resultado


def fluxo_caixa(db: Session, *, data_inicio=None, data_fim=None, canal=None) -> list[dict]:
    """Fluxo de caixa mensal (líquido recebido agrupado por mês de competência).

    Agrupa em Python para ser independente do dialeto do banco (SQLite/Postgres).
    """
    stmt = filtro_vendas(
        select(Venda.data_venda, Venda.liquido_recebido),
        data_inicio=data_inicio, data_fim=data_fim, canal=canal,
    ).where(Venda.data_venda.is_not(None))

    por_mes: dict[str, Decimal] = {}
    for data_venda, liquido in db.execute(stmt).all():
        mes = data_venda.strftime("%Y-%m")
        por_mes[mes] = por_mes.get(mes, ZERO) + _d(liquido)
    return [
        {"mes": mes, "liquido_recebido": str(por_mes[mes].quantize(CENT))}
        for mes in sorted(por_mes)
    ]
