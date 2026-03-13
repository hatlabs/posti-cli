"""Tests for Posti 2025-04 API client."""

import json
from unittest.mock import patch, MagicMock

import pytest

from posti_cli.core.client import PostiAPIError
from posti_cli.core.client_v2 import PostiV2Client, make_v2_client
from posti_cli.core.oauth import OAuthToken


def _make_client():
    oauth = MagicMock(spec=OAuthToken)
    oauth.access_token = "test-bearer-token"
    return PostiV2Client(url="https://api.example.com", oauth=oauth)


class TestPostiV2Client:
    def test_sends_bearer_token(self):
        client = _make_client()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            client._request("/test")
            req = mock_urlopen.call_args[0][0]
            assert req.get_header("Authorization") == "Bearer test-bearer-token"

    def test_get_request(self):
        client = _make_client()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"data": "value"}).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client._request("/test")
            assert result == {"data": "value"}

    def test_post_request_with_data(self):
        client = _make_client()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            client._request("/test", method="POST", data={"key": "val"})
            req = mock_urlopen.call_args[0][0]
            assert req.method == "POST"
            assert json.loads(req.data) == {"key": "val"}

    def test_raises_on_error_response(self):
        client = _make_client()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "errorCode": "UNAUTHORIZED",
            "message": "Invalid token",
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(PostiAPIError, match="Invalid token"):
                client._request("/test")

    def test_extra_headers(self):
        client = _make_client()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({}).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            client._request("/test", headers_extra={"Accept-Language": "fi"})
            req = mock_urlopen.call_args[0][0]
            assert req.get_header("Accept-language") == "fi"


class TestMakeV2Client:
    def test_default_url(self):
        with patch.dict("os.environ", {
            "POSTI_OAUTH_CLIENT_ID": "id",
            "POSTI_OAUTH_CLIENT_SECRET": "secret",
        }):
            with patch("posti_cli.core.oauth.OAuthToken._fetch_token"):
                client = make_v2_client()
                assert client.url == "https://gateway.posti.fi/2025-04"

    def test_custom_url(self):
        with patch.dict("os.environ", {
            "POSTI_OAUTH_CLIENT_ID": "id",
            "POSTI_OAUTH_CLIENT_SECRET": "secret",
        }):
            with patch("posti_cli.core.oauth.OAuthToken._fetch_token"):
                client = make_v2_client(url="https://custom.example.com/")
                assert client.url == "https://custom.example.com"
