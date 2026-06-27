"""Serviço de importação: persiste ``VendaDTO`` resolvendo SKUs e duplicados."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.venda import Venda
from app.parsers.common import VendaDTO
from app.services.sku_resolver import SkuResolver
from app.services.totais import Totais, calcular_totais


@dataclass
class ResultadoImportacao:
    canal: str
    linhas_arquivo: int           # linhas no arquivo (DTOs gerados)
    vendas_inseridas: int
    pedidos_duplicados: int       # pedidos ignorados por já existirem
    skus_resolvidos: int
    skus_pendentes: int           # sku_canal distintos sem de-para
    totais: Totais

    def as_dict(self) -> dict:
        return {
            "canal": self.canal,
            "linhas_arquivo": self.linhas_arquivo,
            "vendas_inseridas": self.vendas_inseridas,
            "pedidos_duplicados": self.pedidos_duplicados,
            "skus_resolvidos": self.skus_resolvidos,
            "skus_pendentes": self.skus_pendentes,
            "totais": self.totais.as_dict(),
        }


def importar_vendas(
    db: Session, vendas: list[VendaDTO], canal: str
) -> ResultadoImportacao:
    """Persiste a lista de vendas de um canal.

    - Resolve ``sku_canal`` -> ``sku_base`` (pendência quando não encontrado).
    - Ignora pedidos já importados (mesmo canal + id_pedido_canal) — regra 6.
    - Retorna totais agregados do arquivo (independente de duplicidade).
    """
    resolver = SkuResolver(db)

    # Pedidos já existentes deste canal (regra 6: detectar duplicados).
    existentes = set(
        db.execute(
            select(Venda.id_pedido_canal).where(Venda.canal == canal).distinct()
        ).scalars()
    )

    skus_resolvidos = 0
    inseridas = 0
    pedidos_duplicados_ids: set[str] = set()

    for dto in vendas:
        dto.sku_base = resolver.resolver(
            dto.sku_canal,
            canal,
            id_anuncio=dto.id_anuncio,
            titulo=dto.titulo,
        )
        if dto.sku_base is not None:
            skus_resolvidos += 1

        if dto.id_pedido_canal and dto.id_pedido_canal in existentes:
            pedidos_duplicados_ids.add(dto.id_pedido_canal)
            continue

        db.add(_dto_to_model(dto))
        inseridas += 1

    db.flush()

    return ResultadoImportacao(
        canal=canal,
        linhas_arquivo=len(vendas),
        vendas_inseridas=inseridas,
        pedidos_duplicados=len(pedidos_duplicados_ids),
        skus_resolvidos=skus_resolvidos,
        skus_pendentes=len(resolver.pendencias),
        totais=calcular_totais(vendas),
    )


def _dto_to_model(dto: VendaDTO) -> Venda:
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
        receita_bruta=dto.receita_bruta,
        tarifas_plataforma=dto.tarifas_plataforma,
        frete_liquido=dto.frete_liquido,
        descontos=dto.descontos,
        cancelamentos=dto.cancelamentos,
        liquido_recebido=dto.liquido_recebido,
        is_pacote_multi=dto.is_pacote_multi,
    )
