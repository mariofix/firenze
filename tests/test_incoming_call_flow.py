"""Happy-path integration test for a full incoming call.

Walks the exact sequence of AGI CURL calls the Asterisk dialplan issues for
an ANI-authenticated caller from DNC check through call teardown:

    [prepago-service] -> DNC -> DID -> client lookup -> credit limit ->
    active-call check -> operator menu -> operator select ->
    insert online call -> assign operator to call -> (call in progress) ->
    deduct credits -> release operator -> delete online call.

Only covers the OK path: no DNC block, service exists, client has credits,
operator is available, no duplicate call, all DB/Redis writes succeed.
"""

from unittest.mock import MagicMock, patch

from firenze.services.call_service import (
    delete_call,
    get_active_call,
    insert_call,
    update_call_operator,
)
from firenze.services.client_service import deduct_credits, lookup
from firenze.services.credit_service import compute_call_limit
from firenze.services.did_service import resolve_did
from firenze.services.dnc_service import check_dnc
from firenze.services.operator_service import (
    get_menu,
    release_operator,
    select_operator,
)


SERVICE_SLUG = "fonotarot-cl"
CALLER_ANI = "56912345678"
DID = "56229402147"
CLIENT_ID = 12345
OPERATOR_NUMBER = 1001
OPERATOR_OPTION = "01"
INITIAL_CREDITS = 1800  # 30 minutes
CALL_DURATION = 600  # 10 minutes billed at hangup


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


@patch("firenze.services.call_service.call_state")
@patch("firenze.services.operator_service.operator_state")
def test_incoming_call_happy_path(mock_op_state, mock_call_state):
    session = MagicMock()
    redis_conn = MagicMock()
    svc = _make_service()
    did_row = _make_did_row(svc)
    client = _make_client(svc)
    ani_row = _make_ani_row()
    operator = _make_operator()
    call_row = _make_call_row()

    # Redis state reads fall back cleanly; writes are observed via the mock.
    mock_op_state.get_state.return_value = None

    query_chain = session.query.return_value.filter_by.return_value
    lock_chain = query_chain.with_for_update.return_value
    order_chain = query_chain.order_by.return_value

    # ----- Step 1: DNC check - caller is not blocked -------------------------
    query_chain.first.return_value = None
    assert check_dnc(session, CALLER_ANI) is False

    # ----- Step 2: DID -> service config -------------------------------------
    query_chain.first.return_value = did_row
    assert resolve_did(session, DID) == {
        "siguiente": "prepago-service",
        "servicio": SERVICE_SLUG,
        "auth_method": "ani",
        "intro_audio": "zvn/intro-fonotarot-cl",
    }

    # ----- Step 3: Client lookup by ANI --------------------------------------
    # lookup() runs 4 consecutive .filter_by().first() calls:
    #   a) Service by slug, b) Client by pin (miss), c) ClientAni match,
    #   d) Client by client_id.
    query_chain.first.side_effect = [svc, None, ani_row, client]
    assert lookup(session, SERVICE_SLUG, CALLER_ANI) == {
        "clientid": CLIENT_ID,
        "segundos": INITIAL_CREDITS,
    }
    query_chain.first.side_effect = None

    # ----- Step 4: Credit limit - pure function, no DB -----------------------
    limit = compute_call_limit(INITIAL_CREDITS)
    assert limit == {"timeout": 1800, "audio": "zvn/saldo/30", "minutes": 30}

    # ----- Step 5: No duplicate active call for this ANI ---------------------
    query_chain.first.return_value = None
    assert get_active_call(session, SERVICE_SLUG, CALLER_ANI) == {
        "llamada_activa": "false"
    }

    # ----- Step 6: Operator menu - one available operator --------------------
    order_chain.all.return_value = [operator]
    menu = get_menu(session, redis_conn)
    assert menu == {"disponibles": 1, "audio_str": "zvn/operator/1001"}

    # ----- Step 7: Caller picks option 01; operator marked busy atomically ---
    lock_chain.first.return_value = operator
    selected = select_operator(
        session,
        mode="option",
        selection=OPERATOR_OPTION,
        redis_conn=redis_conn,
    )
    assert selected == {
        "ok": True,
        "operador_numero": str(OPERATOR_NUMBER),
        "operador_nombre": "Tarotista Demo",
        "operador_telefono": "56911110001",
        "operador_trunk": "didww-miami",
    }
    assert operator.available is False
    # select_operator stamps a real lastcall on Redis.
    select_kwargs = mock_op_state.set_state.call_args.kwargs
    assert select_kwargs["loggedin"] is True
    assert select_kwargs["available"] is False
    assert isinstance(select_kwargs["lastcall"], int)
    assert select_kwargs["lastcall"] > 0
    mock_op_state.reset_mock()

    # ----- Step 8: Insert online call (no duplicate so commit succeeds) ------
    insert_res = insert_call(
        session,
        SERVICE_SLUG,
        CALLER_ANI,
        DID,
        CLIENT_ID,
        operator=0,
        redis_conn=redis_conn,
    )
    assert insert_res == {"ok": True}
    session.add.assert_called_once()
    mock_call_state.set_call.assert_called_once()

    # ----- Step 9: Assign selected operator to the active call record --------
    query_chain.first.return_value = call_row
    assign_res = update_call_operator(
        session, SERVICE_SLUG, CALLER_ANI, OPERATOR_NUMBER, redis_conn
    )
    assert assign_res == {"ok": True}
    assert call_row.operator == OPERATOR_NUMBER
    mock_call_state.update_operator.assert_called_once_with(
        redis_conn, SERVICE_SLUG, CALLER_ANI, OPERATOR_NUMBER
    )

    # ... call in progress ...

    # ----- Step 10: Deduct credits at hangup ---------------------------------
    # deduct_credits: a) Service by slug, b) Client by client_id.
    query_chain.first.side_effect = [svc, client]
    deduct_res = deduct_credits(session, SERVICE_SLUG, CLIENT_ID, CALL_DURATION)
    assert deduct_res == {"ok": True, "remaining": INITIAL_CREDITS - CALL_DURATION}
    assert client.credits == INITIAL_CREDITS - CALL_DURATION
    query_chain.first.side_effect = None

    # ----- Step 11: Release operator, stamps lastcall ------------------------
    query_chain.first.return_value = operator
    release_operator(session, OPERATOR_NUMBER, redis_conn)
    assert operator.available is True
    release_kwargs = mock_op_state.set_state.call_args.kwargs
    assert release_kwargs["loggedin"] is True
    assert release_kwargs["available"] is True
    assert isinstance(release_kwargs["lastcall"], int)
    assert release_kwargs["lastcall"] > 0

    # ----- Step 12: Delete the online call record ----------------------------
    query_chain.first.return_value = call_row
    delete_res = delete_call(session, SERVICE_SLUG, CALLER_ANI, redis_conn)
    assert delete_res == {"ok": True}
    session.delete.assert_called_once_with(call_row)
    mock_call_state.delete_call.assert_called_once_with(
        redis_conn, SERVICE_SLUG, CALLER_ANI
    )
