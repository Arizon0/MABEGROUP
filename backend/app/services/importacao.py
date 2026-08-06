"""Serviço de importação: persiste ``VendaDTO`` resolvendo SKUs e duplicados."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.venda import Venda
from app.parsers.common import STATUS_VALIDO, VendaDTO
from app.services.estoque import BaixaEstoqueBatch
from app.services.financeiro import gerar_contas_receber
from app.services.sku_resolver import SkuResolver
from app.services.totais import Totais, calcular_totais

ZERO = Decimal("0")


@dataclass
class ResultadoImportacao:
    canal: str
    linhas_arquivo: int           # linhas no arquivo (DTOs gerados)
    vendas_inseridas: int
    pedidos_duplicados: int       # pedidos ignorados por já existirem
    skus_resolvidos: int
    skus_pendentes: int           # sku_canal distintos sem de-para
    totais: Totais
    baixas_estoque: int = 0       # linhas que geraram baixa de estoque
    contas_receber: int = 0       # recebíveis lançados
    cmv_total: Decimal = ZERO     # CMV congelado das vendas inseridas
    skus_nao_cadastrados: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "canal": self.canal,
            "linhas_arquivo": self.linhas_arquivo,
            "vendas_inseridas": self.vendas_inseridas,
            "pedidos_duplicados": self.pedidos_duplicados,
            "skus_resolvidos": self.skus_resolvidos,
            "skus_pendentes": self.skus_pendentes,
            "baixas_estoque": self.baixas_estoque,
            "contas_receber": self.contas_receber,
            "cmv_total": str(self.cmv_total),
            "skus_nao_cadastrados": self.skus_nao_cadastrados,
            "totais": self.totais.as_dict(),
        }


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def importar_vendas(
    db: Session,
    vendas: list[VendaDTO],
    canal: str,
    *,
    baixar_estoque: bool = False,
    gerar_financeiro: bool = False,
    resolver_direto: bool = False,
) -> ResultadoImportacao:
    """Persiste a lista de vendas de um canal.

    - Resolve ``sku_canal`` -> ``sku_base``. Por padrão via tabela ``sku_map``
      (relatórios ML/Shopee). Com ``resolver_direto=True`` (planilha simples da
      DRE) o ``sku_canal`` já é o ``sku_base`` do cadastro.
    - Congela ``custo_unitario`` e ``cmv`` no momento da importação, buscando o
      ``preco_compra`` do produto — garante que DREs antigas não mudem se o
      custo for alterado depois.
    - Ignora pedidos já importados (mesmo canal + id_pedido_canal) — regra 6.
    - Retorna totais agregados do arquivo (independente de duplicidade).
    """
    resolver = None if resolver_direto else SkuResolver(db)

    # Pedidos já existentes deste canal (regra 6: detectar duplicados).
    existentes = set(
        db.execute(
            select(Venda.id_pedido_canal).where(Venda.canal == canal).distinct()
        ).scalars()
    )

    # Mapa sku_base -> (produto_id, preco_compra), carregado uma vez. Usado para
    # a baixa de estoque e para congelar o CMV.
    produto_por_sku: dict[str, tuple[int, Decimal]] = {
        p.sku_base.upper(): (p.id, _d(p.preco_compra))
        for p in db.execute(select(Produto)).scalars()
    }
    baixa_batch = BaixaEstoqueBatch(db) if baixar_estoque else None

    skus_resolvidos = 0
    inseridas = 0
    baixas = 0
    cmv_total = ZERO
    pedidos_duplicados_ids: set[str] = set()
    nao_cadastrados: set[str] = set()
    inseridas_models: list[Venda] = []

    for dto in vendas:
        if resolver_direto:
            sku = (dto.sku_canal or "").strip()
            dto.sku_base = sku if sku.upper() in produto_por_sku else None
            if dto.sku_base is None and sku:
                nao_cadastrados.add(sku)
        else:
            dto.sku_base = resolver.resolver(
                dto.sku_canal,
                canal,
                id_anuncio=dto.id_anuncio,
                titulo=dto.titulo,
            )
        if dto.sku_base is not None:
            skus_resolvidos += 1

        # Congela custo/CMV a partir do cadastro (0 se produto sem custo/ausente).
        custo, cmv = _snapshot_cmv(dto, produto_por_sku)
        cmv_total += cmv

        if dto.id_pedido_canal and dto.id_pedido_canal in existentes:
            pedidos_duplicados_ids.add(dto.id_pedido_canal)
            continue

        modelo = _dto_to_model(dto, custo, cmv)
        db.add(modelo)
        inseridas_models.append(modelo)
        inseridas += 1

        if (
            baixa_batch is not None
            and dto.status_erp == STATUS_VALIDO
            and dto.sku_base
            and dto.sku_base.upper() in produto_por_sku
            and dto.qtd > 0
        ):
            if baixa_batch.baixar(
                produto_id=produto_por_sku[dto.sku_base.upper()][0],
                canal_logistico=dto.canal_logistico,
                qtd=dto.qtd,
                referencia=f"{canal}:{dto.id_pedido_canal}",
            ):
                baixas += 1

    db.flush()

    contas = gerar_contas_receber(db, inseridas_models) if gerar_financeiro else 0
    pendentes = len(resolver.pendencias) if resolver is not None else 0

    return ResultadoImportacao(
        canal=canal,
        linhas_arquivo=len(vendas),
        vendas_inseridas=inseridas,
        pedidos_duplicados=len(pedidos_duplicados_ids),
        skus_resolvidos=skus_resolvidos,
        skus_pendentes=pendentes,
        totais=calcular_totais(vendas),
        baixas_estoque=baixas,
        contas_receber=contas,
        cmv_total=cmv_total,
        skus_nao_cadastrados=sorted(nao_cadastrados),
    )


def _snapshot_cmv(
    dto: VendaDTO, produto_por_sku: dict[str, tuple[int, Decimal]]
) -> tuple[Decimal, Decimal]:
    """Devolve (custo_unitario, cmv) congelados; zero quando não há custo/SKU.

    Só computa CMV para vendas válidas — canceladas/devolvidas não consomem
    estoque nem entram no CMV da DRE.
    """
    if dto.status_erp != STATUS_VALIDO or not dto.sku_base:
        return ZERO, ZERO
    entrada = produto_por_sku.get(dto.sku_base.upper())
    if entrada is None:
        return ZERO, ZERO
    custo = entrada[1]
    return custo, (custo * _d(dto.qtd)).quantize(Decimal("0.01"))


def _dto_to_model(dto: VendaDTO, custo: Decimal, cmv: Decimal) -> Venda:
    return Venda(
        canal=dto.canal,
        id_pedido_canal=dto.id_pedido_canal,
        data_venda=dto.data_venda,
        status_canal=dto.status_canal,
        status_erp=dto.status_erp,
        sku_canal=dto.sku_canal,
        sku_base=dto.sku_base,
        id_anuncio=dto.id_anuncio,
        titulo=dto.titulo,
        tipo_anuncio=dto.tipo_anuncio,
        canal_logistico=dto.canal_logistico,
        variacao=dto.variacao,
        qtd=dto.qtd,
        preco_unitario=dto.preco_unitario,
        custo_unitario=custo,
        cmv=cmv,
        receita_bruta=dto.receita_bruta,
        tarifas_plataforma=dto.tarifas_plataforma,
        frete_liquido=dto.frete_liquido,
        descontos=dto.descontos,
        cancelamentos=dto.cancelamentos,
        liquido_recebido=dto.liquido_recebido,
        is_pacote_multi=dto.is_pacote_multi,
    )
