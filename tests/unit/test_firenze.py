import pytest
from firenze.config import settings


def test_version(client):
    assert settings.VERSION == "1.1.0"


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200


def test_thanks(client):
    response = client.get("/thanks")
    assert response.status_code == 200


def test_create_event_text_html(client):
    response = client.post("/events/test-event/extra-test")
    assert response.status_code == 200


def test_create_event_app_json(client):
    response = client.post(
        "/events/test-event/extra-test", headers={"Content-type": "application/json"}
    )
    assert response.status_code == 200


def test_create_event_errors(client):
    # no event_name
    no_event_name = client.post("/events//extra-test")
    assert no_event_name.status_code == 404

    # no event_extra
    no_event_extra = client.post("/events/test-event/")
    assert no_event_extra.status_code == 404


def test_list_events_no_auth(client):
    new_event = client.get("/events/")
    assert new_event.status_code == 401


# def test_list_events_with_auth(auth_client):
#     new_event = auth_client.get("/events/")
#     assert new_event.status_code == 200
