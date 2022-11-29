from firenze.config import settings
from fastapi.testclient import TestClient
from firenze import create_app
import pytest


@pytest.fixture(scope="module")
def client():
    settings.SQLALCHEMY_DATABASE_URL = "sqlite:///tests/test.db"
    settings.ENVIRONMENT = "testing"
    settings.AUDIOTEX_DSN = None
    settings.ALLOWED_DOMAINS = '["*"]'
    app = create_app()
    test_client = TestClient(app)
    yield test_client


def test_user_override():
    return 1


@pytest.fixture(scope="module")
def auth_client():
    settings.SQLALCHEMY_DATABASE_URL = "sqlite:///tests/test.db"
    settings.ENVIRONMENT = "testing"
    settings.AUDIOTEX_DSN = None
    settings.ALLOWED_DOMAINS = '["*"]'
    app = create_app()
    test_client = TestClient(app)
    yield test_client
