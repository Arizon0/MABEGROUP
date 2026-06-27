"""Seed do de-para de SKUs verificado nos dados reais (mai–jun 2026).

⚠️ ``8126STA`` (Shopee) é o mesmo produto que ``8126`` / ``8126STD`` / ``8126a``
(ML). A heurística de prefixo numérico não detecta esse caso — por isso o
de-para manual é obrigatório.
"""
from __future__ import annotations

from app.parsers.common import CANAL_ML, CANAL_SHOPEE

# Nomes conhecidos (top SKUs). Os demais recebem nome genérico no seed.
NOMES_PRODUTOS: dict[str, str] = {
    "5338": "Retentor Volante Virabrequim Ka/Fiesta/Ecosport",
    "8126": "Jogo Anel Pistão STD VW Fox 1.6 8v EA111",
    "5245": "Retentor Volante Traseiro Palio Fiat Fire",
    "5699": "Retentor Volante Liso VW Fox 1.0 8v Power",
    "7224": "Jogo Anéis Motor VW Fox 1.0 8v EA111 STD",
}

# sku_base -> {"ml": [sku_canal...], "anuncios": [...], "shopee": [sku_canal...]}
DE_PARA: dict[str, dict[str, list[str]]] = {
    "1942": {"ml": ["1942", "1942a"], "anuncios": ["MLB6495247730", "MLB4713127283"], "shopee": ["1942"]},
    "2178": {"ml": ["2178"], "anuncios": ["MLB6495711080"], "shopee": ["2178"]},
    "2370": {"ml": ["2370", "2370a"], "anuncios": ["MLB4552506931"], "shopee": ["2370"]},
    "2373": {"ml": ["2373", "2373a"], "anuncios": ["MLB6495838052", "MLB4711870615"], "shopee": ["2373"]},
    "2374": {"ml": ["2374"], "anuncios": [], "shopee": ["2374"]},
    "2400": {"ml": ["2400"], "anuncios": [], "shopee": ["2400"]},
    "2525": {"ml": ["2525", "2525a"], "anuncios": ["MLB6495579710", "MLB4712115725"], "shopee": ["2525"]},
    "2544": {"ml": ["2544"], "anuncios": [], "shopee": ["2544"]},
    "3044": {"ml": ["3044"], "anuncios": ["MLB4550074163"], "shopee": ["3044"]},
    "5159": {"ml": ["5159", "5159a"], "anuncios": ["MLB4564251491", "MLB6839450010"], "shopee": ["5159"]},
    "5245": {"ml": ["5245"], "anuncios": ["MLB6756962850"], "shopee": ["5245"]},
    "5338": {"ml": ["5338", "5338a"], "anuncios": ["MLB6527593792", "MLB4655278977"], "shopee": ["5338"]},
    "5601": {"ml": ["5601", "5601a"], "anuncios": ["MLB6526699676", "MLB4712498891"], "shopee": ["5601"]},
    "5699": {"ml": ["5699"], "anuncios": [], "shopee": []},
    "5702": {"ml": ["5702"], "anuncios": ["MLB4749590423"], "shopee": ["5702"]},
    "5801": {"ml": ["5801"], "anuncios": ["MLB4629269093"], "shopee": ["5801"]},
    "7224": {"ml": ["7224STD"], "anuncios": ["MLB6665531492"], "shopee": ["7224STD"]},
    "7224050": {"ml": ["7224050"], "anuncios": [], "shopee": ["7224050"]},
    "8126": {"ml": ["8126", "8126STD", "8126a"], "anuncios": ["MLB4672105869"], "shopee": ["8126STA"]},
    "1035": {"ml": ["1035j"], "anuncios": ["MLB4672045699"], "shopee": ["1035j"]},
}


def nome_para(sku_base: str) -> str:
    return NOMES_PRODUTOS.get(sku_base, f"Produto {sku_base}")


def iter_mapeamentos():
    """Gera tuplas (sku_canal, canal, id_anuncio, sku_base) para popular sku_map."""
    for sku_base, dados in DE_PARA.items():
        anuncios = dados.get("anuncios", [])
        for sku_canal in dados.get("ml", []):
            # Anexa um anúncio quando há exatamente um, senão deixa nulo.
            anuncio = anuncios[0] if len(anuncios) == 1 else None
            yield sku_canal, CANAL_ML, anuncio, sku_base
        for sku_canal in dados.get("shopee", []):
            yield sku_canal, CANAL_SHOPEE, None, sku_base
