"""Happy-path HTTP test for a full incoming call.

Exercises the same 12-step dialplan CURL sequence as
``test_incoming_call_flow.py`` but through the FastAPI router, so the
request shapes (query strings, form bodies, path params, status codes,
response JSON) match exactly what Asterisk's ``CURL()`` issues.

Mounts a minimal app with only ``agiRouter`` and overrides ``get_db`` /
``get_redis`` so no real MySQL or Redis is touched.
"""

from hashlib import sha256
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from firenze.api.agi import agiRouter
from firenze.dependencies import get_db, get_redis

SERVICE_SLUG = "fonotarot-cl"
CALLER_ANI = "56912345678"
DID = "56229402147"
CLIENT_ID = 12345
OPERATOR_NUMBER = 1001
OPERATOR_OPTION = "01"
INITIAL_CREDITS = 1800
CALL_DURATION = 600


def _make_service():
    svc = MagicMock()
    svc.id = 1
    svc.slug = SERVICE_SLUG
    svc.auth_method = "ani"
    svc.intro_audio = "zvn/intro-fonotarot-cl"
    return svc


def _make_did_row(svc):
    row = MagicMock()
    row.asterisk_context = "prepago-service"
    row.service = svc
    return row


def _make_client(svc):
    client = MagicMock()
    client.service_id = svc.id
    client.client_id = CLIENT_ID
    client.credits = INITIAL_CREDITS
    return client


def _make_ani_row():
    row = MagicMock()
    row.client_id = CLIENT_ID
    return row


def _make_operator():
    op = MagicMock()
    op.number = OPERATOR_NUMBER
    op.option = OPERATOR_OPTION
    op.name = "Tarotista Demo"
    op.loggedin = True
    op.available = True
    op.enable_valkey = True
    op.audio_file = "zvn/operator/1001"
    phone = MagicMock()
    phone.number = "56911110001"
    phone.trunk = "didww-miami"
    phone.contact = True
    phone.enabled = True
    op.numbers = [phone]
    return op


def _make_call_row():
    call = MagicMock()
    call.service = SERVICE_SLUG
    call.ani = CALLER_ANI
    call.did = DID
    call.client_id = CLIENT_ID
    call.operator = 0
    return call


def _build_app(session, redis_conn):
    app = FastAPI()
    app.include_router(agiRouter)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_redis] = lambda: redis_conn
    return app


@patch("firenze.api.agi.resolve_did")
@patch("firenze.api.agi.send_measurement_event")
def test_agi_did_lookup_sends_measurement_event_found(mock_measurement, mock_resolve_did):
    session = MagicMock()
    redis_conn = MagicMock()
    mock_resolve_did.return_value = {
        "siguiente": "prepago-service",
        "servicio": SERVICE_SLUG,
        "auth_method": "ani",
        "intro_audio": "zvn/intro-fonotarot-cl",
    }

    client_http = TestClient(_build_app(session, redis_conn))
    uniqueid = "1748812345.1001"
    channel = "SIP/provider-0000002a"
    r = client_http.get(f"/agi/services/did/{DID}", params={"uniqueid": uniqueid, "channel": channel})

    assert r.status_code == 200
    assert r.json()["servicio"] == SERVICE_SLUG
    mock_measurement.assert_called_once()
    event_name, payload = mock_measurement.call_args.args
    event_client_id = mock_measurement.call_args.kwargs["client_id"]
    assert event_name == "service_lookup"
    assert payload["query_did"] == DID
    assert payload["assigned_context"] == "prepago-service"
    assert payload["service"] == SERVICE_SLUG
    assert payload["found"] is True
    assert isinstance(payload["query_duration_ms"], float)
    assert payload["query_duration_ms"] >= 0
    assert event_client_id == sha256(uniqueid.encode("utf-8")).hexdigest()


@patch("firenze.api.agi.resolve_did")
@patch("firenze.api.agi.send_measurement_event")
def test_agi_did_lookup_sends_measurement_event_not_found(mock_measurement, mock_resolve_did):
    session = MagicMock()
    redis_conn = MagicMock()
    mock_resolve_did.return_value = {
        "siguiente": "",
        "servicio": "",
        "auth_method": "",
        "intro_audio": "",
    }

    client_http = TestClient(_build_app(session, redis_conn))
    r = client_http.get(f"/agi/services/did/{DID}")

    assert r.status_code == 200
    assert r.json()["servicio"] == ""
    mock_measurement.assert_called_once()
    event_name, payload = mock_measurement.call_args.args
    assert event_name == "service_lookup"
    assert payload["query_did"] == DID
    assert payload["assigned_context"] == ""
    assert payload["service"] == ""
    assert payload["found"] is False
    assert isinstance(payload["query_duration_ms"], float)
    assert payload["query_duration_ms"] >= 0
    assert mock_measurement.call_args.kwargs["client_id"] is None


@patch("firenze.api.agi.resolve_did")
@patch("firenze.api.agi.send_measurement_event")
def test_agi_did_lookup_uses_channel_hash_when_uniqueid_missing(mock_measurement, mock_resolve_did):
    session = MagicMock()
    redis_conn = MagicMock()
    channel = "SIP/provider-00000099"
    mock_resolve_did.return_value = {
        "siguiente": "prepago-service",
        "servicio": SERVICE_SLUG,
        "auth_method": "ani",
        "intro_audio": "zvn/intro-fonotarot-cl",
    }

    client_http = TestClient(_build_app(session, redis_conn))
    r = client_http.get(f"/agi/services/did/{DID}", params={"channel": channel})

    assert r.status_code == 200
    assert mock_measurement.call_args.kwargs["client_id"] == sha256(channel.encode("utf-8")).hexdigest()


@patch("firenze.api.agi.compute_call_limit")
@patch("firenze.api.agi.send_measurement_event")
def test_agi_credit_limit_sends_measurement_event(mock_measurement, mock_compute_call_limit):
    session = MagicMock()
    redis_conn = MagicMock()
    uniqueid = "1748812345.2002"
    mock_compute_call_limit.return_value = {"timeout": 1800, "audio": "zvn/saldo/30", "minutes": 30}

    client_http = TestClient(_build_app(session, redis_conn))
    r = client_http.get("/agi/credits/limit", params={"seconds": 1800, "uniqueid": uniqueid})

    assert r.status_code == 200
    assert r.json() == {"timeout": 1800, "audio": "zvn/saldo/30", "minutes": 30}
    mock_measurement.assert_called_once()
    event_name, payload = mock_measurement.call_args.args
    assert event_name == "credit_compute"
    assert payload["requested_seconds"] == 1800
    assert payload["timeout"] == 1800
    assert payload["audio"] == "zvn/saldo/30"
    assert payload["minutes"] == 30
    assert isinstance(payload["query_duration_ms"], float)
    assert payload["query_duration_ms"] >= 0
    assert mock_measurement.call_args.kwargs["client_id"] == sha256(uniqueid.encode("utf-8")).hexdigest()


@patch("firenze.services.call_service.call_state")
@patch("firenze.services.operator_service.operator_state")
@patch("firenze.services.client_service.maybe_send_post_call_email")
def test_incoming_call_happy_path_http(mock_post_call_email, mock_op_state, mock_call_state):
    session = MagicMock()
    redis_conn = MagicMock()
    svc = _make_service()
    did_row = _make_did_row(svc)
    client = _make_client(svc)
    ani_row = _make_ani_row()
    operator = _make_operator()
    call_row = _make_call_row()

    mock_op_state.get_state.return_value = None

    query_chain = session.query.return_value.filter_by.return_value
    order_chain = query_chain.order_by.return_value
    filter_lock_chain = session.query.return_value.filter.return_value.with_for_update.return_value

    # All the .filter_by().first() results the dialplan sequence triggers,
    # in order across the 12 HTTP requests below.
    query_chain.first.side_effect = [
        None,  # 1: /agi/dnc/{ani}              - check_dnc
        did_row,  # 2: /agi/services/did/{did}     - resolve_did
        svc,  # 3a: /agi/clients/lookup        - update_ani_stats _get_service
        None,  # 3b: update_ani_stats ANI miss
        svc,  # 3c: /agi/clients/lookup        - _get_service
        ani_row,  # 3d: ClientAni match
        client,  # 3e: Client by client_id
        None,  # 5: /agi/calls/online/.../?     - get_active_call
        call_row,  # 9: /agi/calls/online/.../assign - update_call_operator
        svc,  # 10a: /agi/clients/.../deduct   - _get_service
        client,  # 10b: Client by client_id
        operator,  # 11: /agi/operators/{n}/release - _get_operator
        call_row,  # 12: /agi/calls/online/.../close - delete_call
    ]
    query_chain.all.return_value = [operator]  # 6: operator menu
    order_chain.all.return_value = [operator]  # 6: operator menu
    filter_lock_chain.first.return_value = operator  # 7: operator select (option mode)

    client_http = TestClient(_build_app(session, redis_conn))

    # ----- Step 1: DNC check -------------------------------------------------
    r = client_http.get(f"/agi/dnc/{CALLER_ANI}")
    assert r.status_code == 200
    assert r.json() == {"dnc": "NO"}

    # ----- Step 2: DID -> service config -------------------------------------
    r = client_http.get(f"/agi/services/did/{DID}")
    assert r.status_code == 200
    assert r.json() == {
        "siguiente": "prepago-service",
        "servicio": SERVICE_SLUG,
        "auth_method": "ani",
        "intro_audio": "zvn/intro-fonotarot-cl",
    }

    # ----- Step 3: Client lookup by ANI --------------------------------------
    r = client_http.get(
        "/agi/clients/lookup",
        params={"service": SERVICE_SLUG, "identifier": CALLER_ANI},
    )
    assert r.status_code == 200
    assert r.json() == {
        "clientid": CLIENT_ID,
        "segundos": INITIAL_CREDITS,
        "timeout": 1800,
        "audio": "zvn/saldo/30",
        "minutes": 30,
    }

    # ----- Step 4: Credit limit - pure function ------------------------------
    r = client_http.get("/agi/credits/limit", params={"seconds": INITIAL_CREDITS})
    assert r.status_code == 200
    assert r.json() == {"timeout": 1800, "audio": "zvn/saldo/30", "minutes": 30}

    # ----- Step 5: No duplicate active call ----------------------------------
    r = client_http.get(f"/agi/calls/online/{SERVICE_SLUG}/{CALLER_ANI}")
    assert r.status_code == 200
    assert r.json() == {"llamada_activa": "false"}

    # ----- Step 6: Operator menu ---------------------------------------------
    r = client_http.get("/agi/operators/menu")
    assert r.status_code == 200
    assert r.json() == {"disponibles": 1, "audio_str": "zvn/operator/1001"}

    # ----- Step 7: Caller picks option 01 ------------------------------------
    r = client_http.post(
        "/agi/operators/select",
        data={"mode": "option", "selection": OPERATOR_OPTION},
    )
    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "operador_numero": str(OPERATOR_NUMBER),
        "operador_nombre": "Tarotista Demo",
        "operador_telefono": "56911110001",
        "operador_trunk": "didww-miami",
    }
    assert operator.available is False
    select_kwargs = mock_op_state.set_state.call_args.kwargs
    assert select_kwargs["available"] is False
    assert isinstance(select_kwargs["lastcall"], int)
    assert select_kwargs["lastcall"] > 0
    mock_op_state.reset_mock()

    # ----- Step 8: Insert online call ----------------------------------------
    r = client_http.post(
        "/agi/calls/online",
        data={
            "service": SERVICE_SLUG,
            "ani": CALLER_ANI,
            "did": DID,
            "client_id": CLIENT_ID,
            "operator": 0,
        },
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    session.add.assert_called_once()
    mock_call_state.set_call.assert_called_once()

    # ----- Step 9: Assign operator to call record ----------------------------
    r = client_http.post(
        f"/agi/calls/online/{SERVICE_SLUG}/{CALLER_ANI}/assign",
        data={"operator": OPERATOR_NUMBER},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert call_row.operator == OPERATOR_NUMBER
    mock_call_state.update_operator.assert_called_once_with(redis_conn, SERVICE_SLUG, CALLER_ANI, OPERATOR_NUMBER)

    # ... call in progress ...

    # ----- Step 10: Deduct credits at hangup ---------------------------------
    r = client_http.post(
        f"/agi/clients/{SERVICE_SLUG}/{CLIENT_ID}/deduct",
        data={"seconds": CALL_DURATION},
    )
    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "remaining": INITIAL_CREDITS - CALL_DURATION,
        "before": INITIAL_CREDITS,
        "client_id": CLIENT_ID,
        "service": SERVICE_SLUG,
    }
    assert client.credits == INITIAL_CREDITS - CALL_DURATION
    mock_post_call_email.assert_called_once_with(client, svc)

    # ----- Step 11: Release operator -----------------------------------------
    r = client_http.post(f"/agi/operators/{OPERATOR_NUMBER}/release")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert operator.available is True
    release_kwargs = mock_op_state.set_state.call_args.kwargs
    assert release_kwargs["available"] is True
    assert isinstance(release_kwargs["lastcall"], int)
    assert release_kwargs["lastcall"] > 0

    # ----- Step 12: Delete online call ---------------------------------------
    # Asterisk CURL() can only send POST with a body, so the close endpoint
    # is POST with a dummy ``_=1`` field.
    r = client_http.post(
        f"/agi/calls/online/{SERVICE_SLUG}/{CALLER_ANI}/close",
        data={"_": "1"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    session.delete.assert_called_once_with(call_row)
    mock_call_state.delete_call.assert_called_once_with(redis_conn, SERVICE_SLUG, CALLER_ANI)
