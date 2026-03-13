"""Tests for delivery estimation."""

import json
from unittest.mock import patch, MagicMock

from posti_cli.core.client_v2 import PostiV2Client
from posti_cli.core.oauth import OAuthToken
from posti_cli.core import estimate


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


class TestEstimateDelivery:
    def test_sends_post_to_estimate(self):
        client = _make_client()
        request_data = {
            "estimate": {
                "time": "2026-03-13T10:00:00Z",
                "origin": {"countryCode": "FI", "postcode": "20100"},
                "destination": {"countryCode": "FI", "postcode": "00100"},
                "product": {"code": "2103"},
            }
        }
        response_data = {"estimates": [{"time": "2026-03-14T16:00:00Z"}]}

        with patch("urllib.request.urlopen", return_value=_mock_response(response_data)) as mock:
            result = estimate.estimate_delivery(client, request_data)
            req = mock.call_args[0][0]
            assert req.method == "POST"
            assert "/estimate" in req.full_url
            assert result == response_data
