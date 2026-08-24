"""Perfis de acesso e o que cada um pode fazer.

Três níveis, do menor para o maior poder:

``viewer``    lê tudo, não altera nada. É o perfil de quem só consulta números.
``analista``  opera o sistema — importa planilhas, edita cadastros, lança
              despesas. Não mexe em usuários.
``admin``     tudo, incluindo criar, editar e remover usuários.

A verificação acontece **no servidor**. Esconder um item de menu é conveniência
de interface, nunca controle de acesso: quem souber a URL da API chega lá do
mesmo jeito.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.models.usuario import Usuario
from app.services.auth import get_current_user

PERFIL_VIEWER = "viewer"
PERFIL_ANALISTA = "analista"
PERFIL_ADMIN = "admin"

# Ordem de poder. Um perfil desconhecido cai no menor nível: se alguém gravar
# lixo nessa coluna, o resultado é perda de acesso, não ganho.
HIERARQUIA = {PERFIL_VIEWER: 0, PERFIL_ANALISTA: 1, PERFIL_ADMIN: 2}
PERFIS = tuple(HIERARQUIA)

# Métodos que não alteram nada e por isso o viewer pode usar.
METODOS_DE_LEITURA = frozenset({"GET", "HEAD", "OPTIONS"})


def nivel(perfil: str | None) -> int:
    return HIERARQUIA.get((perfil or "").strip().lower(), 0)


def pode(perfil: str | None, minimo: str) -> bool:
    """True quando ``perfil`` alcança ao menos ``minimo``."""
    return nivel(perfil) >= nivel(minimo)


def _negar(mensagem: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=mensagem)


def exige_perfil(minimo: str):
    """Dependência que cobra um perfil mínimo do usuário autenticado."""

    def _verificar(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if not pode(usuario.perfil, minimo):
            raise _negar(
                f"Esta ação exige perfil '{minimo}'. O seu é '{usuario.perfil}'."
            )
        return usuario

    return _verificar


def autorizar_escrita(
    request: Request, usuario: Usuario = Depends(get_current_user)
) -> Usuario:
    """Deixa o viewer ler, mas barra qualquer método que altere dados.

    Aplicada no registro dos routers, cobre por método em vez de por endpoint —
    então um endpoint de escrita novo já nasce fechado para o perfil de leitura,
    sem ninguém precisar lembrar de anotá-lo.
    """
    if request.method in METODOS_DE_LEITURA:
        return usuario
    if nivel(usuario.perfil) < nivel(PERFIL_ANALISTA):
        raise _negar("Seu perfil é somente leitura.")
    return usuario
