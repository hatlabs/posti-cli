"""Tests for labelless sending operations."""

import json
from unittest.mock import patch, MagicMock

from posti_cli.core.client_v2 import PostiV2Client
from posti_cli.core.oauth import OAuthToken
from posti_cli.core import labelless


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


class TestCreateSendingCode:
    def test_sends_post_to_labelless(self):
        client = _make_client()
        request_data = {"searchCriteria": {"trackingNumber": "JJFI12345678"}}
        response_data = {"shipments": [{"trackingNumber": "JJFI12345678", "sendingCode": "ABC123"}]}

        with patch("urllib.request.urlopen", return_value=_mock_response(response_data)) as mock:
            result = labelless.create_sending_code(client, request_data)
            req = mock.call_args[0][0]
            assert req.method == "POST"
            assert "/labelless" in req.full_url
            assert result == response_data


class TestGetByTrackingNumber:
    def test_sends_get_with_tracking(self):
        client = _make_client()
        response_data = {"shipments": [{"trackingNumber": "JJFI12345678", "sendingCode": "ABC123"}]}

        with patch("urllib.request.urlopen", return_value=_mock_response(response_data)) as mock:
            result = labelless.get_by_tracking_number(client, "JJFI12345678")
            req = mock.call_args[0][0]
            assert req.method == "GET"
            assert req.full_url.endswith("/labelless/JJFI12345678")
            assert result == response_data


class TestGetBySendingCode:
    def test_sends_get_with_code(self):
        client = _make_client()
        response_data = {"shipments": [{"trackingNumber": "JJFI12345678", "sendingCode": "ABC123"}]}

        with patch("urllib.request.urlopen", return_value=_mock_response(response_data)) as mock:
            result = labelless.get_by_sending_code(client, "ABC123")
            req = mock.call_args[0][0]
            assert req.method == "GET"
            assert req.full_url.endswith("/labelless/shipment/ABC123")
            assert result == response_data
