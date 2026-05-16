from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from firenze.services import auth_service


def _mock_session_for_auth(credential, user):
    session = MagicMock()
    first = session.query.return_value.filter.return_value.first
    first.return_value = credential
    session.get.return_value = user
    return session


def test_authenticate_api_credential_returns_user_when_valid(monkeypatch):
    credential = SimpleNamespace(
        user_id=10,
        enabled=True,
        revoked_at=None,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        api_secret_hash="hash",
    )
    user = SimpleNamespace(id=10, enabled=True)
    session = _mock_session_for_auth(credential, user)
    monkeypatch.setattr("firenze.services.auth_service.verify_secret", lambda s, h: True)
    monkeypatch.setattr("firenze.services.auth_service.crud.get_user", lambda db, user_id: user)

    result = auth_service.authenticate_api_credential(session, "key", "secret")

    assert result is not None
    assert result[0].id == 10


def test_authenticate_api_credential_rejects_expired(monkeypatch):
    credential = SimpleNamespace(
        user_id=10,
        enabled=True,
        revoked_at=None,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        api_secret_hash="hash",
    )
    user = SimpleNamespace(id=10, enabled=True)
    session = _mock_session_for_auth(credential, user)
    monkeypatch.setattr("firenze.services.auth_service.verify_secret", lambda s, h: True)
    monkeypatch.setattr("firenze.services.auth_service.crud.get_user", lambda db, user_id: user)

    result = auth_service.authenticate_api_credential(session, "key", "secret")

    assert result is None


def test_authenticate_api_credential_rejects_revoked(monkeypatch):
    credential = SimpleNamespace(
        user_id=10,
        enabled=False,
        revoked_at=datetime.now(timezone.utc),
        expires_at=None,
        api_secret_hash="hash",
    )
    user = SimpleNamespace(id=10, enabled=True)
    session = _mock_session_for_auth(credential, user)
    monkeypatch.setattr("firenze.services.auth_service.verify_secret", lambda s, h: True)
    monkeypatch.setattr("firenze.services.auth_service.crud.get_user", lambda db, user_id: user)

    result = auth_service.authenticate_api_credential(session, "key", "secret")

    assert result is None
