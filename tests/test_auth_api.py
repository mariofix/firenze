from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from firenze.admin import FirenzeAdmin
from firenze.auth import AdminAuth, authRouter
from firenze.config import settings
from firenze.dependencies import get_db


def _build_app(session):
    app = FastAPI()
    app.include_router(authRouter)
    app.dependency_overrides[get_db] = lambda: session
    return app


def _build_admin_app():
    app = FastAPI()
    FirenzeAdmin(
        app,
        create_engine("sqlite+pysqlite:///:memory:"),
        title="Firenze Admin",
        authentication_backend=AdminAuth(secret_key="test-secret"),
        templates_dir="/home/mariofix/proyectos/zvn-firenze/firenze/templates",
    )
    return app


def test_token_works_with_password_login_enabled(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORD_LOGIN_ENABLED", True)
    monkeypatch.setattr(
        "firenze.auth.auth_service.authenticate_password_user",
        lambda db, login, password: SimpleNamespace(id=7),
    )
    monkeypatch.setattr(
        "firenze.auth.auth_service.create_access_token",
        lambda data, expires_delta=None: "jwt-token",
    )
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"access_token": "jwt-token", "token_type": "bearer"}


def test_token_fails_when_password_login_disabled(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORD_LOGIN_ENABLED", False)
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "secret"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Password login is disabled"


def test_passwordless_request_is_generic_for_unknown_user(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORDLESS_ENABLED", True)
    monkeypatch.setattr(
        "firenze.auth.auth_service.find_user_for_passwordless_identifier",
        lambda db, identifier: None,
    )
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/auth/passwordless/request",
        json={"identifier": "nobody@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_passwordless_request_creates_and_sends_code(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORDLESS_ENABLED", True)
    fake_user = SimpleNamespace(id=10, enabled=True, email="user@example.com")
    monkeypatch.setattr(
        "firenze.auth.auth_service.find_user_for_passwordless_identifier",
        lambda db, identifier: fake_user,
    )
    monkeypatch.setattr(
        "firenze.auth.auth_service.can_issue_passwordless_code",
        lambda db, user, request_ip: True,
    )
    monkeypatch.setattr(
        "firenze.auth.auth_service.create_passwordless_code",
        lambda db, user, request_ip, user_agent: "123456",
    )
    send_mock = MagicMock()
    monkeypatch.setattr(
        "firenze.auth.auth_service.send_passwordless_code_email", send_mock
    )
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/auth/passwordless/request",
        json={"identifier": "user@example.com"},
    )

    assert response.status_code == 200
    send_mock.assert_called_once_with("user@example.com", "123456")


def test_passwordless_verify_returns_token(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORDLESS_ENABLED", True)
    monkeypatch.setattr(
        "firenze.auth.auth_service.verify_passwordless_code",
        lambda db, identifier, code: SimpleNamespace(id=99),
    )
    monkeypatch.setattr(
        "firenze.auth.auth_service.create_access_token",
        lambda data, expires_delta=None: "jwt-token",
    )
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/auth/passwordless/verify",
        json={"identifier": "user@example.com", "code": "123456"},
    )

    assert response.status_code == 200
    assert response.json() == {"access_token": "jwt-token", "token_type": "bearer"}


def test_passwordless_verify_rejects_invalid_code(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORDLESS_ENABLED", True)
    monkeypatch.setattr(
        "firenze.auth.auth_service.verify_passwordless_code",
        lambda db, identifier, code: None,
    )
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/auth/passwordless/verify",
        json={"identifier": "user@example.com", "code": "999999"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired code"


def test_admin_passwordless_request_redirects_to_code_step(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORDLESS_ENABLED", True)
    fake_user = SimpleNamespace(id=11, enabled=True, email="admin@example.com")
    monkeypatch.setattr(
        "firenze.admin.SessionLocal", lambda: SimpleNamespace(close=lambda: None)
    )
    monkeypatch.setattr(
        "firenze.admin.auth_service.find_user_for_passwordless_identifier",
        lambda db, identifier: fake_user,
    )
    monkeypatch.setattr(
        "firenze.admin.auth_service.can_issue_passwordless_code",
        lambda db, user, request_ip: True,
    )
    monkeypatch.setattr(
        "firenze.admin.auth_service.create_passwordless_code",
        lambda db, user, request_ip, user_agent: "123456",
    )
    send_mock = MagicMock()
    monkeypatch.setattr(
        "firenze.admin.auth_service.send_passwordless_code_email", send_mock
    )
    client = TestClient(_build_admin_app())

    response = client.post(
        "/admin/login/passwordless-request",
        data={"username": "admin@example.com"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "step=code" in response.headers["location"]
    assert "identifier=admin%40example.com" in response.headers["location"]
    send_mock.assert_called_once_with("admin@example.com", "123456")


def test_admin_passwordless_verify_sets_session_and_redirects(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PASSWORDLESS_ENABLED", True)
    monkeypatch.setattr(
        "firenze.admin.SessionLocal", lambda: SimpleNamespace(close=lambda: None)
    )
    monkeypatch.setattr(
        "firenze.admin.auth_service.verify_passwordless_code",
        lambda db, identifier, code: SimpleNamespace(id=42, scopes=["admin"]),
    )
    monkeypatch.setattr(
        "firenze.admin.auth_service.has_required_scopes",
        lambda user, scopes: True,
    )
    monkeypatch.setattr(
        "firenze.admin.auth_service.create_access_token",
        lambda data, expires_delta=None: "admin-token",
    )
    client = TestClient(_build_admin_app())

    response = client.post(
        "/admin/login/passwordless-verify",
        data={"identifier": "admin@example.com", "code": "123456"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].endswith("/admin/")
