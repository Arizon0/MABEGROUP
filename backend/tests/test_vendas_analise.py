"""Testes da análise venda-a-venda.

O teste âncora é ``test_reproduz_a_margem_da_referencia``: quatro pedidos com
os números exatos da ferramenta que o cliente usa hoje como referência. Se a
fórmula da margem, o rateio de Ads ou a alíquota mudarem de comportamento, é
esse teste que quebra primeiro.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.custos_venda import (
    ESCOPO_ANUNCIO,
    ESCOPO_CANAL,
    ESCOPO_SKU,
    AdsInvestimento,
    AliquotaImposto,
)
from app.models.venda import Venda
from app.parsers.common import CANAL_ML, CANAL_SHOPEE, STATUS_VALIDO
from app.services import vendas_analise as va

D = Decimal
ALIQUOTA_REFERENCIA = D("8.22")


def nova_venda(
    db,
    *,
    pedido: str,
    total="0",
    comissao="0",
    frete="0",
    cmv="0",
    canal=CANAL_ML,
    sku="5338",
    anuncio="MLB1",
    data=datetime(2026, 7, 31, 10, 0),
    descontos="0",
    cancelamentos="0",
    liquido=None,
    pacote=False,
    nf=None,
    titulo="Retentor",
    qtd="1",
    status=STATUS_VALIDO,
) -> Venda:
    """Cria uma linha de venda. ``comissao`` e ``frete`` entram como custo (−).

    Quando ``liquido`` não é informado, usa a identidade do canal
    (receita − comissão − frete + descontos + cancelamentos), que é o caso
    normal; passar um valor diferente serve para simular divergência.
    """
    tarifas = -D(comissao)
    frete_liq = -D(frete)
    if liquido is None:
        liquido = D(total) + tarifas + frete_liq + D(descontos) + D(cancelamentos)
    venda = Venda(
        canal=canal,
        id_pedido_canal=pedido,
        numero_nf=nf,
        data_venda=data,
        status_canal="Entregue",
        status_erp=status,
        sku_canal=sku or "",
        sku_base=sku,
        id_anuncio=anuncio,
        titulo=titulo,
        canal_logistico="ML Full",
        qtd=D(qtd),
        preco_unitario=D(total),
        custo_unitario=D(cmv),
        cmv=D(cmv),
        receita_bruta=D(total),
        tarifas_plataforma=tarifas,
        frete_liquido=frete_liq,
        descontos=D(descontos),
        cancelamentos=D(cancelamentos),
        liquido_recebido=D(liquido),
        is_pacote_multi=pacote,
    )
    db.add(venda)
    db.flush()
    return venda


def aliquota(db, ano=2026, mes=7, pct=ALIQUOTA_REFERENCIA):
    db.add(AliquotaImposto(ano=ano, mes=mes, aliquota_pct=D(str(pct))))
    db.flush()


def ads(db, valor, *, escopo=ESCOPO_ANUNCIO, referencia="MLB1", canal=CANAL_ML,
        ano=2026, mes=7, receita_ads=None):
    db.add(
        AdsInvestimento(
            canal=canal, ano=ano, mes=mes, escopo=escopo, referencia=referencia,
            valor=D(str(valor)),
            receita_ads=D(str(receita_ads)) if receita_ads is not None else None,
        )
    )
    db.flush()


def por_pedido(resultado: dict) -> dict[str, dict]:
    return {p["id_pedido_canal"]: p for p in resultado["pedidos"]}


# --------------------------------------------------------------------------- #
# O teste âncora                                                                #
# --------------------------------------------------------------------------- #

# (pedido, NF, total, custo, frete, comissão, ads, receita_ads,
#  imposto esperado, margem R$ esperada, margem % esperada)
REFERENCIA = [
    ("V1735", "1735", "33.87", "16.02", "7.95", "4.06", "8.79", None,
     "2.78", "-5.73", "-16.92"),
    ("V1725", "1725", "135.87", "76.02", "19.25", "16.30", "9.35", "89.13",
     "11.17", "3.78", "2.78"),
    ("V1734", "1734", "199.74", "103.50", "28.90", "23.96", "12.42", "139.86",
     "16.42", "14.54", "7.28"),
    ("V1730", "1730", "161.22", "72.54", "39.90", "18.54", "1.55", None,
     "13.25", "15.44", "9.58"),
]


@pytest.fixture()
def cenario_referencia(db):
    """Reproduz os quatro pedidos da ferramenta de referência."""
    aliquota(db)
    for i, (pedido, nf, total, custo, frete, comissao, gasto_ads,
            receita_ads, *_) in enumerate(REFERENCIA):
        anuncio = f"MLB{i}"
        nova_venda(
            db, pedido=pedido, nf=nf, total=total, cmv=custo, frete=frete,
            comissao=comissao, anuncio=anuncio, sku=f"SKU{i}",
        )
        ads(db, gasto_ads, referencia=anuncio, receita_ads=receita_ads)
    return db


class TestReferencia:
    def test_reproduz_a_margem_da_referencia(self, cenario_referencia):
        linhas = por_pedido(va.analisar(cenario_referencia))
        for pedido, _nf, total, custo, frete, comissao, gasto_ads, _r, \
                imposto, margem, margem_pct in REFERENCIA:
            linha = linhas[pedido]
            assert linha["total"] == total
            assert linha["custo"] == custo
            assert linha["frete"] == frete
            assert linha["comissao"] == comissao
            assert linha["ads"] == gasto_ads
            assert linha["imposto"] == imposto, f"imposto de {pedido}"
            assert linha["margem_valor"] == margem, f"margem R$ de {pedido}"
            assert linha["margem_pct"] == margem_pct, f"margem % de {pedido}"

    def test_tacos_e_ads_sobre_a_receita_total(self, cenario_referencia):
        linhas = por_pedido(va.analisar(cenario_referencia))
        # 8,79 de ads sobre 33,87 de receita = 25,95%.
        assert linhas["V1735"]["tacos_pct"] == "25.95"
        assert linhas["V1730"]["tacos_pct"] == "0.96"

    def test_acos_so_existe_quando_o_canal_atribui_receita(self, cenario_referencia):
        linhas = por_pedido(va.analisar(cenario_referencia))
        # Sem receita atribuída à publicidade o ACOS é indeterminado.
        assert linhas["V1735"]["acos_pct"] is None
        # Com ela, é o gasto sobre a receita que veio de anúncio.
        assert linhas["V1725"]["acos_pct"] == "10.49"
        assert linhas["V1734"]["acos_pct"] == "8.88"

    def test_a_nota_fiscal_importada_aparece_na_linha(self, cenario_referencia):
        assert por_pedido(va.analisar(cenario_referencia))["V1735"]["numero_nf"] == "1735"

    def test_o_resumo_soma_as_colunas_da_tela(self, cenario_referencia):
        resumo = va.analisar(cenario_referencia)["resumo"]
        assert resumo["pedidos"] == 4
        assert resumo["total"] == "530.70"          # 33.87+135.87+199.74+161.22
        assert resumo["custo"] == "268.08"
        assert resumo["ads"] == "32.11"
        assert resumo["imposto"] == "43.62"
        assert resumo["margem_valor"] == "28.03"    # -5.73+3.78+14.54+15.44
        assert resumo["negativos"] == 1
        assert resumo["pct_negativos"] == "25.00"


# --------------------------------------------------------------------------- #
# Imposto                                                                       #
# --------------------------------------------------------------------------- #


class TestImposto:
    def test_sem_aliquota_cadastrada_o_imposto_e_zero(self, db):
        nova_venda(db, pedido="A", total="100", cmv="40")
        linha = por_pedido(va.analisar(db))["A"]
        assert linha["imposto"] == "0.00"
        assert linha["aliquota_pct"] == "0"

    def test_usa_a_aliquota_da_competencia_da_venda(self, db):
        aliquota(db, ano=2026, mes=5, pct="6")
        aliquota(db, ano=2026, mes=7, pct="8.22")
        nova_venda(db, pedido="MAIO", total="100", data=datetime(2026, 5, 15))
        nova_venda(db, pedido="JULHO", total="100", data=datetime(2026, 7, 15))
        linhas = por_pedido(va.analisar(db))
        assert linhas["MAIO"]["imposto"] == "6.00"
        assert linhas["JULHO"]["imposto"] == "8.22"

    def test_alteracao_futura_nao_reescreve_competencia_passada(self, db):
        """Cadastrar agosto não pode mudar o imposto já apurado em maio."""
        aliquota(db, ano=2026, mes=5, pct="6")
        nova_venda(db, pedido="MAIO", total="100", data=datetime(2026, 5, 15))
        antes = por_pedido(va.analisar(db))["MAIO"]["imposto"]
        aliquota(db, ano=2026, mes=8, pct="15")
        assert por_pedido(va.analisar(db))["MAIO"]["imposto"] == antes == "6.00"

    def test_venda_anterior_a_primeira_vigencia_fica_sem_imposto(self, db):
        aliquota(db, ano=2026, mes=7, pct="8.22")
        nova_venda(db, pedido="ANTIGA", total="100", data=datetime(2026, 3, 1))
        assert por_pedido(va.analisar(db))["ANTIGA"]["imposto"] == "0.00"

    def test_aliquota_para_escolhe_a_mais_recente_nao_futura(self):
        vigencias = [(2026, 1, D("4")), (2026, 5, D("6")), (2026, 8, D("15"))]
        assert va.aliquota_para((2026, 7), vigencias) == D("6")
        assert va.aliquota_para((2026, 8), vigencias) == D("15")
        assert va.aliquota_para((2025, 12), vigencias) == D("0")
        assert va.aliquota_para(None, vigencias) == D("0")


# --------------------------------------------------------------------------- #
# Rateio de publicidade                                                         #
# --------------------------------------------------------------------------- #


class TestRateioAds:
    def test_rateia_proporcional_a_receita(self, db):
        nova_venda(db, pedido="GRANDE", total="300", anuncio="MLB1")
        nova_venda(db, pedido="PEQUENO", total="100", anuncio="MLB1")
        ads(db, "40", referencia="MLB1")
        linhas = por_pedido(va.analisar(db))
        assert linhas["GRANDE"]["ads"] == "30.00"   # 300/400 de 40
        assert linhas["PEQUENO"]["ads"] == "10.00"

    def test_a_soma_do_rateio_fecha_com_o_lancamento(self, db):
        """Três pedidos iguais e R$ 10: 3,33 três vezes deixaria 1 centavo fora."""
        for i in range(3):
            nova_venda(db, pedido=f"P{i}", total="100", anuncio="MLB1")
        ads(db, "10", referencia="MLB1")
        resultado = va.analisar(db)
        assert resultado["resumo"]["ads"] == "10.00"
        assert resultado["resumo"]["ads_nao_alocado"] == "0.00"

    def test_anuncio_tem_precedencia_sobre_sku_e_canal(self, db):
        nova_venda(db, pedido="A", total="100", anuncio="MLB1", sku="S1")
        ads(db, "10", escopo=ESCOPO_ANUNCIO, referencia="MLB1")
        ads(db, "99", escopo=ESCOPO_SKU, referencia="S1")
        ads(db, "999", escopo=ESCOPO_CANAL, referencia="")
        assert por_pedido(va.analisar(db))["A"]["ads"] == "10.00"

    def test_sku_tem_precedencia_sobre_canal(self, db):
        nova_venda(db, pedido="A", total="100", anuncio="MLB1", sku="S1")
        ads(db, "20", escopo=ESCOPO_SKU, referencia="S1")
        ads(db, "999", escopo=ESCOPO_CANAL, referencia="")
        assert por_pedido(va.analisar(db))["A"]["ads"] == "20.00"

    def test_lancamento_de_canal_cobre_o_que_sobrou(self, db):
        nova_venda(db, pedido="COM_ANUNCIO", total="100", anuncio="MLB1", sku="S1")
        nova_venda(db, pedido="SEM_ANUNCIO", total="100", anuncio="MLB9", sku="S9")
        ads(db, "10", escopo=ESCOPO_ANUNCIO, referencia="MLB1")
        ads(db, "50", escopo=ESCOPO_CANAL, referencia="")
        linhas = por_pedido(va.analisar(db))
        assert linhas["COM_ANUNCIO"]["ads"] == "10.00"
        # O pedido já coberto pelo anúncio não recebe verba do canal de novo.
        assert linhas["SEM_ANUNCIO"]["ads"] == "50.00"

    def test_lancamento_de_outra_competencia_nao_vaza(self, db):
        nova_venda(db, pedido="A", total="100", anuncio="MLB1",
                   data=datetime(2026, 7, 10))
        ads(db, "10", referencia="MLB1", ano=2026, mes=6)
        resultado = va.analisar(db)
        assert por_pedido(resultado)["A"]["ads"] == "0.00"
        assert resultado["resumo"]["ads_nao_alocado"] == "10.00"

    def test_lancamento_de_outro_canal_nao_vaza(self, db):
        nova_venda(db, pedido="A", total="100", canal=CANAL_SHOPEE, anuncio="MLB1")
        ads(db, "10", referencia="MLB1", canal=CANAL_ML)
        assert por_pedido(va.analisar(db))["A"]["ads"] == "0.00"

    def test_anuncio_sem_venda_no_mes_vira_nao_alocado(self, db):
        nova_venda(db, pedido="A", total="100", anuncio="MLB1")
        ads(db, "10", referencia="MLB1")
        ads(db, "7", referencia="MLB_QUE_NAO_VENDEU")
        resultado = va.analisar(db)
        assert resultado["resumo"]["ads"] == "10.00"
        assert resultado["resumo"]["ads_nao_alocado"] == "7.00"

    def test_bucket_com_receita_zero_nao_divide_por_zero(self, db):
        nova_venda(db, pedido="A", total="0", anuncio="MLB1")
        ads(db, "10", referencia="MLB1")
        resultado = va.analisar(db)
        assert por_pedido(resultado)["A"]["ads"] == "0.00"
        assert resultado["resumo"]["ads_nao_alocado"] == "10.00"


# --------------------------------------------------------------------------- #
# Consolidação de pedidos                                                       #
# --------------------------------------------------------------------------- #


class TestConsolidacao:
    def test_pacote_multi_vira_um_pedido_so(self, db):
        """Resumo (dinheiro, sem SKU) + componentes (SKU e CMV, sem dinheiro)."""
        nova_venda(db, pedido="PAC", total="200", comissao="30", frete="10",
                   cmv="0", sku=None, anuncio=None, pacote=True,
                   titulo="Pacote de 2 produtos")
        nova_venda(db, pedido="PAC", total="0", cmv="60", sku="5245",
                   anuncio="MLB2", pacote=True, titulo="Retentor Palio",
                   liquido="0")
        nova_venda(db, pedido="PAC", total="0", cmv="25", sku="5699",
                   anuncio="MLB3", pacote=True, titulo="Retentor Liso",
                   liquido="0")
        resultado = va.analisar(db)
        assert resultado["resumo"]["pedidos"] == 1
        linha = resultado["pedidos"][0]
        assert linha["linhas"] == 3
        assert linha["is_pacote_multi"] is True
        assert linha["total"] == "200.00"
        assert linha["custo"] == "85.00"            # 60 + 25
        assert sorted(linha["skus"]) == ["5245", "5699"]
        # líquido 160 − CMV 85 = 75 de margem (sem ads nem imposto).
        assert linha["margem_valor"] == "75.00"

    def test_o_titulo_do_componente_vence_o_generico_do_pacote(self, db):
        nova_venda(db, pedido="PAC", total="200", sku=None, anuncio=None,
                   pacote=True, titulo="Pacote de 2 produtos")
        nova_venda(db, pedido="PAC", total="0", cmv="60", sku="5245",
                   pacote=True, titulo="Retentor Palio", liquido="0")
        assert va.analisar(db)["pedidos"][0]["titulo"] == "Retentor Palio"

    def test_mesmo_id_em_canais_diferentes_sao_pedidos_distintos(self, db):
        nova_venda(db, pedido="123", total="100", canal=CANAL_ML)
        nova_venda(db, pedido="123", total="200", canal=CANAL_SHOPEE)
        assert va.analisar(db)["resumo"]["pedidos"] == 2

    def test_canceladas_ficam_de_fora_por_padrao(self, db):
        nova_venda(db, pedido="OK", total="100")
        nova_venda(db, pedido="CANC", total="100", status="Cancelado")
        assert va.analisar(db)["resumo"]["pedidos"] == 1
        assert va.analisar(db, apenas_validas=False)["resumo"]["pedidos"] == 2


# --------------------------------------------------------------------------- #
# Recortes                                                                      #
# --------------------------------------------------------------------------- #


class TestRecortes:
    @pytest.fixture()
    def cenario(self, db):
        aliquota(db)
        # Prejuízo: custo alto demais.
        nova_venda(db, pedido="NEG", total="100", cmv="90", comissao="15",
                   frete="10", sku="S1", anuncio="MLB1")
        # Saudável.
        nova_venda(db, pedido="BOM", total="200", cmv="60", comissao="20",
                   frete="10", sku="S2", anuncio="MLB2")
        # Produto sem custo cadastrado.
        nova_venda(db, pedido="SEMCUSTO", total="150", cmv="0", comissao="15",
                   frete="10", sku="S3", anuncio="MLB3")
        # Sem comissão e sem frete.
        nova_venda(db, pedido="SEMTAXA", total="120", cmv="50", comissao="0",
                   frete="0", sku="S4", anuncio="MLB4")
        # Pacote.
        nova_venda(db, pedido="PAC", total="180", cmv="70", comissao="18",
                   frete="9", sku="S5", anuncio="MLB5", pacote=True)
        # Líquido informado pelo canal não bate com a soma dos componentes.
        nova_venda(db, pedido="DIVERG", total="100", cmv="40", comissao="10",
                   frete="5", sku="S6", anuncio="MLB6", liquido="70")
        return db

    def _ids(self, db, recorte):
        return set(por_pedido(va.analisar(db, recorte=recorte)))

    def test_todos(self, cenario):
        assert len(self._ids(cenario, va.RECORTE_TODOS)) == 6

    def test_negativos(self, cenario):
        assert self._ids(cenario, va.RECORTE_NEGATIVOS) == {"NEG"}

    def test_sem_custo(self, cenario):
        assert self._ids(cenario, va.RECORTE_SEM_CUSTO) == {"SEMCUSTO"}

    def test_sem_comissao(self, cenario):
        assert self._ids(cenario, va.RECORTE_SEM_COMISSAO) == {"SEMTAXA"}

    def test_sem_frete(self, cenario):
        assert self._ids(cenario, va.RECORTE_SEM_FRETE) == {"SEMTAXA"}

    def test_pacotes(self, cenario):
        assert self._ids(cenario, va.RECORTE_PACOTES) == {"PAC"}

    def test_revisar_junta_todos_os_alertas(self, cenario):
        assert self._ids(cenario, va.RECORTE_REVISAR) == {
            "SEMCUSTO", "SEMTAXA", "DIVERG",
        }

    def test_o_alerta_diz_qual_e_o_problema(self, cenario):
        linhas = por_pedido(va.analisar(cenario))
        assert linhas["DIVERG"]["alertas"] == [va.ALERTA_RECEBER_NAO_BATE]
        assert linhas["DIVERG"]["diferenca_liquido"] == "15.00"  # 85 − 70
        assert va.ALERTA_SEM_CUSTO in linhas["SEMCUSTO"]["alertas"]
        assert va.ALERTA_SEM_COMISSAO in linhas["SEMTAXA"]["alertas"]
        assert linhas["BOM"]["alertas"] == []

    def test_contagem_por_recorte_vem_junto(self, cenario):
        contagem = va.analisar(cenario)["contagem_por_recorte"]
        assert contagem[va.RECORTE_TODOS] == 6
        assert contagem[va.RECORTE_NEGATIVOS] == 1
        assert contagem[va.RECORTE_REVISAR] == 3
        # A contagem não muda quando um recorte está aplicado.
        assert va.analisar(cenario, recorte=va.RECORTE_NEGATIVOS)[
            "contagem_por_recorte"
        ] == contagem

    def test_recorte_desconhecido_cai_em_todos(self, cenario):
        assert va.analisar(cenario, recorte="inventado")["resumo"]["pedidos"] == 6

    def test_pedido_sem_sku_e_marcado(self, db):
        nova_venda(db, pedido="A", total="100", comissao="10", cmv="0", sku=None)
        alertas = por_pedido(va.analisar(db))["A"]["alertas"]
        assert va.ALERTA_SEM_SKU in alertas


# --------------------------------------------------------------------------- #
# Ordenação, busca e paginação                                                  #
# --------------------------------------------------------------------------- #


class TestOrdenacao:
    @pytest.fixture()
    def cenario(self, db):
        nova_venda(db, pedido="P1", total="100", cmv="90", comissao="20",
                   frete="5", data=datetime(2026, 7, 1))    # margem −15
        nova_venda(db, pedido="P2", total="500", cmv="100", comissao="50",
                   frete="40", data=datetime(2026, 7, 2))   # margem +310
        nova_venda(db, pedido="P3", total="200", cmv="150", comissao="20",
                   frete="60", data=datetime(2026, 7, 3))   # margem −30
        return db

    def _ordem(self, db, ordem):
        return [p["id_pedido_canal"] for p in va.analisar(db, ordem=ordem)["pedidos"]]

    def test_pior_margem_em_reais(self, cenario):
        assert self._ordem(cenario, va.ORDEM_PIOR_MARGEM_VALOR) == ["P3", "P1", "P2"]

    def test_melhor_margem_em_reais(self, cenario):
        assert self._ordem(cenario, va.ORDEM_MELHOR_MARGEM_VALOR) == ["P2", "P1", "P3"]

    def test_pior_margem_percentual(self, cenario):
        # P1 −15% ; P3 −15% ; P2 +62% → os dois negativos vêm primeiro.
        assert self._ordem(cenario, va.ORDEM_PIOR_MARGEM_PCT)[-1] == "P2"

    def test_melhor_margem_percentual(self, cenario):
        assert self._ordem(cenario, va.ORDEM_MELHOR_MARGEM_PCT)[0] == "P2"

    def test_maior_venda(self, cenario):
        assert self._ordem(cenario, va.ORDEM_MAIOR_VENDA) == ["P2", "P3", "P1"]

    def test_maior_frete(self, cenario):
        assert self._ordem(cenario, va.ORDEM_MAIOR_FRETE) == ["P3", "P2", "P1"]

    def test_data_mais_recente_primeiro(self, cenario):
        assert self._ordem(cenario, va.ORDEM_DATA) == ["P3", "P2", "P1"]

    def test_pedido_sem_receita_nao_encabeca_pior_margem_pct(self, db):
        """Sem receita não há percentual — não pode empurrar o prejuízo real."""
        nova_venda(db, pedido="PREJUIZO", total="100", cmv="150")
        nova_venda(db, pedido="SEM_RECEITA", total="0", cmv="0", liquido="0")
        ordem = [p["id_pedido_canal"] for p in
                 va.analisar(db, ordem=va.ORDEM_PIOR_MARGEM_PCT)["pedidos"]]
        assert ordem == ["PREJUIZO", "SEM_RECEITA"]
        assert por_pedido(va.analisar(db))["SEM_RECEITA"]["margem_pct"] is None


class TestBuscaEPaginacao:
    @pytest.fixture()
    def cenario(self, db):
        for i in range(1, 13):
            nova_venda(
                db, pedido=f"P{i:02d}", total="100", cmv="40",
                sku=f"SKU{i}", nf=f"NF{i}", titulo=f"Retentor {i}",
                data=datetime(2026, 7, i),
            )
        return db

    def test_pagina_recorta_a_janela(self, cenario):
        pagina = va.analisar(cenario, tamanho=5, pagina=1)
        assert len(pagina["pedidos"]) == 5
        assert pagina["paginacao"] == {
            "pagina": 1, "tamanho": 5, "total": 12, "paginas": 3, "de": 1, "ate": 5,
        }

    def test_ultima_pagina_parcial(self, cenario):
        pagina = va.analisar(cenario, tamanho=5, pagina=3)
        assert len(pagina["pedidos"]) == 2
        assert pagina["paginacao"]["de"] == 11
        assert pagina["paginacao"]["ate"] == 12

    def test_pagina_alem_do_fim_vem_vazia(self, cenario):
        pagina = va.analisar(cenario, tamanho=5, pagina=99)
        assert pagina["pedidos"] == []
        assert pagina["paginacao"]["de"] == 0

    def test_resumo_cobre_o_conjunto_inteiro_nao_so_a_pagina(self, cenario):
        pagina = va.analisar(cenario, tamanho=5)
        assert pagina["resumo"]["pedidos"] == 12
        assert pagina["resumo"]["total"] == "1200.00"

    def test_busca_por_sku(self, cenario):
        assert set(por_pedido(va.analisar(cenario, busca="SKU12"))) == {"P12"}

    def test_busca_por_nota_fiscal(self, cenario):
        assert set(por_pedido(va.analisar(cenario, busca="NF7"))) == {"P07"}

    def test_busca_ignora_caixa(self, cenario):
        assert set(por_pedido(va.analisar(cenario, busca="retentor 3"))) == {"P03"}


class TestPeriodoECanal:
    @pytest.fixture()
    def cenario(self, db):
        nova_venda(db, pedido="JUN", total="100", data=datetime(2026, 6, 15))
        nova_venda(db, pedido="JUL", total="100", data=datetime(2026, 7, 15))
        nova_venda(db, pedido="SHP", total="100", canal=CANAL_SHOPEE,
                   data=datetime(2026, 7, 20))
        return db

    def test_filtra_por_periodo(self, cenario):
        resultado = va.analisar(
            cenario, data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 31)
        )
        assert set(por_pedido(resultado)) == {"JUL", "SHP"}

    def test_o_ultimo_dia_do_periodo_entra_inteiro(self, db):
        nova_venda(db, pedido="TARDE", total="100",
                   data=datetime(2026, 7, 31, 23, 59, 30))
        resultado = va.analisar(db, data_fim=date(2026, 7, 31))
        assert set(por_pedido(resultado)) == {"TARDE"}

    def test_filtra_por_canal(self, cenario):
        assert set(por_pedido(va.analisar(cenario, canal=CANAL_SHOPEE))) == {"SHP"}


# --------------------------------------------------------------------------- #
# Endpoints                                                                     #
# --------------------------------------------------------------------------- #


class TestEndpoints:
    def test_analise_responde_a_tela_inteira(self, client, cenario_referencia):
        resp = client.get("/api/vendas/analise", params={"tamanho": 2})
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["resumo"]["pedidos"] == 4
        assert len(corpo["pedidos"]) == 2
        assert corpo["paginacao"]["paginas"] == 2
        assert set(corpo["contagem_por_recorte"]) == set(va.RECORTES)

    def test_analise_aceita_recorte_e_ordem(self, client, cenario_referencia):
        resp = client.get(
            "/api/vendas/analise",
            params={"recorte": va.RECORTE_NEGATIVOS, "ordem": va.ORDEM_PIOR_MARGEM_VALOR},
        )
        assert [p["id_pedido_canal"] for p in resp.json()["pedidos"]] == ["V1735"]

    def test_opcoes_lista_o_que_a_tela_pode_pedir(self, client):
        corpo = client.get("/api/vendas/analise/opcoes").json()
        assert corpo["recortes"] == list(va.RECORTES)
        assert corpo["ordenacoes"] == list(va.ORDENACOES)

    def test_tamanho_de_pagina_absurdo_e_rejeitado(self, client):
        assert client.get("/api/vendas/analise", params={"tamanho": 10_000}).status_code == 422

    def test_ciclo_de_vida_da_aliquota(self, client):
        criada = client.put(
            "/api/vendas/aliquotas",
            json={"ano": 2026, "mes": 7, "aliquota_pct": "8.22"},
        )
        assert criada.status_code == 200
        assert criada.json()["aliquota_pct"] == "8.2200"

        # Regravar a mesma competência atualiza em vez de duplicar.
        client.put(
            "/api/vendas/aliquotas",
            json={"ano": 2026, "mes": 7, "aliquota_pct": "9"},
        )
        listagem = client.get("/api/vendas/aliquotas").json()
        assert len(listagem) == 1
        assert listagem[0]["aliquota_pct"] == "9.0000"

        assert client.delete(f"/api/vendas/aliquotas/{listagem[0]['id']}").status_code == 204
        assert client.get("/api/vendas/aliquotas").json() == []

    def test_aliquota_fora_de_faixa_e_rejeitada(self, client):
        resp = client.put(
            "/api/vendas/aliquotas",
            json={"ano": 2026, "mes": 7, "aliquota_pct": "150"},
        )
        assert resp.status_code == 422

    def test_ciclo_de_vida_do_lancamento_de_ads(self, client):
        criado = client.put(
            "/api/vendas/ads",
            json={
                "canal": CANAL_ML, "ano": 2026, "mes": 7,
                "escopo": ESCOPO_ANUNCIO, "referencia": "MLB1",
                "valor": "120.50", "receita_ads": "1000",
            },
        )
        assert criado.status_code == 200
        ads_id = criado.json()["id"]

        assert len(client.get("/api/vendas/ads", params={"ano": 2026, "mes": 7}).json()) == 1
        assert client.get("/api/vendas/ads", params={"mes": 6}).json() == []

        assert client.delete(f"/api/vendas/ads/{ads_id}").status_code == 204
        assert client.delete(f"/api/vendas/ads/{ads_id}").status_code == 404

    def test_escopo_invalido_de_ads_e_rejeitado(self, client):
        resp = client.put(
            "/api/vendas/ads",
            json={"canal": CANAL_ML, "ano": 2026, "mes": 7,
                  "escopo": "galaxia", "valor": "10"},
        )
        assert resp.status_code == 422

    def test_gravar_nf_alcanca_todas_as_linhas_do_pacote(self, client, db):
        nova_venda(db, pedido="PAC", total="200", sku=None, pacote=True)
        nova_venda(db, pedido="PAC", total="0", cmv="60", sku="5245",
                   pacote=True, liquido="0")
        resp = client.put(
            "/api/vendas/nf",
            json={"canal": CANAL_ML, "id_pedido_canal": "PAC", "numero_nf": " 4321 "},
        )
        assert resp.status_code == 200
        assert resp.json()["linhas_atualizadas"] == 2
        assert por_pedido(va.analisar(db))["PAC"]["numero_nf"] == "4321"

    def test_gravar_nf_de_pedido_inexistente_da_404(self, client):
        resp = client.put(
            "/api/vendas/nf",
            json={"canal": CANAL_ML, "id_pedido_canal": "NAO_EXISTE", "numero_nf": "1"},
        )
        assert resp.status_code == 404

    def test_export_excel(self, client, cenario_referencia):
        resp = client.get("/api/vendas/analise/export", params={"formato": "excel"})
        assert resp.status_code == 200
        assert resp.content[:2] == b"PK"  # xlsx é um zip
        assert "analise-vendas.xlsx" in resp.headers["content-disposition"]

    def test_export_pdf(self, client, cenario_referencia):
        resp = client.get("/api/vendas/analise/export", params={"formato": "pdf"})
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"

    def test_formato_de_export_invalido_e_rejeitado(self, client):
        assert client.get(
            "/api/vendas/analise/export", params={"formato": "csv"}
        ).status_code == 422
