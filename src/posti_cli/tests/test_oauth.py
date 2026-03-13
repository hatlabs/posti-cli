"""Tests for OAuth 2.0 token handling."""

import json
import time
from unittest.mock import patch, MagicMock

import pytest

from posti_cli.core.oauth import OAuthToken, make_oauth_token
from posti_cli.core.client import PostiAPIError


class TestOAuthToken:
    def test_fetches_token_on_first_access(self):
        token = OAuthToken("client-id", "client-secret")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "test-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert token.access_token == "test-token-123"

    def test_caches_token_until_expiry(self):
        token = OAuthToken("client-id", "client-secret")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "cached-token",
            "expires_in": 3600,
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            _ = token.access_token
            _ = token.access_token
            assert mock_urlopen.call_count == 1

    def test_refreshes_expired_token(self):
        token = OAuthToken("client-id", "client-secret")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "token-1",
            "expires_in": 3600,
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            _ = token.access_token

        # Force expiry
        token._expires_at = time.time() - 1

        mock_response2 = MagicMock()
        mock_response2.read.return_value = json.dumps({
            "access_token": "token-2",
            "expires_in": 3600,
        }).encode("utf-8")
        mock_response2.__enter__ = lambda s: s
        mock_response2.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response2):
            assert token.access_token == "token-2"

    def test_raises_on_http_error(self):
        token = OAuthToken("client-id", "client-secret")

        import urllib.error
        error = urllib.error.HTTPError(
            url="https://example.com",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=MagicMock(read=lambda: b'{"error": "invalid_client"}'),
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(PostiAPIError, match="OAuth token request failed"):
                _ = token.access_token


class TestMakeOAuthToken:
    def test_from_explicit_args(self):
        token = make_oauth_token("my-id", "my-secret")
        assert token.client_id == "my-id"
        assert token.client_secret == "my-secret"

    def test_from_env_vars(self):
        with patch.dict("os.environ", {
            "POSTI_OAUTH_CLIENT_ID": "env-id",
            "POSTI_OAUTH_CLIENT_SECRET": "env-secret",
        }):
            token = make_oauth_token()
            assert token.client_id == "env-id"
            assert token.client_secret == "env-secret"

    def test_raises_when_missing_client_id(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(PostiAPIError, match="POSTI_OAUTH_CLIENT_ID"):
                make_oauth_token()

    def test_raises_when_missing_client_secret(self):
        with patch.dict("os.environ", {"POSTI_OAUTH_CLIENT_ID": "id"}, clear=True):
            with pytest.raises(PostiAPIError, match="POSTI_OAUTH_CLIENT_SECRET"):
                make_oauth_token()
