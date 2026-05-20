from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from firenze.api.clients import clientsRouter
from firenze.auth import loggedin_user
from firenze.dependencies import get_db
from firenze.services.client_service import (
    ClientAlreadyExists,
    ClientNotFound,
    InvalidClientExtraConfig,
)


def _build_app(session, authenticated: bool = True):
    app = FastAPI()
    app.include_router(clientsRouter)
    app.dependency_overrides[get_db] = lambda: session
    if authenticated:
        app.dependency_overrides[loggedin_user] = lambda: 1
    return app


def test_clients_requires_bearer_token():
    app = _build_app(MagicMock(), authenticated=False)
    client = TestClient(app)

    response = client.get("/api/v1/clients/fonotarot-cl/12")

    assert response.status_code == 401


@patch("firenze.api.clients.get_client")
def test_clients_get(mock_get):
    mock_get.return_value = {
        "id": 1,
        "service": "fonotarot-cl",
        "client_id": 12,
        "full_name": "Buyer",
        "email": "buyer@example.com",
        "pin": "12345678",
        "credits": 900,
        "extra_config": {"tarotista_favorita": 7001, "aviso_creditos": 120},
        "anis": [],
        "created_at": "2026-05-20T00:00:00",
        "modified_at": "2026-05-20T00:00:00",
    }
    client = TestClient(_build_app(MagicMock()))

    response = client.get("/api/v1/clients/fonotarot-cl/12")

    assert response.status_code == 200
    assert response.json()["pin"] == "12345678"


@patch("firenze.api.clients.create_client")
def test_clients_create_ignores_phone_number(mock_create):
    mock_create.return_value = {
        "id": 1,
        "service": "fonotarot-cl",
        "client_id": 12,
        "full_name": "Buyer",
        "email": "buyer@example.com",
        "pin": "12345678",
        "credits": 900,
        "extra_config": {"tarotista_favorita": 7001, "aviso_creditos": 120},
        "anis": [],
        "created_at": "2026-05-20T00:00:00",
        "modified_at": "2026-05-20T00:00:00",
    }
    session = MagicMock()
    client = TestClient(_build_app(session))

    response = client.post(
        "/api/v1/clients/fonotarot-cl",
        json={
            "client_id": 12,
            "full_name": "Buyer",
            "email": "buyer@example.com",
            "pin": "12345678",
            "credits": 900,
            "phone_number": "56912345678",
        },
    )

    assert response.status_code == 200
    mock_create.assert_called_once_with(
        session,
        "fonotarot-cl",
        client_id=12,
        full_name="Buyer",
        email="buyer@example.com",
        pin="12345678",
        credits=900,
        extra_config=None,
    )


@patch("firenze.api.clients.update_client_record")
def test_clients_update(mock_update):
    mock_update.return_value = {
        "id": 1,
        "service": "fonotarot-cl",
        "client_id": 12,
        "full_name": "New Name",
        "email": "new@example.com",
        "pin": "22222222",
        "credits": 1000,
        "extra_config": None,
        "anis": [],
        "created_at": "2026-05-20T00:00:00",
        "modified_at": "2026-05-20T00:00:00",
    }
    session = MagicMock()
    client = TestClient(_build_app(session))

    response = client.patch(
        "/api/v1/clients/fonotarot-cl/12",
        json={"full_name": "New Name", "pin": "22222222", "credits": 1000},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "New Name"
    mock_update.assert_called_once_with(
        session,
        "fonotarot-cl",
        client_id=12,
        full_name="New Name",
        email=None,
        pin="22222222",
        credits=1000,
        extra_config=None,
        extra_config_provided=False,
    )


@patch("firenze.api.clients.delete_client")
def test_clients_delete(mock_delete):
    mock_delete.return_value = {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "deleted": True,
    }
    client = TestClient(_build_app(MagicMock()))

    response = client.delete("/api/v1/clients/fonotarot-cl/12")

    assert response.status_code == 200
    assert response.json()["deleted"] is True


@patch("firenze.api.clients.create_client")
def test_clients_create_returns_conflict_when_duplicate(mock_create):
    mock_create.side_effect = ClientAlreadyExists("client already exists")
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/clients/fonotarot-cl",
        json={"client_id": 12, "full_name": "Buyer"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "client already exists"


@patch("firenze.api.clients.get_client")
def test_clients_get_returns_not_found(mock_get):
    mock_get.side_effect = ClientNotFound("missing client")
    client = TestClient(_build_app(MagicMock()))

    response = client.get("/api/v1/clients/fonotarot-cl/12")

    assert response.status_code == 404
    assert response.json()["detail"] == "missing client"


@patch("firenze.api.clients.create_client")
def test_clients_create_rejects_unknown_extra_config_key(mock_create):
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/clients/fonotarot-cl",
        json={
            "client_id": 12,
            "extra_config": {"tier": "vip"},
        },
    )

    assert response.status_code == 422
    mock_create.assert_not_called()


@patch("firenze.api.clients.create_client")
def test_clients_create_rejects_invalid_extra_config_type(mock_create):
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/clients/fonotarot-cl",
        json={
            "client_id": 12,
            "extra_config": {"aviso_creditos": "123"},
        },
    )

    assert response.status_code == 422
    mock_create.assert_not_called()


@patch("firenze.api.clients.create_client")
def test_clients_create_rejects_unknown_favorite_operator(mock_create):
    mock_create.side_effect = InvalidClientExtraConfig(
        "extra_config.tarotista_favorita=7001 does not match any operator number"
    )
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/clients/fonotarot-cl",
        json={
            "client_id": 12,
            "extra_config": {"tarotista_favorita": 7001},
        },
    )

    assert response.status_code == 422
    assert "tarotista_favorita=7001" in response.json()["detail"]


@patch("firenze.api.clients.update_client_record")
def test_clients_update_rejects_unknown_favorite_operator(mock_update):
    mock_update.side_effect = InvalidClientExtraConfig(
        "extra_config.tarotista_favorita=7001 does not match any operator number"
    )
    client = TestClient(_build_app(MagicMock()))

    response = client.patch(
        "/api/v1/clients/fonotarot-cl/12",
        json={
            "extra_config": {"tarotista_favorita": 7001},
        },
    )

    assert response.status_code == 422
    assert "tarotista_favorita=7001" in response.json()["detail"]


@patch("firenze.api.clients.update_client_record")
def test_clients_update_can_clear_extra_config(mock_update):
    mock_update.return_value = {
        "id": 1,
        "service": "fonotarot-cl",
        "client_id": 12,
        "full_name": "Buyer",
        "email": "buyer@example.com",
        "pin": "12345678",
        "credits": 900,
        "extra_config": None,
        "anis": [],
        "created_at": "2026-05-20T00:00:00",
        "modified_at": "2026-05-20T00:00:00",
    }
    session = MagicMock()
    client = TestClient(_build_app(session))

    response = client.patch(
        "/api/v1/clients/fonotarot-cl/12",
        json={"extra_config": None},
    )

    assert response.status_code == 200
    mock_update.assert_called_once_with(
        session,
        "fonotarot-cl",
        client_id=12,
        full_name=None,
        email=None,
        pin=None,
        credits=None,
        extra_config=None,
        extra_config_provided=True,
    )
