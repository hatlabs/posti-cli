"""Tests for Posti Pro GraphQL client."""

import json
from unittest.mock import patch, MagicMock

import pytest

from posti_cli.core.client import PostiAPIError
from posti_cli.core.pro.client import ProClient


def _mock_auth(id_token="test-id", role_token="test-role"):
    """Create a mock ProAuth."""
    auth = MagicMock()
    auth.get_headers.return_value = {
        "Authorization": role_token,
        "x-omaposti-token": f"Bearer {id_token}",
    }
    return auth


def _mock_response(body, status=200):
    """Create a mock HTTP response."""
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestProClientExecute:
    def test_sends_graphql_request_with_auth_headers(self):
        auth = _mock_auth()
        client = ProClient(auth)

        response_body = {"data": {"test": "value"}}
        with patch("urllib.request.urlopen",
                   return_value=_mock_response(response_body)) as mock_open:
            result = client.execute("query { test }", {})

            assert result == {"data": {"test": "value"}}
            req = mock_open.call_args[0][0]
            assert req.get_header("Authorization") == "test-role"
            assert req.get_header("X-omaposti-token") == "Bearer test-id"
            assert req.get_header("Content-type") == "application/json"
            body = json.loads(req.data)
            assert body["query"] == "query { test }"

    def test_raises_on_graphql_errors(self):
        auth = _mock_auth()
        client = ProClient(auth)

        error_body = {
            "data": None,
            "errors": [{"message": "Not authorized", "errorType": "Unauthorized"}],
        }
        with patch("urllib.request.urlopen",
                   return_value=_mock_response(error_body)):
            with pytest.raises(PostiAPIError, match="Not authorized"):
                client.execute("query { test }", {})

    def test_retries_on_auth_error(self):
        auth = _mock_auth()
        client = ProClient(auth)

        import urllib.error
        auth_error = urllib.error.HTTPError(
            url="https://graphql.posti.fi/graphql",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=MagicMock(read=lambda: b'{"message": "Unauthorized"}'),
        )
        success_body = {"data": {"test": "retried"}}

        with patch("urllib.request.urlopen",
                   side_effect=[auth_error, _mock_response(success_body)]):
            result = client.execute("query { test }", {})
            assert result == {"data": {"test": "retried"}}
            assert auth.authenticate.call_count == 1

    def test_raises_after_retry_fails(self):
        auth = _mock_auth()
        client = ProClient(auth)

        import urllib.error
        auth_error = urllib.error.HTTPError(
            url="https://graphql.posti.fi/graphql",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=MagicMock(read=lambda: b'{"message": "Unauthorized"}'),
        )

        with patch("urllib.request.urlopen", side_effect=[auth_error, auth_error]):
            with pytest.raises(PostiAPIError):
                client.execute("query { test }", {})
            # Should only retry once, not loop
            assert auth.authenticate.call_count == 1
