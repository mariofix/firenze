"""Tests for firenze.services.operator_service — login, logout, availability."""

from unittest.mock import MagicMock, patch

import pytest

from firenze.services.operator_service import (
    OperatorNotFound,
    login,
    logout,
    set_availability,
)


def _make_operator(number=1001, enable_valkey=True, loggedin=False, available=False):
    """Create a mock Operator with sensible defaults."""
    op = MagicMock()
    op.number = number
    op.enable_valkey = enable_valkey
    op.loggedin = loggedin
    op.available = available
    return op


def _mock_session(operator=None):
    """Create a mock Session whose query().filter_by().first() returns `operator`."""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = operator
    return session


class TestLogin:
    def test_sets_loggedin_and_available(self):
        op = _make_operator()
        session = _mock_session(op)

        result = login(session, 1001)

        assert op.loggedin is True
        assert op.available is True
        session.commit.assert_called_once()
        assert result is op

    def test_raises_operator_not_found(self):
        session = _mock_session(None)

        with pytest.raises(OperatorNotFound):
            login(session, 9999)

    @patch("firenze.services.operator_service.operator_state")
    def test_syncs_to_redis_when_valkey_enabled(self, mock_state):
        op = _make_operator(enable_valkey=True)
        session = _mock_session(op)
        redis_conn = MagicMock()

        login(session, 1001, redis_conn)

        mock_state.set_state.assert_called_once_with(
            redis_conn, 1001, loggedin=True, available=True, lastcall=0
        )

    @patch("firenze.services.operator_service.operator_state")
    def test_skips_redis_when_valkey_disabled(self, mock_state):
        op = _make_operator(enable_valkey=False)
        session = _mock_session(op)
        redis_conn = MagicMock()

        login(session, 1001, redis_conn)

        mock_state.set_state.assert_not_called()

    @patch("firenze.services.operator_service.operator_state")
    def test_skips_redis_when_no_connection(self, mock_state):
        op = _make_operator(enable_valkey=True)
        session = _mock_session(op)

        login(session, 1001, redis_conn=None)

        mock_state.set_state.assert_not_called()


class TestLogout:
    def test_clears_loggedin_and_available(self):
        op = _make_operator(loggedin=True, available=True)
        session = _mock_session(op)

        result = logout(session, 1001)

        assert op.loggedin is False
        assert op.available is False
        session.commit.assert_called_once()
        assert result is op

    def test_raises_operator_not_found(self):
        session = _mock_session(None)

        with pytest.raises(OperatorNotFound):
            logout(session, 9999)

    @patch("firenze.services.operator_service.operator_state")
    def test_syncs_to_redis(self, mock_state):
        op = _make_operator(enable_valkey=True)
        session = _mock_session(op)
        redis_conn = MagicMock()

        logout(session, 1001, redis_conn)

        mock_state.set_state.assert_called_once_with(
            redis_conn, 1001, loggedin=False, available=False
        )


class TestSetAvailability:
    def test_sets_available_true(self):
        op = _make_operator(loggedin=True, available=False)
        session = _mock_session(op)

        result = set_availability(session, 1001, True)

        assert op.available is True
        session.commit.assert_called_once()
        assert result is op

    def test_sets_available_false(self):
        op = _make_operator(loggedin=True, available=True)
        session = _mock_session(op)

        result = set_availability(session, 1001, False)

        assert op.available is False

    def test_does_not_change_loggedin(self):
        op = _make_operator(loggedin=True)
        session = _mock_session(op)

        set_availability(session, 1001, False)

        # loggedin should not have been touched — only available
        assert op.loggedin is True

    def test_raises_operator_not_found(self):
        session = _mock_session(None)

        with pytest.raises(OperatorNotFound):
            set_availability(session, 9999, True)

    @patch("firenze.services.operator_service.operator_state")
    def test_syncs_to_redis_with_existing_state(self, mock_state):
        mock_state.get_state.return_value = {
            "loggedin": True,
            "available": False,
            "lastcall": 0,
        }
        op = _make_operator(enable_valkey=True)
        session = _mock_session(op)
        redis_conn = MagicMock()

        set_availability(session, 1001, True, redis_conn)

        mock_state.set_state.assert_called_once_with(
            redis_conn, 1001, loggedin=True, available=True
        )

    @patch("firenze.services.operator_service.operator_state")
    def test_falls_back_to_db_loggedin_when_no_redis_state(self, mock_state):
        mock_state.get_state.return_value = None
        op = _make_operator(enable_valkey=True, loggedin=True)
        session = _mock_session(op)
        redis_conn = MagicMock()

        set_availability(session, 1001, False, redis_conn)

        mock_state.set_state.assert_called_once_with(
            redis_conn, 1001, loggedin=True, available=False
        )
