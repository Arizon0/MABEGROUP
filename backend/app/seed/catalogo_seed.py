"""Seed do catálogo real de produtos (SKU extraído do nome + custo).

Dados fornecidos pelo cliente. O SKU é derivado por ``extrair_sku`` — a mesma
regra usada na importação em massa — garantindo consistência total.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.catalogo import LinhaCatalogo, extrair_sku, importar_catalogo

# (nome do produto, custo unitário em R$)
CATALOGO: list[tuple[str, str]] = [
    ("Aneis 8126050", "75.00"),
    ("Aneis 9200STD", "75.00"),
    ("Aneis 9403STD", "75.00"),
    ("Anel 8126 STD", "75.00"),
    ("Anel SDA6631 050", "75.00"),
    ("Anel SDA7092", "75.00"),
    ("Bronzina De Biela SBB 1035-J 0,25", "32.00"),
    ("Jogo de Anel 7224 050", "75.00"),
    ("Jogo de Anel 7224-STD", "75.00"),
    ("Retentor 1135", "8.00"),
    ("Retentor 1942", "5.00"),
    ("Retentor 2075", "6.00"),
    ("Retentor 2178", "5.00"),
    ("Retentor 2283", "12.00"),
    ("Retentor 2317", "7.00"),
    ("Retentor 2370", "6.50"),
    ("Retentor 2371", "6.00"),
    ("Retentor 2373", "6.00"),
    ("Retentor 2374", "8.00"),
    ("Retentor 2400", "14.00"),
    ("Retentor 2525", "5.00"),
    ("Retentor 2539", "6.00"),
    ("Retentor 2544", "12.00"),
    ("Retentor 3044", "8.00"),
    ("Retentor 5159", "6.00"),
    ("Retentor 5245", "50.00"),
    ("Retentor 5266", "6.00"),
    ("Retentor 5338", "55.00"),
    ("Retentor 5502", "65.00"),
    ("Retentor 5601", "20.00"),
    ("Retentor 5699", "95.00"),
    ("Retentor 5702", "25.00"),
    ("Retentor 5772", "40.00"),
    ("Retentor 5801", "80.00"),
    ("Vedadores 9203", "8.00"),
]


def seed_catalogo(db: Session) -> dict[str, int]:
    """Cria/atualiza os produtos do catálogo real (idempotente por SKU)."""
    linhas = [
        LinhaCatalogo(nome=nome, custo=Decimal(custo), sku=extrair_sku(nome))
        for nome, custo in CATALOGO
    ]
    resultado = importar_catalogo(db, linhas)
    db.commit()
    return {"criados": resultado.criados, "atualizados": resultado.atualizados}
