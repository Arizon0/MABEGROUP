"""Cadastro de usuários e perfis de acesso.

Dois grupos de garantia aqui:

1. **Quem pode o quê** — o viewer lê mas não escreve, o analista opera mas não
   mexe em usuários, o admin faz tudo. Verificado contra a API, não contra a
   função de permissão isolada, porque o que importa é o que o endpoint responde.
2. **Ninguém se tranca do lado de fora** — o sistema recusa remover o último
   administrador ativo, e recusa que um admin rebaixe ou desative a si mesmo.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.usuario import Usuario
from app.services.auth import criar_access_token, hash_senha
from app.services.permissoes import (
    PERFIL_ADMIN,
    PERFIL_ANALISTA,
    PERFIL_VIEWER,
    pode,
)

SENHA = "uma-senha-de-teste"


def criar_usuario(db, login: str, perfil: str, ativo: bool = True) -> Usuario:
    usuario = Usuario(
        email=login,
        nome=login.capitalize(),
        senha_hash=hash_senha(SENHA),
        perfil=perfil,
        ativo=ativo,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@pytest.fixture()
def como(db):
    """Devolve um cliente autenticado como um usuário de determinado perfil."""
    abertos: dict[str, TestClient] = {}

    def _abrir(perfil: str, login: str | None = None) -> TestClient:
        chave = login or f"{perfil}@teste"
        if chave not in abertos:
            usuario = criar_usuario(db, chave, perfil)
            app.dependency_overrides[get_db] = lambda: db
            cliente = TestClient(app)
            cliente.headers["Authorization"] = f"Bearer {criar_access_token(usuario)}"
            abertos[chave] = cliente
        return abertos[chave]

    try:
        yield _abrir
    finally:
        app.dependency_overrides.clear()


class TestHierarquia:
    def test_admin_alcanca_todos_os_niveis(self):
        assert pode(PERFIL_ADMIN, PERFIL_VIEWER)
        assert pode(PERFIL_ADMIN, PERFIL_ANALISTA)
        assert pode(PERFIL_ADMIN, PERFIL_ADMIN)

    def test_analista_nao_alcanca_admin(self):
        assert pode(PERFIL_ANALISTA, PERFIL_VIEWER)
        assert not pode(PERFIL_ANALISTA, PERFIL_ADMIN)

    def test_viewer_so_alcanca_a_si_mesmo(self):
        assert pode(PERFIL_VIEWER, PERFIL_VIEWER)
        assert not pode(PERFIL_VIEWER, PERFIL_ANALISTA)

    def test_perfil_desconhecido_cai_no_menor_nivel(self):
        """Lixo na coluna vira perda de acesso, nunca ganho."""
        assert not pode("superusuario", PERFIL_ANALISTA)
        assert not pode(None, PERFIL_ANALISTA)
        assert pode("QUALQUER-COISA", PERFIL_VIEWER)

    def test_perfil_ignora_caixa_e_espacos(self):
        assert pode("  ADMIN  ", PERFIL_ADMIN)


class TestViewerSoLe:
    def test_viewer_le_os_relatorios(self, como):
        assert como(PERFIL_VIEWER).get("/api/dashboard").status_code == 200
        assert como(PERFIL_VIEWER).get("/api/vendas/analise").status_code == 200

    def test_viewer_nao_altera_nada(self, como):
        cliente = como(PERFIL_VIEWER)
        resposta = cliente.put(
            "/api/vendas/aliquotas", json={"ano": 2026, "mes": 7, "aliquota_pct": "8"}
        )
        assert resposta.status_code == 403
        assert "somente leitura" in resposta.json()["detail"]

    def test_viewer_nao_importa_planilha(self, como):
        resposta = como(PERFIL_VIEWER).post("/api/importar/ml")
        assert resposta.status_code == 403

    def test_viewer_nao_exclui(self, como):
        assert como(PERFIL_VIEWER).delete("/api/vendas/ads/1").status_code == 403

    def test_analista_escreve(self, como):
        resposta = como(PERFIL_ANALISTA).put(
            "/api/vendas/aliquotas", json={"ano": 2026, "mes": 7, "aliquota_pct": "8"}
        )
        assert resposta.status_code == 200


class TestSoAdminGerenciaUsuarios:
    def test_viewer_nao_lista_usuarios(self, como):
        assert como(PERFIL_VIEWER).get("/api/usuarios").status_code == 403

    def test_analista_nao_lista_usuarios(self, como):
        """A lista de logins é informação de segurança, não de operação."""
        resposta = como(PERFIL_ANALISTA).get("/api/usuarios")
        assert resposta.status_code == 403
        assert "admin" in resposta.json()["detail"]

    def test_analista_nao_cria_usuario(self, como):
        resposta = como(PERFIL_ANALISTA).post(
            "/api/usuarios",
            json={"login": "novo", "senha": "uma-senha-longa", "perfil": "admin"},
        )
        assert resposta.status_code == 403

    def test_sem_token_nao_chega_perto(self, client_anonimo):
        assert client_anonimo.get("/api/usuarios").status_code == 401

    def test_admin_lista(self, como):
        resposta = como(PERFIL_ADMIN).get("/api/usuarios")
        assert resposta.status_code == 200
        assert any(u["perfil"] == PERFIL_ADMIN for u in resposta.json())


class TestCrudDeUsuarios:
    def test_cria_e_o_novo_usuario_consegue_entrar(self, como, client_anonimo):
        criado = como(PERFIL_ADMIN).post(
            "/api/usuarios",
            json={
                "login": "Canaveze",
                "nome": "Canaveze",
                "senha": "uma-senha-longa",
                "perfil": PERFIL_ADMIN,
            },
        )
        assert criado.status_code == 201
        # Login é normalizado para minúsculas ao gravar.
        assert criado.json()["login"] == "canaveze"

        entrada = client_anonimo.post(
            "/api/auth/login", json={"email": "Canaveze", "senha": "uma-senha-longa"}
        )
        assert entrada.status_code == 200
        assert entrada.json()["usuario"]["perfil"] == PERFIL_ADMIN

    def test_login_duplicado_e_recusado(self, como):
        cliente = como(PERFIL_ADMIN)
        corpo = {"login": "repetido", "senha": "uma-senha-longa"}
        assert cliente.post("/api/usuarios", json=corpo).status_code == 201
        conflito = cliente.post("/api/usuarios", json=corpo)
        assert conflito.status_code == 409
        assert "já está em uso" in conflito.json()["detail"]

    def test_login_duplicado_ignora_caixa(self, como):
        cliente = como(PERFIL_ADMIN)
        cliente.post("/api/usuarios", json={"login": "Fulano", "senha": "uma-senha-longa"})
        conflito = cliente.post(
            "/api/usuarios", json={"login": "FULANO", "senha": "uma-senha-longa"}
        )
        assert conflito.status_code == 409

    def test_senha_curta_e_recusada(self, como):
        resposta = como(PERFIL_ADMIN).post(
            "/api/usuarios", json={"login": "curto", "senha": "1234567"}
        )
        assert resposta.status_code == 422

    def test_perfil_invalido_e_recusado(self, como):
        resposta = como(PERFIL_ADMIN).post(
            "/api/usuarios",
            json={"login": "x", "senha": "uma-senha-longa", "perfil": "deus"},
        )
        assert resposta.status_code == 422

    def test_perfil_padrao_e_o_mais_restrito(self, como):
        """Quem esquecer de escolher o perfil não cria um admin sem querer."""
        criado = como(PERFIL_ADMIN).post(
            "/api/usuarios", json={"login": "semperfil", "senha": "uma-senha-longa"}
        )
        assert criado.json()["perfil"] == PERFIL_VIEWER

    def test_altera_nome_perfil_e_situacao(self, como, db):
        cliente = como(PERFIL_ADMIN)
        alvo = criar_usuario(db, "alvo", PERFIL_VIEWER)
        resposta = cliente.put(
            f"/api/usuarios/{alvo.id}",
            json={"nome": "Nome Novo", "perfil": PERFIL_ANALISTA, "ativo": False},
        )
        assert resposta.status_code == 200
        assert resposta.json() == {
            "id": alvo.id, "login": "alvo", "nome": "Nome Novo",
            "perfil": PERFIL_ANALISTA, "ativo": False,
        }

    def test_campo_ausente_fica_como_esta(self, como, db):
        cliente = como(PERFIL_ADMIN)
        alvo = criar_usuario(db, "alvo", PERFIL_ANALISTA)
        resposta = cliente.put(f"/api/usuarios/{alvo.id}", json={"nome": "Só o nome"})
        assert resposta.json()["perfil"] == PERFIL_ANALISTA
        assert resposta.json()["ativo"] is True

    def test_admin_redefine_a_senha_de_outro(self, como, db, client_anonimo):
        cliente = como(PERFIL_ADMIN)
        alvo = criar_usuario(db, "esqueceu", PERFIL_ANALISTA)
        resposta = cliente.put(
            f"/api/usuarios/{alvo.id}/senha", json={"senha_nova": "senha-redefinida"}
        )
        assert resposta.status_code == 200

        entrar = lambda senha: client_anonimo.post(  # noqa: E731
            "/api/auth/login", json={"email": "esqueceu", "senha": senha}
        ).status_code
        assert entrar("senha-redefinida") == 200
        assert entrar(SENHA) == 401

    def test_exclui_usuario(self, como, db):
        cliente = como(PERFIL_ADMIN)
        alvo = criar_usuario(db, "descartavel", PERFIL_VIEWER)
        assert cliente.delete(f"/api/usuarios/{alvo.id}").status_code == 204
        assert cliente.delete(f"/api/usuarios/{alvo.id}").status_code == 404

    def test_usuario_inexistente_da_404(self, como):
        assert como(PERFIL_ADMIN).put("/api/usuarios/999", json={}).status_code == 404

    def test_desativar_corta_o_login_na_hora(self, como, db, client_anonimo):
        cliente = como(PERFIL_ADMIN)
        alvo = criar_usuario(db, "afastado", PERFIL_ANALISTA)
        cliente.put(f"/api/usuarios/{alvo.id}", json={"ativo": False})
        resposta = client_anonimo.post(
            "/api/auth/login", json={"email": "afastado", "senha": SENHA}
        )
        assert resposta.status_code == 401


class TestNinguemSeTranca:
    """Tem de sobrar sempre um administrador ativo — inclusive contra si mesmo."""

    def test_unico_admin_ativo_nao_se_rebaixa(self, como, db):
        cliente = como(PERFIL_ADMIN, login="dono")
        eu = db.query(Usuario).filter_by(email="dono").one()
        resposta = cliente.put(f"/api/usuarios/{eu.id}", json={"perfil": PERFIL_VIEWER})
        assert resposta.status_code == 400
        assert "último administrador ativo" in resposta.json()["detail"]

    def test_unico_admin_ativo_nao_se_desativa(self, como, db):
        cliente = como(PERFIL_ADMIN, login="dono")
        eu = db.query(Usuario).filter_by(email="dono").one()
        assert cliente.put(f"/api/usuarios/{eu.id}", json={"ativo": False}).status_code == 400

    def test_admin_inativo_nao_conta_como_substituto(self, como, db):
        """Uma conta de admin desativada não segura o sistema se o ativo sair."""
        cliente = como(PERFIL_ADMIN, login="dono")
        criar_usuario(db, "admin-afastado", PERFIL_ADMIN, ativo=False)
        eu = db.query(Usuario).filter_by(email="dono").one()
        resposta = cliente.put(f"/api/usuarios/{eu.id}", json={"perfil": PERFIL_VIEWER})
        assert resposta.status_code == 400

    def test_com_outro_admin_ativo_o_socio_pode_sair(self, como, db):
        """Dois donos: um pode se rebaixar sem trancar ninguém do lado de fora."""
        cliente = como(PERFIL_ADMIN, login="dono")
        criar_usuario(db, "socio", PERFIL_ADMIN)
        eu = db.query(Usuario).filter_by(email="dono").one()
        resposta = cliente.put(f"/api/usuarios/{eu.id}", json={"perfil": PERFIL_ANALISTA})
        assert resposta.status_code == 200
        assert resposta.json()["perfil"] == PERFIL_ANALISTA

    def test_nao_remove_o_ultimo_admin_ativo(self, como, db):
        cliente = como(PERFIL_ADMIN, login="dono")
        substituto = criar_usuario(db, "substituto", PERFIL_ADMIN)
        # Com dois admins ativos, remover um é permitido.
        assert cliente.delete(f"/api/usuarios/{substituto.id}").status_code == 204

    def test_nunca_exclui_a_propria_conta(self, como, db):
        """Mesmo havendo outro admin: apagar a conta logada não tem uso legítimo."""
        cliente = como(PERFIL_ADMIN, login="dono")
        criar_usuario(db, "socio", PERFIL_ADMIN)
        eu = db.query(Usuario).filter_by(email="dono").one()
        resposta = cliente.delete(f"/api/usuarios/{eu.id}")
        assert resposta.status_code == 400
        assert "própria conta" in resposta.json()["detail"]

    def test_rebaixar_outro_usuario_nao_admin_e_livre(self, como, db):
        cliente = como(PERFIL_ADMIN, login="dono")
        alvo = criar_usuario(db, "estagiario", PERFIL_ANALISTA)
        resposta = cliente.put(f"/api/usuarios/{alvo.id}", json={"perfil": PERFIL_VIEWER})
        assert resposta.status_code == 200


class TestSeedDosDonos:
    """As contas de proprietário criadas no primeiro boot, via ambiente."""

    def _semear(self, db, monkeypatch, logins, senha):
        from app.seed import usuarios as seed_mod

        monkeypatch.setattr(seed_mod, "USUARIOS_INICIAIS", logins)
        monkeypatch.setattr(seed_mod, "SENHA_INICIAL", senha)
        return seed_mod.seed_usuarios(db)

    def test_cria_os_donos_como_admin(self, db, monkeypatch, client_anonimo):
        resultado = self._semear(db, monkeypatch, ["arizono", "canaveze"], "senha-dos-donos")
        assert resultado == {"usuarios_iniciais_criados": 2}

        for login in ("arizono", "Canaveze"):  # login não diferencia caixa
            resposta = client_anonimo.post(
                "/api/auth/login", json={"email": login, "senha": "senha-dos-donos"}
            )
            assert resposta.status_code == 200, login
            assert resposta.json()["usuario"]["perfil"] == PERFIL_ADMIN

    def test_e_idempotente(self, db, monkeypatch):
        self._semear(db, monkeypatch, ["arizono"], "senha-dos-donos")
        segunda = self._semear(db, monkeypatch, ["arizono"], "senha-dos-donos")
        assert segunda == {"usuarios_iniciais_criados": 0}

    def test_nao_reescreve_senha_ja_trocada(self, db, monkeypatch, client_anonimo):
        """Rodar o seed de novo não pode ressuscitar a senha inicial."""
        self._semear(db, monkeypatch, ["arizono"], "senha-dos-donos")
        dono = db.query(Usuario).filter_by(email="arizono").one()
        dono.senha_hash = hash_senha("a-que-ele-escolheu")
        db.commit()

        self._semear(db, monkeypatch, ["arizono"], "senha-dos-donos")

        entrar = lambda senha: client_anonimo.post(  # noqa: E731
            "/api/auth/login", json={"email": "arizono", "senha": senha}
        ).status_code
        assert entrar("a-que-ele-escolheu") == 200
        assert entrar("senha-dos-donos") == 401

    def test_sem_senha_no_ambiente_nao_cria_conta_alguma(self, db, monkeypatch):
        """Melhor nenhuma conta do que uma conta com senha inventada."""
        resultado = self._semear(db, monkeypatch, ["arizono", "canaveze"], "")
        assert resultado == {"usuarios_iniciais_criados": 0}
        assert db.query(Usuario).filter_by(email="arizono").one_or_none() is None

    def test_sem_lista_de_logins_nao_faz_nada(self, db, monkeypatch):
        assert self._semear(db, monkeypatch, [], "senha-dos-donos") == {
            "usuarios_iniciais_criados": 0
        }
