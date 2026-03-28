"""Tests for Posti Pro SSO authentication."""

import json
import time
from http.cookiejar import CookieJar
from unittest.mock import patch, MagicMock, call
from urllib.parse import urlencode

import pytest

from posti_cli.core.client import PostiAPIError
from posti_cli.core.pro.auth import ProAuth


def _mock_response(status=200, url="https://example.com", body=b"",
                   headers=None):
    """Create a mock HTTP response."""
    resp = MagicMock()
    resp.status = status
    resp.geturl.return_value = url
    resp.url = url
    resp.read.return_value = body
    resp.info.return_value = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    if headers:
        resp.getheader = lambda h, d=None: headers.get(h, d)
    return resp


class TestProAuthTokenCaching:
    def test_tokens_cached_within_ttl(self):
        auth = ProAuth("user@test.fi", "pass123")
        auth._id_token = "cached-id"
        auth._role_token = "cached-role"
        auth._expires_at = time.time() + 3000

        headers = auth.get_headers()
        assert headers["Authorization"] == "cached-role"
        assert headers["x-omaposti-token"] == "Bearer cached-id"

    def test_tokens_refreshed_when_expired(self):
        auth = ProAuth("user@test.fi", "pass123")
        auth._id_token = "old-id"
        auth._role_token = "old-role"
        auth._expires_at = time.time() - 1

        with patch.object(auth, "authenticate") as mock_auth:
            def set_new_tokens():
                auth._id_token = "new-id"
                auth._role_token = "new-role"
                auth._expires_at = time.time() + 3600
            mock_auth.side_effect = set_new_tokens

            headers = auth.get_headers()
            mock_auth.assert_called_once()
            assert headers["Authorization"] == "new-role"
            assert headers["x-omaposti-token"] == "Bearer new-id"

    def test_authenticate_called_when_no_tokens(self):
        auth = ProAuth("user@test.fi", "pass123")

        with patch.object(auth, "authenticate") as mock_auth:
            def set_tokens():
                auth._id_token = "fresh-id"
                auth._role_token = "fresh-role"
                auth._expires_at = time.time() + 3600
            mock_auth.side_effect = set_tokens

            headers = auth.get_headers()
            mock_auth.assert_called_once()


class TestProAuthTokenExchange:
    def test_token_v2_parses_response(self):
        auth = ProAuth("user@test.fi", "pass123")
        token_response = {
            "id_token": "the-id-token",
            "access_token": "the-access-token",
            "refresh_token": "the-refresh-token",
            "role_tokens": [{
                "type": "corporate",
                "identityId": "abc-123",
                "token": "the-role-token",
                "businessId": "FI12345678",
            }],
        }
        auth._parse_token_response(token_response)
        assert auth._id_token == "the-id-token"
        assert auth._role_token == "the-role-token"
        assert auth._expires_at > time.time()

    def test_token_v2_raises_on_missing_role_tokens(self):
        auth = ProAuth("user@test.fi", "pass123")
        with pytest.raises(PostiAPIError, match="No role tokens"):
            auth._parse_token_response({"id_token": "x", "role_tokens": []})

    def test_token_v2_raises_on_missing_id_token(self):
        auth = ProAuth("user@test.fi", "pass123")
        with pytest.raises(PostiAPIError, match="id_token"):
            auth._parse_token_response({"role_tokens": [{"token": "x"}]})


class TestExtractSessionId:
    def test_extracts_from_path(self):
        url = "https://todentaminen.posti.fi/uas/authn/83446950-6ee1-472c-a2c6-c718a88bce14/view?_id=83446950-6ee1-472c-a2c6-c718a88bce14&entityID=5b05bc63"
        assert ProAuth._extract_session_id(url) == "83446950-6ee1-472c-a2c6-c718a88bce14"

    def test_extracts_from_query_param(self):
        url = "https://todentaminen.posti.fi/uas/something?_id=abc-123&other=val"
        assert ProAuth._extract_session_id(url) == "abc-123"

    def test_returns_none_for_unknown_url(self):
        assert ProAuth._extract_session_id("https://example.com/other") is None


class TestExtractCode:
    def test_extracts_code_from_redirect(self):
        url = "https://pro.posti.fi/?code=eyJjdHkiOiJKV1Qi&other=val"
        assert ProAuth._extract_code(url) == "eyJjdHkiOiJKV1Qi"

    def test_returns_none_when_no_code(self):
        assert ProAuth._extract_code("https://pro.posti.fi/") is None


class TestMakeProAuth:
    def test_from_env_vars(self):
        from posti_cli.core.pro.auth import make_pro_auth
        with patch.dict("os.environ", {
            "POSTI_PRO_USERNAME": "env-user",
            "POSTI_PRO_PASSWORD": "env-pass",
        }):
            auth = make_pro_auth()
            assert auth.username == "env-user"
            assert auth.password == "env-pass"

    def test_raises_when_missing_username(self):
        from posti_cli.core.pro.auth import make_pro_auth
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(PostiAPIError, match="POSTI_PRO_USERNAME"):
                make_pro_auth()

    def test_raises_when_missing_password(self):
        from posti_cli.core.pro.auth import make_pro_auth
        with patch.dict("os.environ", {"POSTI_PRO_USERNAME": "u"}, clear=True):
            with pytest.raises(PostiAPIError, match="POSTI_PRO_PASSWORD"):
                make_pro_auth()
