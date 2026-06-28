"""Testes de Pedidos de Compra (Prioridade 4)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.estoque import LOCAL_GALPAO, EstoqueSaldo, Local
from app.models.financeiro import ContaPagar
from app.models.fornecedor import Fornecedor
from app.models.produto import Produto
from app.models.venda import Venda
from app.services import compras as svc
from app.services import estoque as estoque_svc


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def fornecedor(db):
    f = Fornecedor(
        cnpj="11222333000181", razao_social="Fornecedor X",
        condicoes_pagamento_dias=30,
    )
    db.add(f)
    db.flush()
    return f


@pytest.fixture()
def produtos(db):
    ps = [
        Produto(sku_base="5338", nome="Retentor", estoque_minimo=Decimal("10")),
        Produto(sku_base="8126", nome="Anel", estoque_minimo=Decimal("0")),
    ]
    db.add_all(ps)
    db.flush()
    return ps


@pytest.fixture()
def galpao(db):
    l = Local(nome="Galpão Central", tipo=LOCAL_GALPAO)
    db.add(l)
    db.flush()
    return l


def _criar(client, fornecedor, produtos):
    return client.post(
        "/api/compras",
        json={
            "fornecedor_id": fornecedor.id,
            "itens": [
                {"produto_id": produtos[0].id, "qtd": "10", "custo_unitario": "5.00"},
                {"produto_id": produtos[1].id, "qtd": "4", "custo_unitario": "12.50"},
            ],
        },
    )


def test_criar_pedido_calcula_total(client, fornecedor, produtos):
    resp = _criar(client, fornecedor, produtos)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "rascunho"
    # 10*5 + 4*12.5 = 100
    assert Decimal(body["total"]) == Decimal("100.00")
    assert len(body["itens"]) == 2
    assert Decimal(body["itens"][0]["subtotal"]) == Decimal("50.00")


def test_aprovar_gera_conta_a_pagar(client, db, fornecedor, produtos):
    pedido = _criar(client, fornecedor, produtos).json()
    resp = client.post(f"/api/compras/{pedido['id']}/aprovar")
    assert resp.status_code == 200
    assert resp.json()["status"] == "aprovado"

    contas = db.query(ContaPagar).all()
    assert len(contas) == 1
    assert contas[0].valor == Decimal("100.00")
    assert contas[0].pedido_compra_id == pedido["id"]
    assert contas[0].status == "aberto"
    # vencimento = hoje + 30 dias (condições do fornecedor)
    assert contas[0].vencimento == date.today() + timedelta(days=30)


def test_receber_incrementa_estoque_com_custo_medio(client, db, fornecedor, produtos, galpao):
    pedido = _criar(client, fornecedor, produtos).json()
    client.post(f"/api/compras/{pedido['id']}/aprovar")
    resp = client.post(f"/api/compras/{pedido['id']}/receber", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "recebido"

    saldo = (
        db.query(EstoqueSaldo)
        .filter(EstoqueSaldo.produto_id == produtos[0].id, EstoqueSaldo.local_id == galpao.id)
        .one()
    )
    assert saldo.qtd_disponivel == Decimal("10")
    assert saldo.custo_medio == Decimal("5.0000")


def test_fluxo_invalido(client, fornecedor, produtos, galpao):
    pedido = _criar(client, fornecedor, produtos).json()
    # receber sem aprovar
    assert client.post(f"/api/compras/{pedido['id']}/receber", json={}).status_code == 422
    # aprovar duas vezes
    client.post(f"/api/compras/{pedido['id']}/aprovar")
    assert client.post(f"/api/compras/{pedido['id']}/aprovar").status_code == 422


def test_pedido_sem_itens_rejeitado(client, fornecedor):
    resp = client.post(
        "/api/compras", json={"fornecedor_id": fornecedor.id, "itens": []}
    )
    assert resp.status_code == 422


def test_nf_anexo(client, fornecedor, produtos, tmp_path, monkeypatch):
    import app.services.anexos as anexos_mod

    monkeypatch.setattr(anexos_mod, "UPLOAD_DIR", str(tmp_path))
    pedido = _criar(client, fornecedor, produtos).json()
    resp = client.post(
        f"/api/compras/{pedido['id']}/anexos",
        files={"arquivo": ("nf123.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert resp.status_code == 201
    assert resp.json()["categoria"] == "nota_fiscal"


# --------------------------------------------------------------------------- #
# Sugestão automática                                                           #
# --------------------------------------------------------------------------- #


def test_sugestao_compra(db, produtos, galpao):
    # Produto 5338: estoque_minimo 10, sem estoque, sem vendas -> sugerida = 10
    sugestoes = {s.sku_base: s for s in svc.sugestao_compra(db)}
    assert sugestoes["5338"].qtd_sugerida == Decimal("10")
    assert sugestoes["5338"].repor is True

    # Adiciona venda recente de 5 unidades -> media_mensal 5 -> sugerida = 15
    db.add(
        Venda(
            canal="Mercado Livre", id_pedido_canal="V1",
            data_venda=datetime.utcnow() - timedelta(days=2),
            status_erp="Válido", sku_base="5338", qtd=Decimal("5"),
        )
    )
    db.flush()
    sugestoes = {s.sku_base: s for s in svc.sugestao_compra(db)}
    assert sugestoes["5338"].media_mensal == Decimal("5")
    assert sugestoes["5338"].qtd_sugerida == Decimal("15")

    # Com 20 disponíveis em estoque -> sugerida = 5 + 10 - 20 = -5 (não repor)
    estoque_svc.registrar_entrada(
        db, produto_id=produtos[0].id, local_id=galpao.id, qtd=Decimal("20"),
        custo_unitario=Decimal("5"),
    )
    sugestoes = {s.sku_base: s for s in svc.sugestao_compra(db)}
    assert sugestoes["5338"].qtd_sugerida == Decimal("-5")
    assert sugestoes["5338"].repor is False


def test_sugestao_considera_reservado(db, produtos, galpao):
    # disponível 8, reservado 4, mínimo 10, sem vendas -> 0 + 10 + 4 - 8 = 6
    estoque_svc.registrar_entrada(
        db, produto_id=produtos[0].id, local_id=galpao.id, qtd=Decimal("12"),
        custo_unitario=Decimal("5"),
    )
    estoque_svc.reservar(db, produto_id=produtos[0].id, local_id=galpao.id, qtd=Decimal("4"))
    sugestoes = {s.sku_base: s for s in svc.sugestao_compra(db)}
    s = sugestoes["5338"]
    assert s.qtd_atual == Decimal("8")
    assert s.qtd_pendente == Decimal("4")
    assert s.qtd_sugerida == Decimal("6")
