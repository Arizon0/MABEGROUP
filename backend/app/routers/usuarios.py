"""Cadastro de usuários — restrito ao perfil ``admin``.

Todas as rotas exigem admin, inclusive as de leitura: a lista de logins do
sistema é informação de segurança, não de operação.

As travas contra auto-bloqueio existem porque o erro é fácil de cometer e caro
de desfazer — sem acesso ao banco, um admin que se rebaixa ou se desativa fica
trancado do lado de fora do próprio sistema.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import (
    SenhaReset,
    UsuarioAdminOut,
    UsuarioCreate,
    UsuarioUpdate,
)
from app.services.auth import hash_senha
from app.services.permissoes import PERFIL_ADMIN, exige_perfil

router = APIRouter(
    prefix="/api/usuarios",
    tags=["usuarios"],
    dependencies=[Depends(exige_perfil(PERFIL_ADMIN))],
)

AdminAtual = Depends(exige_perfil(PERFIL_ADMIN))


def _obter(db: Session, usuario_id: int) -> Usuario:
    alvo = db.get(Usuario, usuario_id)
    if alvo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return alvo


def _quantos_admins_ativos(db: Session, exceto: int | None = None) -> int:
    stmt = select(func.count(Usuario.id)).where(
        Usuario.perfil == PERFIL_ADMIN, Usuario.ativo.is_(True)
    )
    if exceto is not None:
        stmt = stmt.where(Usuario.id != exceto)
    return int(db.execute(stmt).scalar_one())


def _garantir_que_sobra_admin(db: Session, alvo: Usuario) -> None:
    """Impede remover o último administrador ativo do sistema."""
    if alvo.perfil == PERFIL_ADMIN and alvo.ativo:
        if _quantos_admins_ativos(db, exceto=alvo.id) == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Este é o último administrador ativo. Promova outro usuário "
                "antes de rebaixar, desativar ou remover este.",
            )


@router.get("", response_model=list[UsuarioAdminOut])
def listar(db: Session = Depends(get_db)):
    """Usuários cadastrados, em ordem alfabética de login."""
    usuarios = db.execute(select(Usuario).order_by(Usuario.email)).scalars().all()
    return [UsuarioAdminOut.do_modelo(u) for u in usuarios]


@router.post("", response_model=UsuarioAdminOut, status_code=status.HTTP_201_CREATED)
def criar(payload: UsuarioCreate, db: Session = Depends(get_db)):
    """Cria um usuário. O login precisa ser único."""
    existe = db.execute(
        select(Usuario).where(Usuario.email == payload.login)
    ).scalar_one_or_none()
    if existe is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"O login '{payload.login}' já está em uso."
        )
    novo = Usuario(
        email=payload.login,
        nome=payload.nome or payload.login,
        senha_hash=hash_senha(payload.senha),
        perfil=payload.perfil,
        ativo=payload.ativo,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return UsuarioAdminOut.do_modelo(novo)


@router.put("/{usuario_id}", response_model=UsuarioAdminOut)
def atualizar(
    usuario_id: int,
    payload: UsuarioUpdate,
    db: Session = Depends(get_db),
    eu: Usuario = AdminAtual,
):
    """Altera nome, perfil ou situação. O login não muda — crie outro usuário."""
    alvo = _obter(db, usuario_id)

    perdendo_admin = payload.perfil is not None and payload.perfil != alvo.perfil
    desativando = payload.ativo is False and alvo.ativo

    # A única regra é "tem de sobrar um administrador ativo" — e ela vale
    # igualmente para si mesmo e para os outros. Uma proibição separada de
    # mexer na própria conta seria ao mesmo tempo restritiva demais (impediria
    # um sócio de sair quando o outro continua admin) e inútil: como quem age
    # é sempre um admin ativo e diferente do alvo, a contagem nunca chegaria a
    # zero, e a regra do último admin nunca dispararia.
    if perdendo_admin or desativando:
        _garantir_que_sobra_admin(db, alvo)

    if payload.nome is not None:
        alvo.nome = payload.nome
    if payload.perfil is not None:
        alvo.perfil = payload.perfil
    if payload.ativo is not None:
        alvo.ativo = payload.ativo
    db.commit()
    db.refresh(alvo)
    return UsuarioAdminOut.do_modelo(alvo)


@router.put("/{usuario_id}/senha", response_model=UsuarioAdminOut)
def redefinir_senha(
    usuario_id: int, payload: SenhaReset, db: Session = Depends(get_db)
):
    """Define uma senha nova para o usuário (uso: alguém esqueceu a sua).

    Não pede a senha antiga — quem chega aqui já provou ser administrador. Os
    tokens que o usuário já tinha continuam valendo até vencer; para cortar o
    acesso agora, desative a conta.
    """
    alvo = _obter(db, usuario_id)
    alvo.senha_hash = hash_senha(payload.senha_nova)
    db.commit()
    db.refresh(alvo)
    return UsuarioAdminOut.do_modelo(alvo)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(usuario_id: int, db: Session = Depends(get_db), eu: Usuario = AdminAtual):
    """Remove o usuário. Prefira desativar quando ele já operou o sistema."""
    alvo = _obter(db, usuario_id)
    if alvo.id == eu.id:
        # Apagar a conta com que se está logado não tem uso legítimo e destrói
        # o histórico; para sair do sistema, desative ou rebaixe.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Você não pode excluir a própria conta. Desative-a ou rebaixe o perfil.",
        )
    _garantir_que_sobra_admin(db, alvo)
    db.delete(alvo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
