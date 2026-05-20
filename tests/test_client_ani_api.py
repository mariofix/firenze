from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from firenze.api.clients import clientsRouter
from firenze.auth import loggedin_user
from firenze.dependencies import get_db
from firenze.services.payment_service import AniAlreadyTaken


def _build_app(session, authenticated: bool = True):
    app = FastAPI()
    app.include_router(clientsRouter)
    app.dependency_overrides[get_db] = lambda: session
    if authenticated:
        app.dependency_overrides[loggedin_user] = lambda: 1
    return app


def test_client_ani_requires_bearer_token():
    app = _build_app(MagicMock(), authenticated=False)
    client = TestClient(app)

    response = client.post(
        "/api/v1/clients/fonotarot-cl/12/ani",
        json={"ani": "56912345678"},
    )

    assert response.status_code == 401


@patch("firenze.api.clients.list_client_anis")
def test_client_ani_list(mock_list):
    mock_list.return_value = {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "anis": ["56912345678", "56987654321"],
    }
    app = _build_app(MagicMock())
    client = TestClient(app)

    response = client.get("/api/v1/clients/fonotarot-cl/12/ani")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "anis": ["56912345678", "56987654321"],
    }


@patch("firenze.api.clients.create_client_ani")
def test_client_ani_create(mock_create):
    mock_create.return_value = {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "ani": "56912345678",
        "created": True,
    }
    app = _build_app(MagicMock())
    client = TestClient(app)

    response = client.post(
        "/api/v1/clients/fonotarot-cl/12/ani",
        json={"ani": "56912345678"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "ani": "56912345678",
        "created": True,
    }


@patch("firenze.api.clients.create_client_ani")
def test_client_ani_create_idempotent(mock_create):
    mock_create.return_value = {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "ani": "56911111111",
        "created": False,
    }
    app = _build_app(MagicMock())
    client = TestClient(app)

    response = client.post(
        "/api/v1/clients/fonotarot-cl/12/ani",
        json={"ani": "56911111111"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "ani": "56911111111",
        "created": False,
    }


@patch("firenze.api.clients.create_client_ani")
def test_client_ani_create_returns_conflict_when_ani_taken(mock_create):
    mock_create.side_effect = AniAlreadyTaken("ani already taken")
    app = _build_app(MagicMock())
    client = TestClient(app)

    response = client.post(
        "/api/v1/clients/fonotarot-cl/12/ani",
        json={"ani": "56912345678"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "ani already taken"


@patch("firenze.api.clients.delete_client_ani")
def test_client_ani_delete(mock_delete):
    mock_delete.return_value = {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "ani": "56912345678",
        "deleted": True,
    }
    app = _build_app(MagicMock())
    client = TestClient(app)

    response = client.delete("/api/v1/clients/fonotarot-cl/12/ani/56912345678")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "fonotarot-cl",
        "client_id": 12,
        "ani": "56912345678",
        "deleted": True,
    }
