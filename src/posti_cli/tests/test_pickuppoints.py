"""Tests for pickup point operations."""

import json
from unittest.mock import patch, MagicMock

from posti_cli.core.client_v2 import PostiV2Client
from posti_cli.core.oauth import OAuthToken
from posti_cli.core import pickuppoints


def _make_client():
    oauth = MagicMock(spec=OAuthToken)
    oauth.access_token = "test-token"
    return PostiV2Client(url="https://api.example.com", oauth=oauth)


def _mock_response(data):
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestSearchPickuppoints:
    def test_sends_post_request(self):
        client = _make_client()
        search_data = {"searchCriteria": {"location": {"postcode": "00100"}}}
        response_data = {"pickupPoints": [{"id": "1", "publicName": "Test Point"}]}

        with patch("urllib.request.urlopen", return_value=_mock_response(response_data)) as mock:
            result = pickuppoints.search_pickuppoints(client, search_data)
            req = mock.call_args[0][0]
            assert req.method == "POST"
            assert "/pickuppoints" in req.full_url
            assert result == response_data

    def test_sends_language_header(self):
        client = _make_client()

        with patch("urllib.request.urlopen", return_value=_mock_response({})) as mock:
            pickuppoints.search_pickuppoints(client, {}, language="sv")
            req = mock.call_args[0][0]
            assert req.get_header("Accept-language") == "sv"


class TestListPickuppoints:
    def test_sends_get_with_country(self):
        client = _make_client()

        with patch("urllib.request.urlopen", return_value=_mock_response({"pickupPoints": []})) as mock:
            pickuppoints.list_pickuppoints(client, "FI")
            req = mock.call_args[0][0]
            assert req.method == "GET"
            assert req.full_url.endswith("/pickuppoints/FI")


class TestGetPickuppoint:
    def test_sends_get_with_country_and_id(self):
        client = _make_client()
        point_data = {"id": "123", "publicName": "Test"}

        with patch("urllib.request.urlopen", return_value=_mock_response(point_data)) as mock:
            result = pickuppoints.get_pickuppoint(client, "FI", "123")
            req = mock.call_args[0][0]
            assert req.method == "GET"
            assert req.full_url.endswith("/pickuppoints/FI/123")
            assert result == point_data
