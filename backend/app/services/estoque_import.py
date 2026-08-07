"""Importação do estoque atual a partir de uma planilha (contagem/inventário).

O usuário sobe uma planilha com o que tem fisicamente em estoque hoje. O
estoque pode estar dividido entre locais — tipicamente **Galpão** e **ML
Fulfillment**. A planilha suporta três formatos:

1. **Duas colunas de quantidade** (mais comum): ``SKU`` + ``Galpão`` +
   ``ML Full`` (+ ``Custo``). Cada coluna com valor vira um saldo no local.
2. **Coluna Local por linha**: ``SKU`` + ``Local`` (Galpão/Full) +
   ``Quantidade`` (+ ``Custo``).
3. **Um local só**: ``SKU`` + ``Quantidade`` (+ ``Custo``) — vai para o galpão
   (ou para o ``local_id`` informado).

Para cada local presente na planilha o serviço faz uma **substituição total**
(a planilha vira a verdade daquele local): os SKUs listados recebem a
quantidade informada e qualquer SKU que hoje tem saldo naquele local mas **não
está na planilha é zerado**. Locais que não aparecem na planilha (ex.: importar
só o galpão não mexe no Full) ficam intactos. Tudo idempotente — reimportar a
mesma planilha dá o mesmo resultado — e cada mudança é registrada no ledger com
origem ``inventario``.

Com o estoque valorizado (quantidade × custo), os cálculos que dependem de
estoque passam a considerar esses saldos: valor total do estoque, giro por SKU
e alertas de estoque mínimo.

Regra de custo (para valorização):
- Se a planilha traz um custo > 0, ele vira o custo médio do saldo.
- Senão, usa o ``preco_compra`` cadastrado do produto (mesma base do CMV).
- Senão, mantém o custo médio já existente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.estoque import (
    LOCAL_FULFILLMENT,
    LOCAL_GALPAO,
    MOV_ENTRADA,
    MOV_SAIDA,
    EstoqueSaldo,
    Local,
    MovimentoEstoque,
)
from app.models.produto import Produto
from app.models.sku_map import SkuMap
from app.parsers.common import is_empty, to_decimal, to_str
from app.services.catalogo import _achar_coluna, extrair_sku
from app.services.estoque import _d, obter_ou_criar_saldo

ZERO = Decimal("0")
CENT = Decimal("0.01")
Q_QTD = Decimal("0.001")

# Nomes de local padrão por tipo (usados ao criar o local se ainda não existir).
NOME_LOCAL_PADRAO = {LOCAL_GALPAO: "Galpão Central", LOCAL_FULFILLMENT: "ML Fulfillment"}

# Nomes de coluna aceitos (case-insensitive), com match parcial.
_COLS_SKU = ("sku base", "sku", "código", "codigo", "cod", "referência", "referencia", "ref")
_COLS_NOME = ("item", "nome", "produto", "descrição", "descricao")
_COLS_QTD = (
    "quantidade em estoque", "estoque atual", "qtd disponível", "qtd disponivel",
    "quantidade atual", "quantidade", "estoque", "saldo", "qtd", "unidades",
)
_COLS_CUSTO = (
    "custo unitário", "custo unitario", "valor de custo", "preço de custo",
    "preco de custo", "custo", "valor und", "valor unitário", "valor unitario",
)
# Colunas de quantidade específicas por local (formato "largo").
_COLS_QTD_GALPAO = (
    "galpão", "galpao", "estoque galpão", "estoque galpao", "depósito", "deposito",
    "próprio", "proprio", "casa", "estoque próprio", "estoque proprio",
)
_COLS_QTD_FULL = (
    "ml full", "mercado livre full", "fulfillment", "estoque full", "full", "fba",
)
# Coluna de texto que indica o local (formato "longo").
_COLS_LOCAL = ("local", "depósito", "deposito", "armazém", "armazem", "estoque local")


def _tipo_local_por_texto(texto: str) -> str:
    """Mapeia um rótulo de local para o tipo interno (fulfillment ou galpão)."""
    t = (texto or "").strip().lower()
    if any(k in t for k in ("full", "fulfillment", "fba")):
        return LOCAL_FULFILLMENT
    return LOCAL_GALPAO


@dataclass
class LinhaEstoque:
    sku_texto: str
    qtd: Decimal
    custo: Decimal | None = None
    # Tipo de local desejado ("galpao"/"fulfillment") ou None (usa o default).
    local_tipo: str | None = None


@dataclass
class ResultadoEstoqueImport:
    linhas: int = 0
    atualizados: int = 0
    saldos_criados: int = 0
    zerados: int = 0
    ignorados: int = 0
    unidades_total: Decimal = ZERO
    valor_total: Decimal = ZERO
    locais: list[str] = field(default_factory=list)
    por_local: dict[str, dict] = field(default_factory=dict)
    nao_encontrados: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    def _local(self, nome: str) -> dict:
        return self.por_local.setdefault(
            nome, {"atualizados": 0, "zerados": 0, "unidades": ZERO, "valor": ZERO}
        )

    def as_dict(self) -> dict:
        return {
            "linhas": self.linhas,
            "atualizados": self.atualizados,
            "saldos_criados": self.saldos_criados,
            "zerados": self.zerados,
            "ignorados": self.ignorados,
            "unidades_total": str(self.unidades_total.quantize(Q_QTD)),
            "valor_total": str(self.valor_total.quantize(CENT)),
            "locais": self.locais,
            "por_local": [
                {
                    "local": nome,
                    "atualizados": dados["atualizados"],
                    "zerados": dados["zerados"],
                    "unidades": str(dados["unidades"].quantize(Q_QTD)),
                    "valor": str(dados["valor"].quantize(CENT)),
                }
                for nome, dados in self.por_local.items()
            ],
            "nao_encontrados": self.nao_encontrados,
            "erros": self.erros,
        }


def parse_estoque(registros: list[dict]) -> list[LinhaEstoque]:
    """Converte as linhas da planilha em ``LinhaEstoque`` (uma ou mais por linha).

    Detecta automaticamente o formato: colunas separadas por local (Galpão/ML
    Full), coluna Local por linha, ou um único local. A quantidade é
    obrigatória em algum desses formatos; custo é opcional.
    """
    if not registros:
        return []
    colunas = list(registros[0].keys())
    col_sku = _achar_coluna(colunas, _COLS_SKU)
    col_nome = _achar_coluna(colunas, _COLS_NOME)
    col_custo = _achar_coluna(colunas, _COLS_CUSTO)
    col_galpao = _achar_coluna(colunas, _COLS_QTD_GALPAO)
    col_full = _achar_coluna(colunas, _COLS_QTD_FULL)
    col_local = _achar_coluna(colunas, _COLS_LOCAL)
    # A coluna genérica de quantidade não pode colidir com as de local.
    ocupadas = {c for c in (col_galpao, col_full) if c}
    col_qtd = _achar_coluna([c for c in colunas if c not in ocupadas], _COLS_QTD)

    if col_sku is None and col_nome is None:
        raise ValueError(
            "Coluna de SKU não encontrada (esperado 'SKU', 'Código' ou 'Nome')."
        )
    tem_largo = bool(col_galpao or col_full)
    if not tem_largo and col_qtd is None:
        raise ValueError(
            "Coluna de quantidade não encontrada (esperado 'Quantidade', "
            "'Estoque', ou colunas 'Galpão' e 'ML Full')."
        )

    linhas: list[LinhaEstoque] = []
    for reg in registros:
        sku_texto = to_str(reg.get(col_sku)) if col_sku else ""
        if not sku_texto and col_nome:
            sku_texto = to_str(reg.get(col_nome))
        if not sku_texto:
            continue
        custo = to_decimal(reg.get(col_custo)) if col_custo else None

        if tem_largo:
            # Uma entrada por coluna de local preenchida (célula vazia = pular).
            if col_galpao is not None and not is_empty(reg.get(col_galpao)):
                linhas.append(LinhaEstoque(sku_texto, to_decimal(reg.get(col_galpao)),
                                           custo, LOCAL_GALPAO))
            if col_full is not None and not is_empty(reg.get(col_full)):
                linhas.append(LinhaEstoque(sku_texto, to_decimal(reg.get(col_full)),
                                           custo, LOCAL_FULFILLMENT))
        else:
            local_tipo = None
            if col_local is not None:
                local_tipo = _tipo_local_por_texto(to_str(reg.get(col_local)))
            linhas.append(LinhaEstoque(sku_texto, to_decimal(reg.get(col_qtd)),
                                       custo, local_tipo))
    return linhas


def _local_por_tipo(db: Session, tipo: str, cache: dict[str, Local]) -> Local:
    """Obtém (ou cria) o local do tipo informado."""
    if tipo in cache:
        return cache[tipo]
    local = db.execute(
        select(Local).where(Local.tipo == tipo).order_by(Local.id)
    ).scalars().first()
    if local is None:
        local = Local(nome=NOME_LOCAL_PADRAO.get(tipo, tipo.title()), tipo=tipo)
        db.add(local)
        db.flush()
    cache[tipo] = local
    return local


def _local_default(db: Session, local_id: int | None, cache: dict[str, Local]) -> Local:
    if local_id is not None:
        local = db.get(Local, local_id)
        if local is None:
            raise ValueError(f"Local id={local_id} não encontrado")
        return local
    return _local_por_tipo(db, LOCAL_GALPAO, cache)


def _resolver_produto(
    texto: str, por_sku: dict[str, Produto], por_canal: dict[str, Produto]
) -> Produto | None:
    """Resolve o texto da planilha para um produto (sku_base, SKU derivado ou de-para)."""
    chave = texto.strip().upper()
    if chave in por_sku:
        return por_sku[chave]
    derivado = extrair_sku(texto)
    if derivado and derivado in por_sku:
        return por_sku[derivado]
    if chave in por_canal:
        return por_canal[chave]
    return None


def importar_estoque(
    db: Session, linhas: list[LinhaEstoque], *, local_id: int | None = None
) -> ResultadoEstoqueImport:
    """Ajusta o saldo de estoque de cada (SKU, local) para o valor da planilha.

    Define ``qtd_disponivel`` igual à quantidade informada (ajuste de
    inventário, idempotente) e registra a diferença no ledger. Atualiza o custo
    médio para valorização. SKUs não encontrados vão para ``nao_encontrados``
    sem bloquear a importação.
    """
    resultado = ResultadoEstoqueImport()
    cache_local: dict[str, Local] = {}

    por_sku: dict[str, Produto] = {}
    for p in db.execute(select(Produto)).scalars():
        if p.sku_base:
            por_sku[p.sku_base.strip().upper()] = p
    por_canal: dict[str, Produto] = {}
    for sm in db.execute(select(SkuMap)).scalars():
        if sm.sku_canal and sm.produto_id:
            produto = db.get(Produto, sm.produto_id)
            if produto is not None:
                por_canal[sm.sku_canal.strip().upper()] = produto

    # SKUs listados na planilha por local (para saber o que zerar depois).
    locais_tocados: dict[int, Local] = {}
    presentes_por_local: dict[int, set[int]] = {}

    for linha in linhas:
        resultado.linhas += 1
        produto = _resolver_produto(linha.sku_texto, por_sku, por_canal)
        if produto is None:
            resultado.ignorados += 1
            if linha.sku_texto not in resultado.nao_encontrados:
                resultado.nao_encontrados.append(linha.sku_texto)
            continue

        if linha.local_tipo is not None:
            local = _local_por_tipo(db, linha.local_tipo, cache_local)
        else:
            local = _local_default(db, local_id, cache_local)
        locais_tocados[local.id] = local
        presentes_por_local.setdefault(local.id, set()).add(produto.id)

        qtd_nova = _d(linha.qtd)
        saldo = obter_ou_criar_saldo(db, produto.id, local.id)
        criado = _d(saldo.qtd_disponivel) == ZERO and _d(saldo.custo_medio) == ZERO
        delta = qtd_nova - _d(saldo.qtd_disponivel)

        # Custo médio para valorização (planilha > preço de compra > existente).
        if linha.custo is not None and _d(linha.custo) > 0:
            saldo.custo_medio = _d(linha.custo).quantize(Decimal("0.0001"))
        elif produto.preco_compra is not None and _d(produto.preco_compra) > 0:
            saldo.custo_medio = _d(produto.preco_compra).quantize(Decimal("0.0001"))

        saldo.qtd_disponivel = qtd_nova

        if delta != ZERO:
            _mov(db, produto.id, local.id, delta, _d(saldo.custo_medio))

        valor_linha = qtd_nova * _d(saldo.custo_medio)
        resultado.atualizados += 1
        if criado:
            resultado.saldos_criados += 1
        resultado.unidades_total += qtd_nova
        resultado.valor_total += valor_linha

        agg = resultado._local(local.nome)
        agg["atualizados"] += 1
        agg["unidades"] += qtd_nova
        agg["valor"] += valor_linha
        if local.nome not in resultado.locais:
            resultado.locais.append(local.nome)

    # Substituição total por local: zera os SKUs que têm saldo no local mas não
    # vieram na planilha (a planilha vira a verdade daquele local).
    for local_id_tocado, local in locais_tocados.items():
        presentes = presentes_por_local.get(local_id_tocado, set())
        saldos = db.execute(
            select(EstoqueSaldo).where(EstoqueSaldo.local_id == local_id_tocado)
        ).scalars().all()
        for saldo in saldos:
            if saldo.produto_id in presentes:
                continue
            atual = _d(saldo.qtd_disponivel)
            if atual == ZERO:
                continue
            _mov(db, saldo.produto_id, local_id_tocado, -atual, _d(saldo.custo_medio))
            saldo.qtd_disponivel = ZERO
            resultado.zerados += 1
            resultado._local(local.nome)["zerados"] += 1

    db.flush()
    return resultado


def _mov(db: Session, produto_id: int, local_id: int, delta: Decimal, custo: Decimal) -> None:
    """Registra no ledger o ajuste de inventário (entrada se +, saída se −)."""
    db.add(
        MovimentoEstoque(
            produto_id=produto_id, local_id=local_id,
            tipo=MOV_ENTRADA if delta > 0 else MOV_SAIDA,
            qtd=abs(delta), custo_unitario=custo,
            origem="inventario", referencia="Importação de estoque",
        )
    )
