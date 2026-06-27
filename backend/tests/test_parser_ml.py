"""Testes do parser do Mercado Livre (incluindo armadilhas)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.parsers.common import (
    STATUS_CANCELADO,
    STATUS_DEVOLUCAO,
    STATUS_VALIDO,
)
from app.parsers.mercadolivre import (
    classificar_canal_logistico,
    classificar_status,
    detectar_header_ml,
    parse_ml,
)
from app.services.totais import calcular_totais
from tests.factories import build_ml_xlsx


@pytest.fixture()
def ml_file(tmp_path):
    return build_ml_xlsx(tmp_path / "ml.xlsx")


def test_detecta_header_com_metadados(tmp_path):
    _, esperado = build_ml_xlsx(tmp_path / "ml.xlsx", leading_meta=6)
    assert detectar_header_ml(tmp_path / "ml.xlsx") == esperado["header_index"] == 6


def test_detecta_header_sem_metadados(tmp_path):
    build_ml_xlsx(tmp_path / "ml0.xlsx", leading_meta=0)
    assert detectar_header_ml(tmp_path / "ml0.xlsx") == 0


def test_header_ausente_levanta_erro(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["coluna qualquer", "outra"])
    wb.save(tmp_path / "ruim.xlsx")
    with pytest.raises(ValueError):
        detectar_header_ml(tmp_path / "ruim.xlsx")


def test_totais_batem_com_esperado(ml_file):
    path, esperado = ml_file
    dtos = parse_ml(path)
    assert len(dtos) == esperado["dtos"]

    t = calcular_totais(dtos)
    assert t.linhas == esperado["linhas"]
    assert t.unidades == esperado["unidades"]
    assert t.receita_bruta == esperado["receita_bruta"]
    assert t.tarifas_plataforma == esperado["tarifas_plataforma"]
    assert t.frete_liquido == esperado["frete_liquido"]
    assert t.descontos == esperado["descontos"]
    assert t.cancelamentos == esperado["cancelamentos"]
    assert t.liquido_recebido == esperado["liquido_recebido"]


def test_valores_sao_decimal(ml_file):
    path, _ = ml_file
    for dto in parse_ml(path):
        assert isinstance(dto.liquido_recebido, Decimal)
        assert isinstance(dto.receita_bruta, Decimal)
        assert isinstance(dto.qtd, Decimal)


def test_pacote_multi_resumo_e_componentes(ml_file):
    path, _ = ml_file
    dtos = parse_ml(path)
    por_pedido = [d for d in dtos if d.id_pedido_canal == "V3"]
    # 1 resumo + 2 componentes
    assert len(por_pedido) == 3

    resumo = [d for d in por_pedido if d.sku_canal == ""][0]
    assert resumo.is_pacote_multi is True
    assert resumo.liquido_recebido == Decimal("165")
    assert resumo.receita_bruta == Decimal("200")
    assert resumo.qtd == Decimal("0")

    componentes = [d for d in por_pedido if d.sku_canal != ""]
    skus = sorted(d.sku_canal for d in componentes)
    assert skus == ["5245", "5699"]
    for comp in componentes:
        assert comp.is_pacote_multi is True
        # componentes não carregam dinheiro (evita dupla contagem)
        assert comp.liquido_recebido == Decimal("0")
        assert comp.receita_bruta == Decimal("0")
    # unidades preservadas para baixa de estoque
    assert {d.sku_canal: d.qtd for d in componentes} == {
        "5245": Decimal("3"),
        "5699": Decimal("1"),
    }


def test_status_e_canal_logistico(ml_file):
    path, _ = ml_file
    by_first: dict = {}
    for d in parse_ml(path):
        by_first.setdefault(d.id_pedido_canal, d)

    assert by_first["V1"].status_erp == STATUS_VALIDO
    assert by_first["V1"].canal_logistico == "ML Full"
    assert by_first["V1"].tipo_anuncio == "Premium"

    assert by_first["V2"].status_erp == STATUS_CANCELADO
    assert by_first["V2"].canal_logistico == "ML Flex"

    assert by_first["V4"].status_erp == STATUS_DEVOLUCAO


def test_classificar_status():
    assert classificar_status("Entregue") == STATUS_VALIDO
    assert classificar_status("Cancelada") == STATUS_CANCELADO
    assert classificar_status("Devolução a caminho") == STATUS_DEVOLUCAO
    assert classificar_status("Devolução finalizada com reembolso") == STATUS_DEVOLUCAO


def test_classificar_canal_logistico():
    assert classificar_canal_logistico("Mercado Envios Full") == "ML Full"
    assert classificar_canal_logistico("Mercado Envios Flex") == "ML Flex"
    assert classificar_canal_logistico("Correios") == "ML Agência/Correios"
    assert classificar_canal_logistico("") == ""
