"""Serviço da DRE mensal (Demonstração do Resultado do Exercício).

Consolida, por competência (ano/mês) e marketplace, as vendas importadas
(receita bruta e CMV congelado) com as despesas editáveis lançadas pelo
usuário, produzindo a estrutura clássica da DRE e as margens.

Regras (do prompt):
- Receita Bruta = Σ vendas importadas (válidas).
- Receita Líquida = Receita Bruta − Cancelamentos − Devoluções − Reembolsos.
- CMV = Σ (quantidade × custo congelado). **Nunca editável.**
- Lucro Bruto = Receita Líquida − CMV.
- Lucro Operacional = Lucro Bruto − Despesas Operacionais.
- Lucro Líquido = Lucro Operacional − Despesas Gerais.
- Margens sempre sobre a Receita Líquida.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models.dre import (
    GRUPO_DEDUCOES,
    GRUPO_GERAL,
    GRUPO_OPERACIONAL_ML,
    GRUPO_OPERACIONAL_SHOPEE,
    DespesaDRE,
)
from app.models.venda import Venda
from app.parsers.common import CANAL_ML, CANAL_SHOPEE, STATUS_VALIDO

ZERO = Decimal("0")
MARKETPLACE_TODOS = "todos"

# Categorias padrão de cada grupo (renderizadas mesmo sem valor lançado).
TEMPLATE: dict[str, list[str]] = {
    GRUPO_DEDUCOES: ["Cancelamentos", "Devoluções", "Reembolsos"],
    GRUPO_OPERACIONAL_ML: [
        "Comissão", "Frete Full", "Frete Flex", "ADS Mercado Livre",
        "Tarifas", "Outras despesas",
    ],
    GRUPO_OPERACIONAL_SHOPEE: [
        "Comissão", "Frete", "ADS Shopee", "Tarifas", "Outras despesas",
    ],
    GRUPO_GERAL: [
        "Salários", "Pró-labore", "Contador", "Internet", "Energia",
        "Embalagens", "Etiquetas", "Software", "Aluguel", "Marketing",
        "Impostos", "Outras despesas",
    ],
}


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def _margem(numerador: Decimal, base: Decimal) -> Decimal:
    if base == ZERO:
        return ZERO
    return (numerador / base * Decimal("100")).quantize(Decimal("0.01"))


def _competencia_intervalo(ano: int, mes: int) -> tuple[datetime, datetime]:
    ultimo = monthrange(ano, mes)[1]
    inicio = datetime(ano, mes, 1)
    fim = datetime(ano, mes, ultimo, 23, 59, 59)
    return inicio, fim


def _receita_cmv_por_canal(db: Session, ano: int, mes: int) -> dict[str, dict]:
    """Σ receita bruta, CMV, unidades e nº de linhas por canal (válidas)."""
    stmt = (
        select(
            Venda.canal,
            func.coalesce(func.sum(Venda.receita_bruta), 0),
            func.coalesce(func.sum(Venda.cmv), 0),
            func.coalesce(func.sum(Venda.qtd), 0),
            func.count(Venda.id),
        )
        .where(
            Venda.status_erp == STATUS_VALIDO,
            extract("year", Venda.data_venda) == ano,
            extract("month", Venda.data_venda) == mes,
        )
        .group_by(Venda.canal)
    )
    resultado: dict[str, dict] = {}
    for canal, receita, cmv, qtd, linhas in db.execute(stmt):
        resultado[canal] = {
            "receita": _d(receita),
            "cmv": _d(cmv),
            "unidades": _d(qtd),
            "linhas": int(linhas),
        }
    return resultado


def listar_despesas(db: Session, ano: int, mes: int) -> dict[str, dict[str, Decimal]]:
    """Despesas lançadas na competência, agrupadas: grupo -> {categoria: valor}.

    Preenche com o TEMPLATE (valor 0) as categorias ainda não lançadas, para a
    tela renderizar todos os campos editáveis.
    """
    agrupado: dict[str, dict[str, Decimal]] = {
        grupo: {cat: ZERO for cat in cats} for grupo, cats in TEMPLATE.items()
    }
    stmt = select(DespesaDRE).where(DespesaDRE.ano == ano, DespesaDRE.mes == mes)
    for d in db.execute(stmt).scalars():
        agrupado.setdefault(d.grupo, {})[d.categoria] = _d(d.valor)
    return agrupado


def upsert_despesa(
    db: Session, ano: int, mes: int, grupo: str, categoria: str, valor: Decimal
) -> DespesaDRE:
    """Cria ou atualiza uma linha de despesa da DRE (idempotente pela chave)."""
    existente = db.execute(
        select(DespesaDRE).where(
            DespesaDRE.ano == ano,
            DespesaDRE.mes == mes,
            DespesaDRE.grupo == grupo,
            DespesaDRE.categoria == categoria,
        )
    ).scalar_one_or_none()
    if existente is None:
        existente = DespesaDRE(
            ano=ano, mes=mes, grupo=grupo, categoria=categoria, valor=valor
        )
        db.add(existente)
    else:
        existente.valor = valor
    db.flush()
    return existente


def calcular_dre(
    db: Session, ano: int, mes: int, marketplace: str = MARKETPLACE_TODOS
) -> dict:
    """Monta a DRE completa da competência para o marketplace informado."""
    por_canal = _receita_cmv_por_canal(db, ano, mes)
    ml = por_canal.get(CANAL_ML, {"receita": ZERO, "cmv": ZERO, "unidades": ZERO, "linhas": 0})
    shopee = por_canal.get(CANAL_SHOPEE, {"receita": ZERO, "cmv": ZERO, "unidades": ZERO, "linhas": 0})

    filtro = (marketplace or MARKETPLACE_TODOS).strip()
    inclui_ml = filtro in (MARKETPLACE_TODOS, CANAL_ML)
    inclui_shopee = filtro in (MARKETPLACE_TODOS, CANAL_SHOPEE)

    receita_ml = ml["receita"] if inclui_ml else ZERO
    receita_shopee = shopee["receita"] if inclui_shopee else ZERO
    receita_bruta = receita_ml + receita_shopee

    cmv = (ml["cmv"] if inclui_ml else ZERO) + (shopee["cmv"] if inclui_shopee else ZERO)
    unidades = (ml["unidades"] if inclui_ml else ZERO) + (shopee["unidades"] if inclui_shopee else ZERO)

    despesas = listar_despesas(db, ano, mes)

    deducoes_itens = despesas.get(GRUPO_DEDUCOES, {})
    total_deducoes = sum(deducoes_itens.values(), ZERO)
    receita_liquida = receita_bruta - total_deducoes

    lucro_bruto = receita_liquida - cmv

    op_ml_itens = despesas.get(GRUPO_OPERACIONAL_ML, {}) if inclui_ml else {}
    op_shopee_itens = despesas.get(GRUPO_OPERACIONAL_SHOPEE, {}) if inclui_shopee else {}
    total_op_ml = sum(op_ml_itens.values(), ZERO)
    total_op_shopee = sum(op_shopee_itens.values(), ZERO)
    total_operacionais = total_op_ml + total_op_shopee

    lucro_operacional = lucro_bruto - total_operacionais

    gerais_itens = despesas.get(GRUPO_GERAL, {})
    total_gerais = sum(gerais_itens.values(), ZERO)
    lucro_liquido = lucro_operacional - total_gerais

    # EBITDA aproximado: lucro operacional (não rastreamos depreciação/amortização).
    ebitda = lucro_operacional

    def itens(mapa: dict[str, Decimal]) -> dict[str, str]:
        return {k: str(_q(v)) for k, v in mapa.items()}

    return {
        "competencia": {"ano": ano, "mes": mes},
        "marketplace": filtro,
        "unidades": str(_q(unidades)),
        "receitas": {
            "mercado_livre": str(_q(receita_ml)),
            "shopee": str(_q(receita_shopee)),
            "receita_bruta": str(_q(receita_bruta)),
            "deducoes": {
                "itens": itens(deducoes_itens),
                "total": str(_q(total_deducoes)),
            },
            "receita_liquida": str(_q(receita_liquida)),
        },
        "cmv": str(_q(cmv)),
        "lucro_bruto": str(_q(lucro_bruto)),
        "despesas_operacionais": {
            "mercado_livre": {"itens": itens(op_ml_itens), "total": str(_q(total_op_ml))},
            "shopee": {"itens": itens(op_shopee_itens), "total": str(_q(total_op_shopee))},
            "total": str(_q(total_operacionais)),
        },
        "lucro_operacional": str(_q(lucro_operacional)),
        "despesas_gerais": {"itens": itens(gerais_itens), "total": str(_q(total_gerais))},
        "lucro_liquido": str(_q(lucro_liquido)),
        "ebitda": str(_q(ebitda)),
        "margens": {
            "bruta": str(_margem(lucro_bruto, receita_liquida)),
            "operacional": str(_margem(lucro_operacional, receita_liquida)),
            "liquida": str(_margem(lucro_liquido, receita_liquida)),
        },
    }


def competencias_disponiveis(db: Session) -> list[dict]:
    """Lista de (ano, mes) que possuem vendas válidas, mais recente primeiro."""
    stmt = (
        select(
            extract("year", Venda.data_venda).label("ano"),
            extract("month", Venda.data_venda).label("mes"),
        )
        .where(Venda.data_venda.isnot(None), Venda.status_erp == STATUS_VALIDO)
        .distinct()
    )
    linhas = [
        {"ano": int(a), "mes": int(m)}
        for a, m in db.execute(stmt)
        if a is not None and m is not None
    ]
    linhas.sort(key=lambda x: (x["ano"], x["mes"]), reverse=True)
    return linhas
