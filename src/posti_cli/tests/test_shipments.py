"""Tests for shipment operations."""

import json
from unittest.mock import patch, MagicMock

from posti_cli.core.client import PostiClient
from posti_cli.core.shipments import create_shipment


def _make_client():
    return PostiClient(
        url="https://api.example.com",
        api_key="test-key",
        customer_number="12345",
    )


def _mock_response(data):
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestCreateShipment:
    def test_defaults_value_per_parcel_to_false(self):
        client = _make_client()
        data = {
            "shipment": {
                "parcels": [
                    {"weight": 2.5, "contents": "Electronics"},
                ]
            }
        }

        with patch("urllib.request.urlopen", return_value=_mock_response([{}])) as mock:
            create_shipment(client, data)
            req = mock.call_args[0][0]
            sent_data = json.loads(req.data)
            assert sent_data["shipment"]["parcels"][0]["valuePerParcel"] is False

    def test_preserves_explicit_value_per_parcel(self):
        client = _make_client()
        data = {
            "shipment": {
                "parcels": [
                    {"weight": 2.5, "valuePerParcel": True},
                ]
            }
        }

        with patch("urllib.request.urlopen", return_value=_mock_response([{}])) as mock:
            create_shipment(client, data)
            req = mock.call_args[0][0]
            sent_data = json.loads(req.data)
            assert sent_data["shipment"]["parcels"][0]["valuePerParcel"] is True

    def test_handles_data_without_shipment_key(self):
        client = _make_client()
        data = {"pdfConfig": {"target1Media": "thermo-225"}}

        with patch("urllib.request.urlopen", return_value=_mock_response([{}])):
            # Should not raise
            create_shipment(client, data)
