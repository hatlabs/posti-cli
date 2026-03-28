"""Tests for Posti Pro shipment operations."""

import json
from unittest.mock import MagicMock

import pytest

from posti_cli.core.client import PostiAPIError
from posti_cli.core.pro.shipments import list_shipments, get_shipment


def _mock_client(response_data):
    """Create a mock ProClient that returns given data."""
    client = MagicMock()
    client.execute.return_value = {"data": response_data}
    return client


class TestListShipments:
    def test_returns_feed_items(self):
        client = _mock_client({
            "getOPPROCorporateShipmentFeed": {
                "totalFound": 2,
                "moreResults": False,
                "items": [
                    {
                        "trackingNumbers": ["TRACK001"],
                        "savedDateTime": "2026-03-25T10:00:00Z",
                        "product": {"code": "2351", "name": {"en": "Parcel Connect"}},
                        "receiver": {"name": "Test User", "country": "SE"},
                        "status": {"code": "DELIVERED", "description": [
                            {"lang": "en", "value": "Delivered"},
                        ]},
                    },
                    {
                        "trackingNumbers": ["TRACK002"],
                        "savedDateTime": "2026-03-24T10:00:00Z",
                        "product": {"code": "2103", "name": {"en": "Postipaketti"}},
                        "receiver": {"name": "Other User", "country": "FI"},
                        "status": {"code": "IN_TRANSPORT", "description": [
                            {"lang": "en", "value": "On the way"},
                        ]},
                    },
                ],
            },
        })

        result = list_shipments(client, first=50, offset=0)
        assert result["totalFound"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["trackingNumbers"] == ["TRACK001"]

    def test_passes_query_and_starred_filter(self):
        client = _mock_client({
            "getOPPROCorporateShipmentFeed": {
                "totalFound": 0, "moreResults": False, "items": [],
            },
        })

        list_shipments(client, first=10, offset=0, query_term="hello",
                       starred=True)

        call_args = client.execute.call_args
        variables = call_args[0][1]  # second positional arg
        assert variables["queryTerm"] == "hello"
        assert "STARRED" in variables["extra"]


    def test_raises_on_null_data(self):
        client = MagicMock()
        client.execute.return_value = {"data": None}

        with pytest.raises(PostiAPIError, match="no shipment feed data"):
            list_shipments(client, first=10, offset=0)


class TestGetShipment:
    def test_returns_shipment_detail(self):
        client = _mock_client({
            "getOPPROShipmentInfoV2": [{
                "trackingNumbers": ["00164300796603200188"],
                "weight": {"unit": "kg", "value": 0.35},
                "height": {"unit": "cm", "value": 8.5},
                "length": {"unit": "cm", "value": 26.5},
                "width": {"unit": "cm", "value": 20.0},
                "volume": {"unit": "m3", "value": 0.0045},
                "status": {"code": "DELIVERED"},
                "events": [
                    {"timeStamp": "2026-01-09T11:48:00Z", "eventCode": "LUO"},
                ],
            }],
        })

        result = get_shipment(client, "00164300796603200188")
        assert result["weight"]["value"] == 0.35
        assert result["height"]["value"] == 8.5
        assert len(result["events"]) == 1

    def test_returns_first_item_from_list(self):
        client = _mock_client({
            "getOPPROShipmentInfoV2": [
                {"trackingNumbers": ["FIRST"]},
                {"trackingNumbers": ["SECOND"]},
            ],
        })

        result = get_shipment(client, "FIRST")
        assert result["trackingNumbers"] == ["FIRST"]

    def test_raises_on_null_data(self):
        client = MagicMock()
        client.execute.return_value = {"data": None}

        with pytest.raises(PostiAPIError, match="No shipment found"):
            get_shipment(client, "TRACK123")

    def test_raises_on_empty_result(self):
        client = _mock_client({
            "getOPPROShipmentInfoV2": [],
        })

        with pytest.raises(PostiAPIError, match="No shipment found"):
            get_shipment(client, "NONEXISTENT")
