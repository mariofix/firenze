from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from firenze.api.admin_reports import adminReportsRouter
from firenze.auth import loggedin_user
from firenze.dependencies import get_db


def _build_app(session):
    app = FastAPI()
    app.include_router(adminReportsRouter)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[loggedin_user] = lambda: 1
    return app


@patch("firenze.api.admin_reports.get_client")
def test_admin_system_status_client_credit_preview(mock_get_client):
    mock_get_client.return_value = {"email": "buyer@example.com", "credits": 900}
    client = TestClient(_build_app(MagicMock()))

    response = client.get(
        "/api/v1/admin/system-status/client-credit/preview",
        params={
            "service_slug": "fonotarot-cl",
            "client_id": 12,
            "credits_to_add": 120,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "saved": False,
        "service_slug": "fonotarot-cl",
        "client_id": 12,
        "email": "buyer@example.com",
        "current_credits": 900,
        "credits_to_add": 120,
        "new_credits": 1020,
    }


@patch("firenze.api.admin_reports.apply_purchase")
@patch("firenze.api.admin_reports.get_client")
def test_admin_system_status_client_credit_apply(mock_get_client, mock_apply_purchase):
    mock_get_client.return_value = {"email": "buyer@example.com", "credits": 900}
    mock_apply_purchase.return_value = {
        "credits_before": 900,
        "credits_after": 1020,
    }
    client = TestClient(_build_app(MagicMock()))

    response = client.post(
        "/api/v1/admin/system-status/client-credit",
        json={
            "service_slug": "fonotarot-cl",
            "client_id": 12,
            "credits_to_add": 120,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "saved": True,
        "service_slug": "fonotarot-cl",
        "client_id": 12,
        "email": "buyer@example.com",
        "current_credits": 900,
        "credits_to_add": 120,
        "new_credits": 1020,
    }
    mock_apply_purchase.assert_called_once_with(
        mock_apply_purchase.call_args.args[0],
        service_slug="fonotarot-cl",
        client_id=12,
        credits=120,
    )
