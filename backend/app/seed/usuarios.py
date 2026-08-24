"""Criação das contas de proprietário no primeiro boot.

Existe para que um deploy novo já suba com os donos podendo entrar, sem
precisar de acesso ao banco. Depois disso, o cadastro de usuários é feito pela
tela **Usuários**.

A senha vem de ``SENHA_INICIAL``. Deliberadamente não há valor padrão: uma
senha embutida aqui entraria no histórico do Git e continuaria pública mesmo
depois de trocada no sistema.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import SENHA_INICIAL, USUARIOS_INICIAIS
from app.models.usuario import Usuario
from app.services.auth import hash_senha
from app.services.permissoes import PERFIL_ADMIN

log = logging.getLogger(__name__)


def seed_usuarios(db: Session) -> dict[str, int]:
    """Cria as contas de ``USUARIOS_INICIAIS`` como admin (idempotente).

    Nunca altera a senha de um login que já existe: se a conta está lá, alguém
    pode já ter trocado a senha, e reescrevê-la a cada boot desfaria isso.
    """
    if not USUARIOS_INICIAIS:
        return {"usuarios_iniciais_criados": 0}
    if not SENHA_INICIAL:
        log.warning(
            "USUARIOS_INICIAIS definido (%s) mas SENHA_INICIAL está vazia — "
            "nenhuma conta foi criada. Defina SENHA_INICIAL para que os donos "
            "consigam entrar no primeiro acesso.",
            ", ".join(USUARIOS_INICIAIS),
        )
        return {"usuarios_iniciais_criados": 0}

    criados = 0
    for login in USUARIOS_INICIAIS:
        existe = db.execute(
            select(Usuario).where(Usuario.email == login)
        ).scalar_one_or_none()
        if existe is not None:
            continue
        db.add(
            Usuario(
                email=login,
                nome=login.capitalize(),
                senha_hash=hash_senha(SENHA_INICIAL),
                perfil=PERFIL_ADMIN,
                ativo=True,
            )
        )
        criados += 1
    if criados:
        db.commit()
    return {"usuarios_iniciais_criados": criados}
