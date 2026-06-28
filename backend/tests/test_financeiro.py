"""Testes do serviço/endpoints financeiros (Prioridade 5)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.financeiro import CONTA_ABERTA, ContaPagar, ContaReceber
from app.models.venda import Venda
from app.services import financeiro as svc


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _venda(**kw) -> Venda:
    base = dict(
        canal="Mercado Livre", id_pedido_canal="X", status_erp="Válido",
        sku_base="5338", qtd=Decimal("1"), liquido_recebido=Decimal("0"),
        data_venda=datetime(2026, 6, 20),
    )
    base.update(kw)
    return Venda(**base)


def test_gerar_contas_receber(db):
    vendas = [
        _venda(id_pedido_canal="V1", liquido_recebido=Decimal("80")),
        _venda(id_pedido_canal="V2", canal="Shopee", liquido_recebido=Decimal("43")),
        # cancelada -> não gera recebível
        _venda(id_pedido_canal="V3", status_erp="Cancelado", liquido_recebido=Decimal("0")),
        # líquido zero -> não gera
        _venda(id_pedido_canal="V4", liquido_recebido=Decimal("0")),
    ]
    db.add_all(vendas)
    db.flush()

    criadas = svc.gerar_contas_receber(db, vendas)
    assert criadas == 2

    # idempotente: não duplica
    assert svc.gerar_contas_receber(db, vendas) == 0
    assert db.query(ContaReceber).count() == 2


def test_resumo_financeiro(db):
    # a receber
    db.add_all([
        ContaReceber(canal="Mercado Livre", descricao="V1", valor=Decimal("80"),
                     competencia=date(2026, 6, 20), status=CONTA_ABERTA),
        ContaReceber(canal="Shopee", descricao="V2", valor=Decimal("43"),
                     competencia=date(2026, 6, 21), status=CONTA_ABERTA),
    ])
    # a pagar
    db.add(ContaPagar(descricao="PC#1", valor=Decimal("100"),
                      vencimento=date(2026, 7, 10), status=CONTA_ABERTA))
    db.flush()

    resumo = svc.resumo_financeiro(db)
    assert resumo.a_receber.total == Decimal("123")
    assert resumo.a_pagar.total == Decimal("100")
    assert resumo.saldo_projetado == Decimal("23")

    # filtro por canal
    so_shopee = svc.resumo_financeiro(db, canal="Shopee")
    assert so_shopee.a_receber.total == Decimal("43")


def test_endpoint_financeiro(client, db):
    db.add(ContaReceber(canal="Mercado Livre", descricao="V1", valor=Decimal("80"),
                        competencia=date(2026, 6, 20), status=CONTA_ABERTA))
    db.flush()
    resp = client.get("/api/financeiro")
    assert resp.status_code == 200
    assert resp.json()["a_receber"]["total"] == "80.00"


def test_importacao_gera_financeiro(db, tmp_path):
    from app.parsers.common import CANAL_ML
    from app.parsers.mercadolivre import parse_ml
    from app.seed import seed_sku_map
    from app.services.importacao import importar_vendas
    from tests.factories import build_ml_xlsx

    seed_sku_map(db)
    path, _ = build_ml_xlsx(tmp_path / "ml.xlsx")
    resultado = importar_vendas(
        db, parse_ml(path), CANAL_ML, gerar_financeiro=True
    )
    db.commit()

    # Válidas com líquido != 0: V1 (80), V3-resumo (165), V4 devolução? não.
    # V1 válido 80; V3 resumo válido 165; V4 devolução -> não; V5 válido 32.
    assert resultado.contas_receber >= 1
    assert db.query(ContaReceber).count() == resultado.contas_receber
