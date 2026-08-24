"""Testes da trava de autenticação.

O teste que mais importa aqui é ``test_todo_endpoint_de_api_exige_token``: ele
varre as rotas registradas na aplicação e cobra 401 de cada uma. Um endpoint
novo que entre sem proteção quebra esse teste — que é exatamente o mecanismo
que faltava quando a API inteira estava aberta.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.routing import APIRoute

from app import config
from app.config import JWT_ALGORITHM, SECRET_KEY, validar_configuracao
from app.main import app
from app.services.auth import criar_access_token

# Rotas que devem responder sem token, e por quê.
PUBLICAS = {
    "/health",                 # sonda de saúde do orquestrador
    "/api/auth/login",         # é onde o token nasce
    "/api/admin/setup",        # bootstrap, travado pelo próprio SETUP_TOKEN
}


def _rotas_de_api() -> list[tuple[str, str]]:
    """(método, caminho) de toda rota /api que deveria exigir token."""
    pares: list[tuple[str, str]] = []
    for rota in app.routes:
        if not isinstance(rota, APIRoute):
            continue
        if not rota.path.startswith("/api") or rota.path in PUBLICAS:
            continue
        metodo = next(iter(sorted(rota.methods - {"HEAD", "OPTIONS"})), None)
        if metodo:
            pares.append((metodo, rota.path))
    return pares


def _preencher(caminho: str) -> str:
    """Troca {parametros} por um valor qualquer — o 401 vem antes de usá-los."""
    partes = []
    for trecho in caminho.split("/"):
        partes.append("1" if trecho.startswith("{") else trecho)
    return "/".join(partes)


class TestTrava:
    def test_ha_rotas_protegidas_para_verificar(self):
        """Guarda contra o teste abaixo passar por varrer uma lista vazia."""
        assert len(_rotas_de_api()) > 20

    @pytest.mark.parametrize("metodo,caminho", _rotas_de_api())
    def test_todo_endpoint_de_api_exige_token(self, client_anonimo, metodo, caminho):
        resposta = client_anonimo.request(metodo, _preencher(caminho), json={})
        assert resposta.status_code == 401, (
            f"{metodo} {caminho} respondeu {resposta.status_code} sem token — "
            "esse endpoint está exposto."
        )

    def test_health_continua_publico(self, client_anonimo):
        """O orquestrador precisa da sonda sem credencial para saber se subiu."""
        assert client_anonimo.get("/health").status_code == 200

    def test_setup_e_publico_mas_travado_pelo_proprio_token(self, client_anonimo):
        resposta = client_anonimo.post("/api/admin/setup")
        assert resposta.status_code == 403  # não 401: a trava dele é o SETUP_TOKEN

    def test_com_token_valido_o_endpoint_responde(self, client):
        assert client.get("/api/dashboard").status_code == 200


class TestToken:
    def test_token_ilegivel_e_recusado(self, client_anonimo):
        client_anonimo.headers["Authorization"] = "Bearer nao-e-um-jwt"
        assert client_anonimo.get("/api/dashboard").status_code == 401

    def test_token_sem_prefixo_bearer_e_recusado(self, client_anonimo, token):
        client_anonimo.headers["Authorization"] = token
        assert client_anonimo.get("/api/dashboard").status_code == 401

    def test_token_expirado_e_recusado(self, client_anonimo, usuario):
        vencido = jwt.encode(
            {
                "sub": str(usuario.id),
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        client_anonimo.headers["Authorization"] = f"Bearer {vencido}"
        assert client_anonimo.get("/api/dashboard").status_code == 401

    def test_token_assinado_com_outra_chave_e_recusado(self, client_anonimo, usuario):
        """É isto que a SECRET_KEY padrão em produção jogaria fora."""
        forjado = jwt.encode(
            {
                "sub": str(usuario.id),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "outra-chave-qualquer",
            algorithm=JWT_ALGORITHM,
        )
        client_anonimo.headers["Authorization"] = f"Bearer {forjado}"
        assert client_anonimo.get("/api/dashboard").status_code == 401

    def test_token_de_usuario_inexistente_e_recusado(self, client_anonimo):
        orfao = jwt.encode(
            {"sub": "9999", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        client_anonimo.headers["Authorization"] = f"Bearer {orfao}"
        assert client_anonimo.get("/api/dashboard").status_code == 401

    def test_usuario_desativado_perde_o_acesso_com_o_token_na_mao(
        self, client_anonimo, db, usuario
    ):
        """Desativar a conta corta o acesso na hora, sem esperar o token vencer."""
        valido = criar_access_token(usuario)
        client_anonimo.headers["Authorization"] = f"Bearer {valido}"
        assert client_anonimo.get("/api/dashboard").status_code == 200
        usuario.ativo = False
        db.commit()
        assert client_anonimo.get("/api/dashboard").status_code == 401


class TestLogin:
    def test_login_devolve_token_que_funciona(self, client_anonimo, usuario):
        resposta = client_anonimo.post(
            "/api/auth/login",
            json={"email": config.ADMIN_EMAIL, "senha": config.ADMIN_SENHA},
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["token_type"] == "bearer"
        assert corpo["usuario"]["email"] == config.ADMIN_EMAIL

        client_anonimo.headers["Authorization"] = f"Bearer {corpo['access_token']}"
        assert client_anonimo.get("/api/dashboard").status_code == 200

    def test_senha_errada_nao_entra(self, client_anonimo, usuario):
        resposta = client_anonimo.post(
            "/api/auth/login",
            json={"email": config.ADMIN_EMAIL, "senha": "chute"},
        )
        assert resposta.status_code == 401

    def test_email_inexistente_nao_entra(self, client_anonimo, usuario):
        resposta = client_anonimo.post(
            "/api/auth/login",
            json={"email": "ninguem@exemplo.com", "senha": config.ADMIN_SENHA},
        )
        assert resposta.status_code == 401

    def test_email_e_case_insensitive(self, client_anonimo, usuario):
        resposta = client_anonimo.post(
            "/api/auth/login",
            json={"email": config.ADMIN_EMAIL.upper(), "senha": config.ADMIN_SENHA},
        )
        assert resposta.status_code == 200

    def test_conta_desativada_nao_entra(self, client_anonimo, db, usuario):
        usuario.ativo = False
        db.commit()
        resposta = client_anonimo.post(
            "/api/auth/login",
            json={"email": config.ADMIN_EMAIL, "senha": config.ADMIN_SENHA},
        )
        assert resposta.status_code == 401

    def test_me_identifica_o_dono_do_token(self, client):
        corpo = client.get("/api/auth/me").json()
        assert corpo["email"] == config.ADMIN_EMAIL
        assert corpo["perfil"] == "admin"

    def test_me_sem_token_e_recusado(self, client_anonimo):
        assert client_anonimo.get("/api/auth/me").status_code == 401


class TestTrocaDeSenha:
    def test_troca_a_senha_e_a_nova_passa_a_valer(self, client, client_anonimo):
        resposta = client.post(
            "/api/auth/senha",
            json={"senha_atual": config.ADMIN_SENHA, "senha_nova": "uma-senha-longa"},
        )
        assert resposta.status_code == 200

        entrar = lambda senha: client_anonimo.post(  # noqa: E731
            "/api/auth/login", json={"email": config.ADMIN_EMAIL, "senha": senha}
        ).status_code
        assert entrar("uma-senha-longa") == 200
        assert entrar(config.ADMIN_SENHA) == 401

    def test_exige_a_senha_atual(self, client):
        """Um token vazado não pode virar sequestro da conta."""
        resposta = client.post(
            "/api/auth/senha",
            json={"senha_atual": "chute", "senha_nova": "uma-senha-longa"},
        )
        assert resposta.status_code == 400

    def test_recusa_senha_nova_curta(self, client):
        resposta = client.post(
            "/api/auth/senha",
            json={"senha_atual": config.ADMIN_SENHA, "senha_nova": "curta"},
        )
        assert resposta.status_code == 422

    def test_sem_token_nao_troca(self, client_anonimo):
        resposta = client_anonimo.post(
            "/api/auth/senha",
            json={"senha_atual": "x", "senha_nova": "uma-senha-longa"},
        )
        assert resposta.status_code == 401


class TestValidacaoDeConfiguracao:
    """Em desenvolvimento os padrões são convenientes; em produção, fatais."""

    def test_em_sqlite_nao_reclama(self, monkeypatch):
        monkeypatch.setattr(config, "DATABASE_URL", "sqlite:///./erp.db")
        monkeypatch.setattr(config, "SECRET_KEY", config.SECRET_KEY_PADRAO)
        monkeypatch.setattr(config, "ADMIN_SENHA", config.ADMIN_SENHA_PADRAO)
        assert validar_configuracao() == []

    def test_secret_key_padrao_em_producao_derruba_o_boot(self, monkeypatch):
        monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u:p@host/db")
        monkeypatch.setattr(config, "SECRET_KEY", config.SECRET_KEY_PADRAO)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            validar_configuracao()

    def test_senha_padrao_em_producao_so_avisa(self, monkeypatch):
        monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u:p@host/db")
        monkeypatch.setattr(config, "SECRET_KEY", "uma-chave-aleatoria-de-verdade")
        monkeypatch.setattr(config, "ADMIN_SENHA", config.ADMIN_SENHA_PADRAO)
        avisos = validar_configuracao()
        assert len(avisos) == 1 and "ADMIN_SENHA" in avisos[0]

    def test_producao_configurada_nao_gera_aviso(self, monkeypatch):
        monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u:p@host/db")
        monkeypatch.setattr(config, "SECRET_KEY", "uma-chave-aleatoria-de-verdade")
        monkeypatch.setattr(config, "ADMIN_SENHA", "outra-senha-forte")
        assert validar_configuracao() == []
