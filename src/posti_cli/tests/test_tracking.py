"""Tests for public consumer shipment tracking."""

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from posti_cli.core.client import PostiAPIError
from posti_cli.core import tracking
from posti_cli.core.tracking import TrackingClient, track_shipment


def _hit(**over):
    base = {
        "displayId": "LR288565359NL",
        "shipmentType": "LETTER",
        "status": {"main": "IN_TRANSPORT", "subStatus": ["IN_CUSTOMS_PROCESS"]},
        "measurements": {
            "size": "S",
            "weight": {"unit": "kg", "value": "0.35"},
            "length": {"unit": "cm", "value": "20.5"},
            "width": {"unit": "cm", "value": "17.5"},
            "height": {"unit": "cm", "value": "5.0"},
            "volume": {"unit": "m3", "value": "0.001796"},
            "packageQuantity": {"unit": "PC", "value": "1"},
        },
        "events": [],
    }
    base.update(over)
    return base


def _mock_client(hits):
    client = MagicMock()
    client.execute.return_value = {
        "data": {"consumerSearchShipments": {"totalHits": len(hits), "hits": hits}}
    }
    return client


class TestTrackShipment:
    def test_returns_first_hit_with_weight(self):
        client = _mock_client([_hit()])
        result = track_shipment(client, "LR288565359NL")
        assert result["measurements"]["weight"]["value"] == "0.35"
        assert result["status"]["subStatus"] == ["IN_CUSTOMS_PROCESS"]

    def test_sends_tracking_number_as_list_with_public_filter(self):
        client = _mock_client([_hit()])
        track_shipment(client, "LR288565359NL")
        _query, variables = client.execute.call_args[0]
        assert variables["searchTerms"] == ["LR288565359NL"]
        assert variables["type"] == "PUBLIC_SHIPMENTS"

    def test_raises_when_no_hits(self):
        client = _mock_client([])
        with pytest.raises(PostiAPIError, match="No shipment found"):
            track_shipment(client, "DOESNOTEXIST")

    def test_null_data_raises_clean_error_not_crash(self):
        # A valid GraphQL {"data": null} must surface as PostiAPIError, not KeyError.
        client = MagicMock()
        client.execute.return_value = {"data": None}
        with pytest.raises(PostiAPIError, match="No shipment found"):
            track_shipment(client, "X")


class TestExecuteRetry:
    """execute() re-authenticates and retries once on 401/403, never loops."""

    def _authed(self):
        c = TrackingClient()
        c._authorization, c._posti_token = "tok", "id"
        return c

    def test_retries_once_on_401_then_succeeds(self):
        client = self._authed()
        calls, auths = [], []
        def fake_do(query, variables):
            calls.append(1)
            if len(calls) == 1:
                raise PostiAPIError("unauthorized", status_code=401)
            return {"data": {"ok": True}}
        client._do_request = fake_do
        client.authenticate = lambda: auths.append(1)
        assert client.execute("q", {}) == {"data": {"ok": True}}
        assert len(calls) == 2 and len(auths) == 1

    def test_second_401_propagates_without_looping(self):
        client = self._authed()
        calls = []
        def fake_do(query, variables):
            calls.append(1)
            raise PostiAPIError("unauthorized", status_code=401)
        client._do_request = fake_do
        client.authenticate = lambda: None
        with pytest.raises(PostiAPIError):
            client.execute("q", {})
        assert len(calls) == 2  # one retry, then give up

    def test_non_auth_error_not_retried(self):
        client = self._authed()
        calls = []
        def fake_do(query, variables):
            calls.append(1)
            raise PostiAPIError("server error", status_code=500)
        client._do_request = fake_do
        client.authenticate = lambda: None
        with pytest.raises(PostiAPIError):
            client.execute("q", {})
        assert len(calls) == 1


class TestGraphQLErrorBranch:
    """_do_request maps a GraphQL errors payload to PostiAPIError + status."""

    def _authed(self):
        c = TrackingClient()
        c._authorization, c._posti_token = "t", "i"
        return c

    def test_unauthorized_maps_to_status_401(self):
        client = self._authed()
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps(
                {"errors": [{"message": "nope", "errorType": "Unauthorized"}]}).encode())
            with pytest.raises(PostiAPIError) as ei:
                client._do_request("q", {})
        assert ei.value.status_code == 401

    def test_generic_graphql_error_has_no_status(self):
        client = self._authed()
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps(
                {"errors": [{"message": "bad"}]}).encode())
            with pytest.raises(PostiAPIError) as ei:
                client._do_request("q", {})
        assert ei.value.status_code is None


class TestAnonymousAuth:
    """authenticate() maps the token response to the two GraphQL headers."""

    def _token_response(self):
        return json.dumps({
            "id_token": "ID_TOKEN_JWT",
            "role_tokens": [
                {"type": "anonymous", "token": "ROLE_TOKEN_JWT", "email": None},
            ],
        }).encode("utf-8")

    def test_maps_tokens_to_headers(self):
        client = TrackingClient()
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = io.BytesIO(self._token_response())
            client.authenticate()
        assert client._authorization == "ROLE_TOKEN_JWT"
        assert client._posti_token == "ID_TOKEN_JWT"

    def test_role_fallback_to_first_when_no_anonymous(self):
        client = TrackingClient()
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps({
                "id_token": "ID", "role_tokens": [{"type": "guest", "token": "GUEST_TOK"}],
            }).encode("utf-8"))
            client.authenticate()
        assert client._authorization == "GUEST_TOK"

    def test_missing_tokens_raise(self):
        client = TrackingClient()
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = io.BytesIO(
                json.dumps({"id_token": None, "role_tokens": []}).encode("utf-8")
            )
            with pytest.raises(PostiAPIError, match="missing tokens"):
                client.authenticate()

    def test_execute_authenticates_then_posts_with_both_headers(self):
        client = TrackingClient()
        responses = [
            io.BytesIO(self._token_response()),
            io.BytesIO(json.dumps(
                {"data": {"consumerSearchShipments": {"totalHits": 1, "hits": [_hit()]}}}
            ).encode("utf-8")),
        ]
        captured = {}

        def _fake_urlopen(req, timeout=30):
            if req.full_url == tracking.GRAPHQL_URL:
                captured["headers"] = dict(req.headers)
            cm = MagicMock()
            cm.__enter__.return_value = responses.pop(0)
            return cm

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            out = track_shipment(client, "LR288565359NL")

        assert out["displayId"] == "LR288565359NL"
        # urllib title-cases header keys
        assert captured["headers"]["Authorization"] == "ROLE_TOKEN_JWT"
        assert captured["headers"]["X-posti-token"] == "Bearer ID_TOKEN_JWT"
