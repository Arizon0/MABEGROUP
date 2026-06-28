"""Testes do serviço/endpoints de Estoque Multi-local (Prioridade 3)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.estoque import LOCAL_FULFILLMENT, LOCAL_GALPAO, Local
from app.models.produto import Produto
from app.seed import seed_locais
from app.services import estoque as svc


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def produto(db):
    p = Produto(sku_base="5338", nome="Retentor", estoque_minimo=Decimal("10"))
    db.add(p)
    db.flush()
    return p


@pytest.fixture()
def galpao(db):
    l = Local(nome="Galpão Central", tipo=LOCAL_GALPAO)
    db.add(l)
    db.flush()
    return l


# --------------------------------------------------------------------------- #
# Custo médio ponderado                                                         #
# --------------------------------------------------------------------------- #


def test_custo_medio_ponderado(db, produto, galpao):
    # Entrada 1: 10 un a R$ 5,00
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("10"),
        custo_unitario=Decimal("5.00"),
    )
    # Entrada 2: 10 un a R$ 7,00 -> média ponderada = 6,00
    saldo = svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("10"),
        custo_unitario=Decimal("7.00"),
    )
    assert saldo.qtd_disponivel == Decimal("20")
    assert saldo.custo_medio == Decimal("6.0000")


def test_saida_nao_altera_custo_medio(db, produto, galpao):
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("10"),
        custo_unitario=Decimal("5.00"),
    )
    saldo = svc.registrar_saida(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("3")
    )
    assert saldo.qtd_disponivel == Decimal("7")
    assert saldo.custo_medio == Decimal("5.0000")


def test_saida_insuficiente_bloqueia(db, produto, galpao):
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("2"),
        custo_unitario=Decimal("5"),
    )
    with pytest.raises(HTTPException) as exc:
        svc.registrar_saida(db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("5"))
    assert exc.value.status_code == 422


def test_saida_permitir_negativo(db, produto, galpao):
    saldo = svc.registrar_saida(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("5"),
        permitir_negativo=True,
    )
    assert saldo.qtd_disponivel == Decimal("-5")


# --------------------------------------------------------------------------- #
# Reservas                                                                       #
# --------------------------------------------------------------------------- #


def test_reserva_move_disponivel_para_reservada(db, produto, galpao):
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("10"),
        custo_unitario=Decimal("5"),
    )
    saldo = svc.reservar(db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("4"))
    assert saldo.qtd_disponivel == Decimal("6")
    assert saldo.qtd_reservada == Decimal("4")

    saldo = svc.liberar_reserva(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("4")
    )
    assert saldo.qtd_disponivel == Decimal("10")
    assert saldo.qtd_reservada == Decimal("0")


def test_reserva_sem_disponivel_bloqueia(db, produto, galpao):
    with pytest.raises(HTTPException) as exc:
        svc.reservar(db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("1"))
    assert exc.value.status_code == 422


# --------------------------------------------------------------------------- #
# Alertas e relatórios                                                          #
# --------------------------------------------------------------------------- #


def test_alerta_quando_abaixo_do_minimo(db, produto, galpao):
    # estoque_minimo = 10; coloca 8 disponível -> alerta
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("8"),
        custo_unitario=Decimal("5"),
    )
    alertas = svc.alertas_estoque(db)
    assert len(alertas) == 1
    assert alertas[0].sku_base == "5338"
    assert alertas[0].disponivel_total == Decimal("8")

    # repõe acima do mínimo -> sem alerta
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("5"),
        custo_unitario=Decimal("5"),
    )
    assert svc.alertas_estoque(db) == []


def test_valor_total_estoque(db, produto, galpao):
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=galpao.id, qtd=Decimal("10"),
        custo_unitario=Decimal("5.50"),
    )
    assert svc.valor_total_estoque(db) == Decimal("55.00")


# --------------------------------------------------------------------------- #
# Mapeamento canal logístico -> local + baixa por venda                         #
# --------------------------------------------------------------------------- #


def test_ml_full_baixa_no_fulfillment(db, produto):
    seed_locais(db)
    fulfillment = db.query(Local).filter(Local.tipo == LOCAL_FULFILLMENT).one()
    galpao = db.query(Local).filter(Local.tipo == LOCAL_GALPAO).one()
    svc.registrar_entrada(
        db, produto_id=produto.id, local_id=fulfillment.id, qtd=Decimal("20"),
        custo_unitario=Decimal("5"),
    )

    saldo = svc.baixar_estoque_venda(
        db, produto_id=produto.id, canal_logistico="ML Full", qtd=Decimal("3"),
    )
    assert saldo.local_id == fulfillment.id
    assert saldo.qtd_disponivel == Decimal("17")

    # canal não-Full vai para o galpão
    saldo2 = svc.baixar_estoque_venda(
        db, produto_id=produto.id, canal_logistico="ML Flex", qtd=Decimal("1"),
    )
    assert saldo2.local_id == galpao.id
    assert saldo2.qtd_disponivel == Decimal("-1")  # permite negativo (histórico)


# --------------------------------------------------------------------------- #
# Endpoints                                                                      #
# --------------------------------------------------------------------------- #


def test_endpoint_movimento_e_saldo(client, db, produto, galpao):
    r = client.post(
        "/api/estoque/movimentos",
        json={
            "produto_id": produto.id, "local_id": galpao.id,
            "tipo": "entrada", "qtd": "10", "custo_unitario": "5.00",
        },
    )
    assert r.status_code == 201, r.text

    saldos = client.get("/api/estoque").json()
    assert len(saldos) == 1
    assert saldos[0]["qtd_disponivel"] == "10.000"
    assert saldos[0]["valor_total"] == "50.00"
    assert saldos[0]["local_nome"] == "Galpão Central"


def test_endpoint_relatorio(client, db, produto, galpao):
    client.post(
        "/api/estoque/movimentos",
        json={"produto_id": produto.id, "local_id": galpao.id,
              "tipo": "entrada", "qtd": "8", "custo_unitario": "5.00"},
    )
    rel = client.get("/api/estoque/relatorio").json()
    assert rel["valor_total_estoque"] == "40.00"
    assert rel["total_alertas"] == 1  # 8 <= minimo 10
    assert rel["alertas"][0]["sku_base"] == "5338"


# --------------------------------------------------------------------------- #
# Integração importação -> baixa de estoque                                     #
# --------------------------------------------------------------------------- #


def test_importacao_baixa_estoque(db, tmp_path):
    from app.parsers.common import CANAL_ML
    from app.parsers.mercadolivre import parse_ml
    from app.seed import seed_locais, seed_sku_map
    from app.services.importacao import importar_vendas
    from tests.factories import build_ml_xlsx

    seed_sku_map(db)  # cria produtos (5338, 5245, 5699, 8126...)
    seed_locais(db)   # Galpão Central, ML Fulfillment, Escritório
    path, _ = build_ml_xlsx(tmp_path / "ml.xlsx")

    resultado = importar_vendas(db, parse_ml(path), CANAL_ML, baixar_estoque=True)
    db.commit()

    # Válidas com sku resolvido e qtd>0: V1 (5338), V3a (5245), V3b (5699) = 3
    # (V2 cancelada, V4 devolução, V3-resumo sem sku, V5 sem sku -> não baixam)
    assert resultado.baixas_estoque == 3

    # V1 é ML Full -> baixou no Fulfillment
    from app.models.estoque import EstoqueSaldo

    fulfillment = db.query(Local).filter(Local.tipo == LOCAL_FULFILLMENT).one()
    p5338 = db.query(Produto).filter(Produto.sku_base == "5338").one()
    saldo_5338 = (
        db.query(EstoqueSaldo)
        .filter(
            EstoqueSaldo.produto_id == p5338.id,
            EstoqueSaldo.local_id == fulfillment.id,
        )
        .one()
    )
    assert saldo_5338.qtd_disponivel == Decimal("-2")  # 2 unidades baixadas, sem entrada
