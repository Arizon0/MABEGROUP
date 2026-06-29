"""Testes de hashing de senha (login/JWT foram removidos do app)."""
from __future__ import annotations

from app.services.auth import hash_senha, verificar_senha


def test_hash_e_verificacao_de_senha():
    h = hash_senha("segredo123")
    assert h != "segredo123"
    assert verificar_senha("segredo123", h)
    assert not verificar_senha("errada", h)
