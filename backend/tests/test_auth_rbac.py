"""Testes de autenticação e RBAC (Parte 8.1 — item 1.3/1.4 e 5.1).

Cobre: setup inicial e política de senha; login admin e vendedor; ciclo de
vida do token (válido, expirado, inválido, outra assinatura, token de outro
sistema); e o caso do item 5.1 — quem só tem a ação "ver" em
fiscal_transmitir NÃO transmite NF-e (precisa de "executar").
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from config import settings
from models.painel_vendedor import Usuario as UsuarioVendedor
from models.usuario import Permissao
from models.venda import Vendedor
from services.auth_service import (
    criar_token_admin,
    criar_token_vendedor,
    hash_senha,
    verificar_token,
)

SENHA = "senha@123"


def _token(claims: dict) -> str:
    return jwt.encode(claims, settings.jwt_segredo, algorithm="HS256")


def _token_expirado(admin) -> str:
    return _token(
        {
            "sub": f"adm:{admin.id}",
            "username": admin.username,
            "tipo": "admin",
            "jti": uuid.uuid4().hex,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
    )


class TestSetupInicial:
    def test_setup_primeiro_usuario_cria_admin(self, client):
        res = client.post(
            "/api/v1/auth/setup",
            json={
                "username": "root",
                "nome_completo": "Root Teste",
                "senha": SENHA,
            },
        )
        assert res.status_code == 201
        assert res.json()["data"]["token"]

    def test_setup_senha_curta_rejeitada(self, client):
        res = client.post(
            "/api/v1/auth/setup",
            json={
                "username": "root",
                "nome_completo": "Root Teste",
                "senha": "123",
            },
        )
        assert res.status_code == 400
        assert "mínimo 8" in res.json()["detail"]

    def test_setup_bloqueado_apos_primeiro_usuario(self, client, admin):
        res = client.post(
            "/api/v1/auth/setup",
            json={
                "username": "outro",
                "nome_completo": "Outro",
                "senha": SENHA,
            },
        )
        assert res.status_code == 400
        assert "uma vez" in res.json()["detail"]


class TestLoginAdmin:
    def test_login_sucesso(self, client, admin):
        res = client.post("/api/v1/auth/login", json={"username": "admin", "senha": SENHA})
        assert res.status_code == 200
        body = res.json()
        assert body["error"] is None
        payload = verificar_token(body["data"]["token"])
        assert payload["tipo"] == "admin"
        assert payload["is_admin"] is True

    def test_login_senha_errada(self, client, admin):
        res = client.post("/api/v1/auth/login", json={"username": "admin", "senha": "errada123"})
        assert res.status_code == 401
        assert res.json()["detail"] == "Credenciais inválidas"

    def test_login_usuario_inativo(self, client, admin, db_session):
        admin.ativo = False
        db_session.commit()
        res = client.post("/api/v1/auth/login", json={"username": "admin", "senha": SENHA})
        assert res.status_code == 401


class TestCicloToken:
    def test_me_com_token_valido(self, client, admin, headers_admin):
        res = client.get("/api/v1/auth/me", headers=headers_admin)
        assert res.status_code == 200
        assert res.json()["data"]["username"] == admin.username

    def test_me_sem_token(self, client):
        res = client.get("/api/v1/auth/me")
        assert res.status_code == 401
        assert res.json()["detail"] == "Token não informado"

    def test_me_token_expirado(self, client, admin):
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_token_expirado(admin)}"})
        assert res.status_code == 401
        assert res.json()["detail"] == "Token expirado"

    def test_me_token_invalido(self, client):
        res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nao.e.um.jwt"})
        assert res.status_code == 401
        assert res.json()["detail"] == "Token inválido"

    def test_me_token_com_outra_assinatura(self, client, admin):
        tok = jwt.encode(
            {
                "sub": f"adm:{admin.id}",
                "username": admin.username,
                "tipo": "admin",
                "jti": uuid.uuid4().hex,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "outra-chave",
            algorithm="HS256",
        )
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert res.status_code == 401

    def test_token_vendedor_nao_autentica_no_admin(self, client):
        tok = criar_token_vendedor(uuid.uuid4(), "vendedor1")
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert res.status_code == 401
        assert res.json()["detail"] == "Token inválido para o sistema administrativo"


class TestLoginVendedor:
    def test_login_sucesso_e_token_do_tipo_certo(self, client, db_session):
        vendedor = Vendedor(nome="VENDEDOR TESTE")
        db_session.add(vendedor)
        db_session.commit()
        usuario = UsuarioVendedor(
            vendedor_id=vendedor.id,
            username="vendedor1",
            senha_hash=hash_senha(SENHA),
            ativo=True,
        )
        db_session.add(usuario)
        db_session.commit()

        res = client.post("/api/v1/vendedor/login", json={"username": "vendedor1", "senha": SENHA})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["vendedor_id"] == str(vendedor.id)
        assert data["nome"] == "VENDEDOR TESTE"
        payload = verificar_token(data["token"])
        assert payload["tipo"] == "vendedor"
        assert payload["sub"].startswith("ven:")

    def test_login_vendedor_sem_vendedor_usa_usuario(self, client, db_session):
        # Regressão: a resposta do login tinha chave "nome" duplicada e
        # estourava 500 quando não havia Vendedor vinculado.
        usuario = UsuarioVendedor(
            vendedor_id=uuid.uuid4(),
            username="vendedor2",
            senha_hash=hash_senha(SENHA),
            ativo=True,
        )
        db_session.add(usuario)
        db_session.commit()

        res = client.post("/api/v1/vendedor/login", json={"username": "vendedor2", "senha": SENHA})
        assert res.status_code == 200
        assert res.json()["data"]["nome"] == "vendedor2"


class TestRequirePermission:
    def test_sem_permissao_403(self, client, usuario_simples):
        token = criar_token_admin(usuario_simples)
        res = client.get("/api/v1/clientes/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "não tem permissão" in res.json()["detail"]

    def test_com_permissao_200(self, client, db_session, usuario_simples):
        db_session.add(
            Permissao(
                usuario_id=usuario_simples.id,
                modulo="cadastros_clientes",
                acao="ver",
                permitido=True,
            )
        )
        db_session.commit()
        token = criar_token_admin(usuario_simples)
        res = client.get("/api/v1/clientes/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    def test_admin_sempre_passa(self, client, headers_admin):
        res = client.get("/api/v1/clientes/", headers=headers_admin)
        assert res.status_code == 200


class TestItem51ExecucaoFiscal:
    """Item 5.1: 'ver' em fiscal_transmitir nunca autoriza transmitir —
    apenas a ação 'executar'."""

    def test_so_ver_bloqueia_transmitir(self, client, db_session, usuario_simples):
        db_session.add(
            Permissao(
                usuario_id=usuario_simples.id,
                modulo="fiscal_transmitir",
                acao="ver",
                permitido=True,
            )
        )
        db_session.commit()
        token = criar_token_admin(usuario_simples)
        res = client.post("/api/v1/nfe/999999/transmitir", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

    def test_executar_libera_o_rbac_e_prossegue(self, client, db_session, usuario_simples):
        db_session.add(
            Permissao(
                usuario_id=usuario_simples.id,
                modulo="fiscal_transmitir",
                acao="executar",
                permitido=True,
            )
        )
        db_session.commit()
        token = criar_token_admin(usuario_simples)
        # Passou do RBAC → cai no handler → NF-e inexistente → 404 (e não 403).
        res = client.post("/api/v1/nfe/999999/transmitir", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404
