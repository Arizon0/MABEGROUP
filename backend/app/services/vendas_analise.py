"""Análise venda-a-venda: margem real de cada pedido.

O dashboard e a DRE respondem "quanto sobrou no mês". Esta análise responde a
pergunta que muda decisão: **quais pedidos deram prejuízo e por quê**. Para
isso reconstrói, pedido a pedido, todos os custos que consomem a receita:

    margem = líquido recebido − CMV − Ads − Imposto

``líquido recebido`` é o valor que o canal efetivamente pagou (já descontadas
comissão, frete e descontos/cancelamentos) — importado direto do relatório, sem
recálculo, conforme a armadilha nº 4 do CLAUDE.md. As colunas Comissão e Frete
existem para **explicar** o líquido, não para serem subtraídas de novo.

Os dois custos que nenhum relatório de vendas entrega são reconstruídos aqui:

- **Imposto**: alíquota efetiva da competência (``AliquotaImposto``, com
  vigência) aplicada sobre a receita bruta do pedido.
- **Ads**: rateio do investimento em publicidade do mês (``AdsInvestimento``)
  entre os pedidos que ele cobre, proporcional à receita. Ver ``ratear_ads``.

A unidade de análise é o **pedido**, não a linha da planilha: um pacote
multi-produto do Mercado Livre chega como uma linha-resumo (que carrega o
dinheiro) mais N linhas-componente (que carregam os SKUs e o CMV). Analisadas
separadamente, a linha-resumo pareceria lucro puro e cada componente, prejuízo
total. Agrupadas por ``(canal, id_pedido_canal)``, fecham a conta.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.custos_venda import (
    ESCOPO_ANUNCIO,
    ESCOPO_CANAL,
    ESCOPO_SKU,
    AdsInvestimento,
    AliquotaImposto,
)
from app.models.venda import Venda
from app.parsers.common import CANAL_ML, STATUS_VALIDO

ZERO = Decimal("0")
CENT = Decimal("0.01")
CEM = Decimal("100")
# Tolerância da conferência do líquido: 1 centavo de arredondamento do canal.
TOLERANCIA = CENT

# ---- Recortes (os "chips" da tela) --------------------------------------- #
RECORTE_TODOS = "todos"
RECORTE_NEGATIVOS = "negativos"
RECORTE_SEM_CUSTO = "sem-custo"
RECORTE_SEM_COMISSAO = "sem-comissao"
RECORTE_SEM_FRETE = "sem-frete"
RECORTE_PACOTES = "pacotes"
RECORTE_REVISAR = "revisar"

RECORTES = (
    RECORTE_TODOS,
    RECORTE_NEGATIVOS,
    RECORTE_SEM_CUSTO,
    RECORTE_SEM_COMISSAO,
    RECORTE_SEM_FRETE,
    RECORTE_PACOTES,
    RECORTE_REVISAR,
)

# ---- Ordenações ----------------------------------------------------------- #
ORDEM_PIOR_MARGEM_VALOR = "pior-margem-valor"
ORDEM_PIOR_MARGEM_PCT = "pior-margem-pct"
ORDEM_MELHOR_MARGEM_VALOR = "melhor-margem-valor"
ORDEM_MELHOR_MARGEM_PCT = "melhor-margem-pct"
ORDEM_MAIOR_VENDA = "maior-venda"
ORDEM_MAIOR_FRETE = "maior-frete"
ORDEM_DATA = "data"

ORDENACOES = (
    ORDEM_PIOR_MARGEM_VALOR,
    ORDEM_PIOR_MARGEM_PCT,
    ORDEM_MELHOR_MARGEM_VALOR,
    ORDEM_MELHOR_MARGEM_PCT,
    ORDEM_MAIOR_VENDA,
    ORDEM_MAIOR_FRETE,
    ORDEM_DATA,
)

# ---- Alertas de qualidade do dado ---------------------------------------- #
ALERTA_SEM_SKU = "sem_sku"
ALERTA_SEM_CUSTO = "sem_custo"
ALERTA_SEM_COMISSAO = "sem_comissao"
ALERTA_RECEBER_NAO_BATE = "receber_nao_bate"

TAMANHO_PAGINA_PADRAO = 50
TAMANHO_PAGINA_MAX = 500


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENT)


def _pct(numerador: Decimal, base: Decimal) -> Decimal | None:
    """Percentual de ``numerador`` sobre ``base``; ``None`` quando não há base.

    Sem base não existe percentual — devolver 0 faria um pedido de receita zero
    aparecer como margem neutra, escondendo justamente o caso a investigar.
    """
    if base == ZERO:
        return None
    return (numerador / base * CEM).quantize(CENT)


# --------------------------------------------------------------------------- #
# Imposto: alíquota vigente por competência                                     #
# --------------------------------------------------------------------------- #


def aliquotas_vigentes(db: Session) -> list[tuple[int, int, Decimal]]:
    """Alíquotas cadastradas como ``(ano, mes, pct)``, da mais antiga à mais nova."""
    linhas = db.execute(select(AliquotaImposto)).scalars().all()
    return sorted(
        ((a.ano, a.mes, _d(a.aliquota_pct)) for a in linhas),
        key=lambda x: (x[0], x[1]),
    )


def aliquota_para(
    competencia: tuple[int, int] | None,
    vigencias: Sequence[tuple[int, int, Decimal]],
) -> Decimal:
    """Alíquota vigente na competência: a mais recente que não seja futura.

    Uma venda de maio continua tributada pela alíquota de maio mesmo depois de a
    empresa mudar de faixa em agosto — é o que permite reabrir uma competência
    antiga e encontrar o mesmo número.
    """
    if competencia is None:
        return ZERO
    vigente = ZERO
    for ano, mes, pct in vigencias:  # ordenada crescente
        if (ano, mes) <= competencia:
            vigente = pct
        else:
            break
    return vigente


# --------------------------------------------------------------------------- #
# Pedido: a unidade de análise                                                  #
# --------------------------------------------------------------------------- #


@dataclass
class Pedido:
    """Um pedido consolidado a partir de uma ou mais linhas importadas."""

    canal: str
    id_pedido_canal: str
    data_venda: datetime | None = None
    numero_nf: str | None = None
    titulo: str = ""
    skus: list[str] = field(default_factory=list)
    anuncios: list[str] = field(default_factory=list)
    canal_logistico: str = ""
    status_canal: str = ""
    linhas: int = 0
    qtd: Decimal = ZERO
    receita_bruta: Decimal = ZERO
    tarifas_plataforma: Decimal = ZERO
    frete_liquido: Decimal = ZERO
    descontos: Decimal = ZERO
    cancelamentos: Decimal = ZERO
    liquido_recebido: Decimal = ZERO
    cmv: Decimal = ZERO
    is_pacote_multi: bool = False
    # Preenchidos depois do rateio.
    ads: Decimal = ZERO
    acos_pct: Decimal | None = None
    imposto: Decimal = ZERO
    aliquota_pct: Decimal = ZERO

    @property
    def competencia(self) -> tuple[int, int] | None:
        if self.data_venda is None:
            return None
        return (self.data_venda.year, self.data_venda.month)

    @property
    def margem_valor(self) -> Decimal:
        return _q(self.liquido_recebido - self.cmv - self.ads - self.imposto)

    @property
    def margem_pct(self) -> Decimal | None:
        return _pct(self.margem_valor, self.receita_bruta)

    @property
    def tacos_pct(self) -> Decimal | None:
        """Ads sobre a receita **total** do pedido (não só a vinda de anúncio)."""
        return _pct(self.ads, self.receita_bruta)

    @property
    def diferenca_liquido(self) -> Decimal:
        """Soma dos componentes menos o líquido informado pelo canal."""
        soma = (
            self.receita_bruta
            + self.tarifas_plataforma
            + self.frete_liquido
            + self.descontos
            + self.cancelamentos
        )
        return _q(soma - self.liquido_recebido)

    @property
    def alertas(self) -> list[str]:
        """Motivos para o pedido entrar na fila de revisão."""
        problemas: list[str] = []
        if not self.skus:
            problemas.append(ALERTA_SEM_SKU)
        if self.cmv == ZERO:
            problemas.append(ALERTA_SEM_CUSTO)
        if self.tarifas_plataforma == ZERO:
            problemas.append(ALERTA_SEM_COMISSAO)
        if abs(self.diferenca_liquido) > TOLERANCIA:
            problemas.append(ALERTA_RECEBER_NAO_BATE)
        return problemas


def _absorver(pedido: Pedido, venda: Venda) -> None:
    """Soma uma linha importada dentro do pedido consolidado."""
    pedido.linhas += 1
    pedido.qtd += _d(venda.qtd)
    pedido.receita_bruta += _d(venda.receita_bruta)
    pedido.tarifas_plataforma += _d(venda.tarifas_plataforma)
    pedido.frete_liquido += _d(venda.frete_liquido)
    pedido.descontos += _d(venda.descontos)
    pedido.cancelamentos += _d(venda.cancelamentos)
    pedido.liquido_recebido += _d(venda.liquido_recebido)
    pedido.cmv += _d(venda.cmv)
    pedido.is_pacote_multi = pedido.is_pacote_multi or bool(venda.is_pacote_multi)

    if venda.data_venda and (
        pedido.data_venda is None or venda.data_venda < pedido.data_venda
    ):
        pedido.data_venda = venda.data_venda
    if venda.numero_nf and not pedido.numero_nf:
        pedido.numero_nf = venda.numero_nf
    if venda.status_canal and not pedido.status_canal:
        pedido.status_canal = venda.status_canal
    if venda.canal_logistico and not pedido.canal_logistico:
        pedido.canal_logistico = venda.canal_logistico
    if venda.sku_base and venda.sku_base not in pedido.skus:
        pedido.skus.append(venda.sku_base)
    if venda.id_anuncio and venda.id_anuncio not in pedido.anuncios:
        pedido.anuncios.append(venda.id_anuncio)
    # A linha-resumo de um pacote tem título genérico ("Pacote de N produtos") e
    # vem antes dos componentes. O título de um componente descreve o produto de
    # verdade, então ele substitui o genérico.
    if venda.titulo and (not pedido.titulo or venda.sku_base):
        pedido.titulo = venda.titulo


def consolidar_pedidos(vendas: Iterable[Venda]) -> list[Pedido]:
    """Agrupa linhas importadas em pedidos por ``(canal, id_pedido_canal)``."""
    pedidos: dict[tuple[str, str], Pedido] = {}
    for venda in vendas:
        chave = (venda.canal, venda.id_pedido_canal)
        pedido = pedidos.get(chave)
        if pedido is None:
            pedido = pedidos[chave] = Pedido(
                canal=venda.canal, id_pedido_canal=venda.id_pedido_canal
            )
        _absorver(pedido, venda)
    return list(pedidos.values())


# --------------------------------------------------------------------------- #
# Rateio de publicidade                                                         #
# --------------------------------------------------------------------------- #


@dataclass
class _Bucket:
    """Um lançamento de Ads e os pedidos que ele cobre."""

    valor: Decimal
    receita_ads: Decimal | None
    pedidos: list[Pedido] = field(default_factory=list)


def _chave_bucket(canal: str, ano: int, mes: int, escopo: str, referencia: str):
    return (canal, ano, mes, escopo, referencia)


def ratear_ads(db: Session, pedidos: Sequence[Pedido]) -> Decimal:
    """Distribui o investimento em Ads entre os pedidos, proporcional à receita.

    Cada pedido é coberto por **um só** lançamento: o de escopo mais específico
    que casar com ele — anúncio, depois SKU, depois o canal inteiro. Assim um
    lançamento de canal representa o investimento que sobrou fora dos anúncios e
    SKUs já detalhados, e nenhum pedido recebe verba duas vezes.

    Devolve o total que **não** pôde ser rateado: lançamento de uma competência
    em que aquele anúncio/SKU não vendeu, ou cujos pedidos somam receita zero.
    Esse resto aparece no resumo em vez de sumir — se ele for alto, a margem por
    pedido está subestimando o custo de publicidade.
    """
    lancamentos = db.execute(select(AdsInvestimento)).scalars().all()
    if not lancamentos:
        return ZERO

    por_chave: dict[tuple, _Bucket] = {
        _chave_bucket(a.canal, a.ano, a.mes, a.escopo, a.referencia or ""): _Bucket(
            valor=_d(a.valor),
            receita_ads=_d(a.receita_ads) if a.receita_ads is not None else None,
        )
        for a in lancamentos
    }

    for pedido in pedidos:
        competencia = pedido.competencia
        if competencia is None:
            continue
        ano, mes = competencia
        bucket = None
        for anuncio in pedido.anuncios:
            bucket = por_chave.get(
                _chave_bucket(pedido.canal, ano, mes, ESCOPO_ANUNCIO, anuncio)
            )
            if bucket is not None:
                break
        if bucket is None:
            for sku in pedido.skus:
                bucket = por_chave.get(
                    _chave_bucket(pedido.canal, ano, mes, ESCOPO_SKU, sku)
                )
                if bucket is not None:
                    break
        if bucket is None:
            bucket = por_chave.get(
                _chave_bucket(pedido.canal, ano, mes, ESCOPO_CANAL, "")
            )
        if bucket is not None:
            bucket.pedidos.append(pedido)

    nao_alocado = ZERO
    for bucket in por_chave.values():
        base = sum((p.receita_bruta for p in bucket.pedidos), ZERO)
        if base <= ZERO:
            nao_alocado += bucket.valor
            continue

        acos = None
        if bucket.receita_ads is not None and bucket.receita_ads > ZERO:
            acos = (bucket.valor / bucket.receita_ads * CEM).quantize(CENT)

        # Rateio com resto: distribui centavo a centavo e joga a sobra de
        # arredondamento no maior pedido, para Σ ads == valor lançado.
        distribuido = ZERO
        for pedido in bucket.pedidos:
            parte = _q(bucket.valor * pedido.receita_bruta / base)
            pedido.ads += parte
            pedido.acos_pct = acos
            distribuido += parte
        sobra = _q(bucket.valor - distribuido)
        if sobra != ZERO:
            maior = max(bucket.pedidos, key=lambda p: p.receita_bruta)
            maior.ads += sobra

    return _q(nao_alocado)


def aplicar_imposto(db: Session, pedidos: Sequence[Pedido]) -> None:
    """Calcula o imposto de cada pedido pela alíquota vigente na competência."""
    vigencias = aliquotas_vigentes(db)
    if not vigencias:
        return
    for pedido in pedidos:
        pct = aliquota_para(pedido.competencia, vigencias)
        pedido.aliquota_pct = pct
        pedido.imposto = _q(pedido.receita_bruta * pct / CEM)


# --------------------------------------------------------------------------- #
# Recorte, ordenação e serialização                                             #
# --------------------------------------------------------------------------- #


def _casa_recorte(pedido: Pedido, recorte: str) -> bool:
    if recorte == RECORTE_NEGATIVOS:
        return pedido.margem_valor < ZERO
    if recorte == RECORTE_SEM_CUSTO:
        return pedido.cmv == ZERO
    if recorte == RECORTE_SEM_COMISSAO:
        return pedido.tarifas_plataforma == ZERO
    if recorte == RECORTE_SEM_FRETE:
        return pedido.frete_liquido == ZERO
    if recorte == RECORTE_PACOTES:
        return pedido.is_pacote_multi
    if recorte == RECORTE_REVISAR:
        return bool(pedido.alertas)
    return True


_EPOCA = datetime.min


def _ordenar(pedidos: list[Pedido], ordem: str) -> list[Pedido]:
    """Ordena a lista. Percentuais nulos vão sempre para o fim, em qualquer sentido.

    Um pedido sem receita não tem margem percentual; deixá-lo participar da
    ordenação faria ele encabeçar a lista de "pior margem %" e empurrar para
    baixo os prejuízos reais.
    """
    def pct_asc(p: Pedido):
        valor = p.margem_pct
        return (valor is None, valor if valor is not None else ZERO)

    def pct_desc(p: Pedido):
        valor = p.margem_pct
        return (valor is None, -(valor if valor is not None else ZERO))

    if ordem == ORDEM_PIOR_MARGEM_VALOR:
        return sorted(pedidos, key=lambda p: p.margem_valor)
    if ordem == ORDEM_MELHOR_MARGEM_VALOR:
        return sorted(pedidos, key=lambda p: p.margem_valor, reverse=True)
    if ordem == ORDEM_PIOR_MARGEM_PCT:
        return sorted(pedidos, key=pct_asc)
    if ordem == ORDEM_MELHOR_MARGEM_PCT:
        return sorted(pedidos, key=pct_desc)
    if ordem == ORDEM_MAIOR_VENDA:
        return sorted(pedidos, key=lambda p: p.receita_bruta, reverse=True)
    if ordem == ORDEM_MAIOR_FRETE:
        return sorted(pedidos, key=lambda p: abs(p.frete_liquido), reverse=True)
    # ORDEM_DATA (padrão): mais recente primeiro; sem data vai para o fim.
    return sorted(pedidos, key=lambda p: p.data_venda or _EPOCA, reverse=True)


def _serializar(pedido: Pedido) -> dict:
    """Uma linha da tabela. Valores de custo saem positivos (é o que se lê)."""
    margem_pct = pedido.margem_pct
    tacos = pedido.tacos_pct
    return {
        "canal": pedido.canal,
        "id_pedido_canal": pedido.id_pedido_canal,
        "numero_nf": pedido.numero_nf,
        "data_venda": pedido.data_venda.isoformat() if pedido.data_venda else None,
        "titulo": pedido.titulo,
        "skus": pedido.skus,
        "anuncios": pedido.anuncios,
        "canal_logistico": pedido.canal_logistico,
        "status_canal": pedido.status_canal,
        "linhas": pedido.linhas,
        "is_pacote_multi": pedido.is_pacote_multi,
        "qtd": str(pedido.qtd),
        "total": str(_q(pedido.receita_bruta)),
        "custo": str(_q(pedido.cmv)),
        "frete": str(_q(abs(pedido.frete_liquido))),
        "comissao": str(_q(abs(pedido.tarifas_plataforma))),
        "descontos": str(_q(pedido.descontos)),
        "cancelamentos": str(_q(pedido.cancelamentos)),
        "liquido_recebido": str(_q(pedido.liquido_recebido)),
        "ads": str(_q(pedido.ads)),
        "acos_pct": str(pedido.acos_pct) if pedido.acos_pct is not None else None,
        "tacos_pct": str(tacos) if tacos is not None else None,
        "imposto": str(_q(pedido.imposto)),
        "aliquota_pct": str(pedido.aliquota_pct),
        "margem_valor": str(pedido.margem_valor),
        "margem_pct": str(margem_pct) if margem_pct is not None else None,
        "diferenca_liquido": str(pedido.diferenca_liquido),
        "alertas": pedido.alertas,
    }


# --------------------------------------------------------------------------- #
# Entrada principal                                                             #
# --------------------------------------------------------------------------- #


def carregar_pedidos(
    db: Session,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    canal: str | None = None,
    apenas_validas: bool = True,
) -> list[Pedido]:
    """Consolida os pedidos do período, já com Ads rateado e imposto aplicado."""
    stmt = select(Venda)
    if apenas_validas:
        stmt = stmt.where(Venda.status_erp == STATUS_VALIDO)
    if data_inicio:
        stmt = stmt.where(Venda.data_venda >= datetime.combine(data_inicio, time.min))
    if data_fim:
        stmt = stmt.where(Venda.data_venda <= datetime.combine(data_fim, time.max))
    if canal:
        stmt = stmt.where(Venda.canal == canal)

    pedidos = consolidar_pedidos(db.execute(stmt).scalars())
    aplicar_imposto(db, pedidos)
    ratear_ads(db, pedidos)
    return pedidos


def analisar(
    db: Session,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    canal: str | None = None,
    recorte: str = RECORTE_TODOS,
    ordem: str = ORDEM_DATA,
    busca: str | None = None,
    pagina: int = 1,
    tamanho: int = TAMANHO_PAGINA_PADRAO,
    apenas_validas: bool = True,
) -> dict:
    """Página da análise venda-a-venda, com resumo e contagem de cada recorte."""
    recorte = recorte if recorte in RECORTES else RECORTE_TODOS
    ordem = ordem if ordem in ORDENACOES else ORDEM_DATA
    pagina = max(1, pagina)
    tamanho = max(1, min(tamanho, TAMANHO_PAGINA_MAX))

    stmt = select(Venda)
    if apenas_validas:
        stmt = stmt.where(Venda.status_erp == STATUS_VALIDO)
    if data_inicio:
        stmt = stmt.where(Venda.data_venda >= datetime.combine(data_inicio, time.min))
    if data_fim:
        stmt = stmt.where(Venda.data_venda <= datetime.combine(data_fim, time.max))
    if canal:
        stmt = stmt.where(Venda.canal == canal)

    todos = consolidar_pedidos(db.execute(stmt).scalars())
    aplicar_imposto(db, todos)
    ads_nao_alocado = ratear_ads(db, todos)

    if busca:
        alvo = busca.strip().lower()
        todos = [p for p in todos if _bate_busca(p, alvo)]

    # Contagem por recorte sobre o período inteiro: é o que permite a tela
    # mostrar quantos pedidos cada chip esconde antes de o usuário clicar.
    contagem = {r: sum(1 for p in todos if _casa_recorte(p, r)) for r in RECORTES}

    filtrados = [p for p in todos if _casa_recorte(p, recorte)]
    ordenados = _ordenar(filtrados, ordem)

    total = len(ordenados)
    inicio = (pagina - 1) * tamanho
    fim = min(inicio + tamanho, total)
    janela = ordenados[inicio:fim] if inicio < total else []

    return {
        "filtros": {
            "data_inicio": data_inicio.isoformat() if data_inicio else None,
            "data_fim": data_fim.isoformat() if data_fim else None,
            "canal": canal,
            "recorte": recorte,
            "ordem": ordem,
            "busca": busca or None,
        },
        "resumo": _resumo(filtrados, ads_nao_alocado),
        "contagem_por_recorte": contagem,
        "paginacao": {
            "pagina": pagina,
            "tamanho": tamanho,
            "total": total,
            "paginas": (total + tamanho - 1) // tamanho if total else 0,
            "de": inicio + 1 if janela else 0,
            "ate": fim,
        },
        "pedidos": [_serializar(p) for p in janela],
    }


def _bate_busca(pedido: Pedido, alvo: str) -> bool:
    campos = [
        pedido.id_pedido_canal,
        pedido.numero_nf or "",
        pedido.titulo,
        *pedido.skus,
        *pedido.anuncios,
    ]
    return any(alvo in campo.lower() for campo in campos if campo)


def _resumo(pedidos: Sequence[Pedido], ads_nao_alocado: Decimal) -> dict:
    """Totais do conjunto exibido — a prova de que as colunas fecham."""
    total = len(pedidos)
    negativos = sum(1 for p in pedidos if p.margem_valor < ZERO)
    revisar = sum(1 for p in pedidos if p.alertas)

    receita = sum((p.receita_bruta for p in pedidos), ZERO)
    cmv = sum((p.cmv for p in pedidos), ZERO)
    frete = sum((abs(p.frete_liquido) for p in pedidos), ZERO)
    comissao = sum((abs(p.tarifas_plataforma) for p in pedidos), ZERO)
    ads = sum((p.ads for p in pedidos), ZERO)
    imposto = sum((p.imposto for p in pedidos), ZERO)
    liquido = sum((p.liquido_recebido for p in pedidos), ZERO)
    margem = sum((p.margem_valor for p in pedidos), ZERO)
    unidades = sum((p.qtd for p in pedidos), ZERO)
    prejuizo = sum((p.margem_valor for p in pedidos if p.margem_valor < ZERO), ZERO)

    return {
        "pedidos": total,
        "negativos": negativos,
        "pct_negativos": str(_pct(Decimal(negativos), Decimal(total)) or ZERO),
        "para_revisar": revisar,
        "unidades": str(unidades),
        "total": str(_q(receita)),
        "custo": str(_q(cmv)),
        "frete": str(_q(frete)),
        "comissao": str(_q(comissao)),
        "ads": str(_q(ads)),
        "imposto": str(_q(imposto)),
        "liquido_recebido": str(_q(liquido)),
        "margem_valor": str(_q(margem)),
        "margem_pct": str(_pct(margem, receita) or ZERO),
        "prejuizo_dos_negativos": str(_q(prejuizo)),
        "ads_nao_alocado": str(_q(ads_nao_alocado)),
    }
